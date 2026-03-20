# TODO

## 高优先级待办

### 1. 当前主线

- [ ] 先解决 `Qwen/Qwen3-8B` 在当前框架里的 PTM/TPM/通道稳定性问题，让小模型至少能稳定跑通训练与测试

  - 当前优先级最高的不是 skill 本身，而是先让小模型在现有 API、上下文长度和速率限制下稳定工作；否则后续所有 skill 方案对比都会失真。
  - 需要明确区分：到底是模型能力问题，还是 API/TPM/通道/上下文长度问题。

- [ ] 用 `Qwen/Qwen3-8B` 做 executor-only 对照实验，并与 `gpt-5.4 executor`、`earth agent MCP` 做效果对比

  - 保持 `router/actor/critic` 不变，只替换 `executor`，避免把模型能力差异和 skill 学习差异混在一起。
  - 至少要有一版对照：`gpt-5.4 executor` vs `Qwen/Qwen3-8B executor` vs `earth agent MCP`。
  - 需要重点记录：task success、平均工具步数、长上下文稳定性、错误类型分布。
  - 同时把 `Qwen/Qwen3-8B` 的 API 稳定性 / TPM 问题当成单独高优先级风险：确认真实长跑里是否频繁出现通道不可用、TPM 打满、请求被限流、长提示下吞吐骤降等问题。

- [ ] 先用当前框架在 `EarthBench` 上稳定跑前 20 题，确认除了上下文和速率之外是否还有框架级问题

  - 如果前 20 题阶段仍频繁出现协议、上下文、速率、路由或工具层报错，说明还不适合直接上更大规模训练或更复杂的 skill 机制。
  - 只有在这一步基本跑稳以后，再继续做新的 skill 生成/聚合方案，结果才有解释价值。

- [ ] 如果前 20 题不再报上下文或速率问题，就切到“方案二”模式做训练 + 测试，先看分数上限和 skill 复用效果

  - 即：逐题生成未去重 skill 池 -> 框架外去重/聚类/高阶整合 -> 再回灌 skill 机制统一测试。
  - 如果这条主线仍跑不通或分数没有明显提升，再回头调整 skill 架构，而不是继续在当前局部 patch 上消耗时间。

### 2. 实验复盘与行为诊断

- [ ] 复盘 3 组 `20-4` 并行实验，重点看 skill 库数量、复用、失败模式、是否出现“修复式退化”

  - 目标实验：`debug_train_first20_parallel_01_20260319_01`、`debug_train_first20_parallel_02_20260319_01`、`debug_train_first20_parallel_03_20260319_01`
  - 重点记录：
    - skill 库最终数量、每类 skill 的增减变化
    - 每个 task 命中历史 skill 的比例，而不是只看是否创建新 skill
    - 命中历史 skill 后的一次通过率，以及命中后仍需多少次 modify 才能过
    - 是否出现同一个 skill 被反复修改但始终不过的模式
    - 是否出现“修复式退化”：为了修通当前题而 patch 既有 skill 后，原本已稳定的题反而退化
    - experience buffer 的 failure signature 是否高度重复、是否在鼓励局部死循环
  - 成功部分也要显式标记：哪些 skill 被稳定复用、哪些 helper/coverage policy 真正降低了迭代次数、哪些题型已经从“反复补丁”变成“一次命中即可通过”。
  - 最好形成对照表：`实验 -> q1/q2/q3... -> 命中 skill -> 是否复用成功 -> 修改次数 -> 最终 skill 数量`

- [ ] 系统梳理每一步里 `critic` 和 `actor` 的真实操作与决策点，避免只盯 executor 而忽略上游错误归因和下游 skill 修改策略

  - 明确一轮 iteration 里 `critic` 看到了什么输入、产出了哪些字段、这些字段如何驱动 `actor_action_selection` 和后续 `create/modify/merge`。
  - 梳理 `actor` 在各 action 下的输入差异：`create_skill` 基本不检索经验库，`modify_skill` 会调用 `retrieve_similar_experiences(...)`，`merge_skill` 又是另一套 prompt。
  - 形成一版逐步决策图：`router -> executor -> evaluation -> critic -> actor_action_selection -> actor_{create|modify|merge} -> apply -> append_experience`
  - 重点观察 `critic` 是否持续把工具 bug 翻译成 skill 问题、`actor` 是否因此在错误方向上越改越多。

- [ ] 调整当前 skill 的 prompt / 使用方式，减少“端到端大 skill + 工具逐步调用指导”带来的过拟合和局部补丁化

  - 当前 skill prompt 明显偏向“按工具一步一步指导”，容易把 benchmark 专属规则、coverage 解释、MCQ 映射全塞进一个大 skill。
  - 重点判断：
    - 这种写法到底是在提高复用，还是在把 skill 写成单题 patch
    - 是否存在“为了适应当前题，把原本适应之前题目的 skill 又改坏”的情况
  - 这件事要结合三组并行实验一起看，而不是只看单个 q1。

### 3. 数据集与 bench

- [ ] 系统梳理 EarthBench 及其它协作者找来的 bench 的性质，明确任务类型、分布和合适的训练子集

  - 先对当前转换后的数据集做 taxonomy，而不是只按题号顺序看：例如 TVDI trend、single-date threshold ratio、time-series spike count、threshold-conditioned mean、difference/compare、非 TVDI 遥感统计等。
  - 统计每类题数量、各类 gold tool pattern 是否稳定、哪些类之间共享公共 stem。
  - 回答两个直接影响训练设置的问题：
    - 训练集应该放多少题才有代表性，才能让 skill 真正出现复用，而不是只是在连续补单题 patch
    - 哪些题适合作为早期训练集，哪些题应该保留作验证/测试，避免训练阶段全是极端难题或同一类题导致误判 skill 泛化性
  - 最好形成推荐切分：`warmup train subset`、`main train subset`、`held-out eval subset`

- [ ] 对方支线：探索其它 bench，包括 `SWE-bench Verified/Lite`、`GAIA`、`DSBench`、`InnoGym` 等，并预先构建对应的工具系统

  - `GAIA` 这类 bench 可能没有天然训练集，需要自己构造训练数据或任务切分。
  - 这些 bench 进入实验前，首先要确认工具接口是否齐全，否则对比没有意义。

### 4. 方案探索与协作

- [ ] 方案一：把多个任务/失败样本按 batch 一起总结，再统一修改 skill，作为更高视角、更统一的 skill 修改范式

  - 目标是把 skill 修改从“单题 patch”提升到“同类题批量归纳”，减少局部补丁、扩大视野、形成更统一的分类和修改范式。
  - 适合观察：如果多题共享公共 stem，但各自失败细节不同，batch 汇总是否能帮助 actor 产出更统一、更抽象的 skill 修改。

- [ ] 方案二（当前优先）：逐题把 task 丢进框架，先形成一个未去重的 skill 池；训练结束后脱离框架做去重、聚类和高阶整合

  - 这是当前更偏向先尝试的方案，因为它对现有框架改动更小，也更容易先拿到一版“全量生成 -> 后处理聚合”的结果。
  - 目标是先看：在 EarthBench 全任务上生成的 skill 池，经过高维聚合后，能不能比当前端到端单 skill 机制更稳、更泛化。

- [ ] 我方主线：先把 `Qwen/Qwen3-8B` 跑通，并完成 EarthBench 前 20 题稳定性检查，再推进方案二的训练 + 测试

- [ ] 对方支线：复现 EarthBench 在其他 3~4 个框架上的效果，并行探索更多框架实现与对比

  - 目标是别只盯当前框架，后续可以把 skill 机制、工具机制和框架机制区分开看。

- [ ] 有时间的话评估额外基础设施/机器方案（如对方推荐的服务器服务、云主机/轻量服务器）是否需要纳入实验计划，支撑多框架并行测试与工具部署

- [ ] 有时间的话体验一下 `Cursor`（已下载），登录对方账户实际使用一轮，感受其 workflow、代码理解和交互效果，再决定是否值得纳入对比观察

## 中优先级待办

- [ ] 把“单轮只选一个 skill”的执行结构升级成“主流程 skill + helper modules”的模块化匹配，避免把公共 stem 和题型 tail 强行糅进一个大 skill

  - 当前 router 只产出一个 `selected_skill`，executor 也只按这一个 skill 执行；这会天然诱导 actor 把公共前半段与题型特有后半段写进同一个 skill。
  - 优先尝试“主流程 skill + 若干易错点 helper”的轻量组合，而不是直接放开多 skill 并列。
  - 推荐结构：
    - `primary skill` 负责主流程骨架，例如 `get_filelist -> 配对 -> compute_tvdi`
    - `helper modules` 负责高频易错点或局部策略，例如 `coverage-audit`、`pairing-policy`、`annual-trend-tail`、`threshold-ratio-tail`、`spike-count-tail`、`mcq-mapping`
    - q1 可先试：`tvdi-core` + `annual-trend-tail` + `coverage-audit` + `mcq-mapping`
  - router 输出也要从单一 `selected_skill` 升级为：`primary_skill + helper_skills[]`
  - executor 规则需要明确：primary 决定主流程，helper 只补局部，不允许推翻主流程。

- [ ] 给 actor/skill 操作原语增加“降权 / 冻结 / 剔除有害 skill”的能力，避免同一个坏 skill 在同题上反复被命中并进入修改死循环

  - 当前只有 `create_skill / modify_skill / merge_skill` 这类正向原语。
  - 应考虑补充：`disable_skill_for_task`、`quarantine_skill`、`downgrade_skill_priority`、`split_skill`、`revert_skill_to_previous_version`
  - router 侧也应消费这种负反馈：同一任务上若某个 skill 连续 N 次失败且 failure signature 高度重复，应允许临时降权或排除该 skill。

## 后续优化 / Trick

- [ ] 调整训练主流程顺序，避免成功样本仍然先执行 `critic`

  - 当前顺序是 `evaluation -> critic -> success check -> actor(if fail)`
  - 对成功样本来说，`critic` 的诊断日志不会继续驱动 skill 修改，存在额外开销。
  - 可考虑改成 `evaluation -> success check -> critic/actor only if fail`

- [ ] 设计“失败后回退 skill 库”的机制

  - 当前一轮修改后的 skill 会直接进入下一轮，同题继续尝试，但效果可能更差。
  - 可考虑在失败时解析出更明确的失败经验，判断这次修改是否导致退化。
  - 如果检测到退化，可引导 skill 库回退到上一版或最近稳定版本。
  - 同时把失败和回退原因继续追加到 `runtime_state/experience_buffer.jsonl`

- [ ] 继续补齐 `skill -> tool schema -> tool implementation` 的接口契约校验，优先把低级参数传递错误和错误归因压住

  - 目标是让系统更容易区分：到底是 skill 策略错，还是工具契约/实现错。
  - 后续补强点包括：
    - skill 修改后的接口一致性检查
    - 参数类型校验
    - 失败类型分流（skill 错 vs 工具错）

## 已完成（保留记录）

- [x] critic 输入中补上“当前激活 skill 可调用工具”的真实签名/参数 schema，而不只是工具名称和调用轨迹

  - 2026-03-18 已补到 critic 输入，并用 `project_skills/runs/debug_q1_gpt54_critic_tool_specs_v2` 验证：critic 已能明确指出 `compute_tvdi(ndvi_path: str, lst_path: str, output_path: str) -> str` 是单文件签名，不再把这类问题仅仅归因为 skill 文案。

- [x] 统一 EO 工具的相对输入路径解析

  - 2026-03-18 已在 `project_skills/nlrl_skills/tools.py` 的统一 EO 调用入口补上输入路径规范化。
  - 验证结果：`project_skills/runs/debug_q1_gpt54_tool_path_fix/iteration_01/env/executor/executor_steps/20260318T124420Z_executor_step_2_request.json` 已显示 step 1 的 `get_filelist(dir_path="benchmark/data/question1")` 返回 `success: True`。

- [x] 让 executor 只消费首个合法 JSON action，并容忍单次响应里出现多个 JSON / 列表被串成字符串的低级格式噪声

  - 2026-03-18 已在 `project_skills/nlrl_skills/utils.py` 的 `extract_json_object(...)` 中改为基于 `JSONDecoder.raw_decode` 抽取首个顶层 JSON 对象。

- [x] 让统一 EO 调用层对齐 gold 所需的 batched `compute_tvdi` 契约，并阻断“列表被错误串成字符串”或“因误判为标量接口而提前 blocked”的两类低级失败

  - 2026-03-18 已在 `project_skills/nlrl_skills/tools.py` 完成这层修复：EO schema 按真实注解展示；`compute_tvdi` 支持 `string | list[string]`；字符串化列表会先还原为原生 list；输出路径会被规范化。

- [x] 修复 `calculate_tif_average` 对 `NaN` / `nodata` 的错误聚合，消除 q1 年度平均栅格全空的 EO 数值工具链问题

  - 2026-03-19 已在 `project_skills/agent/tools/Statistics.py` 修复：读取时把 `nodata` / `inf` 转成 `NaN`；累计时维护 `valid_count`；输出时仅在 `valid_count > 0` 的位置求均值。
  - 修复后验证：`project_skills/runs/debug_q1_after_tool_fix_20260319_01/task_summary.json` 中 q1 已成功；`project_skills/runs/debug_train_first5_after_tool_fix_20260319_01/run_summary.json` 中前五题全部成功。

- [x] 确认 `GDAL runtime is not available in this environment` 这类致命报错的根因是运行目录 / 模块入口错误，而不是 `Statistics.py` 修复回退或 `system.local.json` 配错

  - 2026-03-20 已用同一套 conda 解释器做导入对照：在外层目录 `D:\skills-evo\project_skills` 执行 `import osgeo`，会落到 `E:\miniconda3\envs\earth-bench-skill-eval\Lib\site-packages\osgeo\__init__.py`；在内层目录 `D:\skills-evo\project_skills\project_skills` 执行，则会落到仓库自带的 `D:\skills-evo\project_skills\project_skills\osgeo\__init__.py`。
  - 结论：再次看到这个致命 GDAL 报错时，先检查当前工作目录是不是外层仓库根目录，以及入口是否写成 `python -m project_skills.nlrl_skills.cli --config "project_skills/configs/system.local.json" ...`，不要先怀疑 GDAL 数值修复文件被回退。

## 现象记录

- 端到端 monolithic skill 的定位例子：`project_skills/runs/_isolated/train20_empty_skill_library/skill_library/tvdi-annual-trend-from-ndvi-lst/SKILL.md`
- 对应执行例子：`project_skills/runs/debug_train_first20_empty_20260319_01/task_01_1/iteration_04/env/state.json`
- q1 的 gold snapshot 应被当成显式 benchmark contract：`project_skills/runs/debug_train_first20_parallel_03_20260319_01/task_01_1/task.json`（以及源数据 `project_skills/data/converted/earth_bench_skill_rl/question.json`）里的 `gold_trajectory` 明确要求走 `get_filelist -> compute_tvdi -> calculate_tif_average x4 -> calc_batch_image_mean -> compute_linear_trend -> B`
- 更细的 gold 发现是：q1 实际只按 2019/2020/2021/2022 四个年度聚合，年度均值固定为 `[0.45, 0.42, 0.39, 0.37]`、线性趋势为 `-0.037`；同时 `task.json`/`file_list` 里还带了一个未配对的 `Xinjiang_2022-10-16_LST.tif`，最终 2022 年聚合只用了 22 景 TVDI。
- step budget 与端到端 skill 有天然冲突：`project_skills/runs/debug_train_first5_after_tool_fix_20260319_01/task_01_1/iteration_01/env/state.json` 中，q1 成功时也已经用了 8 次工具调用 + 1 次 final，共 9 个 executor step；在此前 `max_executor_steps=10` 的配置下几乎没有额外试错空间。
