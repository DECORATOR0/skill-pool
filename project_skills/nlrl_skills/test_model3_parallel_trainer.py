from __future__ import annotations

from pathlib import Path

from project_skills.nlrl_skills.config import LLMConfig, PathsConfig, RuntimeConfig, SystemConfig
from project_skills.nlrl_skills.skills import discover_skills, write_skill_bundle
from project_skills.nlrl_skills.trainer import SkillRLTrainer
from project_skills.nlrl_skills.utils import write_json


def _dummy_llm_config(name: str) -> LLMConfig:
    return LLMConfig(
        name=name,
        model=f"{name}-model",
        base_url="http://example.com/v1",
        api_key="test-key",
    )


def _make_config(tmp_path: Path, dataset_path: Path) -> SystemConfig:
    return SystemConfig(
        actor=_dummy_llm_config("actor"),
        critic=_dummy_llm_config("critic"),
        router=_dummy_llm_config("router"),
        executor=_dummy_llm_config("executor"),
        planner=_dummy_llm_config("planner"),
        parameter_worker=_dummy_llm_config("parameter_worker"),
        paths=PathsConfig(
            workspace_root=str(tmp_path / "workspace"),
            prompt_root=str(tmp_path / "prompts"),
            run_root=str(tmp_path / "runs"),
            skill_library_root=str(tmp_path / "skill_library"),
            experience_buffer_path=str(tmp_path / "runtime_state" / "experience_buffer.jsonl"),
            dataset_path=str(tmp_path / "question.json"),
            converted_dataset_path=str(dataset_path),
            docs_root=str(tmp_path / "docs"),
        ),
        runtime=RuntimeConfig(
            max_iterations_per_task=10,
            max_executor_steps=20,
            task_concurrency=2,
            skill_consumption_mode="planner",
        ),
    )


def _write_dataset(tmp_path: Path) -> Path:
    dataset_path = tmp_path / "converted_dataset.json"
    write_json(
        dataset_path,
        {
            "dataset_name": "test",
            "tasks": [
                {
                    "task_id": "earth-bench-c-2",
                    "source_type": "C",
                    "prompt": "Task two",
                    "choices": ["A", "B", "C", "D"],
                    "gold_answer": "A",
                    "data_dir": "benchmark/data/question2",
                    "file_list": [],
                    "gold_trajectory": [],
                    "gold_tool_names": [],
                    "metadata": {"original_question_id": "2"},
                },
                {
                    "task_id": "earth-bench-c-3",
                    "source_type": "C",
                    "prompt": "Task three",
                    "choices": ["A", "B", "C", "D"],
                    "gold_answer": "B",
                    "data_dir": "benchmark/data/question3",
                    "file_list": [],
                    "gold_trajectory": [],
                    "gold_tool_names": [],
                    "metadata": {"original_question_id": "3"},
                },
            ],
        },
    )
    return dataset_path


def test_train_tasks_model3_promotes_successful_task_skills_only(tmp_path: Path, monkeypatch) -> None:
    dataset_path = _write_dataset(tmp_path)
    config = _make_config(tmp_path, dataset_path)

    def fake_train_task(self: SkillRLTrainer, task, task_run_dir: Path) -> dict:
        task_run_dir.mkdir(parents=True, exist_ok=True)
        if task.metadata.get("original_question_id") == "2":
            write_skill_bundle(
                self.config.skill_library_root,
                "draft-local-skill",
                {
                    "SKILL.md": (
                        "---\n"
                        "name: draft-local-skill\n"
                        "description: Local draft skill.\n"
                        "consumption-mode: planner\n"
                        "allowed-tools: get_filelist compute_tvdi\n"
                        "---\n"
                        "# Draft\n"
                        "\n"
                        "## Skill Objective\n"
                        "Solve task two.\n"
                    )
                },
            )
            final_headers = [header.__dict__ for header in discover_skills(self.config.skill_library_root)]
            summary = {
                "task_id": task.task_id,
                "original_question_id": task.metadata.get("original_question_id", ""),
                "task_success": True,
                "iterations": [],
                "final_skill_headers": final_headers,
            }
        else:
            write_skill_bundle(
                self.config.skill_library_root,
                "failed-local-skill",
                {
                    "SKILL.md": (
                        "---\n"
                        "name: failed-local-skill\n"
                        "description: Failed local skill.\n"
                        "consumption-mode: planner\n"
                        "allowed-tools: get_filelist\n"
                        "---\n"
                        "# Failed\n"
                    )
                },
            )
            final_headers = [header.__dict__ for header in discover_skills(self.config.skill_library_root)]
            summary = {
                "task_id": task.task_id,
                "original_question_id": task.metadata.get("original_question_id", ""),
                "task_success": False,
                "iterations": [],
                "final_skill_headers": final_headers,
            }
        write_json(task_run_dir / "task_summary.json", summary)
        return summary

    monkeypatch.setattr(SkillRLTrainer, "train_task", fake_train_task)

    trainer = SkillRLTrainer(config)
    run_dir = trainer.train_tasks_model3(run_name="model3_parallel_test", concurrency=2)

    promoted_headers = discover_skills(run_dir / "successful_skill_library")
    assert [header.name for header in promoted_headers] == ["task-01-2-skill-01"]

    promoted_skill_text = (run_dir / "successful_skill_library" / "task-01-2-skill-01" / "SKILL.md").read_text(encoding="utf-8")
    assert "name: task-01-2-skill-01" in promoted_skill_text
    assert "model3_source_task_id: earth-bench-c-2" in promoted_skill_text
    assert "model3_source_skill_name: draft-local-skill" in promoted_skill_text

    task_one_summary = (run_dir / "task_01_2" / "task_summary.json").read_text(encoding="utf-8")
    task_two_summary = (run_dir / "task_02_3" / "task_summary.json").read_text(encoding="utf-8")
    assert '"promoted_skill_count": 1' in task_one_summary
    assert '"promoted_skill_count": 0' in task_two_summary
    assert not (run_dir / "task_01_2" / "_runtime").exists()
    assert not (run_dir / "task_02_3" / "_runtime").exists()


def test_train_tasks_model3_resume_skips_completed_tasks_and_reruns_pending(tmp_path: Path, monkeypatch) -> None:
    dataset_path = _write_dataset(tmp_path)
    config = _make_config(tmp_path, dataset_path)
    trainer = SkillRLTrainer(config)
    run_dir = trainer.prepare_run_dir("model3_resume_test")
    write_json(
        run_dir / "selected_tasks.json",
        [
            {
                "task_id": "earth-bench-c-2",
                "original_question_id": "2",
                "prompt": "Task two",
            },
            {
                "task_id": "earth-bench-c-3",
                "original_question_id": "3",
                "prompt": "Task three",
            },
        ],
    )
    existing_promoted_dir = write_skill_bundle(
        run_dir / "successful_skill_library",
        "task-01-2-skill-01",
        {
            "SKILL.md": (
                "---\n"
                "name: task-01-2-skill-01\n"
                "description: Existing promoted skill.\n"
                "consumption-mode: planner\n"
                "allowed-tools: get_filelist\n"
                "metadata:\n"
                "  model3_source_task_id: earth-bench-c-2\n"
                "  model3_source_skill_name: existing-skill\n"
                "---\n"
                "# Existing\n"
            )
        },
    )
    assert existing_promoted_dir.exists()
    task_one_dir = run_dir / "task_01_2"
    task_one_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        task_one_dir / "task_summary.json",
        {
            "task_id": "earth-bench-c-2",
            "original_question_id": "2",
            "task_success": True,
            "iterations": [],
            "final_skill_headers": [],
            "promoted_skills": [
                {
                    "skill_name": "task-01-2-skill-01",
                    "source_skill_name": "existing-skill",
                    "description": "Existing promoted skill.",
                    "source_task_id": "earth-bench-c-2",
                    "source_question_id": "2",
                    "source_task_label": "task_01_2",
                    "relative_skill_dir": "successful_skill_library/task-01-2-skill-01",
                }
            ],
            "promoted_skill_count": 1,
            "promotion_error": "",
            "discarded_generated_skill_count": 0,
            "isolated_runtime_cleaned": True,
        },
    )

    stale_partial_file = run_dir / "task_02_3" / "iteration_01" / "stale.txt"
    stale_partial_file.parent.mkdir(parents=True, exist_ok=True)
    stale_partial_file.write_text("stale", encoding="utf-8")

    call_log: list[str] = []

    def fake_train_task(self: SkillRLTrainer, task, task_run_dir: Path) -> dict:
        call_log.append(task.task_id)
        task_run_dir.mkdir(parents=True, exist_ok=True)
        write_skill_bundle(
            self.config.skill_library_root,
            "new-local-skill",
            {
                "SKILL.md": (
                    "---\n"
                    "name: new-local-skill\n"
                    "description: New local skill.\n"
                    "consumption-mode: planner\n"
                    "allowed-tools: get_filelist\n"
                    "---\n"
                    "# New\n"
                )
            },
        )
        summary = {
            "task_id": task.task_id,
            "original_question_id": task.metadata.get("original_question_id", ""),
            "task_success": True,
            "iterations": [],
            "final_skill_headers": [header.__dict__ for header in discover_skills(self.config.skill_library_root)],
        }
        write_json(task_run_dir / "task_summary.json", summary)
        return summary

    monkeypatch.setattr(SkillRLTrainer, "train_task", fake_train_task)

    resumed_run_dir = trainer.train_tasks_model3(run_name="model3_resume_test", concurrency=2, resume=True)

    assert resumed_run_dir == run_dir
    assert call_log == ["earth-bench-c-3"]
    assert not stale_partial_file.exists()

    promoted_headers = discover_skills(run_dir / "successful_skill_library")
    assert [header.name for header in promoted_headers] == ["task-01-2-skill-01", "task-02-3-skill-01"]

    run_summary_text = (run_dir / "run_summary.json").read_text(encoding="utf-8")
    successful_skill_summary_text = (run_dir / "successful_skill_summary.json").read_text(encoding="utf-8")
    assert '"task_count": 2' in run_summary_text
    assert '"successful_task_count": 2' in successful_skill_summary_text
    assert '"skill_count": 2' in successful_skill_summary_text
