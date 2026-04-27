import datetime as dt
import unittest
from unittest.mock import patch

import pandas as pd

from big_day_optimizer import ebird_api


class EbirdApiTest(unittest.TestCase):
    def setUp(self):
        ebird_api._cached_checklist_species.cache_clear()

    def test_sampling_dates_can_include_same_window_last_year(self):
        dates = ebird_api._sampling_dates(
            back=3,
            as_of=dt.date(2026, 4, 26),
            same_dates_last_year=True,
            include_recent=True,
            today=dt.date(2026, 4, 26),
        )

        self.assertEqual(
            dates,
            [
                dt.date(2026, 4, 26),
                dt.date(2026, 4, 25),
                dt.date(2026, 4, 24),
                dt.date(2025, 4, 26),
                dt.date(2025, 4, 25),
                dt.date(2025, 4, 24),
            ],
        )

    def test_sampling_dates_supports_historical_only(self):
        dates = ebird_api._sampling_dates(
            back=2,
            as_of="2026-04-26",
            historical_years=1,
            include_recent=False,
            today=dt.date(2026, 4, 26),
        )

        self.assertEqual(
            dates,
            [
                dt.date(2025, 4, 26),
                dt.date(2025, 4, 25),
            ],
        )

    def test_sampling_dates_supports_multiple_historical_years(self):
        dates = ebird_api._sampling_dates(
            back=1,
            as_of="2026-04-26",
            historical_years=2,
            include_recent=False,
            today=dt.date(2026, 4, 26),
        )

        self.assertEqual(
            dates,
            [
                dt.date(2025, 4, 26),
                dt.date(2024, 4, 26),
            ],
        )

    def test_sampling_dates_skips_future_recent_dates(self):
        dates = ebird_api._sampling_dates(
            back=3,
            as_of=dt.date(2026, 5, 2),
            same_dates_last_year=True,
            include_recent=True,
            today=dt.date(2026, 4, 26),
        )

        self.assertEqual(
            dates,
            [
                dt.date(2025, 5, 2),
                dt.date(2025, 5, 1),
                dt.date(2025, 4, 30),
            ],
        )

    def test_probabilities_are_checklist_detection_rates(self):
        def fake_get_visits(token, area, date=None, max_results=10):
            self.assertEqual(token, "token")
            self.assertEqual(area, "loc-1")
            self.assertEqual(date, "2026-04-26")
            self.assertEqual(max_results, 50)
            return [{"subId": "S1"}, {"subId": "S2"}]

        def fake_get_checklist(token, sub_id):
            payloads = {
                "S1": {
                    "obs": [
                        {"speciesCode": "amecro"},
                        {"speciesCode": "amecro"},
                        {"speciesCode": "mallar3"},
                    ]
                },
                "S2": {
                    "obs": [
                        {"speciesCode": "mallar3"},
                    ]
                },
            }
            return payloads[sub_id]

        with patch.object(ebird_api, "get_visits", side_effect=fake_get_visits), patch.object(
            ebird_api, "get_checklist", side_effect=fake_get_checklist
        ):
            probabilities = ebird_api._prob_vector_for_loc(
                "token",
                "loc-1",
                dates=[dt.date(2026, 4, 26)],
                max_checklists_per_day=50,
            )

        self.assertEqual(probabilities["amecro"], 0.5)
        self.assertEqual(probabilities["mallar3"], 1.0)

    def test_species_prob_by_loc_uses_same_dates_last_year(self):
        requested_dates = []

        def fake_prob_vector(api_key, loc_id, *, dates, max_checklists_per_day):
            requested_dates.extend(dates)
            return {loc_id: 1.0}

        hotspots = pd.DataFrame({"locId": ["loc-1"]})
        with patch.object(ebird_api, "_prob_vector_for_loc", side_effect=fake_prob_vector):
            result = ebird_api.species_prob_by_loc(
                "token",
                hotspots,
                back=1,
                as_of="2026-04-26",
                historical_years=1,
                include_recent=False,
            )

        self.assertEqual(result, {"loc-1": {"loc-1": 1.0}})
        self.assertEqual(requested_dates, [dt.date(2025, 4, 26)])


if __name__ == "__main__":
    unittest.main()
