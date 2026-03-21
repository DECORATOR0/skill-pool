from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import project_skills.nlrl_skills.planner_runtime as planner_runtime_module
from project_skills.nlrl_skills.planner_runtime import PlannedStep, PlannerSkillRuntime
from project_skills.nlrl_skills.schemas import DatasetTask, SkillDetail, SkillHeader
from project_skills.nlrl_skills.tools import ToolContext, ToolSpec, Toolbox


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_toolbox_resolves_task_relative_inputs_and_output_aliases(tmp_path: Path) -> None:
    workspace_root = _workspace_root()
    context = ToolContext(
        workspace_root=workspace_root,
        skill_library_root=workspace_root / "skill_library",
        temp_root=tmp_path / "temp",
    )
    toolbox = Toolbox(context)
    toolbox.set_active_task_data_dir("benchmark/data/question1")
    try:
        result = toolbox.execute(
            "compute_tvdi",
            {
                "ndvi_path": "Xinjiang_2019-01-01_NDVI.tif",
                "lst_path": "Xinjiang_2019-01-01_LST.tif",
                "output_path": "question1/test_tvdi_runtime_fix.tif",
            },
        )
        assert Path(result).exists()
        assert toolbox.context.path_aliases["question1/test_tvdi_runtime_fix.tif"] == result

        ratio = toolbox.execute(
            "calculate_threshold_ratio",
            {
                "image_paths": "question1/test_tvdi_runtime_fix.tif",
                "threshold": 0.75,
                "mode": "above",
            },
        )
        assert isinstance(ratio, float)
    finally:
        toolbox.set_active_task_data_dir(None)


class _FailingToolbox:
    def __init__(self) -> None:
        self.active_skill_dir = None
        self.active_task_data_dir = None

    def set_active_skill_dir(self, skill_dir: str | None) -> None:
        self.active_skill_dir = skill_dir

    def set_active_task_data_dir(self, data_dir: str | None) -> None:
        self.active_task_data_dir = data_dir

    def execute(self, tool_name: str, arguments: dict[str, str]) -> str:
        raise FileNotFoundError(f"missing input for {tool_name}: {arguments}")


def test_planner_runtime_keeps_worker_arguments_on_execute_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime = PlannerSkillRuntime.__new__(PlannerSkillRuntime)
    runtime.toolbox = _FailingToolbox()
    runtime.parameter_worker_config = object()
    runtime._render_worker_tools = lambda tool_specs: ""
    runtime._build_worker_prompt = lambda **kwargs: "prompt"
    runtime._truncate = PlannerSkillRuntime._truncate.__get__(runtime, PlannerSkillRuntime)

    worker_args = {
        "ndvi_path": "Xinjiang_2019-01-01_NDVI.tif",
        "lst_path": "Xinjiang_2019-01-01_LST.tif",
        "output_path": "question1/tvdi_2019-01-01.tif",
    }
    monkeypatch.setattr(
        planner_runtime_module,
        "choose_tool_arguments",
        lambda *args, **kwargs: SimpleNamespace(arguments=worker_args, rationale="bind exact files"),
    )

    task = DatasetTask(
        task_id="task_01_1",
        source_type="benchmark",
        prompt="Compute the TVDI trend.",
        choices=["A", "B", "C", "D"],
        gold_answer="A",
        data_dir="benchmark/data/question1",
        file_list=[],
        gold_trajectory=[],
        gold_tool_names=[],
    )
    skill = SkillDetail(
        header=SkillHeader(
            name="dummy-skill",
            description="",
            skill_dir=str(tmp_path / "skill"),
            skill_md_path=str(tmp_path / "skill" / "SKILL.md"),
        ),
        body="",
        full_text="",
    )
    tool_specs = [
        ToolSpec(
            name="compute_tvdi",
            description="",
            parameters={},
            callable=lambda **kwargs: None,
            source="agent/tools/Index.py",
        )
    ]

    records = runtime._execute_plan(
        task,
        skill,
        [PlannedStep(tool_name="compute_tvdi", reason="derive drought index")],
        tool_specs,
        tmp_path / "planner_execution",
    )

    assert records[0].arguments == worker_args
    log_payload = json.loads((tmp_path / "planner_execution" / "step_01.json").read_text(encoding="utf-8"))
    assert log_payload["arguments"] == worker_args
    assert "missing input for compute_tvdi" in log_payload["error"]
