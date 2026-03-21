from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path


EXCLUDED_RUN_NAMES = {"_isolated", "_launch_logs", "temp"}
TIMESTAMP_PREFIX = re.compile(r"^(?P<stamp>\d{8}_\d{4})_")


def read_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def sanitize(text: object, limit: int = 140) -> str:
    if text is None:
        return ""
    value = re.sub(r"\s+", " ", str(text)).strip().replace("|", "/")
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "…"


def parse_run_timestamp(run_dir: Path) -> datetime:
    match = TIMESTAMP_PREFIX.match(run_dir.name)
    if match:
        return datetime.strptime(match.group("stamp"), "%Y%m%d_%H%M")
    return datetime.fromtimestamp(run_dir.stat().st_ctime)


def format_run_timestamp(run_dir: Path) -> str:
    return parse_run_timestamp(run_dir).strftime("%Y-%m-%d %H:%M")


def get_run_display_name(run_dir: Path) -> str:
    match = TIMESTAMP_PREFIX.match(run_dir.name)
    if not match:
        return run_dir.name
    return run_dir.name[match.end() :]


def is_run_artifact_dir(run_dir: Path) -> bool:
    if (run_dir / "config_snapshot.json").exists():
        return True
    if (run_dir / "task_summary.json").exists() or (run_dir / "evaluation_summary.json").exists():
        return True
    return any(path.is_dir() for path in run_dir.glob("task_*"))


def iter_run_artifact_dirs(runs_root: Path) -> list[Path]:
    run_dirs: list[Path] = []
    seen: set[Path] = set()
    for child in runs_root.iterdir():
        if not child.is_dir() or child.name in EXCLUDED_RUN_NAMES:
            continue
        if is_run_artifact_dir(child):
            resolved = child.resolve()
            if resolved not in seen:
                seen.add(resolved)
                run_dirs.append(child)
            continue
        for grandchild in child.iterdir():
            if not grandchild.is_dir() or grandchild.name in EXCLUDED_RUN_NAMES:
                continue
            if is_run_artifact_dir(grandchild):
                resolved = grandchild.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    run_dirs.append(grandchild)
    return run_dirs


def load_config_bits(run_dir: Path) -> tuple[str, str]:
    config = read_json(run_dir / "config_snapshot.json") or {}
    actor = ((config.get("actor") or {}).get("model")) or "?"
    critic = ((config.get("critic") or {}).get("model")) or "?"
    router = ((config.get("router") or {}).get("model")) or "?"
    executor = ((config.get("executor") or {}).get("model")) or "?"
    planner = ((config.get("planner") or {}).get("model")) or ""
    parameter_worker = ((config.get("parameter_worker") or {}).get("model")) or ""
    runtime = config.get("runtime") or {}
    model_parts = [f"a={actor}", f"c={critic}", f"r={router}", f"e={executor}"]
    if planner:
        model_parts.append(f"p={planner}")
    if parameter_worker:
        model_parts.append(f"pw={parameter_worker}")
    model_bits = "; ".join(model_parts)
    runtime_parts = [
        f"iter={runtime.get('max_iterations_per_task', '?')}",
        f"exec={runtime.get('max_executor_steps', '?')}",
        f"actor={runtime.get('max_actor_steps', '?')}",
        f"threshold={runtime.get('skill_match_threshold', '?')}",
    ]
    if runtime.get("task_concurrency") not in (None, "", 1):
        runtime_parts.append(f"conc={runtime.get('task_concurrency')}")
    runtime_bits = "; ".join(runtime_parts)
    return model_bits, runtime_bits


def determine_stage(run_dir: Path) -> str:
    if (run_dir / "evaluation_summary.json").exists():
        return "评估"
    if any(path.is_dir() for path in run_dir.glob("task_*")):
        return "训练"
    return "单题调试"


def extract_final_skill_count(run_dir: Path) -> int | None:
    run_summary = read_json(run_dir / "run_summary.json")
    if isinstance(run_summary, dict):
        final_headers = run_summary.get("final_skill_headers")
        if isinstance(final_headers, list):
            return len(final_headers)

    successful_skill_summary = read_json(run_dir / "successful_skill_summary.json")
    if isinstance(successful_skill_summary, dict):
        skill_count = successful_skill_summary.get("skill_count")
        if isinstance(skill_count, int):
            return skill_count

    successful_skill_library = run_dir / "successful_skill_library"
    if successful_skill_library.exists():
        return len([path for path in successful_skill_library.iterdir() if path.is_dir()])

    task_summaries = sorted(run_dir.glob("task_*/task_summary.json"))
    if task_summaries:
        last_summary = read_json(task_summaries[-1]) or {}
        final_headers = last_summary.get("final_skill_headers")
        if isinstance(final_headers, list):
            return len(final_headers)
    return None


def extract_selected_task_count(run_dir: Path) -> int | None:
    selected_tasks = read_json(run_dir / "selected_tasks.json")
    if isinstance(selected_tasks, list):
        return len(selected_tasks)
    return None


def build_train_task_row(run_dir: Path, task_dir: Path, config_bits: str) -> dict:
    summary = read_json(task_dir / "task_summary.json")
    if not isinstance(summary, dict):
        iteration_dirs = sorted(path for path in task_dir.glob("iteration_*") if path.is_dir())
        return {
            "time": format_run_timestamp(run_dir),
            "run_dir_name": run_dir.name,
            "run_name": get_run_display_name(run_dir),
            "task_label": task_dir.name,
            "question_id": "",
            "stage": "训练",
            "status": "未结束/缺摘要",
            "config": config_bits,
            "rounds": str(len(iteration_dirs)),
            "result": "暂无 task_summary.json",
            "note": "该 task 目录缺少 task_summary.json，可能仍在运行或中途中断。",
        }

    iterations = summary.get("iterations") or []
    final_iteration = iterations[-1] if iterations else {}
    reward = final_iteration.get("reward") or {}
    evaluation = final_iteration.get("evaluation") or {}
    actor_decision = final_iteration.get("actor_decision") or {}
    success = bool(summary.get("task_success"))
    error = final_iteration.get("error") or ""

    if error:
        result = sanitize(error, 90)
    elif success:
        accuracy = evaluation.get("accuracy")
        result = f"成功; accuracy={accuracy}" if accuracy is not None else "成功"
    else:
        result = "未通过"

    note = (
        reward.get("experience_note")
        or reward.get("summary")
        or actor_decision.get("summary")
        or evaluation.get("notes")
        or error
        or "无额外摘要"
    )

    return {
        "time": format_run_timestamp(run_dir),
        "run_dir_name": run_dir.name,
        "run_name": get_run_display_name(run_dir),
        "task_label": task_dir.name,
        "question_id": str(summary.get("original_question_id", "")),
        "stage": "训练",
        "status": "成功" if success else "失败",
        "config": config_bits,
        "rounds": str(len(iterations)),
        "result": sanitize(result, 90),
        "note": sanitize(note),
    }


def build_eval_task_row(run_dir: Path, task_dir: Path, config_bits: str) -> dict:
    summary = read_json(task_dir / "evaluation_summary.json")
    if not isinstance(summary, dict):
        return {
            "time": format_run_timestamp(run_dir),
            "run_dir_name": run_dir.name,
            "run_name": get_run_display_name(run_dir),
            "task_label": task_dir.name,
            "question_id": "",
            "stage": "评估",
            "status": "缺摘要",
            "config": config_bits,
            "rounds": "1",
            "result": "暂无 evaluation_summary.json",
            "note": "该 task 目录缺少 evaluation_summary.json。",
        }

    metrics = summary.get("metrics") or {}
    success = bool(metrics.get("task_success"))
    result_bits: list[str] = []
    if "accuracy" in metrics:
        result_bits.append(f"accuracy={metrics.get('accuracy')}")
    if summary.get("final_choice_label"):
        result_bits.append(f"choice={summary.get('final_choice_label')}")
    result = "; ".join(result_bits) or ("成功" if success else "失败")
    note = metrics.get("notes") or summary.get("error") or "无额外摘要"

    return {
        "time": format_run_timestamp(run_dir),
        "run_dir_name": run_dir.name,
        "run_name": get_run_display_name(run_dir),
        "task_label": task_dir.name,
        "question_id": str(summary.get("original_question_id", "")),
        "stage": "评估",
        "status": "成功" if success else "失败",
        "config": config_bits,
        "rounds": "1",
        "result": sanitize(result, 90),
        "note": sanitize(note),
    }


def format_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def collect_rows(runs_root: Path) -> tuple[list[dict], list[dict]]:
    run_rows: list[dict] = []
    task_rows: list[dict] = []

    run_dirs = iter_run_artifact_dirs(runs_root)
    run_dirs.sort(key=lambda item: (parse_run_timestamp(item), item.name))

    for run_dir in run_dirs:
        model_bits, runtime_bits = load_config_bits(run_dir)
        config_bits = f"{model_bits}; {runtime_bits}"
        stage = determine_stage(run_dir)
        task_dirs = sorted(path for path in run_dir.glob("task_*") if path.is_dir())
        selected_task_count = extract_selected_task_count(run_dir)
        finished = 0
        success_count = 0

        if stage == "评估":
            for task_dir in task_dirs:
                row = build_eval_task_row(run_dir, task_dir, config_bits)
                task_rows.append(row)
                finished += 1
                if row["status"] == "成功":
                    success_count += 1
        else:
            if task_dirs:
                for task_dir in task_dirs:
                    row = build_train_task_row(run_dir, task_dir, config_bits)
                    task_rows.append(row)
                    if row["status"] != "未结束/缺摘要":
                        finished += 1
                    if row["status"] == "成功":
                        success_count += 1
            elif (run_dir / "task_summary.json").exists():
                row = build_train_task_row(run_dir, run_dir, config_bits)
                task_rows.append(row)
                finished = 1 if row["status"] != "未结束/缺摘要" else 0
                success_count = 1 if row["status"] == "成功" else 0

        final_skill_count = extract_final_skill_count(run_dir)
        display_task_count = selected_task_count if selected_task_count is not None else len(task_dirs)
        note_bits = [f"已完成={finished}", f"成功={success_count}"]
        if selected_task_count is not None and selected_task_count != len(task_dirs):
            note_bits.insert(0, f"已启动目录={len(task_dirs)}")
            note_bits.insert(0, f"已选任务={selected_task_count}")
        else:
            note_bits.insert(0, f"任务目录={len(task_dirs)}")
        if final_skill_count is not None:
            note_bits.append(f"最终skill数={final_skill_count}")

        run_rows.append(
            {
                "time": format_run_timestamp(run_dir),
                "run_dir_name": run_dir.name,
                "run_name": get_run_display_name(run_dir),
                "stage": stage,
                "task_count": str(display_task_count),
                "finished": str(finished),
                "success": str(success_count),
                "config": sanitize(config_bits, 180),
                "note": "; ".join(note_bits),
            }
        )

    task_rows.sort(key=lambda item: (item["time"], item["run_dir_name"], item["task_label"]))
    return run_rows, task_rows


def build_markdown(runs_root: Path) -> str:
    run_rows, task_rows = collect_rows(runs_root)

    run_table = format_table(
        ["时间", "run 名称", "run 目录名", "阶段", "任务数", "已完成", "成功", "关键配置", "备注"],
        [
            [
                row["time"],
                row["run_name"],
                row["run_dir_name"],
                row["stage"],
                row["task_count"],
                row["finished"],
                row["success"],
                row["config"],
                row["note"],
            ]
            for row in run_rows
        ],
    )

    task_table = format_table(
        ["时间", "run 名称", "run 目录名", "task 目录", "题号", "阶段", "状态", "关键配置", "轮数", "结果", "现象 / 分析"],
        [
            [
                row["time"],
                row["run_name"],
                row["run_dir_name"],
                row["task_label"],
                row["question_id"],
                row["stage"],
                row["status"],
                row["config"],
                row["rounds"],
                row["result"],
                row["note"],
            ]
            for row in task_rows
        ],
    )

    return "\n".join(
        [
            "# 实验总表",
            "",
            "这份表由脚本自动从 `project_skills/runs/` 下的 JSON 产物生成。",
            "",
            "- 排序规则：严格按 run 的分钟级时间排序",
            "- 命名规则：`run 目录名 = YYYYMMDD_HHMM_特征名`",
            "- 生成范围：默认跳过 `_isolated`、`_launch_logs`、`temp`",
            "- 说明：如果某个 task 缺少 `task_summary.json` 或 `evaluation_summary.json`，一般表示 run 仍在进行中或曾经中断",
            "",
            "## run 级总览",
            "",
            run_table,
            "",
            "## task 级逐条记录",
            "",
            task_table,
            "",
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a markdown experiment table from run artifacts.")
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[2]),
        help="Repository root. Defaults to the current project root.",
    )
    parser.add_argument(
        "--runs-root",
        default="project_skills/runs",
        help="Run root relative to repo root.",
    )
    parser.add_argument(
        "--output",
        default="实验记录/实验总表.md",
        help="Output markdown path relative to repo root.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    runs_root = (repo_root / args.runs_root).resolve()
    output_path = (repo_root / args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_markdown(runs_root), encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
