import json
import os
import re
import sys
from collections import defaultdict

DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def load_args():
    if len(sys.argv) > 1:
        return json.loads(sys.argv[1])
    return json.load(sys.stdin)


def main():
    args = load_args()
    data_dir = args["data_dir"]
    files = args["files"]
    output_dir = args.get("output_dir", "benchmark/out/tvdi")

    ndvi_by_date = {}
    lst_by_date = {}

    for name in files:
        base = os.path.basename(name)
        m = DATE_RE.search(base)
        if not m:
            continue
        date = m.group(1)
        full_path = name if os.path.isabs(name) or name.startswith(data_dir) else os.path.join(data_dir, name)
        if base.endswith("_NDVI.tif"):
            ndvi_by_date[date] = full_path
        elif base.endswith("_LST.tif"):
            lst_by_date[date] = full_path

    matched_dates = sorted(set(ndvi_by_date) & set(lst_by_date))
    unmatched_ndvi_dates = sorted(set(ndvi_by_date) - set(lst_by_date))
    unmatched_lst_dates = sorted(set(lst_by_date) - set(ndvi_by_date))

    years = sorted({d[:4] for d in matched_dates})
    lst_paths = [lst_by_date[d] for d in matched_dates]
    ndvi_paths = [ndvi_by_date[d] for d in matched_dates]
    tvdi_output_paths = [os.path.join(output_dir, f"tvdi_{d}.tif") for d in matched_dates]

    year_to_tvdi_outputs = defaultdict(list)
    for d, outp in zip(matched_dates, tvdi_output_paths):
        year_to_tvdi_outputs[d[:4]].append(outp)

    result = {
        "years": years,
        "matched_dates": matched_dates,
        "lst_paths": lst_paths,
        "ndvi_paths": ndvi_paths,
        "tvdi_output_paths": tvdi_output_paths,
        "year_to_tvdi_outputs": dict(year_to_tvdi_outputs),
        "unmatched_ndvi_dates": unmatched_ndvi_dates,
        "unmatched_lst_dates": unmatched_lst_dates,
        "matched_pair_count": len(matched_dates),
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
