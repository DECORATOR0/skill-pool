---
name: remote-sensing-derived-raster-statistics-analysis
description: Derive a remote-sensing raster from required bands, then compute class, mean, difference, count, or threshold-area statistics for Landsat 8 NDVI/LST comparisons or MODIS band-ratio atmospheric absorption/PWV analyses. Use when a task requires deterministic band pairing before summarizing the derived raster.
allowed-tools:
  - get_filelist
  - lst_single_channel
  - calculate_mean_lst_by_ndvi
  - difference
  - band_ratio
  - calc_batch_image_mean
  - calculate_threshold_ratio
  - mean
  - run_python_script
---
Use this when the task requires: (a) identifying sensor-specific bands from filenames, (b) creating a derived raster, and (c) summarizing it with class comparison, temporal mean/count logic, or threshold-area percentage.

Branches:
- Landsat 8 single-date NDVI/LST comparison:
  1. `get_filelist`
  2. identify Band 4, Band 5, Band 10/BT10
  3. `lst_single_channel`
  4. `calculate_mean_lst_by_ndvi` for each class
  5. `difference`
- MODIS band-ratio analysis:
  1. `get_filelist`
  2. `run_python_script` with `script_path="scripts/group_remote_sensing_inputs.py"` to group timestamped files and validate required bands
  3. `band_ratio` on complete timestamp bundles
  4. Then choose the statistic path that matches the question:
     - daily/image means: `calc_batch_image_mean`
     - overall mean of those values: `mean`
     - threshold-area percentage per raster: `calculate_threshold_ratio`
     - aggregate multiple percentages to one answer: `mean`

MODIS defaults:
- Common required bands may include b02/b05/b17/b18/b19; map exactly as requested.
- Default to all complete same-day timestamp groups unless the prompt gives a selection rule.
- Skip incomplete timestamp groups only when the question can still be answered from remaining complete groups; report skipped timestamps clearly. If completeness is essential to the asked comparison/count, report the blocker.
- For relative-threshold questions, compute threshold from the requested reference mean exactly, e.g. `urban_mean * 1.15` for above 115% of the urban mean.

Landsat defaults:
- Use exact NDVI thresholds from the prompt.
- `mode: above` for high-vegetation/forested classes; `mode: below` for bare/non-vegetated classes.
- Interpret `difference` sign according to warmer/cooler wording.

Answering rule:
- Return the requested numeric statistic only: temperature difference, count, mean, or percentage/average percentage, matching the prompt wording.
