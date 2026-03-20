# NL-RL 技能训练框架

这个项目实现了一个基于自然语言强化学习的 Agent Skill 训练框架，用 benchmark 任务驱动智能体持续构建、修正和筛选 `skill_library/` 中的技能。

当前仓库已经适配本工作区里的 EO 任务场景，核心能力包括：

- `actor`：根据环境反馈决定创建、合并或修改技能
- `critic`：对当前执行结果给出自然语言奖励和结构化指导
- `router`：根据任务与技能头信息匹配最合适的技能
- `executor`：读取技能定义并实际执行工具调用
- `NL-Experience Buffer`：把经验以 JSONL 的形式持续沉淀

## 已实现内容

### 框架能力

- `actor`、`critic`、`router`、`executor` 四个角色使用独立的 LLM 配置
- 所有 prompt 外置在 `prompts/` 目录，便于单独调优
- 基于 `SKILL.md` 的技能发现、解析与路由
- 支持技能的创建、合并、修改
- 经验缓冲区持久化到 `runtime_state/experience_buffer.jsonl`
- 直接桥接 `agent/tools/*.py` 中的 EO 工具
- 将 Earth-Bench 风格评测逻辑重写并接入当前框架
- 每次运行都生成结构化日志，包含请求响应、阶段产物和迭代快照

### 数据层

- 统一了训练数据格式，兼容 `A`、`B`、`C` 三类 source type
- 提供当前 EO `benchmark/question.json` 到训练格式的转换逻辑
- 转换后的数据默认写入 `data/converted/earth_bench_skill_rl/question.json（这个应该是全部合在一起了）`

### 当前技能库

当前仓库里已经包含这些技能：

- `skill_library/ndvi-lst-tvdi-annual-trend/`
- `skill_library/ndvi-lst-tvdi-spike-count/`
- `skill_library/ndvi-lst-tvdi-single-date-threshold-exceedance/`
- `skill_library/ndvi-lst-tvdi-multidate-area-exceedance-count/`

## 目录结构

```text
configs/
  system.json
  system.local.json

docs/
  agent_skill_definition.md
  onboarding_guide_zh.md
  training_data_format.md

nlrl_skills/
  actor.py
  agent_loop.py
  cli.py
  config.py
  critic.py
  data.py
  environment.py
  evaluation.py
  evaluator_runner.py
  llm.py
  prompting.py
  router.py
  schemas.py
  skills.py
  tools.py
  trainer.py
  utils.py

prompts/
  actor_action_selection.md
  actor_create_skill.md
  actor_merge_skill.md
  actor_modify_skill.md
  actor_system.md
  critic_system.md
  critic_user.md
  executor_system.md
  executor_user.md
  router_system.md
  router_user.md
  tool_agent_protocol.md

skill_library/
  ndvi-lst-tvdi-annual-trend/
  ndvi-lst-tvdi-spike-count/
  ndvi-lst-tvdi-single-date-threshold-exceedance/
  ndvi-lst-tvdi-multidate-area-exceedance-count/

runtime_state/
  experience_buffer.jsonl

runs/
  ...
```

## 运行前准备

### 1. 安装依赖

最小依赖见 `requirements.txt`：

- `openai`
- `PyYAML`

安装方式：

```powershell
pip install -r requirements.txt
```

如果你已经在 `earth-bench-skill-eval` 这类现成环境里运行，也可以继续沿用原环境。EO 工具侧通常还依赖：

- `fastmcp`
- `rasterio`
- `numpy`
- `scipy`

### 1.1 启动方式坑：一定从外层仓库根目录启动

这个项目当前有一层容易踩的目录/导入陷阱：

- 外层仓库根目录：`D:\skills-evo\project_skills`
- Python 包目录：`D:\skills-evo\project_skills\project_skills`

仓库里还带了一个本地兼容 shim：

- `project_skills/osgeo/gdal.py`

如果你在内层目录 `D:\skills-evo\project_skills\project_skills` 里直接运行：

```powershell
python -m nlrl_skills.cli ...
```

Python 会优先导入本地这个假 `osgeo` 包，而不是 conda 环境里的真 GDAL。结果就是 `calculate_tif_average` 这类 GDAL 工具会直接报：

```text
GDAL runtime is not available in this environment. A GDAL-dependent tool was invoked.
```

这不是 `system.local.json` 配错，也不是 `project_skills/agent/tools/Statistics.py` 的修复被回退；根因是 Python 导入优先级变了，先吃到了仓库里的假 `osgeo`。

正确做法是：

- 当前工作目录放在外层根目录：`D:\skills-evo\project_skills`
- 用模块入口 `project_skills.nlrl_skills.cli`
- 配置路径也写成外层根目录下可解析的路径

推荐命令模板：

```powershell
conda run -n earth-bench-skill-eval python -m project_skills.nlrl_skills.cli --config "project_skills/configs/system.local.json" <command> [args]
```

最小自检方法：

```powershell
# 正确：外层目录，会导入 conda 环境里的真 osgeo
cd D:\skills-evo\project_skills
E:\miniconda3\envs\earth-bench-skill-eval\python.exe -c "import osgeo; print(osgeo.__file__)"

# 错误：内层目录，会导入仓库自带的假 osgeo
cd D:\skills-evo\project_skills\project_skills
E:\miniconda3\envs\earth-bench-skill-eval\python.exe -c "import osgeo; print(osgeo.__file__)"
```

2026-03-18 的 q1 调试已经验证过：

- 外层目录 + `project_skills.nlrl_skills.cli` 能绕开假 `osgeo` 抢导入
- 屏幕上若只看到 `Cannot find gdalvrt.xsd (GDAL_DATA is not defined)`，这通常只是 GDAL warning，不是之前那个致命导入错误

2026-03-20 再次复核的导入结果是：

- 外层目录：`E:\miniconda3\envs\earth-bench-skill-eval\Lib\site-packages\osgeo\__init__.py`
- 内层目录：`D:\skills-evo\project_skills\project_skills\osgeo\__init__.py`

因此，后续任何 AI 或协作者如果再次看到这条致命 GDAL 报错，第一反应应该是检查“当前命令是不是在外层目录、是不是走 `project_skills.nlrl_skills.cli`”，而不是先回滚代码或修改配置。

### 2. 选择配置文件

CLI 的全局入口参数是 `--config`，必须显式传入一个配置文件。

仓库里常见有两个配置：

- `configs/system.json`：通用配置模板
- `configs/system.local.json`：当前这台机器的本地路径配置

在这个仓库里，更建议优先使用 `configs/system.local.json`，因为它的路径已经指向当前工作目录下的 `project_skills/`。

## 配置说明

配置文件主要分为三部分：

- LLM 配置：`actor`、`critic`、`router`、`executor`
- 路径配置：`workspace_root`、`run_root`、`skill_library_root` 等
- 运行时配置：最大迭代轮数、最大执行步数、路由阈值等

### LLM 角色

- `actor`：决定是否创建、合并、修改技能
- `critic`：根据执行结果生成奖励和改进建议
- `router`：对已有技能打分并选择最匹配的技能
- `executor`：真正执行技能内容和工具调用

### `max_tokens` 规则

- `actor` 和 `critic` 不主动发送 `max_tokens`
- `router` 只有在配置文件里显式设置 `max_tokens` 才会发送
- `executor` 如果未显式设置，会默认使用 `32768`

### 重试策略

每次 LLM 调用在遇到暂时性请求失败时最多重试 5 次，重试间隔 6 秒。常见的 `400`、`429`、`500`、`502` 等错误都会进入这套重试逻辑。

## 框架工作流

一次完整训练迭代大致如下：

1. `router` 对当前所有技能头信息分别打分。
2. 如果没有技能超过阈值，当前轮直接进入无技能状态。
3. 如果选中了技能，`executor` 会读取该技能目录下的 `SKILL.md`，并可调用其附带脚本和资源。
4. `critic` 根据执行结果给出自然语言奖励和结构化建议。
5. `actor` 选择一个一层动作：`create_skill`、`merge_skills`、`modify_skill`。
6. `actor` 把结果写入 `skill_library/`。
7. 经验摘要被追加写入 `runtime_state/experience_buffer.jsonl`。

## 评测指标

EO 评测逻辑已经重写到 `nlrl_skills/evaluation.py`，当前实现了这些指标：

- `accuracy`
- `efficiency`
- `tool_any_order`
- `tool_in_order`
- `tool_exact_match`
- `parameter_accuracy`

EO 工具本体仍然来自：

- `agent/tools/*.py`

## CLI 使用说明

统一入口：

下面所有命令都默认在外层仓库根目录 `D:\skills-evo\project_skills` 执行。不要在内层包目录 `D:\skills-evo\project_skills\project_skills` 中运行 `python -m nlrl_skills.cli`，否则会导入假 `osgeo` 并触发上面的致命 GDAL runtime 报错。

```powershell
python -m project_skills.nlrl_skills.cli --config "project_skills/configs/system.local.json" <command> [args]
```

如果你习惯用 conda 环境，也可以这样调用：

```powershell
conda run -n earth-bench-skill-eval python -m project_skills.nlrl_skills.cli --config "project_skills/configs/system.local.json" <command> [args]
```

### 全局参数

| 参数         | 是否必填 | 作用                                                               |
| ------------ | -------- | ------------------------------------------------------------------ |
| `--config` | 是       | 配置文件路径。决定模型配置、数据路径、运行日志目录、技能库位置等。 |

### 1. 转换数据集：`convert-earth-bench`

把 Earth-Bench 原始 `question.json` 转成当前框架可训练的数据格式。

```powershell
python -m project_skills.nlrl_skills.cli --config "project_skills/configs/system.local.json" convert-earth-bench --src "project_skills/benchmark/question.json" --dst "project_skills/data/converted/earth_bench_skill_rl/question.json"
```

参数说明：

| 参数      | 是否必填 | 作用                                                 |
| --------- | -------- | ---------------------------------------------------- |
| `--src` | 是       | 原始 Earth-Bench `question.json` 路径。            |
| `--dst` | 是       | 转换后输出的标准化数据集路径。程序会自动创建父目录。 |

执行结果：

- 命令结束后会在终端打印生成的目标文件路径。
- 产物是一个包含 `tasks` 列表的标准化 JSON 文件。

### 2. 查看技能头：`inspect-skills`

读取当前 `skill_library/` 中所有技能，并输出技能头信息。

```powershell
python -m project_skills.nlrl_skills.cli --config "project_skills/configs/system.local.json" inspect-skills
```

如果想把结果保存成 JSON 文件：

```powershell
python -m project_skills.nlrl_skills.cli --config "project_skills/configs/system.local.json" inspect-skills --output "project_skills/runs/skill_headers_snapshot.json"
```

参数说明：

| 参数         | 是否必填 | 作用                                                         |
| ------------ | -------- | ------------------------------------------------------------ |
| `--output` | 否       | 可选输出文件路径。传了就写 JSON 文件；不传则直接打印到终端。 |

### 3. 单任务调试：`debug-single-task`

对一个任务完整跑一遍路由、执行、评估、技能更新流程，适合排查技能行为和 prompt 问题。

```powershell
python -m project_skills.nlrl_skills.cli --config "project_skills/configs/system.local.json" debug-single-task --task-id 1 --run-name "debug_q1" --reset-skill-library
```

参数说明：

| 参数                          | 是否必填 | 作用                                                                                               |
| ----------------------------- | -------- | -------------------------------------------------------------------------------------------------- |
| `--task-id`                 | 否       | 任务标识。既可以传标准化后的 `task_id`，也可以传原始题号；如果不传，默认取数据集中的第一个任务。 |
| `--run-name`                | 否       | 运行目录名。传了就写到 `runs/<run-name>/`；不传则自动生成时间戳目录。                            |
| `--reset-skill-library`     | 否       | 运行前清空当前生成型技能库，再从空技能库开始调试。                                                 |
| `--reset-experience-buffer` | 否       | 运行前清空 `runtime_state/experience_buffer.jsonl`。                                             |

执行结果：

- 命令结束后会打印本次 run 目录路径。
- 单任务调试会直接在该目录下写入 `task.json`、`task_summary.json`、`run_summary.json` 和每轮迭代日志。

### 4. 多任务训练：`train-tasks`

按给定任务集合连续训练，允许技能在任务之间累积演化。

```powershell
python -m project_skills.nlrl_skills.cli --config "project_skills/configs/system.local.json" train-tasks --count 5 --start-index 0 --run-name "train_first5_k10" --reset-skill-library --reset-experience-buffer
```

也可以按明确题号训练：

```powershell
python -m project_skills.nlrl_skills.cli --config "project_skills/configs/system.local.json" train-tasks --task-ids 1 2 3 4 5 --run-name "train_selected"
```

参数说明：

| 参数                          | 是否必填 | 作用                                                                                            |
| ----------------------------- | -------- | ----------------------------------------------------------------------------------------------- |
| `--task-ids`                | 否       | 指定要训练的任务列表，可传标准化 `task_id` 或原始题号。传了这个参数后，会直接按这组任务运行。 |
| `--count`                   | 否       | 从切片结果里取前 N 个任务。常与 `--start-index` 搭配使用。                                    |
| `--start-index`             | 否       | 数据集起始偏移量，默认 `0`。表示从第几个任务开始截取。                                        |
| `--run-name`                | 否       | 运行目录名。                                                                                    |
| `--reset-skill-library`     | 否       | 训练开始前清空技能库。                                                                          |
| `--reset-experience-buffer` | 否       | 训练开始前清空经验缓冲区。                                                                      |

参数优先级：

- 如果传了 `--task-ids`，程序会直接按这些任务训练，`--count` 和 `--start-index` 不再参与筛选。
- 如果没传 `--task-ids`，程序会先从 `--start-index` 开始截取数据集，再应用 `--count`。

执行结果：

- 训练 run 目录下会生成 `selected_tasks.json`，记录这次选中的任务集合。
- 每个任务会生成独立子目录，例如 `task_01_1/`、`task_02_2/`。
- 最终会产出 `run_summary.json` 汇总所有任务结果和最终技能头信息。

### 5. 仅评估当前技能库：`evaluate-tasks`

对当前技能库做推理评估，不再执行技能创建、合并、修改，因此适合在训练后做单独验证。

```powershell
python -m project_skills.nlrl_skills.cli --config "project_skills/configs/system.local.json" evaluate-tasks --count 5 --start-index 0 --run-name "eval_first5_after_training"
```

也可以只评估指定题目：

```powershell
python -m project_skills.nlrl_skills.cli --config "project_skills/configs/system.local.json" evaluate-tasks --task-ids 1 2 3
```

参数说明：

| 参数              | 是否必填 | 作用                                                  |
| ----------------- | -------- | ----------------------------------------------------- |
| `--task-ids`    | 否       | 指定评估的任务列表。                                  |
| `--count`       | 否       | 从切片结果里取前 N 个任务。                           |
| `--start-index` | 否       | 数据集起始偏移量，默认 `0`。                        |
| `--run-name`    | 否       | 评估结果目录名；不传则自动生成 `eval_<timestamp>`。 |

参数优先级：

- 如果传了 `--task-ids`，`--count` 和 `--start-index` 会被忽略。
- 如果没传 `--task-ids`，就按 `start-index -> count` 的顺序选择任务。

执行结果：

- 每个任务目录下会生成 `evaluation_summary.json`。
- 如果评估阶段报错，会额外生成 `evaluation_failure.json`。
- 根目录会生成 `evaluation_summary.json`，其中包含平均指标、成功数和逐任务结果。

## 运行日志说明

每次运行都会在 `runs/` 下创建一个独立目录。

常见公共文件：

- `config_snapshot.json`：本次运行时的配置快照
- `task.json`：任务内容
- `run_summary.json`：训练 run 的总汇总
- `selected_tasks.json`：多任务训练或评估时选中的任务清单
- `evaluation_summary.json`：评估 run 的汇总

训练迭代目录中常见文件：

- `skill_headers_before.json`
- `skill_headers_after.json`
- `iteration_summary.json`
- `iteration_failure.json`

组件级日志：

- `env/state.json`
- `critic/reward.json`
- `actor/actor_decision.json`
- 各个 LLM 请求/响应的 JSON 记录

执行器还会额外保存每一步工具调用的请求和响应。

## Prompt 调优位置

所有 prompt 都是普通 Markdown 文件，位于 `prompts/`。

最常改的通常是：

- `prompts/router_system.md`
- `prompts/executor_system.md`
- `prompts/critic_system.md`
- `prompts/actor_create_skill.md`
- `prompts/actor_modify_skill.md`

## 当前状态

目前已经实现并打通过这些能力：

- 框架主流程
- 数据转换
- prompt 外置化
- 结构化日志
- 技能创建与修订
- EO 评测重写
- 技能相对路径脚本解析

当前已知问题：

- `Qwen/Qwen3-8B` 在长 EO 轨迹上仍然容易触发 provider 的 TPM 限流
- 某些训练出的技能在 batch 参数格式上还需要继续收紧

## 建议的下一步

可以基于当前日志结果继续迭代：

- 收紧批量 EO 工具的调用模板
- 给 executor 增加更多 list 参数示例
- 继续压缩 router 和 executor prompt，减少长文件列表导致的 TPM 峰值
