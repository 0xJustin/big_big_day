
"""Thin wrapper around the **ebird.api** package.

We expose just the helpers the optimiser needs,
while hiding pandas & caching details from the rest of the code base.
"""

from functools import lru_cache
from datetime import date, datetime, timedelta
import collections
from typing import Iterable, Optional, Sequence

import pandas as pd
from ebird.api import (
    get_hotspots,
    get_visits,
    get_checklist,
)
import time

__all__ = [
    "hotspots_df",
    "species_prob_by_loc",
]

# ------------------------------------------------------------------
# Hotspots
# ------------------------------------------------------------------
@lru_cache(maxsize=None)
def hotspots_df(api_key: str, region: str) -> pd.DataFrame:
    """Return a DataFrame with hotspot meta‑data for *region*.

    Columns: locId, locName, lat, lng
    """
    hs = get_hotspots(api_key, region)
    return pd.DataFrame(hs)[["locId", "locName", "lat", "lng"]]


# ------------------------------------------------------------------
# Species probabilities
# ------------------------------------------------------------------
def _coerce_date(value: Optional[date | datetime | str]) -> date:
    if value is None:
        return date.today()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError("as_of must be a date, datetime, ISO date string, or None")


def _shift_year(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year - years)
    except ValueError:
        # Feb 29 has no same calendar date in non-leap years.
        return d.replace(year=d.year - years, day=28)


def _date_window(as_of: date, *, back: int) -> list[date]:
    if back <= 0:
        raise ValueError("back must be positive")
    return [as_of - timedelta(days=i) for i in range(back)]


def _sampling_dates(
    *,
    back: int = 7,
    as_of: Optional[date | datetime | str] = None,
    same_dates_last_year: bool = False,
    historical_years: int = 0,
    include_recent: bool = True,
    today: Optional[date] = None,
) -> list[date]:
    """Dates to sample for probability estimation.

    Current-year dates later than today are skipped because eBird has no
    checklist data for future dates.  Historical sampling adds the same
    calendar-date window from each requested prior year.
    """
    anchor = _coerce_date(as_of)
    today = today or date.today()
    if historical_years < 0:
        raise ValueError("historical_years cannot be negative")
    if same_dates_last_year:
        historical_years = max(historical_years, 1)

    dates: list[date] = []
    if include_recent:
        dates.extend(d for d in _date_window(anchor, back=back) if d <= today)
    for years_back in range(1, historical_years + 1):
        dates.extend(_shift_year(d, years_back) for d in _date_window(anchor, back=back))
    if not dates:
        raise ValueError("No sampling dates selected; enable recent data or at least one historical year")
    return list(dict.fromkeys(dates))


def _with_retry(fn, *args, retries: int = 2, delay: float = 2.0, **kwargs):
    for attempt in range(retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception:
            if attempt >= retries:
                raise
            time.sleep(delay)


def _checklists_for_dates(
    api_key: str,
    loc_id: str,
    dates: Iterable[date],
    *,
    max_checklists_per_day: int = 50,
) -> list[str]:
    """List unique checklist IDs for a hotspot over exact sample dates."""
    if max_checklists_per_day <= 0:
        raise ValueError("max_checklists_per_day must be positive")

    sub_ids: list[str] = []
    seen: set[str] = set()
    for d in dates:
        visits = _with_retry(
            get_visits,
            api_key,
            loc_id,
            d.isoformat(),
            max_results=max_checklists_per_day,
        ) or []
        for visit in visits:
            sub_id = visit.get("subId")
            if sub_id and sub_id not in seen:
                seen.add(sub_id)
                sub_ids.append(sub_id)
    return sub_ids


def _species_codes_from_checklist(checklist) -> set[str]:
    """Extract one presence/absence species set from an eBird checklist payload."""
    if isinstance(checklist, list):
        observations = checklist
    elif isinstance(checklist, dict):
        observations = checklist.get("obs") or checklist.get("observations") or []
    else:
        observations = []

    species = set()
    for obs in observations:
        code = obs.get("speciesCode")
        if code:
            species.add(code)
    return species


@lru_cache(maxsize=50_000)
def _cached_checklist_species(api_key: str, sub_id: str) -> frozenset[str]:
    checklist = _with_retry(get_checklist, api_key, sub_id)
    return frozenset(_species_codes_from_checklist(checklist))


def _prob_vector_for_loc(
    api_key: str,
    loc_id: str,
    *,
    dates: Sequence[date],
    max_checklists_per_day: int = 50,
):
    """Return {speciesCode: P(species appears on a sampled checklist)}."""
    sub_ids = _checklists_for_dates(
        api_key,
        loc_id,
        dates,
        max_checklists_per_day=max_checklists_per_day,
    )
    if not sub_ids:
        return {}

    hits = collections.Counter()
    n_lists = 0
    for sub_id in sub_ids:
        species = _cached_checklist_species(api_key, sub_id)
        n_lists += 1
        hits.update(species)

    return {sp: hits[sp] / n_lists for sp in hits}


def species_prob_by_loc(
    api_key: str,
    hotspots: pd.DataFrame,
    *,
    back: int = 7,
    as_of: Optional[date | datetime | str] = None,
    same_dates_last_year: bool = False,
    historical_years: int = 0,
    include_recent: bool = True,
    max_checklists_per_day: int = 50,
):
    """Return {locId: {speciesCode: detection probability}} for every hotspot.

    Probabilities are checklist-level detection rates: a species counts at most
    once per checklist, then P is species-checklist hits divided by sampled
    checklists.  `historical_years` adds matching calendar windows from prior
    years; `same_dates_last_year=True` remains as a one-year compatibility alias.
    """
    dates = _sampling_dates(
        back=back,
        as_of=as_of,
        same_dates_last_year=same_dates_last_year,
        historical_years=historical_years,
        include_recent=include_recent,
    )
    return {
        row.locId: _prob_vector_for_loc(
            api_key,
            row.locId,
            dates=dates,
            max_checklists_per_day=max_checklists_per_day,
        )
        for row in hotspots.itertuples()
    }
