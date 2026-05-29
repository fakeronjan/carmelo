# ============================================================
# CARMELO - International Men's Basketball Power Ratings
# Massey-style weighted-least-squares rolling rating engine.
#
# Cloned from NBA/duncan.py (the DUNCAN engine): same WLS Massey solver, same
# linear recency decay across a rolling game-day window, same sign-preserving
# margin-cap transform, same zero-sum constraint via a high-weight extra row.
#
# International adaptations (vs DUNCAN):
#   * NO continuous season -> a FIXED game-day window (see WINDOW_GAME_DAYS).
#   * HCA = 0 for neutral-site games (Olympics, World Cup, all continental
#     championships), HCA = 2.0 only for home-and-away WC qualifiers. The
#     `neutral` flag is set per game by the scraper.
#   * Per-tournament TIER weights enter the WLS observation weight (MESSI-style)
#     so a World Cup game is a stronger signal than a qualifier.
#
# Data-integrity guards (cloned from soccer us-mex/cobi.py):
#   * Append-only union lives in build_games.py (the games CSV is the DB).
#   * This engine recomputes ratings from scratch every run (no positional
#     ranking_id cache) — simplest and safe for the sparse intl calendar, which
#     is small enough that a full rebuild is cheap. This sidesteps the
#     cache-validity desync class of bug entirely.
# ============================================================
import os
import numpy as np
import pandas as pd
from datetime import datetime

from countries import CODE_TO_NAME, CONFEDERATION, canon_code

# ============================================================
# PARAMETERS  (documented; flagged for tuning in the build report)
# ============================================================

# Fixed rolling window in GAME-DAYS (distinct dates on which any game was
# played). International basketball has no continuous season — events cluster
# in summers (Olympics/WC/continental) with WC qualifier windows scattered
# across Nov/Feb. A game-day window of 150 spans roughly the last ~3-4 major
# event cycles' worth of game-days. START VALUE — NEEDS USER TUNING. Too small
# and a team's rating swings on a single tournament; too large and stale
# rosters from 6+ years ago still weight the current rating.
WINDOW_GAME_DAYS = 150

# Margin transform: cap at +/- MARGIN_CAP points (DUNCAN's basketball value).
# Keeps 40-point blowouts from dominating the regression; below the cap the
# response is raw point margin.
MARGIN_TRANSFORM = "cap"
MARGIN_CAP = 25

# Home-court advantage (raw points) subtracted from the home margin BEFORE the
# transform. Applied only to non-neutral games (WC qualifiers). Neutral-site
# tournaments get HCA = 0.
HOME_COURT_ADJUSTMENT = 2.0

WEIGHTING_MODE = "wls"

# Minimum games in the window for a team to appear in the published ratings.
# Sparse-calendar guard: a team with 1-2 games in the window has an unreliable
# rating. Mirrors MESSI's min_competitive_games idea.
MIN_GAMES = 4

GAMES_CSV = "all_games.csv"
RATINGS_CSV = "carmelo_ratings.csv"


# ============================================================
# MASSEY WLS SOLVER  (copied from DUNCAN, team-keyed for intl)
# ============================================================

def _apply_margin_transform(margin, transform, cap):
    m = np.asarray(margin, dtype=float)
    if transform == "raw":
        return m
    if transform == "sqrt":
        return np.sign(m) * np.sqrt(np.abs(m))
    if transform == "cap":
        return np.clip(m, -cap, cap)
    if transform == "tanh":
        return cap * np.tanh(m / cap)
    raise ValueError(f"Unknown MARGIN_TRANSFORM: {transform}")


def _solve_massey(window_df):
    """WLS Massey solve on one rolling window. Builds X (n_games x n_teams)
    with +1 home / -1 away, y = transformed (HCA-adjusted) home margin, W =
    combined observation weight (recency x tier). Zero-sum constraint via a
    high-weight extra row. WLS via sqrt(w) row-scaling -> ordinary lstsq.
    (Same math as DUNCAN _solve_massey.)"""
    teams = sorted(set(window_df["team_a"]) | set(window_df["team_b"]))
    team_idx = {t: i for i, t in enumerate(teams)}
    n_teams = len(teams)
    n_games = len(window_df)

    X = np.zeros((n_games + 1, n_teams))
    y = np.zeros(n_games + 1)
    w = np.zeros(n_games + 1)

    score_a = window_df["score_a"].to_numpy(dtype=float)   # "home" perspective
    score_b = window_df["score_b"].to_numpy(dtype=float)
    hca = window_df["hca"].to_numpy(dtype=float)
    weights = window_df["weight"].to_numpy(dtype=float)
    a_names = window_df["team_a"].to_numpy()
    b_names = window_df["team_b"].to_numpy()

    raw_margin = score_a - score_b - hca
    transformed = _apply_margin_transform(raw_margin, MARGIN_TRANSFORM, MARGIN_CAP)

    for i in range(n_games):
        X[i, team_idx[a_names[i]]] = 1.0
        X[i, team_idx[b_names[i]]] = -1.0

    y[:n_games] = transformed
    w[:n_games] = weights

    X[-1, :] = 1.0
    y[-1] = 0.0
    w[-1] = 1.0e8

    sqrt_w = np.sqrt(w)
    Xw = X * sqrt_w[:, None]
    yw = y * sqrt_w
    r, *_ = np.linalg.lstsq(Xw, yw, rcond=None)

    out = pd.DataFrame({"code": teams, "rating": r})
    out["rank"] = out["rating"].rank(ascending=False, method="min").astype(int)
    return out


# ============================================================
# DATA PREP
# ============================================================

def load_games():
    df = pd.read_csv(GAMES_CSV)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df = df.dropna(subset=["team_a", "team_b", "score_a", "score_b", "date"])
    df["score_a"] = pd.to_numeric(df["score_a"], errors="coerce")
    df["score_b"] = pd.to_numeric(df["score_b"], errors="coerce")
    df = df.dropna(subset=["score_a", "score_b"])
    df = df[df["team_a"] != df["team_b"]]

    # Canonicalise alternate codes (SVN->SLO, NGA->NGR, ...) so a team's
    # history isn't split across two codes for the same nation.
    df["team_a"] = df["team_a"].map(canon_code)
    df["team_b"] = df["team_b"].map(canon_code)

    # neutral may be missing for legacy rows; default True (most intl games are
    # neutral). tier may be missing; default 1.0.
    if "neutral" not in df.columns:
        df["neutral"] = True
    df["neutral"] = df["neutral"].fillna(True).astype(bool)
    if "tier" not in df.columns:
        df["tier"] = 1.0
    df["tier"] = pd.to_numeric(df["tier"], errors="coerce").fillna(1.0)

    # HCA only on non-neutral games (WC qualifiers).
    df["hca"] = np.where(df["neutral"], 0.0, HOME_COURT_ADJUSTMENT)

    # Win flags (for standings / records).
    df["a_win"] = (df["score_a"] > df["score_b"]).astype(int)
    df["b_win"] = 1 - df["a_win"]

    df = df.sort_values("date").reset_index(drop=True)
    # Positional game-day id. Recomputed every run; engine does a full rebuild
    # so there is no cache to desync.
    df["grouped_date_id"] = df.groupby("date").ngroup() + 1
    return df


# ============================================================
# ROLLING RATINGS
# ============================================================

def compute_ratings(df):
    max_id = int(df["grouped_date_id"].max())
    frames = []
    last_year = None

    for i in range(1, max_id + 1):
        current_date = df.loc[df["grouped_date_id"] == i, "date"].max()
        if pd.isnull(current_date):
            continue

        window = df[
            (df["grouped_date_id"] >= i - WINDOW_GAME_DAYS + 1) &
            (df["grouped_date_id"] <= i)
        ].copy()
        if len(window) < 10:
            continue

        # Linear recency decay across the window (DUNCAN-style), multiplied by
        # the per-game tournament tier weight (MESSI-style).
        window["game_days_ago"] = i - window["grouped_date_id"]
        window["date_weight"] = 1 - (window["game_days_ago"] / WINDOW_GAME_DAYS)
        window["weight"] = window["date_weight"] * window["tier"]
        window = window[window["weight"] > 0]
        if len(window) < 10:
            continue

        ranked = _solve_massey(window)
        if ranked["rating"].isna().any() or np.isinf(ranked["rating"]).any():
            continue

        # games-in-window count per team (eligibility filter).
        ga = window.groupby("team_a").size().rename("ga")
        gb = window.groupby("team_b").size().rename("gb")
        gp = pd.concat([ga, gb], axis=1).fillna(0)
        gp["games_in_window"] = (gp["ga"] + gp["gb"]).astype(int)
        ranked = ranked.merge(
            gp[["games_in_window"]], left_on="code", right_index=True, how="left"
        )
        ranked["games_in_window"] = ranked["games_in_window"].fillna(0).astype(int)

        ranked["ranking_id"] = i
        ranked["date"] = current_date
        ranked["season"] = current_date.year
        frames.append(ranked)

        if current_date.year != last_year:
            pct = round(100 * i / max_id)
            print(f"  Ratings: {current_date.year} ({pct}%)")
            last_year = current_date.year

    ratings = pd.concat(frames, ignore_index=True)
    ratings["country"] = ratings["code"].map(CODE_TO_NAME).fillna(ratings["code"])
    ratings["confederation"] = ratings["code"].map(CONFEDERATION).fillna("Other")
    return ratings


# ============================================================
# CAREER / STANDINGS HELPERS
# ============================================================

def attach_last_game(ratings, games):
    """Attach each team's most-recent game result as of each ranking date."""
    g = games.copy()
    g["a_str"] = (np.where(g["a_win"] == 1, "W ", "L ") + g["score_a"].astype(int).astype(str)
                  + "-" + g["score_b"].astype(int).astype(str) + " vs. "
                  + g["team_b"].map(CODE_TO_NAME).fillna(g["team_b"])
                  + " (" + g["tournament"] + ")")
    g["b_str"] = (np.where(g["b_win"] == 1, "W ", "L ") + g["score_b"].astype(int).astype(str)
                  + "-" + g["score_a"].astype(int).astype(str) + " vs. "
                  + g["team_a"].map(CODE_TO_NAME).fillna(g["team_a"])
                  + " (" + g["tournament"] + ")")
    la = g[["date", "team_a", "a_str"]].rename(columns={"team_a": "code", "a_str": "last_game"})
    lb = g[["date", "team_b", "b_str"]].rename(columns={"team_b": "code", "b_str": "last_game"})
    last = pd.concat([la, lb], ignore_index=True)
    last["date"] = pd.to_datetime(last["date"])

    r = ratings.copy()
    r["date_dt"] = pd.to_datetime(r["date"])
    r = r.sort_values("date_dt")
    last = last.sort_values("date")
    merged = pd.merge_asof(
        r, last.rename(columns={"date": "match_date"}),
        left_on="date_dt", right_on="match_date", by="code", direction="backward",
    )
    merged["last_game"] = merged["last_game"].fillna("")
    merged["last_game_date"] = merged["match_date"].dt.date
    merged = merged.drop(columns=["date_dt", "match_date"])
    return merged


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print(f"CARMELO rating engine — window={WINDOW_GAME_DAYS} game-days, "
          f"cap={MARGIN_CAP}, HCA={HOME_COURT_ADJUSTMENT} (non-neutral only)")
    games = load_games()
    print(f"Loaded {len(games):,} games over "
          f"{games['date'].min()} .. {games['date'].max()} "
          f"({games['grouped_date_id'].max()} game-days)")

    ratings = compute_ratings(games)
    ratings = attach_last_game(ratings, games)

    # Eligibility filter for the PUBLISHED file (full history kept for snapshots
    # but min-games guards the displayed leaderboard).
    ratings = ratings.sort_values(["ranking_id", "rank"]).reset_index(drop=True)
    ratings.to_csv(RATINGS_CSV, index=False)
    print(f"\n{RATINGS_CSV} saved ({len(ratings):,} rows)")

    # Face-validity: most-recent snapshot top 15 (min-games filtered).
    latest_id = ratings["ranking_id"].max()
    latest = ratings[(ratings["ranking_id"] == latest_id) &
                     (ratings["games_in_window"] >= MIN_GAMES)].copy()
    latest = latest.sort_values("rating", ascending=False).head(15)
    print(f"\n=== FACE-VALIDITY: top 15 as of {ratings.loc[ratings['ranking_id']==latest_id,'date'].iloc[0]} ===")
    print(latest[["rank", "country", "confederation", "rating", "games_in_window"]]
          .to_string(index=False))
