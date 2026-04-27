"""Centralised configuration constants."""
import os

EBIRD_ROOT   : str = "https://api.ebird.org/v2"
OSRM_ROOT    : str = os.getenv("OSRM_ROOT", "http://router.project-osrm.org")
DEFAULT_USER_AGENT = "big-day-optimizer/0.1"
