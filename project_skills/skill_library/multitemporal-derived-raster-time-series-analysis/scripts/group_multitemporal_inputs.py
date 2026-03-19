from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from typing import Dict, List, Tuple

DATE_PATTERNS = [
    re.compile(r'(20\d{2}[01]\d[0-3]\d(?:[T_]?\d{4,6})?)'),
    re.compile(r'(20\d{2}[-_][01]\d[-_][0-3]\d(?:[-_T]\d{2}[-_]?\d{2}(?:[-_]?\d{2})?)?)'),
]


def extract_stamp(name: str) -> str | None:
    for pat in DATE_PATTERNS:
        m = pat.search(name)
        if m:
            return m.group(1)
    return None


def classify(name: str) -> str | None:
    low = name.lower()
    if 'b02' in low:
        return 'b02'
    if 'b05' in low:
        return 'b05'
    if 'b17' in low:
        return 'b17'
    if 'b18' in low:
        return 'b18'
    if 'b19' in low:
        return 'b19'
    if 'band 31' in low or 'band31' in low or 'bt_31' in low or 'b31' in low:
        return 'band31'
    if 'band 32' in low or 'band32' in low or 'bt_32' in low or 'b32' in low:
        return 'band32'
    if 'bt10' in low or 'bt_10' in low:
        return 'bt10'
    if re.search(r'(^|[^0-9])b4([^0-9]|$)', low):
        return 'b4'
    if re.search(r'(^|[^0-9])b5([^0-9]|$)', low):
        return 'b5'
    return None


def main() -> None:
    files = json.load(sys.stdin)
    grouped: Dict[str, Dict[str, str]] = defaultdict(dict)
    for path in files:
        name = os.path.basename(path)
        stamp = extract_stamp(name)
        band = classify(name)
        if stamp and band:
            grouped[stamp][band] = path

    modis_required = ['b02', 'b05', 'b17', 'b18', 'b19']
    split_required = ['band31', 'band32']
    single_required = ['bt10', 'b4', 'b5']

    out = {
        'modis_band_ratio': [],
        'lst_split_window': [],
        'lst_single_channel': [],
    }

    for stamp in sorted(grouped):
        g = grouped[stamp]
        if all(k in g for k in modis_required):
            out['modis_band_ratio'].append({'stamp': stamp, **{k: g[k] for k in modis_required}})
        if all(k in g for k in split_required):
            out['lst_split_window'].append({'stamp': stamp, **{k: g[k] for k in split_required}})
        if all(k in g for k in single_required):
            out['lst_single_channel'].append({'stamp': stamp, **{k: g[k] for k in single_required}})

    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
