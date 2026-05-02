import unittest
from unittest import mock

import datetime as dt
import numpy as np
import pandas as pd

from big_day_optimizer.dashboard import (
    DashboardConfig,
    _bird_highlight_frames,
    _classify_stop_birds,
    _format_minutes,
    _is_public_deployment,
    _load_default_api_key,
    _load_preloaded_loudoun_itinerary,
    _parse_observation_date,
    _route_species_probability_frame,
    _summary_dataframe,
    _species_items,
    _validate,
)


class DashboardTest(unittest.TestCase):
    def test_parse_observation_date_accepts_iso(self):
        parsed, error = _parse_observation_date("2026-05-02")

        self.assertEqual(parsed, dt.date(2026, 5, 2))
        self.assertIsNone(error)

    def test_parse_observation_date_accepts_slashes(self):
        parsed, error = _parse_observation_date("2026/05/02")

        self.assertEqual(parsed, dt.date(2026, 5, 2))
        self.assertIsNone(error)

    def test_parse_observation_date_rejects_ambiguous_dates(self):
        parsed, error = _parse_observation_date("05/02/2026")

        self.assertIsNone(parsed)
        self.assertEqual(error, "Observation date must be YYYY-MM-DD or YYYY/MM/DD.")

    def test_species_items_parses_and_sorts_probabilities(self):
        items = _species_items("mallar3:0.25, cangoo:0.80", limit=2)

        self.assertEqual(items[0][0], "Canada Goose")
        self.assertEqual(items[0][1], 0.8)
        self.assertEqual(items[1][0], "Mallard")
        self.assertEqual(items[1][1], 0.25)

    def test_format_minutes(self):
        self.assertEqual(_format_minutes(95), "1h 35m")
        self.assertEqual(_format_minutes(60), "1h")
        self.assertEqual(_format_minutes(42), "42m")

    def test_preloaded_loudoun_itinerary_renders_like_optimizer_output(self):
        itinerary = _load_preloaded_loudoun_itinerary()
        summary = _summary_dataframe(itinerary)

        self.assertEqual(summary.loc[0, "Site"], "Algonkian Regional Park--Sanctuary Trail")
        self.assertEqual(summary.loc[0, "eBird hotspot"], "https://ebird.org/hotspot/L4946002")
        self.assertGreater(itinerary.expected_species, 40)
        self.assertEqual(len(itinerary.route_idx), 8)
        self.assertIn("Blue-gray Gnatcatcher", summary.loc[0, "Top new birds"])

    def test_public_deployment_does_not_prefill_api_key(self):
        with mock.patch.dict(
            "os.environ",
            {"BBD_PUBLIC_DEPLOYMENT": "1", "EBIRD_API_KEY": "secret-token"},
            clear=False,
        ):
            self.assertTrue(_is_public_deployment())
            self.assertEqual(_load_default_api_key(), "")

    def test_summary_dataframe_keeps_species_compact(self):
        class FakeItinerary:
            def leg_rows(self):
                return [
                    {
                        "leg": 0,
                        "loc_id": "L123",
                        "site": "First Stop",
                        "arrive": "05:30",
                        "depart": "06:20",
                        "drive_min": 0,
                        "dwell_min": 50.0,
                        "expected_new_sp": 12.3,
                        "species": "cangoo:0.90, mallar3:0.70, amecro:0.60, amerob:0.50, blujay:0.40",
                    }
                ]

        summary = _summary_dataframe(FakeItinerary())

        self.assertEqual(summary.loc[0, "Stop"], 1)
        self.assertEqual(summary.loc[0, "Expected new"], 12.3)
        self.assertEqual(summary.loc[0, "Cumulative expected"], 12.3)
        self.assertEqual(summary.loc[0, "eBird hotspot"], "https://ebird.org/hotspot/L123")
        self.assertIn("Canada Goose (90%)", summary.loc[0, "Top new birds"])
        self.assertNotIn("Blue Jay", summary.loc[0, "Top new birds"])

    def test_bird_highlights_separates_specialties_and_shared_birds(self):
        class FakeItinerary:
            route_idx = [0, 1, 2]
            sp_all = ["cangoo", "mallar3", "amecro"]
            gain_matrix = np.array(
                [
                    [0.90, 0.45, 0.10],
                    [0.05, 0.50, 0.70],
                    [0.00, 0.20, 0.65],
                ]
            )
            hotspots = pd.DataFrame(
                {
                    "locName": ["Marsh", "Pond", "Woods"],
                }
            )

        specialties, shared = _bird_highlight_frames(FakeItinerary())

        marsh_specialties = specialties[specialties["Hotspot"] == "Marsh"]
        self.assertIn("Canada Goose", set(marsh_specialties["Bird"]))
        self.assertIn("Mallard", set(shared["Bird"]))
        self.assertIn("American Crow", set(shared["Bird"]))
        self.assertNotIn("Canada Goose", set(shared["Bird"]))

    def test_classify_stop_birds_groups_common_uncommon_and_rare(self):
        class FakeItinerary:
            route_idx = [0, 1, 2]
            sp_all = ["cangoo", "mallar3", "amecro"]
            gain_matrix = np.array(
                [
                    [0.90, 0.45, 0.35],
                    [0.80, 0.05, 0.10],
                    [0.70, 0.05, 0.00],
                ]
            )

        groups = _classify_stop_birds(
            FakeItinerary(),
            1,
            [("amecro", "American Crow", 0.35)],
        )

        self.assertEqual([item["name"] for item in groups["common"]], ["Canada Goose"])
        self.assertEqual([item["name"] for item in groups["uncommon"]], ["Mallard"])
        self.assertEqual([item["name"] for item in groups["rare"]], ["American Crow"])
        self.assertAlmostEqual(groups["common"][0]["cumulative_probability"], 0.9)

    def test_route_species_probability_combines_small_chances(self):
        class FakeItinerary:
            route_idx = [0, 1, 2]
            sp_all = ["lowodd", "single"]
            gain_matrix = np.array(
                [
                    [0.10, 0.30],
                    [0.10, 0.00],
                    [0.10, 0.00],
                ]
            )
            hotspots = pd.DataFrame(
                {
                    "locName": ["Marsh", "Pond", "Woods"],
                }
            )

        probabilities = _route_species_probability_frame(
            FakeItinerary(),
            min_route_probability=0.25,
            min_best_stop_probability=0.25,
        )

        low_odd_row = probabilities[probabilities["Bird"] == "lowodd"].iloc[0]
        self.assertAlmostEqual(low_odd_row["Route chance"], 0.271)
        self.assertEqual(low_odd_row["Contributing stops"], 3)

    def test_future_date_requires_historical_years(self):
        config = DashboardConfig(
            api_key="token",
            region="US-VA-059",
            observation_date=dt.date(2999, 5, 2),
            date_error=None,
            start_time=dt.time(5, 30),
            end_time=dt.time(20, 30),
            depot_locid=None,
            include_recent=True,
            historical_years=0,
            back=7,
            max_checklists_per_day=50,
            min_checklists_per_hotspot=5,
            max_hotspots=40,
            min_stops=3,
            max_stops=8,
            min_prob=0.15,
            display_min_prob=0.15,
            nearby_drive_min=8,
            nearby_pair_penalty=0.15,
            base_idle=30,
            dwell_per=2,
            time_limit=60,
        )

        errors = _validate(config)

        self.assertIn(
            "Future dates require at least one historical year; eBird has no future checklists.",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
