#!/usr/bin/env bash
# Build and (re)start the Model Pulse API on the Hostinger VM behind Dokploy's Traefik.
# Usage: ./deploy.sh   (run locally; syncs code to the VM and restarts the container)
set -euo pipefail
# the server address lives outside the repo: put DEPLOY_HOST=user@host in space/.deploy.env (gitignored)
[ -f "$(dirname "$0")/.deploy.env" ] && . "$(dirname "$0")/.deploy.env"
HOST="${DEPLOY_HOST:?set DEPLOY_HOST=user@host in space/.deploy.env}"
DIR=/opt/modelpulse
cd "$(dirname "$0")"
rsync -a --delete --exclude .venv --exclude web --exclude __pycache__ ./ "$HOST:$DIR/src/"
rsync -a --delete --exclude __pycache__ ../pipeline/ "$HOST:$DIR/src/pipeline/"
# the same frontend build the Space uses, served on our own domain with server-rendered pages
(cd web && npm run build >/dev/null)
rsync -a --delete ../site/ "$HOST:$DIR/src/app/static/"
rsync -a web/src/report.md "$HOST:$DIR/src/app/report.md"
ssh "$HOST" bash -s <<'REMOTE'
set -euo pipefail
DIR=/opt/modelpulse
mkdir -p $DIR/data $DIR/work && chown -R 1000:1000 $DIR/data $DIR/work
touch $DIR/.env && chmod 600 $DIR/.env
docker build -q -t modelpulse-api $DIR/src
docker rm -f modelpulse-api >/dev/null 2>&1 || true
docker run -d --name modelpulse-api --restart unless-stopped \
  --network dokploy-network --memory 10g --cpus 3 \
  --env-file $DIR/.env \
  -e DATA_REPO=modelpulse/model-pulse-data -e SITE_REPO=tardellirs/model-pulse -e LINK_CAP=25000 \
  -v $DIR/data:/home/user/data -v $DIR/work:/home/user/work \
  -l traefik.enable=true \
  -l traefik.docker.network=dokploy-network \
  -l 'traefik.http.routers.modelpulse.rule=Host(`modelpulse.ifsp.dev`)' \
  -l traefik.http.routers.modelpulse.entrypoints=websecure \
  -l traefik.http.routers.modelpulse.tls.certresolver=le \
  -l traefik.http.services.modelpulse.loadbalancer.server.port=7860 \
  modelpulse-api
docker ps --filter name=modelpulse-api --format '{{.Names}} {{.Status}}'
REMOTE
