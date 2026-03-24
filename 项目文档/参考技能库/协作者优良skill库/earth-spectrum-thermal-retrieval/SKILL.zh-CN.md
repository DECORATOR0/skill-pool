---
name: earth-spectrum-thermal-retrieval
description: 解决 Earth-Bench 中的 spectrum thermal retrieval 问题，覆盖 split-window、single-channel、multi-channel、TES、MODIS day-night LST、TTM、阈值比例以及时段对比等任务。适用于涉及热红外 Band 31/32、发射率、LST 阈值、月均值、季节差异或极端高温计数的问题。
allowed-tools: Read, Glob, Grep, Bash(python *), Edit
---

# Earth Spectrum Thermal Retrieval

当 `Autonomous Planning` 的 spectrum 问题核心流程是下面这种形式时，使用这个 skill：

`get_filelist -> thermal retrieval transform -> threshold/statistics tail`

这个 skill 覆盖的典型 benchmark 家族包括：

- `split_window` 热波段反演
- `lst_single_channel`、`lst_multi_channel`、`temperature_emissivity_separation`
- `modis_day_night_lst`、`ttm_lst`、`band_ratio`
- threshold-ratio、threshold-count、condition-count、period-average、year-to-year difference

不要把这个 skill 用在 `TVDI` 或 `ATI` 的 drought-stress 问题上。那类问题属于 `earth-spectrum-drought-stress`。

## Skill 目标

产出一个紧凑、但忠实于 benchmark 模式的执行计划，以及逐步的工具调用序列，用来解决 thermal retrieval 问题。

这个 skill 用来替代旧单智能体行为中的以下问题：

- 在本应使用专门阈值工具时，过度使用泛化的 `mean` 尾部
- 混淆 `split_window` 和 `lst_multi_channel`
- 把双时段问题错误压缩成一次变换加一次最终统计

## 工具范围

优先使用 `agent/skill_eval/skill_router.py` 预先路由好的工具子集。

这个 skill 的核心工具包括：

- `get_filelist`
- `split_window`
- `lst_single_channel`
- `lst_multi_channel`
- `temperature_emissivity_separation`
- `modis_day_night_lst`
- `ttm_lst`
- `band_ratio`
- `calculate_threshold_ratio`
- `count_images_exceeding_threshold_ratio`
- `count_images_exceeding_mean_multiplier`
- `count_pixels_satisfying_conditions`
- `calculate_band_mean_by_condition`
- `calc_batch_image_mean_threshold`
- `calc_threshold_value_mean`
- `calc_batch_image_mean`
- `calc_batch_image_mean_mean`
- `calc_batch_image_max`
- `difference`
- `mean`

避免引入无关的 product 或 RGB 工具。

## 家族规则

1. `split_window`：
当问题明确提到 split-window，或者使用成对热波段 `31/32` 直接进行场景 LST 反演时，使用它。

2. `lst_multi_channel`：
当问题要求基于成对热波段计算日/月/年平均 LST，但没有明确要求 split-window 时，使用它。

3. `lst_single_channel`：
当输入只有单个热波段，或者题目明确说 single-channel 时，使用它。

4. `temperature_emissivity_separation`：
当发射率变化或 ASTER TES 输出是问题核心时，使用它。

5. 专用尾部工具优先于泛化均值：
如果 benchmark 家族关注的是阈值比例、条件下计数、或条件筛选后的波段均值，应优先使用：
- `calculate_threshold_ratio`
- `count_images_exceeding_threshold_ratio`
- `count_images_exceeding_mean_multiplier`
- `count_pixels_satisfying_conditions`
- `calculate_band_mean_by_condition`
- `calc_threshold_value_mean`

除非问题本身明确要求均值，否则不要用 `calc_batch_image_mean -> mean` 去替代这些专用工具。

6. 双时段对比：
如果问题比较两个不同月份、季节或年份，必须先分别构造两个完整计算块，再做 `difference`。

## 分步执行模式

按以下顺序执行：

1. 调用 `get_filelist`。
2. 检查文件名，判断属于哪一种反演家族。
3. 选择正确的反演工具。
4. 生成第一份反演输出。
5. 如果存在多个时段，就为每个时段重复对应的反演/聚合块。
6. 应用正确的尾部统计工具。
7. 一旦已有足够证据支撑最终四选一答案，就停止。

## 参数选择策略

工具参数不是一次性决定的。

对于每一步工具调用：

1. 构造用户提示词，内容包括：
   - 当前上下文，或者原始问题
   - `Relevant datas are stored at {data path}`
   - 以类似 LangChain 的 `name + description + args` 格式渲染的已路由工具列表
2. 把这个提示词发送给 `agent/skill_eval/config.py` 中定义的参数模型
3. 要求模型只返回**一个**带具体参数的下一步工具调用
4. 执行该工具
5. 将结果 observation 追加到上下文中
6. 重复上述流程

使用 `agent/skill_eval/config.py` 中共享的 worker system prompt。

## Prompt 格式

分步 worker 提示词必须遵循以下结构：

1. 如果已有上下文，先放上下文
2. 否则使用原始问题
3. 加上 `Relevant datas are stored at {data path}`
4. 再附上已路由工具及其参数说明

对应的辅助实现已经存在于：

- `agent/skill_eval/prompt_builder.py`
- `agent/skill_eval/tool_rendering.py`
- `agent/skill_eval/parameter_worker.py`

## 停止条件

当满足以下任一条件时停止：

- 关键热产品以及所需汇总统计已经算出
- 最终比较值、比例、计数或排序结果已经可用
- 继续调用工具只会重复表达同一结果

不要在这个 skill 内部完成最终四选一答案选择。那是 skill 之后的独立步骤。
