from dataclasses import dataclass
import pandas as pd
import datetime as dt
import math
from typing import Dict, List, Optional, Sequence
from ortools.sat.python import cp_model
import numpy as np

@dataclass
class Itinerary:
    route_idx: List[int]          # hotspot indices in visit order
    visit_mask: List[bool]        # length N
    seen_species: List[str]
    hotspots: pd.DataFrame
    travel: Sequence[Sequence[int]]
    start_time: dt.datetime
    base_idle: int
    dwell_per: int
    include_depot: bool
    depot_idx: Optional[int]
    sp_all: List[str]
    gain_matrix: np.ndarray
    expected_species: float = 0.0
    probability_steps: int = 100

    def leg_rows(self) -> List[dict]:
        """Return per-leg route details using marginal expected species gains."""
        rows = []
        clock = self.start_time
        remaining = np.ones(len(self.sp_all), dtype=float)

        for leg, idx in enumerate(self.route_idx):
            drive = 0 if leg == 0 else self.travel[self.route_idx[leg - 1]][idx]
            clock += dt.timedelta(minutes=drive)
            arrive = clock

            probabilities = self.gain_matrix[idx].astype(float)
            marginal = remaining * probabilities
            expected_new = float(marginal.sum())

            species_parts = [
                f"{self.sp_all[k]}:{marginal[k]:.2f}"
                for k in np.argsort(-marginal)
                if marginal[k] > 0
            ]

            dwell = self.base_idle + self.dwell_per * expected_new
            clock += dt.timedelta(minutes=dwell)

            rows.append(dict(
                leg=leg,
                loc_id=self.hotspots.locId.iloc[idx] if "locId" in self.hotspots.columns else "",
                site=self.hotspots.locName.iloc[idx],
                arrive=arrive.strftime("%H:%M"),
                depart=clock.strftime("%H:%M"),
                drive_min=drive,
                expected_new_sp=round(expected_new, 2),
                dwell_min=round(dwell, 1),
                species=", ".join(species_parts),
            ))
            remaining *= (1 - probabilities)

        return rows

    def to_markdown(self) -> str:
        lines = ["| leg | site | arrive | depart | drive | exp. new sp | dwell | species |",
                 "|---|---|---|---|---|---|---|---|"]
        for row in self.leg_rows():
            lines.append(
                f"| {row['leg']} | **{row['site']}** | {row['arrive']} | {row['depart']} | "
                f"{row['drive_min']} | {row['expected_new_sp']:.2f} | "
                f"{row['dwell_min']:.1f} | {row['species']} |"
            )
        lines.append(f"**Expected unique species:** {self.expected_species:.2f}")
        return "\n".join(lines)
    def to_dataframe(self, *, translate: bool = True):
        """Return the itinerary as a pandas DataFrame (see utils.itinerary_to_df)."""
        from big_day_optimizer.utils import itinerary_to_df
        return itinerary_to_df(self, translate=translate)

# ---------------------------------------------------------------------
def _build_probability_matrix(hotspots: pd.DataFrame,
                              prob_by_loc: Dict[str, Dict[str, float]],
                              *,
                              min_prob: float = 0.03):
    sp_all = sorted({sp for d in prob_by_loc.values() for sp in d})
    sp_id = {sp: i for i, sp in enumerate(sp_all)}
    probabilities = np.zeros((len(hotspots), len(sp_all)), dtype=float)

    for i, loc in enumerate(hotspots.locId):
        for sp, p in prob_by_loc.get(loc, {}).items():
            if p >= min_prob:
                probabilities[i, sp_id[sp]] = min(max(float(p), 0.0), 1.0)
    return probabilities, sp_all


def _loc_position(hotspots: pd.DataFrame, loc_id: str) -> int:
    matches = np.flatnonzero(hotspots.locId.to_numpy() == loc_id)
    if len(matches) == 0:
        raise ValueError(f"depot_locid {loc_id!r} is not present in the hotspot table")
    return int(matches[0])


def _success_hit_vars(
    model: cp_model.CpModel,
    visit: Sequence[cp_model.IntVar],
    probabilities: np.ndarray,
    *,
    int_scale: int,
    probability_steps: int,
) -> list[cp_model.IntVar]:
    """Approximate expected unique species via log-exposure step variables.

    For a species with site probabilities p_i, route success is
    1 - product(1 - p_i).  Summing -log(1 - p_i) over selected sites makes the
    nonlinear product additive; threshold booleans approximate the concave
    success curve in `probability_steps` equal probability increments.
    """
    if probability_steps < 2:
        raise ValueError("probability_steps must be at least 2")

    n, m = probabilities.shape
    clipped = np.clip(probabilities, 0.0, 0.999999)
    exposure_gain = np.rint(-np.log1p(-clipped) * int_scale).astype(int)
    hit_vars: list[cp_model.IntVar] = []

    thresholds = [
        int(math.ceil(-math.log1p(-(step / probability_steps)) * int_scale))
        for step in range(1, probability_steps)
    ]

    for k in range(m):
        max_exposure = int(exposure_gain[:, k].sum())
        if max_exposure <= 0:
            continue

        exposure = model.NewIntVar(0, max_exposure, f"exposure[{k}]")
        model.Add(exposure == sum(int(exposure_gain[i, k]) * visit[i] for i in range(n)))

        for threshold in thresholds:
            if threshold > max_exposure:
                break
            hit = model.NewBoolVar(f"success_step[{k},{threshold}]")
            model.Add(exposure >= threshold * hit)
            hit_vars.append(hit)

    return hit_vars


def solve_itinerary(
    hotspots: pd.DataFrame,
    travel: Sequence[Sequence[int]],
    prob_by_loc: Dict[str, Dict[str, float]],
    *,
    include_depot: bool = False,
    depot_locid: Optional[str] = None,
    start_time: dt.datetime,
    end_time: dt.datetime,
    base_idle: int = 30,
    dwell_per: int = 2,
    min_stops: int = 3,
    max_stops: int = 5,
    min_prob: float = 0.03,
    int_scale: int = 1_000,
    probability_steps: int = 100,
    nearby_drive_min: int = 8,
    nearby_pair_penalty: float = 0.15,
    time_limit: int = 60,
):
    probabilities, sp_all = _build_probability_matrix(
        hotspots,
        prob_by_loc,
        min_prob=min_prob,
    )
    n, _ = probabilities.shape

    M = cp_model.CpModel()
    edge = {(i, j): M.NewBoolVar(f"e[{i},{j}]") for i in range(n) for j in range(n) if i != j}
    visit = [M.NewBoolVar(f"v[{i}]") for i in range(n)]
    order = [M.NewIntVar(0, n-1, f"ord[{i}]") for i in range(n)]
    source = [M.NewBoolVar(f"src[{i}]") for i in range(n)]
    end = [M.NewBoolVar(f"end[{i}]") for i in range(n)]

    M.Add(sum(source) == 1)
    M.Add(sum(end) == 1)

    if include_depot:
        assert depot_locid, "depot_locid required when include_depot=True"
        START = _loc_position(hotspots, depot_locid)
        for i in range(n):
            M.Add(source[i] == int(i == START))
        M.Add(order[START] == 0)
    else:
        for i in range(n):
            M.Add(order[i] == 0).OnlyEnforceIf(source[i])

    for i in range(n):
        out = sum(edge[i, j] for j in range(n) if i != j)
        inn = sum(edge[j, i] for j in range(n) if i != j)

        M.Add(out <= 1)
        M.Add(inn <= 1)
        M.Add(out <= visit[i])
        M.Add(inn <= visit[i])
        M.Add(source[i] <= visit[i])
        M.Add(end[i] <= visit[i])
        M.Add(visit[i] <= inn + source[i])
        M.Add(out - inn == source[i] - end[i])

    BIG = n
    for i, j in edge:
        M.Add(order[j] >= order[i] + 1 - BIG * (1 - edge[i, j]))

    success_hits = _success_hit_vars(
        M,
        visit,
        probabilities,
        int_scale=int_scale,
        probability_steps=probability_steps,
    )

    nearby_pairs: list[cp_model.IntVar] = []
    if nearby_drive_min > 0 and nearby_pair_penalty > 0:
        for i in range(n):
            for j in range(i + 1, n):
                pair_drive = min(int(travel[i][j]), int(travel[j][i]))
                if pair_drive > nearby_drive_min:
                    continue
                pair = M.NewBoolVar(f"nearby_pair[{i},{j}]")
                M.Add(pair <= visit[i])
                M.Add(pair <= visit[j])
                M.Add(pair >= visit[i] + visit[j] - 1)
                nearby_pairs.append(pair)

    if include_depot:
        M.Add(sum(visit) - visit[START] >= min_stops)
        M.Add(sum(visit) - visit[START] <= max_stops)
    else:
        M.Add(sum(visit) >= min_stops)
        M.Add(sum(visit) <= max_stops)

    travel_part = sum(travel[i][j] * edge[i, j] for i, j in edge)
    T_MAX = int((end_time - start_time).total_seconds() / 60)
    M.Add(
        probability_steps * (travel_part + base_idle * sum(visit))
        + dwell_per * sum(success_hits)
        <= probability_steps * T_MAX
    )

    # Primary objective: expected unique species. Tie-breaks: less driving, then
    # fewer stops. The weights ensure a one-step species gain dominates any
    # possible travel/stop penalty within the day's time budget.
    nearby_penalty_steps = int(round(max(0.0, nearby_pair_penalty) * probability_steps))
    primary_score = sum(success_hits)
    if nearby_pairs and nearby_penalty_steps:
        primary_score -= nearby_penalty_steps * sum(nearby_pairs)

    travel_tie_weight = n + 1
    species_weight = travel_tie_weight * max(T_MAX, 0) + n + 1
    M.Maximize(
        species_weight * primary_score
        - travel_tie_weight * travel_part
        - sum(visit)
    )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    status = solver.Solve(M)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError("No feasible itinerary found.")

    if include_depot:
        cur = START
    else:
        cur = next(i for i in range(n) if solver.BooleanValue(source[i]))
    route = [cur]
    while True:
        nxt = [j for j in range(n) if j != cur and solver.BooleanValue(edge[cur, j])]
        if not nxt:
            break
        cur = nxt[0]
        route.append(cur)

    if route:
        route_success = 1 - np.prod(1 - probabilities[route], axis=0)
    else:
        route_success = np.zeros(len(sp_all), dtype=float)
    seen_species = [sp_all[k] for k, p in enumerate(route_success) if p > 0]
    expected_species = float(route_success.sum())

    return Itinerary(
        route_idx=route,
        visit_mask=[solver.BooleanValue(v) for v in visit],
        seen_species=seen_species,
        hotspots=hotspots.copy(),
        travel=travel,
        start_time=start_time,
        base_idle=base_idle,
        dwell_per=dwell_per,
        include_depot=include_depot,
        depot_idx=START if include_depot else None,
        sp_all=sp_all,
        gain_matrix=probabilities,
        expected_species=expected_species,
        probability_steps=probability_steps,
    )
