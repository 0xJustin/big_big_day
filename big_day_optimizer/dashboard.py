from __future__ import annotations

import os
import datetime as dt
import html
import json
import math
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import streamlit as st

from .optimizer import BigDayOptimizer
from .solver import Itinerary
from .utils import translate_codes


DEFAULT_REGION = "US-VA-107"
DEFAULT_OBSERVATION_DATE = dt.date(2026, 5, 2)
PUBLIC_DEPLOYMENT_ENV = "BBD_PUBLIC_DEPLOYMENT"
EBIRD_API_HELP_URL = "https://support.ebird.org/en/support/solutions/articles/48000838205-download-ebird-data"


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
    min_checklists_per_hotspot: int
    max_hotspots: int
    min_stops: int
    max_stops: int
    min_prob: float
    display_min_prob: float
    nearby_drive_min: int
    nearby_pair_penalty: float
    base_idle: int
    dwell_per: int
    time_limit: int


def _page_style() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;500;600;700;800;900&family=Source+Serif+4:opsz,wght@8..60,700;8..60,850&display=swap');

        :root {
            --bbd-ink: #243238;
            --bbd-strong: #10252d;
            --bbd-muted: #54656b;
            --bbd-faint: #748186;
            --bbd-line: #ccd7d5;
            --bbd-line-strong: #8fa6a2;
            --bbd-panel: #fffdf8;
            --bbd-panel-soft: #f5f4ee;
            --bbd-sidebar: #f1f4ef;
            --bbd-field: #fffdf8;
            --bbd-field-border: #91a39e;
            --bbd-accent: #007b78;
            --bbd-accent-hover: #00635f;
            --bbd-accent-soft: #dcefed;
            --bbd-banner: #3d6377;
            --bbd-banner-dark: #31556a;
            --bbd-banner-light: #d9e7ed;
            --bbd-highlight: #80bc42;
            --bbd-rust: #b45d3f;
            --bbd-gold: #b9892d;
            --bbd-sky: #e5eff1;
            --bbd-info-bg: #e8f1f2;
            --bbd-info-text: #17464e;
            --bbd-shadow: 0 8px 18px rgba(23, 47, 57, 0.10);
            --bbd-soft-shadow: 0 4px 12px rgba(23, 47, 57, 0.07);
            --bbd-serif: "Source Serif 4", Georgia, serif;
            --bbd-sans: "Source Sans 3", "Avenir Next", "Helvetica Neue", sans-serif;
        }

        html, body, .stApp {
            font-family: var(--bbd-sans) !important;
            color: var(--bbd-ink) !important;
        }

        .stApp {
            background: #f4f6f2;
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
            padding: 1.75rem clamp(1rem, 3vw, 3rem) 3.5rem;
            position: relative;
            z-index: 1;
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
            background: transparent !important;
            border: 0 !important;
            height: 0 !important;
            min-height: 0 !important;
        }

        [data-testid="stToolbar"],
        [data-testid="stStatusWidget"] {
            display: none !important;
        }

        [data-testid="stHeader"] *,
        [data-testid="stToolbar"] *,
        [data-testid="stStatusWidget"] *,
        [role="banner"] *,
        header * {
            color: #fff8e7 !important;
            fill: #fff8e7 !important;
            opacity: 1 !important;
            -webkit-text-fill-color: #fff8e7 !important;
        }

        [data-testid="stHeader"] img,
        [data-testid="stHeader"] svg,
        [data-testid="stToolbar"] img,
        [data-testid="stToolbar"] svg,
        [data-testid="stStatusWidget"] img,
        [data-testid="stStatusWidget"] svg,
        [role="banner"] img,
        [role="banner"] svg {
            filter: brightness(0) invert(1);
        }

        [data-testid="stSidebar"] {
            background: var(--bbd-sidebar) !important;
            border-right: 1px solid rgba(96, 113, 112, 0.26);
            box-shadow: 5px 0 18px rgba(25, 44, 49, 0.06);
        }

        [data-testid="stSidebar"] > div {
            background:
                linear-gradient(180deg, #f7f8f2 0%, #eef2eb 100%) !important;
        }

        [data-testid="stSidebar"] [data-testid="stSidebarContent"] {
            background:
                linear-gradient(180deg, #f7f8f2 0%, #eef2eb 100%) !important;
            box-sizing: border-box;
            padding: 0 !important;
            width: 100%;
        }

        [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
            gap: 0.45rem;
            width: 100%;
        }

        [data-testid="stSidebar"] [data-testid="stElementContainer"] {
            box-sizing: border-box;
            padding-left: 1.05rem;
            padding-right: 1.05rem;
            width: 100%;
        }

        [data-testid="stSidebar"] [data-testid="stElementContainer"] > div {
            box-sizing: border-box;
            max-width: 100%;
        }

        [data-testid="stSidebar"] [data-testid="stElementContainer"]:has(.bbd-sidebar-brand) {
            padding-left: 0;
            padding-right: 0;
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
            font-family: var(--bbd-sans) !important;
        }

        h1, h2, h3 {
            letter-spacing: -0.025em;
        }

        h1 {
            font-family: var(--bbd-sans) !important;
            font-size: clamp(2.6rem, 6vw, 4.65rem);
            font-weight: 900;
            line-height: 0.96;
            color: var(--bbd-strong) !important;
            margin: 0;
        }

        h2, h3 {
            font-family: var(--bbd-sans) !important;
            color: var(--bbd-strong) !important;
        }

        .bbd-hero {
            background: linear-gradient(180deg, var(--bbd-banner) 0%, var(--bbd-banner-dark) 100%);
            border: 1px solid rgba(26, 63, 78, 0.36);
            border-radius: 8px;
            box-shadow: 0 8px 18px rgba(31, 51, 61, 0.12);
            margin-bottom: 0.85rem;
            overflow: hidden;
            padding: 0.62rem clamp(1rem, 2.5vw, 1.35rem) 0.68rem;
            position: relative;
        }

        .bbd-hero::after {
            display: none;
        }

        .bbd-hero-copy {
            color: #e8f1f4 !important;
            font-size: 0.86rem;
            font-style: italic;
            line-height: 1.25;
            margin: 0.06rem 0 0;
            max-width: 720px;
        }

        .bbd-hero p.bbd-hero-copy,
        .bbd-hero .bbd-hero-copy {
            color: #e8f1f4 !important;
            -webkit-text-fill-color: #e8f1f4 !important;
        }

        .bbd-hero-meta {
            color: #d7e7ed !important;
            font-size: 0.75rem;
            font-weight: 800;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }

        .bbd-breadcrumb {
            color: #d7e6ec !important;
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 0.01em;
            margin-bottom: 0.38rem;
        }

        .bbd-hero-main {
            align-items: end;
            display: flex;
            gap: 1rem;
            justify-content: space-between;
        }

        .bbd-hero h1 {
            color: #ffffff !important;
            font-size: clamp(1.55rem, 3vw, 2.35rem);
            font-weight: 820;
            letter-spacing: -0.035em;
        }

        .bbd-hero-status {
            align-items: center;
            background: rgba(18, 43, 54, 0.34);
            border: 1px solid rgba(255, 255, 255, 0.18);
            border-radius: 999px;
            color: #f7fbfb !important;
            display: inline-flex;
            font-size: 0.72rem;
            font-weight: 800;
            gap: 0.35rem;
            line-height: 1;
            padding: 0.36rem 0.58rem;
            white-space: nowrap;
        }

        .bbd-product-tabs {
            display: flex;
            flex-wrap: wrap;
            gap: 0.34rem;
            margin-top: 0.62rem;
        }

        .bbd-product-tab {
            border: 1px solid rgba(222, 239, 244, 0.48);
            border-radius: 999px;
            color: #e8f2f5 !important;
            -webkit-text-fill-color: #e8f2f5 !important;
            display: inline-flex;
            font-size: 0.74rem;
            font-weight: 800;
            line-height: 1;
            padding: 0.34rem 0.62rem;
        }

        .bbd-product-tab.is-active {
            background: var(--bbd-highlight);
            border-color: var(--bbd-highlight);
            color: #123126 !important;
            -webkit-text-fill-color: #123126 !important;
        }

        .bbd-hero .bbd-product-tab.is-active {
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
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
            font-size: 0.78rem !important;
            font-weight: 800 !important;
            letter-spacing: 0.01em;
            margin-bottom: 0.08rem !important;
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
            min-height: 2.18rem !important;
            padding-bottom: 0.34rem !important;
            padding-top: 0.34rem !important;
        }

        [data-testid="stSidebar"] [data-baseweb="select"] > div {
            min-height: 2.18rem !important;
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
            box-sizing: border-box !important;
            border-radius: 8px !important;
            max-width: 100% !important;
            min-height: 2.25rem !important;
            transition: border-color 160ms ease, box-shadow 160ms ease, transform 160ms ease;
            width: 100% !important;
        }

        [data-testid="stSidebar"] [data-testid="stTextInput"],
        [data-testid="stSidebar"] [data-testid="stTimeInput"],
        [data-testid="stSidebar"] [data-testid="stSelectbox"],
        [data-testid="stSidebar"] [data-testid="stNumberInput"],
        [data-testid="stSidebar"] [data-testid="stSlider"] {
            box-sizing: border-box;
            margin-bottom: 0.26rem;
            max-width: 100%;
            width: 100%;
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

        div[data-baseweb="input"]:focus-within,
        div[data-baseweb="select"]:focus-within,
        div[data-baseweb="textarea"]:focus-within,
        div[data-baseweb="base-input"]:focus-within {
            border-color: #1d402d !important;
            box-shadow: 0 0 0 3px rgba(201, 223, 99, 0.34) !important;
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

        .stButton > button {
            background: var(--bbd-accent) !important;
            border: 1px solid rgba(0, 67, 64, 0.55) !important;
            border-radius: 999px;
            color: #fffdf7 !important;
            box-shadow: 0 6px 12px rgba(0, 91, 88, 0.14);
            font-weight: 800;
            padding: 0.52rem 1rem;
            transition: transform 150ms ease, box-shadow 150ms ease, background 150ms ease;
        }

        .stButton > button p,
        .stButton > button span {
            color: #fffdf7 !important;
        }

        .stButton > button:hover {
            background: var(--bbd-accent-hover) !important;
            border-color: var(--bbd-accent-hover) !important;
            box-shadow: 0 10px 20px rgba(0, 91, 88, 0.20);
            color: #fffdf7 !important;
            transform: translateY(-1px);
        }

        [data-testid="stAlert"] {
            background: var(--bbd-info-bg) !important;
            border: 1px solid #7fb2c5 !important;
            border-radius: 18px !important;
            min-height: unset !important;
        }

        [data-testid="stAlert"] *,
        [data-testid="stAlert"] p,
        [data-testid="stAlert"] div[data-testid="stMarkdownContainer"] {
            color: var(--bbd-info-text) !important;
            opacity: 1 !important;
        }

        [data-testid="stDataFrame"] {
            border: 1px solid var(--bbd-line);
            border-radius: 18px;
            overflow: hidden;
            box-shadow: var(--bbd-soft-shadow);
        }

        .bbd-subtitle {
            max-width: 760px;
            color: var(--bbd-muted) !important;
            font-size: 1.05rem;
            margin-top: -0.7rem;
            margin-bottom: 0.85rem;
        }

        .bbd-sidebar-brand {
            background: linear-gradient(180deg, var(--bbd-banner) 0%, var(--bbd-banner-dark) 100%);
            border: 1px solid rgba(255, 255, 255, 0.16);
            border-left: 0;
            border-radius: 0;
            border-right: 0;
            border-top: 0;
            box-shadow: 0 5px 12px rgba(23, 47, 57, 0.08);
            margin: 0 0 0.62rem;
            padding: 0.68rem 1.05rem 0.72rem;
            width: 100%;
        }

        .bbd-sidebar-brand span {
            color: #dce8ed !important;
            display: block;
            font-size: 0.62rem;
            font-weight: 900;
            letter-spacing: 0.13em;
            margin-bottom: 0.22rem;
            text-transform: uppercase;
        }

        .bbd-sidebar-brand strong {
            color: #fffdf7 !important;
            display: block;
            font-family: var(--bbd-sans);
            font-size: 1.02rem;
            font-weight: 850;
            letter-spacing: -0.02em;
            line-height: 1;
        }

        .bbd-help {
            background: rgba(255, 248, 232, 0.92);
            border: 1px solid #d5c9a9;
            border-radius: 16px;
            color: var(--bbd-strong) !important;
            font-size: 0.9rem;
            line-height: 1.42;
            margin: 0.25rem 0 0.85rem;
            padding: 0.75rem 0.8rem;
        }

        .bbd-help strong {
            color: var(--bbd-strong) !important;
        }

        .bbd-public-note {
            background: rgba(232, 241, 242, 0.72);
            border: 1px solid #c5d7d9;
            border-radius: 10px;
            color: var(--bbd-muted) !important;
            font-size: 0.78rem;
            line-height: 1.34;
            margin: 0.1rem 0 0.52rem;
            padding: 0.5rem 0.58rem;
        }

        .bbd-public-note a {
            color: var(--bbd-accent-hover) !important;
            font-weight: 800;
            text-decoration: none;
        }

        .bbd-public-note a:hover,
        .bbd-public-note a:focus-visible {
            text-decoration: underline;
        }

        .bbd-sidebar-title {
            color: var(--bbd-strong) !important;
            font-family: var(--bbd-serif);
            font-size: 1.45rem;
            font-weight: 900;
            letter-spacing: -0.045em;
            line-height: 1;
            margin: 0 0 0.65rem;
        }

        .bbd-sidebar-section {
            color: var(--bbd-muted) !important;
            font-size: 0.68rem;
            font-weight: 900;
            letter-spacing: 0.08em;
            margin: 0.55rem 0 0.02rem;
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
            border-radius: 16px !important;
            background: rgba(255, 251, 239, 0.55) !important;
        }

        [data-testid="stSidebar"] summary p {
            color: var(--bbd-strong) !important;
            font-size: 0.86rem !important;
            font-weight: 850 !important;
        }

        .bbd-callout,
        .bbd-stop-card,
        .bbd-route-summary {
            background: var(--bbd-panel);
            border: 1px solid var(--bbd-line);
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(23, 47, 57, 0.05);
        }

        .bbd-callout {
            border-left: 4px solid var(--bbd-accent);
            margin: 0.95rem 0 1.15rem;
            padding: 0.76rem 0.95rem 0.78rem 1rem;
        }

        .bbd-callout-title,
        .bbd-stop-title {
            color: var(--bbd-strong) !important;
            font-weight: 900;
            margin-bottom: 0.25rem;
        }

        .bbd-callout-title {
            font-size: 1.08rem;
            letter-spacing: -0.01em;
        }

        .bbd-callout-body,
        .bbd-stop-meta {
            color: var(--bbd-muted) !important;
            line-height: 1.45;
        }

        .bbd-stop-card {
            margin-bottom: 0.78rem;
            padding: 0.92rem 1rem;
        }

        .bbd-stop-number {
            align-items: center;
            background: var(--bbd-accent);
            border: 1px solid #b8d0c8;
            border-radius: 999px;
            color: #fffdf7 !important;
            display: inline-flex;
            font-size: 0.85rem;
            font-weight: 800;
            height: 1.75rem;
            justify-content: center;
            margin-right: 0.55rem;
            width: 1.75rem;
        }

        .bbd-chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
            margin-top: 0.8rem;
        }

        .bbd-chip {
            background: #fbfdfb;
            border: 1px solid #c8d8cf;
            border-left: 3px solid var(--bbd-accent);
            border-radius: 5px;
            color: var(--bbd-strong) !important;
            display: inline-block;
            font-size: 0.78rem;
            font-weight: 700;
            padding: 0.24rem 0.48rem;
        }

        .bbd-specialty-chip {
            background: #fff5d9;
            border-color: #d8c796;
            border-left-color: var(--bbd-gold);
        }

        .bbd-rare-chip {
            background: #fff0e8;
            border-color: #e0c0ad;
            border-left-color: var(--bbd-rust);
        }

        .bbd-common-chip {
            background: #eef5ef;
            border-color: #c7d8c9;
            border-left-color: #789878;
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
            font-family: var(--bbd-sans);
            font-size: clamp(1.45rem, 2.5vw, 2rem);
            font-weight: 900;
            letter-spacing: -0.025em;
            margin: 1.25rem 0 0.35rem;
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

        .bbd-stat-grid {
            display: grid;
            gap: 0.75rem;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            margin: 0.95rem 0 1.05rem;
        }

        .bbd-stat-card {
            background: var(--bbd-panel);
            border: 1px solid var(--bbd-line);
            border-top: 4px solid var(--bbd-accent);
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(23, 47, 57, 0.05);
            min-height: 6.7rem;
            overflow: hidden;
            padding: 0.85rem 0.95rem;
            position: relative;
        }

        .bbd-stat-card::before {
            display: none;
        }

        .bbd-stat-label {
            color: var(--bbd-muted) !important;
            font-size: 0.7rem;
            font-weight: 900;
            letter-spacing: 0.11em;
            margin-bottom: 0.58rem;
            text-transform: uppercase;
        }

        .bbd-stat-value {
            color: var(--bbd-strong) !important;
            font-family: var(--bbd-sans);
            font-size: clamp(1.85rem, 3vw, 2.75rem);
            font-weight: 900;
            letter-spacing: -0.05em;
            line-height: 0.9;
        }

        .bbd-stat-caption {
            color: var(--bbd-faint) !important;
            font-size: 0.8rem;
            font-weight: 700;
            margin-top: 0.75rem;
        }

        [data-testid="stTabs"] [role="tablist"] {
            background: rgba(255, 251, 239, 0.7);
            border: 1px solid var(--bbd-line);
            border-radius: 999px;
            display: inline-flex;
            gap: 0.2rem;
            padding: 0.25rem;
        }

        [data-testid="stTabs"] [role="tab"] {
            border-radius: 999px;
            color: var(--bbd-muted) !important;
            font-weight: 800;
            padding: 0.3rem 0.9rem;
        }

        [data-testid="stTabs"] [aria-selected="true"] {
            background: var(--bbd-accent) !important;
            color: #fffdf7 !important;
        }

        [data-testid="stSidebar"] div[data-testid="stVerticalBlockBorderWrapper"] {
            background: rgba(255, 251, 239, 0.78);
            border-color: var(--bbd-line) !important;
            border-radius: 20px !important;
            box-shadow: 0 12px 30px rgba(20, 33, 23, 0.08);
        }

        [data-testid="stMain"] div[data-testid="stVerticalBlockBorderWrapper"] {
            background: rgba(255, 251, 239, 0.88);
            border-color: rgba(98, 116, 94, 0.28) !important;
            border-radius: 26px !important;
            box-shadow: var(--bbd-soft-shadow);
        }

        [data-testid="stMain"] div[data-testid="stVerticalBlockBorderWrapper"]:hover {
            border-color: rgba(29, 64, 45, 0.38) !important;
        }

        .bbd-data-grid,
        .bbd-highlight-grid {
            display: grid;
            gap: 0.9rem;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            margin: 0.75rem 0 1.15rem;
        }

        .bbd-data-card {
            background: var(--bbd-panel);
            border: 1px solid var(--bbd-line);
            border-radius: 10px;
            box-shadow: var(--bbd-soft-shadow);
            padding: 1rem;
        }

        .bbd-card-kicker {
            color: var(--bbd-muted) !important;
            font-size: 0.72rem;
            font-weight: 900;
            letter-spacing: 0.1em;
            margin-bottom: 0.25rem;
            text-transform: uppercase;
        }

        .bbd-data-card h3 {
            font-size: 1.2rem;
            font-weight: 900;
            margin: 0 0 0.75rem;
        }

        .bbd-bar-list {
            display: grid;
            gap: 0.72rem;
        }

        .bbd-bar-row {
            display: grid;
            gap: 0.25rem;
        }

        .bbd-bar-meta {
            align-items: baseline;
            display: flex;
            gap: 0.75rem;
            justify-content: space-between;
        }

        .bbd-bar-meta span,
        .bbd-prob-stop {
            color: var(--bbd-muted) !important;
            font-size: 0.86rem;
            line-height: 1.25;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .bbd-bar-meta strong,
        .bbd-prob-value {
            color: var(--bbd-strong) !important;
            font-size: 0.9rem;
            font-weight: 850;
            white-space: nowrap;
        }

        .bbd-bar-track,
        .bbd-stack-track,
        .bbd-prob-track {
            background: #e8eee6;
            border: 1px solid #d2ddd1;
            border-radius: 999px;
            height: 0.7rem;
            overflow: hidden;
            position: relative;
        }

        .bbd-bar-fill,
        .bbd-prob-fill {
            background: var(--bbd-accent);
            border-radius: 999px;
            display: block;
            height: 100%;
        }

        .bbd-stack-track {
            display: flex;
        }

        .bbd-stack-drive,
        .bbd-stack-birding {
            display: block;
            height: 100%;
        }

        .bbd-stack-drive {
            background: #9bb0a4;
        }

        .bbd-stack-birding {
            background: var(--bbd-accent);
        }

        .bbd-legend-row {
            color: var(--bbd-muted) !important;
            display: flex;
            flex-wrap: wrap;
            font-size: 0.82rem;
            font-weight: 750;
            gap: 0.85rem;
            margin-top: 0.75rem;
        }

        .bbd-legend-swatch {
            border-radius: 999px;
            display: inline-block;
            height: 0.62rem;
            margin-right: 0.32rem;
            width: 0.62rem;
        }

        .bbd-highlight-list,
        .bbd-prob-list {
            display: grid;
            gap: 0.55rem;
        }

        .bbd-highlight-item,
        .bbd-prob-row {
            background: #fbfaf4;
            border: 1px solid #dbe2d7;
            border-left: 3px solid var(--bbd-accent);
            border-radius: 8px;
            padding: 0.62rem 0.72rem;
        }

        .bbd-highlight-item.is-specialty {
            border-left-color: var(--bbd-rust);
        }

        .bbd-highlight-title,
        .bbd-prob-title {
            align-items: baseline;
            display: flex;
            gap: 0.7rem;
            justify-content: space-between;
        }

        .bbd-highlight-title strong,
        .bbd-prob-title strong {
            color: var(--bbd-strong) !important;
            font-size: 0.98rem;
            line-height: 1.2;
        }

        .bbd-highlight-detail,
        .bbd-prob-detail {
            color: var(--bbd-muted) !important;
            font-size: 0.84rem;
            line-height: 1.35;
            margin-top: 0.2rem;
        }

        .bbd-prob-list {
            max-height: 34rem;
            overflow: auto;
            padding-right: 0.15rem;
        }

        .bbd-prob-row {
            display: grid;
            gap: 0.35rem;
        }

        .bbd-prob-row.is-high {
            border-left-color: var(--bbd-accent);
        }

        .bbd-prob-row.is-medium {
            border-left-color: var(--bbd-gold);
        }

        .bbd-prob-row.is-low {
            border-left-color: var(--bbd-rust);
        }

        .bbd-prob-fill.is-high {
            background: var(--bbd-accent);
        }

        .bbd-prob-fill.is-medium {
            background: var(--bbd-gold);
        }

        .bbd-prob-fill.is-low {
            background: var(--bbd-rust);
        }

        html body header [data-testid="stToolbar"] *,
        html body header [data-testid="stToolbar"] button,
        html body header [data-testid="stToolbar"] button *,
        html body header [data-testid="stStatusWidget"] *,
        html body header [data-testid="stStatusWidget"] div,
        html body header [data-testid="stStatusWidget"] span {
            color: #fff8e7 !important;
            fill: #fff8e7 !important;
            opacity: 1 !important;
            -webkit-text-fill-color: #fff8e7 !important;
        }

        @media (max-width: 900px) {
            .block-container {
                padding: 1rem 1rem 2rem;
            }

            .bbd-hero {
                border-radius: 24px;
                padding: 1.2rem;
            }

            .bbd-stat-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }

            .bbd-data-grid,
            .bbd-highlight-grid {
                grid-template-columns: 1fr;
            }
        }

        @media (max-width: 520px) {
            .bbd-stat-grid {
                grid-template-columns: 1fr;
            }

            .bbd-stat-card {
                min-height: 6.8rem;
            }
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
    if _is_public_deployment():
        return ""

    env_api_key = os.getenv("EBIRD_API_KEY", "").strip()
    if env_api_key:
        return env_api_key

    repo_root = Path(__file__).resolve().parents[1]
    secrets_paths = [
        Path.home() / ".streamlit" / "secrets.toml",
        repo_root / ".streamlit" / "secrets.toml",
    ]
    for secrets_path in secrets_paths:
        if not secrets_path.exists():
            continue
        try:
            lines = secrets_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            if key.strip() != "EBIRD_API_KEY":
                continue
            secrets_api_key = value.strip().strip('"').strip("'")
            if secrets_api_key:
                return secrets_api_key

    token_path = repo_root / "ebird_token.json"
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


def _is_public_deployment() -> bool:
    return os.getenv(PUBLIC_DEPLOYMENT_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def _load_preloaded_loudoun_itinerary() -> Itinerary:
    """Return the bundled Loudoun demo route without calling external services."""
    demo_resource = resources.files("big_day_optimizer").joinpath(
        "data/loudoun_demo_itinerary.json"
    )
    with resources.as_file(demo_resource) as demo_path:
        payload = json.loads(demo_path.read_text(encoding="utf-8"))

    stops = payload["stops"]
    hotspots = pd.DataFrame(
        [
            {
                "locId": str(stop.get("locId", "")),
                "locName": str(stop["locName"]),
                "lat": float(stop["lat"]),
                "lng": float(stop["lng"]),
            }
            for stop in stops
        ]
    )

    species_codes: list[str] = []

    def add_species(code: str) -> None:
        if code not in species_codes:
            species_codes.append(code)

    for code in payload.get("shared_species", {}):
        add_species(code)
    for stop in stops:
        for code in stop.get("species", {}):
            add_species(code)

    species_index = {code: idx for idx, code in enumerate(species_codes)}
    gain_matrix = np.zeros((len(stops), len(species_codes)), dtype=float)

    for code, probabilities in payload.get("shared_species", {}).items():
        species_idx = species_index[code]
        for stop_idx, probability in enumerate(probabilities[: len(stops)]):
            gain_matrix[stop_idx, species_idx] = min(max(float(probability), 0.0), 1.0)

    for stop_idx, stop in enumerate(stops):
        for code, probability in stop.get("species", {}).items():
            gain_matrix[stop_idx, species_index[code]] = min(max(float(probability), 0.0), 1.0)

    travel = [[0 for _ in stops] for _ in stops]
    for stop_idx, stop in enumerate(stops):
        if stop_idx == 0:
            continue
        drive = int(stop.get("drive_from_previous_min", 0))
        travel[stop_idx - 1][stop_idx] = drive
        travel[stop_idx][stop_idx - 1] = drive

    route_idx = list(range(len(stops)))
    route_success = 1 - np.prod(1 - gain_matrix[route_idx], axis=0)
    seen_species = [
        code
        for code, probability in zip(species_codes, route_success)
        if float(probability) > 0
    ]

    return Itinerary(
        route_idx=route_idx,
        visit_mask=[True for _ in stops],
        seen_species=seen_species,
        hotspots=hotspots,
        travel=travel,
        start_time=dt.datetime.fromisoformat(str(payload["start_time"])),
        base_idle=int(payload.get("base_idle", 30)),
        dwell_per=int(payload.get("dwell_per", 2)),
        include_depot=False,
        depot_idx=None,
        sp_all=species_codes,
        gain_matrix=gain_matrix,
        expected_species=float(route_success.sum()),
    )


def _read_config() -> DashboardConfig:
    default_api_key = _load_default_api_key()

    with st.sidebar:
        st.markdown(
            """
            <div class="bbd-sidebar-brand">
                <span>Big Day</span>
                <strong>Route controls</strong>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown('<div class="bbd-sidebar-section">Trip setup</div>', unsafe_allow_html=True)
        api_key = st.text_input("eBird API key", value=default_api_key, type="password")
        if _is_public_deployment():
            st.markdown(
                f"""
                <div class="bbd-public-note">
                    Use your own eBird API key for live runs.
                    The key is used for this Streamlit session and is not stored by the app.
                    <a href="{EBIRD_API_HELP_URL}" target="_blank" rel="noopener noreferrer">Get a key</a>.
                </div>
                """,
                unsafe_allow_html=True,
            )
        region = st.text_input(
            "eBird area",
            value=DEFAULT_REGION,
            help="Region code such as US-VA-107 for Loudoun County.",
        )
        observation_date_text = st.text_input(
            "Date",
            value=DEFAULT_OBSERVATION_DATE.isoformat(),
            help="YYYY-MM-DD. Future dates use historical years.",
        )
        observation_date, date_error = _parse_observation_date(observation_date_text)

        st.divider()
        st.markdown('<div class="bbd-sidebar-section">Day</div>', unsafe_allow_html=True)
        start_time = st.time_input("Start time", value=dt.time(5, 30))
        end_time = st.time_input("End time", value=dt.time(20, 30))

        st.divider()
        st.markdown('<div class="bbd-sidebar-section">Sampling</div>', unsafe_allow_html=True)
        include_recent = st.checkbox(
            "Recent checklists",
            value=False,
            help="Use current-year checklists when they exist.",
        )
        historical_years = st.selectbox(
            "Historical years",
            options=[0, 1, 2, 3, 4, 5],
            index=2,
            help="Same calendar window from prior years.",
        )
        with st.expander("Sampling notes", expanded=False):
            st.markdown(
                """
                <div class="bbd-help">
                  This year skips future dates. Historical years use the same calendar window.
                </div>
                """,
                unsafe_allow_html=True,
            )
        depot_locid = None
        with st.expander("Advanced settings", expanded=False):
            depot_enabled = st.checkbox(
                "Use fixed starting hotspot",
                help="Force the route to begin at a specific eBird hotspot instead of letting the solver choose the best first stop.",
            )
            if depot_enabled:
                depot_locid = st.text_input(
                    "Starting hotspot locId",
                    help="eBird hotspot ID for the forced starting point, such as L123456. Leave blank to let the solver choose.",
                ).strip() or None

            back = st.number_input(
                "Days in each sample window",
                min_value=1,
                max_value=30,
                value=7,
                help="Number of days before and after the selected date to include when sampling checklist history.",
            )
            max_checklists_per_day = st.number_input(
                "Max checklists per hotspot/day",
                min_value=1,
                max_value=200,
                value=50,
                step=5,
                help="Maximum checklists to sample for one hotspot on one date. Lower values run faster; higher values use more data.",
            )
            min_checklists_per_hotspot = st.number_input(
                "Min checklists per hotspot",
                min_value=1,
                max_value=100,
                value=5,
                step=1,
                help="Exclude hotspots with fewer sampled checklists before solving.",
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
            min_stops = col_a.number_input(
                "Min stops",
                min_value=1,
                max_value=50,
                value=3,
                help="Minimum number of hotspots the route must include.",
            )
            max_stops = col_b.number_input(
                "Max stops",
                min_value=1,
                max_value=50,
                value=8,
                help="Maximum number of hotspots the route may include.",
            )
            min_prob = st.slider(
                "Solver floor",
                0.0,
                0.5,
                0.03,
                0.01,
                help="Ignore species-hotspot probabilities below this value.",
            )
            display_min_prob = st.slider(
                "Display floor",
                0.0,
                0.5,
                0.15,
                0.01,
                help="Hide lower-probability birds from the UI.",
            )
            st.markdown('<div class="bbd-sidebar-section">Nearby penalty</div>', unsafe_allow_html=True)
            nearby_drive_min = st.number_input(
                "Nearby drive minutes",
                min_value=0,
                max_value=30,
                value=8,
                help="Set to 0 to disable.",
            )
            nearby_pair_penalty = st.slider(
                "Penalty per pair",
                0.0,
                1.0,
                0.15,
                0.05,
                help="Expected-species penalty for a second nearby stop.",
            )
            base_idle = st.number_input(
                "Base dwell minutes",
                min_value=0,
                max_value=240,
                value=30,
                help="Minimum birding time assigned to each selected hotspot before species-based dwell time is added.",
            )
            dwell_per = st.number_input(
                "Minutes per expected new species",
                min_value=0,
                max_value=30,
                value=2,
                help="Additional birding time added for each expected new species at a stop.",
            )
            time_limit = st.number_input(
                "Solver time limit seconds",
                min_value=5,
                max_value=900,
                value=60,
                help="Maximum time the route solver can spend searching before returning the best route found.",
            )

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
        min_checklists_per_hotspot=int(min_checklists_per_hotspot),
        max_hotspots=int(max_hotspots),
        min_stops=int(min_stops),
        max_stops=int(max_stops),
        min_prob=float(min_prob),
        display_min_prob=float(display_min_prob),
        nearby_drive_min=int(nearby_drive_min),
        nearby_pair_penalty=float(nearby_pair_penalty),
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
    if config.min_checklists_per_hotspot <= 0:
        errors.append("Minimum checklists per hotspot must be positive.")
    if (
        config.observation_date is not None
        and config.observation_date > dt.date.today()
        and config.historical_years <= 0
    ):
        errors.append("Future dates require at least one historical year; eBird has no future checklists.")
    if config.depot_locid is None and config.min_stops < 1:
        errors.append("Free-start routes need at least one stop.")
    if config.nearby_drive_min < 0:
        errors.append("Nearby hotspot drive threshold cannot be negative.")
    if config.nearby_pair_penalty < 0:
        errors.append("Nearby hotspot penalty cannot be negative.")
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
        min_checklists_per_hotspot=config.min_checklists_per_hotspot,
        max_hotspots=config.max_hotspots,
        min_stops=config.min_stops,
        max_stops=config.max_stops,
        min_prob=config.min_prob,
        nearby_drive_min=config.nearby_drive_min,
        nearby_pair_penalty=config.nearby_pair_penalty,
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


def _bar_width(value: float, maximum: float) -> float:
    if maximum <= 0:
        return 0.0
    return max(0.0, min(100.0, (value / maximum) * 100.0))


def _compact_html(fragment: str) -> str:
    """Remove indentation that Streamlit Markdown can mistake for code blocks."""
    return " ".join(line.strip() for line in fragment.splitlines() if line.strip())


def _probability_band(probability: float) -> str:
    if probability >= 0.70:
        return "high"
    if probability >= 0.40:
        return "medium"
    return "low"


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
        cumulative_probability = _combined_probability(
            [
                float(itinerary.gain_matrix[itinerary.route_idx[position], species_idx])
                for position in range(route_position + 1)
            ]
        )
        items.append(
            {
                "code": code,
                "name": _common_species_name(code),
                "probability": probability,
                "cumulative_probability": cumulative_probability,
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
    raw_by_code = {str(item["code"]): item for item in raw_items}

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
        {
            "code": code,
            "name": bird,
            "probability": probability,
            "cumulative_probability": float(
                raw_by_code.get(code, {}).get("cumulative_probability", probability)
            ),
        }
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
    chip_parts = []
    for item in items:
        stop_probability = float(item["probability"])
        cumulative_probability = float(item.get("cumulative_probability", stop_probability))
        chip_parts.append(
            f'<span class="bbd-chip{extra_class}">'
            f'{html.escape(str(item["name"]))} {stop_probability:.0%} / {cumulative_probability:.0%}'
            f'</span>'
        )
    chips = "".join(chip_parts)
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
                Start <strong>{first_site}</strong> · finish <strong>{last_site}</strong> at <strong>{last_row["Depart"]}</strong> ·
                <strong>{expected_species:.1f}</strong> expected species · top gain <strong>{best_row["Expected new"]:.1f}</strong> at <strong>{best_site}</strong>.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_metric_cards(
    itinerary,
    *,
    stop_count: int,
    total_drive: float,
    total_dwell: float,
    finish_time: str,
) -> None:
    cards = [
        ("Expected species", f"{itinerary.expected_species:.1f}", "route estimate"),
        ("Stops", str(stop_count), "planned hotspots"),
        ("Drive", _format_minutes(total_drive), "between stops"),
        ("Birding", _format_minutes(total_dwell), f"ends {finish_time}"),
    ]
    card_html = "".join(
        '<div class="bbd-stat-card">'
        f'<div class="bbd-stat-label">{html.escape(label)}</div>'
        f'<div class="bbd-stat-value">{html.escape(value)}</div>'
        f'<div class="bbd-stat-caption">{html.escape(caption)}</div>'
        '</div>'
        for label, value, caption in cards
    )
    st.markdown(f'<div class="bbd-stat-grid">{card_html}</div>', unsafe_allow_html=True)


def _render_route_charts(summary_df: pd.DataFrame) -> None:
    if summary_df.empty:
        return

    chart_df = summary_df.copy()
    max_expected = float(chart_df["Expected new"].max()) if "Expected new" in chart_df else 0.0
    max_time = float((chart_df["Drive min"] + chart_df["Birding min"]).max()) if not chart_df.empty else 0.0

    expected_rows = []
    time_rows = []
    for _, row in chart_df.iterrows():
        stop_label = f"{int(row['Stop'])}. {row['Site']}"
        expected = float(row["Expected new"])
        drive = float(row["Drive min"])
        birding = float(row["Birding min"])
        total = max(drive + birding, 0.0)
        expected_rows.append(_compact_html(
            f"""
            <div class="bbd-bar-row">
                <div class="bbd-bar-meta">
                    <span>{html.escape(stop_label)}</span>
                    <strong>{expected:.1f}</strong>
                </div>
                <div class="bbd-bar-track">
                    <span class="bbd-bar-fill" style="width:{_bar_width(expected, max_expected):.1f}%"></span>
                </div>
            </div>
            """
        ))
        time_rows.append(_compact_html(
            f"""
            <div class="bbd-bar-row">
                <div class="bbd-bar-meta">
                    <span>{html.escape(stop_label)}</span>
                    <strong>{_format_minutes(total)}</strong>
                </div>
                <div class="bbd-stack-track">
                    <span class="bbd-stack-drive" style="width:{_bar_width(drive, max_time):.1f}%"></span>
                    <span class="bbd-stack-birding" style="width:{_bar_width(birding, max_time):.1f}%"></span>
                </div>
            </div>
            """
        ))

    st.markdown(
        f"""
        <div class="bbd-data-grid">
            <section class="bbd-data-card">
                <div class="bbd-card-kicker">Yield by stop</div>
                <h3>Expected species gain</h3>
                <div class="bbd-bar-list">{''.join(expected_rows)}</div>
            </section>
            <section class="bbd-data-card">
                <div class="bbd-card-kicker">Time allocation</div>
                <h3>Drive and birding time</h3>
                <div class="bbd-bar-list">{''.join(time_rows)}</div>
                <div class="bbd-legend-row">
                    <span><i class="bbd-legend-swatch" style="background:#9bb0a4"></i>Drive</span>
                    <span><i class="bbd-legend-swatch" style="background:var(--bbd-accent)"></i>Birding</span>
                </div>
            </section>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_bird_highlights(specialties: pd.DataFrame, shared: pd.DataFrame) -> None:
    st.subheader("Bird highlights")
    st.markdown(
        '<div class="bbd-section-note">Stop-specific birds on the left; repeated chances on the right.</div>',
        unsafe_allow_html=True,
    )

    specialty_items = []
    if specialties.empty:
        specialty_items.append(
            '<div class="bbd-highlight-item is-specialty"><div class="bbd-highlight-detail">No clear hotspot specialties above the current probability threshold.</div></div>'
        )
    else:
        for _, row in specialties.head(12).iterrows():
            chance = float(row["Best chance"])
            edge = float(row["Edge"])
            specialty_items.append(_compact_html(
                f"""
                <div class="bbd-highlight-item is-specialty">
                    <div class="bbd-highlight-title">
                        <strong>{html.escape(str(row["Bird"]))}</strong>
                        <span class="bbd-prob-value">{chance:.0%}</span>
                    </div>
                    <div class="bbd-prob-track">
                        <span class="bbd-prob-fill is-{_probability_band(chance)}" style="width:{chance * 100:.1f}%"></span>
                    </div>
                    <div class="bbd-highlight-detail">
                        Stop {int(row["Stop"])} · {html.escape(str(row["Hotspot"]))} · {edge:.0%} better than the next route stop
                    </div>
                </div>
                """
            ))

    shared_items = []
    if shared.empty:
        shared_items.append(
            '<div class="bbd-highlight-item"><div class="bbd-highlight-detail">No species currently meet the repeated-likelihood threshold.</div></div>'
        )
    else:
        for _, row in shared.head(12).iterrows():
            route_chance = float(row["Route chance"])
            shared_items.append(_compact_html(
                f"""
                <div class="bbd-highlight-item">
                    <div class="bbd-highlight-title">
                        <strong>{html.escape(str(row["Bird"]))}</strong>
                        <span class="bbd-prob-value">{route_chance:.0%}</span>
                    </div>
                    <div class="bbd-prob-track">
                        <span class="bbd-prob-fill is-{_probability_band(route_chance)}" style="width:{route_chance * 100:.1f}%"></span>
                    </div>
                    <div class="bbd-highlight-detail">
                        {int(row["Likely stops"])} likely stops · {html.escape(str(row["Where"]))}
                    </div>
                </div>
                """
            ))

    st.markdown(
        f"""
        <div class="bbd-highlight-grid">
            <section class="bbd-data-card">
                <div class="bbd-card-kicker">Hotspot signal</div>
                <h3>Specialties</h3>
                <div class="bbd-highlight-list">{''.join(specialty_items)}</div>
            </section>
            <section class="bbd-data-card">
                <div class="bbd-card-kicker">Route redundancy</div>
                <h3>Likely at multiple stops</h3>
                <div class="bbd-highlight-list">{''.join(shared_items)}</div>
            </section>
        </div>
        """,
        unsafe_allow_html=True,
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
        '<div class="bbd-section-note">Species at or above the display probability floor.</div>',
        unsafe_allow_html=True,
    )
    if route_probabilities.empty:
        st.info("No species meet the displayed probability floor for the route.")
        return

    display = route_probabilities.copy()
    rows = []
    for _, row in display.iterrows():
        route_chance = float(row["Route chance"])
        best_stop_chance = float(row["Best stop chance"])
        band = _probability_band(route_chance)
        rows.append(_compact_html(
            f"""
            <div class="bbd-prob-row is-{band}">
                <div class="bbd-prob-title">
                    <strong>{html.escape(str(row["Bird"]))}</strong>
                    <span class="bbd-prob-value">{route_chance:.0%}</span>
                </div>
                <div class="bbd-prob-track">
                    <span class="bbd-prob-fill is-{band}" style="width:{route_chance * 100:.1f}%"></span>
                </div>
                <div class="bbd-prob-detail">
                    Best stop: {html.escape(str(row["Best stop"]))} ({best_stop_chance:.0%}) ·
                    {int(row["Contributing stops"])} contributing stops
                </div>
            </div>
            """
        ))

    st.markdown(
        f"""
        <section class="bbd-data-card">
            <div class="bbd-card-kicker">Full route list</div>
            <h3>Species probability catalog</h3>
            <div class="bbd-prob-list">{''.join(rows)}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("Show table with contributing stops", expanded=False):
        table = display.copy()
        table["Route chance"] = table["Route chance"].map(_display_percent)
        table["Best stop chance"] = table["Best stop chance"].map(_display_percent)
        st.dataframe(
            table[
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
        '<div class="bbd-section-note">Order, timing, eBird links, and expected birds.</div>',
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

    _render_metric_cards(
        itinerary,
        stop_count=len(itinerary.route_idx),
        total_drive=total_drive,
        total_dwell=total_dwell,
        finish_time=finish_time,
    )
    _render_route_brief(summary_df, total_drive, total_dwell, itinerary.expected_species)
    _render_stop_cards(itinerary, specialties_by_stop, display_min_prob=display_min_prob)
    _render_route_charts(summary_df)
    _render_trip_probabilities(itinerary, display_min_prob=display_min_prob)

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

    st.markdown(
        """
        <section class="bbd-hero">
            <div class="bbd-breadcrumb">Big Day Planner &gt; Loudoun County</div>
            <div class="bbd-hero-main">
                <div>
                    <h1>Big Day Optimizer</h1>
                    <p class="bbd-hero-copy">One-day route planning from eBird checklist probabilities.</p>
                </div>
                <div class="bbd-hero-status">Demo route loaded</div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    config = _read_config()
    if "last_itinerary" not in st.session_state:
        st.session_state["last_itinerary"] = _load_preloaded_loudoun_itinerary()
        st.session_state["last_itinerary_source"] = "preloaded"

    run = st.button("Run optimizer", type="primary")
    if run:
        errors = _validate(config)
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
        st.session_state["last_itinerary_source"] = "live"

    itinerary = st.session_state.get("last_itinerary")
    if itinerary is None:
        st.info("Set the run options, then start the optimizer.")
        return

    if st.session_state.get("last_itinerary_source") == "preloaded":
        st.markdown(
            """
            <div class="bbd-table-note">
                Demo route · run optimizer for live eBird data.
            </div>
            """,
            unsafe_allow_html=True,
        )

    _render_results(itinerary, display_min_prob=config.display_min_prob)


if __name__ == "__main__":
    main()
