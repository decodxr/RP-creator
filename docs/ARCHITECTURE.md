# Arquitetura e decisões

## Escolha da stack

| Alternativa | Vantagem | Custo | Decisão |
|---|---|---|---|
| FastAPI + Python | Validação, documentação de API, async, ecossistema local de IA | Ambiente Python | Escolhido |
| Node/TypeScript em todo o projeto | Uma linguagem com o frontend | Requer runtime JS no PC e mais dependências | Não necessário para este núcleo |
| React + bundler | Componentização para uma UI muito maior | Build e instalação separados | Interface JS/CSS nativa evita isso |
| Electron/Godot/Unity | Janela nativa/ambiente 3D | Empacotamento e implementação maiores | UI web local cobre a experiência narrativa |
| SQLite + FTS5 | Sem serviço externo, transações, busca textual | Um escritor por vez | Escolhido, modo WAL |
| Banco vetorial dedicado | ANN, melhor latência em milhões de vetores | Outro processo/serviço | Cosseno exato em lotes por enquanto |
| Obsidian como único banco | Legível e editável | Sem transação/índices robustos | Projeção + importação controlada |

## Fluxo de um turno

1. A API valida o corpo e o token local; o engine serializa ações por campanha.
2. Checa `request_id`: reenvios do mesmo turno devolvem o resultado anterior; reutilizar ID com outra mensagem é erro.
3. Verifica se jogador e NPC estão no mesmo local.
4. Busca apenas memórias válidas cuja audiência contém NPC ou `*`. Históricos de outros NPCs nunca são enviados.
5. Combina FTS5/BM25, importância e cosseno opcional; monta contexto limitado em caracteres, até 12 turnos recentes.
6. Chama o modelo para narrativa; chama novamente para extração estruturada da fala do jogador.
7. Valida esquema, trecho literal de evidência, métricas, limites, locais e datas. O modelo não escolhe a audiência de novos fatos.
8. Salva turno, relações, memórias e promessas na mesma transação. Falha da narrativa não salva turno; falha da extração salva narrativa com aviso.
9. Indexa embeddings pendentes, consolida quando aplicável e atualiza a projeção Markdown.

O prompt é uma restrição comportamental, não uma prova de verdade. O banco nunca adota localização/hora arbitrária produzida pelo modelo. Fatos extraídos continuam sendo interpretações, revisáveis pelo criador. O chat bruto persiste mesmo quando uma mensagem não gera memória relevante.

## Dados

- `campaigns`: premissa, jogador, horário, lugar, relógio e revisão do mundo.
- `locations`, `npcs`: locais, perfis, humor, rotinas e objetivos.
- `relationships`: arestas direcionais e nove métricas entre −100 e +100.
- `turns`: mensagem, resposta, memória fornecida ao contexto, aviso e chave idempotente.
- `memories`: tipos, audiência, entidades, evidência, fonte, fontes parentais, importância, validade e embedding.
- `memory_fts`: índice FTS5 atualizado por triggers.
- `events`, `promises`: causalidade do motor e compromissos com estado explícito.
- `vault_files`: hash dos bytes exportados e revisão para detecção de conflitos.
- `settings`: configuração local. A chave pode vir de `RP_AI_KEY` para não persistir em SQLite.

Esquema v1 em `schema.sql`, `PRAGMA user_version=1`. Não há histórico de migrações anterior. Mudanças futuras exigem scripts de migração versionados antes de abrir bancos de versões anteriores.

## Memória e conhecimento

Um registro público usa `known_by=["*"]`; um privado usa IDs de NPCs e/ou `player`. A API de criador pode consultar qualquer audiência: isto é uma ferramenta pessoal, não um controle de acesso multiusuário. O filtro de conhecimento protege o **contexto da IA**, não os dados do dono do computador.

Fatos com `fact_key` só substituem versões da mesma campanha e mesma audiência. Assim, Alex pode guardar uma crença antiga enquanto Sara já sabe da mudança. Versões anteriores continuam no banco. Resumos são extrativos e agrupados pela mesma audiência; fontes invalidadas invalidam resumos dependentes. Conhecimento derivado atual inclui confiança baseada em relações e consequências de encontros.

O NPC pode interpretar ou contar uma memória na resposta. Não existe detector infalível de divulgação de segredo no texto livre; o criador pode editar `known_by` no Obsidian quando quiser tornar essa descoberta permanente para outros personagens. A exportação nunca coloca segredos privados dentro de uma nota pública de memória.

## Tempo

Rotinas são recorrências diárias por hora. Encontros agendados têm prioridade durante sua janela: o NPC vai ao local combinado; a presença do jogador decide o cumprimento. Encontros sobrepostos para o mesmo NPC são descartados na extração. Saltos processam todas as fronteiras horárias e os vencimentos de encontros no intervalo. O limite por solicitação é sete dias. O relógio contínuo usa wall time apenas para calcular minutos a processar; o tempo canônico permanece no banco. O processo pausa avanços da mesma campanha enquanto espera um turno da IA, evitando gerar respostas contra um estado que mudou durante o request.

## Segurança e operação

- Bind em `127.0.0.1`; sem CORS aberto; Host e Origin validados; token local em mutações.
- Nenhum modelo executa código, SQL, comandos de sistema, navegação ou plugins.
- Endpoints de IA restritos a loopback/host Docker; redirects desativados; proxy de ambiente ignorado.
- Escapamento de HTML na interface; CSP sem scripts inline; nenhum CDN/font remoto.
- Vault gerado com IDs, contenção de caminho, rejeição de symlinks e limite de tamanho de importação.
- O backup remove a chave persistida e executa VACUUM para eliminar resíduos livres no snapshot.
- Não é um servidor público nem serviço multiusuário. O adaptador do murn. também é exclusivamente local.

## Escalabilidade e limites medidos

Busca textual usa FTS5 e até 400 candidatos. Recência e importância adicionam candidatos limitados. Busca semântica varre os vetores em lotes de 256, mantendo os 60 melhores; memória RAM limitada, custo linear no número de vetores. O armazenamento é limitado pelo disco, não pelo contexto. O teste de regressão cobre recuperação após 1.500 memórias mais recentes; isso não equivale a validar 5.000 horas reais de jogo.

A exportação do vault verifica os registros da campanha, e a consolidação percorre fontes candidatas. Campanhas gigantes exigirão exportação incremental, fila de embeddings, índice ANN e paginação mais ampla. A UI mostra até 50 turnos por NPC (API: até 200), 200 eventos e 100 encontros; todos os registros antigos permanecem no banco/backup.

Um worker e um usuário são o escopo suportado. Locks em memória não coordenam múltiplos processos; não rode `uvicorn --workers N` com N > 1.
