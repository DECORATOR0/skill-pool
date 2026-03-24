#!/usr/bin/env bash
set -euo pipefail

source /data/xsy/miniconda3/etc/profile.d/conda.sh
conda activate earth-bench-skill-eval

cd /data/xsy/skill-pool

python -m project_skills.nlrl_skills.cli \
  --config project_skills/configs/system.dualmode_mode1.linux.json \
  train-tasks \
  --start-index 0 \
  --count 1 \
  --run-name linux_qwen14b_mode1 \
  --reset-skill-library \
  --reset-experience-buffer

python -m project_skills.nlrl_skills.cli \
  --config project_skills/configs/system.dualmode_mode2.linux.json \
  train-tasks \
  --start-index 0 \
  --count 1 \
  --run-name linux_qwen14b_mode2 \
  --reset-skill-library \
  --reset-experience-buffer
