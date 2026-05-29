# ============================================================
# CARMELO - FIBA/IOC 3-letter code <-> country name mappings.
#
# Wikipedia {{bk|CODE}} / {{flagdeco|CODE}} use standard IOC/FIBA 3-letter
# codes. Knockout-game templates sometimes pass the full country NAME instead
# (e.g. {{bk-rt|Germany}}); NAME_TO_CODE resolves those back to a code.
#
# CONFEDERATION map mirrors FIBA's five zones (used for filtering / display).
# ============================================================

# code -> canonical display name
CODE_TO_NAME = {
    # Europe (FIBA Europe)
    "ESP": "Spain", "SRB": "Serbia", "FRA": "France", "GRE": "Greece",
    "LTU": "Lithuania", "SLO": "Slovenia", "GER": "Germany", "ITA": "Italy",
    "CRO": "Croatia", "TUR": "Turkey", "RUS": "Russia", "URS": "Soviet Union",
    "YUG": "Yugoslavia", "SCG": "Serbia and Montenegro", "FRG": "West Germany",
    "GDR": "East Germany", "TCH": "Czechoslovakia", "CZE": "Czech Republic",
    "POL": "Poland", "FIN": "Finland", "LAT": "Latvia", "EST": "Estonia",
    "GEO": "Georgia", "UKR": "Ukraine", "MNE": "Montenegro", "BIH": "Bosnia and Herzegovina",
    "BEL": "Belgium", "NED": "Netherlands", "GBR": "Great Britain", "ENG": "England",
    "SWE": "Sweden", "NOR": "Norway", "DEN": "Denmark", "ISR": "Israel",
    "MKD": "North Macedonia", "HUN": "Hungary", "BUL": "Bulgaria", "ROU": "Romania",
    "AUT": "Austria", "SUI": "Switzerland", "POR": "Portugal", "ISL": "Iceland",
    "IRL": "Ireland", "CYP": "Cyprus", "LUX": "Luxembourg", "SVK": "Slovakia",
    "ALB": "Albania", "ARM": "Armenia", "AZE": "Azerbaijan", "BLR": "Belarus",
    "MDA": "Moldova", "KOS": "Kosovo", "MLT": "Malta", "MON": "Monaco",
    "AND": "Andorra", "SMR": "San Marino", "GIB": "Gibraltar",

    # Americas (FIBA Americas)
    "USA": "United States", "ARG": "Argentina", "BRA": "Brazil", "CAN": "Canada",
    "PUR": "Puerto Rico", "MEX": "Mexico", "VEN": "Venezuela", "DOM": "Dominican Republic",
    "URU": "Uruguay", "CHI": "Chile", "COL": "Colombia", "PAN": "Panama",
    "CUB": "Cuba", "ECU": "Ecuador", "PER": "Peru", "PAR": "Paraguay",
    "BOL": "Bolivia", "BAH": "Bahamas", "ISV": "U.S. Virgin Islands",
    "CRC": "Costa Rica", "JAM": "Jamaica", "NCA": "Nicaragua", "HON": "Honduras",
    "GUA": "Guatemala", "SLV": "El Salvador", "TTO": "Trinidad and Tobago",
    "HAI": "Haiti", "ARU": "Aruba", "ISLV": "U.S. Virgin Islands",

    # Asia + Oceania (FIBA Asia, includes Oceania since 2017)
    "AUS": "Australia", "NZL": "New Zealand", "CHN": "China", "PHI": "Philippines",
    "JPN": "Japan", "KOR": "South Korea", "PRK": "North Korea", "IRI": "Iran",
    "IRN": "Iran", "JOR": "Jordan", "LBN": "Lebanon", "SYR": "Syria",
    "QAT": "Qatar", "KSA": "Saudi Arabia", "UAE": "United Arab Emirates",
    "IRQ": "Iraq", "KAZ": "Kazakhstan", "IND": "India", "INA": "Indonesia",
    "TPE": "Chinese Taipei", "THA": "Thailand", "MAS": "Malaysia", "SIN": "Singapore",
    "VIE": "Vietnam", "HKG": "Hong Kong", "KUW": "Kuwait", "BHR": "Bahrain",
    "PLE": "Palestine", "UZB": "Uzbekistan", "MGL": "Mongolia", "SRI": "Sri Lanka",
    "BAN": "Bangladesh", "PAK": "Pakistan", "GUM": "Guam", "FIJ": "Fiji",

    # Africa (FIBA Africa)
    "ANG": "Angola", "NGR": "Nigeria", "SEN": "Senegal", "CIV": "Ivory Coast",
    "TUN": "Tunisia", "EGY": "Egypt", "CMR": "Cameroon", "MLI": "Mali",
    "CPV": "Cape Verde", "SSD": "South Sudan", "GUI": "Guinea", "MAR": "Morocco",
    "ALG": "Algeria", "RSA": "South Africa", "CGO": "Congo", "COD": "DR Congo",
    "KEN": "Kenya", "UGA": "Uganda", "MOZ": "Mozambique", "MAD": "Madagascar",
    "RWA": "Rwanda", "GHA": "Ghana", "GAB": "Gabon", "CAF": "Central African Republic",
    "CHA": "Chad", "LBA": "Libya", "BKF": "Burkina Faso", "ZAM": "Zambia",
    "ZIM": "Zimbabwe", "NAM": "Namibia", "BOT": "Botswana", "GBS": "Guinea-Bissau",
}

# name -> code (built from CODE_TO_NAME, plus common alias spellings)
NAME_TO_CODE = {v: k for k, v in CODE_TO_NAME.items()}
NAME_TO_CODE.update({
    "Iran": "IRI",
    "Côte d'Ivoire": "CIV",
    "Cote d'Ivoire": "CIV",
    "Czechia": "CZE",
    "Republic of Ireland": "IRL",
    "USA": "USA",
    "United States of America": "USA",
    "Great Britain and Northern Ireland": "GBR",
    "South Sudan": "SSD",
    "Cape Verde": "CPV",
    "Cabo Verde": "CPV",
    "Republic of the Congo": "CGO",
    "Democratic Republic of the Congo": "COD",
    "The Bahamas": "BAH",
    "Türkiye": "TUR",
    "Turkiye": "TUR",
    "U.S. Virgin Islands": "ISV",
    "United States Virgin Islands": "ISV",
    # 1992 Unified Team (post-USSR former Soviet republics) competed under the
    # Olympic flag; its Wikipedia box cells wikilink to the Soviet Union men's
    # team with display text "Unified Team". Map both to URS so resolve_nation
    # folds the 1992 edition into Russia (the USSR continuation).
    "Unified Team": "URS",
    "Soviet Union": "URS",
    "Soviet Union men's national basketball team": "URS",
    # Yugoslav-lineage names that appear in old {{bk|NAME}} cells. All map to
    # the YUG code; resolve_nation then splits by GAME year into Yugoslavia /
    # Serbia and Montenegro (e.g. "FR Yugoslavia" in 2002 -> SCG).
    "Yugoslavia": "YUG",
    "SFR Yugoslavia": "YUG",
    "FR Yugoslavia": "YUG",
    "SR Yugoslavia": "YUG",
    "Serbia and Montenegro": "SCG",
    "West Germany": "FRG",
    "East Germany": "GDR",
    "Czechoslovakia": "TCH",
})

# FIBA zone (confederation) per code. FIBA merged Asia + Oceania in 2017; we
# keep "Oceania" as a separate display label for AUS/NZL/FIJI heritage but the
# rating model treats them as one pool (zones are display-only).
CONFEDERATION = {}
_EUROPE = ["ESP","SRB","FRA","GRE","LTU","SLO","GER","ITA","CRO","TUR","RUS","URS",
    "YUG","SCG","FRG","GDR","TCH","CZE","POL","FIN","LAT","EST","GEO","UKR","MNE",
    "BIH","BEL","NED","GBR","ENG","SWE","NOR","DEN","ISR","MKD","HUN","BUL","ROU",
    "AUT","SUI","POR","ISL","IRL","CYP","LUX","SVK","ALB","ARM","AZE","BLR","MDA",
    "KOS","MLT","MON","AND","SMR","GIB"]
_AMERICAS = ["USA","ARG","BRA","CAN","PUR","MEX","VEN","DOM","URU","CHI","COL","PAN",
    "CUB","ECU","PER","PAR","BOL","BAH","ISV","CRC","JAM","NCA","HON","GUA","SLV",
    "TTO","HAI","ARU"]
_ASIA = ["AUS","NZL","CHN","PHI","JPN","KOR","PRK","IRI","IRN","JOR","LBN","SYR",
    "QAT","KSA","UAE","IRQ","KAZ","IND","INA","TPE","THA","MAS","SIN","VIE","HKG",
    "KUW","BHR","PLE","UZB","MGL","SRI","BAN","PAK","GUM","FIJ"]
_AFRICA = ["ANG","NGR","SEN","CIV","TUN","EGY","CMR","MLI","CPV","SSD","GUI","MAR",
    "ALG","RSA","CGO","COD","KEN","UGA","MOZ","MAD","RWA","GHA","GAB","CAF","CHA",
    "LBA","BKF","ZAM","ZIM","NAM","BOT","GBS"]
for c in _EUROPE:   CONFEDERATION[c] = "Europe"
for c in _AMERICAS: CONFEDERATION[c] = "Americas"
for c in _ASIA:     CONFEDERATION[c] = "Asia/Oceania"
for c in _AFRICA:   CONFEDERATION[c] = "Africa"


# Alternate FIBA/IOC/3-letter codes that Wikipedia uses interchangeably for the
# same nation. Canonicalised to a single code so a team's history isn't split
# across two codes (e.g. Slovenia appears as both SLO and SVN). Apply via
# canon_code() at games-load time in carmelo.py / generate_data.py.
CODE_ALIASES = {
    "SVN": "SLO",   # Slovenia
    "LIT": "LTU",   # Lithuania
    "SPA": "ESP",   # Spain
    "NGA": "NGR",   # Nigeria
    "LIB": "LBN",   # Lebanon
    "BFA": "BKF",   # Burkina Faso
    "DRC": "COD",   # DR Congo
    "ESA": "ESA",   # El Salvador (keep; add name below)
    "GUY": "GUY",   # Guyana (keep; add name below)
    "TOG": "TOG",   # Togo (keep; add name below)
    "ROC": "CHN",   # Republic of China (1936/1948 Olympics) -> China lineage
}

# Names for codes that only appear via the alias set / minor nations.
CODE_TO_NAME.update({
    "ESA": "El Salvador",
    "GUY": "Guyana",
    "TOG": "Togo",
})
CONFEDERATION.update({
    "ESA": "Americas", "GUY": "Americas", "TOG": "Africa",
})


def canon_code(code):
    """Map an alternate code to its canonical code (identity if none)."""
    return CODE_ALIASES.get(code, code)


# ============================================================
# YEAR-AWARE NATION RESOLUTION (defunct-state lineage)
# ============================================================
# Applied at SCRAPE time so all_games.csv stores CANONICAL codes (the rating
# engine rates strictly by code). A given 3-letter code can mean different
# nations in different eras (FRG -> Germany, YUG -> Yugoslavia vs Serbia &
# Montenegro), so resolution MUST be keyed on the GAME year, not the flag-year
# suffix Wikipedia sometimes carries ({{bk|YUG|1998}} -> resolve by game year).
#
# RULES (user-reviewed; keep EXACT — do not improvise):
#   URS  any year                 -> RUS  "Russia"                  [MERGE]
#   FRG/GER pre-1990, GDR any     -> GER  "Germany"                 [MERGE]
#   YUG  year < 1992              -> YUG  "Yugoslavia"              [SEPARATE]
#   YUG  1992-2002, SCG any,
#        SRB/MNE-pair 2003-2006   -> SCG  "Serbia and Montenegro"   [SEPARATE]
#   SRB  year >= 2006             -> SRB  "Serbia"                  (modern)
#   TCH  any year                 -> TCH  "Czechoslovakia"          [SEPARATE]
#   CRO/SLO/BIH/MKD/MNE ...       -> their own codes (Yugoslav breakaways)
#   All modern codes unchanged.
#
# Returns (canonical_code, country_name).

def resolve_nation(code, year):
    """Resolve a raw 3-letter code + GAME year to (canonical_code, name).

    `year` may be int or str; non-numeric years fall back to modern handling.
    """
    code = (code or "").upper()
    code = CODE_ALIASES.get(code, code)  # collapse SVN/LIT/etc first
    try:
        y = int(str(year)[:4])
    except (ValueError, TypeError):
        y = None

    # USSR -> Russia (continuation merge), any year.
    if code == "URS":
        return "RUS", "Russia"

    # 1992 Unified Team (former Soviet republics competing under the IOC/EUN
    # flag, code "IOC"/"EUN") is the direct USSR continuation in 1992 — folded
    # into Russia to keep the Soviet -> Russia lineage unbroken. (FLAGGED: a
    # documented extension of the user's URS->RUS merge rule, since the spec did
    # not enumerate the Unified Team explicitly.)
    if code in ("EUN", "IOC") and y is not None and y == 1992:
        return "RUS", "Russia"
    # IOC in any OTHER year is an unidentifiable Olympic-flag placeholder (e.g.
    # malformed 1980 Moscow boxes); leave it as IOC so the scraper drops the
    # game rather than mis-attributing it to a wrong nation.

    # Germany merge: West Germany (FRG, or GER pre-unification) + East
    # Germany (GDR) all fold into modern Germany.
    if code == "FRG":
        return "GER", "Germany"
    if code == "GDR":
        return "GER", "Germany"
    # GER pre-1990 is West Germany competing as "Germany" -> merge to GER.
    # GER 1990+ is unified Germany (already GER). Either way the code is GER.
    if code == "GER":
        return "GER", "Germany"

    # Yugoslav lineage — three SEPARATE entities by era.
    if code == "YUG":
        if y is not None and y < 1992:
            return "YUG", "Yugoslavia"            # SFR Yugoslavia
        # 1992-2002 (and any undated YUG row from that middle era) = the
        # FR Yugoslavia / Serbia & Montenegro entity.
        return "SCG", "Serbia and Montenegro"
    if code == "SCG":
        return "SCG", "Serbia and Montenegro"
    if code == "SRB":
        # 2003-2006 Serbia competed as part of Serbia & Montenegro; the
        # federation dissolved mid-2006. Modern Serbia is 2006+.
        if y is not None and 2003 <= y < 2006:
            return "SCG", "Serbia and Montenegro"
        return "SRB", "Serbia"
    if code == "MNE":
        # Montenegro as an INDEPENDENT nation is 2006+. A 2003-2006 MNE cell
        # would only appear as part of the joint S&M team; fold those in.
        if y is not None and 2003 <= y < 2006:
            return "SCG", "Serbia and Montenegro"
        return "MNE", CODE_TO_NAME.get("MNE", "Montenegro")

    # Czechoslovakia stays its own separate entity, any year.
    if code == "TCH":
        return "TCH", "Czechoslovakia"

    # Everything else (incl. Yugoslav breakaways CRO/SLO/BIH/MKD): unchanged.
    return code, CODE_TO_NAME.get(code, code)


def name_for(code):
    return CODE_TO_NAME.get(canon_code(code), code)
