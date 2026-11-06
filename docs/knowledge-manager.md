# Local Knowledge Manager (initial implementation)

This module stores agent knowledge in a separate local SQLite file: `data/knowledge.db`. It does **not** train a model and does **not** automatically synchronize to a cloud database.

## Setup
Set `KNOWLEDGE_API_KEY` to a long random secret in the server environment before starting the API. Send it in the `X-Knowledge-Key` header for all knowledge requests. Keep the API on localhost or behind an authenticated private tunnel; **do not expose the existing unauthenticated task endpoints publicly**.

## Endpoints
- `POST /knowledge/entries`: create an entry.
- `GET /knowledge/search?q=...`: substring search across title, content and topic; optional `agent_id` and `topic` filters.
- `GET /knowledge/entries/{id}`: read entry.
- `PUT /knowledge/entries/{id}`: update entry.

Entries include agent ID, topic, title, content, source URL, source date, and verified flag. A common database permits cross-agent retrieval, with agent filters for organization; **agent-level access control is not implemented yet**. Do not put confidential data in the store until proper per-agent permissions are added.

## Next steps for Lauren
1. Add agent identity and fine-grained read/write permissions, plus audit logs.
2. Add scheduled source checks with change detection, citations, human review before verified legal updates, and version history.
3. Add Thai-aware retrieval (tokenization or embeddings) and evaluation tests.
4. Add backup/restore, migration and retention policies, API integration tests, and an authenticated Task Orchestrator deployment.
5. Wire the agents to call the knowledge API, then connect ChatGPT to the orchestrator. Do not send sensitive retrieved text to cloud models without approval.

This PR is a foundation, not a finished unattended learning system.
