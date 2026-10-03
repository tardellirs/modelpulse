#!/usr/bin/env bash
# Build the frontend and publish it to the static Space. Never touches README.md,
# whose `models:` list is maintained by the API's link bot.
set -euo pipefail
cd "$(dirname "$0")"
(cd space/web && npm run build)
space/.venv/bin/python - <<'PY'
from huggingface_hub import HfApi
print(HfApi().upload_folder(repo_id="modelpulse/model-pulse", repo_type="space", folder_path="site",
      allow_patterns=["index.html", "assets/*"], delete_patterns=["assets/*"], commit_message="Update site"))
PY
