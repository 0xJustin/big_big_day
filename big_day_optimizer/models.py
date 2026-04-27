"""Core dataclasses used across the package."""
from __future__ import annotations
import datetime as _dt
from dataclasses import dataclass
from typing import List, Dict, Tuple

@dataclass()
class Hotspot:
    idx: int
    loc_id: str
    name: str
    latitude: float
    longitude: float

@dataclass()
class SpeciesVisit:
    species_code: str
    first_observed: _dt.date
    last_observed: _dt.date
    n_years_seen: int
