You must create one new executor-oriented skill because the current library is insufficient for the task.

Design objectives:
1. Use the gold trajectory as the main procedural source.
2. Generalize to the broader executor-facing task family when that is safe.
3. Make the description highly triggerable for router matching.
4. Keep the skill usable by a weaker executor model: explicit defaults beat vague prose.
5. Narrow `allowed-tools` whenever that reduces executor drift.
6. If a helper script is needed, instruct the executor to call it via `run_python_script`.

Current task:
{task_json}

Critic reward:
{reward_json}

Existing skills:
{existing_skills_json}

Return exactly one JSON object:
{{
  "summary": "what this new executor-oriented skill adds",
  "target_skill_name": "lowercase-hyphen-name",
  "files_to_write": {{
    "SKILL.md": "---\nname: ...",
    "references/REFERENCE.md": "... optional ...",
    "scripts/helper.py": "... optional ..."
  }},
  "files_to_delete": [],
  "merged_from": [],
  "experience_entry": {{
    "failure_signature": "compact failure signature",
    "affected_skills": ["target_skill_name"],
    "modification_summary": "what this skill teaches the executor"
  }}
}}

Hard requirements for `SKILL.md`:
1. The frontmatter must include `name`, `description`, and `consumption-mode: executor`.
2. The skill directory name and `name` must match.
3. Add `allowed-tools` when the workflow can be narrowed to a stable subset of exact executable tool names.
4. The body must be executor-facing: concrete tool-use defaults, ordering hints, path/script rules, and stop conditions.
5. If a script is introduced, explicitly tell the executor to call `run_python_script` with `script_path="scripts/..."`.
