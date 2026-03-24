#!/usr/bin/env bash

set -u

source /data/xsy/miniconda3/etc/profile.d/conda.sh
conda activate earth-bench-skill-eval

export HF_HOME=/data/xsy/.cache/huggingface

while true; do
  python - <<'PY'
from pathlib import Path

from huggingface_hub import hf_hub_download, list_repo_files

repo_id = "Sssunset/Earth-Bench"
local_dir = "/data/xsy/skill-pool/benchmark/benchmark/data"
local_root = Path(local_dir)

print("Listing remote files for Sssunset/Earth-Bench ...", flush=True)
files = [name for name in list_repo_files(repo_id, repo_type="dataset") if name.startswith("question")]
print(f"Found {len(files)} files to sync.", flush=True)

for index, filename in enumerate(files, start=1):
    if (local_root / filename).exists():
        if index == 1 or index % 500 == 0 or index == len(files):
            print(f"Skipped existing {index}/{len(files)} files; latest={filename}", flush=True)
        continue
    hf_hub_download(
        repo_id=repo_id,
        repo_type="dataset",
        filename=filename,
        local_dir=local_dir,
        etag_timeout=30,
    )
    if index == 1 or index % 50 == 0 or index == len(files):
        print(f"Synced {index}/{len(files)} files; latest={filename}", flush=True)

print("DOWNLOAD_COMPLETED", flush=True)
PY
  status=$?
  if [ "$status" -eq 0 ]; then
    exit 0
  fi
  echo "download failed with status $status, retrying in 120s" >&2
  sleep 120
done
