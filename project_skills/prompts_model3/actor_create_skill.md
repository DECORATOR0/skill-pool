You must create one new planner-oriented skill because the current library is insufficient for the task.

Model-three design objectives:
1. Follow the compact field style used by the reference high-quality skill set.
2. Use the gold trajectory as the main source of benchmark-faithful planning structure.
3. Generalize beyond the exact instance into a reusable task family.
4. Make the skill primarily useful to the planner, not as a long executor checklist.
5. Keep `allowed-tools` as a stable exact executable subset whenever possible.
6. Keep the main skill compact; only create `references/REFERENCE.md` when a concrete edge-case block would otherwise bloat `SKILL.md`.
7. A provisional lower-case-hyphen `target_skill_name` is fine. Successful tasks will be renamed by runtime during promotion, so do not optimize for a clever final library name.

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
4. The body must stay planner-oriented and use exactly this core section order:
   - `Skill Objective`
   - `Tool Scope`
   - `Family Rules`
   - `Stepwise Execution Pattern`
   - `Parameter Selection Policy`
   - `Stop Conditions`
5. `Optimization Notes` is optional and should appear only when it adds a real planning prior.
6. Prefer keeping everything inside `SKILL.md`; only emit `references/REFERENCE.md` when it carries concrete extra value.
7. The skill should describe how to choose and order tools, not dump a rigid executor transcript.
