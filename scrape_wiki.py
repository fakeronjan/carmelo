# ============================================================
# CARMELO - International basketball scraper
# Parses {{basketballbox}} game templates from Wikipedia tournament pages.
#
# Page structure varies by event. A single event's games can live in any of:
#   1. {{basketballbox}} blocks directly on the main event page
#      (e.g. FIBA Asia Cup, AfroBasket).
#   2. {{:Sub Page}} transclusions of group/knockout sub-pages
#      (e.g. FIBA World Cup groups, EuroBasket groups + knockout stage).
#   3. {{Template:... game N}} / {{... Gold Medal}} per-game template
#      transclusions in the Template: namespace (e.g. WC knockout rounds,
#      EuroBasket "knockout stage matches").
#   4. [[Sub Page]] wikilinks (older / continental sub-pages).
# This scraper follows ALL of these recursively (one level deep is enough in
# practice; a transcluded sub-page rarely transcludes a further sub-page).
#
# Team identity in a {{basketballbox}} cell appears as one of:
#   {{bk|USA}}  {{bk-rt|USA}}  {{bk-rb|USA}}      -> 3-letter FIBA/IOC code
#   {{flagdeco|USA}} {{flagicon|USA}}             -> 3-letter code
#   {{bk-rt|Germany}}  {{flag decoration|Serbia}} -> full country NAME
#   [[2024 Serbia men's Olympic basketball team|Serbia]] -> NAME via wikilink
# We normalise everything to a 3-letter code (NAME -> code via NAME_TO_CODE).
# ============================================================
import re
import sys
import time
import requests
import pandas as pd
from datetime import datetime

from countries import NAME_TO_CODE, resolve_nation  # name->code + year-aware nation lineage

WIKI_RAW = "https://en.wikipedia.org/w/index.php?title={title}&action=raw"
HEADERS = {"User-Agent": "carmelo-ratings/1.0 (international basketball ratings; contact via github.com/fakeronjan)"}


def fetch_wikitext(title, max_retries=3):
    """Fetch raw wikitext for a Wikipedia page title. Returns '' on failure
    (NEVER raises) so a flaky fetch degrades to 'no new games' rather than
    crashing the run — the append-only union downstream protects history."""
    url = WIKI_RAW.format(title=requests.utils.quote(title.replace(" ", "_")))
    for attempt in range(max_retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 404:
                return ""
            r.raise_for_status()
            time.sleep(0.25)
            return r.text
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"  [warn] fetch failed for {title!r}: {e}")
                return ""
            time.sleep(2 ** attempt)
    return ""


def _balanced_blocks(text, opener="{{basketballbox"):
    """Yield each {{basketballbox ... }} block with balanced braces.
    Case-insensitive on the opener ({{Basketballbox is also used).

    Opener positions are located with a case-insensitive regex on the ORIGINAL
    text (NOT text.lower()): str.lower() can CHANGE string length for some
    Unicode code points (e.g. Turkish 'İ' -> 'i̇' is two code points), which
    would shift every offset and make the brace scanner index the wrong region
    — silently truncating blocks on pages that contain such characters. Old
    EuroBasket/World-Championship pages (Turkish player names) tripped this.
    """
    op_re = re.compile(re.escape(opener), re.IGNORECASE)
    i = 0
    while True:
        m = op_re.search(text, i)
        if not m:
            return
        start = m.start()
        depth = 0
        j = start
        while j < len(text):
            if text[j:j+2] == "{{":
                depth += 1; j += 2
            elif text[j:j+2] == "}}":
                depth -= 1; j += 2
                if depth == 0:
                    yield text[start:j]
                    break
            else:
                j += 1
        else:
            return
        i = j


# Team-identity extraction, in priority order.
#   1. {{bk|CODE}} / {{bk-rt|CODE}} / {{bk-rb|CODE}} where CODE is 2-4 letters.
#   2. {{flagdeco|CODE}} / {{flagicon|CODE}} / {{flagu|CODE}} with 2-4 letters.
# Both #1 and #2 also accept a full country NAME as the argument; we detect
# that (argument longer than 4 chars or not all-caps) and map via NAME_TO_CODE.
#   3. wikilink "[[... men's ... basketball team|Country]]" -> Country -> code.
_BK_RE = re.compile(r"\{\{\s*bk(?:-rt|-rb)?\s*\|\s*([^}|\]\n]+?)\s*(?:\||\}\}|$)", re.IGNORECASE)
# Flag templates: {{flagdeco|X}} {{flagicon|X}} {{flagu|X}} {{flag country|X}}
# and the Olympic-roster variant {{flagIOC|X|YEAR Summer Olympics}} /
# {{flagIOC-rt|X|...}} used on 1936-1948 Olympic basketball pages. The right/
# bottom suffixes (-rt/-rb) are tolerated. X is the country CODE or NAME.
_FLAG_RE = re.compile(
    r"\{\{\s*flag\s*(?:deco|decoration|icon|u|country|ioc)?(?:-rt|-rb)?\s*\|\s*([^}|\]\n]+?)\s*(?:\||\}\}|$)",
    re.IGNORECASE)
_WIKILINK_RE = re.compile(r"\[\[[^\]|]*\|\s*([^\]|]+?)\s*\]\]")


def _arg_to_code(arg):
    """Resolve a {{bk|...}} / {{flagdeco|...}} argument to a 3-letter code.
    Accepts either a code (USA) or a country name (United States / Germany)."""
    arg = arg.strip().strip("'").strip()
    if not arg:
        return None
    # Pure 2-4 letter token that is all uppercase -> treat as code.
    if re.fullmatch(r"[A-Za-z]{2,4}", arg) and arg.upper() == arg:
        return arg.upper()
    # Otherwise treat as a country name.
    code = NAME_TO_CODE.get(arg)
    if code:
        return code
    # Some args are codes given in mixed case (rare) — accept if 2-4 letters.
    if re.fullmatch(r"[A-Za-z]{2,4}", arg):
        return arg.upper()
    return None


# "IOC" is the International Olympic Committee placeholder flag, used for teams
# competing under the Olympic flag rather than a national one (e.g. several
# nations at the 1980 Moscow boycott, the 1992 Unified Team). It is NOT a
# nation. The real identity comes from the cell's [[... national basketball
# team|Display]] wikilink (1992 -> "Unified Team" -> URS -> Russia; 1980 ->
# "Italy"). When NO wikilink disambiguates the cell (some 1980 boxes carry only
# a bare {{flagicon|IOC}} with the team buried in player stats), the team is
# unidentifiable, so the game is DROPPED rather than mis-attributed to a wrong
# nation — never publish "IOC" as if it were a country.
_PLACEHOLDER_CODES = {"IOC"}


def _team_code(raw):
    """Extract a 3-letter team code from a teamA/teamB cell. Tries bk template,
    then flag template, then a wikilinked country name.

    A bk/flag code that is a non-national placeholder (IOC) is held back; the
    wikilinked country name is preferred. If only the placeholder resolves, it
    is returned (so resolve_nation can map the 1992 Unified Team -> Russia);
    years where IOC is NOT a single identifiable nation are dropped downstream
    in parse_basketballboxes."""
    placeholder = None
    m = _BK_RE.search(raw)
    if m:
        code = _arg_to_code(m.group(1))
        if code and code not in _PLACEHOLDER_CODES:
            return code
        if code in _PLACEHOLDER_CODES:
            placeholder = code
    m = _FLAG_RE.search(raw)
    if m:
        code = _arg_to_code(m.group(1))
        if code and code not in _PLACEHOLDER_CODES:
            return code
        if code in _PLACEHOLDER_CODES:
            placeholder = code
    for m in _WIKILINK_RE.finditer(raw):
        code = NAME_TO_CODE.get(m.group(1).strip())
        if code:
            return code
    return placeholder


def _field(block, key):
    """Extract |key=value from a template block (value up to next |field or end)."""
    m = re.search(rf"\|\s*{key}\s*=\s*(.*?)(?=\n\s*\||\}}\}})", block, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ""


def _score(raw):
    m = re.search(r"\d+", raw.replace("'''", ""))
    return int(m.group(0)) if m else None


_MONTHS = {m.lower(): i for i, m in enumerate(
    ["", "January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"]) if m}
_MONTHS.update({m[:3].lower(): i for m, i in list(_MONTHS.items())})


def _parse_date(date_raw, season=None):
    """Parse a {{basketballbox}} date field. Handles '10 September 2023',
    'September 10, 2023', ISO '2014-09-14', and the {{dts}} date-sorting
    template '{{dts|...|2014|9|14}}' / '{{dts|2014|September|14}}' (positional
    year|month|day after any named args). Returns a date or None.

    season: the edition year (as int or str). OLD tournament pages (pre-2000s)
    write the date WITHOUT a year, e.g. '|date=5 July', because the year is
    implicit (the edition's). When the date string carries no 4-digit year, the
    season year is attached so these games are no longer silently dropped.
    Verified: '5 July' + season 1986 -> 1986-07-05."""
    from datetime import date as _date

    # season year as int, if usable.
    season_year = None
    if season is not None:
        try:
            season_year = int(str(season).strip()[:4])
        except (ValueError, TypeError):
            season_year = None

    # Date-template handling: {{dts|...|Y|M|D}}, {{Start date|Y|M|D|df=yes}},
    # {{End date|...}} — extract the positional Y|M|D (skipping named args like
    # df=yes/format=/link=). No closing-brace required since _field can truncate
    # the value at the template's inner }}.
    mdts = re.search(r"\{\{\s*(?:dts|start[\s_]?date|end[\s_]?date)\b([^}]*)",
                     date_raw, re.IGNORECASE)
    if mdts:
        toks = [t.strip() for t in mdts.group(1).split("|") if t.strip() and "=" not in t]
        if len(toks) >= 3:
            try:
                yr = int(toks[0])
                mo = int(toks[1]) if toks[1].isdigit() else _MONTHS.get(toks[1].lower())
                day = int(toks[2])
                if mo:
                    return _date(yr, mo, day)
            except (ValueError, TypeError):
                pass
    # Strip single-bracket external links ([http...] report links) BEFORE other
    # cleanup: their URLs embed digit runs (archive timestamps like 20120803...)
    # that otherwise look like a 4-digit year and defeat the year-less fallback.
    s = re.sub(r"\[https?://[^\]]*\]", "", date_raw)
    s = re.sub(r"\{\{[^}]*\}\}|\[\[|\]\]", "", s).strip()
    # ISO YYYY-MM-DD
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return _date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    for fmt in ("%d %B %Y", "%B %d, %Y", "%d %b %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    # Relaxed leading-date match: "<day> <Month> <Year>"
    m = re.match(r"(\d{1,2}\s+[A-Za-z]+\s+\d{4})", s)
    if m:
        try:
            return datetime.strptime(m.group(1), "%d %B %Y").date()
        except ValueError:
            pass

    # YEAR-LESS old-page dates: attach the season's year. Try both day-first
    # ('5 July') and month-first ('July 5') with the edition year appended.
    if season_year is not None and not re.search(r"\d{4}", s):
        for fmt in ("%d %B %Y", "%B %d %Y", "%d %b %Y", "%b %d %Y"):
            try:
                return datetime.strptime(f"{s} {season_year}", fmt).date()
            except ValueError:
                continue
        # Relaxed leading "<day> <Month>" or "<Month> <day>" prefix.
        m = re.match(r"(\d{1,2}\s+[A-Za-z]+)", s)
        if m:
            for fmt in ("%d %B %Y", "%d %b %Y"):
                try:
                    return datetime.strptime(f"{m.group(1)} {season_year}", fmt).date()
                except ValueError:
                    continue
        m = re.match(r"([A-Za-z]+\s+\d{1,2})", s)
        if m:
            for fmt in ("%B %d %Y", "%b %d %Y"):
                try:
                    return datetime.strptime(f"{m.group(1)} {season_year}", fmt).date()
                except ValueError:
                    continue
    return None


def parse_basketballboxes(wikitext, tournament, season):
    """Yield dict rows: date, team_a (code), score_a, team_b (code), score_b."""
    rows = []
    # Year used for defunct-nation resolution. Prefer the parsed game date's
    # year (handles editions spanning a year boundary); fall back to the
    # edition season. resolve_nation is keyed on the GAME year, NOT any flag
    # year-suffix the cell may carry ({{bk|YUG|1998}}).
    # Deterministic season-fallback date for boxes that carry teams + scores but
    # an EMPTY/unparseable date field (some old Olympic pages, e.g. 1964, write
    # |date= with no value). Without this the entire edition is dropped. We stamp
    # the games with a fixed day in the edition year so they still count toward
    # ratings and land in the correct season. NOTE: this collapses an edition's
    # games onto fewer game-days, which is acceptable for the WLS window but can
    # blur medal-final detection for that specific edition (flagged in report).
    from datetime import date as _date
    season_fallback = None
    try:
        _sy = int(str(season).strip()[:4])
        season_fallback = _date(_sy, 8, 1)  # Aug 1: typical Olympic/summer-event window
    except (ValueError, TypeError):
        season_fallback = None

    for block in _balanced_blocks(wikitext):
        date = _parse_date(_field(block, "date"), season)
        ta = _team_code(_field(block, "teamA"))
        tb = _team_code(_field(block, "teamB"))
        sa = _score(_field(block, "scoreA"))
        sb = _score(_field(block, "scoreB"))
        if date is None and season_fallback is not None:
            date = season_fallback
        if not (ta and tb and sa is not None and sb is not None and date is not None):
            continue
        game_year = date.year if date is not None else season
        ta, _ = resolve_nation(ta, game_year)
        tb, _ = resolve_nation(tb, game_year)
        # Drop games whose team is still an unresolved Olympic-flag placeholder
        # (IOC outside 1992): the nation is unidentifiable and must not be
        # published as a fake country.
        if ta in ("IOC", "EUN") or tb in ("IOC", "EUN"):
            continue
        if ta == tb:
            continue
        rows.append({
            "date": date, "tournament": tournament, "season": season,
            "team_a": ta, "score_a": sa, "team_b": tb, "score_b": sb,
        })
    return rows


def discover_pages(main_title, wikitext, template_prefix=None):
    """Enumerate every page that may hold {{basketballbox}} games for an event:
      - [[<main_title> <suffix>]] wikilink sub-pages
      - {{:<Page>}} transclusions (group/knockout sub-pages)
      - {{<Template page>}} per-game / medal / match template transclusions
        whose name starts with the event title (fetched from Template: ns)
    Returns a list of (title, is_template) tuples to fetch.

    template_prefix: when set, per-game templates are matched against this
        prefix instead of main_title. Needed when recursing into a sub-page
        (e.g. '... final round') whose per-game templates are named after the
        ROOT event ('2014 FIBA Basketball World Cup Gold Medal'), not the
        sub-page.
    """
    pages = []  # (title, is_template)
    seen = set()
    tmpl_prefix = template_prefix or main_title

    def add(title, is_template):
        key = (title, is_template)
        if title and key not in seen:
            seen.add(key)
            pages.append((title, is_template))

    base = re.escape(main_title)

    # 1. [[main_title <suffix>]] wikilinks (group/round/final sub-pages).
    for m in re.finditer(rf"\[\[({base}[^\]|#]*)", wikitext):
        add(m.group(1).strip(), False)

    # 2. {{:Page}} transclusions of full sub-pages.
    for m in re.finditer(r"\{\{:\s*([^}|#]+)", wikitext):
        add(m.group(1).strip(), False)

    # 3. {{Template ...}} per-game/medal/match templates that start with the
    #    event title (or template_prefix). Each transcludes a basketballbox.
    for m in re.finditer(r"\{\{\s*([^}|:#][^}|#]*?)\s*(?:\||\}\})", wikitext):
        name = m.group(1).strip()
        if name.startswith(tmpl_prefix) and name != tmpl_prefix and name != main_title:
            add(name, True)

    return pages


# Sub-pages whose titles contain any of these substrings are NOT followed when
# scraping a finals event — they are separate events (qualifiers) that the
# driver scrapes on their own with their own tournament tag / tier / neutral
# flag. Without this, a World Cup finals page would pull in ~300 qualifier
# games and mis-tag them as neutral top-tier finals games.
_SKIP_SUBPAGE_SUBSTR = ("qualif", "Qualif", "pre-qualif", "Pre-Qualif")


def _should_follow(title, follow_qualifiers):
    if follow_qualifiers:
        return True
    return not any(s.lower() in title.lower() for s in ("qualif",))


def scrape_event(main_title, tournament, season, neutral=True,
                 follow_qualifiers=False, _depth=0):
    """Scrape an event: main page + discovered sub-pages and per-game
    templates. Recurses ONE extra level into discovered sub-pages so that a
    'knockout stage' page that itself references per-game templates is fully
    captured.

    neutral: tournament-wide venue flag stamped on every game row (True for
        finals events at a single neutral host; False for home-and-away
        qualifiers). The driver sets this per event.
    follow_qualifiers: when False (default for finals events) sub-pages whose
        title mentions 'qualification' are skipped — they are scraped as their
        own events. Set True when scraping a qualification event directly.
    """
    main_wt = fetch_wikitext(main_title)
    if not main_wt:
        if _depth == 0:
            print(f"  [warn] no wikitext for event {main_title!r}")
        return pd.DataFrame()

    all_rows = []
    all_rows.extend(parse_basketballboxes(main_wt, tournament, season))

    pages = [(t, tmpl) for (t, tmpl) in discover_pages(main_title, main_wt)
             if _should_follow(t, follow_qualifiers)]
    subpage_wts = {}
    for title, is_template in pages:
        fetch_title = f"Template:{title}" if is_template else title
        wt = fetch_wikitext(fetch_title)
        subpage_wts[(title, is_template)] = wt
        rows = parse_basketballboxes(wt, tournament, season)
        if rows:
            print(f"    {fetch_title}: {len(rows)} games")
        all_rows.extend(rows)

    # One level of recursion: a discovered (non-template) sub-page may itself
    # reference per-game templates or further transclusions (e.g. EuroBasket
    # 'knockout stage' -> 'knockout stage matches' template).
    if _depth == 0:
        for (title, is_template), wt in list(subpage_wts.items()):
            if is_template or not wt:
                continue
            for sub_title, sub_is_tmpl in discover_pages(title, wt, template_prefix=main_title):
                if not _should_follow(sub_title, follow_qualifiers):
                    continue
                ft = f"Template:{sub_title}" if sub_is_tmpl else sub_title
                if (sub_title, sub_is_tmpl) in subpage_wts:
                    continue
                sub_wt = fetch_wikitext(ft)
                subpage_wts[(sub_title, sub_is_tmpl)] = sub_wt
                rows = parse_basketballboxes(sub_wt, tournament, season)
                if rows:
                    print(f"    {ft}: {len(rows)} games (L2)")
                all_rows.extend(rows)

    df = pd.DataFrame(all_rows)
    if len(df):
        df = df.drop_duplicates(subset=["date", "team_a", "team_b", "score_a", "score_b"])
        df["neutral"] = neutral
    return df


if __name__ == "__main__":
    # Proof: FIBA World Cup 2023 + Olympics 2024
    for title, tour, season in [
        ("2023 FIBA Basketball World Cup", "FIBA World Cup", "2023"),
        ("Basketball at the 2024 Summer Olympics – Men's tournament", "Olympics", "2024"),
    ]:
        df = scrape_event(title, tour, season)
        print(f"\n=== {title}: {len(df)} games extracted ===")
        if len(df):
            print(f"distinct teams: {sorted(set(df['team_a']) | set(df['team_b']))}\n")
