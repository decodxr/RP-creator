# Validação da entrega

Executada em 25/09/2026, Linux, Python 3.12 e Node 24.

| Verificação | Resultado |
|---|---|
| Instalação de `requirements.txt` em venv vazio | Passou |
| Construção e instalação do pacote Python (wheel) | Passou |
| Compilação dos módulos Python | Passou |
| Sintaxe de `static/app.js` | Passou |
| Testes Python | **24 passaram** |
| Integração de interface com jsdom + servidor HTTP real | Passou, sem exceções JS |
| Recuperação de memória antiga após 1.500 registros | Passou |
| Isolamento de segredos entre NPCs/campanhas/jogador | Passou |
| Perfil privado do jogador ausente do prompt do NPC | Passou |
| Idempotência e falhas de IA | Passou |
| Contratos OpenAI, Ollama e custom | Passaram com transporte HTTP simulado |
| Embeddings e filtragem de audiência | Passaram com vetores de teste |
| Memória superada e invalidação de resumo dependente | Passou |
| Rotinas, encontros, objetivos e promessas cumpridas/perdidas | Passaram |
| Importação Obsidian e preservação de conflitos | Passaram |
| Backup binário, remoção da chave e restauração real | Passaram |
| Proteções de Origin, token e endpoint local | Passaram |

O teste da interface inicia a aplicação, configura modo demonstração, cria uma campanha, seleciona Sara, envia uma mensagem, consulta sua memória e origem, cria um lugar e NPC, avança uma hora e exporta o vault.

Os testes rodaram com as versões fixadas em `requirements.txt`. A suíte registra um aviso de depreciação do TestClient do Starlette sobre seu transporte httpx; não houve falha por esse aviso. A aplicação de produção usa httpx diretamente para conversar com a IA, não TestClient.

## Não validado neste ambiente

- Conexão com a instância real do murn./Ollama do usuário. O contrato foi verificado no código do murn. e passou em transporte HTTP simulado; a qualidade narrativa depende do modelo instalado.
- Inspeção visual num navegador: o navegador remoto bloqueou o endereço loopback. jsdom verifica comportamento/DOM, não layout ou aparência.
- Execução no Windows/macOS e matriz Python 3.11/3.13. O workflow foi preparado, mas não executado no GitHub.
- Campanhas de milhares de horas, carga multiusuário e desempenho com milhões de vetores.
- A execução do CI no GitHub está pendente após a publicação.

A distinção entre esses testes e uso com um modelo real é intencional: nenhuma resposta de demonstração foi apresentada como geração do murn.
