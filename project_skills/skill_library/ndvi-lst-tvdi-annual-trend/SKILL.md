---
name: ndvi-lst-tvdi-annual-trend
description: Compute annual dryness trend from NDVI and LST raster time series by pairing filenames by date, generating TVDI rasters, averaging TVDI within each available year, extracting yearly means, and fitting a linear trend.
allowed-tools:
  - get_filelist
  - compute_tvdi
  - calculate_tif_average
  - calc_batch_image_mean
  - compute_linear_trend
---

Use this skill for annual dryness/wetness trend tasks from NDVI+LST GeoTIFFs stored in one directory.

Default mode: native tools only.
- Do not use `run_python_script`.
- Do not use helper scripts or unrelated file-inspection tools.
- Do not call `get_filelist` more than once unless the first call clearly failed. If it returns the same result twice, do not call it again.

Procedure:
1. Call `get_filelist(dir_path=DATA_DIR)` once.
2. From the returned bare filenames, parse date token `YYYY-MM-DD` in-memory and build two maps by date:
   - `*_LST.tif`
   - `*_NDVI.tif`
3. Match only dates present in both maps. Exclude unmatched dates; do not invent pairs.
4. Early coverage check:
   - If the prompt requests a span like 2019–2023, compare requested years with available matched years.
   - If a requested year is absent, continue with available years and state the limitation explicitly.
   - If some dates are unmatched within a year, note that briefly and continue.
   - If fewer than 2 yearly means will be available, report that a linear trend is not reliable.
5. Build aligned lists in sorted date order:
   - `lst_path=[DATA_DIR/<lst-file>, ...]`
   - `ndvi_path=[DATA_DIR/<ndvi-file>, ...]`
   - `output_path=[TASK_OUT/tvdi_YYYY-MM-DD.tif, ...]`
6. Call `compute_tvdi(lst_path=..., ndvi_path=..., output_path=...)` once over all matched pairs if batch is supported.
7. If batch `compute_tvdi` fails, iterate once per matched pair using the same pairing result already in memory. Do not re-query the file list.
8. Group produced TVDI rasters by year and call `calculate_tif_average(file_list=year_tvdis, output_path=annual_avg_path)` once per available year.
9. Call `calc_batch_image_mean(file_list=annual_avg_paths)` once.
10. Call `compute_linear_trend(x=sorted_years, y=annual_means)`.
11. Return the result in words:
   - negative slope = dryness decreases annually
   - positive slope = dryness increases annually
   - near zero = little or no clear annual change
   If the task is multiple choice, also return the choice label.

Deterministic filename-pairing rule:
- For filenames like `Xinjiang_2022-09-30_LST.tif` and `Xinjiang_2022-09-30_NDVI.tif`, the shared key is `2022-09-30`.
- Pair only exact shared date keys.
- Example discrepancy handling: if `Xinjiang_2022-10-16_LST.tif` exists but `Xinjiang_2022-10-16_NDVI.tif` does not, skip that date and mention one unmatched 2022 date.

Required execution rules:
- Use exact signatures only:
  - `get_filelist(dir_path=...)`
  - `compute_tvdi(lst_path=[...], ndvi_path=[...], output_path=[...])`
  - `calculate_tif_average(file_list=[...], output_path=...)`
  - `calc_batch_image_mean(file_list=[...])`
  - `compute_linear_trend(x=[years], y=[means])`
- Prefer one batch `compute_tvdi` call over many single-date calls.
- In a batch `compute_tvdi` call, `lst_path`, `ndvi_path`, and `output_path` must all be lists of the same length.
- `output_path` must be a JSON list, never one comma-joined string.
- Do not retry tools with guessed parameter names.
- Do not probe unsupported tools after a policy error; continue with the allowed tool pipeline.
- After `get_filelist`, do parsing/grouping in the reasoning step and move downstream; do not stall on repeated listing.

Path convention:
- Inputs: `DATA_DIR/<filename>`
- TVDI outputs: `question1/tvdi_YYYY-MM-DD.tif` or task-matched output subdir
- Annual averages: `benchmark/out/question1/tvdi_annual_avg_YYYY.tif`

Mini example:
- `get_filelist(dir_path="benchmark/data/question1")`
- Pair `Xinjiang_2019-01-01_LST.tif` with `Xinjiang_2019-01-01_NDVI.tif`
- Build:
  - `lst_path=["benchmark/data/question1/Xinjiang_2019-01-01_LST.tif", "benchmark/data/question1/Xinjiang_2019-01-17_LST.tif"]`
  - `ndvi_path=["benchmark/data/question1/Xinjiang_2019-01-01_NDVI.tif", "benchmark/data/question1/Xinjiang_2019-01-17_NDVI.tif"]`
  - `output_path=["question1/tvdi_2019-01-01.tif", "question1/tvdi_2019-01-17.tif"]`
- Then average per year, get annual means, and fit `x=[2019,2020,2021,2022]`.
- Example slope `-0.037` => decreasing dryness; if MCQ is present, choose the option describing decreasing dryness (often `B`).

Final answer template:
- `Available matched years: 2019, 2020, 2021, 2022; requested 2023 is absent, so trend is computed on available years only.`
- `Annual mean TVDI values: [...]`
- `Linear trend slope: ...`
- `Interpretation: dryness is increasing/decreasing/stable annually.`
- `MCQ: <label>` if applicable.
