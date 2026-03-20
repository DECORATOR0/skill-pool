You must revise one existing executor-oriented skill in response to the critic reward.

Revision objectives:
1. Fix the specific failure mode with the smallest reliable change.
2. Preserve the skill's useful executor-facing coverage.
3. Prefer explicit defaults, few-shot patterns, path conventions, and scripts over vague advice.
4. Tighten `allowed-tools` when that reduces executor drift.
5. If the executor guessed numbers, paths, or logic, add a script or a stricter rule.

Critic reward:
{reward_json}

Reference task:
{task_json}

Target skill:
{skill_json}

Similar experiences:
{experiences_json}

Return exactly one JSON object:
{{
  "summary": "what was revised and why",
  "target_skill_name": "existing-skill-name",
  "files_to_write": {{
    "SKILL.md": "---\nname: ...",
    "references/REFERENCE.md": "... optional ...",
    "scripts/helper.py": "... optional ..."
  }},
  "files_to_delete": [],
  "merged_from": [],
  "experience_entry": {{
    "failure_signature": "compact failure signature",
    "affected_skills": ["existing-skill-name"],
    "modification_summary": "what changed in the executor-oriented skill"
  }}
}}

Hard requirements for `SKILL.md`:
1. Preserve `consumption-mode: executor`.
2. Keep instructions executor-facing and operational.
3. Any `allowed-tools` entries must be exact executable tool names.
4. If you mention a bundled script, explicitly route it through `run_python_script`.
