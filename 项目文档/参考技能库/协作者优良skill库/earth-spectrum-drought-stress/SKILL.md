---
name: earth-spectrum-drought-stress
description: Solves Earth-Bench spectrum drought and dryness questions based on TVDI or ATI, including drought severity thresholds, annual trend analysis, average dryness statistics, and period-to-period comparisons. Use for TVDI, ATI, dryness, drought severity, or thermal-vegetation stress tasks.
allowed-tools: Read, Glob, Grep, Bash(python *), Edit
---

# Earth Spectrum Drought Stress

Use this skill for spectrum questions whose semantic target is dryness or drought stress rather than generic thermal retrieval.

Typical benchmark families covered by this skill:

- `compute_tvdi`
- `ATI`
- drought severity threshold classification
- annual average dryness trend
- dryness comparison across two periods
- mean dryness under a temperature condition

Do not use this skill for plain LST retrieval or emissivity-only questions unless the final task is explicitly drought-oriented.

## Skill Objective

Produce a benchmark-faithful drought workflow:

`get_filelist -> drought indicator transform -> drought-specific threshold/statistics tail`

This skill exists because the old single-agent planner often:

- confused `TVDI` questions with generic `LST mean` chains
- under-modeled repeated annual aggregation blocks
- replaced specialized drought tails with overly generic aggregates

## Tool Scope

Core tools for this skill:

- `get_filelist`
- `compute_tvdi`
- `ATI`
- `calculate_tif_average`
- `calc_batch_image_mean`
- `mean`
- `difference`
- `calculate_threshold_ratio`
- `calc_threshold_value_mean`
- `calc_batch_image_mean_threshold`
- `calc_batch_image_mean_max_min`
- `compute_linear_trend`
- `mann_kendall_test`

If the routed subset includes generic thermal retrieval tools, use them only when they are needed to produce the drought indicator. Prefer `compute_tvdi` or `ATI` when the benchmark dialogue clearly centers on those products.

## Family Rules

1. `TVDI`:
Use when the question mentions:
- `TVDI`
- dryness from `NDVI/EVI + LST`
- drought severity classes from thermal-vegetation dryness

2. `ATI`:
Use when the question mentions:
- `ATI`
- `apparent thermal inertia`
- drought stress inferred from thermal inertia

3. Annual trend:
If the question asks for annual dryness change, build each year’s average block explicitly:

`indicator -> annual average -> annual average list -> trend`

4. Threshold families:
If the question asks for drought severity percentages, threshold-area proportion, or mean dryness under a heat condition, prefer:
- `calculate_threshold_ratio`
- `calc_threshold_value_mean`
- `calc_batch_image_mean_threshold`

Do not replace these with plain `mean`.

5. Period comparison:
For two months/years/seasons, compute both period blocks first, then use `difference`.

## Stepwise Execution Pattern

1. Call `get_filelist`.
2. Separate thermal inputs from vegetation inputs if both appear.
3. Compute the drought indicator.
4. If needed, aggregate the indicator by month or year.
5. Apply the drought-specific threshold/statistic tool.
6. Stop as soon as the derived indicator is sufficient for answer selection.

## Parameter Selection Policy

Use the sequential parameter worker, not one-shot argument generation.

For each step:

1. Provide current context or the original question
2. Add `Relevant datas are stored at {data path}`
3. Append the routed tool list rendered with argument schemas
4. Ask the worker for exactly one next tool call
5. Execute and append the observation
6. Repeat

Use the shared worker system prompt and `Qwen/Qwen3-8B-1` settings from `agent/skill_eval/config.py`.

## Optimization Notes

This skill specifically preserves the benchmark patterns that were weak in the old plan-only flow:

- repeated annual `calculate_tif_average` blocks before trend
- explicit drought threshold or severity statistics
- specialized dryness tails instead of generic mean-only endings

## Stop Conditions

Stop when:

- the drought indicator has been produced and summarized enough to choose among the four answers
- the annual or period comparison statistic is already computed
- the remaining work would only duplicate equivalent summaries

The final 4-choice answer selection remains outside this skill.
