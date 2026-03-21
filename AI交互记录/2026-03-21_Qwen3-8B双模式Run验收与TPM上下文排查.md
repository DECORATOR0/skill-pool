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
