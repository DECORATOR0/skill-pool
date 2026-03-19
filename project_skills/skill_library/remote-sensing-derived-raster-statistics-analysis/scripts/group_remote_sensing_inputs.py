import os
import re
import json
import sys
from collections import defaultdict

# Usage:
# python group_remote_sensing_inputs.py <directory> <sensor> <band1> [<band2> ...]
# Outputs JSON to stdout.

BAND_PAT = re.compile(r'(b\d{2}|B\d{1,2}|BT10)', re.IGNORECASE)
TS_PAT = re.compile(r'(\d{4}_\d{2}_\d{2})(?:_(\d{4}))?')


def extract_band(name):
    m = BAND_PAT.search(name)
    return m.group(1).lower() if m else None


def extract_timestamp(name):
    m = TS_PAT.search(name)
    if not m:
        return None
    d, hm = m.groups()
    return f"{d}_{hm}" if hm else d


def main():
    directory = sys.argv[1]
    sensor = sys.argv[2].lower()
    required = [b.lower() for b in sys.argv[3:]]
    groups = defaultdict(dict)
    for fn in os.listdir(directory):
        if not fn.lower().endswith('.tif'):
            continue
        ts = extract_timestamp(fn)
        band = extract_band(fn)
        if ts and band:
            groups[ts][band] = os.path.join(directory, fn)
    complete = []
    incomplete = []
    for ts in sorted(groups):
        missing = [b for b in required if b not in groups[ts]]
        if missing:
            incomplete.append({"timestamp": ts, "missing": missing})
        else:
            complete.append({
                "timestamp": ts,
                "bands": {b: groups[ts][b] for b in required}
            })
    json.dump({
        "sensor": sensor,
        "required_bands": required,
        "complete_groups": complete,
        "incomplete_groups": incomplete
    }, sys.stdout, indent=2)


if __name__ == '__main__':
    main()
