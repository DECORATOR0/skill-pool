# AGENTS.md

## Scope

- This file keeps only high-value project rules. Avoid turning it into a rigid full checklist.

## Before Starting

- When entering this project or answering project-specific questions, read these first:
  - `D:\skills-evo\project_skills\README.md`
  - `D:\skills-evo\project_skills\项目文档\给AI先看_项目工作约定.md`
  - `D:\skills-evo\project_skills\项目文档\项目架构与工作流说明书.md`
- If the task touches current progress or experiment interpretation, also check:
  - `D:\skills-evo\project_skills\待办\进行中.md`
  - `D:\skills-evo\project_skills\实验记录\实验总表.md`
- Do not scan `AI交互记录/` by default. Only read it when the user asks for prior chat history or when the needed convention is missing from the core docs.

## Running Commands

- Run project commands from the outer root: `D:\skills-evo\project_skills`
- Do not run the CLI from the inner directory `D:\skills-evo\project_skills\project_skills`
- Prefer this CLI entry form:
  - `python -m project_skills.nlrl_skills.cli --config "project_skills/configs/<config>.json" <command> [args]`
- If the Python environment matters, prefer launching the target environment's `python.exe` directly.
- Do not start long-running experiments from a visible `cmd.exe` window.
- Treat any launch method that briefly pops a visible console window as disallowed too, even if the real work later detaches.
- Prefer PowerShell or a background-safe launch method, and redirect logs when relevant to `project_skills/runs/_launch_logs/`.
- For long-running training, prefer hidden PowerShell or `pythonw.exe`-style no-window launch paths over any method that may surface a terminal window.
- If a GDAL or `osgeo` import issue appears, first check the working directory and CLI entry before suspecting code or config problems.

## Docs And Naming

- Do not mechanically update documentation for every small code change.
- If the task changes long-lived project conventions, workflow, directory structure, or important experiment conclusions, proactively check whether the relevant docs should be updated.
- Usually the relevant docs are:
  - `D:\skills-evo\project_skills\README.md`
  - `D:\skills-evo\project_skills\项目文档\项目架构与工作流说明书.md`
  - `D:\skills-evo\project_skills\待办\进行中.md`
  - `D:\skills-evo\project_skills\实验记录\实验总表.md`
- For new long-lived notes, records, or user-facing docs, prefer a date or time prefix in the name, for example `2026-03-21_xxx.md` or `20260321_2051_xxx`.

## Response Style For This Project

- If only a few key files matter, provide absolute paths.
- If many files are involved, use normal concise references instead of dumping many absolute paths.
- Do not spend tokens exhaustively listing all success or failure reasons unless the user explicitly asks for that level of analysis.
