from __future__ import annotations

import os
import datetime as dt
import html
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

from .optimizer import BigDayOptimizer
from .utils import translate_codes


DEFAULT_REGION = "US-VA-107"
DEFAULT_OBSERVATION_DATE = dt.date(2026, 5, 2)


@dataclass(frozen=True)
class DashboardConfig:
    api_key: str
    region: str
    observation_date: object
    date_error: Optional[str]
    start_time: object
    end_time: object
    depot_locid: Optional[str]
    include_recent: bool
    historical_years: int
    back: int
    max_checklists_per_day: int
    max_hotspots: int
    min_stops: int
    max_stops: int
    min_prob: float
    display_min_prob: float
    base_idle: int
    dwell_per: int
    time_limit: int


def _page_style() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bbd-ink: #142117;
            --bbd-strong: #0a120d;
            --bbd-muted: #3f5146;
            --bbd-line: #c8d2c5;
            --bbd-panel: #fffdf5;
            --bbd-sidebar: #f1eadb;
            --bbd-field: #fffaf0;
            --bbd-field-border: #677766;
            --bbd-accent: #1f3a2a;
            --bbd-accent-hover: #31553d;
            --bbd-info-bg: #d8ecf5;
            --bbd-info-text: #103445;
        }

        html, body, .stApp {
            color: var(--bbd-ink) !important;
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(178, 207, 152, 0.26), transparent 30rem),
                linear-gradient(135deg, #f7f3e8 0%, #eef3e7 52%, #fbf8ee 100%);
        }

        [data-testid="stAppViewContainer"],
        [data-testid="stMain"],
        [data-testid="stMain"] > div {
            background: transparent !important;
            background-color: transparent !important;
        }

        [data-testid="stMainBlockContainer"],
        .stMainBlockContainer,
        .stMainBlockContainer.block-container,
        .block-container {
            background: transparent !important;
            background-color: transparent !important;
            box-shadow: none !important;
            max-width: none;
            padding: 2rem clamp(1.25rem, 4vw, 4rem) 3rem;
        }

        [data-testid="stMain"] [data-testid="stElementContainer"],
        [data-testid="stMain"] [data-testid="stMarkdownContainer"] {
            background: transparent !important;
            background-color: transparent !important;
        }

        [data-testid="stMain"] div[data-testid="stVerticalBlockBorderWrapper"] {
            background: transparent !important;
            background-color: transparent !important;
            border-color: transparent !important;
            box-shadow: none !important;
        }

        [data-testid="stHeader"] {
            background: #0d1310;
        }

        [data-testid="stSidebar"] {
            background: var(--bbd-sidebar);
            border-right: 1px solid var(--bbd-line);
        }

        [data-testid="stSidebar"] > div {
            background: var(--bbd-sidebar);
        }

        [data-testid="stSidebar"] [data-testid="stSidebarContent"] {
            padding: 1.25rem 1.05rem 1.5rem;
        }

        [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
            gap: 0.45rem;
        }

        .stApp h1,
        .stApp h2,
        .stApp h3,
        .stApp h4,
        .stApp h5,
        .stApp h6,
        .stApp p,
        .stApp li,
        .stApp span,
        .stApp label,
        .stApp div[data-testid="stMarkdownContainer"],
        .stApp div[data-testid="stWidgetLabel"] p {
            color: var(--bbd-ink) !important;
        }

        h1, h2, h3 {
            letter-spacing: -0.035em;
        }

        h1 {
            font-size: 2.8rem;
            line-height: 0.95;
            color: var(--bbd-strong) !important;
            margin-bottom: 0.65rem;
        }

        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] div[data-testid="stWidgetLabel"] p {
            color: var(--bbd-strong) !important;
            opacity: 1 !important;
        }

        [data-testid="stSidebar"] section {
            color: var(--bbd-strong) !important;
        }

        [data-testid="stSidebar"] div[data-testid="stWidgetLabel"] p {
            color: var(--bbd-strong) !important;
            font-size: 0.84rem !important;
            font-weight: 800 !important;
            letter-spacing: 0.01em;
            margin-bottom: 0.15rem !important;
        }

        [data-testid="stSidebar"] input,
        [data-testid="stSidebar"] [data-baseweb="select"] div,
        [data-testid="stSidebar"] [data-testid="stNumberInput"] input,
        [data-testid="stSidebar"] [data-testid="stDateInput"] input {
            font-size: 0.95rem !important;
            line-height: 1.2 !important;
        }

        [data-testid="stSidebar"] div[data-baseweb="input"] input,
        [data-testid="stSidebar"] [data-baseweb="base-input"] input,
        [data-testid="stSidebar"] [data-testid="stNumberInput"] input {
            min-height: 2.35rem !important;
            padding-bottom: 0.42rem !important;
            padding-top: 0.42rem !important;
        }

        [data-testid="stSidebar"] [data-baseweb="select"] > div {
            min-height: 2.35rem !important;
            padding-bottom: 0 !important;
            padding-top: 0 !important;
        }

        [data-testid="stSidebar"] svg {
            height: 1rem;
            width: 1rem;
        }

        [data-testid="stSidebar"] div[data-baseweb="input"],
        [data-testid="stSidebar"] div[data-baseweb="select"],
        [data-testid="stSidebar"] div[data-baseweb="base-input"],
        [data-testid="stSidebar"] [data-testid="stNumberInput"] div[data-baseweb="input"] {
            border-radius: 12px !important;
            min-height: 2.45rem !important;
        }

        [data-testid="stSidebar"] [data-testid="stTextInput"],
        [data-testid="stSidebar"] [data-testid="stTimeInput"],
        [data-testid="stSidebar"] [data-testid="stSelectbox"],
        [data-testid="stSidebar"] [data-testid="stNumberInput"],
        [data-testid="stSidebar"] [data-testid="stSlider"] {
            margin-bottom: 0.35rem;
        }

        [data-testid="stSidebar"] [data-testid="stCheckbox"] {
            margin: 0.25rem 0 0.2rem;
        }

        [data-testid="stSidebar"] [data-testid="stCheckbox"] label {
            align-items: flex-start !important;
            gap: 0.5rem !important;
        }

        [data-testid="stSidebar"] [data-testid="stCheckbox"] label p {
            font-size: 0.9rem !important;
            font-weight: 750 !important;
            line-height: 1.25 !important;
        }

        [data-testid="stSidebar"] [data-testid="stCheckbox"] div[role="checkbox"] {
            height: 1rem !important;
            margin-top: 0.15rem;
            width: 1rem !important;
        }

        [data-testid="stSidebar"] [data-testid="stTooltipHoverTarget"] {
            color: var(--bbd-muted) !important;
        }

        hr {
            border-color: var(--bbd-line) !important;
        }

        [data-testid="stSidebar"] hr {
            margin: 0.65rem 0 !important;
        }

        div[data-baseweb="input"],
        div[data-baseweb="select"],
        div[data-baseweb="textarea"],
        div[data-baseweb="base-input"],
        [data-testid="stDateInput"] div[data-baseweb="input"],
        [data-testid="stTimeInput"] div[data-baseweb="select"],
        [data-testid="stNumberInput"] div[data-baseweb="input"] {
            background: var(--bbd-field) !important;
            border-color: var(--bbd-field-border) !important;
            box-shadow: none !important;
        }

        input,
        textarea,
        [data-baseweb="select"] div,
        [data-testid="stNumberInput"] input,
        [data-testid="stDateInput"] input {
            color: var(--bbd-strong) !important;
            background: var(--bbd-field) !important;
            -webkit-text-fill-color: var(--bbd-strong) !important;
            caret-color: var(--bbd-strong) !important;
        }

        input::placeholder,
        textarea::placeholder {
            color: #68776e !important;
            opacity: 1 !important;
        }

        svg {
            color: currentColor;
        }

        [data-testid="stCheckbox"] label,
        [data-testid="stCheckbox"] label p,
        [data-testid="stCheckbox"] span {
            color: var(--bbd-strong) !important;
            opacity: 1 !important;
        }

        [data-testid="stCheckbox"] div[role="checkbox"] {
            border-color: var(--bbd-field-border) !important;
            background: #ffffff !important;
        }

        [data-testid="stSlider"] * {
            color: var(--bbd-strong) !important;
        }

        div[data-testid="stMetric"] {
            background: var(--bbd-panel);
            border: 1px solid var(--bbd-line);
            border-radius: 18px;
            padding: 1rem 1.1rem;
            box-shadow: 0 14px 30px rgba(31, 46, 33, 0.07);
        }

        div[data-testid="stMetricLabel"] {
            color: var(--bbd-muted) !important;
        }

        div[data-testid="stMetricValue"] {
            color: var(--bbd-strong) !important;
        }

        .stButton > button {
            background: var(--bbd-accent) !important;
            border: 1px solid var(--bbd-accent) !important;
            border-radius: 999px;
            color: #fff8e7 !important;
            font-weight: 700;
            padding: 0.55rem 1.2rem;
        }

        .stButton > button p,
        .stButton > button span {
            color: #fff8e7 !important;
        }

        .stButton > button:hover {
            background: var(--bbd-accent-hover) !important;
            border-color: var(--bbd-accent-hover) !important;
            color: #fff8e7 !important;
        }

        [data-testid="stAlert"] {
            background: var(--bbd-info-bg) !important;
            border: 1px solid #7fb2c5 !important;
        }

        [data-testid="stAlert"] *,
        [data-testid="stAlert"] p {
            color: var(--bbd-info-text) !important;
        }

        [data-testid="stDataFrame"] {
            border: 1px solid var(--bbd-line);
            border-radius: 14px;
            overflow: hidden;
        }

        .bbd-subtitle {
            max-width: 760px;
            color: var(--bbd-muted) !important;
            font-size: 1.05rem;
            margin-top: -0.7rem;
            margin-bottom: 0.85rem;
        }

        .bbd-help {
            background: #fff8e8;
            border: 1px solid #d5c9a9;
            border-radius: 12px;
            color: var(--bbd-strong) !important;
            font-size: 0.9rem;
            line-height: 1.42;
            margin: 0.25rem 0 0.85rem;
            padding: 0.75rem 0.8rem;
        }

        .bbd-help strong {
            color: var(--bbd-strong) !important;
        }

        .bbd-sidebar-title {
            color: var(--bbd-strong) !important;
            font-size: 1.55rem;
            font-weight: 900;
            letter-spacing: -0.045em;
            line-height: 1;
            margin: 0 0 0.65rem;
        }

        .bbd-sidebar-section {
            color: var(--bbd-muted) !important;
            font-size: 0.74rem;
            font-weight: 900;
            letter-spacing: 0.08em;
            margin: 0.7rem 0 0.05rem;
            text-transform: uppercase;
        }

        [data-testid="stSidebar"] .bbd-help {
            font-size: 0.78rem;
            line-height: 1.35;
            margin: 0.15rem 0 0.45rem;
            padding: 0.62rem 0.7rem;
        }

        [data-testid="stSidebar"] details {
            border-color: var(--bbd-line) !important;
            border-radius: 12px !important;
        }

        [data-testid="stSidebar"] summary p {
            color: var(--bbd-strong) !important;
            font-size: 0.86rem !important;
            font-weight: 850 !important;
        }

        .bbd-callout,
        .bbd-stop-card,
        .bbd-route-summary {
            background: rgba(255, 253, 245, 0.94);
            border: 1px solid var(--bbd-line);
            border-radius: 18px;
            box-shadow: 0 12px 30px rgba(20, 33, 23, 0.07);
        }

        .bbd-callout {
            margin: 1rem 0 1.25rem;
            padding: 1rem 1.15rem;
        }

        .bbd-callout-title,
        .bbd-stop-title {
            color: var(--bbd-strong) !important;
            font-weight: 800;
            margin-bottom: 0.25rem;
        }

        .bbd-callout-body,
        .bbd-stop-meta {
            color: var(--bbd-muted) !important;
            line-height: 1.45;
        }

        .bbd-stop-card {
            margin-bottom: 0.85rem;
            padding: 1rem 1.1rem;
        }

        .bbd-stop-number {
            align-items: center;
            background: var(--bbd-accent);
            border-radius: 999px;
            color: #fff8e7 !important;
            display: inline-flex;
            font-size: 0.85rem;
            font-weight: 800;
            height: 2rem;
            justify-content: center;
            margin-right: 0.55rem;
            width: 2rem;
        }

        .bbd-chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
            margin-top: 0.8rem;
        }

        .bbd-chip {
            background: #eaf2df;
            border: 1px solid #c9d8bd;
            border-radius: 999px;
            color: var(--bbd-strong) !important;
            display: inline-block;
            font-size: 0.88rem;
            padding: 0.28rem 0.62rem;
        }

        .bbd-specialty-chip {
            background: #fff0c2;
            border-color: #d3a83b;
        }

        .bbd-rare-chip {
            background: #fde6c8;
            border-color: #d38a38;
        }

        .bbd-common-chip {
            background: #eef2e3;
            border-color: #ccd8bd;
        }

        .bbd-empty-chip {
            background: #f2ead8;
            border-color: #d8cab0;
            color: var(--bbd-muted) !important;
        }

        .bbd-chip-label {
            color: var(--bbd-muted) !important;
            font-size: 0.82rem;
            font-weight: 800;
            letter-spacing: 0.04em;
            margin-top: 0.9rem;
            text-transform: uppercase;
        }

        .bbd-table-note {
            color: var(--bbd-muted) !important;
            font-size: 0.92rem;
            margin: -0.3rem 0 0.6rem;
        }

        .bbd-section-note {
            color: var(--bbd-muted) !important;
            font-size: 0.95rem;
            margin: -0.35rem 0 0.9rem;
        }

        .bbd-section-title {
            color: var(--bbd-strong) !important;
            font-size: 1.45rem;
            font-weight: 800;
            letter-spacing: -0.02em;
            margin: 1.15rem 0 0.35rem;
        }

        .bbd-tooltip {
            align-items: center;
            background: #eaf2df;
            border: 1px solid #b8c8ad;
            border-radius: 999px;
            color: var(--bbd-strong) !important;
            cursor: help;
            display: inline-flex;
            font-size: 0.78rem;
            font-weight: 800;
            height: 1.15rem;
            justify-content: center;
            margin-left: 0.35rem;
            vertical-align: 0.15rem;
            width: 1.15rem;
        }

        .bbd-hotspot-link {
            color: #1f5f3b !important;
            display: inline-block;
            font-weight: 800;
            margin-top: 0.35rem;
            text-decoration: none;
        }

        .bbd-hotspot-link:hover {
            color: #123822 !important;
            text-decoration: underline;
        }

        [data-testid="stSidebar"] div[data-testid="stVerticalBlockBorderWrapper"] {
            background: rgba(255, 253, 245, 0.94);
            border-color: var(--bbd-line) !important;
            box-shadow: 0 12px 30px rgba(20, 33, 23, 0.07);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _parse_observation_date(value: str) -> tuple[Optional[dt.date], Optional[str]]:
    cleaned = value.strip()
    if not cleaned:
        return None, "Observation date is required."

    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return dt.datetime.strptime(cleaned, fmt).date(), None
        except ValueError:
            pass
    return None, "Observation date must be YYYY-MM-DD or YYYY/MM/DD."


def _load_default_api_key() -> str:
    try:
        secrets_api_key = str(st.secrets.get("EBIRD_API_KEY", "")).strip()
    except Exception:
        secrets_api_key = ""
    if secrets_api_key:
        return secrets_api_key

    env_api_key = os.getenv("EBIRD_API_KEY", "").strip()
    if env_api_key:
        return env_api_key

    token_path = Path(__file__).resolve().parents[1] / "ebird_token.json"
    if not token_path.exists():
        return ""

    try:
        token_payload = json.loads(token_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""

    if isinstance(token_payload, str):
        return token_payload.strip()
    if isinstance(token_payload, dict):
        for key in ("EBIRD_API_KEY", "api_key", "token", "key"):
            value = token_payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _read_config() -> DashboardConfig:
    default_api_key = _load_default_api_key()

    with st.sidebar:
        st.markdown('<div class="bbd-sidebar-title">Run</div>', unsafe_allow_html=True)
        st.markdown('<div class="bbd-sidebar-section">Trip setup</div>', unsafe_allow_html=True)
        api_key = st.text_input("eBird API key", value=default_api_key, type="password")
        region = st.text_input("eBird region", value=DEFAULT_REGION)
        observation_date_text = st.text_input(
            "Observation date",
            value=DEFAULT_OBSERVATION_DATE.isoformat(),
            help="Use YYYY-MM-DD. Future dates are allowed.",
        )
        observation_date, date_error = _parse_observation_date(observation_date_text)

        st.divider()
        st.markdown('<div class="bbd-sidebar-section">Day window</div>', unsafe_allow_html=True)
        start_time = st.time_input("Start time", value=dt.time(5, 30))
        end_time = st.time_input("End time", value=dt.time(20, 30))

        st.divider()
        st.markdown('<div class="bbd-sidebar-section">Checklist data</div>', unsafe_allow_html=True)
        include_recent = st.checkbox(
            "Use recent checklists from this year",
            value=False,
            help="Samples current-year checklists in the date window. Future checklist dates are skipped.",
        )
        historical_years = st.selectbox(
            "Number of historical years",
            options=[0, 1, 2, 3, 4, 5],
            index=2,
            help="Adds matching calendar-date windows from prior years.",
        )
        with st.expander("How sampling works", expanded=False):
            st.markdown(
                """
                <div class="bbd-help">
                  <strong>Recent checklists</strong> use this year’s reports in the selected date window, skipping future dates that do not exist yet.<br>
                  <strong>Historical years</strong> add matching calendar windows from prior years. For future dates, use at least one historical year.
                </div>
                """,
                unsafe_allow_html=True,
            )
        depot_locid = None
        with st.expander("Advanced settings", expanded=False):
            depot_enabled = st.checkbox("Use fixed starting hotspot")
            if depot_enabled:
                depot_locid = st.text_input("Starting hotspot locId").strip() or None

            back = st.number_input("Days in each sample window", min_value=1, max_value=30, value=7)
            max_checklists_per_day = st.number_input(
                "Max checklists per hotspot/day",
                min_value=1,
                max_value=200,
                value=50,
                step=5,
            )
            max_hotspots = st.number_input(
                "Candidate hotspots",
                min_value=1,
                max_value=500,
                value=40,
                step=5,
                help="Caps hotspot probability fetching before the solver runs.",
            )

            col_a, col_b = st.columns(2)
            min_stops = col_a.number_input("Min stops", min_value=1, max_value=50, value=3)
            max_stops = col_b.number_input("Max stops", min_value=1, max_value=50, value=8)
            min_prob = st.slider(
                "Optimization probability floor",
                0.0,
                0.5,
                0.03,
                0.01,
                help="Species-hotspot probabilities below this value are ignored by the solver. Lower values let several small chances combine into a meaningful route-level chance, but increase solve time.",
            )
            display_min_prob = st.slider(
                "Displayed bird probability floor",
                0.0,
                0.5,
                0.15,
                0.01,
                help="Keeps low-probability solver inputs from cluttering the stop cards and trip probability table.",
            )
            base_idle = st.number_input("Base dwell minutes", min_value=0, max_value=240, value=30)
            dwell_per = st.number_input("Minutes per expected new species", min_value=0, max_value=30, value=2)
            time_limit = st.number_input("Solver time limit seconds", min_value=5, max_value=900, value=60)

    return DashboardConfig(
        api_key=api_key.strip(),
        region=region.strip(),
        observation_date=observation_date,
        date_error=date_error,
        start_time=start_time,
        end_time=end_time,
        depot_locid=depot_locid,
        include_recent=include_recent,
        historical_years=int(historical_years),
        back=int(back),
        max_checklists_per_day=int(max_checklists_per_day),
        max_hotspots=int(max_hotspots),
        min_stops=int(min_stops),
        max_stops=int(max_stops),
        min_prob=float(min_prob),
        display_min_prob=float(display_min_prob),
        base_idle=int(base_idle),
        dwell_per=int(dwell_per),
        time_limit=int(time_limit),
    )


def _validate(config: DashboardConfig) -> list[str]:
    errors = []
    if not config.api_key:
        errors.append("Enter an eBird API key or set EBIRD_API_KEY.")
    if not config.region:
        errors.append("Enter an eBird region code.")
    if config.date_error:
        errors.append(config.date_error)
    if config.start_time >= config.end_time:
        errors.append("Start time must be before end time.")
    if config.min_stops > config.max_stops:
        errors.append("Min stops cannot exceed max stops.")
    if config.historical_years < 0:
        errors.append("Number of historical years cannot be negative.")
    if not config.include_recent and config.historical_years <= 0:
        errors.append("Select recent checklists or at least one historical year.")
    if (
        config.observation_date is not None
        and config.observation_date > dt.date.today()
        and config.historical_years <= 0
    ):
        errors.append("Future dates require at least one historical year; eBird has no future checklists.")
    if config.depot_locid is None and config.min_stops < 1:
        errors.append("Free-start routes need at least one stop.")
    return errors


def _run_optimizer(config: DashboardConfig):
    optimizer = BigDayOptimizer(
        api_key=config.api_key,
        region=config.region,
        depot_locid=config.depot_locid,
        include_depot=config.depot_locid is not None,
        observation_date=config.observation_date,
        start_time=config.start_time,
        end_time=config.end_time,
        include_recent=config.include_recent,
        historical_years=config.historical_years,
        back=config.back,
        max_checklists_per_day=config.max_checklists_per_day,
        max_hotspots=config.max_hotspots,
        min_stops=config.min_stops,
        max_stops=config.max_stops,
        min_prob=config.min_prob,
        base_idle=config.base_idle,
        dwell_per=config.dwell_per,
        time_limit=config.time_limit,
    )
    return optimizer.solve()


def _route_map_data(itinerary) -> pd.DataFrame:
    rows = []
    for leg, idx in enumerate(itinerary.route_idx):
        hotspot = itinerary.hotspots.iloc[idx]
        if {"lat", "lng"}.issubset(itinerary.hotspots.columns):
            rows.append(
                {
                    "leg": leg,
                    "site": hotspot["locName"],
                    "lat": float(hotspot["lat"]),
                    "lon": float(hotspot["lng"]),
                }
            )
    return pd.DataFrame(rows)


def _format_minutes(minutes: float) -> str:
    minutes_int = int(round(minutes))
    hours, mins = divmod(minutes_int, 60)
    if hours and mins:
        return f"{hours}h {mins}m"
    if hours:
        return f"{hours}h"
    return f"{mins}m"


def _common_species_name(code: str) -> str:
    translated = translate_codes(code)
    prefix = f"{code} ("
    if translated.startswith(prefix) and translated.endswith(")"):
        return translated[len(prefix):-1]
    return translated


def _species_items(species_text: str, *, limit: Optional[int] = None) -> list[tuple[str, float]]:
    items: list[tuple[str, float]] = []
    if not species_text:
        return items

    for part in species_text.split(", "):
        if ":" not in part:
            continue
        code, probability = part.rsplit(":", 1)
        try:
            items.append((_common_species_name(code), float(probability)))
        except ValueError:
            continue

    items.sort(key=lambda item: item[1], reverse=True)
    if limit is not None:
        return items[:limit]
    return items


def _summary_dataframe(itinerary) -> pd.DataFrame:
    rows = []
    cumulative = 0.0
    for row in itinerary.leg_rows():
        cumulative += row["expected_new_sp"]
        top_species = _species_items(row["species"], limit=4)
        loc_id = row.get("loc_id") or ""
        rows.append(
            {
                "Stop": int(row["leg"]) + 1,
                "Site": row["site"],
                "eBird hotspot": f"https://ebird.org/hotspot/{loc_id}" if loc_id else "",
                "Arrive": row["arrive"],
                "Depart": row["depart"],
                "Drive min": int(row["drive_min"]),
                "Birding min": round(float(row["dwell_min"]), 1),
                "Expected new": round(float(row["expected_new_sp"]), 1),
                "Cumulative expected": round(cumulative, 1),
                "Top new birds": ", ".join(
                    f"{name} ({probability:.0%})" for name, probability in top_species
                ),
            }
        )
    return pd.DataFrame(rows)


def _selected_species_probabilities(itinerary) -> pd.DataFrame:
    rows = []
    for leg, idx in enumerate(itinerary.route_idx):
        site = itinerary.hotspots.locName.iloc[idx]
        for species_idx, code in enumerate(itinerary.sp_all):
            probability = float(itinerary.gain_matrix[idx, species_idx])
            if probability <= 0:
                continue
            rows.append(
                {
                    "Stop": leg + 1,
                    "Site": site,
                    "Species code": code,
                    "Bird": _common_species_name(code),
                    "Probability": probability,
                }
            )
    return pd.DataFrame(rows)


def _combined_probability(probabilities: list[float]) -> float:
    miss_probability = 1.0
    for probability in probabilities:
        miss_probability *= 1 - probability
    return 1 - miss_probability


def _bird_highlight_frames(
    itinerary,
    *,
    specialty_min_probability: float = 0.20,
    specialty_gap: float = 0.20,
    shared_min_probability: float = 0.15,
    limit: int = 12,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    probabilities = _selected_species_probabilities(itinerary)
    if probabilities.empty:
        return pd.DataFrame(), pd.DataFrame()

    specialty_rows = []
    shared_rows = []

    for (species_code, bird), group in probabilities.groupby(["Species code", "Bird"], sort=False):
        ranked = group.sort_values("Probability", ascending=False).reset_index(drop=True)
        best = ranked.iloc[0]
        second_probability = float(ranked.iloc[1]["Probability"]) if len(ranked) > 1 else 0.0
        gap = float(best["Probability"]) - second_probability

        if float(best["Probability"]) >= specialty_min_probability and (
            gap >= specialty_gap or second_probability < shared_min_probability
        ):
            specialty_rows.append(
                {
                    "Stop": int(best["Stop"]),
                    "Hotspot": best["Site"],
                    "Species code": species_code,
                    "Bird": bird,
                    "Best chance": float(best["Probability"]),
                    "Next best": second_probability,
                    "Edge": gap,
                }
            )

        shared = ranked[ranked["Probability"] >= shared_min_probability]
        if len(shared) >= 2:
            shared_rows.append(
                {
                    "Species code": species_code,
                    "Bird": bird,
                    "Likely stops": len(shared),
                    "Route chance": _combined_probability(shared["Probability"].tolist()),
                    "Where": ", ".join(
                        f"{int(row['Stop'])}. {row['Site']} ({float(row['Probability']):.0%})"
                        for _, row in shared.iterrows()
                    ),
                }
            )

    specialties = pd.DataFrame(specialty_rows)
    if not specialties.empty:
        specialties = (
            specialties.sort_values(["Stop", "Best chance", "Edge"], ascending=[True, False, False])
            .groupby("Stop", group_keys=False)
            .head(limit)
            .reset_index(drop=True)
        )

    shared = pd.DataFrame(shared_rows)
    if not shared.empty:
        shared = shared.sort_values(
            ["Likely stops", "Route chance"],
            ascending=[False, False],
        ).head(limit).reset_index(drop=True)

    return specialties, shared


def _display_percent(value: float) -> str:
    return f"{value:.0%}"


def _stop_specialties(specialties: pd.DataFrame, *, per_stop: int = 8) -> dict[int, list[tuple[str, str, float]]]:
    if specialties.empty:
        return {}

    result: dict[int, list[tuple[str, str, float]]] = {}
    for stop, group in specialties.groupby("Stop"):
        result[int(stop)] = [
            (str(row["Species code"]), str(row["Bird"]), float(row["Best chance"]))
            for _, row in group.sort_values("Best chance", ascending=False).head(per_stop).iterrows()
        ]
    return result


def _route_species_probability_frame(
    itinerary,
    *,
    min_route_probability: float = 0.15,
    min_best_stop_probability: float = 0.15,
) -> pd.DataFrame:
    rows = []
    if not itinerary.route_idx:
        return pd.DataFrame()

    route_probabilities = itinerary.gain_matrix[itinerary.route_idx].astype(float)
    for species_idx, code in enumerate(itinerary.sp_all):
        probabilities = route_probabilities[:, species_idx]
        positive_positions = [
            position
            for position, probability in enumerate(probabilities)
            if float(probability) > 0
        ]
        if not positive_positions:
            continue

        route_chance = _combined_probability([float(probabilities[position]) for position in positive_positions])
        best_position = max(positive_positions, key=lambda position: float(probabilities[position]))
        best_probability = float(probabilities[best_position])
        if route_chance < min_route_probability and best_probability < min_best_stop_probability:
            continue

        ranked_positions = sorted(
            positive_positions,
            key=lambda position: float(probabilities[position]),
            reverse=True,
        )
        top_stops = []
        for position in ranked_positions[:5]:
            hotspot_idx = itinerary.route_idx[position]
            top_stops.append(
                f"{position + 1}. {itinerary.hotspots.locName.iloc[hotspot_idx]} ({float(probabilities[position]):.0%})"
            )

        best_hotspot_idx = itinerary.route_idx[best_position]
        rows.append(
            {
                "Bird": _common_species_name(code),
                "Route chance": route_chance,
                "Best stop": f"{best_position + 1}. {itinerary.hotspots.locName.iloc[best_hotspot_idx]}",
                "Best stop chance": best_probability,
                "Contributing stops": len(positive_positions),
                "Top contributing stops": ", ".join(top_stops),
            }
        )

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["Route chance", "Best stop chance", "Bird"],
        ascending=[False, False, True],
    ).reset_index(drop=True)


def _common_species_codes(
    itinerary,
    *,
    min_probability: float = 0.15,
    route_share: float = 0.60,
) -> set[str]:
    route_count = len(itinerary.route_idx)
    if route_count == 0:
        return set()

    threshold = max(1 if route_count == 1 else 2, math.ceil(route_count * route_share))
    route_probabilities = itinerary.gain_matrix[itinerary.route_idx]
    counts = (route_probabilities >= min_probability).sum(axis=0)
    return {
        code
        for species_idx, code in enumerate(itinerary.sp_all)
        if int(counts[species_idx]) >= threshold
    }


def _stop_probability_items(
    itinerary,
    stop_number: int,
    *,
    min_probability: float = 0.05,
) -> list[dict[str, object]]:
    route_position = stop_number - 1
    if route_position < 0 or route_position >= len(itinerary.route_idx):
        return []

    hotspot_idx = itinerary.route_idx[route_position]
    items = []
    for species_idx, code in enumerate(itinerary.sp_all):
        probability = float(itinerary.gain_matrix[hotspot_idx, species_idx])
        if probability < min_probability:
            continue
        items.append(
            {
                "code": code,
                "name": _common_species_name(code),
                "probability": probability,
            }
        )
    return sorted(items, key=lambda item: float(item["probability"]), reverse=True)


def _classify_stop_birds(
    itinerary,
    stop_number: int,
    specialties: list[tuple[str, str, float]],
    *,
    common_codes: Optional[set[str]] = None,
    min_probability: float = 0.05,
    max_common: Optional[int] = None,
    max_uncommon: Optional[int] = None,
    max_rare: Optional[int] = None,
) -> dict[str, list[dict[str, object]]]:
    common_codes = common_codes if common_codes is not None else _common_species_codes(itinerary)
    specialty_codes = {code for code, _, _ in specialties}
    raw_items = _stop_probability_items(itinerary, stop_number, min_probability=min_probability)

    common = [
        item
        for item in raw_items
        if str(item["code"]) in common_codes and str(item["code"]) not in specialty_codes
    ]
    uncommon = [
        item
        for item in raw_items
        if str(item["code"]) not in common_codes and str(item["code"]) not in specialty_codes
    ]
    rare = [
        {"code": code, "name": bird, "probability": probability}
        for code, bird, probability in specialties
    ]
    if max_common is not None:
        common = common[:max_common]
    if max_uncommon is not None:
        uncommon = uncommon[:max_uncommon]
    if max_rare is not None:
        rare = rare[:max_rare]
    return {"common": common, "uncommon": uncommon, "rare": rare}


def _chip_row_html(
    items: list[dict[str, object]],
    *,
    empty_text: str,
    chip_class: str = "",
) -> str:
    if not items:
        return f'<div class="bbd-chip-row"><span class="bbd-chip bbd-empty-chip">{html.escape(empty_text)}</span></div>'

    extra_class = f" {chip_class}" if chip_class else ""
    chips = "".join(
        f'<span class="bbd-chip{extra_class}">{html.escape(str(item["name"]))} {float(item["probability"]):.0%}</span>'
        for item in items
    )
    return f'<div class="bbd-chip-row">{chips}</div>'


def _render_route_brief(summary_df: pd.DataFrame, total_drive: float, total_dwell: float, expected_species: float) -> None:
    if summary_df.empty:
        return

    first_site = html.escape(str(summary_df.iloc[0]["Site"]))
    last_row = summary_df.iloc[-1]
    best_row = summary_df.sort_values("Expected new", ascending=False).iloc[0]
    last_site = html.escape(str(last_row["Site"]))
    best_site = html.escape(str(best_row["Site"]))

    st.markdown(
        f"""
        <div class="bbd-callout">
            <div class="bbd-callout-title">Route at a glance</div>
            <div class="bbd-callout-body">
                Start at <strong>{first_site}</strong> and finish at <strong>{last_site}</strong> around <strong>{last_row["Depart"]}</strong>.
                The plan estimates <strong>{expected_species:.1f}</strong> species, with <strong>{_format_minutes(total_dwell)}</strong> birding and
                <strong>{_format_minutes(total_drive)}</strong> driving. The biggest expected gain is <strong>{best_row["Expected new"]:.1f}</strong>
                species at <strong>{best_site}</strong>.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_route_charts(summary_df: pd.DataFrame) -> None:
    if summary_df.empty:
        return

    chart_df = summary_df.copy()
    chart_df["Stop label"] = chart_df["Stop"].astype(str) + ". " + chart_df["Site"].str.slice(0, 26)

    left, right = st.columns(2)
    with left:
        st.subheader("Expected species by stop")
        st.bar_chart(
            chart_df.set_index("Stop label")[["Expected new"]],
            use_container_width=True,
        )
    with right:
        st.subheader("Time by stop")
        st.bar_chart(
            chart_df.set_index("Stop label")[["Drive min", "Birding min"]],
            use_container_width=True,
        )


def _render_bird_highlights(specialties: pd.DataFrame, shared: pd.DataFrame) -> None:
    st.subheader("Bird highlights")
    st.markdown(
        '<div class="bbd-section-note">Specialties are species where one planned stop is clearly better than the other route stops. Shared birds have useful odds at multiple stops.</div>',
        unsafe_allow_html=True,
    )

    left, right = st.columns(2)
    with left:
        st.markdown("**Hotspot specialties**")
        if specialties.empty:
            st.info("No clear hotspot specialties above the current probability threshold.")
        else:
            display = specialties.copy()
            display["Best chance"] = display["Best chance"].map(_display_percent)
            display["Next best"] = display["Next best"].map(_display_percent)
            display["Edge"] = display["Edge"].map(_display_percent)
            st.dataframe(
                display[["Stop", "Hotspot", "Bird", "Best chance", "Next best", "Edge"]],
                use_container_width=True,
                hide_index=True,
            )

    with right:
        st.markdown("**Likely at multiple stops**")
        if shared.empty:
            st.info("No species currently meet the repeated-likelihood threshold.")
        else:
            display = shared.copy()
            display["Route chance"] = display["Route chance"].map(_display_percent)
            st.dataframe(
                display[["Bird", "Likely stops", "Route chance", "Where"]],
                use_container_width=True,
                hide_index=True,
            )


def _render_trip_probabilities(itinerary, *, display_min_prob: float) -> None:
    route_probabilities = _route_species_probability_frame(
        itinerary,
        min_route_probability=display_min_prob,
        min_best_stop_probability=display_min_prob,
    )
    st.markdown(
        """
        <div class="bbd-section-title">
            Full trip species probabilities
            <span class="bbd-tooltip" title="For each species, the route chance is calculated as 1 minus the product of missing it at every planned stop: 1 - Π(1 - p_stop). This treats hotspot probabilities as independent estimates, so several modest chances can combine into one stronger trip-level chance.">?</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="bbd-section-note">This table keeps species whose full-route chance or best single-stop chance clears the displayed probability floor.</div>',
        unsafe_allow_html=True,
    )
    if route_probabilities.empty:
        st.info("No species meet the displayed probability floor for the route.")
        return

    display = route_probabilities.copy()
    display["Route chance"] = display["Route chance"].map(_display_percent)
    display["Best stop chance"] = display["Best stop chance"].map(_display_percent)
    st.dataframe(
        display[
            [
                "Bird",
                "Route chance",
                "Best stop",
                "Best stop chance",
                "Contributing stops",
                "Top contributing stops",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )


def _render_stop_cards(
    itinerary,
    specialties_by_stop: dict[int, list[tuple[str, str, float]]],
    *,
    display_min_prob: float,
) -> None:
    st.subheader("Stop plan")
    st.markdown(
        '<div class="bbd-section-note">Read this top to bottom for the route order, timing, eBird links, and expected birds at each location.</div>',
        unsafe_allow_html=True,
    )
    common_codes = _common_species_codes(itinerary, min_probability=display_min_prob)
    for row in itinerary.leg_rows():
        stop_number = int(row["leg"]) + 1
        specialties = specialties_by_stop.get(stop_number, [])
        bird_groups = _classify_stop_birds(
            itinerary,
            stop_number,
            specialties,
            common_codes=common_codes,
            min_probability=display_min_prob,
        )
        site = html.escape(str(row["site"]))
        loc_id = str(row.get("loc_id") or "")
        hotspot_url = f"https://ebird.org/hotspot/{html.escape(loc_id)}" if loc_id else ""

        with st.container(border=True):
            st.markdown(
                f"""
                <div class="bbd-stop-title">
                    <span class="bbd-stop-number">{stop_number}</span>{site}
                </div>
                <div class="bbd-stop-meta">
                    {row["arrive"]} to {row["depart"]} · drive {row["drive_min"]} min · bird {row["dwell_min"]:.1f} min ·
                    +{row["expected_new_sp"]:.1f} expected species
                </div>
                """,
                unsafe_allow_html=True,
            )
            if hotspot_url:
                st.markdown(
                    f'<a class="bbd-hotspot-link" href="{hotspot_url}" target="_blank" rel="noopener noreferrer">Open eBird hotspot</a>',
                    unsafe_allow_html=True,
                )

            with st.expander(
                f"Expected common birds ({len(bird_groups['common'])})",
                expanded=False,
            ):
                st.markdown(
                    _chip_row_html(
                        bird_groups["common"],
                        empty_text="No common birds above the route threshold.",
                        chip_class="bbd-common-chip",
                    ),
                    unsafe_allow_html=True,
                )

            st.markdown('<div class="bbd-chip-label">Uncommon birds</div>', unsafe_allow_html=True)
            st.markdown(
                _chip_row_html(
                    bird_groups["uncommon"],
                    empty_text="No uncommon birds above the probability threshold.",
                ),
                unsafe_allow_html=True,
            )

            st.markdown('<div class="bbd-chip-label">Rare / hotspot specialties</div>', unsafe_allow_html=True)
            st.markdown(
                _chip_row_html(
                    bird_groups["rare"],
                    empty_text="No clear specialties for this stop.",
                    chip_class="bbd-rare-chip",
                ),
                unsafe_allow_html=True,
            )


def _render_results(itinerary, *, display_min_prob: float = 0.15) -> None:
    raw_df = itinerary.to_dataframe()
    summary_df = _summary_dataframe(itinerary)
    specialties, shared = _bird_highlight_frames(itinerary)
    specialties_by_stop = _stop_specialties(specialties)
    total_drive = int(summary_df["Drive min"].sum()) if "Drive min" in summary_df else 0
    total_dwell = float(summary_df["Birding min"].sum()) if "Birding min" in summary_df else 0.0
    finish_time = summary_df.iloc[-1]["Depart"] if not summary_df.empty else "--"

    metric_cols = st.columns(4)
    metric_cols[0].metric("Expected species", f"{itinerary.expected_species:.1f}")
    metric_cols[1].metric("Stops", str(len(itinerary.route_idx)))
    metric_cols[2].metric("Drive", _format_minutes(total_drive))
    metric_cols[3].metric("Finish", finish_time)

    _render_route_brief(summary_df, total_drive, total_dwell, itinerary.expected_species)
    _render_stop_cards(itinerary, specialties_by_stop, display_min_prob=display_min_prob)
    _render_bird_highlights(specialties, shared)
    _render_trip_probabilities(itinerary, display_min_prob=display_min_prob)
    _render_route_charts(summary_df)

    overview_tab, table_tab, map_tab = st.tabs(["Overview", "Table", "Map"])

    with overview_tab:
        st.subheader("Route summary")
        st.markdown(
            '<div class="bbd-table-note">Compact view for scanning the plan. Full species details are in the stop cards and CSV.</div>',
            unsafe_allow_html=True,
        )
        st.dataframe(
            summary_df[
                [
                    "Stop",
                    "Site",
                    "eBird hotspot",
                    "Arrive",
                    "Depart",
                    "Drive min",
                    "Birding min",
                    "Expected new",
                    "Cumulative expected",
                    "Top new birds",
                ]
            ],
            use_container_width=True,
            hide_index=True,
            column_config={
                "eBird hotspot": st.column_config.LinkColumn(
                    "eBird",
                    display_text="Open",
                )
            },
        )

    with table_tab:
        st.subheader("Raw itinerary")
        st.dataframe(raw_df, use_container_width=True, hide_index=True)

        csv = raw_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download CSV",
            data=csv,
            file_name="big_day_itinerary.csv",
            mime="text/csv",
        )

    with map_tab:
        map_df = _route_map_data(itinerary)
        if not map_df.empty:
            st.subheader("Map")
            st.map(map_df, latitude="lat", longitude="lon")
        else:
            st.info("No coordinates available for this route.")


def main() -> None:
    st.set_page_config(
        page_title="Big Day Optimizer",
        layout="wide",
    )
    _page_style()

    st.title("Big Day Optimizer")
    st.markdown(
        '<div class="bbd-subtitle">Build a one-day eBird route from checklist detection rates, drive time, and stop constraints.</div>',
        unsafe_allow_html=True,
    )

    config = _read_config()
    errors = _validate(config)

    itinerary = st.session_state.get("last_itinerary")
    run = st.button("Run optimizer", type="primary")
    auto_run = (
        itinerary is None
        and not st.session_state.get("default_run_attempted")
        and not errors
    )
    if auto_run:
        st.session_state["default_run_attempted"] = True

    run = run or auto_run
    if run:
        if errors:
            for error in errors:
                st.error(error)
            return

        with st.spinner("Fetching eBird data, travel times, and solving route..."):
            try:
                itinerary = _run_optimizer(config)
            except Exception as exc:
                st.error(str(exc))
                return

        st.session_state["last_itinerary"] = itinerary

    itinerary = st.session_state.get("last_itinerary")
    if itinerary is None:
        st.info("Set the run options, then start the optimizer.")
        return

    _render_results(itinerary, display_min_prob=config.display_min_prob)


if __name__ == "__main__":
    main()
