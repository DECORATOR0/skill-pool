from __future__ import annotations

import ast
import importlib.util
import inspect
import json
import subprocess
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Union, get_args, get_origin, get_type_hints

from .utils import ensure_dir, read_text, write_text

EO_TOOL_FILES = ["Index.py", "Inversion.py", "Perception.py", "Analysis.py", "Statistics.py"]
_RESULT_PATH_PREFIXES = ("Result saved at ", "Result save at ")


def _compute_tvdi_batch_signature(
    ndvi_path: str | list[str],
    lst_path: str | list[str],
    output_path: str | list[str],
) -> str | list[str]:
    raise NotImplementedError


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    callable: Callable[..., Any]
    source: str
    signature_callable: Callable[..., Any] | None = None

    def prompt_entry(self) -> str:
        return json.dumps(
            {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
                "source": self.source,
            },
            ensure_ascii=False,
        )

    def debug_entry(self) -> dict[str, Any]:
        signature_target = self.signature_callable or self.callable
        signature = inspect.signature(signature_target)
        return {
            "name": self.name,
            "description": self.description,
            "source": self.source,
            "prompt_parameters": self.parameters,
            "python_signature": str(signature),
            "python_parameters": [
                {
                    "name": param.name,
                    "kind": str(param.kind),
                    "annotation": _annotation_repr(param.annotation),
                    "has_default": param.default is not inspect._empty,
                    "default": None if param.default is inspect._empty else repr(param.default),
                }
                for param in signature.parameters.values()
            ],
            "python_return_annotation": _annotation_repr(signature.return_annotation),
        }


def _truncate(value: Any, limit: int = 4000) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return text[:limit]


def _annotation_repr(annotation: Any) -> str:
    if annotation is inspect._empty:
        return ""
    if isinstance(annotation, str):
        return annotation
    if getattr(annotation, "__module__", "") == "builtins":
        return getattr(annotation, "__name__", repr(annotation))
    return repr(annotation)


def _annotation_to_schema(annotation: Any) -> dict[str, Any]:
    if annotation is inspect._empty or annotation is Any:
        return {"type": "string"}
    if annotation is None or annotation is type(None):
        return {"type": "null"}
    if annotation is bool:
        return {"type": "boolean"}
    if annotation is int:
        return {"type": "integer"}
    if annotation is float:
        return {"type": "number"}
    if annotation is str:
        return {"type": "string"}
    origin = get_origin(annotation)
    if origin in (Union, types.UnionType):
        return {"anyOf": [_annotation_to_schema(arg) for arg in get_args(annotation)]}
    if origin in (list, tuple, set):
        args = get_args(annotation)
        item_annotation = args[0] if args else Any
        return {"type": "array", "items": _annotation_to_schema(item_annotation)}
    if origin is dict:
        args = get_args(annotation)
        value_annotation = args[1] if len(args) >= 2 else Any
        return {"type": "object", "additionalProperties": _annotation_to_schema(value_annotation)}
    if annotation in (list, tuple, set):
        return {"type": "array"}
    if annotation is dict:
        return {"type": "object"}
    return {"type": "string"}


def _schema_from_signature(
    signature_target: Callable[..., Any],
    *,
    parameter_descriptions: dict[str, str] | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {"type": "object", "properties": {}, "required": []}
    try:
        resolved_annotations = get_type_hints(signature_target)
    except Exception:
        resolved_annotations = {}
    for param in inspect.signature(signature_target).parameters.values():
        if param.name == "self":
            continue
        annotation = resolved_annotations.get(param.name, param.annotation)
        param_schema = _annotation_to_schema(annotation)
        param_schema["description"] = (parameter_descriptions or {}).get(param.name, f"Argument {param.name}")
        params["properties"][param.name] = param_schema
        if param.default is inspect._empty:
            params["required"].append(param.name)
    return params


def _workspace_relative_path(base_dir: Path, user_path: str) -> Path:
    normalized = user_path.replace("\\", "/").strip()
    path = Path(normalized)
    if path.is_absolute():
        return path
    if any(part == ".." for part in path.parts):
        raise ValueError(f"Path escapes base directory: {user_path}")
    return base_dir.joinpath(*[part for part in path.parts if part not in {"", "."}])


class EOToolRuntime:
    def __init__(self, workspace_root: Path, temp_root: Path):
        self.workspace_root = workspace_root
        self.tools_dir = workspace_root / "agent" / "tools"
        self.temp_root = ensure_dir(temp_root)
        self._registry: dict[str, ToolSpec] = {}
        self._load_all()

    def _tool_signature_target(self, tool_name: str, func: Callable[..., Any]) -> Callable[..., Any]:
        if tool_name == "compute_tvdi":
            return _compute_tvdi_batch_signature
        return func

    def _tool_parameter_descriptions(self, tool_name: str) -> dict[str, str]:
        if tool_name == "compute_tvdi":
            return {
                "ndvi_path": "Single NDVI raster path, or an aligned list of NDVI raster paths for one batched TVDI call.",
                "lst_path": "Single LST raster path, or an aligned list of LST raster paths in the same order as ndvi_path.",
                "output_path": "Single relative output path, or aligned output paths for batched TVDI generation.",
            }
        return {}

    def _is_output_argument(self, param_name: str) -> bool:
        normalized = param_name.lower()
        return any(token in normalized for token in ("output", "save", "result"))

    def _is_input_path_argument(self, param_name: str) -> bool:
        normalized = param_name.lower()
        if self._is_output_argument(normalized):
            return False
        return (
            normalized == "path"
            or normalized == "dir_path"
            or normalized.endswith("_path")
            or normalized.endswith("_file")
            or normalized.endswith("_dir")
            or "file_path" in normalized
            or "image_path" in normalized
        )

    def _is_input_path_list_argument(self, param_name: str) -> bool:
        normalized = param_name.lower()
        if self._is_output_argument(normalized):
            return False
        return (
            normalized in {"paths", "files"}
            or normalized.endswith("_paths")
            or normalized.endswith("_files")
            or "file_list" in normalized
            or "path_list" in normalized
            or "image_list" in normalized
        )

    def _normalize_path_key(self, value: str) -> str:
        return value.replace("\\", "/").strip()

    def _resolve_workspace_input_path(
        self,
        value: str,
        *,
        data_dir: Path | None = None,
        path_aliases: dict[str, str] | None = None,
    ) -> str:
        normalized = self._normalize_path_key(value)
        if not normalized:
            return value
        if path_aliases:
            aliased = path_aliases.get(normalized)
            if aliased:
                return aliased
        if Path(normalized).is_absolute():
            return str(Path(normalized))
        workspace_candidate = _workspace_relative_path(self.workspace_root, normalized)
        if workspace_candidate.exists():
            return str(workspace_candidate)
        if data_dir is not None:
            try:
                data_candidate = _workspace_relative_path(data_dir, normalized)
            except ValueError:
                data_candidate = None
            if data_candidate is not None and data_candidate.exists():
                return str(data_candidate)
        temp_candidate = _workspace_relative_path(self.temp_root, normalized)
        if temp_candidate.exists():
            return str(temp_candidate)
        for child in self.temp_root.iterdir():
            if not child.is_dir():
                continue
            child_candidate = _workspace_relative_path(child, normalized)
            if child_candidate.exists():
                return str(child_candidate)
        return str(workspace_candidate)

    def _normalize_argument(
        self,
        param_name: str,
        value: Any,
        *,
        data_dir: Path | None = None,
        path_aliases: dict[str, str] | None = None,
    ) -> Any:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                for parser in (json.loads, ast.literal_eval):
                    try:
                        parsed = parser(stripped)
                    except Exception:
                        continue
                    if isinstance(parsed, list):
                        value = parsed
                        break
        if isinstance(value, str) and self._is_input_path_argument(param_name):
            return self._resolve_workspace_input_path(value, data_dir=data_dir, path_aliases=path_aliases)
        if isinstance(value, list) and (
            self._is_input_path_list_argument(param_name) or self._is_input_path_argument(param_name)
        ):
            return [
                self._resolve_workspace_input_path(item, data_dir=data_dir, path_aliases=path_aliases)
                if isinstance(item, str)
                else item
                for item in value
            ]
        return value

    def _parse_tool_nodes(self, path: Path) -> list[tuple[str, str, dict[str, Any]]]:
        tree = ast.parse(read_text(path))
        parsed: list[tuple[str, str, dict[str, Any]]] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            decorator_src = " ".join(ast.unparse(d) for d in node.decorator_list)
            if "mcp.tool" not in decorator_src:
                continue
            description = ""
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call):
                    for kw in dec.keywords:
                        if kw.arg == "description" and isinstance(kw.value, ast.Constant):
                            description = str(kw.value.value).strip()
            params: dict[str, Any] = {"type": "object", "properties": {}, "required": []}
            for arg in node.args.args:
                if arg.arg == "self":
                    continue
                params["properties"][arg.arg] = {
                    "type": "string",
                    "description": f"Argument {arg.arg}",
                }
            default_count = len(node.args.defaults)
            required_count = len(node.args.args) - default_count
            for idx, arg in enumerate(node.args.args):
                if arg.arg == "self":
                    continue
                if idx < required_count:
                    params["required"].append(arg.arg)
            parsed.append((node.name, description, params))
        return parsed

    def _load_module(self, module_file: str) -> Any:
        module_path = self.tools_dir / module_file
        module_name = f"nlrl_runtime_{module_path.stem.lower()}_{abs(hash(str(module_path))) % 100000}"
        old_argv = sys.argv[:]
        try:
            sys.argv = [str(module_path), "--temp_dir", str(self.temp_root / module_path.stem.lower())]
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            if spec is None or spec.loader is None:
                raise RuntimeError(f"Cannot load {module_path}")
            module = importlib.util.module_from_spec(spec)
            if str(self.tools_dir) not in sys.path:
                sys.path.insert(0, str(self.tools_dir))
            spec.loader.exec_module(module)
            return module
        finally:
            sys.argv = old_argv

    def _load_all(self) -> None:
        for module_file in EO_TOOL_FILES:
            source_path = self.tools_dir / module_file
            if not source_path.exists():
                continue
            parsed = {name: (desc, schema) for name, desc, schema in self._parse_tool_nodes(source_path)}
            module = self._load_module(module_file)
            for name, value in vars(module).items():
                if name not in parsed or not inspect.isfunction(value):
                    continue
                desc, _ = parsed[name]
                signature_target = self._tool_signature_target(name, value)
                schema = _schema_from_signature(
                    signature_target,
                    parameter_descriptions=self._tool_parameter_descriptions(name),
                )
                self._registry[name] = ToolSpec(
                    name=name,
                    description=desc or f"EO tool {name}",
                    parameters=schema,
                    callable=value,
                    source=f"agent/tools/{module_file}",
                    signature_callable=signature_target,
                )

    def specs(self) -> list[ToolSpec]:
        return [self._registry[name] for name in sorted(self._registry)]

    def _normalize_tool_result(self, result: Any) -> Any:
        if isinstance(result, str):
            for prefix in _RESULT_PATH_PREFIXES:
                if result.startswith(prefix):
                    return result[len(prefix) :].strip()
            return result
        if isinstance(result, list):
            return [self._normalize_tool_result(item) for item in result]
        if isinstance(result, tuple):
            return [self._normalize_tool_result(item) for item in result]
        return result

    def _execute_compute_tvdi(
        self,
        func: Callable[..., Any],
        arguments: dict[str, Any],
        *,
        data_dir: Path | None = None,
        path_aliases: dict[str, str] | None = None,
    ) -> Any:
        accepted = {
            name: self._normalize_argument(name, arguments[name], data_dir=data_dir, path_aliases=path_aliases)
            for name in ("ndvi_path", "lst_path", "output_path")
            if name in arguments
        }
        ndvi_value = accepted.get("ndvi_path")
        lst_value = accepted.get("lst_path")
        output_value = accepted.get("output_path")
        has_batch = any(isinstance(value, list) for value in (ndvi_value, lst_value, output_value))
        if not has_batch:
            return self._normalize_tool_result(func(**accepted))
        if not all(isinstance(value, list) for value in (ndvi_value, lst_value, output_value)):
            raise ValueError(
                "compute_tvdi batch mode requires ndvi_path, lst_path, and output_path to all be lists of equal length."
            )
        if not (len(ndvi_value) == len(lst_value) == len(output_value)):
            raise ValueError(
                "compute_tvdi batch mode requires ndvi_path, lst_path, and output_path to have the same length."
            )
        outputs: list[Any] = []
        for ndvi_path, lst_path, output_path in zip(ndvi_value, lst_value, output_value, strict=True):
            outputs.append(
                self._normalize_tool_result(
                    func(
                        ndvi_path=ndvi_path,
                        lst_path=lst_path,
                        output_path=output_path,
                    )
                )
            )
        return outputs

    def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        data_dir: Path | None = None,
        path_aliases: dict[str, str] | None = None,
    ) -> Any:
        if tool_name not in self._registry:
            raise KeyError(f"Unknown EO tool: {tool_name}")
        func = self._registry[tool_name].callable
        if tool_name == "compute_tvdi":
            return self._execute_compute_tvdi(
                func,
                arguments,
                data_dir=data_dir,
                path_aliases=path_aliases,
            )
        accepted: dict[str, Any] = {}
        sig = inspect.signature(func)
        for param_name, param in sig.parameters.items():
            if param.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY):
                if param_name in arguments:
                    accepted[param_name] = self._normalize_argument(
                        param_name,
                        arguments[param_name],
                        data_dir=data_dir,
                        path_aliases=path_aliases,
                    )
        return self._normalize_tool_result(func(**accepted))


@dataclass
class ToolContext:
    workspace_root: Path
    skill_library_root: Path
    temp_root: Path
    python_executable: str = "python"
    shell_program: str = "powershell"
    eo_runtime: EOToolRuntime | None = None
    active_skill_dir: Path | None = None
    active_task_data_dir: Path | None = None
    path_aliases: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        ensure_dir(self.workspace_root)
        ensure_dir(self.skill_library_root)
        ensure_dir(self.temp_root)
        if self.eo_runtime is None:
            self.eo_runtime = EOToolRuntime(self.workspace_root, self.temp_root / "eo_runtime")


class Toolbox:
    def __init__(self, context: ToolContext):
        self.context = context
        self._registry: dict[str, ToolSpec] = {}
        self._register_builtin_tools()
        for spec in self.context.eo_runtime.specs():
            self._registry[spec.name] = ToolSpec(
                name=spec.name,
                description=spec.description,
                parameters=spec.parameters,
                callable=self._wrap_eo_tool(spec.name),
                source=spec.source,
                signature_callable=spec.signature_callable or spec.callable,
            )

    def _register(self, spec: ToolSpec) -> None:
        self._registry[spec.name] = spec

    def set_active_skill_dir(self, skill_dir: str | Path | None) -> None:
        self.context.active_skill_dir = None if skill_dir is None else Path(skill_dir).resolve()

    def set_active_task_data_dir(self, data_dir: str | Path | None) -> None:
        if data_dir is None or str(data_dir).strip() == "":
            self.context.active_task_data_dir = None
            self.context.path_aliases.clear()
            return
        target = Path(str(data_dir).strip())
        if target.is_absolute():
            resolved = target.resolve()
        else:
            resolved = _workspace_relative_path(self.context.workspace_root, str(data_dir)).resolve()
        self.context.active_task_data_dir = resolved
        self.context.path_aliases.clear()

    def _resolve_workspace_path(self, user_path: str, *, prefer_existing: bool = True) -> Path:
        normalized = user_path.replace("\\", "/").strip()
        skill_dir = self.context.active_skill_dir
        skill_relative_prefixes = ("scripts", "references", "assets", "SKILL.md")
        if skill_dir is not None and (
            normalized == "SKILL.md"
            or normalized in {"scripts", "references", "assets"}
            or normalized.startswith("scripts/")
            or normalized.startswith("references/")
            or normalized.startswith("assets/")
        ):
            skill_target = _workspace_relative_path(skill_dir, normalized)
            if skill_target.exists() or not prefer_existing:
                return skill_target
        return _workspace_relative_path(self.context.workspace_root, normalized)

    def _wrap_eo_tool(self, tool_name: str) -> Callable[..., Any]:
        def _call(**kwargs: Any) -> Any:
            return self.context.eo_runtime.execute(
                tool_name,
                kwargs,
                data_dir=self.context.active_task_data_dir,
                path_aliases=self.context.path_aliases,
            )

        return _call

    def _is_output_argument(self, param_name: str) -> bool:
        normalized = param_name.lower()
        return any(token in normalized for token in ("output", "save", "result"))

    def _normalize_path_key(self, value: str) -> str:
        return value.replace("\\", "/").strip()

    def _record_output_aliases(self, tool_name: str, arguments: dict[str, Any], result: Any) -> None:
        spec = self._registry[tool_name]
        if spec.source == "built_in":
            return
        output_paths: list[str] = []
        for name, value in arguments.items():
            if not self._is_output_argument(name):
                continue
            if isinstance(value, str):
                output_paths.append(value)
            elif isinstance(value, list):
                output_paths.extend(item for item in value if isinstance(item, str))
        if not output_paths:
            return
        if isinstance(result, str):
            resolved_paths = [result]
        elif isinstance(result, list):
            resolved_paths = [item for item in result if isinstance(item, str)]
        else:
            return
        if len(output_paths) != len(resolved_paths):
            return
        for raw_output, resolved_output in zip(output_paths, resolved_paths, strict=True):
            normalized = self._normalize_path_key(raw_output)
            if normalized:
                self.context.path_aliases[normalized] = resolved_output

    def _register_builtin_tools(self) -> None:
        self._register(
            ToolSpec(
                name="list_dir",
                description="List files and directories under a workspace-relative path.",
                parameters={
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": [],
                },
                callable=self.list_dir,
                source="built_in",
            )
        )
        self._register(
            ToolSpec(
                name="read_file",
                description="Read a UTF-8 text file from the workspace.",
                parameters={
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
                callable=self.read_file,
                source="built_in",
            )
        )
        self._register(
            ToolSpec(
                name="write_file",
                description="Write a UTF-8 text file under the workspace.",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["path", "content"],
                },
                callable=self.write_file,
                source="built_in",
            )
        )
        self._register(
            ToolSpec(
                name="replace_in_file",
                description="Replace one exact string occurrence in a workspace file.",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "old_text": {"type": "string"},
                        "new_text": {"type": "string"},
                    },
                    "required": ["path", "old_text", "new_text"],
                },
                callable=self.replace_in_file,
                source="built_in",
            )
        )
        self._register(
            ToolSpec(
                name="glob_search",
                description="Glob files under the workspace using a relative pattern like benchmark/**/*.json.",
                parameters={
                    "type": "object",
                    "properties": {"pattern": {"type": "string"}},
                    "required": ["pattern"],
                },
                callable=self.glob_search,
                source="built_in",
            )
        )
        self._register(
            ToolSpec(
                name="run_shell",
                description="Run a non-interactive shell command from the workspace root.",
                parameters={
                    "type": "object",
                    "properties": {"command": {"type": "string"}},
                    "required": ["command"],
                },
                callable=self.run_shell,
                source="built_in",
            )
        )
        self._register(
            ToolSpec(
                name="run_python_script",
                description="Run a Python script under the workspace with optional string arguments.",
                parameters={
                    "type": "object",
                    "properties": {
                        "script_path": {"type": "string"},
                        "args": {"type": "array"},
                    },
                    "required": ["script_path"],
                },
                callable=self.run_python_script,
                source="built_in",
            )
        )

    def specs(self, allowed_tools: list[str] | None = None) -> list[ToolSpec]:
        if not allowed_tools:
            return [self._registry[name] for name in sorted(self._registry)]
        allowed = set(allowed_tools)
        return [spec for name, spec in sorted(self._registry.items()) if name in allowed]

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        if tool_name not in self._registry:
            raise KeyError(f"Unknown tool: {tool_name}")
        result = self._registry[tool_name].callable(**arguments)
        self._record_output_aliases(tool_name, arguments, result)
        return result

    def tool_prompt(self, allowed_tools: list[str] | None = None) -> str:
        return "\n".join(spec.prompt_entry() for spec in self.specs(allowed_tools))

    def tool_debug_specs(self, allowed_tools: list[str] | None = None) -> list[dict[str, Any]]:
        return [spec.debug_entry() for spec in self.specs(allowed_tools)]

    def list_dir(self, path: str = ".") -> list[str]:
        target = self._resolve_workspace_path(path)
        if not target.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")
        return sorted(p.name for p in target.iterdir())

    def read_file(self, path: str) -> str:
        target = self._resolve_workspace_path(path)
        return read_text(target)

    def write_file(self, path: str, content: str) -> str:
        target = self._resolve_workspace_path(path, prefer_existing=False)
        write_text(target, content)
        return f"Wrote {target}"

    def replace_in_file(self, path: str, old_text: str, new_text: str) -> str:
        target = self._resolve_workspace_path(path)
        source = read_text(target)
        if old_text not in source:
            raise ValueError("old_text was not found in file.")
        updated = source.replace(old_text, new_text, 1)
        write_text(target, updated)
        return f"Updated {target}"

    def glob_search(self, pattern: str) -> list[str]:
        return sorted(
            str(path.relative_to(self.context.workspace_root)).replace("\\", "/")
            for path in self.context.workspace_root.glob(pattern)
        )

    def run_shell(self, command: str) -> dict[str, Any]:
        completed = subprocess.run(
            [self.context.shell_program, "-Command", command],
            cwd=self.context.workspace_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        return {
            "returncode": completed.returncode,
            "stdout": _truncate(completed.stdout),
            "stderr": _truncate(completed.stderr),
        }

    def run_python_script(self, script_path: str, args: list[str] | None = None) -> dict[str, Any]:
        target = self._resolve_workspace_path(script_path)
        cmd = [self.context.python_executable, str(target), *(args or [])]
        completed = subprocess.run(
            cmd,
            cwd=self.context.workspace_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        return {
            "returncode": completed.returncode,
            "stdout": _truncate(completed.stdout),
            "stderr": _truncate(completed.stderr),
        }
