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


def name_for(code):
    return CODE_TO_NAME.get(code, code)
