# 2026-03-21 Qwen3-8B双模式 Run 验收与 TPM / 上下文排查

## 你现在该看哪里

- 如果你只想先知道结论，看下面的“速览”。
- 如果你最关心“除了 TPM 之外还有什么严重问题”，直接看“非 TPM 严重错误汇总”。
- 如果你最关心“是不是上下文超限”，直接看“上下文窗口实测”。
- 如果你最关心“TPM 探测值和最近两次 run 是否对得上”，直接看“TPM 探测与最近两次 run 的对照”。

## 速览

- 当前最新两个 dualmode run 确实是：
  - `project_skills/runs/dualmode_mode1/20260321_0001_dualmode_mode1_train`
  - `project_skills/runs/dualmode_mode2/20260321_0001_dualmode_mode2_train`
- 但它们都不是完整收官的最终 run：
  - `mode1` 最新完整 `task_summary.json` 停在 `task_18_18`
  - `mode2` 最新完整 `task_summary.json` 停在 `task_05_5`
  - `mode1/task_19_19` 和 `mode2/task_06_6` 仍只有中间产物，没有最终 `task_summary.json`
- 当前小模型不是 38B，而是 `Qwen/Qwen3-8B`：
  - `router = Qwen/Qwen3-8B`
  - `executor = Qwen/Qwen3-8B`
  - `actor / critic = gpt-5.4`
- `TPM` 仍然是最大单项失败原因，但不是唯一主因。
- 这两次 run 里没有证据表明小模型请求超过了 `90K` 上下文。
- 对当前远端 `Qwen/Qwen3-8B` endpoint 的实测表明：
  - `110K` prompt token 可以成功
  - `150K` prompt token 会因 `max_prompt_tokens (131072)` 被拒绝
- 因此：这轮主要不是“90K 上下文爆掉”，而更像是“run-like 调用形态下的有效 TPM 被击穿”。

## 本轮核验范围

- 核验最新两个 dualmode run 是否就是当前最新 run。
- 判断主要失败是否卡在 `TPM`，以及除 `TPM` 之外还有哪些严重问题。
- 澄清当前小模型实际是 `Qwen/Qwen3-8B`，不是 38B。
- 追踪这两个 run 里所有小模型 agent 请求的上下文大小，检查是否超过 `90K`。
- 新写探测脚本，实测当前 `Qwen/Qwen3-8B` endpoint 的上下文窗口上限。
- 做两类 `TPM` 探针，并把探测范围与最近两次 run 的失败时间线对照。

## 最新两个 run 的验收结论

### 1. run 身份

- 当前最新两个 run 确实是：
  - `dualmode_mode1/20260321_0001_dualmode_mode1_train`
  - `dualmode_mode2/20260321_0001_dualmode_mode2_train`

### 2. run 完成状态

- 这两个 run 都不是完整收官。
- 当前能用于验收的“最后完整落盘任务”是：
  - `mode1`: `task_18_18`
  - `mode2`: `task_05_5`

### 3. 模型配置

- 两个 run 的 `config_snapshot.json` 显示：
  - 小模型位是 `Qwen/Qwen3-8B`
  - 大模型位是 `gpt-5.4`
- 所以本轮问题不能表述为“38B 卡住了”，更准确是：
  - `Qwen/Qwen3-8B` 作为 router / executor 时，遇到了明显的 TPM 和一批结构性流程错误

## 失败总览

### 1. 总体统计

| run | 已落盘任务数 | 失败任务数 | TPM 失败 | 非 TPM 严重失败 |
| --- | ---: | ---: | ---: | ---: |
| mode1 | 18 | 14 | 8 | 6 |
| mode2 | 5 | 5 | 1 | 4 |

### 2. 总判断

- `TPM` 是这两次 run 里最大的单项失败源。
- 但如果只解决 `TPM`，这两次实验也不会直接变稳，因为还有一批不是限额问题的结构性错误。
- 这些非 TPM 错误里，真正需要优先修的不是“换更大上下文”，而是：
  - `mode2` 的 parameter-worker / 参数生成链超时与 fail-close
  - 路由 / skill 覆盖与冷启动
  - tool 返回路径传播
  - 结构化输出与 skill 产物稳健性

## 非 TPM 严重错误汇总

这一节是本次整理新增重点。目的不是只列名字，而是明确：

- 数量是多少
- 属于哪一类
- 为什么它严重
- 它是不是“换 API / 绕过 TPM”后还会继续存在

### A. mode1 的非 TPM 严重错误

先纠正一个前提：前一版把 `mode1` 里几类错误过度压成了“结构化输出解析失败”，这不准确。这里按更接近真实根因的方式重写。

| 类别 | 数量 | 对应任务 |
| --- | ---: | --- |
| skill 产物损坏 / YAML 解析失败 | 1 | `task_03_3` |
| 路由 / 技能族错配，并诱发超长截断 JSON | 2 | `task_06_6`, `task_15_15` |
| 返回路径传播 / 聚合契约错配 | 2 | `task_12_12`, `task_17_17` |
| 后端瞬时 `502` | 1 | `task_14_14` |

#### 1. skill 产物损坏 / YAML 解析失败: 1 个

- 对应任务：
  - `task_03_3`
- 代表例子：
  - `iteration_01/actor/..._actor_modify_skill_response.json` 里写出的 skill 文本本身就有格式问题
  - `iteration_01/iteration_failure.json` 直接报：`mapping values are not allowed here`
- 为什么严重：
  - 这不是 executor 普通算错，也不是泛泛的“JSON 没闭合”。
  - 它是 actor 改 skill 时把 `SKILL.md` 产物写坏了，后面连 skill 解析和装载都过不去。
- 这是不是 TPM 问题：
  - 不是。
  - 换 API 不会自动修复 actor 产物格式校验缺失。

#### 2. 路由 / 技能族错配，并诱发超长截断 JSON: 2 个

- 对应任务：
  - `task_06_6`
  - `task_15_15`
- 代表例子：
  - `task_06_6` 其实是热红外单通道 LST 趋势任务，但 router 选成了 `tvdi-multiyear-dryness-trend`，后面 executor 试图拼一个很大的 `compute_tvdi` 参数 JSON，响应被截断，最后报 `Unterminated string...`
  - `task_15_15` 要的是“找最大平均 LST 对应日期”，router 选成了 `split-window-lst-multiyear-trend` 后，executor 又虚构了不受支持的 `parse_and_group_files`，同样因为输出过长被截断
- 为什么严重：
  - 这里的“解析失败”只是表象，前面的真实问题是任务被放进了不合适的技能族或执行抽象。
  - 一旦上游抽象错了，后面就容易生成又长又错的 tool-call JSON，最后以截断的形式爆出来。
- 这是不是 TPM 问题：
  - 不是。
  - 即使把额度放大，这两类任务也仍然会沿着错误方法链继续跑偏。

#### 3. 返回路径传播 / 聚合契约错配: 2 个

- 对应任务：
  - `task_12_12`
  - `task_17_17`
- 代表例子：
  - `task_12_12` 里 `lst_multi_channel` 实际返回的是运行时临时路径，但后续步骤继续拿猜出来的相对路径去做 `calculate_threshold_ratio`，于是文件反复打不开
  - `task_17_17` 不能简单记成“错路由”：那只发生在 iteration 1；从 iteration 2 开始 router 已经选中了新建的 `modis-band-ratio-atmospheric-absorption`，但 executor 仍然忽略 `band_ratio` 返回的真实路径，改用自己拼的 `question17/pwv_...tif`，并且时间点筛选、阈值聚合也没做对
- 为什么严重：
  - 这说明问题不只在 router，还在 tool contract 没有被后续步骤真正遵守。
  - 就算 skill 已经选对，returned path 没沿用、聚合规则没落地，任务还是会持续失败。
- 这是不是 TPM 问题：
  - 不是。
  - 换大模型或绕过 TPM 也不会自动修复 returned-path 和 aggregation contract。

#### 4. 后端 `502`: 1 个

- 对应任务：
  - `task_14_14`
- 代表例子：
  - 直接报错：`Error code: 502`
- 为什么严重：
  - 这是典型的基础设施不稳定。
  - 它和 skill 逻辑无关，但会直接中断任务。
- 这是不是 TPM 问题：
  - 不是。
  - 但这类问题通常可以靠重试 / 退避 / 更稳服务端部分缓解。

### A+. 针对 mode1 这几类错误的建议修法

这一节是后续补充，用来回答一个更实际的问题：`mode1` 这些错误如果现在要修，最合理的修法分别是什么。

先给总排序。我认为不是所有问题都该继续堆 prompt，优先级应该是：

1. 先把 `runtime` 层的硬约束补上
2. 再把 `skill` 的结构化元信息补上
3. 最后才是继续微调 router / actor / executor 的提示词

原因很简单：

- `mode1` 现在很多失败已经不是“模型完全不会”，而是“系统允许它把错误产物写进去”或“系统没有在运行时拦住明显违约”
- 这类错误靠 prompt 只能缓解，靠 runtime 才能真正收口

可以先压成一个实施表：

| 错误类 | 我认为最合理的主修法 | 优先级 |
| --- | --- | --- |
| skill 产物损坏 / YAML 解析失败 | actor 写入前做 `validate -> staged write -> commit`，失败时回滚旧 skill | `P0` |
| 路由 / 技能族错配，并诱发超长截断 JSON | 给 skill header 增加结构化路由元信息，router 先规则筛再 LLM 打分；同时加 tool-call JSON 体积与 schema 守卫 | `P1` |
| 返回路径传播 / 聚合契约错配 | 在 runtime 里引入 artifact registry 和下游输入校验，不再只靠 skill 文本提醒“要沿用 returned path” | `P0` |
| 后端 `502` / 空响应 / 非法 JSON | 把“空响应/坏 JSON/502”视为可重试的瞬时基础设施错误，不写入学习信号 | `P0` |

#### 1. skill 产物损坏 / YAML 解析失败

我认为最合理的修法是：**不要让 actor 直接覆盖正式 skill，而是改成“先验证，再提交”**。

具体做法：

- 在 `project_skills/nlrl_skills/actor.py` 的 `SkillActor.apply(...)` 里，不要直接把 `files_to_write` 写入正式 skill 目录
- 先写到临时目录，例如 `skill_name.__staging__`
- 调用和 `project_skills/nlrl_skills/skills.py::_split_frontmatter(...)` 同一套解析逻辑，对 `SKILL.md` 做强校验：
  - frontmatter 是否闭合
  - YAML 是否能解析成 mapping
  - `name / description / allowed-tools / consumption-mode` 是否存在且类型正确
  - `allowed-tools` 是否都在当前 toolbox 中存在
- 校验通过后再原子替换正式 skill；失败则保留旧 skill，不让坏产物落库

我认为这一步比继续调 actor prompt 更值，因为：

- 这类错误是确定性的
- 根因不是“模型太笨”，而是“系统允许坏 skill 落地”
- 一旦做 staged write + rollback，这类错误基本能被压成局部失败，而不是污染整个 skill 库

建议再补两条保护：

- 若校验失败，可让 actor 原样重试一次，但只允许修 frontmatter，不重新发散内容
- 基础设施错误或产物校验失败时，不要把这次修改写进 experience buffer，避免经验库吸收噪声

#### 2. 路由 / 技能族错配，并诱发超长截断 JSON

我认为最合理的修法不是单纯改 router prompt，而是做 **“结构化路由 + 更窄的 skill 家族边界 + executor JSON 守卫”**。

第一层：给 skill header 补结构化元信息。

当前 `SkillHeader` 已经有 `metadata` 字段，但基本没被真正拿来做路由。建议每个 skill 在 frontmatter 里补这些字段：

- `temporal_scope`: `single_date / multi_date / multi_year`
- `result_kind`: `ratio / count / mean_compare / argmax_date / trend / spike_count`
- `sensor_family`: `landsat_single_channel / bt31_bt32 / ndvi_lst / modis_day_night`
- `primary_tools`
- `negative_triggers`

然后 router 不要只看自由文本描述，而是先做规则筛：

- `single_date` 题先排除 `multi_year` skill
- 要 `argmax_date` 的题先排除纯 `count / trend` skill
- `BT_31 / BT_32` 文件模式先排除必须依赖 `B4 / B5` 的 skill

这样可以先砍掉一批明显不可能的 skill，再让 LLM 在剩下的候选里打分。

第二层：收紧 skill 家族边界。

`mode1` 当前一些失败不是因为完全没 skill，而是 skill 太宽，容易把：

- 多日期计数
- 多日期极值日期选择
- 多年趋势
- 单日期阈值比例

误塞进同一个“看起来像 LST”家族里。

所以我认为应该继续把 skill 拆窄，而不是把所有多日期 LST 任务都压进一个大 skill。

第三层：给 executor 的 tool-call JSON 加体积和 schema 守卫。

当前 `project_skills/nlrl_skills/agent_loop.py` 里，只要模型给出 JSON 就会尝试往下走；这会导致：

- 错 skill 下生成非常长的参数 JSON
- 引入根本不存在的工具名
- 最后以 `Unterminated string` 这种形式表现出来

建议加两条运行时守卫：

- 如果 `arguments` 序列化后超过某个阈值，先不执行，要求模型用更短、更局部的工具调用重发
- 如果工具名不在当前 `allowed_tools` 或参数形态明显不符合 live schema，直接返回“contract mismatch, resend compact call”，而不是把坏 JSON 一路放大

另外还有一个很值得顺手修的小点：

- 像 `task_15_15` 这种明确是 coverage gap 的任务，critic 已经建议 `create_skill`
- 但 actor 仍然被 skill 数量压力带偏去做 `merge_skills`

所以 actor 的动作选择也应该加一个硬规则：

- 当 reward 明确是 coverage gap 且目标 skill 家族不存在时，不要因为 skill count pressure 就优先 merge

#### 3. 返回路径传播 / 聚合契约错配

我认为这类问题最合理的修法是：**把 returned-path 约束从“写在 skill 里提醒”升级成“runtime 里的硬契约”**。

现在很多 skill 已经在文本里强调：

- “必须沿用工具返回路径”
- “不要自己猜输出路径”

但事实证明，光靠文字提醒不够。

更稳的方案是引入一个轻量的 artifact registry：

- 每次 raster-producing tool 成功执行后，把它的真实返回路径登记成一个 runtime artifact
- 记录内容至少包括：
  - `tool_name`
  - `step_index`
  - `returned_paths`
  - `source_inputs`

然后在下游工具执行前做输入校验：

- 如果参数里出现的是一个“看起来像模型猜出来的输出路径”，而它既不在 artifact registry，也不在原始 `get_filelist` 源数据里，就拒绝执行
- 返回一个明确错误，例如：
  - `downstream path was not produced by any previous tool call; use returned path verbatim`

这一步我认为应该放在 `project_skills/nlrl_skills/agent_loop.py` 或 toolbox 执行包装层，而不是继续堆 skill prompt。

对于聚合类工具，还应再加一个 preflight：

- 聚合前检查输入文件数是否等于前面实际产出的文件数
- 若 expected output count 和实际 output count 对不上，不允许直接聚合并回答
- 对 `count_images_exceeding_threshold_ratio`、`calc_batch_image_mean` 这类批处理工具尤其重要

如果只做 prompt 优化，不做 runtime preflight，类似 `task_12_12 / task_17_17` 的问题还会反复出现，因为：

- skill 可以写对
- router 也可以选对
- 但 executor 仍可能凭空拼 `question17/pwv_...tif`

#### 4. 后端 `502` / 空响应 / 非法 JSON

我认为这类问题最合理的修法是：**把它们从“学习问题”剥离出来，归到“可重试基础设施问题”**。

当前 `project_skills/nlrl_skills/llm.py` 已经会对很多 HTTP / network 错误做重试，但还不够，原因是：

- 空响应
- 非空但不是合法 JSON
- 被截断的 JSON

这些在当前流程里往往会直接变成 iteration 失败。

建议补两层：

第一层：在 `chat_json(...)` 或 `JSONToolAgent.run(...)` 里，把下面几类错误视为“可重试”而不是“立即失败”：

- `Empty model response`
- `extract_json_object(...)` 失败
- 明显的 JSON 截断错误，例如 `Unterminated string`

重试策略可以是：

1. 原 prompt 原样重试一次
2. 若仍失败，再发一个短补救提示：
   - “Only resend a compact JSON object following the schema. Do not repeat previous observations.”
3. 若还是失败，再记为 infrastructure-style failure

第二层：这类失败不要立刻写成 skill 学习信号。

也就是说，如果失败根因是：

- `502`
- 空响应
- JSON 壳子丢失

那 critic / actor 最好先跳过 skill 修改，避免把纯基础设施噪声误学成“要改 skill”。

我认为这是合理的，因为：

- 基础设施波动不应该污染 skill 演化
- 否则 experience buffer 会混入很多假失败签名
- actor 可能会去修一个根本没错的 skill

### A++. 如果现在只让我选一轮最值得落地的修复组合

如果只能先做一轮，我会按这个组合落：

1. `P0`：actor staged write + YAML/frontmatter validate + rollback
2. `P0`：artifact registry + downstream path/preflight validation
3. `P0`：empty response / truncated JSON / 502 统一按可重试基础设施错误处理
4. `P1`：给 skill header 补结构化 metadata，让 router 先规则筛再 LLM 排名

为什么不是先改 router？

- 因为当前最伤的是“错误一旦发生会直接污染 skill 或把坏路径继续传播”
- 先补 runtime 硬约束，收益最大，也最不依赖换模型

换句话说，`mode1` 现在最合理的方向不是继续让模型“更小心”，而是让系统先具备：

- 写坏 skill 时不落库
- 猜错输出路径时不往下跑
- 基础设施坏掉时不误学
- 路由时先排除显然不兼容的 skill

这四件事补上后，再回头做 prompt 和 skill 文本精修，性价比才高。

### B. mode2 的非 TPM 严重错误

这里也要纠正前一版的误导：`mode2` 不能简单写成“缺 skill 2 个 + planner 缺参 1 个”。同一个任务在不同 iteration 的失败点是会变化的，下面按根因分层，任务可以重复计入。

| 类别 | 数量 | 对应任务 |
| --- | ---: | --- |
| 首轮冷启动 skill 缺口 | 2 | `task_01_1`, `task_02_2` |
| parameter-worker / 参数生成链超时 | 3 | `task_01_1`, `task_02_2`, `task_04_4` |
| 空响应 / JSON 输出不稳定 | 1 | `task_03_3` |

#### 1. 首轮冷启动 skill 缺口: 2 个

- 对应任务：
  - `task_01_1`
  - `task_02_2`
- 代表例子：
  - 这两个任务的 iteration 1 的确都停在 `No applicable skill`
  - 但这只是首轮冷启动现象，不是它们后续几轮持续失败的最终主因
- 为什么严重：
  - 冷启动会直接浪费一轮迭代，把本来可以用来执行和纠错的预算先花在建 skill 上。
  - 但这里必须和“最终失败归因”分开看，不能据此就说这两个任务是因为没 skill 所以直接失败。
- 这是不是 TPM 问题：
  - 不是。
  - 这是环境先执行、actor 后补 skill 的流程特性加上冷启动共同造成的。

#### 2. parameter-worker / 参数生成链超时: 3 个

- 对应任务：
  - `task_01_1`
  - `task_02_2`
  - `task_04_4`
- 代表例子：
  - `task_01_1/iteration_02/env/planner_execution/step_01.json` 里，planned tool 是 `get_filelist`，prompt 已经明确写了 `Relevant datas are stored at benchmark/data/question1`，但 `raw_result.error` 是 `parameter-worker network error after 5 primary retries and one backup attempt ... Request timed out.`
  - `task_04_4/iteration_01/env/planner_execution/step_01.json` 也是同型问题；日志里的 `arguments: {}` 只是异常后的占位值，不是充分证据说 planner 真决定传空参
- 为什么严重：
  - `mode2` 当前的参数绑定是交给 parameter worker 做的；一旦它超时，运行时没有硬兜底去自动补 `dir_path` 这类明显参数。
  - 所以这里的持续主因不是“planner 笨到不会填参数”，而是“参数生成链本身不稳，而且异常后只留下 `{}` 占位”。
- 这是不是 TPM 问题：
  - 不是。
  - 这更像 parameter-worker 的网络/服务稳定性问题，加上 planner runtime 缺 deterministic fallback。

#### 3. 空响应 / JSON 输出不稳定: 1 个

- 对应任务：
  - `task_03_3`
- 代表例子：
  - `task_03_3` 的 iteration 1 更像是 skill family mismatch / 过触发
  - 但真正把任务打死的是 iteration 2 的：`Empty model response; expected JSON object.`
- 为什么严重：
  - 这说明至少有一轮模型调用连最基本的 JSON 壳子都没返回。
  - 在 planner 模式下，这种错误会直接截断后续步骤，连参数生成和工具执行都走不下去。
- 这是不是 TPM 问题：
  - 不是。
  - 就算没有限额，只要模型或网关偶发空响应，这类任务也照样会断。

### C. 一个很重要的总判断

- 归因修正一：
  - `mode2/task_01_1` 和 `task_02_2` 不能再写成“因为没有 skill 所以直接失败”。
  - 更准确的说法是：iteration 1 确实有冷启动 skill 缺口，但 iteration 2 以后持续卡住的主因是 parameter-worker / 参数生成链超时。
- 归因修正二：
  - `mode2` 日志里很多 `arguments: {}` 不能直接解读成“planner 明确传了空参数”。
  - 从 `planner_runtime.py` 看，这是 `decision = None` 时的异常占位写法；真实失败点往往是 parameter-worker timeout。
- 归因修正三：
  - `mode1` 也不能再泛泛写成“解析失败很多”。
  - 更接近真实情况的是：一类是 actor 把 skill 产物写坏，一类是路由错到别的技能族后诱发超长截断 JSON，一类是 returned-path / 聚合契约没有被后续步骤严格执行。
- 所以，如果你下一步只是绕 TPM：
  - `mode1` 仍会被 skill 产物格式、returned-path、聚合契约、错技能族这些问题绊住
  - `mode2` 仍会被 parameter-worker 超时、空响应，以及首轮冷启动带来的迭代浪费绊住

## 为什么有的任务触发 TPM，有的没有

- 当前不是因为 `train_tasks` 并发执行；主循环本身是串行的。
- 真正关键点是：
  - `TPM` 看的是滚动 60 秒窗口
  - 不是“一个任务固定扣一次”
- 同一任务内部，prompt 会不断膨胀，因为 executor 会把之前的 assistant JSON 和 tool observation 持续带回去。

### 典型例子

- `task_18_18` 的 `executor_step_1_request.json` 约 `16,731` 字符
- 到 `executor_step_8_request.json` 已涨到约 `101,866` 字符
- 所以很多任务不是“一上来就 429”，而是前几步都正常，后面某一步才触发 `TPM`

### 还有两个放大器

- skill library 会随着训练变大，router prompt 也随之变长
- `mode2` 比 `mode1` 多了 planner、planner-worker、answer selector，以及 actor/critic 链路，整体更容易烧 token

## 小模型上下文追踪

### 1. 结论

- 以 `90K` 为判断线，这两个最新 run 里没有任何一条小模型请求超过 `90K`

### 2. 统计结果

- 小模型请求总数：`436`
- `> 90000 token`：`0`
- `> 70000 token`：`0`
- `> 50000 token`：`8`
- `> 32768 token`：`23`

### 3. 分 agent 统计

- `executor`：`357` 条，最大约 `57,167 token`
- `router`：`50` 条，最大约 `1,982 token`
- `planner`：`15` 条，最大约 `4,388 token`
- `planner_answer_selector`：`14` 条，最大约 `1,036 token`
- `planner_worker`：`14` 条，最大约 `1,659 token`

### 4. 解释

- 如果当前 endpoint 的真实上下文窗口确实是 `90K+`，那么这两次 run 没有“小模型上下文超限”的证据
- 如果某个 endpoint 实际只有 `32K`，那么当前这批请求里已经有 `23` 条会贴线甚至越线
- 但对当前已实测的这个远端 `Qwen/Qwen3-8B` endpoint 来说，更像是 TPM 问题，而不是 90K 上下文爆掉

## 上下文窗口实测

### 1. 新增脚本

- `project_skills/scripts/qwen3_context_probe.py`

### 2. 实测结果

| 目标 prompt token | 结果 | 备注 |
| --- | --- | --- |
| `28K` | 成功 | `usage_prompt = 28001` |
| `40K` | 成功 | `usage_prompt = 40001` |
| `80K` | 成功 | `usage_prompt = 80001` |
| `110K` | 成功 | `usage_prompt = 110001` |
| `150K` | 失败 | 超过 `max_prompt_tokens (131072)` |

### 3. 结论

- 当前 endpoint 至少支持到 `110K` prompt token
- 当前 endpoint 的硬上限是 `131072`
- 所以本轮双模式训练里大量失败不能解释成“90K 一到就爆”

## TPM 探测与最近两次 run 的对照

### 1. 两类探针

#### A. 保守探针

- 配置：
  - `target_prompt_tokens = 12000`
  - `max_output_tokens = 8`
  - `sleep_seconds = 0.5`
- 结果：
  - 在 20 轮内没有触发 TPM
  - 60 秒滚动窗口内观测到的 `total_tokens` 达到约 `240080`

这说明：

- 如果请求形态非常保守，且 completion 很小，当前 endpoint 的 TPM 容量明显高于 `240k/min`

#### B. 更接近 dualmode 真形态的探针

- 配置特征：
  - `response_format = json_object`
  - 不显式传 `max_tokens`
  - 请求形态尽量贴近 `nlrl_skills`
- 结果：
  - `30K` prompt：前 3 轮成功，第 4 轮触发 `TPM`
    - 失败前 60 秒累计 `90018`
    - 估计范围：`[90018, 120024]`
  - `20K` prompt：前 5 轮成功，第 6 轮触发 `TPM`
    - 失败前 60 秒累计 `100030`
    - 估计范围：`[100030, 120036]`

### 2. 对 run-like 调用形态的判断

- 对“真实 dualmode 类请求形态”的有效 TPM，可暂时判断在：
  - `100k ~ 120k total_tokens / minute`

### 3. 为什么最近两次 run 里的 TPM 看起来很早就来了

- 因为 `mode1` 和 `mode2` 两次最新 run 在时间线上是重叠的
- 所以判断 `TPM` 时，不能只看单个 run，必须合并成同一条 endpoint 时间线

### 4. 与实际失败点的对照

- 强吻合样本：
  - `mode1/task_18_18`：失败前锚点全局 60 秒累计约 `171321`
  - `mode2/task_05_5`：失败前锚点全局 60 秒累计约 `165630`
  - `mode1/task_13_13`：失败前锚点全局 60 秒累计约 `156845`
  - `mode1/task_16_16`：失败前锚点全局 60 秒累计约 `246157`
  - `mode1/task_01_1`：失败前锚点全局 60 秒累计约 `272014`
- 这些都明显高于本轮探测出的 `100k ~ 120k/min` 有效区间

### 5. 最终判断

- 最近两次实验里最核心的一批 `TPM 429`，和本轮探测得到的有效 TPM 区间是吻合的
- 尤其是后期、长轨迹、双 run 重叠的那些 `TPM 429`，基本可以解释为：
  - 全局 60 秒 token 消耗超过了当前 endpoint 对 run-like 请求形态的有效额度

## 当前最实用的下一步建议

### 1. 如果你的目标是先把训练跑稳

优先级建议是：

1. 先做全局限流和 `429` 指数退避
2. 再修 parameter-worker / 参数生成链的超时重试、fail-close 和显式兜底绑定
3. 再修 tool 返回路径的严格传播
4. 再修 skill 触发精度、冷启动覆盖和 actor 产物格式校验

原因很简单：

- 只换 API 或只绕 TPM，不能解决 parameter-worker 超时后留下的 `{}` 占位、returned-path 没沿用、actor 写坏 `SKILL.md`、空响应这些问题
- `mode2` 里的 `No applicable skill` 确实存在，但主要是首轮冷启动，不应该继续被当成持续主因
- 但如果连 `TPM` 都不控住，后面很多任务连完整轨迹都走不到

### 2. 如果你的目标是继续用 `Qwen/Qwen3-8B`

- 可以继续用，但最好加：
  - 全局 token 节流
  - `429` 重试退避
  - executor 上下文裁剪
  - 更严格的结构化输出约束

### 3. 如果你的目标是换更稳的部署方式

- 这会主要改善两类问题：
  - `TPM`
  - `502` / 服务稳定性
- 但不会自动改善：
  - skill 覆盖
  - 错路由
  - planner 缺参
  - 路径传播错误
  - 空响应 / 结构化解析失败

## 关键产物与文件位置

### 1. 当前交互记录

- `AI交互记录/2026-03-21_Qwen3-8B双模式Run验收与TPM上下文排查.md`

### 2. 新增脚本

- `project_skills/scripts/qwen3_context_probe.py`

### 3. 探测结果

- `project_skills/runs/_tmp_context_probe_qwen3_8b.json`
- `project_skills/runs/_tmp_context_probe_qwen3_8b_150k.json`
- `project_skills/runs/_tmp_qwen3_8b_probe_summary_20260321.json`

### 4. 非 TPM 严重错误的代表样本

- `mode1/task_12_12/task_summary.json`
- `mode1/task_14_14/task_summary.json`
- `mode1/task_17_17/task_summary.json`
- `mode1/task_03_3/task_summary.json`
- `mode1/task_06_6/task_summary.json`
- `mode1/task_15_15/task_summary.json`
- `mode2/task_01_1/task_summary.json`
- `mode2/task_02_2/task_summary.json`
- `mode2/task_03_3/task_summary.json`
- `mode2/task_04_4/task_summary.json`

## 2026-03-21 付费 `qwen3-8b` 切换与 thinking 探针补记

这一段是当天后续追加，不属于前面那组 `Qwen/Qwen3-8B` 免费模型 run 的验收本体，而是用户要求把双模式训练切到模型广场里的付费 `qwen3-8b` 后，围绕 `thinking` 参数做的一轮排查与重发。

### 1. 发生了什么

- 用户要求把双模式训练里的小模型从免费 `Qwen/Qwen3-8B` 切到付费 `qwen3-8b`
- 最初先新建了两份专用配置：
  - `project_skills/configs/system.dualmode_mode1.qwen3-8b-paid.local.json`
  - `project_skills/configs/system.dualmode_mode2.qwen3-8b-paid.local.json`
- 第一批付费 run：
  - `mode1`: `20260321_1127_qwen3_8b_paid_dualmode_mode1_train`
  - `mode2`: `20260321_1127_qwen3_8b_paid_dualmode_mode2_train`
- 这批 run 很快暴露出新的接口兼容问题，不适合作为正式结果保留

### 2. 第一个新错误：非流式下 `thinking` 参数不兼容

- 在这批付费 `qwen3-8b` run 里，大量任务直接报：
  - `Error code: 400 - {'error': {'message': 'parameter.enable_thinking must be set to false for non-streaming calls' ...}}`
- 代表样本：
  - `project_skills/runs/dualmode_mode1/20260321_1127_qwen3_8b_paid_dualmode_mode1_train/task_16_16/task_summary.json`
  - `project_skills/runs/dualmode_mode1/20260321_1127_qwen3_8b_paid_dualmode_mode1_train/task_17_17/task_summary.json`
  - `project_skills/runs/dualmode_mode2/20260321_1127_qwen3_8b_paid_dualmode_mode2_train/task_03_3/task_summary.json`
- 这说明当前训练框架原先使用的“非流式 + `response_format=json_object`”范式，不适配这个付费 `qwen3-8b` 的 thinking 接口

### 3. 临时 workaround 与为什么又被推翻

- 为了先验证是不是纯 thinking 参数导致，曾临时把付费 `qwen3-8b` 的 `router/executor` 配置改成：
  - `enable_thinking = false`
- 然后重发过一批临时 run：
  - `mode1`: `20260321_1144_qwen3_8b_paid_thinkingfix_dualmode_mode1_train`
  - `mode2`: `20260321_1144_qwen3_8b_paid_thinkingfix_dualmode_mode2_train`
- 但用户明确要求：
  - `gpt-5.4` 的原设置不要动
  - `qwen3-8b` 必须尽量保留 thinking 打开
- 所以这批 `1144` run 也被停掉，只作为中间排错产物保留，不作为正式实验结果

### 4. thinking 探针结论

为了不再拍脑袋改配置，单独写了探针脚本并做了范式测试：

- 新增脚本：
  - `project_skills/scripts/qwen3_paid_thinking_probe.py`
- 结果文件：
  - `project_skills/runs/_launch_logs/qwen3_paid_thinking_probe.json`

核心结论是：

1. `non-streaming + enable_thinking=true` 会直接报错
   - `parameter.enable_thinking only support stream call`
2. `streaming + enable_thinking=true + response_format=json_object` 也会直接报错
   - `Json mode response is not supported when enable_thinking is true`
3. `streaming + enable_thinking=true + 不使用 response_format` 可以成功
4. 在这种成功范式下：
   - 思维链出现在 `delta.reasoning_content`
   - 正文答案出现在 `delta.content`
   - 两者是分开的，不是 `<think>...</think>` 混在正文里
5. 如果提示词本身强约束“只返回一个 JSON 对象”，那么即使不走 `response_format=json_object`，正文里的 `content` 仍然可以稳定产出干净 JSON

因此，对这个付费 `qwen3-8b` 来说，兼容且保留 thinking 的可用范式是：

- `stream = true`
- `enable_thinking = true`
- 不使用 `response_format = {"type": "json_object"}`
- 继续在 prompt 里强约束“只返回一个 JSON 对象”
- 运行时只收集 `delta.content` 作为正文 JSON，`delta.reasoning_content` 单独保留或忽略

### 5. 为了兼容 thinking 做的代码改动

- 在 `project_skills/nlrl_skills/config.py` 里，给 `LLMConfig` 增加了 `enable_thinking`
- 在 `project_skills/nlrl_skills/llm.py` 里：
  - 当 `enable_thinking = true` 时，自动改走流式收集
  - 不再附带 `response_format=json_object`
  - 把 `delta.content` 拼成最终正文
  - 把 `delta.reasoning_content` 单独记录到 `raw_response`
- 这样做的目的是：
  - 让 `qwen3-8b` 可以保留 thinking
  - 不改动 `gpt-5.4` 的原有调用方式
  - 尽量减少对训练主逻辑的侵入

### 6. 当前真正有效的一批付费 `qwen3-8b` thinking-on run

在完成上述兼容修改后，重新发起了第三批 run，这一批才是当前应该看的：

- `mode1`
  - run 名：`20260321_1153_qwen3_8b_paid_thinkingon_dualmode_mode1_train`
  - 绝对路径：`D:/skills-evo/project_skills/project_skills/runs/dualmode_mode1/20260321_1153_qwen3_8b_paid_thinkingon_dualmode_mode1_train`
  - 后台 PID：`14180`
- `mode2`
  - run 名：`20260321_1153_qwen3_8b_paid_thinkingon_dualmode_mode2_train`
  - 绝对路径：`D:/skills-evo/project_skills/project_skills/runs/dualmode_mode2/20260321_1153_qwen3_8b_paid_thinkingon_dualmode_mode2_train`
  - 后台 PID：`8740`

对应启动日志：

- `project_skills/runs/_launch_logs/20260321_1153_qwen3_8b_paid_thinkingon_dualmode_mode1_train.stdout.log`
- `project_skills/runs/_launch_logs/20260321_1153_qwen3_8b_paid_thinkingon_dualmode_mode1_train.stderr.log`
- `project_skills/runs/_launch_logs/20260321_1153_qwen3_8b_paid_thinkingon_dualmode_mode2_train.stdout.log`
- `project_skills/runs/_launch_logs/20260321_1153_qwen3_8b_paid_thinkingon_dualmode_mode2_train.stderr.log`

### 7. 哪些 run 是中间废弃产物

- `1127` 这一批：
  - 原始付费 `qwen3-8b` 切换版
  - 因非流式 thinking 不兼容而废弃
- `1144` 这一批：
  - 临时把 `enable_thinking=false` 作为 workaround 的排错版
  - 因不符合“保留 thinking”的目标而废弃
- 当前后续核验和验收，都应优先看 `1153` 这一批 thinking-on run

## 2026-03-21 晚间续更：1153 paid thinking-on 扩大样本

这一段是对 `1153` 这批 paid thinking-on run 的晚间续扫，用来覆盖下午那版只看到前 `19 / 8` 题的局部统计。

### 1. 当前盘面

- 这两个后台 Python 进程仍在运行：
  - `mode1`: PID `14180`
  - `mode2`: PID `8740`
- `mode1`
  - 已生成 `36` 个 `task_*` 目录
  - 已落盘 `35` 个 `task_summary.json`
  - 成功 `16`
  - 失败 `19`
  - 最新完整任务是 `task_35_35`
  - `task_36_36` 已有 `iteration_01` 中间产物，但还没有最终 `task_summary.json`
- `mode2`
  - 已生成 `15` 个 `task_*` 目录
  - 已落盘 `14` 个 `task_summary.json`
  - 成功 `1`
  - 失败 `13`
  - 最新完整任务是 `task_14_14`
  - `task_15_15` 已跑到 `iteration_03` 中间产物，但还没有最终 `task_summary.json`

### 2. 相比下午局部快照的变化

- `mode1` 新增完成了 `16` 个任务，其中成功 `10`、失败 `6`
- `mode1` 成功率从 `31.6% (6/19)` 升到 `45.7% (16/35)`
- `mode2` 新增完成了 `6` 个任务，但 `6` 个全部失败
- `mode2` 成功率从 `12.5% (1/8)` 降到 `7.1% (1/14)`
- 这说明 `mode1` 后段确实出现了 skill / executor 盘面的回升，而 `mode2` 没有出现类似拐点

### 3. 放大样本后的核心判断

- `mode1` 当前主要是两类问题混杂：
  - 一类是 JSON / YAML / 空响应 / 平台拒绝这类格式与调用稳定性问题
  - 另一类是多时相聚合、returned-path、TES 分支、年度聚合这些 workflow / tool-contract 错误
- `mode2` 当前 `13/13` 个失败任务的最新 `planner_execution/step_01.json` 都带有同一条 `parameter-worker network error ... Request timed out.`
- 所以“参数生成链卡死”不是早期局部现象，而是扩大样本后仍然成立的主故障
- actor / critic 在两边都在持续改 skill，但 `mode2` 因为卡在 `parameter-worker`，拿不到足够丰富的真实执行反馈，收益明显低于 `mode1`

### 4. 详细记录位置

- 详细扩大样本分析已追加到：
  - `AI交互记录/2026-03-21_Qwen3-8B付费ThinkingOn_1153双模式错误观察与Mode2链路分析.md`

## 下午 TODO

这一段是下午回看时的执行清单。默认前提是：当前 `1153` 这批 run 先继续跑，不主动中断。

### 1. 先不打断当前实验

- 保持这两条 run 继续跑：
  - `mode1`: `D:/skills-evo/project_skills/project_skills/runs/dualmode_mode1/20260321_1153_qwen3_8b_paid_thinkingon_dualmode_mode1_train`
  - `mode2`: `D:/skills-evo/project_skills/project_skills/runs/dualmode_mode2/20260321_1153_qwen3_8b_paid_thinkingon_dualmode_mode2_train`
- 下午先做盘面检查和归因，不先手动停掉

### 2. 重点看 actor / critic / skill 维护行为

- 重点不是只看任务成败，而是看 skill 库有没有在健康演化
- 下午优先抽查这些内容：
  - actor 的 `create_skill / modify_skill / merge_skills` 决策是否合理
  - critic 给 actor 的反馈是不是具体、可落地，而不是泛泛而谈
  - skill_library 里新 skill 的命名、触发边界、allowed tools、路径规则是否越写越稳定
  - experience buffer 有没有在积累可复用的 failure signature，而不是重复写同类经验

建议优先看的盘面：

- 每个 task 下的 `iteration_xx/critic/`
- 每个 task 下的 `iteration_xx/actor/`
- 两个 run 各自的 `skill_library/`
- 两个 run 各自的 `runtime_state/experience_buffer.jsonl`

### 3. 专门分析为什么 `mode2` 现在效果不够好

- 下午要把 `mode2` 单独拎出来看，不要混在 `mode1` 里一起看
- 重点排查：
  - planner 路由本身是不是还不稳
  - parameter-worker / 参数生成链在付费 `qwen3-8b` thinking-on 范式下是否仍有新的不稳定点
  - planner 产出的步骤序列是否正确，但败在参数绑定或执行契约
  - planner-answer-selector 是否在后段引入额外失真
  - 相比 `mode1`，`mode2` 是不是多了一层规划成本，但没有换来明显更好的 skill 维护收益

要回答的核心问题是：

- `mode2` 差，是差在 planner 质量，还是差在 planner-runtime/worker 契约，还是差在 skill 库冷启动与维护效率

### 4. 一条可直接推进的路线：拿当前局部 skill 库去做评估

- 如果下午看下来发现：
  - 当前 skill 库已经有一批可用 skill
  - 但继续 train 很慢
- 那么可以直接开一个评估分支：
  - 拿当前局部 skill 库冻结下来
  - 直接发起 eval
  - 先看“已有 skill 库的纯使用效果”到底怎么样

这条路线的价值是：

- 把“训练还在继续长 skill”与“现有 skill 库本身到底强不强”拆开
- 先测 skill 库的当前上限，而不是一直混在训练噪音里

### 5. 另一条并行推进的路线：研究并行生成单条 skill，再累积成 skill 库

- 这条路线下午可以开始设计，不一定当天就实现
- 目标不是继续沿用现在这种串行 task-by-task 训练，而是想办法：
  - 让多个 task 各自并行地产出单条 skill
  - 再把这些单条 skill 汇总、筛选、去重、合并
  - 逐步积累成一个更高维的 skill 库

这条路线要重点想清楚的点：

- 并行生成时，怎样避免不同任务各自写出重复或互相冲突的 skill
- skill 合并时按什么标准做：
  - 任务族相近
  - 工具序列相近
  - 失败签名相近
  - 路径/参数契约一致
- 并行生成后，是先人工筛选一轮再入总库，还是先入候选库再自动压缩
- experience buffer 是跟单条 skill 绑定，还是跟最终合并后的 skill 绑定

### 6. 下午最值得产出的东西

如果下午时间有限，优先争取产出这三样：

1. 一份对 `mode2` 当前弱点的清晰归因
2. 一个“当前局部 skill 库是否值得直接 eval”的判断
3. 一个“并行产出单条 skill -> 合并成 skill 库”的可执行设计草图

## Mode2 2240 当前补记

这段补记对应的是 `2026-03-21` 晚间这条新 run：

- `project_skills/runs/dualmode_mode2/20260321_2240_qwen3_8b_paid_allqwen_dualmode_mode2_train_runtimefix`

先说盘面结论。到目前为止，这条 `mode2` 已经不是“系统性全挂”了，而是进入了“可以跑通一批题，但会在少数任务族上反复暴露同一种规划缺陷”的阶段。当前落盘状态是：

- 成功：`task_02_2`、`task_03_3`、`task_04_4`、`task_05_5`、`task_06_6`、`task_08_8`
- 失败：`task_01_1`、`task_07_7`、`task_09_9`、`task_10_10`
- 正在进行：`task_11_11`

也就是说，截至 `task_10_10`，当前是 `6 / 10` 成功。这个结果和早先 `mode2` 大面积因为链路问题直接失效，已经不是一个盘面了。

### 1. 从 skill 库视角看现在的 mode2

当前 skill 库已经有 3 条 skill：

- `remote-sensing-dryness-trend-planning`
- `landsat-lst-single-channel-trend-planning`
- `landsat-single-date-ndvi-lst-class-contrast-planning`

如果只挑一条最有代表性的来看，我建议先看：

- `project_skills/runs/dualmode_mode2/skill_library/remote-sensing-dryness-trend-planning/SKILL.md`

这条 skill 现在基本能代表 `mode2` 里“planner skill”长成什么样。它不是一句 prompt，也不是简单的工具列表，而是一个半结构化的规划策略文档，主要由这几块组成：

- YAML 头部：`name / description / consumption-mode / allowed-tools`
  - 这是 skill 的检索入口。
  - router 先靠这里判断“这条 skill 大概管什么事”，planner 再看正文。
- `Use When`
  - 这是自然语言触发层。
  - 告诉系统什么题型会触发这条 skill，比如 TVDI、LST threshold、trend、count。
- `Family Routing`
  - 这是 skill 内部的二级分流。
  - 同一条 skill 下面再细分成 `single-date TVDI threshold`、`multi-date threshold-count`、`multi-date trend` 之类的小家族。
- `Core Rules`
  - 这是跨家族共享的硬规则。
  - 例如先 `get_filelist`、从文件名解析日期、先做时间窗口过滤、不要伪造不存在的中间产物、`lst_single_channel` 只能吃标量字符串参数等。
- 各个 recipe
  - 这是“碰到某一小家族时，工具顺序和参数约束应该怎么走”的主体。
  - 例如多日期 LST count 分支会明确写成：先发现文件，再按日期组完整 triplet，再逐日期 `lst_single_channel`，最后只做一次 aggregate count。
- `Guardrails`
  - 这是兜底约束。
  - 防止空参数、basename 直传、部分日期就提前收工、把 sidecar 文件当真 TIFF 用进去。
- `Stop Guidance`
  - 这是终止条件。
  - 它规定什么情况下才算“真的算完了”，什么情况下必须停下来报告 blocker，而不是编结果。

所以从 skill 库角度看，`mode2` 现在的 skill 已经不是“经验描述”，而是“带有任务分流、参数绑定、执行边界和停止条件的 planner policy”。

补一条很关键的实现细节：这些 skill 约束现在**主要是注入给 planner** 的，不是所有 agent 都吃到同一份完整 skill。

- planner
  - 这一层是拿到完整 `SKILL.md` 的。
  - `prompts_mode2/planner_system.md` 明确写了：`Read the activated SKILL.md as a planning prior`
  - `prompts_mode2/planner_user.md` 会把整份 `Activated planner-oriented SKILL.md` 连同 tool catalog 一起塞进 planner prompt
  - 所以像 `Use When / Family Routing / Core Rules / Guardrails / Stop Guidance` 这些提醒，planner 理论上都能看到
- router
  - 这一层**只看 header，不看 skill 正文**
  - 也就是主要看：`name / description / compatibility / allowed_tools / metadata`
  - 所以 router 负责的是“这条 skill 大概适不适合这道题”，而不是细读内部 recipe
- parameter_worker
  - 这一层目前**没有拿到完整 `SKILL.md`**
  - `prompts_mode2/planner_worker_user.md` 里只有：
    - 当前上下文
    - `Activated skill` 名字
    - `Planned next tool`
    - planner 给这一小步写的 `reason`
    - 可用工具 schema
  - 也就是说，worker 现在主要靠：
    - 上游 planner 的分步理由
    - 当前 observation
    - tool schema
    - 而不是直接阅读整份 skill 的 guardrails
- planner-answer-selector
  - 这一层同样不直接吃 skill 正文

这也解释了为什么如果只看 `planner_execution/step_xx.json`，会感觉“好像没看到 planner 提醒”：

- 因为你看到的其实是 **worker prompt**
- 真正给 planner 的完整 skill 注入，要去看各 task 下 `env/planner/*.json`

所以目前这套 `mode2` skill 的真实位置可以总结成一句话：

- **skill 已经做到像“优良 skill 库”那样去约束 planner 选工具和分支**
- **但还没有做到把同等强度的约束继续传给 parameter_worker 等后续 agent**

这也是当前盘面里一个很核心的结构性原因：

- planner 高层方向经常已经是对的
- 但 worker 还会把多日期塌成单日期，或者在 `NaN` 之后继续乱传参数

如果后面要进一步逼近你之前那套“六个优良 skill”的效果，下一步最该补的不是 planner 本身，而是：

- 从 `SKILL.md` 里抽一份短版的 `worker guardrails / parameter policy / stop rules`
- 再显式注入给 parameter_worker
- 让 skill 约束真正从“只管高层规划”下沉到“也管参数绑定和中间态停机”

### 2. 现在 skill 是怎么修的，怎么长的

这轮 `mode2` 到目前为止，主旋律其实不是“合并”，而是“失败驱动的定点修补”，再加上一处真正的 coverage 扩展。

先说修补链条：

- `task_01_1`
  - skill 选对了，但多年份 TVDI trend 只算了前面一截日期，然后就开始引用根本没生成出来的年度平均图。
  - 后续 actor 连续对 `remote-sensing-dryness-trend-planning` 做 `modify_skill`，把“全量日期配对 -> 年度聚合 -> 不得伪造缺失年份”的规则补进去。
- `task_07_7`
  - 题目明明是 `2021-06` 到 `2021-09` 的热浪季计数，结果 worker 在 `step_02` 还是只拿了 `2021-05-05` 这一景去算。
  - 于是这条 skill 又被补了“先做时间窗口过滤、不得拿窗口外 exemplar、季节/月份范围题不能只算一景”的约束。
- `task_09_9`
  - planner 理由已经写成“对窗口内每个有效日期都算 LST”，但 worker 仍然只发出了 `2021-01-06` 一景的 `lst_single_channel`，随后又只对这一景做 count。
  - 于是 skill 再次被补强，新增了 sidecar 排除、完整日期枚举、`len(lst_outputs) == len(valid_dates)` 才允许 count、单景不能提前 finalize。

再说真正“长新 skill”的例子：

- `task_10_10`
  - 第一轮不是执行崩，而是 router 直接判定“没有适用 skill”。
  - 这说明当前 skill 库对“单日期、按 NDVI 类别比较 LST”这类题没有显式 coverage。
  - actor 在这一轮做了真正的 `create_skill`，新建了 `landsat-single-date-ndvi-lst-class-contrast-planning`。

所以当前 `mode2` 的 skill 演化机制可以概括成：

1. router / planner 先尝试用现有 skill 接题
2. critic 把失败签名说清楚
3. actor 大多数时候做 `modify_skill`
4. 只有在 router 明显 coverage gap 时，才做 `create_skill`

到目前为止，这条 run 里 `merge_skills = 0`。所以现在更准确的说法不是“skill 正在合并演化”，而是“skill 正在修补演化，少量新增扩展 coverage”。真正的压缩和合并还没开始。

### 3. planner / parameter_worker / executor 目前各自表现如何

先说一个和早前 `mode2` 很不一样的结论：这条 `2240` run 里，`parameter_worker` 没有继续出现之前那种持续性的 `Request timed out` / network error 症状。我专门全局搜过，到目前这条 run 里没有看到那类报错继续主导失败。

但这不等于 `parameter_worker` 已经没问题了。它现在更像是从“链路不通”变成了“链路能通，但语义绑定还不够稳”。

#### planner

`planner` 目前的优点是：大方向经常是对的。

- `task_01_1` 选中了 `remote-sensing-dryness-trend-planning`，这是对的
- `task_06_6` 选中了 `landsat-lst-single-channel-trend-planning`，这是对的
- `task_07_7`、`task_09_9` 仍然都落在正确的 LST threshold-count skill 上
- `task_10_10` 第一轮没触发成功，也确实暴露出了真实的 coverage gap，而不是误判已有 skill

更关键的是，在失败任务里，`planner_reason` 经常已经写对了目标。例如：

- `task_09_9/iteration_01/env/planner_execution/step_02.json`
  - planner 理由已经是“for each valid date in the requested window”
- `task_07_7/iteration_01/env/planner_execution/step_03.json`
  - planner 理由已经是“Count days where >50% area shows LST above 315K threshold”

所以当前很多失败，并不是 planner 完全选错了任务族，而是“高层规划意图对，但没有被下游参数化成完整执行”。

#### parameter_worker

`parameter_worker` 现在的主要问题不再是连不上，而是三个语义层问题：

- 第一，完整性不够
  - `task_07_7` 里，明明文件列表已经包含整个 `2021-06` 到 `2021-09`，worker 还是在 `step_02` 发出了 `2021-05-05` 这一景：
    - `bt_path = Death Valley_2021-05-05_BT10.tif`
  - `task_09_9` 里，明明 planner 说的是“每个有效日期”，worker 还是只发出：
    - `bt_path = Chicago_2021-01-06_BT10.tif`
  - 后面 `step_03` 又都直接对单景 LST 做 count，这就是典型的“任务家族对了，参数展开不完整”。
- 第二，路径绑定意识还是不够稳定
  - `task_01_1/iteration_01/env/planner_execution/step_02.json` 里，worker 给 `compute_tvdi` 的仍然是 basename 数组，不是 full path。
  - 只是这次 runtime 的 basename -> `data_dir` 绑定修复已经生效，所以工具还能跑通并返回绝对路径。
  - 这说明 runtime 稳定性是上来了，但 worker 自己还没有完全学会把路径显式绑定正确。
- 第三，无效中间结果后的继续行为还不够守规矩
  - `task_10_10/iteration_02/env/planner_execution/step_04.json`
    - 第二次 `calculate_mean_lst_by_ndvi` 本该切到 `ndvi_threshold=0.2, mode=below`
    - 但 worker 仍然重复了第一次的 `0.7 / above`
  - 更严重的是 `task_10_10/iteration_02/env/planner_execution/step_05.json`
    - 前两次 class mean 都返回了 `NaN`
    - worker 还是硬构造了 `a=29.5, b=31.0` 去调 `difference`
  - 这已经不是小偏差，而是明显的 invalid-state 后继续编参数

所以现在看，`parameter_worker` 的真实画像是：

- 稳定性比之前好很多
- 但语义完整性、时间窗口服从性、参数切换准确性、invalid-state stop 行为仍然偏弱

#### executor / runtime

`executor` 这一侧现在最大的好消息是：之前那个系统性 path-binding 问题，确实已经被修到“基本不再是主故障源”了。

最直接的证据是：

- `task_01_1/iteration_01/env/planner_execution/step_02.json`
  - worker 传的是 basename
  - 但 `compute_tvdi` 仍然成功返回了一组 runtime 绝对路径

这说明 runtime 现在已经能把 basename 正确映射到 task data dir，再把输出落到自己的 runtime 目录。

再结合：

- `task_02_2`
- `task_03_3`
- `task_04_4`
- `task_05_5`
- `task_06_6`
- `task_08_8`

这些题能成功，说明 `executor + runtime` 这条链已经是可用的。

但 executor 也不是完全没问题。它现在的问题更像是“过于 obedient”：

- 如果上游只给了一景，它就真按一景去算
- 如果上游在 `NaN` 之后还硬传了 `29.5 / 31.0`，它也会继续执行

所以当前最该加的，不再是大修 executor 主流程，而是补少量 runtime guard：

- 多日期 count 题，如果只处理了 1 景但 discovery 明明有很多景，不应允许 finalize
- 如果上游刚拿到 `NaN`，下游不应接受凭空造出来的标量继续算

### 4. 当前系统最大的几个问题

如果把这条 `mode2` run 当前真正最需要盯住的问题按优先级压缩一下，我会列这 5 个：

- 多日期 coverage collapse
  - 年度题、季节题、月份范围题，很容易在参数展开时塌成一景
- parameter 语义漂移
  - 规划的家族是对的，但具体日期、阈值、mode、第二分支参数会漂
- path propagation 仍部分依赖 runtime 兜底
  - worker 还会给 basename，或者丢掉上一步工具真正返回的路径
- invalid intermediate 不会强制 stop
  - `NaN` 之后仍可能继续编数
- skill 边界仍有一点过宽
  - `remote-sensing-dryness-trend-planning` 现在还同时管 TVDI trend、单日期 LST threshold、多日期 LST count
  - 虽然它已经比之前稳很多，但仍然偏“大家族”

还有一个值得单独记下的现象：即便成功题，`parameter_accuracy` 也不算高。

- `task_06_6` 成功，但 `parameter_accuracy = 0.0769`
- `task_08_8` 成功，但 `parameter_accuracy = 0.25`

这说明现在的系统已经出现一种状态：

- 结果能做对一部分
- 但轨迹还不够工整
- 也就是说“可用性先于优雅性”已经出现了

### 5. 对“每个任务先并行产一个 skill，再压成 6 个 skill”的看法

我认为这个方向是对的，而且和现在这条 `mode2` 的状态是衔接得上的，但有一个前提：不要太早直接压缩。

原因很简单。当前 skill 库其实还处在“家族边界刚被修清楚”的阶段：

- `remote-sensing-dryness-trend-planning` 还在持续被拆清内部规则
- `landsat-single-date-ndvi-lst-class-contrast-planning` 甚至是刚新建出来

在这个阶段直接做 merge / compression，很容易把还没稳定的局部规则又糊回去。

所以我更建议把这个方案分成 4 步：

1. 先并行地产出单任务或窄家族 skill
   - 每个 task 先追求“把自己的规划族边界讲清楚”
   - 不急着一开始就做大而全 skill
2. 再把每条 skill 规整成结构化 signature
   - 比如：
   - `task_family`
   - `sensor_family`
   - `temporal_scope`
   - `allowed_tools`
   - 工具顺序骨架
   - 关键 guardrails
   - 常见 failure signature
3. 聚类时不要只看 embedding
   - 更好的做法是“符号特征优先，embedding 辅助”
   - 因为工具顺序、时间范围、传感器家族、输出类型这些东西是离散且高价值的信息
   - 只用文本 embedding，很容易把“都在说 LST”但实际执行结构完全不同的 skill 错聚到一起
4. 每个 cluster 再让更强的大模型做 consolidation
   - 这里 LLM 更适合做“簇内重构总结”，而不是直接决定原始聚类
   - 最后再做 replay / eval，保留表现最稳的约 6 条 skill

如果用一句话概括，我更支持的是：

- 先“并行生长”
- 再“结构化去重”
- 再“LLM 重构压缩”
- 最后“回放验证”

而不是一上来就“把所有 skill 文本直接丢进 embedding 聚类，然后让大模型总结”。

### 6. 这个设想在当前 mode2 上怎么落

结合当前 `mode2` 这 3 条 skill，我会这样看：

- `landsat-lst-single-channel-trend-planning`
  - 已经比较像一个窄家族 skill
- `landsat-single-date-ndvi-lst-class-contrast-planning`
  - 更是典型的单家族 skill
- `remote-sensing-dryness-trend-planning`
  - 反而是当前最像“未来应该先拆，再压缩”的那条 skill

也就是说，如果后面要做并行 skill 方案，一个更合理的起点其实不是“马上把现有 3 条压到更少”，而是：

- 继续让不同 task 家族各自产出更窄、更干净的 skill
- 先把 `remote-sensing-dryness-trend-planning` 这种大 skill 的内部家族拆清楚
- 等 skill 库长到十几二十条以后，再做压缩到约 6 条的尝试

否则很可能会过早把“还在修的规则”压回一个大 skill 里。

### 7. 接下来最值得继续观察的点

基于当前盘面，我觉得接下来最值得盯的不是 skill 数量，而是这三件事：

- 看 `task_11_11` 会不会引入第 4 个真正新家族
- 看 `task_07_7 / task_09_9` 这种“多日期被塌成单日期”的问题，在最新 skill 规则补完后是否还会继续复发
- 看 `task_10_10` 这种新建 skill 后的二次失败，会不会在路径传播和 `NaN` stop 规则补完后很快转正

如果这三件事都开始转好，那么下一阶段就真的可以认真推进：

- 并行单任务产 skill
- 再做高维 skill 压缩

但如果 `task_07 / 09` 这种 coverage collapse 还持续复发，那说明下一步该补的是 runtime 级别的 coverage validator，而不是继续往 skill 文本里堆规则。
