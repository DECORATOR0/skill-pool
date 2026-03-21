from __future__ import annotations

import json
from pathlib import Path

from .agent_loop import JSONToolAgent
from .config import SystemConfig
from .evaluation import evaluate_execution
from .planner_runtime import PlannerSkillRuntime
from .prompting import render_prompt
from .router import SkillRouter
from .schemas import DatasetTask, EnvRunResult, EnvState, EvaluationResult, RouterResult, SkillDetail, SkillHeader, to_dict
from .skills import load_skill_detail
from .tools import ToolContext, Toolbox
from .utils import ensure_dir, write_json


class SkillEnvironment:
    _FALLBACK_BUILTIN_TOOLS = {"list_dir", "read_file", "glob_search", "run_python_script"}

    def __init__(self, config: SystemConfig):
        self.config = config
        self.router = SkillRouter(config)
        tool_context = ToolContext(
            workspace_root=config.workspace_root,
            skill_library_root=config.skill_library_root,
            temp_root=config.run_root / "temp",
            python_executable=config.runtime.python_executable,
            shell_program=config.runtime.shell_program,
        )
        self.toolbox = Toolbox(tool_context)
        self.executor_agent = JSONToolAgent(config.executor, config.prompt_root, self.toolbox)
        self.planner_runtime = PlannerSkillRuntime(config, self.toolbox)

    def _pick_active_skill(self, headers: list[SkillHeader], router_result: RouterResult) -> SkillDetail | None:
        if not router_result.selected_skill:
            return None
        for header in headers:
            if header.name == router_result.selected_skill:
                return load_skill_detail(header)
        return None

    def _task_context(self, task: DatasetTask) -> dict[str, object]:
        return {
            "data_dir": task.data_dir,
            "file_list": task.file_list,
            "choices": task.choices,
            "gold_answer": task.gold_answer,
        }

    def _executor_task_json(self, task: DatasetTask) -> str:
        return json.dumps(
            {
                "task_id": task.task_id,
                "prompt": task.prompt,
                "choices": task.choices,
                "data_dir": task.data_dir,
                "file_count": len(task.file_list),
                "file_list_preview": task.file_list[:20],
                "gold_answer_hidden": True,
            },
            ensure_ascii=False,
            indent=2,
        )

    def _fallback_allowed_tools(self) -> list[str]:
        allowed: list[str] = []
        for spec in self.toolbox.specs():
            if spec.source != "built_in" or spec.name in self._FALLBACK_BUILTIN_TOOLS:
                allowed.append(spec.name)
        return allowed

    def _execute_executor(
        self,
        task: DatasetTask,
        run_dir: Path,
        *,
        active_skill: SkillDetail | None,
        allowed_tools: list[str] | None,
        use_fallback_prompt: bool = False,
    ) -> EnvRunResult:
        system_prompt = render_prompt(
            self.config.prompt_root / "executor_system.md",
            max_steps=self.config.runtime.max_executor_steps,
        )
        self.toolbox.set_active_skill_dir(None if active_skill is None else active_skill.header.skill_dir)
        self.toolbox.set_active_task_data_dir(task.data_dir)
        try:
            task_json = self._executor_task_json(task)
            if use_fallback_prompt:
                user_prompt = render_prompt(
                    self.config.prompt_root / "executor_user_fallback.md",
                    task_json=task_json,
                )
            else:
                if active_skill is None:
                    raise ValueError("Active skill is required when fallback prompt is disabled.")
                user_prompt = render_prompt(
                    self.config.prompt_root / "executor_user.md",
                    task_json=task_json,
                    skill_name=active_skill.header.name,
                    skill_md=active_skill.full_text,
                    resources_json=json.dumps(active_skill.resources, ensure_ascii=False, indent=2),
                )
            final_payload, raw_output, tool_records = self.executor_agent.run(
                role_name="executor",
                base_system_prompt=system_prompt,
                user_prompt=user_prompt,
                allowed_tools=allowed_tools,
                max_steps=self.config.runtime.max_executor_steps,
                log_dir=run_dir / "executor",
            )
        finally:
            self.toolbox.set_active_skill_dir(None)
            self.toolbox.set_active_task_data_dir(None)

        summary = str(final_payload.get("summary", ""))
        if use_fallback_prompt:
            prefix = "Executed in evaluation fallback mode because the router found no applicable skill."
            summary = f"{prefix} {summary}".strip()
        env_result = EnvRunResult(
            final_answer=str(final_payload.get("final_answer", "")),
            final_choice_label=str(final_payload.get("choice_label", "")),
            tool_trajectory=tool_records,
            executor_summary=summary,
            raw_executor_output=raw_output,
            execution_mode="executor",
            used_fallback_executor=use_fallback_prompt,
        )
        env_result.evaluation = evaluate_execution(
            final_choice_label=env_result.final_choice_label,
            final_answer=env_result.final_answer,
            executed_steps=tool_records,
            gold_tool_names=task.gold_tool_names,
            gold_trajectory=task.gold_trajectory,
            gold_answer=task.gold_answer,
        )
        if use_fallback_prompt:
            fallback_note = "Evaluation fallback ran without an active skill because the router found no applicable skill."
            env_result.evaluation.notes = (
                f"{fallback_note} {env_result.evaluation.notes}".strip()
                if env_result.evaluation.notes
                else fallback_note
            )
        return env_result

    def run(
        self,
        task: DatasetTask,
        skill_headers: list[SkillHeader],
        run_dir: Path,
        *,
        allow_no_skill_fallback: bool = False,
    ) -> EnvState:
        ensure_dir(run_dir)
        router_result = self.router.route(task, skill_headers, run_dir / "router")
        active_skill = self._pick_active_skill(skill_headers, router_result)
        if not router_result.has_applicable_skill or active_skill is None:
            if allow_no_skill_fallback:
                env_result = self._execute_executor(
                    task,
                    run_dir,
                    active_skill=None,
                    allowed_tools=self._fallback_allowed_tools(),
                    use_fallback_prompt=True,
                )
            else:
                env_result = EnvRunResult(
                    final_answer="No applicable skill.",
                    executor_summary="Router judged that no skill in the current library is applicable.",
                    evaluation=EvaluationResult(
                        accuracy=0.0,
                        efficiency=0.0,
                        tool_any_order=0.0,
                        tool_in_order=0.0,
                        tool_exact_match=0.0,
                        parameter_accuracy=0.0,
                        task_success=False,
                        notes="Execution was skipped because the router found no applicable skill.",
                    ),
                )
            state = EnvState(
                task_id=task.task_id,
                task_prompt=task.prompt,
                router_result=router_result,
                env_result=env_result,
                gold_trajectory=task.gold_trajectory,
                gold_tool_names=task.gold_tool_names,
                skill_headers=skill_headers,
                active_skill=None,
                task_context=self._task_context(task),
            )
            write_json(run_dir / "state.json", to_dict(state))
            return state

        if self.config.runtime.uses_planner_mode:
            env_result = self.planner_runtime.execute(task, run_dir, active_skill=active_skill)
        else:
            env_result = self._execute_executor(
                task,
                run_dir,
                active_skill=active_skill,
                allowed_tools=active_skill.header.allowed_tools or None,
            )
        state = EnvState(
            task_id=task.task_id,
            task_prompt=task.prompt,
            router_result=router_result,
            env_result=env_result,
            gold_trajectory=task.gold_trajectory,
            gold_tool_names=task.gold_tool_names,
            skill_headers=skill_headers,
            active_skill=active_skill,
            task_context=self._task_context(task),
        )
        write_json(run_dir / "state.json", to_dict(state))
        return state
