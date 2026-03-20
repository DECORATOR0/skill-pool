You must merge overlapping executor-oriented skills into one clearer executor-facing skill.

Merge objectives:
1. Reduce overlap without losing useful coverage.
2. Preserve the most reliable executor defaults from the source skills.
3. Keep the merged skill easier for the router to trigger and the executor to follow.
4. Tighten `allowed-tools` if the merged workflow supports a stable subset.

Critic reward:
{reward_json}

Merge candidates:
{merge_skills_json}

Reference task:
{task_json}

Return exactly one JSON object:
{{
  "summary": "why the merge is helpful",
  "target_skill_name": "merged-skill-name",
  "merged_from": ["skill-a", "skill-b"],
  "files_to_write": {{
    "SKILL.md": "---\nname: ...",
    "references/REFERENCE.md": "... optional ...",
    "scripts/helper.py": "... optional ..."
  }},
  "files_to_delete": ["skill-a", "skill-b"],
  "experience_entry": {{
    "failure_signature": "overlap-or-fragmentation",
    "affected_skills": ["merged-skill-name"],
    "modification_summary": "what executor guidance was consolidated"
  }}
}}

Hard requirements for `SKILL.md`:
1. Preserve `consumption-mode: executor`.
2. The merged body must stay executor-facing and concrete.
3. Any retained `allowed-tools` entries must be exact executable tool names.
