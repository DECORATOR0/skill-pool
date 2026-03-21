---
name: earth-spectrum-thermal-retrieval
description: Solves Earth-Bench spectrum thermal retrieval questions involving split-window, single-channel, multi-channel, TES, MODIS day-night LST, TTM, threshold ratios, and period comparison. Use for thermal Band 31/32, emissivity, LST threshold, monthly average, seasonal difference, or extreme-heat counting tasks.
allowed-tools: Read, Glob, Grep, Bash(python *), Edit
---

# Earth Spectrum Thermal Retrieval

Use this skill for `Autonomous Planning` spectrum questions whose core workflow is:

`get_filelist -> thermal retrieval transform -> threshold/statistics tail`

Typical benchmark families covered by this skill:

- `split_window` thermal-band retrieval
- `lst_single_channel`, `lst_multi_channel`, `temperature_emissivity_separation`
- `modis_day_night_lst`, `ttm_lst`, `band_ratio`
- threshold-ratio, threshold-count, condition-count, period-average, year-to-year difference

Do not use this skill for `TVDI` or `ATI` drought-stress questions. Those belong to `earth-spectrum-drought-stress`.

## Skill Objective

Produce a compact but benchmark-faithful execution plan and stepwise tool calls for thermal retrieval questions.

This skill replaces the old single-agent behavior of:

- overusing generic `mean` tails when a specialized threshold tool is more canonical
- confusing `split_window` and `lst_multi_channel`
- collapsing two-period questions into one transform plus one final tail

## Tool Scope

Prefer the routed tool subset prepared by `agent/skill_eval/skill_router.py`.

Core tools for this skill:

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

Avoid adding unrelated product or RGB tools.

## Family Rules

1. `split_window`:
Use when the question explicitly mentions split-window, or when paired thermal bands `31/32` are used for direct LST retrieval on a scene.

2. `lst_multi_channel`:
Use when the question asks for daily/monthly/annual average LST from paired thermal bands without an explicit split-window instruction.

3. `lst_single_channel`:
Use when a single thermal band is given or the question explicitly says single-channel.

4. `temperature_emissivity_separation`:
Use when emissivity variation or ASTER TES output is central.

5. Specialized tail tools override generic means:
If the benchmark family is about threshold ratio, count under condition, or condition-specific band mean, prefer:
- `calculate_threshold_ratio`
- `count_images_exceeding_threshold_ratio`
- `count_images_exceeding_mean_multiplier`
- `count_pixels_satisfying_conditions`
- `calculate_band_mean_by_condition`
- `calc_threshold_value_mean`

Do not replace those with `calc_batch_image_mean -> mean` unless the question truly asks for a mean.

6. Two-period comparison:
If the question compares two months, seasons, or years, build both blocks explicitly before `difference`.

## Stepwise Execution Pattern

Follow this sequence:

1. Call `get_filelist`.
2. Inspect filenames to determine the retrieval family.
3. Choose the retrieval tool.
4. Generate the first retrieval output.
5. If multiple periods exist, repeat the retrieval/aggregation block per period.
6. Apply the correct tail tool.
7. Stop once enough evidence exists to support the final 4-choice selection.

## Parameter Selection Policy

Tool arguments are not decided in one shot.

For each tool step:

1. Build the user prompt with:
   - current context or the original question
   - `Relevant datas are stored at {data path}`
   - the routed tool list rendered in LangChain-like `name + description + args` format
2. Send the prompt to the parameter model defined in `agent/skill_eval/config.py`
3. Request exactly one next tool call with concrete arguments
4. Execute the tool
5. Append the resulting observation to context
6. Repeat

Use the shared worker system prompt from `agent/skill_eval/config.py`.

## Prompt Format

The stepwise worker prompt must follow this structure:

1. If context exists, put context first
2. Otherwise use the original question
3. Add `Relevant datas are stored at {data path}`
4. Append the routed tools and args description

The helper implementation already exists in:

- `agent/skill_eval/prompt_builder.py`
- `agent/skill_eval/tool_rendering.py`
- `agent/skill_eval/parameter_worker.py`

## Stop Conditions

Stop when one of these is true:

- the key thermal product and required summary statistic are already computed
- a final comparison value, ratio, count, or ranked period is available
- further tool calls would only restate the same result

Do not do the final 4-choice answer selection inside this skill. That is a separate post-skill step.
