You must create one new planner-oriented skill because the current library is insufficient for the task.

Design objectives:
1. Use the gold trajectory as the main source of benchmark-faithful planning structure.
2. Generalize beyond the exact instance into a reusable task family.
3. Make the skill primarily useful to the planner, not as a long executor checklist.
4. Capture high-level priors: tool scope, family rules, stepwise execution pattern, parameter policy, and stop conditions.
5. Keep `allowed-tools` as a stable exact executable subset whenever possible.
6. Do not hard-code one brittle trajectory if the family needs conditional branches.

Current task:
{task_json}

Critic reward:
{reward_json}

Existing skills:
{existing_skills_json}

Return exactly one JSON object:
{{
  "summary": "what this new planner-oriented skill adds",
  "target_skill_name": "lowercase-hyphen-name",
  "files_to_write": {{
    "SKILL.md": "---\nname: ...",
    "references/REFERENCE.md": "... optional ..."
  }},
  "files_to_delete": [],
  "merged_from": [],
  "experience_entry": {{
    "failure_signature": "compact failure signature",
    "affected_skills": ["target_skill_name"],
    "modification_summary": "what planning prior was added"
  }}
}}

Hard requirements for `SKILL.md`:
1. The frontmatter must include `name`, `description`, and `consumption-mode: planner`.
2. The skill directory name and `name` must match.
3. `allowed-tools` must contain exact executable tool names, not abstract aliases.
4. The body must be planner-oriented and include these sections when relevant:
   - `Skill Objective`
   - `Tool Scope`
   - `Family Rules`
   - `Stepwise Execution Pattern`
   - `Parameter Selection Policy`
   - `Stop Conditions`
5. The skill should describe how to choose and order tools, not dump a rigid executor transcript.
