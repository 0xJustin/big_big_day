from __future__ import annotations

import collections
import datetime as dt
import math
import time
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Iterable, Mapping, Sequence

import pandas as pd
from ebird.api import get_checklist, get_visits

from .ebird_api import hotspots_df


TIME_BUCKETS: tuple[tuple[str, dt.time, dt.time], ...] = (
    ("4-9 AM", dt.time(4, 0), dt.time(9, 0)),
    ("9 AM-12 PM", dt.time(9, 0), dt.time(12, 0)),
    ("12-4 PM", dt.time(12, 0), dt.time(16, 0)),
    ("4-8 PM", dt.time(16, 0), dt.time(20, 0)),
)

HOTSPOT_COLUMNS = [
    "locId",
    "locName",
    "checklists",
    "warbler_species",
    "warbler_individuals",
    "species_per_checklist",
    "individuals_per_checklist",
    "morning_species",
    "morning_individuals_per_checklist",
    "qualified_photo_items",
    "photo_items",
    "photo_score",
    "lat",
    "lng",
]

BUCKET_COLUMNS = [
    "locId",
    "locName",
    "time_bucket",
    "checklists",
    "warbler_species",
    "warbler_individuals",
    "species_per_checklist",
    "individuals_per_checklist",
]

SPECIES_COLUMNS = [
    "locId",
    "locName",
    "speciesCode",
    "species",
    "checklists",
    "checklist_rate",
    "individuals",
]


@dataclass(frozen=True)
class MigrantResults:
    region: str
    dates: tuple[dt.date, ...]
    checklist_count: int
    hotspot_count: int
    warbler_species_count: int
    warbler_individuals: int
    hotspot_summary: pd.DataFrame
    bucket_summary: pd.DataFrame
    species_summary: pd.DataFrame


def _with_retry(fn, *args, retries: int = 2, delay: float = 1.5, **kwargs):
    for attempt in range(retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception:
            if attempt >= retries:
                raise
            time.sleep(delay)


def _shift_year(value: dt.date, years: int) -> dt.date:
    try:
        return value.replace(year=value.year - years)
    except ValueError:
        return value.replace(year=value.year - years, day=28)


def recent_dates(days: int, *, today: dt.date | None = None) -> tuple[dt.date, ...]:
    if days <= 0:
        raise ValueError("days must be positive")
    anchor = today or dt.date.today()
    return tuple(anchor - dt.timedelta(days=offset) for offset in range(days))


def historical_dates(anchor: dt.date, *, days: int, years: int) -> tuple[dt.date, ...]:
    if days <= 0:
        raise ValueError("days must be positive")
    if years <= 0:
        raise ValueError("years must be positive")

    base_window = [anchor - dt.timedelta(days=offset) for offset in range(days)]
    dates: list[dt.date] = []
    for years_back in range(1, years + 1):
        dates.extend(_shift_year(day, years_back) for day in base_window)
    return tuple(dict.fromkeys(dates))


@lru_cache(maxsize=1)
def _taxonomy() -> pd.DataFrame:
    taxonomy_resource = resources.files("big_day_optimizer").joinpath("data/eBird_taxonomy_v2024.csv")
    with resources.as_file(taxonomy_resource) as taxonomy_path:
        return pd.read_csv(taxonomy_path, dtype=str, low_memory=False)


@lru_cache(maxsize=1)
def warbler_code_map() -> dict[str, str]:
    """Map eBird codes in Parulidae to canonical species-level codes."""
    taxonomy = _taxonomy().fillna("")
    species_rows = taxonomy[
        (taxonomy["CATEGORY"] == "species")
        & taxonomy["FAMILY"].str.contains("Parulidae", case=False, regex=False)
    ]
    canonical = set(species_rows["SPECIES_CODE"].str.lower())

    code_map: dict[str, str] = {}
    for row in taxonomy.itertuples(index=False):
        code = str(row.SPECIES_CODE).lower()
        report_as = str(row.REPORT_AS).lower()
        family = str(row.FAMILY)
        if code in canonical:
            code_map[code] = code
        elif report_as in canonical:
            code_map[code] = report_as
        elif "Parulidae" in family:
            code_map[code] = report_as if report_as in canonical else code
    return code_map


@lru_cache(maxsize=1)
def species_name_map() -> dict[str, str]:
    taxonomy = _taxonomy().fillna("")
    return dict(zip(taxonomy["SPECIES_CODE"].str.lower(), taxonomy["PRIMARY_COM_NAME"]))


def _coerce_date(value: dt.date | dt.datetime | str) -> dt.date:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(value)


def _parse_obs_datetime(value: object, fallback_date: dt.date | None = None) -> dt.datetime | None:
    if not value:
        return None
    raw = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return dt.datetime.strptime(raw[: len(fmt)], fmt)
        except ValueError:
            pass
    try:
        return dt.datetime.fromisoformat(raw)
    except ValueError:
        if fallback_date:
            for fmt in ("%H:%M", "%H:%M:%S"):
                try:
                    parsed = dt.datetime.strptime(raw, fmt).time()
                    return dt.datetime.combine(fallback_date, parsed)
                except ValueError:
                    pass
    return None


def time_bucket(value: dt.datetime | dt.time | None) -> str:
    if value is None:
        return "No time"
    observed = value.time() if isinstance(value, dt.datetime) else value
    for label, start, end in TIME_BUCKETS:
        if start <= observed < end:
            return label
    return "Other"


def _observations_from_checklist(checklist: object) -> list[Mapping[str, object]]:
    if isinstance(checklist, list):
        observations = checklist
    elif isinstance(checklist, Mapping):
        observations = checklist.get("obs") or checklist.get("observations") or []
    else:
        observations = []
    return [obs for obs in observations if isinstance(obs, Mapping)]


def _numeric_count(value: object) -> int:
    if value is None:
        return 1
    if isinstance(value, bool):
        return 1
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return max(1, int(round(float(value))))
    raw = str(value).strip()
    try:
        return max(1, int(round(float(raw))))
    except ValueError:
        return 1


def _float_from_keys(payload: Mapping[str, object], keys: Sequence[str]) -> float | None:
    lowered = {str(key).lower(): value for key, value in payload.items()}
    for key in keys:
        if key.lower() not in lowered:
            continue
        try:
            value = float(str(lowered[key.lower()]).strip())
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            return value
    return None


def _rating_count_from_keys(payload: Mapping[str, object], keys: Sequence[str]) -> int | None:
    lowered = {str(key).lower(): value for key, value in payload.items()}
    for key in keys:
        if key.lower() not in lowered:
            continue
        value = lowered[key.lower()]
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            return len(value)
        try:
            count = int(float(str(value).strip()))
        except (TypeError, ValueError):
            continue
        return max(0, count)
    return None


def _iter_dicts(value: object) -> Iterable[Mapping[str, object]]:
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _iter_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_dicts(child)


def photo_signal_from_checklist(checklist: object, *, min_rating: float = 4.5, min_ratings: int = 5) -> tuple[int, int]:
    """Return (qualified_photo_items, photo_items_with_rating_metadata)."""
    qualified = 0
    rated_items = 0
    rating_keys = ("rating", "avgRating", "averageRating", "starRating", "assetRating")
    count_keys = ("ratingCount", "ratingsCount", "numRatings", "rating_count", "ratings")

    for payload in _iter_dicts(checklist):
        rating = _float_from_keys(payload, rating_keys)
        rating_count = _rating_count_from_keys(payload, count_keys)
        if rating is None or rating_count is None:
            continue
        rated_items += 1
        if rating >= min_rating and rating_count >= min_ratings:
            qualified += 1
    return qualified, rated_items


@lru_cache(maxsize=100_000)
def _cached_checklist(api_key: str, sub_id: str):
    return _with_retry(get_checklist, api_key, sub_id)


def _visit_sub_id(visit: Mapping[str, object]) -> str | None:
    for key in ("subId", "subID", "sub_id"):
        value = visit.get(key)
        if value:
            return str(value)
    return None


def _checklist_field(checklist: object, visit: Mapping[str, object], keys: Sequence[str]) -> object:
    if isinstance(checklist, Mapping):
        for key in keys:
            value = checklist.get(key)
            if value:
                return value
    for key in keys:
        value = visit.get(key)
        if value:
            return value
    return None


def _sample_visits(
    api_key: str,
    region: str,
    dates: Sequence[dt.date],
    *,
    max_checklists_per_day: int,
) -> list[Mapping[str, object]]:
    visits_by_sub_id: dict[str, Mapping[str, object]] = {}
    for sample_date in dates:
        visits = _with_retry(
            get_visits,
            api_key,
            region,
            sample_date.isoformat(),
            max_results=max_checklists_per_day,
        ) or []
        for visit in visits:
            if not isinstance(visit, Mapping):
                continue
            sub_id = _visit_sub_id(visit)
            if sub_id:
                visits_by_sub_id.setdefault(sub_id, visit)
    return list(visits_by_sub_id.values())


def _checklist_rows(
    api_key: str,
    region: str,
    dates: Sequence[dt.date],
    *,
    max_checklists_per_day: int,
) -> list[dict[str, object]]:
    hotspots = hotspots_df(api_key, region)
    hotspot_lookup = {
        str(row.locId): {
            "locName": str(row.locName),
            "lat": float(row.lat),
            "lng": float(row.lng),
        }
        for row in hotspots.itertuples()
    }
    visits = _sample_visits(api_key, region, dates, max_checklists_per_day=max_checklists_per_day)
    canonical_warblers = warbler_code_map()

    rows: list[dict[str, object]] = []
    for visit in visits:
        sub_id = _visit_sub_id(visit)
        if not sub_id:
            continue
        checklist = _cached_checklist(api_key, sub_id)
        loc_id = _checklist_field(checklist, visit, ("locId", "locID", "locationId"))
        if not loc_id or str(loc_id) not in hotspot_lookup:
            continue

        fallback_date = None
        visit_date = _checklist_field(checklist, visit, ("obsDt", "obsDate", "date"))
        parsed_dt = _parse_obs_datetime(visit_date)
        if parsed_dt:
            fallback_date = parsed_dt.date()
        obs_datetime = parsed_dt or _parse_obs_datetime(
            _checklist_field(checklist, visit, ("time", "obsTime")),
            fallback_date=fallback_date,
        )

        warbler_species: set[str] = set()
        warbler_counts: collections.Counter[str] = collections.Counter()
        for obs in _observations_from_checklist(checklist):
            raw_code = str(obs.get("speciesCode") or "").lower()
            code = canonical_warblers.get(raw_code)
            if not code:
                continue
            count = _numeric_count(obs.get("howMany") or obs.get("count") or obs.get("individualCount"))
            warbler_species.add(code)
            warbler_counts[code] += count

        qualified_photos, photo_items = photo_signal_from_checklist(checklist)
        meta = hotspot_lookup[str(loc_id)]
        rows.append(
            {
                "subId": sub_id,
                "locId": str(loc_id),
                "locName": str(_checklist_field(checklist, visit, ("locName", "locationName")) or meta["locName"]),
                "obsDt": obs_datetime,
                "time_bucket": time_bucket(obs_datetime),
                "warbler_species_set": frozenset(warbler_species),
                "warbler_counts": dict(warbler_counts),
                "warbler_species": len(warbler_species),
                "warbler_individuals": int(sum(warbler_counts.values())),
                "qualified_photo_items": int(qualified_photos),
                "photo_items": int(photo_items),
                "lat": meta["lat"],
                "lng": meta["lng"],
            }
        )
    return rows


def _empty_results(region: str, dates: Sequence[dt.date]) -> MigrantResults:
    return MigrantResults(
        region=region,
        dates=tuple(dates),
        checklist_count=0,
        hotspot_count=0,
        warbler_species_count=0,
        warbler_individuals=0,
        hotspot_summary=pd.DataFrame(columns=HOTSPOT_COLUMNS),
        bucket_summary=pd.DataFrame(columns=BUCKET_COLUMNS),
        species_summary=pd.DataFrame(columns=SPECIES_COLUMNS),
    )


def analyze_migrant_hotspots(
    api_key: str,
    region: str,
    *,
    dates: Sequence[dt.date],
    max_checklists_per_day: int = 200,
    min_checklists_per_hotspot: int = 5,
) -> MigrantResults:
    if not api_key.strip():
        raise ValueError("api_key is required")
    if not region.strip():
        raise ValueError("region is required")
    if max_checklists_per_day <= 0:
        raise ValueError("max_checklists_per_day must be positive")
    if min_checklists_per_hotspot <= 0:
        raise ValueError("min_checklists_per_hotspot must be positive")

    dates = tuple(dict.fromkeys(_coerce_date(day) for day in dates))
    if not dates:
        raise ValueError("at least one sample date is required")

    rows = _checklist_rows(
        api_key,
        region,
        dates,
        max_checklists_per_day=max_checklists_per_day,
    )
    if not rows:
        return _empty_results(region, dates)

    checklist_df = pd.DataFrame(rows)
    checklist_df = checklist_df.groupby("locId").filter(lambda group: len(group) >= min_checklists_per_hotspot)
    if checklist_df.empty:
        return _empty_results(region, dates)

    name_lookup = checklist_df.groupby("locId")["locName"].first().to_dict()
    lat_lookup = checklist_df.groupby("locId")["lat"].first().to_dict()
    lng_lookup = checklist_df.groupby("locId")["lng"].first().to_dict()

    hotspot_rows: list[dict[str, object]] = []
    for loc_id, group in checklist_df.groupby("locId"):
        species_union = set().union(*group["warbler_species_set"].tolist()) if len(group) else set()
        morning = group[group["time_bucket"] == "4-9 AM"]
        morning_union = set().union(*morning["warbler_species_set"].tolist()) if len(morning) else set()
        checklists = int(len(group))
        hotspot_rows.append(
            {
                "locId": loc_id,
                "locName": name_lookup[loc_id],
                "checklists": checklists,
                "warbler_species": len(species_union),
                "warbler_individuals": int(group["warbler_individuals"].sum()),
                "species_per_checklist": float(group["warbler_species"].mean()),
                "individuals_per_checklist": float(group["warbler_individuals"].mean()),
                "morning_species": len(morning_union),
                "morning_individuals_per_checklist": float(morning["warbler_individuals"].mean())
                if len(morning)
                else 0.0,
                "qualified_photo_items": int(group["qualified_photo_items"].sum()),
                "photo_items": int(group["photo_items"].sum()),
                "photo_score": float(group["qualified_photo_items"].sum()) * 100.0 / checklists,
                "lat": lat_lookup[loc_id],
                "lng": lng_lookup[loc_id],
            }
        )
    hotspot_summary = (
        pd.DataFrame(hotspot_rows, columns=HOTSPOT_COLUMNS)
        .sort_values(
            ["warbler_species", "individuals_per_checklist", "checklists"],
            ascending=[False, False, False],
        )
        .reset_index(drop=True)
    )

    bucket_rows: list[dict[str, object]] = []
    for (loc_id, bucket), group in checklist_df.groupby(["locId", "time_bucket"]):
        species_union = set().union(*group["warbler_species_set"].tolist()) if len(group) else set()
        bucket_rows.append(
            {
                "locId": loc_id,
                "locName": name_lookup[loc_id],
                "time_bucket": bucket,
                "checklists": int(len(group)),
                "warbler_species": len(species_union),
                "warbler_individuals": int(group["warbler_individuals"].sum()),
                "species_per_checklist": float(group["warbler_species"].mean()),
                "individuals_per_checklist": float(group["warbler_individuals"].mean()),
            }
        )
    bucket_summary = (
        pd.DataFrame(bucket_rows, columns=BUCKET_COLUMNS)
        .sort_values(["time_bucket", "warbler_species", "individuals_per_checklist"], ascending=[True, False, False])
        .reset_index(drop=True)
    )

    species_rows: list[dict[str, object]] = []
    name_map = species_name_map()
    for loc_id, group in checklist_df.groupby("locId"):
        checklist_count = len(group)
        species_hits: collections.Counter[str] = collections.Counter()
        species_counts: collections.Counter[str] = collections.Counter()
        for _, row in group.iterrows():
            counts = row["warbler_counts"]
            for code, count in counts.items():
                species_hits[code] += 1
                species_counts[code] += int(count)
        for code, hits in species_hits.items():
            species_rows.append(
                {
                    "locId": loc_id,
                    "locName": name_lookup[loc_id],
                    "speciesCode": code,
                    "species": name_map.get(code, code),
                    "checklists": int(hits),
                    "checklist_rate": float(hits / checklist_count),
                    "individuals": int(species_counts[code]),
                }
            )
    species_summary = (
        pd.DataFrame(species_rows, columns=SPECIES_COLUMNS)
        .sort_values(["locName", "checklist_rate", "individuals"], ascending=[True, False, False])
        .reset_index(drop=True)
    )

    all_species = set().union(*checklist_df["warbler_species_set"].tolist()) if len(checklist_df) else set()
    return MigrantResults(
        region=region,
        dates=dates,
        checklist_count=int(len(checklist_df)),
        hotspot_count=int(checklist_df["locId"].nunique()),
        warbler_species_count=len(all_species),
        warbler_individuals=int(checklist_df["warbler_individuals"].sum()),
        hotspot_summary=hotspot_summary,
        bucket_summary=bucket_summary,
        species_summary=species_summary,
    )
