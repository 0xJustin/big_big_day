from __future__ import annotations

import datetime as dt
import html
from dataclasses import dataclass
from typing import Literal

import pandas as pd
import streamlit as st

from .dashboard import (
    EBIRD_API_HELP_URL,
    _compact_html,
    _is_public_deployment,
    _load_default_api_key,
    _page_style,
)
from .migrant_hotspots import (
    TIME_BUCKETS,
    MigrantResults,
    analyze_migrant_hotspots,
    historical_dates,
    recent_dates,
)


DEFAULT_REGION = "US-VA-107"
DEFAULT_ANCHOR_DATE = dt.date(2026, 5, 17)


@dataclass(frozen=True)
class MigrantDashboardConfig:
    api_key: str
    region: str
    mode: Literal["recent", "historical"]
    recent_days: int
    anchor_date: dt.date | None
    anchor_date_error: str | None
    historical_days: int
    historical_years: int
    max_checklists_per_day: int
    min_checklists_per_hotspot: int


def _parse_date(value: str) -> tuple[dt.date | None, str | None]:
    cleaned = value.strip()
    if not cleaned:
        return None, "Date is required."
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return dt.datetime.strptime(cleaned, fmt).date(), None
        except ValueError:
            pass
    return None, "Date must be YYYY-MM-DD or YYYY/MM/DD."


def _format_date_range(dates: tuple[dt.date, ...]) -> str:
    if not dates:
        return "--"
    ordered = sorted(dates)
    if len(ordered) == 1:
        return ordered[0].isoformat()
    return f"{ordered[0].isoformat()} to {ordered[-1].isoformat()}"


def _read_config() -> MigrantDashboardConfig:
    default_api_key = _load_default_api_key()

    with st.sidebar:
        st.markdown(
            """
            <div class="bbd-sidebar-brand">
                <span>Migration</span>
                <strong>Hotspot controls</strong>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown('<div class="bbd-sidebar-section">Setup</div>', unsafe_allow_html=True)
        api_key = st.text_input("eBird API key", value=default_api_key, type="password")
        if _is_public_deployment():
            st.markdown(
                f"""
                <div class="bbd-public-note">
                    Use your own eBird API key for live runs.
                    <a href="{EBIRD_API_HELP_URL}" target="_blank" rel="noopener noreferrer">Get a key</a>.
                </div>
                """,
                unsafe_allow_html=True,
            )
        region = st.text_input(
            "eBird county / region",
            value=DEFAULT_REGION,
            help="Region code such as US-VA-107 for Loudoun County.",
        )

        st.divider()
        st.markdown('<div class="bbd-sidebar-section">Sampling window</div>', unsafe_allow_html=True)
        mode_label = st.radio(
            "Mode",
            ["Recent days", "Historical date window"],
            index=1,
            help="Recent days uses the latest checklist data. Historical date window uses the same calendar window in prior years.",
        )
        mode: Literal["recent", "historical"] = "recent" if mode_label == "Recent days" else "historical"
        recent_days = st.number_input(
            "Recent days",
            min_value=1,
            max_value=30,
            value=10,
            help="For recent mode, sample checklists from today and the previous N-1 days.",
            disabled=mode != "recent",
        )
        anchor_date_text = st.text_input(
            "Target date",
            value=DEFAULT_ANCHOR_DATE.isoformat(),
            help="For historical mode, this is the end date of the migration window.",
            disabled=mode != "historical",
        )
        anchor_date, anchor_date_error = _parse_date(anchor_date_text)
        historical_days = st.number_input(
            "Window days",
            min_value=1,
            max_value=30,
            value=10,
            help="For historical mode, include the target date and previous N-1 days in each prior year.",
            disabled=mode != "historical",
        )
        historical_years = st.selectbox(
            "Historical years",
            options=[1, 2, 3, 4, 5],
            index=2,
            help="Number of prior years to sample for the same calendar window.",
            disabled=mode != "historical",
        )

        with st.expander("Advanced settings", expanded=False):
            max_checklists_per_day = st.number_input(
                "Max county checklists per day",
                min_value=1,
                max_value=200,
                value=200,
                step=10,
                help="eBird returns at most 200 checklist visits per area/date. Lower values run faster but may miss data.",
            )
            min_checklists_per_hotspot = st.number_input(
                "Min checklists per hotspot",
                min_value=1,
                max_value=100,
                value=5,
                step=1,
                help="Exclude hotspots with fewer sampled checklists from the rankings.",
            )

    return MigrantDashboardConfig(
        api_key=api_key.strip(),
        region=region.strip(),
        mode=mode,
        recent_days=int(recent_days),
        anchor_date=anchor_date,
        anchor_date_error=anchor_date_error,
        historical_days=int(historical_days),
        historical_years=int(historical_years),
        max_checklists_per_day=int(max_checklists_per_day),
        min_checklists_per_hotspot=int(min_checklists_per_hotspot),
    )


def _sample_dates(config: MigrantDashboardConfig) -> tuple[dt.date, ...]:
    if config.mode == "recent":
        return recent_dates(config.recent_days)
    if config.anchor_date is None:
        raise ValueError(config.anchor_date_error or "Target date is invalid.")
    return historical_dates(
        config.anchor_date,
        days=config.historical_days,
        years=config.historical_years,
    )


def _validate(config: MigrantDashboardConfig) -> list[str]:
    errors = []
    if not config.api_key:
        errors.append("Enter an eBird API key.")
    if not config.region:
        errors.append("Enter an eBird region code.")
    if config.mode == "historical" and config.anchor_date_error:
        errors.append(config.anchor_date_error)
    return errors


@st.cache_data(show_spinner=False, ttl=60 * 60)
def _run_analysis(
    api_key: str,
    region: str,
    date_values: tuple[str, ...],
    max_checklists_per_day: int,
    min_checklists_per_hotspot: int,
) -> MigrantResults:
    dates = tuple(dt.date.fromisoformat(value) for value in date_values)
    return analyze_migrant_hotspots(
        api_key,
        region,
        dates=dates,
        max_checklists_per_day=max_checklists_per_day,
        min_checklists_per_hotspot=min_checklists_per_hotspot,
    )


def _metric_cards(results: MigrantResults) -> None:
    top_variety = results.hotspot_summary.iloc[0] if not results.hotspot_summary.empty else None
    morning = results.hotspot_summary.sort_values(
        ["morning_species", "morning_individuals_per_checklist", "checklists"],
        ascending=[False, False, False],
    )
    top_morning = morning.iloc[0] if not morning.empty else None
    photo = results.hotspot_summary.sort_values(
        ["photo_score", "qualified_photo_items", "checklists"],
        ascending=[False, False, False],
    )
    top_photo = photo.iloc[0] if not photo.empty else None

    cards = [
        ("Sampled checklists", f"{results.checklist_count:,}", f"{results.hotspot_count:,} hotspots after filters"),
        ("Warbler species", f"{results.warbler_species_count:,}", "unique Parulidae taxa reported"),
        (
            "Top variety",
            str(top_variety["warbler_species"]) if top_variety is not None else "--",
            str(top_variety["locName"]) if top_variety is not None else "No sampled hotspots",
        ),
        (
            "Best morning",
            str(top_morning["morning_species"]) if top_morning is not None else "--",
            str(top_morning["locName"]) if top_morning is not None else "No morning checklists",
        ),
        (
            "Photo signal",
            f"{float(top_photo['photo_score']):.1f}" if top_photo is not None else "--",
            f"{top_photo['locName']} · 4.5+ items / 100 checklists" if top_photo is not None else "No photo metadata",
        ),
    ]
    html_cards = "".join(
        '<div class="bbd-stat-card">'
        f'<div class="bbd-stat-label">{html.escape(label)}</div>'
        f'<div class="bbd-stat-value">{html.escape(value)}</div>'
        f'<div class="bbd-stat-caption">{html.escape(caption)}</div>'
        "</div>"
        for label, value, caption in cards
    )
    st.markdown(f'<div class="bbd-stat-grid">{html_cards}</div>', unsafe_allow_html=True)


def _bar_rows(df: pd.DataFrame, *, label_col: str, value_col: str, suffix: str = "", limit: int = 12) -> str:
    if df.empty:
        return '<div class="bbd-table-note">No data available for this view.</div>'
    max_value = float(df[value_col].max()) or 1.0
    rows = []
    for index, row in df.head(limit).iterrows():
        value = float(row[value_col])
        width = max(3.0, min(100.0, value * 100.0 / max_value))
        rows.append(
            _compact_html(
                f"""
                <div class="bbd-bar-row">
                    <div class="bbd-bar-meta">
                        <span>{int(index) + 1}. {html.escape(str(row[label_col]))}</span>
                        <strong>{value:.1f}{html.escape(suffix)}</strong>
                    </div>
                    <div class="bbd-bar-track">
                        <span class="bbd-bar-fill" style="width:{width:.1f}%"></span>
                    </div>
                </div>
                """
            )
        )
    return "".join(rows)


def _render_overview(results: MigrantResults) -> None:
    _metric_cards(results)
    if results.hotspot_summary.empty:
        st.info("No hotspots met the sampling filters.")
        return

    top_variety = results.hotspot_summary.sort_values(
        ["warbler_species", "individuals_per_checklist", "checklists"],
        ascending=[False, False, False],
    )
    top_abundance = results.hotspot_summary.sort_values(
        ["individuals_per_checklist", "warbler_species", "checklists"],
        ascending=[False, False, False],
    )
    top_photo = results.hotspot_summary.sort_values(
        ["photo_score", "qualified_photo_items", "checklists"],
        ascending=[False, False, False],
    )

    st.markdown(
        f"""
        <div class="bbd-data-grid">
            <section class="bbd-data-card">
                <div class="bbd-card-kicker">Warbler variety</div>
                <h3>Species by hotspot</h3>
                <div class="bbd-bar-list">{_bar_rows(top_variety, label_col="locName", value_col="warbler_species")}</div>
            </section>
            <section class="bbd-data-card">
                <div class="bbd-card-kicker">Warbler abundance</div>
                <h3>Individuals per checklist</h3>
                <div class="bbd-bar-list">{_bar_rows(top_abundance, label_col="locName", value_col="individuals_per_checklist")}</div>
            </section>
        </div>
        <section class="bbd-data-card">
            <div class="bbd-card-kicker">Photo potential</div>
            <h3>High-rated photo signal</h3>
            <div class="bbd-section-note">Items with rating metadata at 4.5+ stars and at least 5 ratings, shown per 100 sampled checklists when available.</div>
            <div class="bbd-bar-list">{_bar_rows(top_photo, label_col="locName", value_col="photo_score")}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_time_buckets(results: MigrantResults) -> None:
    if results.bucket_summary.empty:
        st.info("No time-of-day data available.")
        return

    bucket_order = [label for label, _, _ in TIME_BUCKETS] + ["Other", "No time"]
    cards = []
    for bucket in bucket_order:
        subset = results.bucket_summary[results.bucket_summary["time_bucket"] == bucket].sort_values(
            ["warbler_species", "individuals_per_checklist", "checklists"],
            ascending=[False, False, False],
        )
        if subset.empty:
            continue
        row = subset.iloc[0]
        cards.append(
            _compact_html(
                f"""
                <div class="bbd-stat-card">
                    <div class="bbd-stat-label">{html.escape(bucket)}</div>
                    <div class="bbd-stat-value">{int(row["warbler_species"])}</div>
                    <div class="bbd-stat-caption">{html.escape(str(row["locName"]))} · {float(row["individuals_per_checklist"]):.1f} birds/checklist</div>
                </div>
                """
            )
        )
    st.markdown(f'<div class="bbd-stat-grid">{"".join(cards)}</div>', unsafe_allow_html=True)

    display = results.bucket_summary.copy()
    display["species_per_checklist"] = display["species_per_checklist"].round(2)
    display["individuals_per_checklist"] = display["individuals_per_checklist"].round(2)
    st.dataframe(
        display[
            [
                "time_bucket",
                "locName",
                "checklists",
                "warbler_species",
                "warbler_individuals",
                "species_per_checklist",
                "individuals_per_checklist",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )


def _render_tables(results: MigrantResults) -> None:
    hotspot_display = results.hotspot_summary.copy()
    if not hotspot_display.empty:
        hotspot_display["eBird hotspot"] = hotspot_display["locId"].map(lambda loc_id: f"https://ebird.org/hotspot/{loc_id}")
        for column in ("species_per_checklist", "individuals_per_checklist", "morning_individuals_per_checklist", "photo_score"):
            hotspot_display[column] = hotspot_display[column].round(2)
    st.dataframe(
        hotspot_display[
            [
                "locName",
                "eBird hotspot",
                "checklists",
                "warbler_species",
                "warbler_individuals",
                "species_per_checklist",
                "individuals_per_checklist",
                "morning_species",
                "qualified_photo_items",
                "photo_score",
            ]
        ]
        if not hotspot_display.empty
        else hotspot_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "eBird hotspot": st.column_config.LinkColumn("eBird", display_text="Open"),
        },
    )

    st.download_button(
        "Download hotspot CSV",
        data=results.hotspot_summary.to_csv(index=False).encode("utf-8"),
        file_name="migrant_hotspot_summary.csv",
        mime="text/csv",
    )

    st.subheader("Warbler species by hotspot")
    species_display = results.species_summary.copy()
    if not species_display.empty:
        species_display["checklist_rate"] = species_display["checklist_rate"].round(3)
    st.dataframe(species_display, use_container_width=True, hide_index=True)
    st.download_button(
        "Download species CSV",
        data=results.species_summary.to_csv(index=False).encode("utf-8"),
        file_name="migrant_species_by_hotspot.csv",
        mime="text/csv",
    )


def _render_map(results: MigrantResults) -> None:
    map_df = results.hotspot_summary[["lat", "lng", "locName", "warbler_species"]].rename(
        columns={"lng": "lon"}
    )
    if map_df.empty:
        st.info("No coordinates available.")
        return
    st.map(map_df, latitude="lat", longitude="lon", size="warbler_species")


def _render_results(results: MigrantResults) -> None:
    st.markdown(
        f"""
        <div class="bbd-table-note">
            Sample window: {_format_date_range(results.dates)} · {len(results.dates)} sampled dates.
        </div>
        """,
        unsafe_allow_html=True,
    )
    overview_tab, time_tab, table_tab, map_tab = st.tabs(["Overview", "Time of day", "Tables", "Map"])
    with overview_tab:
        _render_overview(results)
    with time_tab:
        _render_time_buckets(results)
    with table_tab:
        _render_tables(results)
    with map_tab:
        _render_map(results)


def main() -> None:
    st.set_page_config(
        page_title="Migrant Hotspot Dashboard",
        layout="wide",
    )
    _page_style()

    st.markdown(
        """
        <section class="bbd-hero">
            <div class="bbd-breadcrumb">Bird migration &gt; County hotspots</div>
            <div class="bbd-hero-main">
                <div>
                    <h1>Migrant Hotspot Dashboard</h1>
                    <p class="bbd-hero-copy">Warbler movement by hotspot, date window, and checklist time.</p>
                </div>
                <div class="bbd-hero-status">Live eBird data</div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    config = _read_config()
    run = st.button("Analyze hotspots", type="primary")

    if not run and "migrant_results" not in st.session_state:
        st.info("Set the county and sampling window, then run the analysis.")
        return

    if run:
        errors = _validate(config)
        if errors:
            for error in errors:
                st.error(error)
            return
        try:
            dates = _sample_dates(config)
        except ValueError as exc:
            st.error(str(exc))
            return

        with st.spinner("Fetching eBird checklists and calculating hotspot metrics..."):
            try:
                results = _run_analysis(
                    config.api_key,
                    config.region,
                    tuple(day.isoformat() for day in dates),
                    config.max_checklists_per_day,
                    config.min_checklists_per_hotspot,
                )
            except Exception as exc:
                st.error(str(exc))
                return
        st.session_state["migrant_results"] = results

    results = st.session_state.get("migrant_results")
    if results is not None:
        _render_results(results)


if __name__ == "__main__":
    main()
