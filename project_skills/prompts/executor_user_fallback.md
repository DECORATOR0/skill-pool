Task payload:
{task_json}

Fallback mode:
- The router found no applicable skill in the current library.
- No `SKILL.md` is active for this task.
- You are in evaluation-only fallback mode. Do not invent or modify skills.

Execution reminder:
- decide which tools to use from the currently exposed fallback tool set
- prefer tool-grounded execution over free-form reasoning
- inspect the data directory before guessing filenames or paths
- do not invent parameters, file paths, or intermediate outputs

Execute the task now and provide the best supported final answer you can.
