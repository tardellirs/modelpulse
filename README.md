# Model Pulse

Download history for every model on the Hugging Face Hub.

- Site: https://huggingface.co/spaces/modelpulse/model-pulse (static Space, built from `space/web`)
- API + badges: https://modelpulse.ifsp.dev (Docker container on the Hostinger VM, `space/`)
- Data: https://huggingface.co/datasets/modelpulse/model-pulse-data

## Layout

| Path | What |
|---|---|
| `pipeline/backfill.py`, `backfill_xet.py` | One-off: extract daily snapshots from `cfahlgren1/hub-stats` history |
| `pipeline/build.py` | Full build of the dataset from raw snapshots |
| `pipeline/daily.py` | Daily incremental update (runs inside the API container every hour) |
| `space/app/` | FastAPI + DuckDB API, badges, dataset refresher, `models:` link bot |
| `space/web/` | Preact + uPlot frontend |
| `site/README.md` | Static Space card (its `models:` list is maintained by the link bot) |
| `brand/` | Logo, thumbnail and org card |

## Operations

- Deploy API: `space/deploy.sh` (rsyncs code to the VM, rebuilds, restarts `modelpulse-api`).
  The HF token lives only on the VM in `/opt/modelpulse/.env`.
- Publish site: `./publish_site.sh` (never touches the Space README).
- Health: `GET /api/health` returns 503 when data is more than 3 days old; checked every 6 h by `.github/workflows/health.yml`.
- Full rebuild: rerun `pipeline/backfill_xet.py` then `pipeline/build.py raw out` on a machine with ~32 GB RAM.
