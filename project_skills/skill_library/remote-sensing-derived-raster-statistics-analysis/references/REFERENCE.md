Filename and routing guide

1. Landsat 8 branch
- Typical inputs: Band 4 (red), Band 5 (NIR), Band 10 or BT10.
- Use only for single-date class-comparison questions based on NDVI-defined groups and mean LST.

2. MODIS branch
- Expect timestamped reflectance filenames that encode date/time and band, commonly like `YYYY_MM_DD_HHMM_Reflectance_bXX.tif`.
- Group by timestamp first, then assign bands.
- Require exact band matching from the prompt.

3. MODIS statistic sub-branches
- Count of dates above/below threshold relative to annual/day mean:
  - `band_ratio` -> `calc_batch_image_mean` -> `mean` -> compare/count externally.
- Single-date or same-day threshold-area percentage:
  - `band_ratio` -> `calc_batch_image_mean` -> `mean` for reference mean if needed -> threshold calculation externally -> `calculate_threshold_ratio` per raster -> `mean` if multiple timestamps must be combined.
- If the prompt asks for a single percentage over one day with multiple timestamps, default to averaging the per-image percentages across all complete timestamps from that day unless another aggregation rule is stated.

4. Missing data policy
- Deterministically validate bundles before raster derivation.
- Report missing timestamps/bands explicitly.
- Do not invent substitutes or silently reorder files.
