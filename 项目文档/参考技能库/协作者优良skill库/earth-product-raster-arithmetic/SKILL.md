---
name: earth-product-raster-arithmetic
description: Solves Earth-Bench product questions whose benchmark trajectory is dominated by arithmetic over multiple raster products, such as built-volume subtraction, multi-product sums, ratio chains, and percentage-change computation. Use for residential volume, commercial energy saving, built-volume comparisons, and other multi-raster arithmetic workflows.
allowed-tools: Read, Glob, Grep, Bash(python *), Edit
---

# Earth Product Raster Arithmetic

Use this skill when the target reasoning is mainly about composing several raster products through subtraction, sums, division, and percentage change.

Typical families:

- `calculate_tif_average -> calc_batch_image_sum -> division -> percentage_change`
- repeated `subtract` for built-volume or residential-volume estimation

## Planning Principle

Treat these as arithmetic templates, not as generic raster-statistics questions.

Preserve repeated `subtract`, `sum`, and `division` blocks when the benchmark gold trajectory expands them explicitly.

## Canonical Patterns

- energy saving:
  `get_filelist -> calculate_tif_average* -> calc_batch_image_sum* -> division* -> percentage_change`
- residential volume trend:
  `get_filelist -> subtract* -> calc_batch_image_mean -> compute_linear_trend`

## Execution Rule

The stepwise worker only fills arguments for the already planned next tool.
Final answer choice is outside this skill.
