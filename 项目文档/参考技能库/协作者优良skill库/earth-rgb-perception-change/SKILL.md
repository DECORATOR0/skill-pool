---
name: earth-rgb-perception-change
description: Solves Earth-Bench RGB questions involving scene classification, object counting, visual grounding, geometric reasoning from detections, segmentation-based area measurement, and pre/post building change analysis. Use for RGB scene labels, counting, centroids, nearest objects, building area, destruction, recovery, or restoration tasks.
allowed-tools: Read, Glob, Grep, Bash(python *), Edit
---

# Earth RGB Perception And Change

Use this skill for RGB-image Earth-Bench questions.

This skill covers the main RGB families:

- scene classification with repeated `MSCN`
- counting with repeated `InstructSAM`
- visual grounding with `RemoteSAM`
- geometric reasoning from detections using `SM3Det`
- area measurement with `SAM2` or `ChangeOS`
- before/after building destruction or restoration

## Skill Objective

Produce a benchmark-faithful RGB workflow:

`get_filelist -> perception model family -> geometry/area/change tail`

This skill replaces the older planning weaknesses where:

- building region area was confused with `calculate_bbox_area`
- change questions were misrouted to detection-only geometry
- counting, grounding, and segmentation families were mixed together

## Tool Scope

Core tools for this skill:

- `get_filelist`
- `MSCN`
- `InstructSAM`
- `RemoteSAM`
- `SM3Det`
- `SAM2`
- `ChangeOS`
- `bboxes2centroids`
- `centroid_distance_extremes`
- `calculate_area`
- `calculate_bbox_area`
- `count_skeleton_contours`
- `get_list_object_via_indexes`
- `difference`
- `division`
- `multiply`
- `ceil_number`

## Family Rules

1. Scene classification:
If every image belongs to one category from a known set, use repeated `MSCN`.

2. Counting:
If the question asks how many objects of a certain type appear across images, use repeated `InstructSAM`.

3. Visual grounding:
If the question identifies a specific object by language and asks for centroid or location, use:

`RemoteSAM -> bboxes2centroids`

4. Detection geometry:
If the question asks for distances between detected objects, closest pair, or bounding-box retrieval, use:

`SM3Det -> bboxes2centroids -> centroid_distance_extremes`

Optionally use `multiply` for GSD conversion or `get_list_object_via_indexes` when the answer asks for the chosen bounding boxes.

5. Region area:
If the question asks for actual building area in pixels or square meters, prefer segmented region area:

- `ChangeOS -> calculate_area` for before/after building masks
- `SM3Det -> SAM2 -> calculate_area` when detection then segmentation is the canonical path

Do not default to `calculate_bbox_area` when the question means object-region area.

6. Change / destruction / restoration:
For pre/post building change, destruction count, or restored area, prefer `ChangeOS` and the change-specific tail:

- `calculate_area`
- `count_skeleton_contours`

## Stepwise Execution Pattern

1. Call `get_filelist`.
2. Identify the RGB family:
   - classification
   - counting
   - grounding
   - geometry
   - area/change
3. Reuse the same model family across files unless the benchmark family explicitly switches.
4. Apply the right tail tool.
5. Stop once enough evidence exists for the final answer choice.

## Parameter Selection Policy

Use the sequential parameter worker from `agent/skill_eval/parameter_worker.py`.

At each step:

1. Provide current context or the original question
2. Add `Relevant datas are stored at {data path}`
3. Add the rendered tool list and args schema
4. Request one next tool call
5. Execute it
6. Append the latest observation to context

## Optimization Notes

This skill preserves the benchmark distinctions that mattered most in the prior single-agent analysis:

- `building area` is region area, not box area
- `building change` is not plain detection difference
- counting is not grounding
- grounding is not segmentation
- `ChangeOS` should dominate building-damage and restoration questions

## Stop Conditions

Stop when:

- the count, centroid, distance, area, or destruction statistic has been computed
- the remaining work would only duplicate equivalent evidence

The final 4-choice answer selection is outside this skill.
