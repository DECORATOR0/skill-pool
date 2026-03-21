from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .utils import read_json


@dataclass
class LLMConfig:
    name: str
    model: str
    base_url: str
    api_key: str
    temperature: float = 0.2
    max_tokens: int | None = None
    timeout_seconds: int = 180
    enable_thinking: bool | None = None


@dataclass
class PathsConfig:
    workspace_root: str
    prompt_root: str
    run_root: str
    skill_library_root: str
    experience_buffer_path: str
    dataset_path: str
    converted_dataset_path: str
    docs_root: str


@dataclass
class RuntimeConfig:
    max_router_candidates: int = 64
    skill_match_threshold: float = 80.0
    skill_consumption_mode: str = "executor"
    max_executor_steps: int = 12
    max_actor_steps: int = 8
    max_iterations_per_task: int = 3
    skill_count_limit: int = 6
    python_executable: str = "python"
    shell_program: str = "powershell"

    @property
    def normalized_skill_consumption_mode(self) -> str:
        mode = self.skill_consumption_mode.strip().lower()
        return mode or "executor"

    @property
    def uses_planner_mode(self) -> bool:
        return self.normalized_skill_consumption_mode == "planner"


@dataclass
class SystemConfig:
    actor: LLMConfig
    critic: LLMConfig
    router: LLMConfig
    executor: LLMConfig
    paths: PathsConfig
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)

    @property
    def workspace_root(self) -> Path:
        return Path(self.paths.workspace_root).resolve()

    @property
    def prompt_root(self) -> Path:
        return Path(self.paths.prompt_root).resolve()

    @property
    def run_root(self) -> Path:
        return Path(self.paths.run_root).resolve()

    @property
    def skill_library_root(self) -> Path:
        return Path(self.paths.skill_library_root).resolve()

    @property
    def experience_buffer_path(self) -> Path:
        return Path(self.paths.experience_buffer_path).resolve()

    @property
    def dataset_path(self) -> Path:
        return Path(self.paths.dataset_path).resolve()

    @property
    def converted_dataset_path(self) -> Path:
        return Path(self.paths.converted_dataset_path).resolve()

    @property
    def docs_root(self) -> Path:
        return Path(self.paths.docs_root).resolve()


def _llm_from_dict(name: str, data: dict[str, Any]) -> LLMConfig:
    max_tokens: int | None = None
    if name == "router":
        if "max_tokens" in data and data["max_tokens"] is not None:
            max_tokens = int(data["max_tokens"])
    elif name == "executor":
        if "max_tokens" in data:
            max_tokens = None if data["max_tokens"] is None else int(data["max_tokens"])
        else:
            max_tokens = 32768
    return LLMConfig(
        name=name,
        model=data["model"],
        base_url=data["base_url"],
        api_key=data["api_key"],
        temperature=float(data.get("temperature", 0.2)),
        max_tokens=max_tokens,
        timeout_seconds=int(data.get("timeout_seconds", 180)),
        enable_thinking=None if "enable_thinking" not in data else bool(data["enable_thinking"]),
    )


def load_system_config(path: str | Path) -> SystemConfig:
    raw = read_json(Path(path))
    return SystemConfig(
        actor=_llm_from_dict("actor", raw["actor"]),
        critic=_llm_from_dict("critic", raw["critic"]),
        router=_llm_from_dict("router", raw["router"]),
        executor=_llm_from_dict("executor", raw["executor"]),
        paths=PathsConfig(**raw["paths"]),
        runtime=RuntimeConfig(**raw.get("runtime", {})),
    )
