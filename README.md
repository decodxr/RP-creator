# RP creator

**Um simulador narrativo local, com personagens que possuem conhecimento individual e um mundo persistente.** Interface em português, IA local configurável, SQLite, busca de memórias e vault Markdown para Obsidian. Tudo neste repositório; não requer Node, Docker, conta de nuvem ou banco separado para rodar.

## Rodar no seu PC

Requisito: **Python 3.11 ou superior**, com `pip` e `venv` (no Ubuntu/WSL: pacote `python3-venv`).

Linux / CachyOS / WSL:

```bash
cd RP-creator
chmod +x start.sh
./start.sh
```

Windows: execute `start.bat` depois de instalar Python com **Add Python to PATH**.

Abra **http://127.0.0.1:7342**. O primeiro início instala as dependências; depois a aplicação roda localmente. O modelo é executado separadamente pelo murn./Ollama. Não incluímos pesos de modelos.

Alternativa manual:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m rp_creator
```

Porta e pasta opcionais: `./start.sh --port 7342 --data /caminho/para/meus-mundos`.

## Conectar sua IA do murn.

Na aba **Conexão com IA**, selecione o protocolo que o seu servidor realmente oferece, preencha modelo e endereço, **salve** e **teste a conexão salva**.

| Seu servidor | Protocolo | Endereço | Caminho |
|---|---|---|---|
| murn. local (backend web) | **murn. local** | `http://127.0.0.1:7331` | `/v1/chat` |
| murn. no aplicativo desktop | **murn. local** | `http://127.0.0.1:7332` | `/v1/chat` |
| Mesmo modelo do murn. com memórias de NPC isoladas | **Ollama do murn.** | `http://127.0.0.1:11434` | `/api/chat` |
| Outro servidor compatível com OpenAI | Compatível com OpenAI | Endereço local | `/v1/chat/completions` |

Conferi a implementação do seu repositório `decodxr/murn.`: o endpoint é `POST /v1/chat`, recebe `message`, `history` e `source`, e retorna `message`. A conexão direta está implementada. Como a rota do murn. é um agente pessoal com memória e ferramentas, **Ollama do murn.** é a escolha recomendada para manter o conhecimento dos NPCs separado. Ela utiliza o mesmo modelo local, sem baixar outro. A extração estruturada de memórias usa Ollama mesmo quando a narrativa usa a API do murn. [Detalhes](docs/MURN.md).

## O que está implementado

- Múltiplas campanhas isoladas, personagem do jogador, editor de NPCs e locais.
- Chat por personagem, histórico persistente, reenvio idempotente e erro explícito quando o modelo está offline.
- Memórias episódicas, semânticas, sociais, emocionais, temporais, promessas e segredos.
- Origem, trecho de evidência, relevância, prioridade e audiência em cada memória.
- Recuperação híbrida: SQLite FTS5/BM25 + cosseno de embeddings opcionais; somente memórias autorizadas entram no contexto do NPC.
- Correção de fatos por chave e audiência; versões antigas são preservadas como superadas.
- Resumos extrativos automáticos a cada 12 turnos (quando há seis fontes da mesma audiência) ou manuais. As fontes originais não são removidas. Resumos dependentes são invalidados se a fonte muda.
- Nove métricas de relação, relações NPC↔NPC, humor e conhecimento derivado a partir da confiança.
- Relógio manual ou contínuo, rotinas diárias, encontros entre NPCs e dedicação diária a objetivos.
- Encontros prometidos com horário e local, cumprimento e consequências de ausência.
- Linha do tempo, painel de memória, visão do jogador e visão do criador, grafo de relações.
- Exportação automática para Obsidian, importação explícita de memórias editadas e detecção de conflitos.
- Backup consistente do SQLite e vault; restauração em pasta vazia.
- Servidor restrito ao computador local, checagem de origem/Host, token contra CSRF, validação de entradas e proteção de caminhos.

### Um primeiro roteiro de uso

1. Crie uma campanha com Sara e Alex. Sara está na Praça às 09h; selecione-a.
2. Conte: “Eu odeio café e prefiro chá de hibisco.” Confira a memória na aba Memórias.
3. Converse e depois pergunte: “Você lembra da bebida que eu prefiro?” Quando o modelo citar `[mem:ID]`, a interface abre a fonte.
4. Avance uma hora: Sara vai para a Biblioteca. Vá até ela para continuar o diálogo presencial.
5. Com IA conectada, combine um encontro com local e horário explícitos. Confira se a extração registrou em Linha do tempo.
6. Esteja no local **junto com o NPC**, entre o horário combinado e 60 minutos depois. O motor verifica a presença ao mover ou avançar o relógio. Depois da tolerância, marca o encontro como perdido.
7. Ative Modo criador para ver segredos e relações. A história inicial inclui um segredo só de Sara; Alex não o recebe no contexto.

## Tempo, simulação e autoridade

Cada envio de chat preserva o horário atual; você controla os saltos ou ativa o relógio (1 minuto real = 1 minuto no mundo). A API permite ajustar a velocidade entre 0,1 e 60. No modo contínuo, o processo verifica o relógio a cada cinco segundos. Se você fecha o aplicativo, o tempo decorrido é processado ao reabrir, em lotes de até sete dias. No modo pausado não há avanço offline.

A simulação aplica rotinas nos horários definidos, registra encontros de personagens que ficam no mesmo local e dedica tempo aos objetivos às 18h. **É uma simulação narrativa por regras**, sem física, mapa 3D ou agentes que planejam ações arbitrárias sozinhos. A IA interpreta o personagem e propõe memórias/relações/encontros dentro de um esquema validado; não executa comandos, não escreve SQL e não muda locais ou relógio.

A verdade mecânica fica no banco. Modelos locais ainda podem inventar coisas no texto: o prompt e as citações ajudam, mas não garantem fidelidade perfeita. A extração exige evidência literal na mensagem, limita efeitos a ±10 por métrica e não permite escolher a audiência. Isso não prova que a interpretação do LLM seja correta; revise no modo criador quando necessário. Atração existe no modelo de dados mas não recebe alterações automáticas; não há sistema de romance implementado.

## Obsidian

Em **Obsidian & backup → Ver pasta & exportar**, copie a pasta mostrada. No Obsidian, use **Abrir pasta como cofre**. Obsidian não precisa estar instalado para a aplicação funcionar.

```text
data/
├── world.sqlite3
└── vault/
    └── <campaign-id>/
        ├── World.md
        ├── Characters/
        ├── Locations/
        ├── Events/
        ├── Memories/
        └── Player/
```

As notas têm nomes por ID estável e links com rótulos legíveis, evitando colisões de nomes. O banco é a fonte operacional; o vault é uma projeção legível com importação controlada. **Só `Memories/*.md` é importado de volta**. Edite personagens, rotinas e locais no aplicativo. O vault inteiro é a visão do criador e pode conter segredos.

Para editar uma memória, preserve o cabeçalho entre `---`, altere o texto acima de `<!-- rp-links -->` e importe. O cabeçalho usa JSON (também válido como YAML). `known_by` controla a audiência: `player`, IDs de NPCs ou `*` para público. Para criar uma nota nova, copie um modelo, remova `id` e `revision` e importe. Não use `*` em segredos.

Em caso de conflito, sua nota é preservada e a importação informa o arquivo. Compare sua edição com a memória na interface; faça uma cópia antes de resolver. Não há sincronização silenciosa nem importação irrestrita de qualquer vault externo.

## Backup e restauração

Baixe em **Obsidian & backup → Baixar backup completo**. Inclui todas as campanhas, não apenas a selecionada. Chaves de API são removidas das configurações do backup.

```bash
python scripts/restore_backup.py RP-creator-backup.zip --data data-restaurada
./start.sh --data data-restaurada
```

A pasta deve estar vazia. Não sobrescreve campanhas existentes. Restaure apenas backups seus/de fonte confiável: o formato contém um banco SQLite completo e arquivos privados.

## Testes

```bash
python -m pip install pytest
python -m pytest -q
```

Teste opcional de integração da interface (Node 24+): `npm install` e `npm run test:ui`. Ele inicia um servidor temporário e executa os fluxos com jsdom; não é um teste visual de navegador.

Os testes cobrem memória persistente e antiga após 1.500 registros, isolamento de conhecimento, correção de fatos, resumos, rotinas, encontros, promessas, falhas de IA, idempotência, contratos OpenAI/Ollama/custom com transporte simulado, embeddings, round-trip do vault e backup. O arquivo de CI repete os testes em Python 3.11–3.13. Leia [VALIDATION.md](docs/VALIDATION.md) para as verificações efetivamente executadas nesta entrega.

## Organização

```text
rp_creator/
  api.py           # FastAPI, validação local, relógio e rotas
  engine.py        # Orquestração de um turno, isolamento e idempotência
  world.py         # Estado, rotinas, encontros, promessas e relações
  memory.py        # FTS5, embeddings, audiência, resumo e correção de fatos
  ai.py            # Protocolos, prompts e análise estruturada
  vault.py         # Markdown, importação e conflitos
  db.py/schema.sql # SQLite, índices e esquema v1
  models.py        # Contratos validados
  static/          # Interface sem build ou dependências de CDN
scripts/           # Restauração e adaptador opcional do murn.
tests/             # Testes automatizados
```

[Arquitetura e decisões](docs/ARCHITECTURE.md) · [API](docs/API.md) · [Integração murn.](docs/MURN.md).

## Escopo operacional

Aplicação pessoal, **um usuário e um processo**. Não exponha a porta na internet: a visão do criador não é uma barreira de autenticação, o dono do PC pode acessar o banco/vault e as configurações. SQLite WAL e índices suportam campanhas locais; busca vetorial usa cosseno exato em lotes, sem índice ANN. “Memória ilimitada” significa crescimento no disco disponível, não contexto infinito ou garantia de recuperação de todo fato. Não foi feito benchmark de milhares de horas, teste de carga multiusuário ou teste com o seu murn. real.

O histórico enviado ao modelo é limitado por caracteres e pelas 12 interações recentes desse NPC. Memórias recuperadas também obedecem esse orçamento. O limite em caracteres é uma aproximação; escolha um valor adequado ao contexto em tokens do seu modelo. O histórico bruto completo permanece no banco e no backup.

## Repositório Git

O código é publicado em [decodxr/RP-creator](https://github.com/decodxr/RP-creator). Clone assim:

```bash
git clone https://github.com/decodxr/RP-creator.git
cd RP-creator
./start.sh
```

A entrega ZIP também contém um Git bundle para uso offline. Nenhum dado de campanha, modelo ou chave pertence ao Git: `data/`, `.env` e bancos SQLite são ignorados.
