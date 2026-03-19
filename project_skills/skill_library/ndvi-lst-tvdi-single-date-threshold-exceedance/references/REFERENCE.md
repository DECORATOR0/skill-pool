Optional reference only. Do not block execution on this file.

Canonical pattern:
1. List files in `benchmark/data/<question_folder>`.
2. Pair the single-date vegetation raster (NDVI or EVI) with the same-date LST raster.
3. Call `compute_tvdi` with the vegetation raster passed via `ndvi_path`.
4. Call `calculate_threshold_ratio` on the TVDI output with threshold `0.75` unless the prompt specifies another value.
5. If MCQ options are provided, map the computed percentage to the matching/closest option.

If thresholding fails from GDAL/runtime issues, report the blocker clearly and do not guess the percentage or answer choice.
