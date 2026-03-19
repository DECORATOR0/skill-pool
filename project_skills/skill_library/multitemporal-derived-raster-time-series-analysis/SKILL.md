---
name: multitemporal-derived-raster-time-series-analysis
description: Derive multitemporal remote-sensing rasters from matched same-date inputs, summarize per-date values, then answer yearly trend, threshold-count, exceedance-count, or abrupt-spike questions. Use for MODIS b02/b05/b17/b18/b19 atmospheric absorption or PWV series, and for LST series from Band31/Band32 or Landsat 8 BT10+b4+b5 inputs.
allowed-tools:
  - get_filelist
  - band_ratio
  - lst_multi_channel
  - lst_single_channel
  - calc_batch_image_mean
  - mean
  - compute_linear_trend
  - calculate_threshold_ratio
  - count_images_exceeding_threshold_ratio
  - count_spikes_from_values
  - difference
  - run_python_script
---

Use this when a task requires: same-date raster input grouping, derived raster generation, ordered multitemporal summaries, and then a downstream statistic such as annual means, trend, threshold proportion, exceedance count, or spike count.

Supported branches:
- **MODIS atmospheric absorption / PWV**: inputs `b02 b05 b17 b18 b19` -> call `band_ratio`.
- **LST split-window**: paired `Band 31` + `Band 32` -> call `lst_multi_channel`.
- **LST single-channel**: same-date `BT10 + b4 + b5` -> call `lst_single_channel`.

Procedure:
1. Call `get_filelist` on the data directory.
2. Build complete same-date groups and sort chronologically. If filename parsing or pairing is nontrivial, call `run_python_script` with `script_path="scripts/group_multitemporal_inputs.py"`.
3. Generate one derived raster per complete timestamp using the matching algorithm family.
4. Call `calc_batch_image_mean` on the derived rasters to obtain an ordered per-date mean series.
5. Branch by question type:
   - **Annual means / trend**: group dates by year, call `mean` within each year, then `compute_linear_trend` on sorted years.
   - **Single-date threshold proportion**: call `calculate_threshold_ratio`; if the question asks for below-threshold proportion, convert using `difference` from 100.
   - **Multi-date exceedance count (LST)**: call `count_images_exceeding_threshold_ratio`.
   - **Abrupt spike count (MODIS PWV / absorption series)**: pass the ordered mean series directly to `count_spikes_from_values`.
6. Return the numeric result and map to the closest option when choices are provided.

Defaults:
- Use all complete timestamps unless the prompt restricts dates.
- Keep chronological order stable from grouping through final statistics.
- Drop incomplete timestamps rather than guessing missing bands.
- Do not mix algorithm families.

See `references/REFERENCE.md` for grouping rules and branch checklist.
