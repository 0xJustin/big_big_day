import datetime as dt
import unittest

import pandas as pd

from big_day_optimizer.solver import solve_itinerary


class SolverTest(unittest.TestCase):
    def test_fixed_depot_uses_positional_index(self):
        hotspots = pd.DataFrame(
            {
                "locId": ["first", "depot", "last"],
                "locName": ["First", "Depot", "Last"],
            },
            index=[10, 20, 30],
        )
        travel = [
            [0, 1, 1],
            [1, 0, 1],
            [1, 1, 0],
        ]
        probabilities = {
            "first": {"a": 0.9},
            "depot": {"b": 0.9},
            "last": {"c": 0.9},
        }

        itinerary = solve_itinerary(
            hotspots,
            travel,
            probabilities,
            include_depot=True,
            depot_locid="depot",
            start_time=dt.datetime(2026, 5, 2, 5, 30),
            end_time=dt.datetime(2026, 5, 2, 9, 30),
            base_idle=0,
            dwell_per=0,
            min_stops=1,
            max_stops=1,
            min_prob=0.0,
            time_limit=5,
        )

        self.assertEqual(itinerary.route_idx[0], 1)
        self.assertEqual(itinerary.hotspots.locName.iloc[itinerary.route_idx[0]], "Depot")

    def test_expected_species_accumulates_repeat_opportunities(self):
        hotspots = pd.DataFrame(
            {
                "locId": ["a", "b"],
                "locName": ["A", "B"],
            }
        )
        travel = [
            [0, 1],
            [1, 0],
        ]
        probabilities = {
            "a": {"shared": 0.5},
            "b": {"shared": 0.5},
        }

        itinerary = solve_itinerary(
            hotspots,
            travel,
            probabilities,
            include_depot=False,
            start_time=dt.datetime(2026, 5, 2, 5, 30),
            end_time=dt.datetime(2026, 5, 2, 9, 30),
            base_idle=0,
            dwell_per=0,
            min_stops=2,
            max_stops=2,
            min_prob=0.0,
            time_limit=5,
        )

        self.assertAlmostEqual(itinerary.expected_species, 0.75)

    def test_species_ties_prefer_shorter_travel(self):
        hotspots = pd.DataFrame(
            {
                "locId": ["a", "b", "c"],
                "locName": ["A", "B", "C"],
            }
        )
        travel = [
            [0, 100, 1],
            [100, 0, 1],
            [1, 1, 0],
        ]
        probabilities = {
            "a": {"a_sp": 0.9},
            "b": {"b_sp": 0.9},
            "c": {"c_sp": 0.9},
        }

        itinerary = solve_itinerary(
            hotspots,
            travel,
            probabilities,
            include_depot=False,
            start_time=dt.datetime(2026, 5, 2, 5, 30),
            end_time=dt.datetime(2026, 5, 2, 9, 30),
            base_idle=0,
            dwell_per=0,
            min_stops=3,
            max_stops=3,
            min_prob=0.0,
            time_limit=5,
        )

        self.assertEqual(sum(row["drive_min"] for row in itinerary.leg_rows()), 2)

    def test_nearby_penalty_discourages_duplicate_close_hotspots(self):
        hotspots = pd.DataFrame(
            {
                "locId": ["a", "b", "c"],
                "locName": ["A", "B", "C"],
            }
        )
        travel = [
            [0, 1, 10],
            [1, 0, 10],
            [10, 10, 0],
        ]
        probabilities = {
            "a": {"a_sp": 0.50},
            "b": {"b_sp": 0.50},
            "c": {"c_sp": 0.49},
        }

        itinerary = solve_itinerary(
            hotspots,
            travel,
            probabilities,
            include_depot=False,
            start_time=dt.datetime(2026, 5, 2, 5, 30),
            end_time=dt.datetime(2026, 5, 2, 9, 30),
            base_idle=0,
            dwell_per=0,
            min_stops=2,
            max_stops=2,
            min_prob=0.0,
            nearby_drive_min=2,
            nearby_pair_penalty=0.20,
            time_limit=5,
        )

        selected = {hotspots.locId.iloc[idx] for idx in itinerary.route_idx}
        self.assertNotEqual(selected, {"a", "b"})


if __name__ == "__main__":
    unittest.main()
