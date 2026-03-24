# 2026-03-21 论文摘记 Memento-Skills

## 基本信息

- 论文：`Memento-Skills: Let Agents Design Agents`
- arXiv：https://arxiv.org/abs/2603.18743
- PDF：`Memento-Skills_Let_Agents_Design_Agents_arXiv_2603.18743.pdf`
- 代码仓库：论文中给出 `https://github.com/Memento-Teams/Memento-Skills`

## 一句话概括

这篇论文最核心的想法不是“再写一个 agent”，而是把 `skill` 直接当成可写、可进化、可路由的外部长期记忆，让 frozen LLM 通过不断 `读 skill -> 执行 -> 反思 -> 改 skill` 来持续学习，而不是更新模型参数。

## 它到底做了什么

作者把系统拆成一个闭环：

1. `Observe`
   - 接收当前任务
2. `Read`
   - 从 skill 库里路由到最相关的 skill
   - 如果没有合适 skill，可直接新建
3. `Act`
   - 在当前 skill 约束下执行任务
4. `Feedback`
   - judge 判断对错
5. `Write`
   - 成功则更新 utility
   - 失败则做 skill 级归因、修补，必要时发现新 skill

论文里非常强调一点：

- 这里的 memory 不是原始轨迹日志
- memory 的单位是 `skill folder`
- 一个 skill 不是一段文字，而是一组 artefact：
  - `SKILL.md`
  - prompts
  - helper scripts / code

也就是说，它把“经验”压缩成可执行、可复用、可改写的程序性记忆。

## 我认为它最有价值的 5 个点

### 1. 把 `skill` 明确提升成 memory 的基本单位

这点对你特别重要。

你现在也在想：

- skill 是不是不该只是 prompt 文本
- 失败后到底该保留什么
- 正式库和失败池怎么分层

这篇论文给出的答案很直接：

- 不要把长期记忆主要建在“自然语言总结”上
- 直接把 `skill folder` 当 memory cell
- 让 memory 自己成为未来执行的政策载体

这和你现在的方向很接近，但它比“经验缓冲 + skill 文本”更激进，因为它让 skill 本身承担长期学习主体。

### 2. `read` 和 `write` 不是辅助动作，而是学习主循环

它把：

- `read` 看成 policy improvement
- `write` 看成 policy evaluation + policy improvement

这个视角很有价值，因为它把很多工程动作统一了：

- 路由不是检索小功能，而是策略选择
- 修改 skill 不是打补丁，而是在改 policy
- skill 库增长不是堆资料，而是在扩展可控策略空间

如果你接受这个视角，你后面设计 `mode2 / model3` 的时候，很多问题就会变得更清楚：

- 到底什么算一次真正学习
- 什么算只是记录
- 什么算正式可部署 policy

### 3. 它做了 skill 级 failure attribution

论文里有一个很关键但很容易被忽略的机制：

- 失败后不是直接模糊反思
- 而是先找“哪一个 skill 最应该为这次失败负责”

这其实是在做 `credit assignment`。

对你现在的系统很有启发，因为你后面如果走：

- 并行产出 candidate skill
- 再做统一压缩

那么最难的问题之一就是：

- 失败经验应该写回哪个 skill
- 如果一个失败跨了 planner / worker / executor，责任怎么分

Memento-Skills 至少给了一个明确方向：

- 先做 skill 级归因
- 再决定是局部修补还是新增 skill

### 4. 它区分了“修补现有 skill”和“发现新 skill”

论文的 write 不是单一动作，而是两条分支：

- 如果某个 skill 还有价值，就原地优化
- 如果 utility 低到一定阈值，而且样本数足够，就升级成 `DiscoverSkill`

这个判断很贴你现在想做的“正式库 / 候选池 / 失败模式池”三层。

你完全可以借它的思想，改成自己的版本：

- 高频成功但有局部失误：修补
- 多次失败但失败模式稳定：升成“待重构候选”
- 长时间不稳且无迁移价值：降级成 failure pattern，不再给正式库资格

也就是说，它的好思路不一定是具体阈值，而是：

- `修补`
- `重构`
- `新建`

这三类动作要显式分开，不要都塞进一个 modify。

### 5. 它的 router 目标不是语义相似，而是行为相似

这是这篇论文另一个非常值得你注意的点。

作者明确说：

- BM25 不够
- 普通 embedding 相似度也不够
- 因为那些只捕捉“说得像不像”
- 但真正重要的是“执行这个 skill 后行为会不会对”

所以他们把 router 训练成偏 `behavioural utility` 的检索器。

这对你后面的启发很大，因为你现在也在担心：

- skill 文本长短
- planner-oriented 和 executor-oriented 的表述差异
- merge 后 router 会不会命中一个“看起来很像但其实不好用”的 skill

这篇论文的回答是：

- 路由目标不要只建在文本相似上
- 要尽量引入执行成败信号

## 实验里最值得记住的结论

### 1. 不是所有 benchmark 都适合同样的 skill transfer

它在 GAIA 上有提升，但作者明确说：

- GAIA 题目太杂
- 训练中学到的 skill 很多在测试时根本不会被触发

而在 HLE 上，提升更大，因为：

- 题目按学科分布
- domain structure 更稳定
- 一个 Biology skill 更可能迁移到另一个 Biology 题

这点对你特别重要，因为它等于在提醒你：

- skill 学习值不值得做
- 很大程度取决于任务空间有没有稳定 family 结构

也就是你后面别只看总准确率，还要看：

- 你的任务集到底有多少“可迁移家族”
- candidate skill 是不是在家族内部复用，而不是只对单题有效

### 2. skill 库会长，而且长到一定程度后收益递减

论文里从 5 个 atomic skills 出发：

- GAIA 学到 41 个 skills
- HLE 学到 235 个 skills

作者的解释是：

- 一部分收益来自旧 skill 被修补后覆盖更宽
- 另一部分收益来自新 skill 把原来没覆盖的空洞补上

随着 skill 空间变密，后面自然会出现收益递减。

这和你现在的“先并行生长，再后置压缩”其实是同方向的。

换句话说，这篇论文虽然没有直接讲你那套 `model3`，但它实际上支持一个判断：

- skill 库在中前期本来就应该允许先长
- 太早压缩，可能会把还没形成稳定 coverage 的结构压掉

## 和你当前设想最像的地方

### 1. 都强调不要一开始就把所有学习写进模型参数

你和它都更偏向：

- 先在外部结构上学
- 让 skill / memory 成为主要可塑层

### 2. 都默认 skill 需要长期演化

不是一次生成完就结束，而是：

- 路由
- 失败
- 修补
- 扩库

### 3. 都隐含支持“先长，再想压缩”

论文没有把压缩写成主贡献，但从它的实验盘面看，明显更重视：

- 先把 coverage 长出来
- 再讨论库变大后的组织问题

这和你现在对并行 candidate skill 的判断是一致的。

## 和你当前设想不一样、但很值得你想的地方

### 1. 它更偏单体 agent 自演化，不是你现在在想的并行 candidate 产线

你现在更关心的是：

- 多个任务并行产出 skill
- 后面统一筛选 / 压缩 / 整合

而它主要还是：

- 一个 agent
- 一套共享 skill 库
- 顺着任务流持续写回

所以它没有正面解决你现在最关心的这些问题：

- 并行写冲突
- 多任务同时修改同一 skill
- 候选池和正式库怎么隔离
- 压缩阶段如何防止把不同 family 错并

有意思的是，它在注释掉的 future work 里反而提到了多 agent 共享 skill 库会有并发写和 credit assignment 问题。说明你现在担心的点，不是杞人忧天，而是它自己也承认还没解决。

### 2. 它默认 skill 是可执行多 artefact，不只是 planner prior

这和你现在 `mode2` 那种 planner-oriented skill 有差别。

它更像：

- skill = 可执行程序包

而你现在还在探索：

- skill 是 planner policy
- 还是 executor-facing procedure
- 还是二者分层

所以你读它时最值得问自己的一句是：

- 你的 planner skill 要不要最终落到某种“可执行 artefact”层，而不是永远停留在高层文字规划？

### 3. 它有 utility threshold 和 unit-test gate

这两个机制非常实用：

- utility threshold：决定修补还是发现新 skill
- unit-test gate：防止 skill 改坏后直接污染正式库

你现在系统里最容易借的不是它的整套理论，而是这两个工程闸门。

## 我觉得你可以直接借的 4 个设计点

### 1. 给每个 skill 增一个显式 utility / confidence 轨道

不是只看有没有命中，而是记录：

- 命中次数
- 成功率
- 最近窗口表现
- 失败族分布

这样后面更容易决定：

- 修补
- 降级
- 冻结
- 重构

### 2. 在失败后先做 `target skill selection`

不要直接“哪个地方都改一点”。

先明确：

- 这次失败最该写回 planner skill
- 还是 parameter strategy
- 还是 executor habit
- 还是根本该新建 family-specific skill

### 3. 给正式库加一个最小 gate

你现在最需要的其实不是更复杂的 merge，而是正式库入口闸。

至少可以考虑：

- 成功任务覆盖数
- 最近成功率
- 是否通过最小回放测试
- 是否只是单题过拟合

### 4. 把 router 目标慢慢从“文本像”推向“行为像”

即使现在不训一个新 router，也可以先在离线分析时做：

- 哪些 skill 文本很像，但执行行为差很大
- 哪些 merge 后文本更统一，但路由命中变差

这个分析会直接影响你后面的压缩策略。

## 这篇论文对你最重要的一句启发

我觉得不是“让 agent 设计 agent”，而是这句潜台词：

- 真正可持续的 agent 学习，关键不只是能不能生成 skill，而是有没有把 `skill 的生成、路由、归因、修补、晋升、回滚` 做成一个闭环系统。

你现在已经在想：

- 正式库
- 候选池
- 失败模式池
- 并行 candidate
- 后置压缩

这其实比它更进一步了。你接下来最该做的，不是回到“怎么写更漂亮的 SKILL.md”，而是把这些层之间的晋升与回写规则设计清楚。

## 如果你现在只想带着 3 个问题去读原文

1. 它为什么坚持把 `skill folder` 当 memory，而不是只存反思文本？
2. 它是怎么区分“修补旧 skill”和“发现新 skill”的？
3. 如果把它改造成你的并行 `candidate skill -> 后置压缩` 体系，哪些环节必须重做？

## 我的短评

这篇论文真正新的地方，不是某一个 prompt 技巧，而是它把：

- `skill`
- `memory`
- `policy`
- `reflection`

这四件事尽量统一到了一个框架里。

对你来说，它最值得学的不是照搬整套系统，而是借它来坚定两件事：

1. `skill` 不该只是静态说明书
2. 外部可写 memory 这条路，值得继续往“结构化、分层化、可验证”方向走

