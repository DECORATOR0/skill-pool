# 2026-03-20 Skill定位与Planner导向架构观察

## 时间

- 2026-03-20

## 用户要求

- 从最新 `_isolated` 产物与“对方构建的六个优良的skills”中各抽一个 skill 做对比
- 判断对方的优良 skill 是否本质上是当前生成 skill 的高阶版本
- 将选中的两个 skill 翻译成中文并输出到各自目录
- 梳理 skill 在 `router / planner / parameter worker / executor` 中的真实作用层
- 形成一条可长期复用的架构观察：当前生成 skill 更像 executor 说明书，还是 planner 先验
- 将本轮交互中形成的重要结论沉淀到长期交互记录中

## AI执行动作

- 定位并检查最新 isolated run：
  - `D:\skills-evo\project_skills\project_skills\runs\_isolated\train20_qwen_executor_stability_20260320`
  - `D:\skills-evo\project_skills\project_skills\runs\_isolated\train20_qwen_router_executor_stability_20260320`
- 定位“协作者优良 skill 库”目录：
  - `D:\skills-evo\project_skills\项目文档\参考技能库\协作者优良skill库`
- 抽样对比的 skill：
  - 当前 executor-stability 版本窄 skill：
    - `D:\skills-evo\project_skills\project_skills\runs\_isolated\train20_qwen_executor_stability_20260320\skill_library\single-date-landsat-lst-threshold-area\SKILL.md`
  - 对方优良 skill：
    - `D:\skills-evo\project_skills\项目文档\参考技能库\协作者优良skill库\earth-spectrum-thermal-retrieval\SKILL.md`
- 将上述两个 skill 翻译成中文并输出到同目录：
  - `D:\skills-evo\project_skills\project_skills\runs\_isolated\train20_qwen_executor_stability_20260320\skill_library\single-date-landsat-lst-threshold-area\SKILL.zh-CN.md`
  - `D:\skills-evo\project_skills\项目文档\参考技能库\协作者优良skill库\earth-spectrum-thermal-retrieval\SKILL.zh-CN.md`
- 检查当前 `nlrl_skills` 运行时链路：
  - `router.py`
  - `environment.py`
  - `agent_loop.py`
  - `skills.py`
  - `prompts/executor_user.md`
- 检查 `skill_eval` 风格链路：
  - `skill_router.py`
  - `skill_llm_planner.py`
  - `parameter_worker.py`
  - `executor.py`
  - `prompt_builder.py`
- 对 6 个优良 skill 的 `Family Rules / Stepwise Execution Pattern / Parameter Selection Policy / Stop Conditions` 做了并排分析

## 关键样本结论

- 当前生成的 isolated skill，哪怕已经开始从单题模板合并成多题族 skill，本质上仍更像 `executor guide`
- 对方的优良 skill 本质上不是给 executor 直接照着跑的细说明，而是给 planner 的高层规划先验
- 因此两边 skill 的“抽象层级”不能只用文字宽窄比较，更要看它接入系统的哪一层

更准确的说法：

- 当前框架中生成的 skill：主要面向 executor，直接影响“下一步调用什么工具、默认参数怎么填、什么时候停”
- 对方优良 skill：主要面向 planner，影响“应当选择哪类工具链、宏观顺序怎么排、什么家族工具不该混用”

## 当前架构与对方架构的区别

### 1. 当前 `nlrl_skills` 架构

当前执行链更接近：

`task -> router -> 选中 skill -> 把整份 SKILL.md 注入 executor -> executor 在循环中自己决定工具、参数和停止条件`

关键点：

- `router` 只看 skill header，不看 skill 正文
- 被选中的整份 `SKILL.md` 正文会直接放进 executor prompt
- 同一个 executor 同时承担：
  - 选工具
  - 填参数
  - 决定何时停止

因此，当前 skill 的系统角色主要是：

- 给 executor 提供执行说明
- 收窄可用工具范围
- 降低弱模型在执行时的漂移

### 2. `skill_eval` 风格架构

更接近：

`task -> router -> planner -> parameter worker -> executor -> answer selector`

关键点：

- skill 先作为 planner 的 prior 使用，而不是直接作为 executor 全文说明书
- planner 先产出完整的 `tool_sequence`
- parameter worker 不是一次性决定整条链参数，而是逐步只决定当前这一步工具的参数
- executor 只负责执行当前工具
- observation 会回流给后续参数生成，但不会自动重写整个工具链

因此，对方 skill 的系统角色主要是：

- 为 planner 划工具家族范围
- 提供工具链宏观排序规则
- 提供典型任务家族的分支选择规则
- 约束 parameter worker 和 final answer 阶段的职责边界

## 对“六个优良 skill”的进一步判断

这 6 个 skill 整体都偏 planner-facing，而不是 executor-facing。

但内部也有轻微差异：

- 更明显属于粗粒度 planner prior 的：
  - `earth-spectrum-thermal-retrieval`
  - `earth-spectrum-drought-stress`
  - `earth-product-timeseries`
  - `earth-rgb-perception-change`
- 更像 planner 可消费的宏观模板、仍带一点“高阶固定链”味道的：
  - `earth-product-derived-index-change`
  - `earth-product-raster-arithmetic`

所以它们不是完全同质，但整体上都已经脱离了“给 executor 写一步一步说明”的范式。

## 本轮最重要的长期观察

### 观察 1：比较合理的 skill 模式，至少有一条明确方向是“面向 planner”

当前一个重要启发是：

- skill 不一定非要直接规定 executor 怎么调用工具
- 更合理的一种模式，是让 skill 主要去约束 planner：
  - 该题属于哪个工具家族
  - 哪些工具优先
  - 哪些工具不要混用
  - 工具链宏观顺序怎么排

这个观察对后续架构设计很重要，因为它说明“skill 的作用层”本身就是可设计变量，而不是固定只能写执行说明书。

### 观察 2：当前框架后续值得并行尝试两条路线

后续可以考虑同时尝试两种 skill 生成方向：

1. 工具链 / 高阶工具链导向的 skill
   - 继续面向 executor
   - 强调默认流程、路径规则、工具使用约束、脚本调用时机

2. planner 导向的高阶 skill
   - 不直接给 executor 写细执行说明
   - 重点写 `Tool Scope / Family Rules / Stepwise Execution Pattern / Stop Conditions`
   - 让 skill 变成 planner 的规划先验和结构性约束

这两条路线都值得试，因为它们对应不同的稳定性和泛化方式。

### 观察 3：planner-oriented skill 也不是没有问题

planner-oriented skill 的问题在于：

- planner 先生成了一条工具链
- parameter worker 之后只能逐步修参数
- 如果中途才发现高层工具家族一开始就选错了，后面很可能来不及撤回

因此它的优点是：

- 高层结构更稳
- 低层参数更不容易乱猜
- 更适合 benchmark 中套路相对稳定的问题

但它的潜在风险是：

- 工具链一旦先验错误，中途恢复能力弱
- 对多分支、文件模式复杂、需要中途改策略的问题更脆弱
- 如果 `router / planner / parameter worker` 都换成小模型，这种脆弱性可能会更明显

## 三种 skill / 执行范式的对比观察

本轮最终沉淀出的一个重要结论，是需要把以下三种范式分开看：

### A. 直接指定工具链的 skill

形态：

- skill 直接告诉 executor 该按什么链条做

优点：

- 稳
- 容易控
- 对固定题族有效

缺点：

- 窄
- 容易死板
- 泛化弱

### B. 通过 planner 提示词与约束间接指定工具链的 skill

形态：

- skill 不直接写死 executor 行为
- 而是给 planner 一个高层约束，让 planner 为当前题目动态生成工具链

优点：

- 家族级泛化更好
- skill 的复用价值更高
- skill 不必退化为具体模板

缺点：

- 如果 planner 高层判断错，parameter worker 往往救不回来
- 工具链刚性更强
- 没有 replan 机制时会显得脆弱

### C. 边执行边找工具的 ReAct 风格

形态：

- 每一步都根据当前 observation 再决定是否换工具

优点：

- 灵活
- 适合中途变化大、初始难以判断的任务

缺点：

- 更容易漂移
- 更容易在工具调用上不稳定
- 对弱模型更不友好

### 初步结论

这三种方式并不是谁绝对更强，而是适合的 benchmark 范围不同：

- A 更适合模式固定、题族窄的场景
- B 更适合 benchmark 家族清楚、但需要家族级泛化的场景
- C 更适合中途分支多、需要在线纠偏的场景

这一点和 ReAct / 直接规划 / 分层规划之间的适应范围差异有关，后续可以作为重要实验轴。

## 对当前项目的直接启发

- 不要再把“skill 是否高阶”仅理解为“文本写得更宽泛”
- 更重要的是：skill 作用于哪一层
  - 作用于 executor
  - 作用于 planner
  - 作用于 parameter worker 的参数生成约束
- 当前项目后续可以把 skill 设计空间拆成两个正交维度：
  - 抽象层级：窄模板 / 高阶工具链 / 家族级 prior
  - 系统接入层：executor / planner / planner+worker

这比单纯继续把 executor-oriented skill 写得更宽，更值得系统化验证。

## 后续维护要求

- 后续若继续讨论 skill 设计，优先沿着以下两条实验线记录：
  - executor-oriented skill 的继续泛化
  - planner-oriented skill prior 的最小可行接入
- 如果后续真的实现 planner-oriented 路线，需要额外记录：
  - planner 是否可见 file list / data_dir / shortlist / profile
  - parameter worker 是否允许局部 replan
  - 是否需要从“固定 plan + stepwise args”升级到“固定 plan + stepwise args + failure-triggered replanning”
- 若后续继续讨论 ReAct、分层规划、固定链模板三者的适用边界，应统一把它们作为三类范式来比较，而不是混在“skill 是否高阶”一个维度里讨论

## 补充澄清：关于 mode2 的真实实现边界

### 1. 最新澄清

用户补充说明的重点不是“只靠当前 prompt 就要复刻出那 6 个优良 skill”。

真实意思是：

- 如果后续要尝试构建 `mode2`
- 那么它需要的依赖本来就不只是 prompt 依赖
- 还包括 workflow 依赖和必要的架构接入
- 这一点是默认成立的，不需要再假设成“只改 prompt、不改系统”

因此，后续给其他 AI 下发实现任务时，应明确写清：

- `mode2` 可以也应该包含必要的并行架构改造
- 不应被偷换成“planner 风格措辞 + 仍然注入 executor”的假 mode2

### 2. 当前对 mode2 可行性的更准确判断

更准确的判断应写成两层：

1. 从“skill 文本生成”角度看：
   - 通过新建一套 `mode2` actor prompts，并结合跨任务 `create / modify / merge` 迭代
   - 当前框架有可能逐步生成 planner-oriented 风格的 skill 文本

2. 从“系统真实消费这些 skill”角度看：
   - 如果运行时仍然把 skill 全文直接注入 executor
   - 那么这些 planner-oriented 文本即使生成出来，也无法真正按对方范式发挥作用

所以后续实验应把两件事一起做：

- 生成 planner-oriented skill
- 让运行时也以 planner-oriented 的方式消费这些 skill

### 3. 为什么这条澄清重要

如果不把这点说清，后续实验很容易变成：

- 文本看上去更高阶了
- 但系统接入层完全没变
- 最终只是把“高阶 planner 提示词”塞进 executor

这样会把“skill 文本风格变化”和“skill 真实系统角色变化”混为一谈，导致实验结论不干净。

## 补充澄清：当前 actor 是否支持 skill 合并

结论：支持，而且是代码层面已经存在的正式动作，不是概念上的支持。

### 1. 当前 merge 的真实机制

当前 `nlrl_skills` 中已经有独立的 `merge_skills` 分支：

- `D:\skills-evo\project_skills\project_skills\nlrl_skills\actor.py`
- `D:\skills-evo\project_skills\project_skills\prompts\actor_merge_skill.md`

实际流程是：

- actor 读取待合并 skill 的 `header / body / resources`
- 调用 `actor_merge_skill.md`
- 产出新的 merged skill
- 写入新的 skill 目录
- 删除旧 skill 目录

因此它不是“只能改写一个 skill，不能合并两个 skill”，而是已经有真实 merge 能力。

### 2. 当前 merge 的限制

虽然支持 merge，但有三个需要注意的限制：

- 自动强制 merge 的条件是 `skill_count > skill_count_limit`，不是 `>=`
- 也就是说 skill 数量正好达到上限时，不会自动先压缩
- 如果 critic 没提供明确的 `merge_candidates`，当前兜底策略会直接取前两个 skill 作为候选，这个策略比较粗糙

因此后续如果要认真跑“双模式上限 6 个 skill”的实验，需要注意：

- 当前代码不是“满了就先合并再创建”
- 而更像“超了以后再压缩”

### 3. 对后续实验设计的意义

这意味着后续在比较 `mode1 / mode2` 时，至少要区分两件事：

- skill 生成范式本身的差异
- skill 池压缩与 merge 触发策略带来的差异

否则有可能把“merge 触发时机”造成的效果差异，误判成“mode1 / mode2 skill 质量差异”。

## 本次新增产物

- 已新增一份可直接发给其他 AI 的实现提示词文档：
  - `D:\skills-evo\project_skills\项目文档\历史说明\2026-03-20_双模式Skill实验代码构建任务提示词.md`

该文档的定位是：

- 只要求对方 AI 构建代码、prompt、config 和两个运行脚本
- 不要求它实际启动训练或评估
- 明确要求 mode2 必须在必要时进行最小架构改造，而不是伪装成 prompt-only 改造
