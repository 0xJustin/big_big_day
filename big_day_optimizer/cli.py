
"""Command‑line entry point for Big‑Day Optimizer.

Example
-------
python -m big_day_optimizer.cli \
    --api-key  ABC1234567890 \
    --region   US-VA-059 \
    --free-start
"""

import argparse
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from big_day_optimizer import BigDayOptimizer


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="big-day-optimizer",
        description="Plan an optimal birding route for a 1‑day big day",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # required
    p.add_argument("--api-key", required=True, help="Your eBird API token")
    p.add_argument("--region", required=True, help="eBird region code (e.g. US-VA-059)")

    # timing
    p.add_argument("--start-time", default="05:00", metavar="HH:MM",
                   help="Earliest time you can start birding (local)")

    p.add_argument("--end-time",   default="22:00", metavar="HH:MM",
                   help="Latest time you can still be in the field (local)")
    p.add_argument("--output_file_name", default="itinerary.csv",
                   help="Output file name (CSV)")
    p.add_argument("--depot_id", default=None,
                   help="Fixed starting hotspot ID (eBird locId)")
    p.add_argument("--observation-date", default=None, metavar="YYYY-MM-DD",
                   help="Anchor date for checklist sampling; defaults to today")

    # depot vs free start
    p.add_argument(
        "--free-start",
        action="store_true",
        help="Let the optimiser choose the first hotspot; this is the default when --depot_id is omitted.",
    )

    # other tweaks
    p.add_argument("--back", type=int, default=7,
                   help="Number of calendar days in each checklist sampling window")
    p.add_argument("--historical-years", type=int, default=0,
                   help="Number of prior years to sample using the same calendar-date window")
    p.add_argument("--no-recent-checklists", action="store_false", dest="include_recent",
                   help="Do not sample current-year checklist data")
    p.add_argument("--same-dates-last-year", action="store_true",
                   help="Deprecated alias for --historical-years 1")
    p.add_argument("--historical-only", action="store_true",
                   help="Deprecated alias for --no-recent-checklists; requires historical sampling")
    p.add_argument("--max-checklists-per-day", type=int, default=50,
                   help="Maximum eBird checklists to fetch per hotspot per sampled date")
    p.add_argument("--max-hotspots", type=int, default=None,
                   help="Maximum candidate hotspots to evaluate before solving")
    p.add_argument("--min-prob", type=float, default=0.03,
                   help="Minimum species-hotspot probability retained by the optimizer")
    p.add_argument("--max_stops", type=int, default=8,
                   help="Hard cap on hotspots in the final itinerary")
    p.add_argument("--nearby-drive-min", type=int, default=8,
                   help="Hotspots this many drive minutes apart are treated as nearby")
    p.add_argument("--nearby-pair-penalty", type=float, default=0.15,
                   help="Expected-species penalty for selecting two nearby hotspots")
    
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.free_start and args.depot_id is not None:
        parser.error("--free-start and --depot_id are mutually exclusive")
    historical_years = max(args.historical_years, 1 if args.same_dates_last_year else 0)
    include_recent = args.include_recent and not args.historical_only
    if args.historical_only and historical_years <= 0:
        parser.error("--historical-only requires --historical-years or --same-dates-last-year")

    opt = BigDayOptimizer(
        api_key       = args.api_key,
        region        = args.region,
        back          = args.back,
        observation_date = args.observation_date,
        same_dates_last_year = args.same_dates_last_year,
        historical_years = historical_years,
        include_recent = include_recent,
        max_checklists_per_day = args.max_checklists_per_day,
        max_hotspots = args.max_hotspots,
        min_prob = args.min_prob,
        nearby_drive_min = args.nearby_drive_min,
        nearby_pair_penalty = args.nearby_pair_penalty,
        start_time    = args.start_time,
        end_time      = args.end_time,
        include_depot = args.depot_id is not None,
        max_stops     = args.max_stops,
        depot_locid   = args.depot_id,
    )

    itinerary = opt.solve()
    iti = itinerary.to_dataframe()
    print(iti)
    iti.to_csv(args.output_file_name, index=False)


if __name__ == "__main__":
    main()
