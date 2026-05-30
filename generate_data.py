"""
generate_data.py — reads carmelo_ratings.csv + all_games.csv and writes the JSON
the CARMELO web frontend (a MESSI-clone single-page app) consumes. Run after
carmelo.py. Outputs to docs/data/.

Emits the MESSI JSON contract so the ported index.html works unchanged:
  seasons_index.json      {seasons, first_date, last_date, generated_at}
  seasons/<year>.json     {season, snapshots:[{date, label, prestige, teams:[...]}]}
  teams_index.json        [{name, flag, confederation, slug}, ...]
  teams/<slug>.json       {team, flag, confederation, seasons:{<year>:[rows]}}
  goat_teams.json         top-50 single-snapshot ratings at FLAGSHIP finals
  champions.json          per-tournament edition podiums (Tournaments tab)
  current_standings.json  most-recent snapshot leaderboard (compatibility)

Sport adaptation vs MESSI:
  - confederations are FIBA zones: Europe / Americas / Asia/Oceania / Africa
  - margins are "points" (basketball), no draws — W-L records only
  - "League History" tab becomes a "Tournaments" tab built from champions.json,
    one row per edition (Gold / Silver / Bronze) with cumulative medal counts,
    each medalist's rating/rank at that edition's final snapshot, and that
    team's W-L within that specific edition.
"""
import os
import json
import re
import bisect
import pandas as pd
from datetime import datetime, timezone, timedelta

from countries import CODE_TO_NAME, CONFEDERATION, canon_code, NAME_HISTORY

# Pre-parsed (code -> [(name, start_date, end_date), ...]) for fast lookup.
_NAME_HISTORY_PARSED = {
    code: [(n, pd.to_datetime(s).date(), pd.to_datetime(e).date())
           for n, s, e in entries]
    for code, entries in NAME_HISTORY.items()
}
# canonical name -> list of historical names (for teams_index + per-team
# JSON `historical_names` field, used by the SPA's team-select dropdown
# enrichment and team-page header).
HISTORICAL_NAMES_BY_NAME = {
    CODE_TO_NAME.get(code, code): [n for n, _, _ in entries]
    for code, entries in NAME_HISTORY.items()
}
_NAME_TO_CANON_CODE = {v: k for k, v in CODE_TO_NAME.items()}


def display_name_at(code, as_of):
    """DILLON era-aware display name. Returns the historical name in effect on
    `as_of` (a date or date-like) if NAME_HISTORY covers it; else None."""
    hist = _NAME_HISTORY_PARSED.get(code)
    if not hist:
        return None
    d = as_of if hasattr(as_of, "year") else pd.to_datetime(as_of).date()
    for name, start, end in hist:
        if start <= d <= end:
            return name
    return None

DATA_DIR = "docs/data"
os.makedirs(os.path.join(DATA_DIR, "teams"), exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "seasons"), exist_ok=True)

MIN_GAMES = 4  # eligibility for displayed leaderboard / GOAT
GOAT_MIN_GAMES = 4

# Tournaments that crown a champion (qualifiers excluded).
MEDAL_TOURNAMENTS = ["Olympics", "FIBA World Cup", "EuroBasket",
                     "FIBA AmeriCup", "FIBA Asia Cup", "FIBA AfroBasket"]

# Flagship tournaments anchor GOAT entries (continental championships still feed
# the rolling rating but do NOT anchor GOAT entries). 👑 = Olympics (the global
# pinnacle for basketball); the World Cup is the other flagship.
FLAGSHIP_TOURNAMENTS = ["Olympics", "FIBA World Cup"]

# Tournament selector grouping for the Tournaments tab pills.
GLOBAL_TOURNAMENTS = ["Olympics", "FIBA World Cup"]
CONTINENTAL_TOURNAMENT_LIST = ["EuroBasket", "FIBA AmeriCup", "FIBA Asia Cup", "FIBA AfroBasket"]

# Standings season-file labels: tournament -> (label, prestige). Lower prestige
# = more prestigious (controls dropdown default + ordering), mirroring MESSI.
TOURNAMENT_LABELS = {
    "Olympics":        ("Olympic Final",   1),
    "FIBA World Cup":  ("World Cup Final",  2),
    "EuroBasket":      ("EuroBasket Final", 3),
    "FIBA AmeriCup":   ("AmeriCup Final",   4),
    "FIBA Asia Cup":   ("Asia Cup Final",   5),
    "FIBA AfroBasket": ("AfroBasket Final", 6),
}

# Continental championship per FIBA zone (used for the Team Summary year anchor
# + the continental-winner gold pill).
CONFED_CHAMPIONSHIP = {
    "Europe":       "EuroBasket",
    "Americas":     "FIBA AmeriCup",
    "Asia/Oceania": "FIBA Asia Cup",
    "Africa":       "FIBA AfroBasket",
}
CONTINENTAL_TOURNAMENTS = {"EuroBasket", "FIBA AmeriCup", "FIBA Asia Cup", "FIBA AfroBasket"}

# Tournament name -> short label for honor badges.
TOURNAMENT_ABBREV = {
    "Olympics":        "Oly",
    "FIBA World Cup":  "WC",
    "EuroBasket":      "Euro",
    "FIBA AmeriCup":   "AmeriCup",
    "FIBA Asia Cup":   "Asia Cup",
    "FIBA AfroBasket": "AfroBasket",
}

# ISO alpha-2 for flag emoji. FIBA 3-letter code -> ISO2.
CODE_TO_ISO2 = {
    "USA": "US", "ESP": "ES", "SRB": "RS", "FRA": "FR", "GRE": "GR",
    "LTU": "LT", "SLO": "SI", "GER": "DE", "ITA": "IT", "CRO": "HR",
    "TUR": "TR", "RUS": "RU", "CZE": "CZ", "POL": "PL", "FIN": "FI",
    "LAT": "LV", "EST": "EE", "GEO": "GE", "UKR": "UA", "MNE": "ME",
    "BIH": "BA", "BEL": "BE", "NED": "NL", "GBR": "GB", "SWE": "SE",
    "NOR": "NO", "DEN": "DK", "ISR": "IL", "MKD": "MK", "HUN": "HU",
    "BUL": "BG", "ROU": "RO", "AUT": "AT", "SUI": "CH", "POR": "PT",
    "ISL": "IS", "IRL": "IE", "CYP": "CY", "SVK": "SK", "ALB": "AL",
    "ARM": "AM", "AZE": "AZ", "BLR": "BY", "MDA": "MD", "KOS": "XK",
    "LUX": "LU", "MLT": "MT", "MON": "MC", "AND": "AD", "SMR": "SM",
    "GIB": "GI",
    "ARG": "AR", "BRA": "BR", "CAN": "CA", "PUR": "PR", "MEX": "MX",
    "VEN": "VE", "DOM": "DO", "URU": "UY", "CHI": "CL", "COL": "CO",
    "PAN": "PA", "CUB": "CU", "ECU": "EC", "PER": "PE", "PAR": "PY",
    "BOL": "BO", "BAH": "BS", "ISV": "VI", "CRC": "CR", "JAM": "JM",
    "NCA": "NI", "HON": "HN", "GUA": "GT", "ESA": "SV", "SLV": "SV",
    "TTO": "TT", "HAI": "HT", "ARU": "AW", "GUY": "GY",
    "AUS": "AU", "NZL": "NZ", "CHN": "CN", "PHI": "PH", "JPN": "JP",
    "KOR": "KR", "PRK": "KP", "IRI": "IR", "IRN": "IR", "JOR": "JO",
    "LBN": "LB", "SYR": "SY", "QAT": "QA", "KSA": "SA", "UAE": "AE",
    "IRQ": "IQ", "KAZ": "KZ", "IND": "IN", "INA": "ID", "TPE": "TW",
    "THA": "TH", "MAS": "MY", "SIN": "SG", "VIE": "VN", "HKG": "HK",
    "KUW": "KW", "BHR": "BH", "PLE": "PS", "UZB": "UZ", "MGL": "MN",
    "SRI": "LK", "BAN": "BD", "PAK": "PK", "GUM": "GU", "FIJ": "FJ",
    "ANG": "AO", "NGR": "NG", "SEN": "SN", "CIV": "CI", "TUN": "TN",
    "EGY": "EG", "CMR": "CM", "MLI": "ML", "CPV": "CV", "SSD": "SS",
    "GUI": "GN", "MAR": "MA", "ALG": "DZ", "RSA": "ZA", "CGO": "CG",
    "COD": "CD", "KEN": "KE", "UGA": "UG", "MOZ": "MZ", "MAD": "MG",
    "RWA": "RW", "GHA": "GH", "GAB": "GA", "CAF": "CF", "CHA": "TD",
    "LBA": "LY", "BKF": "BF", "ZAM": "ZM", "ZIM": "ZW", "NAM": "NA",
    "BOT": "BW", "GBS": "GW", "TOG": "TG",
}

# Defunct entities have no real-world flag emoji (Soviet Union / SFR & FR
# Yugoslavia / Serbia & Montenegro / West & East Germany / Czechoslovakia).
# Show a neutral white-flag marker rather than crashing or picking a wrong
# modern flag. Modern flags are unaffected.
_DEFUNCT = {"URS", "YUG", "SCG", "FRG", "GDR", "TCH"}
_DEFUNCT_FLAG = "\U0001F3F3️"  # 🏳️ neutral marker for defunct nations


def flag(code):
    code = canon_code(code)
    if code in _DEFUNCT:
        return _DEFUNCT_FLAG
    iso = CODE_TO_ISO2.get(code)
    if not iso or len(iso) != 2:
        return ""
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in iso.upper())


def name_for(code):
    return CODE_TO_NAME.get(canon_code(code), code)


def confed_for(code):
    return CONFEDERATION.get(canon_code(code), "Other")


def slug(name):
    return re.sub(r"[^\w]", "_", name).strip("_")


def clean(val):
    if pd.isna(val):
        return ""
    return str(val)


def round3(x):
    try:
        return round(float(x), 3)
    except (TypeError, ValueError):
        return None


# ============================================================
# LOAD
# ============================================================
print("Reading ratings + games...")
df = pd.read_csv("carmelo_ratings.csv")
df["date"] = pd.to_datetime(df["date"]).dt.date
df["code"] = df["code"].map(canon_code)
# Recompute canonical display fields (engine fields are kept but we re-derive
# so alias codes collapse onto one country / flag / confederation).
df["country"] = df["code"].map(name_for)
df["confederation"] = df["code"].map(confed_for)

games = pd.read_csv("all_games.csv")
games["date"] = pd.to_datetime(games["date"]).dt.date
games["team_a"] = games["team_a"].map(canon_code)
games["team_b"] = games["team_b"].map(canon_code)
games["score_a"] = pd.to_numeric(games["score_a"], errors="coerce")
games["score_b"] = pd.to_numeric(games["score_b"], errors="coerce")
games = games.dropna(subset=["score_a", "score_b"])

# Every CARMELO ratings snapshot date is a game-day (one ranking_id per date).
df["is_game_day"] = 1

# ── W-L record over the rating WINDOW, AS OF a snapshot date ─────────────────
# Each snapshot shows its team's W-L over the WINDOW_YEARS ending at THAT
# snapshot's date — so a 2004 snapshot shows 2000-2004 records, matching its
# rating window. (A global-latest-window version made historical season files
# show present-day records, e.g. currently-banned Russia as 0-0 next to a 2004
# rating.) WINDOW_YEARS must match carmelo.py's window.
WINDOW_YEARS = 4
_WINDOW_DELTA = timedelta(days=int(WINDOW_YEARS * 365.25))
_team_outcomes = {}  # code -> ([sorted dates], [won bools aligned])
_tmp_oc = {}
for _, g in games.iterrows():
    a_won = g["score_a"] > g["score_b"]
    for code, won in ((g["team_a"], a_won), (g["team_b"], not a_won)):
        _tmp_oc.setdefault(code, []).append((g["date"], bool(won)))
for _c, _lst in _tmp_oc.items():
    _lst.sort(key=lambda x: x[0])
    _team_outcomes[_c] = ([d for d, _ in _lst], [w for _, w in _lst])


def record_str(code, as_of):
    """W-L over the WINDOW_YEARS calendar window ending at as_of (a date)."""
    entry = _team_outcomes.get(code)
    if not entry:
        return "0-0"
    dates, wons = entry
    lo = bisect.bisect_left(dates, as_of - _WINDOW_DELTA)
    hi = bisect.bisect_right(dates, as_of)
    w = sum(1 for x in wons[lo:hi] if x)
    return f"{w}-{(hi - lo) - w}"


# ============================================================
# MEDALS (per edition gold/silver/bronze) — CURATED authoritative source
# ============================================================
# Podiums are read from curated_podiums.csv (the authoritative medalist table,
# sourced from Wikipedia per-tournament results summaries with era-aware nation
# codes), NOT bracket-walked from all_games.csv. Bracket-walking misattributed
# golds for editions whose gold-medal game lives on a Template-namespace page the
# scraper never fetched (e.g. Tokyo 2020), and dropped bronze for editions whose
# 3rd-place game shared the final date with the final. The curated table fixes
# both. Each medalist's rating/rank/conf_rank (final-snapshot) and edition W-L
# are still computed from carmelo_ratings.csv / all_games.csv below.
CURATED_PODIUMS_CSV = "curated_podiums.csv"


# ── Per-team W-L within a single tournament edition (no draws in basketball) ──
def edition_team_wl(grp, code):
    """W-L for `code` within one (tournament, season) edition group."""
    w = l = 0
    for _, x in grp.iterrows():
        if x["team_a"] == code:
            won = x["score_a"] > x["score_b"]
        elif x["team_b"] == code:
            won = x["score_b"] > x["score_a"]
        else:
            continue
        if won:
            w += 1
        else:
            l += 1
    return f"{w}-{l}"


# edition_results[(tournament, season)] = {1:gold,2:silver,3:bronze}, all codes
# edition_groups[(tournament, season)] = the full edition game DataFrame (for W-L)
# Medalists come from the curated table; game groups (for edition W-L) come from
# all_games.csv keyed by the same (tournament, season).
edition_results = {}
edition_groups = {}
mgames = games[games["tournament"].isin(MEDAL_TOURNAMENTS)].copy()
edition_groups = {
    (tour, int(season)): grp
    for (tour, season), grp in mgames.groupby(["tournament", "season"])
}

_curated = pd.read_csv(CURATED_PODIUMS_CSV)
for _, _row in _curated.iterrows():
    tour = _row["tournament"]
    if tour not in MEDAL_TOURNAMENTS:
        continue
    season = int(_row["year"])

    def _code(val):
        if pd.isna(val) or str(val).strip() == "":
            return None
        return canon_code(str(val).strip())

    edition_results[(tour, season)] = {
        1: _code(_row.get("gold")),
        2: _code(_row.get("silver")),
        3: _code(_row.get("bronze")),
    }
print(f"  loaded {len(edition_results)} curated edition podiums from {CURATED_PODIUMS_CSV}")

# Per-(code, year) tournament finishes for honor badges.
country_year_finishes = {}  # (code, year) -> [{tournament, finish}]
for (tour, season), res in edition_results.items():
    for finish, code in res.items():
        if not code:
            continue
        country_year_finishes.setdefault((code, season), []).append(
            {"tournament": TOURNAMENT_ABBREV.get(tour, tour), "finish": finish})
for key in country_year_finishes:
    country_year_finishes[key].sort(key=lambda x: x["finish"])


def finishes_for(code, year):
    if pd.isna(year):
        return []
    return country_year_finishes.get((code, int(year)), [])


# Continental winners: (code, year) for any continental championship won.
continental_winners = set()
for (tour, season), res in edition_results.items():
    if tour in CONTINENTAL_TOURNAMENTS and res.get(1):
        continental_winners.add((res[1], season))


# ============================================================
# TOURNAMENT FINAL DATES (per tournament+year) — labels, GOAT + year anchors
# ============================================================
# In-progress gate (see [[feedback-in-progress-season-gate]]): only assign a
# "final date" to a tournament edition that has actually concluded. Signals:
# (a) a game with round=='final' or 'bronze', (b) a curated podium entry.
# Without this gate an in-progress event's latest played game-day gets
# labeled the "Final", which is wrong.
podium_editions = set(edition_results.keys())
tournament_final_date = {}  # (tournament, year) -> final date
for tour in MEDAL_TOURNAMENTS:
    tg = games[games["tournament"] == tour]
    if tg.empty:
        continue
    for year, grp in tg.groupby("season"):
        year = int(year)
        if "round" in grp.columns:
            medal_dates = grp.loc[grp["round"].isin(["final", "bronze"]), "date"]
        else:
            medal_dates = []
        if len(medal_dates):
            tournament_final_date[(tour, year)] = medal_dates.max()
        elif (tour, year) in podium_editions:
            tournament_final_date[(tour, year)] = grp["date"].max()
        # else: in progress -- no Final label assigned

final_dates = set(tournament_final_date.values())
df["is_end_of_season"] = df["date"].apply(lambda d: 1 if d in final_dates else 0)

# date -> (label, prestige) for season-file snapshot labels.
date_label_map = {}
for (tour, year), fdate in tournament_final_date.items():
    lbl, prestige = TOURNAMENT_LABELS.get(tour, (tour, 99))
    ds = str(fdate)
    if ds not in date_label_map or date_label_map[ds][1] > prestige:
        date_label_map[ds] = (lbl, prestige)

# ── Per-(code, year) team participation in each tournament (year anchors) ────
team_year_tournaments = {}  # (code, year) -> set(tournaments)
for tour in MEDAL_TOURNAMENTS:
    tg = games[games["tournament"] == tour]
    for _, g in tg.iterrows():
        yr = int(g["season"])
        for code in (g["team_a"], g["team_b"]):
            team_year_tournaments.setdefault((code, yr), set()).add(tour)

# Latest known confederation per code.
team_confed = df.dropna(subset=["confederation"]).groupby("code")["confederation"].last().to_dict()
# Last game-day per (code, year) — fallback anchor.
team_year_last_game = (
    df[df["is_game_day"] == 1].dropna(subset=["season"])
      .groupby(["code", "season"])["date"].max().to_dict()
)

team_year_anchor = {}  # (code, year) -> (date, label)
for (code, year_f), last_game in team_year_last_game.items():
    year = int(year_f)
    played = team_year_tournaments.get((code, year), set())
    chosen = None
    # 1. Olympics (the global pinnacle for basketball)
    if "Olympics" in played and ("Olympics", year) in tournament_final_date:
        chosen = (tournament_final_date[("Olympics", year)], "End of Olympic basketball")
    # 2. FIBA World Cup
    if chosen is None and "FIBA World Cup" in played and ("FIBA World Cup", year) in tournament_final_date:
        chosen = (tournament_final_date[("FIBA World Cup", year)], "End of FIBA World Cup")
    # 3. Confederation championship
    if chosen is None:
        confed_t = CONFED_CHAMPIONSHIP.get(team_confed.get(code))
        if confed_t and confed_t in played and (confed_t, year) in tournament_final_date:
            chosen = (tournament_final_date[(confed_t, year)], f"End of {confed_t}")
    # 4. Fallback: last game-day of the year
    if chosen is None:
        chosen = (last_game, "End of year")
    team_year_anchor[(code, year)] = chosen

df["is_year_anchor"] = 0
df["year_anchor_label"] = ""
for (code, year), (d, label) in team_year_anchor.items():
    mask = (df["code"] == code) & (df["date"] == d) & (df["season"] == year)
    if mask.any():
        df.loc[mask, "is_year_anchor"] = 1
        df.loc[mask, "year_anchor_label"] = label

# ── Rank + conf_rank recomputed within MIN_GAMES-eligible teams per snapshot ──
# The engine's stored rank includes thin-sample teams; the displayed leaderboard
# filters to games_in_window >= MIN_GAMES, so we redensify rank/conf_rank here.
df["eligible"] = df["games_in_window"] >= MIN_GAMES
df["rank"] = (
    df[df["eligible"]].groupby("ranking_id")["rating"].rank(method="min", ascending=False)
)
df["conf_rank"] = (
    df[df["eligible"]].groupby(["ranking_id", "confederation"])["rating"]
      .rank(method="min", ascending=False)
)


# ============================================================
# 1) SEASON STANDINGS FILES (one per year) + seasons_index.json
# ============================================================
print("Writing season standings files...")
all_seasons = sorted(int(s) for s in df["season"].dropna().unique())


def team_row(r, as_of, slim=False):
    out = {
        "rank":                int(r["rank"]) if not pd.isna(r["rank"]) else None,
        "team":                r["country"],
        "flag":                flag(r["code"]),
        "confederation":       clean(r["confederation"]),
        "rating":              round3(r["rating"]),
        "record":              record_str(r["code"], as_of),
        "last_match":          clean(r["last_game"]),
        "last_match_date":     clean(r["last_game_date"]),
        "tournament_finishes": finishes_for(r["code"], r["season"]),
        "continental_winner":  1 if (r["code"], int(r["season"])) in continental_winners else 0,
    }
    era = display_name_at(r["code"], as_of)
    if era and era != r["country"]:
        out["display_name"] = era
    return out


for season in all_seasons:
    sdf = df[(df["season"] == season) & df["eligible"]]
    snapshots = []
    for ranking_id, rdf in sdf.groupby("ranking_id"):
        rdf = rdf.sort_values("rank")
        snap_date_obj = rdf["date"].iloc[0]
        snap_date = str(snap_date_obj)
        label, prestige = date_label_map.get(snap_date, (None, None))
        snapshots.append({
            "date": snap_date, "label": label, "prestige": prestige,
            "teams": [team_row(r, snap_date_obj) for _, r in rdf.iterrows()],
        })
    snapshots.sort(key=lambda x: x["date"])
    with open(f"{DATA_DIR}/seasons/{season}.json", "w") as f:
        json.dump({"season": season, "snapshots": snapshots}, f,
                  separators=(",", ":"), ensure_ascii=False)

seasons_meta = {
    "seasons":      list(reversed(all_seasons)),
    "first_date":   str(df["date"].min()),
    "last_date":    str(df["date"].max()),
    "generated_at": datetime.now(timezone.utc).isoformat(),
}
with open(f"{DATA_DIR}/seasons_index.json", "w") as f:
    json.dump(seasons_meta, f, separators=(",", ":"), ensure_ascii=False)
print(f"  {len(all_seasons)} season files + seasons_index.json")


# ============================================================
# 2) CURRENT STANDINGS (latest snapshot) — compatibility output
# ============================================================
latest_id = int(df["ranking_id"].max())
latest = df[(df["ranking_id"] == latest_id) & df["eligible"]].sort_values("rank")
latest_date_obj = latest["date"].iloc[0] if len(latest) else None
latest_date = str(latest_date_obj) if latest_date_obj is not None else seasons_meta["last_date"]
standings = []
for _, r in latest.iterrows():
    row = team_row(r, latest_date_obj)
    row["games_played"] = int(r["games_in_window"]) if not pd.isna(r["games_in_window"]) else 0
    standings.append(row)
with open(f"{DATA_DIR}/current_standings.json", "w") as f:
    json.dump({"updated": latest_date, "teams": standings},
              f, separators=(",", ":"), ensure_ascii=False)
print(f"  current_standings.json: {len(standings)} teams as of {latest_date}")


# ============================================================
# 3) GOAT TABLE — top-50 single-snapshot ratings at FLAGSHIP finals
# ============================================================
print("Writing goat_teams.json...")
# Eligibility: medaled (1st/2nd/3rd) in a FLAGSHIP tournament (Olympics or FIBA
# World Cup) that year. Anchor the rating at THAT tournament's final date.
# Continental championships still feed the rolling rating but do NOT anchor a
# GOAT entry — this dedupes to one entry per team per flagship edition and
# drops the overlapping-window clusters (e.g. "USA 2017" from FIBA AmeriCup).
# Mirrors MESSI's GOAT logic.
eligible_podiums = []  # (code, year, tournament)
for (tour, season), res in edition_results.items():
    if tour not in FLAGSHIP_TOURNAMENTS:
        continue
    for finish, code in res.items():
        if code:
            eligible_podiums.append((code, season, tour))
eligible_podiums = sorted(set(eligible_podiums))

df_idx = df.copy()
df_idx["_date_str"] = df_idx["date"].astype(str)
df_idx = df_idx.set_index(["code", "_date_str"])

goat_candidates = []
for code, year, tour in eligible_podiums:
    fdate = tournament_final_date.get((tour, year))
    if fdate is None:
        continue
    try:
        snap = df_idx.loc[(code, str(fdate))]
    except KeyError:
        continue
    if isinstance(snap, pd.DataFrame):
        snap = snap.iloc[0]
    if pd.isna(snap.get("rating")):
        continue
    if snap.get("games_in_window", 0) < GOAT_MIN_GAMES:
        continue
    goat_candidates.append({
        "code": code, "year": year, "tournament": tour,
        "rating": float(snap["rating"]),
        "confederation": clean(snap.get("confederation", "")),
    })

if goat_candidates:
    goat_df = (
        pd.DataFrame(goat_candidates)
        .sort_values("rating", ascending=False)
        .drop_duplicates(subset=["code", "year"], keep="first")
        .head(50)
        .reset_index(drop=True)
    )
else:
    goat_df = pd.DataFrame(columns=["code", "year", "tournament", "rating", "confederation"])

goat_data = []
for i, (_, r) in enumerate(goat_df.iterrows()):
    nm = name_for(r["code"])
    entry = {
        "rank":                i + 1,
        "team":                nm,
        "flag":                flag(r["code"]),
        "confederation":       clean(r["confederation"]),
        "season":              int(r["year"]),
        "rating":              round3(r["rating"]),
        "tournament_finishes": finishes_for(r["code"], r["year"]),
        "continental_winner":  1 if (r["code"], int(r["year"])) in continental_winners else 0,
    }
    fdate = tournament_final_date.get((r.get("tournament", ""), int(r["year"])))
    era = display_name_at(r["code"], fdate) if fdate else None
    if era and era != nm:
        entry["display_name"] = era
    goat_data.append(entry)
with open(f"{DATA_DIR}/goat_teams.json", "w") as f:
    json.dump(goat_data, f, separators=(",", ":"), ensure_ascii=False)
print(f"  goat_teams.json: {len(goat_data)} teams")


# ============================================================
# 4) PER-TEAM JSON FILES + teams_index.json
# ============================================================
print("Writing per-team JSON files...")
team_data = df[(df["is_game_day"] == 1) | (df["is_end_of_season"] == 1) |
               (df["is_year_anchor"] == 1)].copy()
team_data = team_data.sort_values(["code", "date"])

# (code, year) where the team actually played >= 1 game — drop ghost years.
played_team_years = set(
    (c, int(y)) for c, y in
    df.loc[df["is_game_day"] == 1, ["code", "season"]].dropna().itertuples(index=False, name=None)
)

all_codes = sorted(df["code"].unique())
teams_index = []
for code in all_codes:
    tdf = team_data[team_data["code"] == code]
    if len(tdf) == 0:
        continue
    name = name_for(code)
    team_slug = slug(name)
    confed = confed_for(code)
    fl = flag(code)
    hist_names = HISTORICAL_NAMES_BY_NAME.get(name, [])
    idx_entry = {"name": name, "flag": fl, "confederation": confed, "slug": team_slug}
    if hist_names:
        idx_entry["historical_names"] = hist_names
    teams_index.append(idx_entry)

    seasons = {}
    for season, sdf in tdf.groupby("season"):
        if pd.isna(season):
            continue
        if (code, int(season)) not in played_team_years:
            continue
        fin = finishes_for(code, season)
        won_cont = (code, int(season)) in continental_winners
        rows = []
        for _, r in sdf.sort_values("date").iterrows():
            row = {
                "date":                str(r["date"]),
                "rating":              round3(r["rating"]),
                "rank":                int(r["rank"]) if not pd.isna(r["rank"]) else None,
                "conf_rank":           int(r["conf_rank"]) if not pd.isna(r["conf_rank"]) else None,
                "last_match":          clean(r["last_game"]),
                "is_end_of_season":    int(r["is_end_of_season"]),
                "is_game_day":         int(r["is_game_day"]),
                "is_year_anchor":      int(r.get("is_year_anchor", 0) or 0),
                "year_anchor_label":   clean(r.get("year_anchor_label", "")),
                "tournament_finishes": fin,
                "continental_winner":  1 if won_cont else 0,
            }
            era = display_name_at(code, r["date"])
            if era and era != name:
                row["display_name"] = era
            rows.append(row)
        seasons[int(season)] = rows

    team_doc = {"team": name, "flag": fl, "confederation": confed, "seasons": seasons}
    if hist_names:
        team_doc["historical_names"] = hist_names
    with open(f"{DATA_DIR}/teams/{team_slug}.json", "w") as f:
        json.dump(team_doc, f, separators=(",", ":"), ensure_ascii=False)

teams_index.sort(key=lambda x: x["name"])
with open(f"{DATA_DIR}/teams_index.json", "w") as f:
    json.dump(teams_index, f, separators=(",", ":"), ensure_ascii=False)
print(f"  teams_index.json + {len(teams_index)} team files")


# ============================================================
# 4b) CHAMPIONS TABLE (per tournament edition) — Tournaments tab
# ============================================================
# Emits the MESSI champions.json contract, grouped by tournament, editions
# newest-first. Each medalist cell carries:
#   - cumulative medal count for that country in that tournament
#   - rating / rank / conf_rank at that edition's FINAL snapshot
#   - W-L within that specific edition (CARMELO addition vs MESSI)
# Editions where no medalist has a rated snapshot at the final date are marked
# pre_rated (UI renders dashes + † footnote, mirroring MESSI's pre-1986 rows).
print("Writing champions.json...")

# Final-day rating/rank lookup keyed by (code, date_str) — reuse the GOAT index.
_df_str = df.copy()
_df_str["_date_str"] = _df_str["date"].astype(str)
_champ_idx = _df_str.set_index(["code", "_date_str"])


def edition_team_info(code, tour, year):
    """Rating/rank/conf_rank for a medalist at the edition's final snapshot."""
    fdate = tournament_final_date.get((tour, int(year)))
    if fdate is None:
        return {"rating": None, "rank": None, "conf_rank": None, "confederation": confed_for(code)}
    try:
        snap = _champ_idx.loc[(code, str(fdate))]
    except KeyError:
        return {"rating": None, "rank": None, "conf_rank": None, "confederation": confed_for(code)}
    if isinstance(snap, pd.DataFrame):
        snap = snap.iloc[0]
    return {
        "rating":        round3(snap.get("rating")),
        "rank":          int(snap["rank"]) if not pd.isna(snap.get("rank")) else None,
        "conf_rank":     int(snap["conf_rank"]) if not pd.isna(snap.get("conf_rank")) else None,
        "confederation": clean(snap.get("confederation", "")) or confed_for(code),
    }


# Cumulative counts per (tournament, code, slot) tallied oldest-first so each
# edition reflects the running total THROUGH that edition (matches MESSI).
champions = {}
for tour in MEDAL_TOURNAMENTS:
    years = sorted(y for (t, y) in edition_results if t == tour)
    champ_counts, ru_counts, third_counts = {}, {}, {}
    entries_oldest_first = []
    for year in years:
        res = edition_results[(tour, year)]
        grp = edition_groups.get((tour, year), games.iloc[0:0])
        gold, silver, bronze = res.get(1), res.get(2), res.get(3)

        def team_block(code, count_key, counter, _tour=tour, _year=year, _grp=grp):
            if not code:
                return None
            counter[code] = counter.get(code, 0) + 1
            info = edition_team_info(code, _tour, _year)
            nm = name_for(code)
            block = {
                "team":          nm,
                "flag":          flag(code),
                "confederation": info["confederation"],
                "rating":        info["rating"],
                "rank":          info["rank"],
                "conf_rank":     info["conf_rank"],
                count_key:       counter[code],
                "wl":            edition_team_wl(_grp, code),
            }
            fdate = tournament_final_date.get((_tour, _year))
            era = display_name_at(code, fdate) if fdate else None
            if era and era != nm:
                block["display_name"] = era
            return block

        entries_oldest_first.append({
            "season":     year,
            "host_flags": "",  # host data not modeled for CARMELO; UI hides empty
            "champion":   team_block(gold,   "title_count",     champ_counts),
            "runner_up":  team_block(silver, "runner_up_count", ru_counts),
            "third":      team_block(bronze, "third_count",      third_counts),
        })

    # Mark pre_rated editions (no medalist has a rated snapshot at the final
    # date) and strip the now-meaningless rating/rank fields. Mirrors MESSI.
    for entry in entries_oldest_first:
        rated = any(
            entry.get(slot) and entry[slot].get("rating") is not None
            for slot in ("champion", "runner_up", "third")
        )
        if rated:
            continue
        entry["pre_rated"] = True
        for slot in ("champion", "runner_up", "third"):
            tb = entry.get(slot)
            if not tb:
                continue
            for k in ("rating", "rank", "conf_rank", "confederation"):
                tb.pop(k, None)

    champions[tour] = list(reversed(entries_oldest_first))  # newest-first

with open(f"{DATA_DIR}/champions.json", "w") as f:
    json.dump(champions, f, separators=(",", ":"), ensure_ascii=False)
print(f"  champions.json: {sum(len(v) for v in champions.values())} editions "
      f"across {len(champions)} tournaments")

# Remove the legacy flat Medals output if it exists from a prior run.
_legacy_medals = f"{DATA_DIR}/medals.json"
if os.path.exists(_legacy_medals):
    os.remove(_legacy_medals)
    print("  removed legacy medals.json")


# ============================================================
# 5) META (coverage + refresh timestamp)
# ============================================================
meta = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "current_date": latest_date,
    "first_date":   str(games["date"].min()),
    "last_date":    str(games["date"].max()),
    "total_games":  int(len(games)),
    "n_tournaments": int(games["tournament"].nunique()),
}
with open(f"{DATA_DIR}/meta.json", "w") as f:
    json.dump(meta, f, separators=(",", ":"), ensure_ascii=False)

print(f"Done. {len(teams_index)} teams, {len(standings)} in current standings.")
print(f"Wrote {len(all_seasons)} season files. Standings date: {latest_date}")
