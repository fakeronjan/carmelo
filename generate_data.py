"""
generate_data.py — reads carmelo_ratings.csv + all_games.csv and writes the
JSON the CARMELO web frontend consumes. Run after carmelo.py.

Outputs (docs/data/):
  current_rankings.json   most-recent snapshot leaderboard (min-games filtered)
  medals.json             per-edition gold/silver/bronze for each tournament
  peak_teams.json         GOAT-style list: each team's single highest-rated
                          snapshot (peak rating), filtered to eligible teams
  meta.json               coverage dates, game count, params

Medal logic mirrors soccer international/messi.py's podium walk: for each
edition, the GOLD game is the final (last game date), silver = its loser,
bronze = winner of the 3rd-place game on the prior game date among
non-finalists. Qualifiers have no medals.
"""
import os
import json
import pandas as pd
import numpy as np
from datetime import datetime, timezone

from countries import CODE_TO_NAME, CONFEDERATION

DATA_DIR = "docs/data"
os.makedirs(DATA_DIR, exist_ok=True)

MIN_GAMES = 4  # eligibility for displayed leaderboard / peak list

# Tournaments that crown a champion (qualifiers excluded).
MEDAL_TOURNAMENTS = ["Olympics", "FIBA World Cup", "EuroBasket",
                     "FIBA AmeriCup", "FIBA Asia Cup", "FIBA AfroBasket"]

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
    "BOT": "BW", "GBS": "GW",
}


def flag(code):
    iso = CODE_TO_ISO2.get(code)
    if not iso or len(iso) != 2:
        return ""
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in iso.upper())


def name_for(code):
    return CODE_TO_NAME.get(code, code)


def round3(x):
    try:
        return round(float(x), 3)
    except (TypeError, ValueError):
        return None


# ============================================================
# LOAD
# ============================================================
print("Reading ratings + games...")
ratings = pd.read_csv("carmelo_ratings.csv")
ratings["date"] = pd.to_datetime(ratings["date"]).dt.date

games = pd.read_csv("all_games.csv")
games["date"] = pd.to_datetime(games["date"]).dt.date
games["score_a"] = pd.to_numeric(games["score_a"], errors="coerce")
games["score_b"] = pd.to_numeric(games["score_b"], errors="coerce")
games = games.dropna(subset=["score_a", "score_b"])


# ============================================================
# CURRENT RANKINGS (most recent snapshot)
# ============================================================
latest_id = ratings["ranking_id"].max()
snap = ratings[ratings["ranking_id"] == latest_id].copy()
snap = snap[snap["games_in_window"] >= MIN_GAMES]
snap = snap.sort_values("rating", ascending=False).reset_index(drop=True)
snap["rank"] = snap.index + 1

current_date = str(ratings.loc[ratings["ranking_id"] == latest_id, "date"].iloc[0])

current = []
for _, r in snap.iterrows():
    current.append({
        "rank": int(r["rank"]),
        "code": r["code"],
        "team": name_for(r["code"]),
        "flag": flag(r["code"]),
        "confederation": CONFEDERATION.get(r["code"], "Other"),
        "rating": round3(r["rating"]),
        "games_in_window": int(r["games_in_window"]),
        "last_game": "" if pd.isna(r.get("last_game")) else str(r.get("last_game", "")),
        "last_game_date": "" if pd.isna(r.get("last_game_date")) else str(r.get("last_game_date")),
    })

with open(f"{DATA_DIR}/current_rankings.json", "w") as f:
    json.dump({"updated": current_date, "teams": current}, f, ensure_ascii=False)
print(f"current_rankings.json: {len(current)} teams as of {current_date}")


# ============================================================
# MEDALS (per edition gold/silver/bronze)
# ============================================================
def edition_medals(grp):
    """Return (gold, silver, bronze codes) for one tournament edition."""
    grp = grp.sort_values("date")
    last_date = grp["date"].max()
    final_games = grp[grp["date"] == last_date]
    if final_games.empty:
        return None, None, None
    # Gold game = the final. When multiple games share the last date (final +
    # bronze same day), the final is the one between the two semifinal winners.
    finalists_set = None
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

    for cand in reversed(list(final_games.itertuples(index=False))):
        ah = won_prev(cand.team_a)
        bh = won_prev(cand.team_b)
        if ah and bh:
            final_row = cand._asdict() if hasattr(cand, "_asdict") else dict(
                zip(final_games.columns, cand))
            break

    a, b = final_row["team_a"], final_row["team_b"]
    if final_row["score_a"] > final_row["score_b"]:
        gold, silver = a, b
    else:
        gold, silver = b, a
    finalists_set = {a, b}

    # Bronze: winner of the 3rd-place game (latest pre-final date, non-finalists)
    bronze = None
    pre = grp[grp["date"] < last_date]
    if not pre.empty:
        bdate = pre["date"].max()
        bgames = pre[(pre["date"] == bdate) &
                     (~pre["team_a"].isin(finalists_set)) &
                     (~pre["team_b"].isin(finalists_set))]
        if not bgames.empty:
            bg = bgames.iloc[-1]
            bronze = bg["team_a"] if bg["score_a"] > bg["score_b"] else bg["team_b"]
    return gold, silver, bronze


medals = {}
medal_counts = {}  # code -> {"gold":n,"silver":n,"bronze":n}
mgames = games[games["tournament"].isin(MEDAL_TOURNAMENTS)].copy()
for (tour, season), grp in mgames.groupby(["tournament", "season"]):
    gold, silver, bronze = edition_medals(grp)
    if gold is None:
        continue
    medals.setdefault(tour, []).append({
        "season": int(season),
        "gold": {"code": gold, "team": name_for(gold), "flag": flag(gold)},
        "silver": ({"code": silver, "team": name_for(silver), "flag": flag(silver)}
                   if silver else None),
        "bronze": ({"code": bronze, "team": name_for(bronze), "flag": flag(bronze)}
                   if bronze else None),
    })
    for code, m in ((gold, "gold"), (silver, "silver"), (bronze, "bronze")):
        if code:
            medal_counts.setdefault(code, {"gold": 0, "silver": 0, "bronze": 0})
            medal_counts[code][m] += 1

for tour in medals:
    medals[tour].sort(key=lambda e: -e["season"])

with open(f"{DATA_DIR}/medals.json", "w") as f:
    json.dump(medals, f, ensure_ascii=False)
n_editions = sum(len(v) for v in medals.values())
print(f"medals.json: {n_editions} editions across {len(medals)} tournaments")


# ============================================================
# PEAK TEAMS (GOAT-style): each team's highest-rated snapshot
# ============================================================
elig = ratings[ratings["games_in_window"] >= MIN_GAMES].copy()
peak_idx = elig.groupby("code")["rating"].idxmax()
peak = elig.loc[peak_idx].sort_values("rating", ascending=False).reset_index(drop=True)
peak["grank"] = peak.index + 1

peak_list = []
for _, r in peak.head(50).iterrows():
    code = r["code"]
    mc = medal_counts.get(code, {})
    peak_list.append({
        "rank": int(r["grank"]),
        "code": code,
        "team": name_for(code),
        "flag": flag(code),
        "confederation": CONFEDERATION.get(code, "Other"),
        "peak_rating": round3(r["rating"]),
        "peak_date": str(r["date"]),
        "peak_season": int(r["season"]),
        "golds": mc.get("gold", 0),
    })

with open(f"{DATA_DIR}/peak_teams.json", "w") as f:
    json.dump(peak_list, f, ensure_ascii=False)
print(f"peak_teams.json: {len(peak_list)} teams")


# ============================================================
# META
# ============================================================
meta = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "current_date": current_date,
    "first_date": str(games["date"].min()),
    "last_date": str(games["date"].max()),
    "total_games": int(len(games)),
    "n_tournaments": int(games["tournament"].nunique()),
    "tournaments": games.groupby("tournament").size().sort_values(ascending=False).to_dict(),
    "window_game_days": 150,
    "margin_cap": 25,
}
with open(f"{DATA_DIR}/meta.json", "w") as f:
    json.dump(meta, f, ensure_ascii=False)
print(f"meta.json: {meta['total_games']} games, {meta['n_tournaments']} tournaments")
print("Done.")
