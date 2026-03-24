Pairing and yearly grouping
- Match `*_YYYY-MM-DD_LST.tif` with `*_YYYY-MM-DD_NDVI.tif` using shared prefix+date.
- Sort matched pairs by date ascending, then group by year.
- A year is usable if it has matched NDVI/LST pairs available in the environment.

Path convention
- Prefer relative output requests such as:
  - `question1/tvdi_2019-01-01.tif`
  - `question1/tvdi_annual_avg_2019.tif`
- But after a tool returns paths like `benchmark/out/question1/...`, use those returned paths downstream.
- Do not rewrite returned absolute/runtime paths back into guessed relative paths.

Incomplete requested years
- If prompt asks for 2019-2023 but files exist only for 2019-2022, state that 2023 is unavailable.
- Continue with available years if enough data exists for the requested trend analysis.
- Keep two separate statements in the final answer:
  1. analytical result on available years
  2. any benchmark/MCQ choice selected from that result

MCQ mapping rule
1. Compute the numeric slope.
2. Read all options.
3. Filter by correct direction/sign when possible.
4. If options contain numbers or magnitudes, choose the numerically closest directionally consistent option.
5. Do not replace this with a sign-only semantic guess just because no option exactly matches the computed value.
6. If coverage is incomplete, still map from the computed available-data slope and note the limitation separately.

Compact example
- Computed slope: `-0.0197/year`
- Choices include decreasing options `B=-0.037/year` and `C=slight increase`
- Correct policy: eliminate wrong-direction options; among decreasing options choose the closest supported one, so `B`, not a freeform semantic fallback.
