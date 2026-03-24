# 2026-03-21 Qwen3-8B 付费 Thinking-On 1153 双模式错误观察与 Mode2 链路分析

## 记录范围

这份记录对应新的 `1153` 实验，不是前一份 `0001` run 验收记录。

- `mode1`:
  - `project_skills/runs/dualmode_mode1/20260321_1153_qwen3_8b_paid_thinkingon_dualmode_mode1_train`
- `mode2`:
  - `project_skills/runs/dualmode_mode2/20260321_1153_qwen3_8b_paid_thinkingon_dualmode_mode2_train`

旧记录仍保留在：

- `AI交互记录/2026-03-21_Qwen3-8B双模式Run验收与TPM上下文排查.md`

这份新记录只关注：

1. 当前 `1153` 这两个 run 已落盘任务的错误快照
2. `mode1` / `mode2` 错误类型对比
3. `mode2` 真实执行链路
4. `mode2` 当前到底卡在哪一层

## 当前快照

截至 `2026-03-21 18:57`（`mode1` 盘面）/ `2026-03-21 18:53`（`mode2` 盘面）这次扫描时：

- 两个后台 Python 进程仍在运行：
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

### 和上一版局部快照相比

上一版这份记录只覆盖到：

- `mode1`: `19` 个任务，成功 `6`，失败 `13`
- `mode2`: `8` 个任务，成功 `1`，失败 `7`

扩大到当前样本后：

- `mode1` 新增完成了 `16` 个任务，其中成功 `10`、失败 `6`
- `mode1` 成功率从 `31.6% (6/19)` 升到 `45.7% (16/35)`
- `mode2` 新增完成了 `6` 个任务，但 `6` 个全部失败
- `mode2` 成功率从 `12.5% (1/8)` 降到 `7.1% (1/14)`

### 这轮扩大样本后的主判断

- 当前仍然没有看到这一批 `1153` run 以显式 `TPM` 作为主导错误签名。
- `mode1` 不是“整体坏掉”，而是扩大样本后出现了后段回升，说明 executor-skill 盘面确实在变得更能解题。
- `mode2` 则相反：样本扩大后没有出现新拐点，反而把“卡死在参数生成链”这个判断坐实了。

## Mode1 错误观察

`mode1` 现在已经不是只看前 `19` 题就能概括。放大到 `35` 个已完成任务后，失败可以更完整地分成 `5` 类。

### 1. JSON / 结构化输出损坏: 5 个

对应任务：

- `task_01_1`
- `task_06_6`
- `task_15_15`
- `task_17_17`
- `task_18_18`

典型报错：

- `Expecting ',' delimiter`
- `Unterminated string`

含义：

- 模型不是完全没输出
- 而是输出在 JSON 层被截断、拼坏或闭合失败
- 系统因此无法继续解析

代表文件：

- `...mode1.../task_01_1/task_summary.json`
- `...mode1.../task_15_15/task_summary.json`

### 2. skill / YAML 产物损坏: 2 个

对应任务：

- `task_11_11`
- `task_16_16`

典型报错：

- `mapping values are not allowed here`

含义：

- 问题不在执行器算错
- 而是中间生成出来的 skill artifact 本身格式非法
- 后面解析 skill 时直接炸掉

代表文件：

- `...mode1.../task_11_11/task_summary.json`
- `...mode1.../task_16_16/task_summary.json`

### 3. 单次调用层面的模型 / 平台硬失败: 3 个

对应任务：

- `task_13_13`
- `task_14_14`
- `task_32_32`

典型报错：

- `Range of input length should be [1, 98304]`
- `Empty model response; expected JSON object.`
- `data_inspection_failed`

含义：

- 这类问题不是 skill 工作流本身推理错了，而是单次模型调用直接被硬限制、空响应或平台内容检查打断。
- 其中：
  - `task_13_13` 是单次请求长度硬上限
  - `task_14_14` 是空模型响应
  - `task_32_32` 是平台侧 `data_inspection_failed`
- 它们都不是 `TPM`，也不是“任务逻辑已经正确只是差最后一步”。

代表文件：

- `...mode1.../task_13_13/task_summary.json`
- `...mode1.../task_14_14/task_summary.json`
- `...mode1.../task_32_32/task_summary.json`

### 4. 多时相 / 年度工作流与 tool contract 错误: 5 个

对应任务：

- `task_09_9`
- `task_12_12`
- `task_19_19`
- `task_20_20`
- `task_34_34`

这一类不是“格式炸了”，而是 skill 已经跑起来，但多时相聚合、返回路径沿用、年度统计收口这些规则没真正落地。

代表情况：

- `task_09_9`
  - 路由基本对
  - 但执行没走到最后聚合和最终答案
- `task_12_12`
  - 多通道 / 工具契约分支走错，出现假 blocker
- `task_19_19`
  - MODIS peak/max 任务没有真正走到 `max` 聚合
  - 还混入了脆弱 helper-script / path 处理
- `task_20_20`
  - 全年 PWV spike 任务没有处理完整时间序列，还丢了工具返回路径
- `task_34_34`
  - 年度 split-window LST 比较没有稳定走完批量处理、年度聚合和最终比较

### 5. 单景阈值 / TES / 掩膜分支指令错误: 4 个

对应任务：

- `task_10_10`
- `task_23_23`
- `task_25_25`
- `task_28_28`

共同点：

- 这些任务往往已经路由到大致正确的 skill 家族
- 但 skill 内部的分支规则仍写得不够硬
- 于是 executor 会在 TES 输出路径、ASTER band 索引、AOI / 掩膜支持边界、阈值算子限制这些地方走错

代表情况：

- `task_10_10`
  - 把 “按 NDVI 分组比较 LST 均值” 的异常双 NaN 分支处理成了无效重试
- `task_23_23`
  - ASTER / TES 分支的输出路径和 band-index 规则不稳
- `task_25_25`
  - TES 分支仍在路径复用和 schema 理解上出错
- `task_28_28`
  - skill 没有把 AOI/masking 缺口和条件均值工具的阈值算子限制写清楚

### 扩大样本后的 mode1 新判断

- `mode1` 仍有格式脆弱性，但现在已经不能再简单概括成“总是 JSON 坏掉”。
- 新增样本里更显眼的是：多时相聚合、returned-path、TES 分支和年度统计这些 workflow/tool-contract 问题。
- 同时，后半段新增 `16` 个已完成任务里成功了 `10` 个，这说明 actor/critic 驱动下的 executor skill 库并不是在空转，而是在缓慢变稳。

## Mode2 错误观察

`mode2` 的扩大样本没有把图景变复杂，反而把主瓶颈压得更清楚了。

### 结论先说

当前 `mode2` 已失败的 `13` 个任务里：

- `13/13` 的最新 `planner_execution/step_01.json` 都能看到 `parameter-worker network error ... Request timed out.`
- `13/13` 的对应 `step_01.json` 里都落了 `arguments: {}`
- 新增的后半段任务 `task_09_9` 到 `task_14_14` 也全部延续这一签名
- 当前只有 `task_07_7` 一个成功样本，看不到“越跑越稳”的后段趋势

但这里最重要的判断是：

- `arguments: {}` 不是充分证据说明 planner 主动决定传空参
- 它更像是参数生成失败后 runtime 写下的占位结果

### 当前 mode2 主导故障

对应失败任务：

- `task_01_1`
- `task_02_2`
- `task_03_3`
- `task_04_4`
- `task_05_5`
- `task_06_6`
- `task_08_8`
- `task_09_9`
- `task_10_10`
- `task_11_11`
- `task_12_12`
- `task_13_13`
- `task_14_14`

共同特征：

1. planner 已经给出了 planned tool
2. 常见 planned tool 就是 `get_filelist`
3. prompt 里已经有数据目录信息，例如 `benchmark/data/questionX`
4. 但参数生成阶段超时
5. 于是日志里留下 `arguments: {}`
6. 工具执行在这一步就停了
7. 即使 actor / critic 在后段继续修改 planning skill，下一题也经常死在同一处

代表文件：

- `...mode2.../task_01_1/iteration_04/env/planner_execution/step_01.json`
- `...mode2.../task_09_9/iteration_04/env/planner_execution/step_01.json`
- `...mode2.../task_11_11/iteration_01/env/planner_execution/step_01.json`
- `...mode2.../task_14_14/iteration_04/env/planner_execution/step_01.json`

典型错误：

- `parameter-worker network error after 5 primary retries and one backup attempt ... Request timed out.`

### `task_11_11` 是叠加故障，不是反例

- `task_11_11` 的 `task_summary.json` 最后还叠加了一层 `mapping values are not allowed here`
- 但它最新可见的 `planner_execution/step_01.json` 仍然带着同一条 `parameter-worker network error`
- 这说明 `mode2` 不只是可能有 actor 产物格式脆弱性，而是“主故障仍在参数生成链，个别任务还会再叠加 skill 产物损坏”

### 冷启动 skill 缺口不是当前主导终态

有些任务早期 iteration 的确出现过：

- `No applicable skill`

但这只能说明首轮冷启动时 skill 库还没长出来。

不能把它当成当前这批任务最终一直失败的主因。

因为后面真正把任务压死的，是参数生成链路 timeout，而不是 skill 永久缺失。

## Skill 维护盘面

扩大样本后，`mode1` 和 `mode2` 的 actor / critic 维护行为差异也更清楚了。

- `mode1`
  - 在当前 `35` 个已完成任务里，actor 共执行了 `9` 次 `create_skill`、`48` 次 `modify_skill`、`3` 次 `merge_skills`
  - 当前 `skill_library` 最终收敛为 `6` 个 executor skill
  - 这说明 `mode1` 不只是不断喷新 skill，而是已经出现压缩和整合
- `mode2`
  - 在当前 `14` 个已完成任务里，actor 共执行了 `6` 次 `create_skill`、`45` 次 `modify_skill`
  - 当前 `skill_library` 也是 `6` 个 planning skill，但没有看到 merge
  - 这更像是反复补 planner 提示，而不是通过真实执行反馈逐步收敛 workflow
- experience buffer 当前行数：
  - `mode1`: `60`
  - `mode2`: `53`

这组盘面说明：

- `mode2` 不是 actor / critic 完全没干活
- 问题在于它大量卡死在 `parameter-worker` 之前，拿不到足够丰富的真实工具执行证据
- 所以改 skill 的动作很多，但收益远不如 `mode1`

## Mode2 到底是什么链路

你现在关心的点是对的：`mode2` 不是一个自由发挥的 executor 一把梭系统，它其实是分层的。

按当前代码，`mode2` 一轮里更接近下面这条链：

1. `router`
   - 先选 active skill
2. `planner`
   - 根据题目 + skill + allowed tools，输出一个 planned tool sequence
3. `parameter-worker`
   - 对 planner 已经选好的下一步工具，单独补参数
4. `toolbox.execute`
   - 参数补出来后，直接执行真实工具
5. `planner_answer_selector`
   - 看执行轨迹，生成最终答案
6. 迭代结束后才进入 actor / critic
   - 用于修改 skill、总结经验，进入下一轮 iteration

所以关键点是：

- 在当前 `mode2` 里，planner 后面不是再交给一个自由 executor LLM 去“边想边做”
- 而是先走 `parameter-worker`
- 参数成功后，工具就直接真执行了

如果你口中的 “barometer” 指的是最后那个根据执行结果收口答案的环节，那在当前代码里更接近：

- `planner_answer_selector`

而 actor / critic 是 iteration 末尾的反思层，不是单步执行层。

## Mode2 具体卡在哪里

### 不是主要卡在 planner 选错工具链

当然，早期有些 iteration 的确存在 skill 还不对、路由还不稳的问题。

但这不是当前这批失败任务的主导终态。

当前更核心的是：

- planner 已经给出工具名了
- 但参数还没落地，系统就死在 `parameter-worker`

### 代码侧证据

`nlrl_skills/planner_runtime.py` 里，执行 planned step 的逻辑是：

1. 先调用 `choose_tool_arguments(...)`
2. 成功了才会 `self.toolbox.execute(...)`
3. 如果中间异常：
   - `decision = None`
   - `arguments = {}`
   - `success = False`
   - 然后 `break`

也就是说：

- 当你在 `step_01.json` 里看到 `arguments: {}` 时
- 很可能不是 planner 真把空字典当成参数
- 而是 `choose_tool_arguments` 抛异常后，runtime 用空字典作为失败占位

这就是为什么不能把 `{}` 直接解读成“planner 不会填参数”。

更精确的说法是：

- planner 只负责决定“下一步用哪个工具”
- 真正把 `dir_path`、`ndvi_path`、`lst_path` 这些参数补出来的是 `parameter-worker`
- 当前主要是这层超时了

### 更细一点的机制判断

`planner_runtime.py` 还明确把 `task.data_dir` 传进了 planner/worker prompt。

也就是说当前系统并不是“拿不到目录信息”。

实际问题更像是：

1. 数据目录信息明明在 prompt 里
2. 但 `parameter-worker` 这次请求没稳定返回
3. runtime 没有对显而易见参数做 deterministic fallback
4. 所以直接 fail-close，记成 `arguments: {}`
5. 由于第一步工具都没真正执行，后面 answer selector 也没有实质依据

## 对 mode2 的最准判断

所以当前 `mode2` 的主问题不是一句“planner 不会做题”就能概括。

更准确地拆开，是三层：

### 第一层：planner / skill 提示仍然不够硬

- 虽然 prompt 里有 `data_dir`
- 但 skill 没有把“`get_filelist` 第一步必须显式绑定 `dir_path`”写成足够强的硬约束

### 第二层：parameter-worker 服务链路不稳

- 这是当前最直接的卡点
- 一超时，整个 step 就停

### 第三层：runtime 没有明显参数的兜底

例如：

- 对 `get_filelist`
- 当上下文里明明已有 `benchmark/data/questionX`
- 其实是可以做 deterministic fallback 的

但现在没有。

因此当前 mode2 的真实故障句子应该写成：

> planner 已选出工具，但 parameter-worker 在参数落地阶段高频超时；runtime 将失败记为 `arguments: {}` 并中止执行，因此大量任务根本还没进入真实工具执行。

## 为什么这和 mode1 不一样

`mode1` 更像：

- executor 真跑起来了
- 然后在输出格式、路径传递、聚合规则、技能抽象上出错

`mode2` 更像：

- planner 先想出要做什么
- 但很多任务在第一步参数化时就没成功跨过去
- 所以后面真实执行信息非常少

这也解释了为什么：

- `mode1` 的错误看起来五花八门
- `mode2` 的错误看起来总是围绕 `step_01.json`、`arguments: {}`、`parameter-worker timeout`

## 这批观察的直接行动建议

如果后面要修 `mode2`，优先级应该是：

1. 给 `parameter-worker` 先做稳定性修复
   - timeout
   - retry
   - backup endpoint
2. 给明显参数做 deterministic fallback
   - 尤其是 `get_filelist.dir_path`
3. 在 planner skill 里把参数绑定规则写硬
   - 例如看到 `task_context.data_dir` 就必须显式带上
4. 再去看 planner 选错 skill / skill 冷启动

因为当前很多任务甚至还没走到“工具真实执行”那一步。

## 本次记录对应的代表性文件

### 运行结果

- `project_skills/runs/dualmode_mode1/20260321_1153_qwen3_8b_paid_thinkingon_dualmode_mode1_train`
- `project_skills/runs/dualmode_mode2/20260321_1153_qwen3_8b_paid_thinkingon_dualmode_mode2_train`

### Mode1 代表错误

- `...mode1.../task_11_11/task_summary.json`
- `...mode1.../task_20_20/task_summary.json`
- `...mode1.../task_25_25/task_summary.json`
- `...mode1.../task_32_32/task_summary.json`
- `...mode1.../task_34_34/task_summary.json`

### Mode2 代表错误

- `...mode2.../task_09_9/task_summary.json`
- `...mode2.../task_11_11/task_summary.json`
- `...mode2.../task_14_14/task_summary.json`
- `...mode2.../task_09_9/iteration_04/env/planner_execution/step_01.json`
- `...mode2.../task_11_11/iteration_01/env/planner_execution/step_01.json`
- `...mode2.../task_14_14/iteration_04/env/planner_execution/step_01.json`

### 代码侧依据

- `project_skills/nlrl_skills/planner_runtime.py`
- `project_skills/agent/skill_eval/executor.py`
- `project_skills/agent/skill_eval/parameter_worker.py`

## 追加纠偏：为什么说 mode2 的“前面服务”会不稳

这里专门纠正一个很容易误判的点。

如果只看抽象角色名字，你会觉得：

- planner 是一个模型
- 后面执行也是一个模型
- 那应该就是同一个服务前后串起来

但当前代码里不是这样接的。

### 1. planner 和 answer selector 走的是 run 配置里的 executor 通道

在 `project_skills/nlrl_skills/planner_runtime.py` 里：

- `planner_llm = OpenAICompatibleLLM(config.executor)`
- `answer_selector_llm = OpenAICompatibleLLM(config.executor)`

这说明：

- planner
- planner_answer_selector

都走当前 run 的 `config.executor` 那条 paid `qwen3-8b` 通道。

### 2. 但 parameter-worker 不是这条通道

同一个 `planner_runtime.py` 在执行 planned step 时，会调用：

- `project_skills.agent.skill_eval.parameter_worker.choose_tool_arguments(...)`

而这个 `parameter_worker.py` 又不是从当前 run 的 `config.executor` 读配置。

它直接读 `project_skills/agent/skill_eval/config.py` 里的独立参数：

- `PARAMETER_MODEL_NAME = "Qwen3-8B-RL"`
- `PARAMETER_MODEL_BASE_URL = "http://192.168.10.70:8005/v1/"`
- `PARAMETER_MODEL_BACKUP_URL = "http://192.168.10.70:8005/v1/"`

也就是说，当前 `1153 paid thinking-on` 里实际是两条不同的 LLM 通道：

1. planner / answer selector:
   - paid `qwen3-8b`
   - 外部 endpoint
2. parameter-worker:
   - 本地 `Qwen3-8B-RL`
   - `192.168.10.70:8005`

### 3. 所以“前面服务不稳”不是牵强说法

当前 mode2 里完全可能发生：

1. planner 正常返回工具链
2. parameter-worker 这条独立通道超时
3. 参数没有补出来
4. runtime 把失败记成 `decision=None`
5. 最后在日志里落成 `arguments: {}`
6. 工具根本还没真正执行

所以这里不是“同一个 paid qwen3-8b 前半段和后半段自己打架”。

而是：

- 你已经把 planner / answer selector 层切到 paid `qwen3-8b`
- 但 parameter-worker 还留在旧的本地 `Qwen3-8B-RL` 通道上

这正好和当前日志里的报错一致：

- `parameter-worker network error ...`
- `model=Qwen3-8B-RL`
- `backup_base_url=http://192.168.10.70:8005/v1/`

### 4. 这条纠偏对当前诊断的影响

所以现在对 mode2 的最准描述应该是：

- 不是 planner 自己稳定、executor 自己不稳定
- 也不是 paid `qwen3-8b` 同一条链路里前半段和后半段矛盾
- 而是 planner 已经切到 paid 通道，但参数补全层还没切

因此当前 mode2 的主故障依然是：

- parameter-worker 独立服务超时
- runtime 缺少显而易见参数的 deterministic fallback
- 导致大量任务停在真实工具执行之前
