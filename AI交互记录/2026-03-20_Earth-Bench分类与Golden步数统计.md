# 2026-03-20 Earth-Bench 分类与 Golden 步数统计

## 时间

- 2026-03-20

## 用户要求

- 查看 Earth-Bench 题目是否存在既定分类
- 统计 Golden 调用的工具步数上限、下限、平均值
- 如果手工查看麻烦，可以直接写脚本做全量统计

## AI 执行动作

- 定位并检查原始数据文件 `project_skills/benchmark/question.json`
- 定位并检查转换后数据文件 `project_skills/data/converted/earth_bench_skill_rl/question.json`
- 检查数据转换逻辑 `project_skills/nlrl_skills/data.py`，确认 `gold_tool_names` 由 `dialogs[].tool_calls[].function.name` 顺序提取
- 全量统计所有题目的 `gold_tool_names` 长度分布，而不是只做抽样
- 检查 `project_skills/docs/training_data_format.md` 与 `project_skills/agent/skill_eval/README.md`、`project_skills/agent/skill_eval/skill_router.py`，确认当前仓库里的显式分类方式

## 最终落地结果

- 本地这份 Earth-Bench 数据不是 243 题，而是 248 题
- 转换后数据中的题号连续为 `1-248`
- 数据本身没有每题单独的 `category` 字段；显式字段主要是：
  - `source_type = "C"`
  - `metadata.evaluation_type = "Autonomous Planning"`
- 当前 `skill_eval` 运行时存在 6 类既定 skill 分类：
  - `earth-spectrum-thermal-retrieval`
  - `earth-spectrum-drought-stress`
  - `earth-product-timeseries`
  - `earth-product-derived-index-change`
  - `earth-product-raster-arithmetic`
  - `earth-rgb-perception-change`
- 按当前 `skill_router` 对 248 题分桶后的数量为：
  - `earth-spectrum-thermal-retrieval`: 76
  - `earth-spectrum-drought-stress`: 27
  - `earth-product-timeseries`: 42
  - `earth-product-derived-index-change`: 38
  - `earth-product-raster-arithmetic`: 5
  - `earth-rgb-perception-change`: 60
- Golden 工具步数按 `gold_tool_names` 统计结果为：
  - 最少 2 步
  - 最多 19 步
  - 平均 5.3831 步
  - 中位数 5 步
  - 25% 分位数 3 步
  - 75% 分位数 6 步
- 额外确认：
  - 这套数据里每个带工具的 assistant turn 只调用 1 个工具，因此这里的“工具步数”可直接视为 Golden 工具调用步数
  - 最短样本为 `earth-bench-c-121`、`earth-bench-c-180`
  - 最长样本为 `earth-bench-c-108`

## 后续维护要求

- 如果后面 Earth-Bench 源数据版本变化，需要重新统计一次题量、分类分桶和 Golden 步数分布
- 如果 `skill_router.py` 的规则调整，分类数量应以新路由结果为准，不应继续沿用本次统计
- 如果后续要频繁查看单题明细，建议再补一个导出脚本，将每题的 `task_id`、分类、步数、工具序列导出为 `csv` 或 `json`
