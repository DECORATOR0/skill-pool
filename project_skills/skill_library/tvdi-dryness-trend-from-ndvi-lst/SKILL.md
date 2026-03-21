---
name: tvdi-dryness-trend-from-ndvi-lst
description: Compute dryness/TVDI trends from NDVI and LST raster time series when a task asks for dryness, agricultural drought, TVDI, annual averages, or linear trends over years. Use this for directories containing dated NDVI and LST GeoTIFFs that must be paired by timestamp and summarized into yearly trend values.
allowed-tools:
  - get_filelist
  - compute_tvdi
  - calculate_tif_average
  - calc_batch_image_mean
  - compute_linear_trend
  - run_python_script
---

Use this when the task mentions **NDVI + LST**, **TVDI**, **dryness/drought indicator**, **annual trend**, or **linear trend** from raster time series.

Default workflow:
1. Call `get_filelist` on the data directory.
2. Immediately check requested year coverage from filenames:
   - expected pattern: `<prefix>_<YYYY-MM-DD>_LST.tif` and `<prefix>_<YYYY-MM-DD>_NDVI.tif`
   - pair files directly from filenames when prefix and date match and only the final token differs (`LST` vs `NDVI`)
   - group matched pairs by year in ascending order
   - if requested years are partially unavailable, explicitly report: requested years, available years, and omitted years
   - proceed only with available complete pairs; never invent missing files or years
3. Call `compute_tvdi` once over all matched pairs with aligned `lst_path`, `ndvi_path`, and generated `output_path` lists.
4. For each year with matched pairs, call `calculate_tif_average` once on that year's TVDI rasters to produce one annual-average TVDI raster.
5. Call `calc_batch_image_mean` once on the annual-average rasters to get one mean dryness value per year.
6. Call `compute_linear_trend` with `x=years` and `y=annual_means`.
7. Report the annual mean sequence, computed slope in "per year", exact data-year coverage, and interpretation: positive = increasing dryness, negative = decreasing dryness, near-zero = little/no clear trend.
8. If answer choices are present, separate the numeric result from answer selection and apply this rule:
   - first compute and state the numeric slope from the available data
   - then inspect the choices for direction/sign and any numeric or verbal magnitude
   - discard choices with the wrong direction unless every option is directionally inconsistent
   - among the directionally consistent choices, choose the **numerically closest** option to the computed slope when numeric values/ranges are given
   - if choices are verbal only, choose the wording that best matches the computed magnitude category and direction
   - if data coverage is incomplete, still apply the same mapping rule to the computed available-data slope; mention the limitation separately and do **not** switch to a sign-only or "semantic consistency" fallback

Tool-use rules:
- Prefer deterministic filename pairing from `get_filelist`; do not use a script when filenames are regular.
- Build input paths by joining the data directory with filenames returned by `get_filelist`.
- Prefer stable relative output paths consistent with tool examples, e.g. `<task_or_folder>/tvdi_<YYYY-MM-DD>.tif`.
- After any tool call that returns output paths, use the returned paths exactly for downstream steps; do not assume relative/absolute path form.
- Trust the runtime schema/signature over stale wording in tool descriptions.
- For `calculate_tif_average`, use the runtime-required argument name `output_path`.
- Use only years that have at least one matched pair for trend computation, but explicitly mention omitted/incomplete requested years in the answer.
- Do not treat truncated helper-script stdout as a blocker if `get_filelist` already provides enough information to pair files.
- Unless the prompt specifies otherwise, treat TVDI as the dryness indicator.

Optional fallback:
- Use `run_python_script` only if filename structure is irregular.
- Invoke bundled scripts through the `run_python_script` tool; never treat script paths as tool names.
- For `scripts/pair_tvdi_inputs.py`, pass the argument as a JSON string with exact shape: `{"data_dir":"<dir>","files":["file1.tif","file2.tif",...]}`.
- Treat script output as advisory only; stdout may be truncated, so verify/continue using the original file list.

See `references/REFERENCE.md` for pairing, path conventions, incomplete-coverage reporting, and MCQ mapping examples.
