# Integração com o murn.

Conferi o código do seu repositório `decodxr/murn.`. O endpoint real é `POST /v1/chat`. O backend web usa a porta **7331**; o backend do aplicativo desktop usa **7332**. O RP creator usa **7342** para evitar colisão.

## Conexão direta com o murn.

1. Abra o murn. e verifique `curl http://127.0.0.1:7331/health` (ou `7332/health` no aplicativo desktop).
2. Inicie o RP creator com `./start.sh` e abra `http://127.0.0.1:7342`.
3. Em **Conexão com IA**, selecione **murn. local · RP isolado** e informe `http://127.0.0.1:7331` ou `http://127.0.0.1:7332`.
4. Confirme o modelo configurado no murn. (padrão do código: `llama3.1:8b`), salve e clique em **Testar conexão salva**.
5. Crie uma campanha e converse com um NPC.

O RP creator usa `POST /v1/rp/chat`. Esse endpoint recebe a lista completa de mensagens do RP e envia diretamente ao Ollama configurado dentro do murn. Ele **não** acrescenta a identidade pessoal do murn., não passa pelo classificador de programação, não habilita ferramentas, não consulta a memória pessoal e não cria sessão do assistente. Isso evita que o modelo responda como “murn.” quando deveria interpretar Tanjiro, Shinobu ou outro personagem.

A **extração estruturada de memórias** continua usando diretamente o Ollama do murn. em `http://127.0.0.1:11434`, com o modelo selecionado e JSON mode. Assim, a análise não passa pelas ferramentas ou pela memória pessoal do murn. Se o Ollama não estiver acessível ao RP creator, a resposta narrativa é salva com aviso, sem extrair novas memórias naquele turno.

## Isolamento recomendado: Ollama do murn.

Para que Sara e Alex não recebam contexto de memória pessoal do agente murn., escolha **Ollama do murn.** na mesma tela. Endereço `http://127.0.0.1:11434`, modelo `llama3.1:8b` ou o modelo configurado no seu `.env`. Isso usa exatamente a instalação local que o murn. já utiliza; a memória/estado do RP creator permanece no seu próprio banco e vault.

## Ollama nativo

Base `http://127.0.0.1:11434`; rota `/api/chat`; mensagens estruturadas, `stream:false` e temperatura dentro de `options`. Resposta em `message.content`. Embeddings em `/api/embed`, com `model` e `input` (lista), lendo `embeddings`.

Protocolos conferidos na documentação oficial do Ollama: https://github.com/ollama/ollama/blob/main/docs/api.md. Isso não verifica nem substitui o contrato próprio do murn.

## API própria que recebe lista de mensagens

Escolha **murn. · contrato personalizado**:

- `chat_path`: caminho real do endpoint, ex. `/api/chat`.
- `messages_field`: nome do campo de lista, ex. `messages` ou `conversation`.
- `response_path`: caminho no JSON da resposta, ex. `response`, `data.text` ou `choices.0.message.content`.

Os campos `model`, `temperature` e `stream:false` também são enviados. Se o servidor rejeitar campos extras, ajuste o payload em `rp_creator/ai.py` ao seu contrato. O servidor deve aceitar papéis `system`, `user` e `assistant`, sem descartar o contexto do sistema.

## Contratos alternativos

Para servidores que recebem uma lista de mensagens, escolha **murn. · contrato personalizado** e defina `messages_field` e `response_path`. Para outro serviço que aceita uma única string, `scripts/murn_bridge.py` segue disponível; **ele não é necessário para a API atual do seu murn.**

A API do murn. pessoal pode acionar ferramentas e consultar sua memória própria. Por isso, para RP com segredos rigorosamente isolados, prefira o Ollama direto. No backend web, o murn. cria sessões de chat adicionais quando usado via API direta. Não reutilize uma sessão compartilhada entre NPCs.

## JSON e falhas

O modelo faz duas chamadas: narrativa e extração. A segunda pede JSON estrito. Se o provedor suporta, ative JSON mode. Se um modelo responder JSON inválido, a conversa ainda é salva com aviso, mas as propostas de memória e efeitos daquele turno são descartadas. Não há efeitos parciais de um JSON inválido.

O botão de teste valida só a chamada narrativa. A qualidade de extração precisa ser conferida em uma conversa real, olhando as memórias e encontros criados. A evidência literal limita extrações sem fonte, mas ainda é possível haver interpretação errada.

## Diagnóstico rápido

| Sintoma | O que conferir |
|---|---|
| Conexão recusada | murn./Ollama aberto, endereço e porta corretos |
| HTTP 404 | Caminho da API ou nome de modelo inexistente |
| HTTP 400/422 | Formato do payload, JSON mode, campos extras |
| HTTP 401/403 | Chave, políticas locais do servidor |
| Resposta ilegível | Caminho do texto no JSON; streaming precisa estar desligado |
| Demora/timeout | Modelo carregando, RAM/VRAM, contexto; aumente timeout |
| Memórias não extraídas | Confira aviso no turno e formato JSON retornado |
| NPC parece onisciente | Verifique memória global oculta no upstream e conteúdo da premissa |

No WSL, `127.0.0.1` se refere ao ambiente em que o backend está rodando. O caminho mais simples é rodar murn./Ollama e RP creator no mesmo ambiente. Não há dependência de Vercel nem necessidade de publicar a aplicação para usá-la.
