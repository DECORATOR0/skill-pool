You must revise one existing planner-oriented skill in response to the critic reward.

Model-three revision objectives:
1. Fix the specific planning failure with the smallest reliable change.
2. Preserve useful high-level priors already captured by the skill.
3. Keep the skill aligned with the compact reference field style used by the high-quality skill set.
4. Prefer better family routing rules, tool-scope corrections, ordering priors, and stop guidance over low-signal verbosity.
5. Tighten `allowed-tools` when that improves planner fidelity.
6. Keep the skill planner-facing rather than executor-checklist-heavy.
7. Keep `references/REFERENCE.md` optional; do not create one unless it materially helps.

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
    "references/REFERENCE.md": "... optional ..."
  }},
  "files_to_delete": [],
  "merged_from": [],
  "experience_entry": {{
    "failure_signature": "compact failure signature",
    "affected_skills": ["existing-skill-name"],
    "modification_summary": "what planning prior changed"
  }}
}}

Hard requirements for `SKILL.md`:
1. Preserve `consumption-mode: planner`.
2. Keep `allowed-tools` to exact executable tool names only.
3. Preserve the compact section structure and keep these core sections in order:
   - `Skill Objective`
   - `Tool Scope`
   - `Family Rules`
   - `Stepwise Execution Pattern`
   - `Parameter Selection Policy`
   - `Stop Conditions`
4. `Optimization Notes` is optional and should stay short.
5. Focus the revision on planner quality: family disambiguation, tool ordering, parameter policy, and stopping guidance.
