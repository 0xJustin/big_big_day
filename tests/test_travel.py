import unittest

from big_day_optimizer.travel import osrm_matrix


class TravelTest(unittest.TestCase):
    def test_single_coordinate_matrix_does_not_call_osrm(self):
        self.assertEqual(osrm_matrix([(38.7576451, -77.0984124)]), [[0]])

    def test_empty_coordinate_matrix(self):
        self.assertEqual(osrm_matrix([]), [])


if __name__ == "__main__":
    unittest.main()
