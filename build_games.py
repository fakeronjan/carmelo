# ============================================================
# CARMELO - games-database builder
# Enumerates international men's basketball events, scrapes each via
# scrape_wiki.scrape_event, tags tournament / tier / neutral, and unions the
# result into the append-only games database all_games.csv.
#
# Run:  python3 build_games.py            # modern events (default)
#       python3 build_games.py --all      # modern + historical backfill
# ============================================================
import sys
import os
import pandas as pd

from scrape_wiki import scrape_event

# ------------------------------------------------------------
# TIER WEIGHTS (WLS observation-weight uplift). Borrowed from MESSI's
# tier_weight concept. Documented values — flag for tuning.
#   Olympics + FIBA World Cup        = top tier   1.0
#   Continental championships        = mid tier   0.7
#   World Cup qualifiers             = lower tier  0.5
# These multiply the recency weight in the WLS solve; they encode "this game
# is a more reliable signal of senior-team strength", not margin magnitude.
# ------------------------------------------------------------
TIER_WEIGHTS = {
    "Olympics":         1.0,
    "FIBA World Cup":   1.0,
    "EuroBasket":       0.7,
    "FIBA AmeriCup":    0.7,
    "FIBA Asia Cup":    0.7,
    "FIBA AfroBasket":  0.7,
    "WC Qualifiers":    0.5,
}

# neutral flag per tournament family: True everywhere EXCEPT WC qualifiers,
# which are played home-and-away.
NEUTRAL = {t: True for t in TIER_WEIGHTS}
NEUTRAL["WC Qualifiers"] = False


# ------------------------------------------------------------
# EVENT TABLES. Each entry: (wiki_title, tournament_family, season).
# Titles verified against Wikipedia raw wikitext.
# ------------------------------------------------------------

def _oly(year):
    return (f"Basketball at the {year} Summer Olympics – Men's tournament", "Olympics", str(year))


# Olympics: title scheme stable back to 2004 (en-dash). 1992-2000 use a
# slightly different layout but the same page-title scheme; included in --all.
OLYMPICS_MODERN = [_oly(y) for y in (2024, 2020, 2016, 2012, 2008)]
OLYMPICS_HIST   = [_oly(y) for y in (2004, 2000, 1996, 1992)]

# FIBA World Cup (2014+) / FIBA World Championship (<=2010).
WORLDCUP_MODERN = [
    ("2023 FIBA Basketball World Cup", "FIBA World Cup", "2023"),
    ("2019 FIBA Basketball World Cup", "FIBA World Cup", "2019"),
    ("2014 FIBA Basketball World Cup", "FIBA World Cup", "2014"),
    ("2010 FIBA World Championship",   "FIBA World Cup", "2010"),
    ("2006 FIBA World Championship",   "FIBA World Cup", "2006"),
]
WORLDCUP_HIST = [
    ("2002 FIBA World Championship", "FIBA World Cup", "2002"),
    ("1998 FIBA World Championship", "FIBA World Cup", "1998"),
    ("1994 FIBA World Championship", "FIBA World Cup", "1994"),
    ("1990 FIBA World Championship", "FIBA World Cup", "1990"),
    ("1986 FIBA World Championship", "FIBA World Cup", "1986"),
]

# Continental championships (modern editions, ~last 20 years).
EUROBASKET_MODERN = [
    (f"EuroBasket {y}", "EuroBasket", str(y)) for y in (2025, 2022, 2017, 2015, 2013, 2011, 2009, 2007, 2005)
]
AMERICUP_MODERN = [
    ("2025 FIBA AmeriCup", "FIBA AmeriCup", "2025"),
    ("2022 FIBA AmeriCup", "FIBA AmeriCup", "2022"),
    ("2017 FIBA AmeriCup", "FIBA AmeriCup", "2017"),
    ("2015 FIBA Americas Championship", "FIBA AmeriCup", "2015"),
    ("2013 FIBA Americas Championship", "FIBA AmeriCup", "2013"),
    ("2011 FIBA Americas Championship", "FIBA AmeriCup", "2011"),
    ("2009 FIBA Americas Championship", "FIBA AmeriCup", "2009"),
    ("2007 FIBA Americas Championship", "FIBA AmeriCup", "2007"),
]
ASIACUP_MODERN = [
    ("2025 FIBA Asia Cup", "FIBA Asia Cup", "2025"),
    ("2022 FIBA Asia Cup", "FIBA Asia Cup", "2022"),
    ("2017 FIBA Asia Cup", "FIBA Asia Cup", "2017"),
    ("2015 FIBA Asia Championship", "FIBA Asia Cup", "2015"),
    ("2013 FIBA Asia Championship", "FIBA Asia Cup", "2013"),
    ("2011 FIBA Asia Championship", "FIBA Asia Cup", "2011"),
    ("2009 FIBA Asia Championship", "FIBA Asia Cup", "2009"),
    ("2007 FIBA Asia Championship", "FIBA Asia Cup", "2007"),
]
AFROBASKET_MODERN = [
    ("FIBA AfroBasket 2025", "FIBA AfroBasket", "2025"),
    ("FIBA AfroBasket 2021", "FIBA AfroBasket", "2021"),
    ("AfroBasket 2017", "FIBA AfroBasket", "2017"),
    ("AfroBasket 2015", "FIBA AfroBasket", "2015"),
    ("AfroBasket 2013", "FIBA AfroBasket", "2013"),
    ("AfroBasket 2011", "FIBA AfroBasket", "2011"),
    ("AfroBasket 2009", "FIBA AfroBasket", "2009"),
    ("2007 FIBA Africa Championship", "FIBA AfroBasket", "2007"),
]

# World Cup qualifiers (home-and-away, non-neutral). 2023 + 2019 cycles, four
# FIBA zones each. These are the only non-neutral events.
WC_QUALIFIERS = [
    ("2023 FIBA Basketball World Cup qualification (Africa)",   "WC Qualifiers", "2023"),
    ("2023 FIBA Basketball World Cup qualification (Americas)", "WC Qualifiers", "2023"),
    ("2023 FIBA Basketball World Cup qualification (Asia)",     "WC Qualifiers", "2023"),
    ("2023 FIBA Basketball World Cup qualification (Europe)",   "WC Qualifiers", "2023"),
    ("2019 FIBA Basketball World Cup qualification (Africa)",   "WC Qualifiers", "2019"),
    ("2019 FIBA Basketball World Cup qualification (Americas)", "WC Qualifiers", "2019"),
    ("2019 FIBA Basketball World Cup qualification (Asia)",     "WC Qualifiers", "2019"),
    ("2019 FIBA Basketball World Cup qualification (Europe)",   "WC Qualifiers", "2019"),
]


def modern_events():
    return (OLYMPICS_MODERN + WORLDCUP_MODERN + EUROBASKET_MODERN +
            AMERICUP_MODERN + ASIACUP_MODERN + AFROBASKET_MODERN + WC_QUALIFIERS)


def historical_events():
    return OLYMPICS_HIST + WORLDCUP_HIST


def union_with_existing(fresh_df, path="all_games.csv"):
    """Treat the committed games file as the persistent database: a run may ADD
    new games or CORRECT existing ones, but must never DELETE games we already
    have just because this run's scrape came back short. (Cloned from COBI's
    union_with_existing — Wikipedia raw fetches can flake / 404 transiently.)
    Fresh rows win for games present in both (so score corrections land);
    DB-only games are preserved."""
    if not os.path.exists(path):
        return fresh_df
    prev_df = pd.read_csv(path)
    key = ["date", "team_a", "team_b"]
    fresh = fresh_df.copy(); fresh["_src_priority"] = 0   # fresh wins on conflict
    prev = prev_df.copy();   prev["_src_priority"] = 1
    combined = pd.concat([fresh, prev], ignore_index=True, sort=False)
    combined = combined.sort_values("_src_priority").drop_duplicates(subset=key, keep="first")
    combined = combined.drop(columns=["_src_priority"]).reset_index(drop=True)
    fresh_keys = set(map(tuple, fresh_df[key].astype(str).values))
    preserved = sum(1 for k in map(tuple, prev_df[key].astype(str).values) if k not in fresh_keys)
    if preserved:
        print(f"[db-union] preserved {preserved:,} games already in the database "
              f"that this run's scrape did not return (flaky source — not deleting history)")
    return combined


def build(events, out_path="all_games.csv"):
    frames = []
    for title, family, season in events:
        neutral = NEUTRAL[family]
        follow_q = (family == "WC Qualifiers")
        print(f"\n>>> {title}  [{family}, {season}, neutral={neutral}]")
        df = scrape_event(title, family, season, neutral=neutral, follow_qualifiers=follow_q)
        if len(df):
            df["tier"] = TIER_WEIGHTS[family]
            print(f"    -> {len(df)} games")
            frames.append(df)
        else:
            print("    -> 0 games (page missing or unparsed)")

    if not frames:
        print("No games scraped this run.")
        # still run the union so an empty scrape never wipes the DB
        if os.path.exists(out_path):
            print("Existing DB left intact.")
        return pd.DataFrame()

    fresh = pd.concat(frames, ignore_index=True, sort=False)
    # Within this run, a game can appear under two events (shouldn't, but guard).
    fresh = fresh.drop_duplicates(subset=["date", "team_a", "team_b"], keep="first")

    merged = union_with_existing(fresh, out_path)
    merged = merged.sort_values(["date", "team_a", "team_b"]).reset_index(drop=True)
    merged.to_csv(out_path, index=False)
    print(f"\n=== all_games.csv: {len(merged):,} games total ===")
    print(merged.groupby("tournament").size().to_string())
    return merged


if __name__ == "__main__":
    events = modern_events()
    if "--all" in sys.argv:
        events = events + historical_events()
    build(events)
