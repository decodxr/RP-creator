# API local

Base: `http://127.0.0.1:7342`. OpenAPI em `/openapi.json`. O explorador `/docs` padrão do FastAPI referencia CDN e pode não renderizar sob a CSP local; prefira o OpenAPI JSON e este guia.

Todas as mutações exigem `X-RP-Token`, obtido por `GET /api/session`. Em uso no navegador, a origem deve coincidir com Host. A aplicação não aceita acesso remoto autenticado/multiusuário.

| Método | Rota | Uso |
|---|---|---|
| GET | `/api/health` | Saúde do processo |
| GET | `/api/session` | Token local |
| GET / PUT | `/api/settings` | Ler configuração sem chave / salvar configuração |
| POST | `/api/settings/test` | Chamar modelo configurado |
| GET / POST | `/api/campaigns` | Listar / criar campanha |
| GET | `/api/campaigns/{id}?gm=false` | Estado do mundo |
| PUT | `/api/campaigns/{id}/player` | Nome e perfil privado |
| POST | `/api/campaigns/{id}/locations` | Criar lugar |
| POST | `/api/campaigns/{id}/npcs` | Criar NPC |
| PUT | `/api/campaigns/{id}/npcs/{npc}` | Editar perfil/rotina/objetivos |
| POST | `/api/campaigns/{id}/chat` | `{npc,message,request_id}` |
| GET | `/api/campaigns/{id}/history/{npc}?limit=50` | Últimos turnos do NPC |
| POST | `/api/campaigns/{id}/move` | `{location: ID}` |
| POST | `/api/campaigns/{id}/advance` | `{minutes: 1..10080}` |
| PUT | `/api/campaigns/{id}/clock` | `{enabled: bool, rate: 0.1..60}` |
| GET | `/api/campaigns/{id}/memories?q=texto&actor=player` | Memórias por audiência; `actor=gm` mostra todas |
| POST | `/api/campaigns/{id}/memories` | Criar memória pelo criador |
| GET | `/api/campaigns/{id}/memories/{mid}?gm=false` | Fonte e detalhes |
| POST | `/api/campaigns/{id}/memories/{mid}/invalidate` | Superar sem remover histórico |
| POST | `/api/campaigns/{id}/consolidate` | Gerar resumos extrativos |
| POST | `/api/campaigns/{id}/reindex` | Indexar até 32 embeddings pendentes |
| POST | `/api/campaigns/{id}/vault/export` | Exportar preservando edições externas |
| POST | `/api/campaigns/{id}/vault/import` | Importar memórias editadas |
| GET | `/api/backup` | Backup ZIP de todas as campanhas |

Exemplo de memória manual:

```json
{
  "kind": "secret",
  "text": "Sara guardou a chave do farol.",
  "known_by": ["ID_REAL_DE_SARA"],
  "entities": ["ID_REAL_DE_SARA"],
  "importance": 8,
  "fact_key": "lighthouse.key.holder"
}
```

Reenvios de `chat` com o mesmo `request_id`, NPC e mensagem devolvem o turno já salvo. O cliente deve manter o mesmo ID em retries de rede. Não use um ID antigo para uma mensagem diferente.

Sem streaming nesta versão: o turno aparece depois da narrativa e da análise. O servidor tem timeout configurável e mantém a UI em estado de espera.
