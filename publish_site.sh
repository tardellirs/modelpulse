#!/usr/bin/env bash
# Build the frontend and publish it to the static Space. Never touches README.md,
# whose `models:` list is maintained by the API's link bot.
set -euo pipefail
cd "$(dirname "$0")"
(cd space/web && npm run build)
space/.venv/bin/python - <<'PY'
import shutil, tempfile
from huggingface_hub import HfApi
# the Space's own copy points search engines at the site, which serves the same app with a readable page per URL
out = tempfile.mkdtemp()
for d in ("assets", "report"):
    shutil.copytree(f"site/{d}", f"{out}/{d}")
open(f"{out}/index.html", "w").write(open("site/index.html").read().replace(
    "</head>", '  <link rel="canonical" href="https://modelpulse.ifsp.dev/" />\n  </head>', 1))
print(HfApi().upload_folder(repo_id="tardellirs/model-pulse", repo_type="space", folder_path=out,
      allow_patterns=["index.html", "assets/*", "report/*"], delete_patterns=["assets/*", "report/*"], commit_message="Update site"))
shutil.rmtree(out)
PY
