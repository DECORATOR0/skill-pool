Decision rules for `ndvi-lst-tvdi-annual-trend`

Coverage:
- Inventory determines coverage, not the prompt alone.
- Pair only exact matching NDVI/LST dates.
- Unmatched files are skipped, but reduced coverage must be stated.
- Example: if 2022-10-16 LST exists but NDVI is missing, keep other matched 2022 dates and report that matched data cover 2019–2022 only if no 2023 pairs exist.

Mean-validation:
- Preferred annual means: direct `calc_batch_image_mean(file_list=[annual rasters...])`.
- If direct result is all-NaN or mostly-NaN, retry once.
- If still invalid, try `uint8=true` once.
- Reject fallback as implausible when all returned annual means are zero or nearly zero across all years after successful TVDI generation/annual averaging.
- Never fit a linear trend on `[0, 0, 0, ...]` produced only by lossy fallback from invalid means.

Final-answer patterns:
- Success with partial coverage: `Using matched NDVI/LST data available for 2019–2022, dryness decreased annually (negative slope ...); 2023 is missing from the dataset.`
- Blocked after invalid means: `Using matched NDVI/LST data available for 2019–2022, annual TVDI mean extraction remained invalid (all-NaN and implausible all-zero uint8 fallback), so no reliable trend was reported.`
- MCQ tasks: only return the choice label after successful validated trend computation.
