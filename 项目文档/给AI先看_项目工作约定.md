# 给 AI 先看：项目工作约定

这份文档是给后续 AI 看的。进入这个项目后，默认先看这份，再做任何运行、改代码、改文档或解释实验结果。

## 1. 开工前最少要看什么

每次开工默认先看：

1. 根目录 `README.md`
2. 本文档
3. `项目文档/项目架构与工作流说明书.md`
4. `待办/进行中.md`
5. `实验记录/实验总表.md`

`AI交互记录/` 不要求每次全量扫描。只有两种情况才去看：

- 用户明确说“去翻之前我和 AI 的记录”
- 当前问题明显依赖某个长期约定，但在上述文档里找不到

## 2. 运行命令的硬性规则

### 2.1 工作目录

所有命令都在外层根目录执行：

```powershell
cd D:\skills-evo\project_skills
```

不要在内层目录 `D:\skills-evo\project_skills\project_skills` 里跑：

```powershell
python -m nlrl_skills.cli ...
```

那样会优先导入仓库里的假 `osgeo`，引出致命 GDAL 误报。

### 2.2 CLI 入口

统一入口写法：

```powershell
python -m project_skills.nlrl_skills.cli --config "project_skills/configs/<某个配置>.json" <command> [args]
```

如果需要指定 conda 环境，优先用解释器直启：

```powershell
E:\miniconda3\envs\earth-bench-skill-eval\python.exe -m project_skills.nlrl_skills.cli --config "project_skills/configs/<某个配置>.json" <command> [args]
```

### 2.3 长跑方式

不要从可见 `cmd.exe` 窗口拉起长跑实验。用户明确不接受这种方式，因为关掉窗口会连子进程一起杀掉。

优先做法：

- 直接用环境里的 `python.exe`
- 从 PowerShell 启动
- 把 stdout/stderr 重定向到 `project_skills/runs/_launch_logs/`

## 3. 训练、测试、评估怎么选

- 想跑完整训练环：用 `train-tasks`
- 想只看当前 skill 库推理效果，不改 skill：用 `evaluate-tasks`
- 想保留训练流程但每题只试一轮：把 `runtime.max_iterations_per_task` 设成 `1` 后再跑 `train-tasks`
- 想单题细查：用 `debug-single-task`

## 4. 这个项目里最容易踩的坑

### 4.1 假 `osgeo` 抢导入

只要看到：

```text
GDAL runtime is not available in this environment
```

先检查两件事：

1. 当前目录是不是外层根目录
2. 入口是不是 `project_skills.nlrl_skills.cli`

不要第一反应去怀疑 `Statistics.py` 或配置回退。

### 4.2 Qwen 的 TPM / 长上下文问题

当前已知现象：

- `Qwen/Qwen3-8B` 在长 executor 轨迹里容易因为 prompt 累积过长而触发 `429 / TPM limit reached`
- 这通常不是“整个 run 永久坏了”，而是某一道题本地 token 窗口打满了

因此解释实验时要优先查：

- executor 有没有反复调用同一个工具
- prompt token 有没有一路膨胀
- 后续任务是不是只是因为窗口恢复且 prompt 更短才成功

### 4.3 文档维护约束

后续 AI 不能只改代码不落文档。遇到下面几类动作，必须同步文档：

- 新开或跑完一个值得保留的 run：更新 `实验记录/实验总表.md`
- 用户新增了长期约定：追加 `AI交互记录/`
- TODO 状态变化：更新 `待办/进行中.md` 或 `待办/已完成.md`
- 目录结构变化：同步 `README.md` 和说明书

## 5. 命名和归档规则

- 面向用户的长期文档尽量用中文命名
- run 名称不要保留含混的 `debug_xxx_final_final2` 风格；保留历史样本时，优先改成“为什么保留它”的特征名
- 非核心资料统一放进 `杂项归档/`
- 不要把重要结论只留在零散聊天里，至少要落到 `实验记录/` 或 `待办/`

## 6. 每次收尾要做什么

### 6.1 实验收尾

跑完实验后执行：

```powershell
python project_skills/scripts/generate_experiment_table.py
```

### 6.2 文档收尾

检查是否需要同步：

- `实验记录/实验总表.md`
- `待办/进行中.md`
- `待办/已完成.md`
- `AI交互记录/`

### 6.3 解释收尾

对用户解释实验时，优先给出：

1. 具体 run / task 路径
2. 具体配置差异
3. 具体失败点或成功原因

不要只给抽象推测。

