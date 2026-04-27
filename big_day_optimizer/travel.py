
"""OSRM distance helper (adaptive, robust).

*   Respects the 100‑coordinate / 10 000‑cell limits of the public demo.
*   Handles 429 *Too Many Requests* with exponential back‑off.
*   Gracefully fills in \"NoRoute\" gaps using a straight‑line estimate.
"""

from __future__ import annotations

import itertools
import logging
import math
import time
from typing import Sequence

import numpy as np
import requests
from geopy.distance import geodesic

from .config import OSRM_ROOT, DEFAULT_USER_AGENT

OSRM = f"{OSRM_ROOT.rstrip('/')}/table/v1/driving"
BASE_SLEEP   = 0.2      # polite pause between calls (seconds)
COORD_LIMIT  = 100      # <= 100 coordinates per request
CELL_LIMIT   = 10_000   # rows * cols <= 10 000
MAX_RETRIES  = 5
BACKOFF_FACTOR = 2.0

HEADERS = {"User-Agent": DEFAULT_USER_AGENT}


def _straight_line_minutes(p1, p2, kmh: float = 70.0):
    """Fallback: geodesic time at *kmh* average speed."""
    km = geodesic(p1, p2).km
    return int(round((km / kmh) * 60))


def _call_osrm(coords: list[tuple[float, float]],
               rows: list[int],
               cols: list[int]) -> list[list[float]]:
    qs_coords = ";".join(f"{lon},{lat}" for lat, lon in coords)
    qs_src    = ";".join(map(str, rows))
    qs_dst    = ";".join(map(str, cols))
    url = f"{OSRM}/{qs_coords}?sources={qs_src}&destinations={qs_dst}"

    sleep = BASE_SLEEP
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(url, timeout=60, headers=HEADERS)
            if r.status_code == 429:
                raise requests.HTTPError("429 Too Many Requests", response=r)

            r.raise_for_status()
            return r.json()["durations"]

        except (requests.ConnectionError, requests.Timeout):
            logging.warning("OSRM connection issue, retry %s/%s", attempt, MAX_RETRIES)

        except requests.HTTPError as e:
            if e.response.status_code == 400:
                try:
                    err_json = e.response.json()
                    if err_json.get("code") == "NoRoute":
                        logging.warning("NoRoute encountered; using straight‑line fallback")
                        raise ValueError("NoRoute")
                except ValueError:
                    pass  # JSON parse failed

            if 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                raise

        time.sleep(sleep)
        sleep *= BACKOFF_FACTOR

    raise RuntimeError(f"OSRM failed after {MAX_RETRIES} retries: {url[:120]}")
  

def osrm_matrix(latlons: Sequence[tuple[float, float]],
                block: int | None = None) -> list[list[int]]:
    """Return full *N×N* drive‑time matrix (minutes).

    If *block* is None we pick the largest that fits the public OSRM limits.
    Fallbacks: 429 -> exponential back‑off; NoRoute -> straight‑line estimate.
    """
    n = len(latlons)
    if n <= 1:
        return [[0] for _ in range(n)]

    if block is None:
        block = min(COORD_LIMIT // 2, int(math.floor(math.sqrt(CELL_LIMIT))))

    M = np.zeros((n, n), dtype=int)

    def _process_submatrix(r_idx: range, c_idx: range):
        union = list(dict.fromkeys(itertools.chain(r_idx, c_idx)))
        if len(union) > COORD_LIMIT or len(r_idx)*len(c_idx) > CELL_LIMIT:
            raise ValueError("Block size too large for OSRM limits")
        coords = [latlons[i] for i in union]
        idx_lookup = {idx: pos for pos, idx in enumerate(union)}
        rows = [idx_lookup[i] for i in r_idx]
        cols = [idx_lookup[j] for j in c_idx]

        try:
            sub = _call_osrm(coords, rows, cols)
            null_fallback = False
        except ValueError as e:
            if str(e) == "NoRoute":
                # Build fallback matrix with None placeholders
                sub = [[None]*len(c_idx) for _ in rows]
                null_fallback = True
            else:
                raise

        for rr, i in enumerate(r_idx):
            for cc, j in enumerate(c_idx):
                val = sub[rr][cc] if sub else None
                if val is None:
                    minutes = _straight_line_minutes(latlons[i], latlons[j])
                else:
                    minutes = int(round(val / 60))
                M[i, j] = minutes

    current_block = block
    while True:
        try:
            for r_start in range(0, n, current_block):
                r_rng = range(r_start, min(r_start+current_block, n))
                for c_start in range(0, n, current_block):
                    c_rng = range(c_start, min(c_start+current_block, n))
                    _process_submatrix(r_rng, c_rng)
            break
        except RuntimeError as e:
            if "429" in str(e):
                logging.warning("Rate‑limited; sleeping and retrying with smaller block")
                time.sleep(5)
                current_block = max(10, current_block // 2)
            else:
                raise

    return M.tolist()
