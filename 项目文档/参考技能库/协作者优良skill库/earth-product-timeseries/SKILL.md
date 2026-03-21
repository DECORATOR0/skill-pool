---
name: earth-product-timeseries
description: Solves Earth-Bench non-RGB product questions involving multi-date raster statistics, direct aggregation of existing products, derived index products, snow, water quality, fire, temperature conversion, and period comparison. Use for rainfall, nighttime light, vegetation coverage, NDSI, NDWI, NDTI, NBR, turbidity, hotspot, fire, or trend-analysis tasks.
allowed-tools: Read, Glob, Grep, Bash(python *), Edit
---

# Earth Product Time-Series

Use this skill for `Autonomous Planning` questions in the product domain.

Typical benchmark families covered by this skill:

- generic multi-date raster statistics
- rainfall or nighttime-light average/difference
- vegetation coverage trend/statistics
- snow workflows around `NDSI`
- water, turbidity, or hotspot analysis
- fire/snow/water product comparison
- Kelvin-to-Celsius conversion after thermal aggregation

This skill handles both:

- existing product series already stored as target rasters
- raw bands that must be converted into a product before aggregation

## Skill Objective

Produce a benchmark-faithful product workflow:

`get_filelist -> optional product derivation -> period aggregation/statistics -> comparison or trend`

This skill corrects the weaknesses of the older plan-only flow:

- recomputing products unnecessarily when files are already derived products
- skipping canonical tails like `mean`, `difference`, `percentage_change`
- mixing snow/fire/water specialist routes with generic raster statistics

## Tool Scope

Core tools for this skill:

- `get_filelist`
- `calc_batch_image_mean`
- `calc_batch_image_mean_mean`
- `mean`
- `difference`
- `percentage_change`
- `max_value_and_index`
- `min_value_and_index`
- `compute_linear_trend`
- `calculate_tif_average`
- `calculate_tif_difference`
- `calc_batch_image_sum`
- `calc_batch_image_hotspot_percentage`
- `coefficient_of_variation`
- `kurtosis`
- `kelvin_to_celsius`
- `division`
- `multiply`
- `mann_kendall_test`
- `index_to_date_range`
- `calculate_batch_ndsi`
- `calculate_ndwi`
- `calculate_ndti`
- `calculate_nbr`
- `calculate_water_turbidity_ntu`
- `apply_cloud_mask`
- `calc_batch_fire_pixels`
- `identify_fire_prone_areas`

## First Decision Rule

Before choosing a transform, decide which of these two branches the question belongs to:

1. Existing product series:
The filenames or directory already suggest NDVI/NDSI/NDTI/NDWI/nighttime light/rainfall/coverage products.
In this branch, aggregate directly.

2. Raw input bands:
The files are raw bands or raw reflectance/thermal rasters.
In this branch, derive the needed product once, then aggregate.

This distinction is critical. Do not recompute an index when the benchmark family uses the existing product rasters directly.

## Family Rules

1. Generic period statistics:
For two-region or two-period average comparisons, prefer:

`calc_batch_image_mean -> calc_batch_image_mean -> mean -> mean -> difference`

2. Trend:
For many-year change analysis, prefer:

`calc_batch_image_mean -> compute_linear_trend`

or an equivalent benchmark-faithful variant if yearly means are already explicit.

3. Snow:
If the question is about snow cover or NDSI:
- use `calculate_batch_ndsi` when raw inputs require deriving NDSI
- otherwise aggregate the existing NDSI products directly

4. Water / turbidity:
Use `calculate_ndwi`, `calculate_ndti`, or `calculate_water_turbidity_ntu` only when the files require derivation.

5. Fire / hotspot:
Prefer the fire-specific route when the question explicitly asks for fire-prone areas, hotspot percentage, or burn-related changes.

6. Temperature conversion:
If the question asks for Celsius values, apply `kelvin_to_celsius` after the relevant aggregation stage, not before every intermediate step unless required.

## Stepwise Execution Pattern

1. Call `get_filelist`.
2. Decide whether the inputs are raw or already products.
3. If raw, derive the target product.
4. Aggregate by date, region, or period.
5. Apply the requested tail:
   - `difference`
   - `percentage_change`
   - `max_value_and_index`
   - `min_value_and_index`
   - `compute_linear_trend`
   - `coefficient_of_variation`
   - `kurtosis`
6. Stop when enough evidence exists for the final multiple-choice selection.

## Parameter Selection Policy

Use the sequential parameter worker from `agent/skill_eval/parameter_worker.py`.

At each step:

1. Build the prompt with current context
2. Add `Relevant datas are stored at {data path}`
3. Include the routed tool descriptions and args schema
4. Ask for one tool call
5. Execute
6. Append observation
7. Continue

## Optimization Notes

This skill intentionally preserves benchmark tails that were often missing in the old single-agent plan:

- explicit paired aggregation blocks for two-region comparisons
- direct existing-product aggregation
- snow/fire/water family-specific routes
- post-aggregation `difference` or `percentage_change`

## Stop Conditions

Stop when:

- the requested region/period statistic is computed
- the comparison or trend value is available
- an additional tool call would not materially change the answer-choice decision

The final 4-choice answer selection is performed after this skill finishes.
