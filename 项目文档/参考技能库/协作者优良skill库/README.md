# Earth-Bench Skills

This directory contains the current Anthropic-style `SKILL.md` skill set used by the `skill_eval` benchmark pipeline for Earth-Bench `Autonomous Planning` questions.

## Current Skill Set

The runtime currently routes questions into these `6` skills:

- `earth-spectrum-thermal-retrieval`
- `earth-spectrum-drought-stress`
- `earth-product-timeseries`
- `earth-product-derived-index-change`
- `earth-product-raster-arithmetic`
- `earth-rgb-perception-change`

These skills are benchmark-oriented planning priors, not the sole runtime source of truth.

## What Each Skill Covers

1. `earth-spectrum-thermal-retrieval`
   - thermal retrieval, threshold, ratio, condition, and period-comparison spectrum workflows
2. `earth-spectrum-drought-stress`
   - `TVDI`, `ATI`, drought severity, dryness trend, and stress-threshold workflows
3. `earth-product-timeseries`
   - generic non-RGB multi-date raster statistics, trends, minima/maxima, and product-series aggregation
4. `earth-product-derived-index-change`
   - repeated `NDVI`/`NDWI`/`NDTI`/`NBR`/turbidity/cloud-mask derivation before downstream comparison or hotspot analysis
5. `earth-product-raster-arithmetic`
   - arithmetic-heavy product workflows such as subtraction, division, sum chains, and percentage change
6. `earth-rgb-perception-change`
   - RGB scene classification, counting, grounding, geometry, segmentation-based area, and before/after change

## Runtime Relationship

The `SKILL.md` files are the human-readable skill definitions.

The actual runtime source of truth is in:

- `agent/skill_eval/skill_router.py`
- `agent/skill_eval/skill_llm_planner.py`
- `agent/skill_eval/parameter_worker.py`
- `agent/skill_eval/staged_runner.py`
- `agent/skill_eval/executor.py`

In other words:

- `.claude/skills/` describes the skills
- `agent/skill_eval/` decides how benchmark questions are actually routed, planned, parameterized, executed, and evaluated

## How Skills Are Used

In the current `skill_eval` pipeline, a skill is used to:

- bias routing toward the right question family
- inject skill-specific planning guidance into the planner prompt
- identify likely focus tools inside the shortlist
- constrain later parameter generation and execution behavior

The planner still follows the single-agent shape:

1. build a shortlist
2. send `question + data_dir + file list + shortlisted tools` to one planner LLM call
3. let the planner output the full `tool_sequence`

So a skill is no longer a hard-coded plan template by itself.

## Planning Fallbacks

The current planning paths in `skill_eval` are:

- `skill-llm-json`
- `skill-llm-tagged-fallback`
- `skill-template-fallback`

The last one is only used when both LLM planning paths fail.

## Anthropic Skill Notes

These skills follow the lightweight Anthropic-style `SKILL.md` pattern with project-local markdown instructions.

The current documentation-supported ideas that are relevant here include:

- `name`
- `description`
- `allowed-tools`
- `disable-model-invocation`
- `user-invocable`
- `context`
- `agent`
- `$ARGUMENTS` substitution

## Related Documentation

For the current executable benchmark pipeline, commands, logging, model configuration, and staged runner behavior, see:

- `agent/skill_eval/README.md`
