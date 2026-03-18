# Project Skills Onboarding Guide

这份文档面向第一次接手 `project_skills` 的人。目标不是一次讲全，而是帮你在最短时间内回答 4 个问题：

1. 这个项目到底在做什么？
2. 代码主干在哪，先读哪里？
3. 现在不下载 benchmark，也能先做哪些检查？
4. benchmark 到位后，怎么把项目跑起来？

## 1. 先建立一张脑图

这个仓库里其实有两套东西：

- `nlrl_skills/`
  - 这是当前要关注的主项目。
  - 它实现了一个自然语言 RL 框架，让 agent 在做 benchmark 题目时不断创建、修改、合并 `skill_library/` 里的 skills。
- `agent/skill_eval/`
  - 这是较早的一套 Earth-Bench skill-aware 评测/执行管线。
  - 现在不是主训练入口，但仍然很重要，因为底层 EO 工具还在复用 `agent/tools/*.py`。

如果你是第一次接手，建议把注意力放在 `nlrl_skills/`，把 `agent/skill_eval/` 视为“旧评测实现和工具背景资料”。

## 2. 这个项目的核心目标

一句话概括：

> 用 benchmark 任务和 gold trajectory 驱动一个 actor-critic 式循环，让系统自动生成并优化一套可复用的 skills 库。

它的闭环是：

1. 从数据集取一个任务。
2. 扫描当前 `skill_library/`，拿到所有 skill header。
3. `router` 判断哪个 skill 最适合这道题。
4. `executor` 激活该 skill，并调用工具执行。
5. `evaluation` 把执行结果和 gold answer / gold tool trajectory 对比打分。
6. `critic` 产出自然语言 reward 和修改建议。
7. `actor` 决定是 `create_skill`、`modify_skill` 还是 `merge_skills`。
8. 把新经验写入 `runtime_state/experience_buffer.jsonl`，进入下一轮。

你可以把它理解为：

- `skill_library/` 是策略参数的“外显载体”
- `runs/` 是训练过程的完整轨迹
- `experience_buffer.jsonl` 是跨任务累计的失败经验摘要

## 3. 目录怎么读

先只记住这些目录：

```text
project_skills/
  configs/          运行配置，尤其是路径和模型配置
  docs/             现有说明文档
  nlrl_skills/      新 RL 框架主干
  prompts/          router / executor / critic / actor 的提示词
  skill_library/    当前 skill 库
  runtime_state/    experience buffer
  runs/             历史运行结果和调试痕迹
  agent/tools/      EO 工具函数
  agent/skill_eval/ 旧版评测/执行管线
  data/converted/   已转换好的训练数据
```

对第一次接手的人，最重要的是：

- `nlrl_skills/` 决定“系统怎么跑”
- `skill_library/` 决定“系统学到了什么”
- `runs/` 决定“你怎么排查问题”

## 4. 推荐阅读顺序

按下面顺序读，效率最高。

### 第 1 轮：先看入口和配置

1. `README.md`
   - 先拿到全局目标和已有命令。
2. `configs/system.json`
   - 看模型角色、路径配置、运行参数。
3. `nlrl_skills/cli.py`
   - 看有哪些官方入口命令。

读完这 3 个文件，你应该能回答：

- 项目要训练什么
- 入口命令是什么
- 运行依赖哪些目录

### 第 2 轮：看主循环

4. `nlrl_skills/trainer.py`
   - 训练主循环，负责按 iteration 推进一个 task。
5. `nlrl_skills/environment.py`
   - 把 router、executor、evaluation 串起来。
6. `nlrl_skills/router.py`
   - skill 选择。
7. `nlrl_skills/critic.py`
   - 根据执行结果给 reward。
8. `nlrl_skills/actor.py`
   - 根据 reward 改 skill 库。

读完这 5 个文件，你就抓住主干了。

### 第 3 轮：看数据、skill、工具

9. `nlrl_skills/data.py`
   - benchmark 原始数据是怎么转换成统一训练格式的。
10. `nlrl_skills/skills.py`

- `SKILL.md` 如何被发现、解析、写回。

11. `nlrl_skills/tools.py`

- executor 能调用哪些工具，skill 里的脚本路径是怎么解析的。

12. `agent/tools/*.py`

- 真正的 EO tool 实现。

### 第 4 轮：看一个真实 skill 和一个真实 run

13. 随便挑一个 `skill_library/*/SKILL.md`

- 推荐先看 `skill_library/ndvi-lst-tvdi-spike-count/SKILL.md`

14. 看一个历史运行目录

- 推荐先看：
- `runs/debug_q1/`
- `runs/smoke_eval_q1/`
- `runs/train_first5_k10_v3_continue/`

这一步最能帮你把“代码结构”和“实际行为”对上。

## 5. 先理解 skill 在这个项目里是什么

这里的 skill 不是一段 prompt，而是一个目录包，至少包含一个 `SKILL.md`。

典型结构：

```text
skill_name/
  SKILL.md
  scripts/
  references/
```

这个项目对 skill 的使用方式是：

- router 只看 skill header
- executor 只有在 skill 被选中后才加载完整 `SKILL.md`
- skill 可以引用自己的 `scripts/` 和 `references/`
- actor 最终通过写文件的方式更新 skill 包

所以你接手这个项目时，不能只盯 prompt；必须同时看：

- prompt 怎么驱动模型
- skill 怎么被发现
- skill 怎么被执行
- skill 怎么被 actor 写回磁盘

## 6. 现在这个仓库的实际状态

基于当前仓库内容，可以先确认这些事实：

- 已有转换后的数据集：`data/converted/earth_bench_skill_rl/question.json`
- 当前转换后数据集任务数是 `248`
- 当前 checkout 里没有 `benchmark/` 目录
- `skill_library/` 已经不是空库，里面有 4 个现成 skill
- `runs/` 下已经有多次调试、训练、评测的历史产物

这意味着：

- 你现在可以先读代码、读 skill、读历史运行结果
- 你也可以做不依赖 benchmark 原始数据的轻量检查
- 但你暂时不适合直接跑完整 EO benchmark 执行链路

## 7. 第一个坑：`configs/system.json` 现在不能直接照跑

这是最重要的接手提醒。

当前 `configs/system.json` 里的 `paths.*` 指向的是另一台机器上的绝对路径，不是当前仓库路径。所以你如果直接照着 `README.md` 跑，大概率会因为路径不对而失败。

第一次本地接手时，建议这样做：

1. 复制一份配置，例如新建 `configs/system.local.json`
2. 只改 `paths` 段，先把这些路径改成你当前仓库的绝对路径：
   - `workspace_root`
   - `prompt_root`
   - `run_root`
   - `skill_library_root`
   - `experience_buffer_path`
   - `dataset_path`
   - `converted_dataset_path`
   - `docs_root`
3. 再检查模型接口配置是否仍然可用：
   - `base_url`
   - `api_key`
   - `model`

如果你暂时只想先熟悉项目，不一定要立刻改模型配置；但想真正运行 CLI，就必须先修路径。

## 8. 不下载 benchmark 时，先做这 3 件事

这是我建议的最小上手动作。

### 任务 A：确认依赖和 Python 入口没问题

最小依赖在 `requirements.txt`，当前仓库至少显式写了：

- `openai`
- `PyYAML`

但真实 EO 运行通常还依赖原 Earth-Bench 环境里的包，比如：

- `fastmcp`
- `rasterio`
- `numpy`
- `scipy`

如果只是先做轻量检查，可以先用当前 Python 环境确认 `openai`、`yaml` 能导入。

### 任务 B：先看当前 skill 库

把配置路径修好后，先跑：

```powershell
python -m nlrl_skills.cli --config configs/system.local.json inspect-skills
```

这是最安全的入口之一，不依赖 benchmark 数据本体，也不会触发真正的 EO 执行。

### 任务 C：先读历史运行目录

建议先打开这些文件：

- `runs/debug_q1/run_summary.json`
- `runs/debug_q1/iteration_*/iteration_summary.json`
- `runs/*/task_summary.json`
- `runs/*/env/state.json`
- `runs/*/critic/reward.json`
- `runs/*/actor/actor_decision.json`

你会很快看懂：

- 某轮为什么失败
- critic 怎么描述失败
- actor 怎么把失败转成 skill 修改

这比只读代码更快。

## 9. benchmark 到位之后，怎么跑

等 benchmark 下载好，并且 `configs/system.local.json` 的路径已经改对，再按这个顺序跑。

### 第一步：如果需要，重新转换数据

```powershell
python -m nlrl_skills.cli --config configs/system.local.json convert-earth-bench --src benchmark/question.json --dst data/converted/earth_bench_skill_rl/question.json
```

如果你已经确认仓库里的 `data/converted/earth_bench_skill_rl/question.json` 可用，这一步可以跳过。

### 第二步：先跑单题 debug

```powershell
python -m nlrl_skills.cli --config configs/system.local.json debug-single-task --task-id 1 --run-name debug_q1_local
```

如果你想从空 skill 库开始复现一轮创建过程，可以加：

```powershell
--reset-skill-library --reset-experience-buffer
```

注意：这两个参数会清空当前 skill 库或经验缓冲，别在你想保留现有结果时乱用。

### 第三步：再跑小批量训练

```powershell
python -m nlrl_skills.cli --config configs/system.local.json train-tasks --count 5 --start-index 0 --run-name train_first5_local
```

### 第四步：训练后单独评测

```powershell
python -m nlrl_skills.cli --config configs/system.local.json evaluate-tasks --count 5 --start-index 0 --run-name eval_first5_local
```

建议不要一上来就跑大批量。先把单题和前 5 题跑通，再考虑扩大规模。

## 10. 跑完之后先看哪里

每次 run 的核心排查顺序建议固定下来：

1. `runs/<run_name>/run_summary.json`
   - 看总体成败。
2. `runs/<run_name>/task.json` 或 `selected_tasks.json`
   - 看实际跑了哪些题。
3. `runs/<run_name>/iteration_*/env/state.json`
   - 看 router 选了谁，executor 做了什么，evaluation 打了多少分。
4. `runs/<run_name>/iteration_*/critic/reward.json`
   - 看 critic 如何解释失败。
5. `runs/<run_name>/iteration_*/actor/actor_decision.json`
   - 看 actor 到底创建/修改了什么 skill。
6. `runs/<run_name>/iteration_*/skill_headers_before.json` 和 `skill_headers_after.json`
   - 看 skill 库是否真的变了。

如果要定位 LLM 行为，再看 request/response trace JSON。

## 11. 为什么还要看 `agent/skill_eval/`

虽然现在主入口在 `nlrl_skills/`，但 `agent/skill_eval/` 仍然值得知道：

- 它保存了更早的 benchmark-aware staged pipeline 思路
- 它能帮助你理解 Earth-Bench 的评测拆分方式
- 它能帮助你分辨“新 RL 框架”和“旧评测脚本”的边界

但第一次接手时不要先扎进去。否则你容易把两套系统混在一起。

简单原则：

- 想理解当前训练闭环，优先看 `nlrl_skills/`
- 想追 Earth-Bench 旧流程或 staged eval，再看 `agent/skill_eval/`

## 12. 我建议你的首日上手路线

如果你只有半天时间，按这个顺序来：

1. 读 `README.md`
2. 读 `configs/system.json`
3. 读 `nlrl_skills/cli.py`
4. 读 `nlrl_skills/trainer.py`
5. 读 `nlrl_skills/environment.py`
6. 读 `nlrl_skills/actor.py` / `critic.py` / `router.py`
7. 读 `nlrl_skills/skills.py` / `tools.py`
8. 读一个样例 `SKILL.md`
9. 读一个历史 run
10. 新建 `configs/system.local.json`
11. 先跑 `inspect-skills`
12. benchmark 到位后再跑 `debug-single-task`

## 13. 接手时最容易混淆的点

- 不要把 `skill_library/` 当作静态资料库。它是训练产物。
- 不要把 `agent/skill_eval/` 当作当前主入口。主入口是 `nlrl_skills/cli.py`。
- 不要直接使用当前 `configs/system.json` 跑本地副本。路径是硬编码的。
- 不要在 benchmark 缺失时直接验证 EO 执行效果。那会把“环境问题”和“策略问题”混在一起。
- 不要只读 prompt 不读 `runs/`。这个项目的很多真实行为，必须从运行产物里理解。

## 14. 一句话总结

第一次接手时，你可以把这个项目看成：

> 一个以 Earth-Bench 任务为监督信号、以 `skill_library/` 为外显策略载体、通过 `router -> executor -> critic -> actor` 闭环不断自我改写 skills 的训练系统。

先把这条主线抓住，后面的 prompt、工具、skill 细节都会自然落位。
