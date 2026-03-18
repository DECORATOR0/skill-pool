Filename pairing and coverage notes for annual NDVI+LST TVDI trend tasks.

Pairing rule:
- Extract the `YYYY-MM-DD` token from each filename.
- Build `date -> LST filename` and `date -> NDVI filename` maps.
- Use the sorted intersection of dates.
- Never fabricate a missing partner file.

Coverage rule:
- If the prompt requests years beyond available matched years, compute on available years and say so explicitly.
- Typical benchmark pattern: data may cover 2019–2022 only, not 2023.
- Typical discrepancy pattern: one LST date may be present without the NDVI counterpart (for example around 2022-10-16); skip unmatched dates.

Tool order:
1. `get_filelist`
2. `compute_tvdi`
3. `calculate_tif_average` once per year
4. `calc_batch_image_mean`
5. `compute_linear_trend`

Anti-loop rule:
- After a successful `get_filelist`, never keep calling it to make progress.
- If the same listing was already seen, continue by parsing filenames and invoking downstream tools.