
"""High‑level convenience wrapper around the solver.

Example
-------
opt = BigDayOptimizer(api_key="XYZ", region="US-VA-107", include_depot=False)
iti = opt.solve()
print(iti.to_markdown())
"""
from __future__ import annotations
import datetime as dt
import logging
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from .ebird_api import hotspots_df, species_prob_by_loc
from .solver    import solve_itinerary, Itinerary
from .travel    import osrm_matrix

def _ensure_datetime(obj):
    """Accept dt.datetime, dt.time, or 'HH:MM' string → dt.datetime (today)."""
    if isinstance(obj, dt.datetime):
        return obj
    today = dt.date.today()
    if isinstance(obj, dt.time):
        return dt.datetime.combine(today, obj)
    if isinstance(obj, str):
        try:
            t = dt.datetime.strptime(obj, "%H:%M").time()
        except ValueError:
            raise ValueError(f"Time string '{obj}' must be HH:MM")
        return dt.datetime.combine(today, t)
    raise TypeError("start_time/end_time must be datetime, time, or 'HH:MM' string")


def _ensure_date(obj):
    """Accept date, datetime, ISO YYYY-MM-DD string, or None."""
    if obj is None:
        return None
    if isinstance(obj, dt.datetime):
        return obj.date()
    if isinstance(obj, dt.date):
        return obj
    if isinstance(obj, str):
        try:
            return dt.date.fromisoformat(obj)
        except ValueError:
            raise ValueError(f"Date string '{obj}' must be YYYY-MM-DD")
    raise TypeError("observation_date must be date, datetime, ISO date string, or None")


@dataclass
class BigDayOptimizer:
    api_key: str
    region: str
    include_depot: bool = False
    depot_locid: Optional[str] = None
    back: int = 7
    observation_date: Optional[dt.date | dt.datetime | str] = None
    same_dates_last_year: bool = False
    historical_years: int = 0
    include_recent: bool = True
    max_checklists_per_day: int = 50
    max_hotspots: Optional[int] = None

    # time window
    start_time: dt.datetime = field(
        default_factory=lambda: dt.datetime(dt.datetime.now().year, 5, 2, 5, 30))
    end_time: dt.datetime   = field(
        default_factory=lambda: dt.datetime(dt.datetime.now().year, 5, 2, 20, 30))

    # dwell parameters
    base_idle: int = 30
    dwell_per: int = 2

    # stop limits
    min_stops: int = 3
    max_stops: int = 5

    # gain matrix settings
    min_prob: float = 0.03
    int_scale: int = 1_000
    probability_steps: int = 100

    # solver settings
    nearby_drive_min: int = 8
    nearby_pair_penalty: float = 0.15
    time_limit: int = 60

    # internal cache
    hotspots: pd.DataFrame = field(init=False, default=None)
    travel: list[list[int]] = field(init=False, default=None)
    prob_by_loc: dict = field(init=False, default=None)

    def __post_init__(self) -> None:
        if self.depot_locid is not None:
            self.include_depot = True

    def prepare(self) -> None:
        """Download/calculate all data needed for optimisation."""
        logging.info("Fetching hotspots for %s", self.region)
        self.hotspots = hotspots_df(self.api_key, self.region)
        if self.include_depot and not self.depot_locid:
            raise ValueError("depot_locid is required when include_depot=True")
        if self.include_depot and self.depot_locid not in set(self.hotspots.locId):
            raise ValueError(f"depot_locid {self.depot_locid!r} is not a hotspot in {self.region}")
        if self.max_hotspots is not None:
            if self.max_hotspots <= 0:
                raise ValueError("max_hotspots must be positive")
            candidate_mask = self.hotspots.index < self.max_hotspots
            if self.include_depot:
                candidate_mask = candidate_mask | (self.hotspots.locId == self.depot_locid)
            self.hotspots = self.hotspots[candidate_mask].reset_index(drop=True)

        logging.info(
            "Fetching checklist probabilities (back=%d, historical_years=%d, include_recent=%s)…",
            self.back,
            max(self.historical_years, 1 if self.same_dates_last_year else 0),
            self.include_recent,
        )
        self.prob_by_loc = species_prob_by_loc(
            api_key=self.api_key,
            hotspots=self.hotspots,
            back=self.back,
            as_of=_ensure_date(self.observation_date),
            same_dates_last_year=self.same_dates_last_year,
            historical_years=self.historical_years,
            include_recent=self.include_recent,
            max_checklists_per_day=self.max_checklists_per_day,
        )

        self.hotspots["n_species"] = [
            len(self.prob_by_loc[loc]) for loc in self.hotspots.locId
        ]
        active = self.hotspots.n_species > 0
        if self.include_depot:
            active = active | (self.hotspots.locId == self.depot_locid)
        self.hotspots = self.hotspots[active].reset_index(drop=True)
        if self.hotspots.empty:
            raise RuntimeError("No hotspots with recent activity in region.")

        logging.info("Building travel matrix (%d hotspots)…", len(self.hotspots))
        latlons = list(zip(self.hotspots.lat, self.hotspots.lng))
        self.travel = osrm_matrix(latlons)

    # -----------------------------------------------------------------
    def solve(self) -> Itinerary:
        """Run the optimisation and return an Itinerary."""
        if self.hotspots is None:
            self.prepare()
        iti = solve_itinerary(
            hotspots=self.hotspots,
            travel=self.travel,
            prob_by_loc=self.prob_by_loc,
            include_depot=self.include_depot,
            depot_locid=self.depot_locid,
            start_time=_ensure_datetime(self.start_time),
            end_time=_ensure_datetime(self.end_time),
            base_idle=self.base_idle,
            dwell_per=self.dwell_per,
            min_stops=self.min_stops,
            max_stops=self.max_stops,
            min_prob=self.min_prob,
            int_scale=self.int_scale,
            probability_steps=self.probability_steps,
            nearby_drive_min=self.nearby_drive_min,
            nearby_pair_penalty=self.nearby_pair_penalty,
            time_limit=self.time_limit,
        )
        return iti
