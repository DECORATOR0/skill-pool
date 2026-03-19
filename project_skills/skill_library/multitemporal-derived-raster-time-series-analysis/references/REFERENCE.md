Grouping and routing notes

1. Same-date grouping
- Match files by date or timestamp encoded in filenames.
- Keep only complete groups required by the chosen algorithm.
- Sort groups chronologically before any derived computation.

2. Algorithm families
- MODIS PWV / atmospheric absorption: `b02 b05 b17 b18 b19` -> `band_ratio`
- LST split-window: `Band 31 + Band 32` -> `lst_multi_channel`
- LST single-channel: `BT10 + b4 + b5` -> `lst_single_channel`

3. Downstream operation selection
- Annual/yearly average question -> `calc_batch_image_mean` -> yearly `mean`
- Trend/rate question -> yearly `mean` -> `compute_linear_trend`
- Single-date threshold proportion -> `calculate_threshold_ratio`
- Below-threshold proportion -> `calculate_threshold_ratio` then `difference` from 100
- Multi-date exceedance count -> `count_images_exceeding_threshold_ratio`
- Abrupt increase / spike events in ordered MODIS series -> `calc_batch_image_mean` then `count_spikes_from_values`

4. Reporting hygiene
- State if timestamps were dropped for incompleteness.
- Preserve date order in all lists.
- For multiple choice, report computed value first, then nearest option if needed.
