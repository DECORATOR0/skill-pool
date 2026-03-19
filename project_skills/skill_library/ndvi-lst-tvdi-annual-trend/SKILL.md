---
name: ndvi-lst-tvdi-annual-trend
description: Compute annual dryness trend from NDVI and LST raster time series by exact-date pairing, inventory-derived year coverage, batched TVDI generation, yearly averaging, yearly mean extraction, strict invalid-statistics blocking, and linear trend fitting.
allowed-tools:
  - get_filelist
  - compute_tvdi
  - calculate_tif_average
  - calc_batch_image_mean
  - compute_linear_trend
---

Use this skill for annual dryness/wetness trend tasks from NDVI+LST GeoTIFFs in one dataset.

Defaults:
- Infer `DATA_DIR` from the task when possible.
- Start with `get_filelist(dir_path=DATA_DIR)` whenever available.
- Pair only exact shared dates between `_NDVI.tif` and `_LST.tif` from actual inventory.
- Ignore unmatched files for computation, but report reduced matched-date/year coverage when relevant.
- Derive usable years from matched filenames, not prompt wording alone.
- If requested years are partially missing, state the reduced coverage and continue on available years when at least 2 valid annual means remain, unless the user explicitly requires the absent year itself.
- Build full source paths by prefixing inventory filenames with `DATA_DIR`; never pass bare filenames to raster tools.
- Prefer one batched `compute_tvdi` call with native lists when accepted.
- For `calculate_tif_average` and `calc_batch_image_mean`, pass real lists for `file_list`.
- `calculate_tif_average` must use `output_path`.
- `calc_batch_image_mean` has an optional `uint8` argument; use it as a bounded diagnostic fallback only when mean extraction returns all-NaN or mostly-NaN.
- For `compute_linear_trend`, consume only the exposed slope/value; do not assume a tuple schema.
- Reference files are optional aids only; do not stop just because they cannot be read.

Procedure:
1. Call `get_filelist(dir_path=DATA_DIR)`.
2. Parse inventory into NDVI and LST maps keyed by exact `YYYY-MM-DD`; keep only exact shared dates.
3. Group matched dates by year and derive `available_years` from actual coverage.
4. Compare requested years vs `available_years`.
   - State missing requested years briefly, e.g. `available matched data cover 2019–2022 only; 2023 is unavailable`.
   - Continue if at least 2 usable years remain.
   - Stop only when fewer than 2 usable years remain.
5. Build deterministic output paths for per-date TVDI rasters and per-year annual averages.
6. Call `compute_tvdi` for all matched pairs in aligned date order.
7. Regroup returned TVDI outputs by year.
8. Call `calculate_tif_average(file_list=[yearly_tvdi_paths...], output_path=...)` once per available year.
9. If any `calculate_tif_average` call fails with missing GDAL/runtime support, stop immediately and report an environment blocker with preserved error text.
10. After all annual rasters succeed, call `calc_batch_image_mean(file_list=[annual_avg_paths...])` in `available_years` order.
11. Validate annual means strictly.
   - If at least 2 values are numeric and not collectively implausible, use only numeric years/means and continue.
   - If the first result is all-NaN or mostly-NaN, retry once on the same annual raster list.
   - If still all-NaN or mostly-NaN, call `calc_batch_image_mean(file_list=[annual_avg_paths...], uint8=true)` once.
   - Treat `uint8=true` as invalid if it returns all zeros or a nearly all-zero vector across all annual TVDI rasters after upstream TVDI/annual averaging supposedly succeeded; do not fit a trend on that fallback.
   - Do not treat all-NaN means or all-zero uint8 fallback means as trustworthy recovery.
   - If fewer than 2 valid annual means remain after these bounded attempts, report a data-quality/environment blocker explicitly and stop.
12. Call `compute_linear_trend(x=years_used, y=annual_means_used)` only when at least 2 valid yearly means remain.
13. Interpret slope: positive = increasing dryness, negative = decreasing dryness, near zero = little/no clear annual change.
14. Final response must always be produced.
   - If trend computation succeeds: state years used, mention any missing requested years, and provide slope/trend; if answer choices are provided, return only the best matching label after successful trend computation.
   - If blocked or partial: explicitly state the matched-data coverage and why computation could not be completed or why requested years were excluded, e.g. `Using matched NDVI/LST data available for 2019–2022, dryness decreased annually; if 2023 data are required, they are missing from the dataset.` or `Using matched NDVI/LST data available for 2019–2022, annual TVDI mean extraction remained invalid (all-NaN / implausible all-zero fallback), so no reliable trend was reported.`

Postconditions:
- If at least 2 valid annual means exist after validation/fallback, call `compute_linear_trend`.
- Missing requested years are non-fatal when enough valid available years remain for trend fitting.
- If annual means remain all/mostly NaN after one retry plus one `uint8=true` attempt, or if the fallback produces implausible all-zero values, report a blocker and do not claim a scientific trend.

Hard rules:
- Do not require reading bundled references before acting.
- If core analysis tools are present, proceed with the native workflow.
- First inspect inventory and derive actual year coverage before claiming missing coverage.
- Trust actual inventory and pair only exact coexisting dates.
- Use only exact NDVI/LST date pairs; unmatched files are not blockers, but they must be reflected in coverage reporting when they shrink the analyzed window.
- Use native Python/JSON lists for batched `compute_tvdi`; do not stringify lists.
- Do not guess filenames, dates, annual means, slope values, return shapes, or answer labels.
- If annual averaging is blocked by GDAL/runtime support, stop after the first such error and report a structured blocked result.
- If `calc_batch_image_mean` returns anomalous NaNs, do not answer `no trend`; perform the bounded recovery path first.
- Never regress on annual means that are all NaN, all zero from `uint8=true`, or otherwise clearly inconsistent with successful upstream TVDI generation.
- Distinguish missing years, environment unavailability, and anomalous mean-extraction outputs in the final response.
- If bundled scripts are added later, invoke them via `run_python_script`; do not treat file paths as tool names.

Optional reference: `references/REFERENCE.md` contains compact decision rules and examples.
