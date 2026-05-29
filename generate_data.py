"""
generate_data.py — reads carmelo_ratings.csv + all_games.csv and writes the JSON
the CARMELO web frontend (a MESSI-clone single-page app) consumes. Run after
carmelo.py. Outputs to docs/data/.

Emits the MESSI JSON contract so the ported index.html works unchanged:
  seasons_index.json      {seasons, first_date, last_date, generated_at}
  seasons/<year>.json     {season, snapshots:[{date, label, prestige, teams:[...]}]}
  teams_index.json        [{name, flag, confederation, slug}, ...]
  teams/<slug>.json       {team, flag, confederation, seasons:{<year>:[rows]}}
  goat_teams.json         top-50 single-snapshot ratings at tournament finals
  medals.json             per-country gold/silver/bronze counts (Medals tab)
  current_standings.json  most-recent snapshot leaderboard (compatibility)

Sport adaptation vs MESSI:
  - confederations are FIBA zones: Europe / Americas / Asia/Oceania / Africa
  - margins are "points" (basketball), no draws — W-L records only
  - "League History" tab is replaced by a "Medals" tab built from medals.json
"""
import os
import json
import re
import pandas as pd
from datetime import datetime, timezone

from countries import CODE_TO_NAME, CONFEDERATION, canon_code

DATA_DIR = "docs/data"
os.makedirs(os.path.join(DATA_DIR, "teams"), exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "seasons"), exist_ok=True)

MIN_GAMES = 4  # eligibility for displayed leaderboard / GOAT
GOAT_MIN_GAMES = 4

# Tournaments that crown a champion (qualifiers excluded).
MEDAL_TOURNAMENTS = ["Olympics", "FIBA World Cup", "EuroBasket",
                     "FIBA AmeriCup", "FIBA Asia Cup", "FIBA AfroBasket"]

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

# Defunct entities — no flag emoji (intentional).
_DEFUNCT = {"URS", "YUG", "SCG", "FRG", "GDR", "TCH"}


def flag(code):
    code = canon_code(code)
    if code in _DEFUNCT:
        return ""
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

# ── W-L record per country over full history (no draws in basketball) ─────────
records = {}  # code -> {"w","l"}
for _, g in games.iterrows():
    a_won = g["score_a"] > g["score_b"]
    for code, won in ((g["team_a"], a_won), (g["team_b"], not a_won)):
        r = records.setdefault(code, {"w": 0, "l": 0})
        r["w" if won else "l"] += 1


def record_str(code):
    r = records.get(code, {"w": 0, "l": 0})
    return f"{r['w']}-{r['l']}"


# ============================================================
# MEDALS (per edition gold/silver/bronze) — mirrors the prior podium walk
# ============================================================
def edition_medals(grp):
    """Return (gold, silver, bronze codes) for one tournament edition."""
    grp = grp.sort_values("date")
    last_date = grp["date"].max()
    final_games = grp[grp["date"] == last_date]
    if final_games.empty:
        return None, None, None
    final_row = final_games.iloc[-1]

    def won_prev(team):
        prev = grp[(grp["date"] < last_date) &
                   ((grp["team_a"] == team) | (grp["team_b"] == team))].sort_values("date")
        if prev.empty:
            return None
        last = prev.iloc[-1]
        if last["team_a"] == team:
            return last["score_a"] > last["score_b"]
        return last["score_b"] > last["score_a"]

    # Gold game = the final; when the final + bronze share a date, the final is
    # the one between two prior-round winners.
    for cand in reversed(list(final_games.itertuples(index=False))):
        ah = won_prev(cand.team_a)
        bh = won_prev(cand.team_b)
        if ah and bh:
            final_row = dict(zip(final_games.columns, cand))
            break

    a, b = final_row["team_a"], final_row["team_b"]
    if final_row["score_a"] > final_row["score_b"]:
        gold, silver = a, b
    else:
        gold, silver = b, a
    finalists = {a, b}

    bronze = None
    pre = grp[grp["date"] < last_date]
    if not pre.empty:
        bdate = pre["date"].max()
        bgames = pre[(pre["date"] == bdate) &
                     (~pre["team_a"].isin(finalists)) &
                     (~pre["team_b"].isin(finalists))]
        if not bgames.empty:
            bg = bgames.iloc[-1]
            bronze = bg["team_a"] if bg["score_a"] > bg["score_b"] else bg["team_b"]
    return gold, silver, bronze


# edition_results[(tournament, season)] = {1:gold,2:silver,3:bronze}, all codes
edition_results = {}
medal_counts = {}  # code -> {"gold","silver","bronze"}
mgames = games[games["tournament"].isin(MEDAL_TOURNAMENTS)].copy()
for (tour, season), grp in mgames.groupby(["tournament", "season"]):
    gold, silver, bronze = edition_medals(grp)
    if gold is None:
        continue
    edition_results[(tour, int(season))] = {1: gold, 2: silver, 3: bronze}
    for code, m in ((gold, "gold"), (silver, "silver"), (bronze, "bronze")):
        if code:
            medal_counts.setdefault(code, {"gold": 0, "silver": 0, "bronze": 0})
            medal_counts[code][m] += 1

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


# ── medals.json: per-country aggregated counts for the Medals tab ────────────
print("Writing medals.json...")
medal_rows = []
for code, m in medal_counts.items():
    medal_rows.append({
        "code": code,
        "team": name_for(code),
        "flag": flag(code),
        "confederation": confed_for(code),
        "gold": m["gold"], "silver": m["silver"], "bronze": m["bronze"],
        "total": m["gold"] + m["silver"] + m["bronze"],
    })
# Sort: gold desc, silver desc, bronze desc, then name.
medal_rows.sort(key=lambda x: (-x["gold"], -x["silver"], -x["bronze"], x["team"]))
with open(f"{DATA_DIR}/medals.json", "w") as f:
    json.dump(medal_rows, f, separators=(",", ":"), ensure_ascii=False)
print(f"  medals.json: {len(medal_rows)} countries with podiums")


# ============================================================
# TOURNAMENT FINAL DATES (per tournament+year) — labels, GOAT + year anchors
# ============================================================
tournament_final_date = {}  # (tournament, year) -> final date
for tour in MEDAL_TOURNAMENTS:
    tg = games[games["tournament"] == tour]
    if tg.empty:
        continue
    for year, grp in tg.groupby("season"):
        tournament_final_date[(tour, int(year))] = grp["date"].max()

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


def team_row(r, slim=False):
    out = {
        "rank":                int(r["rank"]) if not pd.isna(r["rank"]) else None,
        "team":                r["country"],
        "flag":                flag(r["code"]),
        "confederation":       clean(r["confederation"]),
        "rating":              round3(r["rating"]),
        "record":              record_str(r["code"]),
        "last_match":          clean(r["last_game"]),
        "last_match_date":     clean(r["last_game_date"]),
        "tournament_finishes": finishes_for(r["code"], r["season"]),
        "continental_winner":  1 if (r["code"], int(r["season"])) in continental_winners else 0,
    }
    return out


for season in all_seasons:
    sdf = df[(df["season"] == season) & df["eligible"]]
    snapshots = []
    for ranking_id, rdf in sdf.groupby("ranking_id"):
        rdf = rdf.sort_values("rank")
        snap_date = str(rdf["date"].iloc[0])
        label, prestige = date_label_map.get(snap_date, (None, None))
        snapshots.append({
            "date": snap_date, "label": label, "prestige": prestige,
            "teams": [team_row(r) for _, r in rdf.iterrows()],
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
latest_date = str(latest["date"].iloc[0]) if len(latest) else seasons_meta["last_date"]
standings = []
for _, r in latest.iterrows():
    row = team_row(r)
    row["games_played"] = int(r["games_in_window"]) if not pd.isna(r["games_in_window"]) else 0
    rec = records.get(r["code"], {"w": 0, "l": 0})
    row["record"] = f"{rec['w']}-{rec['l']}"
    standings.append(row)
with open(f"{DATA_DIR}/current_standings.json", "w") as f:
    json.dump({"updated": latest_date, "teams": standings},
              f, separators=(",", ":"), ensure_ascii=False)
print(f"  current_standings.json: {len(standings)} teams as of {latest_date}")


# ============================================================
# 3) GOAT TABLE — top-50 single-snapshot ratings at tournament finals
# ============================================================
print("Writing goat_teams.json...")
# Eligibility: medaled (1st/2nd/3rd) in a major tournament that year. Anchor the
# rating at THAT tournament's final date. Mirrors MESSI's GOAT logic.
eligible_podiums = []  # (code, year, tournament)
for (tour, season), res in edition_results.items():
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
    goat_data.append({
        "rank":                i + 1,
        "team":                name_for(r["code"]),
        "flag":                flag(r["code"]),
        "confederation":       clean(r["confederation"]),
        "season":              int(r["year"]),
        "rating":              round3(r["rating"]),
        "tournament_finishes": finishes_for(r["code"], r["year"]),
        "continental_winner":  1 if (r["code"], int(r["year"])) in continental_winners else 0,
    })
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
    teams_index.append({"name": name, "flag": fl, "confederation": confed, "slug": team_slug})

    seasons = {}
    for season, sdf in tdf.groupby("season"):
        if pd.isna(season):
            continue
        if (code, int(season)) not in played_team_years:
            continue
        fin = finishes_for(code, season)
        won_cont = (code, int(season)) in continental_winners
        seasons[int(season)] = [
            {
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
            for _, r in sdf.sort_values("date").iterrows()
        ]

    with open(f"{DATA_DIR}/teams/{team_slug}.json", "w") as f:
        json.dump({"team": name, "flag": fl, "confederation": confed, "seasons": seasons},
                  f, separators=(",", ":"), ensure_ascii=False)

teams_index.sort(key=lambda x: x["name"])
with open(f"{DATA_DIR}/teams_index.json", "w") as f:
    json.dump(teams_index, f, separators=(",", ":"), ensure_ascii=False)
print(f"  teams_index.json + {len(teams_index)} team files")


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
