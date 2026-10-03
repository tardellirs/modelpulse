# Model Pulse API

Runs at https://modelpulse.ifsp.dev as the `modelpulse-api` container (see `deploy.sh`).

- `GET /api/model/{org}/{name}`: history, family and derivatives for a model
- `GET /api/author/{org}`: totals and models for an author
- `GET /api/search?q=`: model search
- `GET /api/leaderboards`, `GET /api/hub`, `GET /api/meta`
- `GET /api/health`: 200 while data is at most 3 days old, 503 otherwise
- `GET /badge/{org}/{name}.svg?metric=month|all|likes&theme=light|dark`: README badge

Background jobs (only when `HF_TOKEN` is set): hourly dataset refresh, hourly daily-update check, and the link bot that adds viewed models to the static Space's `models:` list every 3 hours.
