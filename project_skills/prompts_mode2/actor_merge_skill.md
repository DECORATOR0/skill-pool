You must merge overlapping planner-oriented skills into one clearer planner prior.

Merge objectives:
1. Reduce overlap without losing useful routing or ordering priors.
2. Preserve the strongest family rules and tool-scope guidance from the source skills.
3. Make the merged skill easier for the router to trigger and the planner to consume.
4. Keep the merged output planner-oriented rather than executor-oriented.

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
    "references/REFERENCE.md": "... optional ..."
  }},
  "files_to_delete": ["skill-a", "skill-b"],
  "experience_entry": {{
    "failure_signature": "overlap-or-fragmentation",
    "affected_skills": ["merged-skill-name"],
    "modification_summary": "what planning prior was consolidated"
  }}
}}

Hard requirements for `SKILL.md`:
1. Preserve `consumption-mode: planner`.
2. Preserve exact executable `allowed-tools` names only.
3. The merged body must stay planner-oriented.
