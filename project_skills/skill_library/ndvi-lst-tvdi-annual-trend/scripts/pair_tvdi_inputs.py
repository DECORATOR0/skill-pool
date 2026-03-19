from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict

DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def classify(name: str):
    date_match = DATE_RE.search(name)
    if not date_match:
        return None
    date = date_match.group(1)
    upper = name.upper()
    if upper.endswith("_NDVI.TIF"):
        kind = "NDVI"
    elif upper.endswith("_LST.TIF"):
        kind = "LST"
    else:
        return None
    return date, kind


def main():
    files = json.load(sys.stdin)
    by_date = defaultdict(dict)
    for name in files:
        base = os.path.basename(name)
        parsed = classify(base)
        if not parsed:
            continue
        date, kind = parsed
        by_date[date][kind] = base

    pairs = []
    years = defaultdict(list)
    for date in sorted(by_date):
        item = by_date[date]
        if "NDVI" in item and "LST" in item:
            pair = {
                "date": date,
                "year": int(date[:4]),
                "ndvi_file": item["NDVI"],
                "lst_file": item["LST"],
            }
            pairs.append(pair)
            years[pair["year"]].append(date)

    result = {
        "pairs": pairs,
        "years": sorted(years.keys()),
        "pair_count": len(pairs),
        "year_to_dates": {str(y): years[y] for y in sorted(years)},
    }
    json.dump(result, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
