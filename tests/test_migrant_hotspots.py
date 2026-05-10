import datetime as dt
import unittest
from unittest.mock import patch

from big_day_optimizer import migrant_hotspots as mh


class MigrantHotspotTests(unittest.TestCase):
    def test_recent_and_historical_dates_are_inclusive_windows(self):
        self.assertEqual(
            mh.recent_dates(3, today=dt.date(2026, 5, 10)),
            (
                dt.date(2026, 5, 10),
                dt.date(2026, 5, 9),
                dt.date(2026, 5, 8),
            ),
        )
        self.assertEqual(
            mh.historical_dates(dt.date(2026, 5, 17), days=2, years=2),
            (
                dt.date(2025, 5, 17),
                dt.date(2025, 5, 16),
                dt.date(2024, 5, 17),
                dt.date(2024, 5, 16),
            ),
        )

    def test_time_bucket_boundaries(self):
        self.assertEqual(mh.time_bucket(dt.time(4, 0)), "4-9 AM")
        self.assertEqual(mh.time_bucket(dt.time(8, 59)), "4-9 AM")
        self.assertEqual(mh.time_bucket(dt.time(9, 0)), "9 AM-12 PM")
        self.assertEqual(mh.time_bucket(dt.time(12, 0)), "12-4 PM")
        self.assertEqual(mh.time_bucket(dt.time(16, 0)), "4-8 PM")
        self.assertEqual(mh.time_bucket(dt.time(20, 0)), "Other")
        self.assertEqual(mh.time_bucket(None), "No time")

    def test_photo_signal_counts_high_rated_items(self):
        checklist = {
            "obs": [
                {
                    "speciesCode": "bawwar",
                    "media": [
                        {"rating": 4.7, "ratingCount": 7},
                        {"avgRating": 4.4, "ratingsCount": 12},
                        {"averageRating": 4.9, "ratings": [1, 2, 3, 4, 5]},
                    ],
                }
            ]
        }
        self.assertEqual(mh.photo_signal_from_checklist(checklist), (2, 3))

    def test_analyze_summarizes_and_filters_hotspots(self):
        rows = [
            {
                "subId": "S1",
                "locId": "L1",
                "locName": "Ridge",
                "obsDt": dt.datetime(2025, 5, 17, 6, 15),
                "time_bucket": "4-9 AM",
                "warbler_species_set": frozenset({"bawwar", "amered"}),
                "warbler_counts": {"bawwar": 2, "amered": 1},
                "warbler_species": 2,
                "warbler_individuals": 3,
                "qualified_photo_items": 1,
                "photo_items": 2,
                "lat": 39.0,
                "lng": -77.0,
            },
            {
                "subId": "S2",
                "locId": "L1",
                "locName": "Ridge",
                "obsDt": dt.datetime(2025, 5, 17, 10, 15),
                "time_bucket": "9 AM-12 PM",
                "warbler_species_set": frozenset({"bawwar"}),
                "warbler_counts": {"bawwar": 1},
                "warbler_species": 1,
                "warbler_individuals": 1,
                "qualified_photo_items": 0,
                "photo_items": 1,
                "lat": 39.0,
                "lng": -77.0,
            },
            {
                "subId": "S3",
                "locId": "L2",
                "locName": "Thin Sample",
                "obsDt": dt.datetime(2025, 5, 17, 6, 15),
                "time_bucket": "4-9 AM",
                "warbler_species_set": frozenset({"ovenbi1"}),
                "warbler_counts": {"ovenbi1": 1},
                "warbler_species": 1,
                "warbler_individuals": 1,
                "qualified_photo_items": 5,
                "photo_items": 5,
                "lat": 39.1,
                "lng": -77.1,
            },
        ]
        with patch.object(mh, "_checklist_rows", return_value=rows):
            results = mh.analyze_migrant_hotspots(
                "token",
                "US-VA-107",
                dates=[dt.date(2025, 5, 17)],
                min_checklists_per_hotspot=2,
            )

        self.assertEqual(results.checklist_count, 2)
        self.assertEqual(results.hotspot_count, 1)
        self.assertEqual(results.warbler_species_count, 2)
        summary = results.hotspot_summary.iloc[0]
        self.assertEqual(summary["locName"], "Ridge")
        self.assertEqual(summary["warbler_species"], 2)
        self.assertEqual(summary["warbler_individuals"], 4)
        self.assertAlmostEqual(summary["photo_score"], 50.0)
        self.assertEqual(set(results.species_summary["speciesCode"]), {"bawwar", "amered"})


if __name__ == "__main__":
    unittest.main()
