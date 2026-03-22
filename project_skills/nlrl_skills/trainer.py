from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from pathlib import Path
import shutil
import threading

from .actor import SkillActor
from .config import SystemConfig
from .critic import SkillCritic
from .data import load_converted_dataset, select_task, select_tasks
from .environment import SkillEnvironment
from .schemas import DatasetTask, to_dict
from .skills import copy_skill_bundle, discover_skills
from .utils import ensure_dir, read_json, slugify, utc_timestamp, write_json


class SkillRLTrainer:
    def __init__(self, config: SystemConfig):
        self.config = config
        self.environment = SkillEnvironment(config)
        self.critic = SkillCritic(config)
        self.actor = SkillActor(config)

    def prepare_run_dir(self, run_name: str | None = None) -> Path:
        run_dir = self.config.run_root / (run_name or f"run_{utc_timestamp()}")
        ensure_dir(run_dir)
        write_json(run_dir / "config_snapshot.json", to_dict(self.config))
        return run_dir

    def _clone_config_for_task_runtime(
        self,
        *,
        run_root: Path,
        skill_library_root: Path,
        experience_buffer_path: Path,
    ) -> SystemConfig:
        cloned = deepcopy(self.config)
        cloned.paths.run_root = str(run_root).replace("\\", "/")
        cloned.paths.skill_library_root = str(skill_library_root).replace("\\", "/")
        cloned.paths.experience_buffer_path = str(experience_buffer_path).replace("\\", "/")
        return cloned

    def _promoted_skill_name(self, task_label: str, skill_index: int) -> str:
        return f"{slugify(task_label)}-skill-{skill_index:02d}"

    def _task_label(self, index: int, task: DatasetTask) -> str:
        return f"task_{index:02d}_{task.metadata.get('original_question_id', task.task_id)}"

    def _promote_successful_task_skills(
        self,
        *,
        source_skill_library_root: Path,
        promoted_skill_library_root: Path,
        task: DatasetTask,
        task_label: str,
    ) -> list[dict]:
        promoted: list[dict] = []
        original_question_id = str(task.metadata.get("original_question_id", ""))
        for skill_index, header in enumerate(discover_skills(source_skill_library_root), start=1):
            promoted_skill_name = self._promoted_skill_name(task_label, skill_index)
            copy_skill_bundle(
                Path(header.skill_dir),
                promoted_skill_library_root,
                promoted_skill_name,
                metadata_updates={
                    "model3_source_task_id": task.task_id,
                    "model3_source_question_id": original_question_id,
                    "model3_source_task_label": task_label,
                    "model3_source_skill_name": header.name,
                    "model3_promotion_mode": "success_only",
                },
            )
            promoted.append(
                {
                    "skill_name": promoted_skill_name,
                    "source_skill_name": header.name,
                    "description": header.description,
                    "source_task_id": task.task_id,
                    "source_question_id": original_question_id,
                    "source_task_label": task_label,
                    "relative_skill_dir": f"successful_skill_library/{promoted_skill_name}",
                }
            )
        return promoted

    def _cleanup_task_runtime(self, task_runtime_root: Path) -> None:
        if task_runtime_root.exists():
            shutil.rmtree(task_runtime_root, ignore_errors=True)

    def _load_selected_tasks_from_run(self, *, tasks: list[DatasetTask], run_dir: Path) -> list[DatasetTask]:
        selected_records = read_json(run_dir / "selected_tasks.json")
        if not isinstance(selected_records, list):
            raise ValueError(f"Run does not contain a valid selected_tasks.json: {run_dir}")
        tasks_by_id = {task.task_id: task for task in tasks}
        selected_tasks: list[DatasetTask] = []
        missing_task_ids: list[str] = []
        for record in selected_records:
            if not isinstance(record, dict):
                continue
            task_id = str(record.get("task_id", "")).strip()
            task = tasks_by_id.get(task_id)
            if task is None:
                missing_task_ids.append(task_id)
                continue
            selected_tasks.append(task)
        if missing_task_ids:
            preview = ", ".join(missing_task_ids[:5])
            raise KeyError(f"Unable to resume run; task ids missing from dataset: {preview}")
        return selected_tasks

    def _collect_model3_task_summaries(self, *, run_dir: Path, selected_tasks: list[DatasetTask]) -> list[dict]:
        task_summaries: list[dict] = []
        for index, task in enumerate(selected_tasks, start=1):
            task_label = self._task_label(index, task)
            summary_path = run_dir / task_label / "task_summary.json"
            summary = read_json(summary_path)
            if isinstance(summary, dict):
                task_summaries.append(summary)
        return task_summaries

    def _write_model3_run_outputs(
        self,
        *,
        run_dir: Path,
        selected_tasks: list[DatasetTask],
        effective_concurrency: int,
    ) -> None:
        promoted_skill_library_root = ensure_dir(run_dir / "successful_skill_library")
        resolved_task_summaries = self._collect_model3_task_summaries(run_dir=run_dir, selected_tasks=selected_tasks)
        successful_skill_records = sorted(
            [
                skill_record
                for summary in resolved_task_summaries
                for skill_record in summary.get("promoted_skills", [])
            ],
            key=lambda item: item["skill_name"],
        )
        final_skill_headers = [header.__dict__ for header in discover_skills(promoted_skill_library_root)]
        write_json(
            run_dir / "successful_skill_summary.json",
            {
                "successful_task_count": sum(1 for summary in resolved_task_summaries if summary.get("task_success")),
                "failed_task_count": sum(1 for summary in resolved_task_summaries if not summary.get("task_success")),
                "promotion_error_count": sum(1 for summary in resolved_task_summaries if summary.get("promotion_error")),
                "skill_count": len(final_skill_headers),
                "successful_skill_library_root": str(promoted_skill_library_root),
                "skills": successful_skill_records,
            },
        )
        run_summary = {
            "training_mode": "model3_parallel_success_only",
            "task_count": len(selected_tasks),
            "task_concurrency": effective_concurrency,
            "successful_skill_library_root": str(promoted_skill_library_root),
            "tasks": resolved_task_summaries,
            "final_skill_headers": final_skill_headers,
        }
        write_json(run_dir / "run_summary.json", run_summary)

    def train_task(self, task: DatasetTask, task_run_dir: Path) -> dict:
        write_json(task_run_dir / "task.json", task.__dict__)
        iteration_records: list[dict] = []
        task_success = False

        for iteration_index in range(1, self.config.runtime.max_iterations_per_task + 1):
            iteration_dir = ensure_dir(task_run_dir / f"iteration_{iteration_index:02d}")
            skill_headers = discover_skills(self.config.skill_library_root)
            write_json(iteration_dir / "skill_headers_before.json", [header.__dict__ for header in skill_headers])
            try:
                state = self.environment.run(task, skill_headers, iteration_dir / "env")
            except Exception as exc:
                write_json(
                    iteration_dir / "iteration_failure.json",
                    {
                        "iteration_index": iteration_index,
                        "error": str(exc),
                    },
                )
                iteration_records.append(
                    {
                        "iteration_index": iteration_index,
                        "error": str(exc),
                    }
                )
                break

            if state.env_result.evaluation.task_success:
                task_success = True
                write_json(
                    iteration_dir / "iteration_summary.json",
                    {
                        "iteration_index": iteration_index,
                        "status": "task_success",
                        "evaluation": state.env_result.evaluation.__dict__,
                        "critic_skipped": True,
                    },
                )
                iteration_records.append(
                    {
                        "iteration_index": iteration_index,
                        "status": "task_success",
                        "evaluation": state.env_result.evaluation.__dict__,
                        "critic_skipped": True,
                        "actor_decision": None,
                    }
                )
                break

            try:
                reward = self.critic.evaluate(state, iteration_dir / "critic")
            except Exception as exc:
                write_json(
                    iteration_dir / "iteration_failure.json",
                    {
                        "iteration_index": iteration_index,
                        "error": str(exc),
                        "evaluation": state.env_result.evaluation.__dict__,
                    },
                )
                iteration_records.append(
                    {
                        "iteration_index": iteration_index,
                        "evaluation": state.env_result.evaluation.__dict__,
                        "error": str(exc),
                    }
                )
                break

            try:
                decision = self.actor.act(state, reward, iteration_dir / "actor")
                self.actor.apply(decision)
            except Exception as exc:
                write_json(
                    iteration_dir / "iteration_failure.json",
                    {
                        "iteration_index": iteration_index,
                        "error": str(exc),
                    },
                )
                iteration_records.append(
                    {
                        "iteration_index": iteration_index,
                        "evaluation": state.env_result.evaluation.__dict__,
                        "reward": reward.__dict__,
                        "error": str(exc),
                    }
                )
                break
            write_json(iteration_dir / "skill_headers_after.json", [header.__dict__ for header in discover_skills(self.config.skill_library_root)])
            write_json(
                iteration_dir / "iteration_summary.json",
                {
                    "iteration_index": iteration_index,
                    "evaluation": state.env_result.evaluation.__dict__,
                    "reward": reward.__dict__,
                    "actor_decision": decision.__dict__ | {"experience_entry": None if decision.experience_entry is None else decision.experience_entry.__dict__},
                },
            )
            iteration_records.append(
                {
                    "iteration_index": iteration_index,
                    "evaluation": state.env_result.evaluation.__dict__,
                    "reward": reward.__dict__,
                    "actor_decision": decision.__dict__ | {"experience_entry": None if decision.experience_entry is None else decision.experience_entry.__dict__},
                }
            )

        task_summary = {
            "task_id": task.task_id,
            "original_question_id": task.metadata.get("original_question_id", ""),
            "task_success": task_success,
            "iterations": iteration_records,
            "final_skill_headers": [header.__dict__ for header in discover_skills(self.config.skill_library_root)],
        }
        write_json(task_run_dir / "task_summary.json", task_summary)
        return task_summary

    def train_single_task(self, task_id: str | None = None, *, run_name: str | None = None) -> Path:
        tasks = load_converted_dataset(self.config.converted_dataset_path)
        task = select_task(tasks, task_id)
        run_dir = self.prepare_run_dir(run_name)
        task_summary = self.train_task(task, run_dir)
        write_json(run_dir / "run_summary.json", task_summary)
        return run_dir

    def train_tasks(
        self,
        *,
        task_ids: list[str] | None = None,
        count: int | None = None,
        start_index: int = 0,
        run_name: str | None = None,
    ) -> Path:
        tasks = load_converted_dataset(self.config.converted_dataset_path)
        selected_tasks = select_tasks(tasks, task_ids=task_ids, count=count, start_index=start_index)
        run_dir = self.prepare_run_dir(run_name)
        write_json(
            run_dir / "selected_tasks.json",
            [
                {
                    "task_id": task.task_id,
                    "original_question_id": task.metadata.get("original_question_id", ""),
                    "prompt": task.prompt,
                }
                for task in selected_tasks
            ],
        )
        task_summaries: list[dict] = []
        for index, task in enumerate(selected_tasks, start=1):
            task_run_dir = ensure_dir(run_dir / f"task_{index:02d}_{task.metadata.get('original_question_id', task.task_id)}")
            task_summaries.append(self.train_task(task, task_run_dir))
        run_summary = {
            "task_count": len(selected_tasks),
            "tasks": task_summaries,
            "final_skill_headers": [header.__dict__ for header in discover_skills(self.config.skill_library_root)],
        }
        write_json(run_dir / "run_summary.json", run_summary)
        return run_dir

    def train_tasks_model3(
        self,
        *,
        task_ids: list[str] | None = None,
        count: int | None = None,
        start_index: int = 0,
        run_name: str | None = None,
        concurrency: int | None = None,
        resume: bool = False,
    ) -> Path:
        tasks = load_converted_dataset(self.config.converted_dataset_path)
        if resume:
            if not run_name:
                raise ValueError("--resume requires --run-name for train-model3.")
            run_dir = self.config.run_root / run_name
            if not run_dir.exists():
                raise FileNotFoundError(f"Resume target run directory does not exist: {run_dir}")
            selected_tasks = self._load_selected_tasks_from_run(tasks=tasks, run_dir=run_dir)
        else:
            selected_tasks = select_tasks(tasks, task_ids=task_ids, count=count, start_index=start_index)
            run_dir = self.prepare_run_dir(run_name)
        promoted_skill_library_root = ensure_dir(run_dir / "successful_skill_library")
        effective_concurrency = max(1, concurrency or self.config.runtime.task_concurrency)
        if concurrency is not None and concurrency != self.config.runtime.task_concurrency:
            config_snapshot = to_dict(self.config)
            runtime_snapshot = config_snapshot.setdefault("runtime", {})
            if isinstance(runtime_snapshot, dict):
                runtime_snapshot["task_concurrency"] = effective_concurrency
            write_json(run_dir / "config_snapshot.json", config_snapshot)
        write_json(
            run_dir / "model3_settings.json",
            {
                "training_mode": "model3_parallel_success_only",
                "task_concurrency": effective_concurrency,
                "max_iterations_per_task": self.config.runtime.max_iterations_per_task,
                "max_executor_steps": self.config.runtime.max_executor_steps,
                "promoted_skill_library_root": str(promoted_skill_library_root),
                "local_task_runtime_pattern": "task_xx/_runtime",
                "promotion_policy": "successful-task-skills-only",
                "failed_task_policy": "discard-local-skill-library",
                "resume_enabled": resume,
            },
        )
        if not resume:
            write_json(
                run_dir / "selected_tasks.json",
                [
                    {
                        "task_id": task.task_id,
                        "original_question_id": task.metadata.get("original_question_id", ""),
                        "prompt": task.prompt,
                    }
                    for task in selected_tasks
                ],
            )

        promotion_lock = threading.Lock()

        def _run_one_task(index: int, task: DatasetTask) -> tuple[int, dict]:
            task_label = self._task_label(index, task)
            task_run_dir = ensure_dir(run_dir / task_label)
            task_runtime_root = task_run_dir / "_runtime"
            task_config = self._clone_config_for_task_runtime(
                run_root=task_runtime_root,
                skill_library_root=task_runtime_root / "skill_library",
                experience_buffer_path=task_runtime_root / "experience_buffer.jsonl",
            )

            try:
                task_trainer = SkillRLTrainer(task_config)
                task_summary = task_trainer.train_task(task, task_run_dir)
            except Exception as exc:
                task_summary = {
                    "task_id": task.task_id,
                    "original_question_id": task.metadata.get("original_question_id", ""),
                    "task_success": False,
                    "iterations": [],
                    "fatal_error": str(exc),
                    "final_skill_headers": [header.__dict__ for header in discover_skills(task_config.skill_library_root)],
                }

            promoted_skills: list[dict] = []
            promotion_error = ""
            if task_summary.get("task_success"):
                try:
                    with promotion_lock:
                        promoted_skills = self._promote_successful_task_skills(
                            source_skill_library_root=task_config.skill_library_root,
                            promoted_skill_library_root=promoted_skill_library_root,
                            task=task,
                            task_label=task_label,
                        )
                except Exception as exc:
                    promotion_error = str(exc)

            final_skill_headers = task_summary.get("final_skill_headers", [])
            task_summary["promoted_skills"] = promoted_skills
            task_summary["promoted_skill_count"] = len(promoted_skills)
            task_summary["promotion_error"] = promotion_error
            task_summary["discarded_generated_skill_count"] = 0 if task_summary.get("task_success") else len(final_skill_headers)
            task_summary["local_task_runtime_root"] = str(task_runtime_root)

            self._cleanup_task_runtime(task_runtime_root)
            task_summary["isolated_runtime_cleaned"] = True
            write_json(task_run_dir / "task_summary.json", task_summary)
            return index - 1, task_summary

        pending_tasks: list[tuple[int, DatasetTask]] = []
        for index, task in enumerate(selected_tasks, start=1):
            task_label = self._task_label(index, task)
            task_run_dir = run_dir / task_label
            summary_path = task_run_dir / "task_summary.json"
            if resume and summary_path.exists():
                continue
            if resume and task_run_dir.exists():
                shutil.rmtree(task_run_dir, ignore_errors=True)
            pending_tasks.append((index, task))

        if pending_tasks:
            worker_count = min(effective_concurrency, len(pending_tasks))
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                futures = [
                    executor.submit(_run_one_task, index, task)
                    for index, task in pending_tasks
                ]
                for future in as_completed(futures):
                    future.result()

        self._write_model3_run_outputs(
            run_dir=run_dir,
            selected_tasks=selected_tasks,
            effective_concurrency=effective_concurrency,
        )
        return run_dir
