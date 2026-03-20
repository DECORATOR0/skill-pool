from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from project_skills.agent.skill_eval.parameter_worker import choose_tool_arguments

from .config import SystemConfig
from .evaluation import evaluate_execution
from .llm import OpenAICompatibleLLM, log_llm_call
from .prompting import render_prompt
from .schemas import DatasetTask, EnvRunResult, LLMMessage, SkillDetail, ToolCallRecord
from .tools import ToolSpec, Toolbox
from .utils import write_json


@dataclass
class PlannedStep:
    tool_name: str
    reason: str = ""


class PlannerSkillRuntime:
    def __init__(self, config: SystemConfig, toolbox: Toolbox):
        self.config = config
        self.toolbox = toolbox
        self.planner_llm = OpenAICompatibleLLM(config.executor)
        self.answer_selector_llm = OpenAICompatibleLLM(config.executor)

    def _default_tool_specs(self) -> list[ToolSpec]:
        return [spec for spec in self.toolbox.specs() if spec.source != "built_in"]

    def _active_tool_specs(self, active_skill: SkillDetail) -> list[ToolSpec]:
        allowed = set(active_skill.header.allowed_tools or [])
        if not allowed:
            return self._default_tool_specs()
        specs = [spec for spec in self.toolbox.specs() if spec.name in allowed]
        return specs or self._default_tool_specs()

    def _tool_catalog_json(self, tool_specs: list[ToolSpec]) -> str:
        return json.dumps(
            [
                {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.parameters,
                    "source": spec.source,
                }
                for spec in tool_specs
            ],
            ensure_ascii=False,
            indent=2,
        )

    def _render_worker_tools(self, tool_specs: list[ToolSpec]) -> str:
        lines: list[str] = []
        for spec in tool_specs:
            properties = spec.parameters.get("properties", {}) if isinstance(spec.parameters, dict) else {}
            lines.append(
                f"{spec.name}: {spec.description}, args: {json.dumps(properties, ensure_ascii=False, sort_keys=True)}"
            )
        return "\n".join(lines)

    def _task_json(self, task: DatasetTask) -> str:
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

    def _plan(
        self,
        task: DatasetTask,
        active_skill: SkillDetail,
        tool_specs: list[ToolSpec],
        log_dir: Path,
    ) -> tuple[list[PlannedStep], str, str]:
        system_prompt = render_prompt(
            self.config.prompt_root / "planner_system.md",
            max_steps=self.config.runtime.max_executor_steps,
        )
        user_prompt = render_prompt(
            self.config.prompt_root / "planner_user.md",
            task_json=self._task_json(task),
            skill_name=active_skill.header.name,
            skill_md=active_skill.full_text,
            resources_json=json.dumps(active_skill.resources, ensure_ascii=False, indent=2),
            tool_catalog_json=self._tool_catalog_json(tool_specs),
        )
        payload, llm_result = self.planner_llm.chat_json(
            [
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=user_prompt),
            ]
        )
        log_llm_call(log_dir, "planner", llm_result)
        allowed_names = {spec.name for spec in tool_specs}
        steps: list[PlannedStep] = []
        for item in payload.get("tool_sequence", []):
            if isinstance(item, str):
                tool_name = item.strip()
                reason = ""
            elif isinstance(item, dict):
                tool_name = str(item.get("tool_name", item.get("name", item.get("tool", "")))).strip()
                reason = str(item.get("reason", item.get("rationale", ""))).strip()
            else:
                continue
            if not tool_name or tool_name not in allowed_names:
                continue
            steps.append(PlannedStep(tool_name=tool_name, reason=reason))
            if len(steps) >= self.config.runtime.max_executor_steps:
                break
        if not steps:
            raise ValueError("Planner did not return any valid tools under the active tool scope.")
        plan_summary = str(payload.get("plan_summary", payload.get("summary", ""))).strip()
        return steps, plan_summary, llm_result.text

    def _truncate(self, value: Any, limit: int = 1600) -> str:
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
        return text if len(text) <= limit else text[: limit - 14] + "\n[truncated]"

    def _build_worker_prompt(
        self,
        *,
        task: DatasetTask,
        active_skill: SkillDetail,
        rendered_tools: str,
        planned_step: PlannedStep,
        prior_steps: list[str],
        latest_observation: str,
    ) -> str:
        context_lines = [f"Original question:\n{task.prompt}", f"Planned next tool:\n{planned_step.tool_name}"]
        if planned_step.reason:
            context_lines.append(f"Planner rationale:\n{planned_step.reason}")
        if prior_steps:
            context_lines.append("Executed steps so far:\n" + "\n".join(f"- {item}" for item in prior_steps))
        if latest_observation:
            context_lines.append("Latest observation:\n" + latest_observation)
        context_block = "\n\n".join(context_lines)
        return render_prompt(
            self.config.prompt_root / "planner_worker_user.md",
            skill_name=active_skill.header.name,
            context_block=context_block,
            data_path=task.data_dir,
            rendered_tools=rendered_tools,
        )

    def _execute_plan(
        self,
        task: DatasetTask,
        active_skill: SkillDetail,
        planned_steps: list[PlannedStep],
        tool_specs: list[ToolSpec],
        log_dir: Path,
    ) -> list[ToolCallRecord]:
        rendered_tools = self._render_worker_tools(tool_specs)
        records: list[ToolCallRecord] = []
        prior_steps: list[str] = []
        latest_observation = ""

        self.toolbox.set_active_skill_dir(active_skill.header.skill_dir)
        try:
            for step_index, planned_step in enumerate(planned_steps, start=1):
                worker_prompt = self._build_worker_prompt(
                    task=task,
                    active_skill=active_skill,
                    rendered_tools=rendered_tools,
                    planned_step=planned_step,
                    prior_steps=prior_steps,
                    latest_observation=latest_observation,
                )
                try:
                    decision = choose_tool_arguments(
                        worker_prompt,
                        planned_tool_name=planned_step.tool_name,
                    )
                    raw_result = self.toolbox.execute(planned_step.tool_name, decision.arguments)
                    observation = json.dumps(raw_result, ensure_ascii=False, default=str)
                    success = True
                    error = ""
                except Exception as exc:
                    decision = None
                    raw_result = {"error": str(exc)}
                    observation = json.dumps(raw_result, ensure_ascii=False)
                    success = False
                    error = str(exc)
                records.append(
                    ToolCallRecord(
                        step_index=step_index,
                        thought=planned_step.reason if decision is None else decision.rationale or planned_step.reason,
                        tool_name=planned_step.tool_name,
                        arguments={} if decision is None else decision.arguments,
                        observation=observation,
                        success=success,
                        raw_result=raw_result,
                        error=error,
                    )
                )
                write_json(
                    log_dir / f"step_{step_index:02d}.json",
                    {
                        "step_index": step_index,
                        "planned_tool_name": planned_step.tool_name,
                        "planner_reason": planned_step.reason,
                        "worker_prompt": worker_prompt,
                        "arguments": {} if decision is None else decision.arguments,
                        "worker_rationale": "" if decision is None else decision.rationale,
                        "success": success,
                        "raw_result": raw_result,
                        "error": error,
                    },
                )
                latest_observation = self._truncate(observation)
                prior_steps.append(f"{planned_step.tool_name}: {self._truncate(raw_result, 240)}")
                if not success:
                    break
        finally:
            self.toolbox.set_active_skill_dir(None)
        return records

    def _selection_user_prompt(
        self,
        task: DatasetTask,
        planned_steps: list[PlannedStep],
        tool_records: list[ToolCallRecord],
        plan_summary: str,
    ) -> str:
        execution_summary = "\n".join(
            f"{record.step_index}. {record.tool_name} success={record.success} observation={self._truncate(record.raw_result, 300)}"
            for record in tool_records
        )
        return render_prompt(
            self.config.prompt_root / "planner_answer_selector_user.md",
            task_json=self._task_json(task),
            plan_summary=plan_summary or "(empty)",
            planned_tools_json=json.dumps([step.__dict__ for step in planned_steps], ensure_ascii=False, indent=2),
            execution_summary=execution_summary or "(no execution steps)",
        )

    def _select_final_answer(
        self,
        task: DatasetTask,
        planned_steps: list[PlannedStep],
        tool_records: list[ToolCallRecord],
        plan_summary: str,
        log_dir: Path,
    ) -> tuple[str, str, str, str]:
        system_prompt = render_prompt(self.config.prompt_root / "planner_answer_selector_system.md")
        user_prompt = self._selection_user_prompt(task, planned_steps, tool_records, plan_summary)
        payload, llm_result = self.answer_selector_llm.chat_json(
            [
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=user_prompt),
            ]
        )
        log_llm_call(log_dir, "planner_answer_selector", llm_result)
        choice_label = str(payload.get("choice_label", "")).strip().upper()
        if not choice_label:
            choice_index = payload.get("choice_index")
            if isinstance(choice_index, int) and 1 <= choice_index <= len(task.choices):
                choice_label = chr(ord("A") + choice_index - 1)
        if choice_label not in {"A", "B", "C", "D"}:
            choice_label = ""
        final_answer = str(payload.get("final_answer", "")).strip()
        if not final_answer and choice_label:
            choice_index = ord(choice_label) - ord("A")
            if 0 <= choice_index < len(task.choices):
                final_answer = str(task.choices[choice_index])
        summary = str(payload.get("summary", payload.get("reason", ""))).strip()
        return final_answer, choice_label, summary, llm_result.text

    def execute(self, task: DatasetTask, run_dir: Path, *, active_skill: SkillDetail) -> EnvRunResult:
        tool_specs = self._active_tool_specs(active_skill)
        planned_steps, plan_summary, raw_planner_output = self._plan(task, active_skill, tool_specs, run_dir / "planner")
        tool_records = self._execute_plan(task, active_skill, planned_steps, tool_specs, run_dir / "planner_execution")
        final_answer, choice_label, selector_summary, raw_selector_output = self._select_final_answer(
            task,
            planned_steps,
            tool_records,
            plan_summary,
            run_dir / "planner_answer_selector",
        )
        summary_parts = [part for part in [plan_summary, selector_summary] if part]
        env_result = EnvRunResult(
            final_answer=final_answer,
            final_choice_label=choice_label,
            tool_trajectory=tool_records,
            executor_summary=" ".join(summary_parts).strip(),
            raw_executor_output=raw_selector_output,
            execution_mode="planner",
            planner_summary=plan_summary,
            planned_tool_sequence=[step.tool_name for step in planned_steps],
            raw_planner_output=raw_planner_output,
        )
        env_result.evaluation = evaluate_execution(
            final_choice_label=env_result.final_choice_label,
            final_answer=env_result.final_answer,
            executed_steps=tool_records,
            gold_tool_names=task.gold_tool_names,
            gold_trajectory=task.gold_trajectory,
            gold_answer=task.gold_answer,
        )
        return env_result
