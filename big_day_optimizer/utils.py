# big_day_optimizer/utils.py
"""
Helpers for translating 4‑ to 7‑letter eBird species codes into their
English common names and for turning an Itinerary into a tidy DataFrame.
"""
from __future__ import annotations
from importlib import resources
import re
from pathlib import Path
from typing import Dict

import pandas as pd

# ------------------------------------------------------------------
# 1.  Species-code -> Common-name lookup
# ------------------------------------------------------------------
def _taxonomy_from_csv(path: Path) -> Dict[str, str]:
    tax = pd.read_csv(path, comment="#", dtype=str, low_memory=False)
    return dict(zip(tax["SPECIES_CODE"].str.lower(), tax["PRIMARY_COM_NAME"]))


def _load_taxonomy(csv_path: str | None = None) -> Dict[str, str]:
    """
    Return {species_code: common_name}.

    Prefer the taxonomy bundled with the installed package. An explicit
    csv_path or root-level development CSV still works as a fallback.
    """
    if csv_path:
        explicit_path = Path(csv_path)
        if explicit_path.exists():
            return _taxonomy_from_csv(explicit_path)

    try:
        taxonomy_resource = resources.files("big_day_optimizer").joinpath(
            "data/eBird_taxonomy_v2024.csv"
        )
        with resources.as_file(taxonomy_resource) as taxonomy_path:
            if taxonomy_path.exists():
                return _taxonomy_from_csv(taxonomy_path)
    except (FileNotFoundError, ModuleNotFoundError):
        pass

    dev_path = Path("eBird_taxonomy_v2024.csv")
    if dev_path.exists():
        return _taxonomy_from_csv(dev_path)
    return {}

_CODE2NAME = _load_taxonomy()
_CODE_RE   = re.compile(r"\b([a-z0-9]{6}[0-9]?)\b", re.I)

def translate_codes(text: str) -> str:
    """Replace every six-letter eBird code by 'code (Common Name)'."""
    return _CODE_RE.sub(
        lambda m: f"{m.group(1)} ({_CODE2NAME.get(m.group(1).lower(), m.group(1))})",
        text
    )

# ------------------------------------------------------------------
# 2.  Itinerary ➜ DataFrame
# ------------------------------------------------------------------
def itinerary_to_df(iti, *, translate: bool = True) -> pd.DataFrame: 
    """
    Convert an `Itinerary` object into a tidy DataFrame with one row per leg.

    Parameters
    ----------
    iti : big_day_optimizer.solver.Itinerary
    translate : bool, default True
        If True, species codes become 'code (Common Name)'.

    Returns
    -------
    pandas.DataFrame with columns:
        leg, site, arrive, depart, drive_min, expected_new_sp, dwell_min, species
    """
    rows = iti.leg_rows()
    for row in rows:
        if translate:
            row["species"] = translate_codes(row["species"])
    return pd.DataFrame(rows)
