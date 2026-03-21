---
name: earth-product-derived-index-change
description: Solves Earth-Bench product questions that repeatedly derive NDVI, NDWI, NDTI, NBR, turbidity, or cloud-masked water products before hotspot, direction, ratio, or period-comparison analysis. Use for NDWI water-body comparison, NDTI turbidity comparison, NBR fire-risk distribution, and repeated derived-index workflows.
allowed-tools: Read, Glob, Grep, Bash(python *), Edit
---

# Earth Product Derived Index Change

Use this skill for product-domain questions where the benchmark repeatedly derives an index or a cloud-masked product before later statistics.

Typical families:

- `apply_cloud_mask -> calculate_ndwi -> ...`
- repeated `calculate_ndti`
- repeated `calculate_nbr`
- repeated `calculate_ndvi`
- `calculate_water_turbidity_ntu`
- hotspot map and hotspot-direction workflows

## Planning Principle

Do not collapse repeated transform families into one generic summary.

When the benchmark computes an index for multiple dates or periods, keep the repeated transform blocks explicit before the final tail.

## Canonical Patterns

- cloud-masked water comparison:
  `get_filelist -> apply_cloud_mask* -> calculate_ndwi* -> stats -> difference`
- turbidity / NDTI comparison:
  `get_filelist -> calculate_tif_average* -> calculate_ndti* -> stats -> difference`
- fire-risk direction:
  `get_filelist -> calculate_nbr* -> calc_batch_image_hotspot_tif -> analyze_hotspot_direction`
- NDVI peak/extremes:
  `get_filelist -> calculate_ndvi* -> calc_batch_image_mean* -> max_value_and_index`

## Execution Rule

The stepwise worker only fills arguments for the already planned next tool.
Final answer choice is outside this skill.
