"""Data profiling and curation for the Chicago Food Inspections project.

Used by the curation notebook and by the ETL scripts so that every stage applies
exactly the same rules.  All thresholds / mappings are defined once, here.
"""
import re
import numpy as np
import pandas as pd

# ----------------------------------------------------------------------------- constants
COMPLETED_RESULTS = ["Pass", "Pass w/ Conditions", "Fail"]          # inspections that were actually carried out
DOCUMENTED_RESULTS = COMPLETED_RESULTS + ["Out of Business", "No Entry", "Not Ready", "Business Not Located"]
DOCUMENTED_RISK = ["Risk 1 (High)", "Risk 2 (Medium)", "Risk 3 (Low)"]
HIGH_VIOLATION_THRESHOLD = 6          # ViolationCount >= 6 (just above the 75th percentile of completed inspections)
CHICAGO_BOX = dict(lat=(41.6, 42.1), lon=(-88.0, -87.4))   # broad bounding box, used only as a validity check
GRID_ORIGIN = (41.8820, -87.6278)     # State St & Madison St: origin of the Chicago street-address grid

RESULT_GROUP = {"Pass": "Pass", "Pass w/ Conditions": "Conditional Pass", "Fail": "Fail"}   # everything else -> Not Completed
RISK_GROUP = {"Risk 1 (High)": "High", "Risk 2 (Medium)": "Medium", "Risk 3 (Low)": "Low"}  # everything else -> Unknown

# ordered rules: the first regular expression that matches the lower-cased facility type wins
FACILITY_GROUP_RULES = [
    ("Restaurant & Food Service", r"^restaurant"),
    ("Schools & Childcare", r"school|shcool|day ?care|daycare|child|charter|cps|preschool|teaching|culinary class|cooking class|after school"),
    ("Healthcare & Residential Care", r"long term care|hospital|nursing|assisted living|supportive living|senior|adult|rehab|shelter|youth housing|hostel|golden diner|archdiocese|pantry|soup kitchen|church"),
    ("Mobile, Catering & Events", r"mobil|catering|catered|special event|pop-up|shared kitchen|commissary|commisary|commiasary|vending|banquet|event|rooftop|roof top|riverwalk|stadium|venue|theat|navy pier|vfw|pushcart|push cart"),
    ("Retail Food & Grocery", r"grocery|bakery|liquor|convenience|convenient|store|gas|wholesale|retail|candy|deli|butcher|newsstand|poultry|slaughter|warehouse|distribution|cold storage|herbal|nutrition|shake|packaged|paleteria|popcorn|donut|frozen"),
    ("Restaurant & Food Service", r"restaurant|tavern|bar|lounge|club|cafe|coffee|ice cream|juice|brewery|dining|cafeteria|hot dog|sushi|tea|hotel|room service|food hall|gym|fitness|kitchen"),
]


def violation_codes(text):
    """Rule numbers found in the Violations text, e.g. '34. FLOORS ... | 35. WALLS ...' -> [34, 35]."""
    if not isinstance(text, str):
        return []
    return [int(m.group(1)) for part in text.split("|") for m in [re.match(r"^\s*(\d+)\.", part)] if m]


def facility_group(ftype):
    if not isinstance(ftype, str):
        return "Unknown"
    t = ftype.strip().lower()
    for group, pattern in FACILITY_GROUP_RULES:
        if re.search(pattern, t):
            return group
    return "Other"


def inspection_type_group(itype):
    t = str(itype).lower()
    if "re-inspection" in t:
        return "Re-inspection"
    if "canvass" in t:
        return "Routine (Canvass)"
    if "license" in t:
        return "License"
    if "complaint" in t or "food poisoning" in t:
        return "Complaint / Illness"
    return "Other"


def violation_band(n):
    if pd.isna(n):
        return "Unknown"
    if n == 0:
        return "None (0)"
    if n <= 2:
        return "Low (1-2)"
    if n <= 5:
        return "Medium (3-5)"
    if n <= 9:
        return "High (6-9)"
    return "Very High (10+)"


def season(month):
    return {12: "Winter", 1: "Winter", 2: "Winter", 3: "Spring", 4: "Spring", 5: "Spring",
            6: "Summer", 7: "Summer", 8: "Summer"}.get(month, "Autumn")


def area_group(lat, lon):
    if pd.isna(lat) or pd.isna(lon):
        return "Unknown"
    ns = "North" if lat > GRID_ORIGIN[0] else "South"
    ew = "West" if lon < GRID_ORIGIN[1] else "East"
    return (ns + ew).title()


# ----------------------------------------------------------------------------- loading
def load_raw(path):
    """Read the portal CSV with every column as text so that nothing is silently converted."""
    return pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])


# ----------------------------------------------------------------------------- profiling
def missing_profile(raw):
    n = len(raw)
    out = pd.DataFrame({"missing": raw.isna().sum(), "missing_pct": (raw.isna().mean() * 100).round(2)})
    out["distinct"] = raw.nunique()
    return out


# ----------------------------------------------------------------------------- curation
def curate(raw):
    """Return (curated_df, decisions).  `decisions` is a list of dicts with the actual count of
    affected rows, the treatment applied and the justification (the data-quality report)."""
    log = []

    def note(problem, field, count, treatment, justification):
        log.append(dict(problem=problem, field=field, count=int(count), treatment=treatment, justification=justification))

    df = raw.copy()
    df.columns = [c.strip().lower().rstrip("_") if c != "license_" else "license_number" for c in df.columns]
    n0 = len(df)

    # ---- text cleaning
    for c in ["dba_name", "aka_name", "facility_type", "risk", "address", "city", "state", "inspection_type", "results"]:
        df[c] = df[c].str.strip()

    # ---- data types
    df["inspection_date"] = pd.to_datetime(df["inspection_date"], errors="coerce")
    bad_date = df["inspection_date"].isna().sum()
    note("Invalid timestamp", "inspection_date", bad_date, "Exclude (none found)" if bad_date == 0 else "Exclude",
         "A date that cannot be parsed cannot be placed in DimDate.")
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["inspection_id"] = df["inspection_id"].astype("int64")
    df["zip"] = df["zip"].str.strip()

    # ---- duplicates
    exact = df.duplicated(subset=[c for c in df.columns if c != "location"], keep="first").sum()
    note("Exact duplicate record", "all columns", exact, "Remove", "Identical rows add no information.")
    df = df.drop_duplicates(subset=[c for c in df.columns if c != "location"], keep="first")
    dup_id = df["inspection_id"].duplicated().sum()
    note("Repeated inspection_id", "inspection_id", dup_id, "Investigate (none found)" if dup_id == 0 else "Remove",
         "inspection_id is the source identifier of one inspection.")
    df = df.drop_duplicates(subset=["inspection_id"], keep="first")

    has_lic = df["license_number"].notna() & (df["license_number"] != "0")
    key = ["license_number", "inspection_date", "inspection_type", "results", "violations"]
    same_content = df[has_lic].duplicated(subset=key, keep="first")
    drop_idx = same_content[same_content].index
    note("Logical duplicate (same licence, date, type, result and violation text, different inspection_id)", "inspection_id",
         len(drop_idx), "Remove later copies",
         "The source documentation says duplicate reports may remain; identical content for the same licence and day is a repeated report.")
    df = df.drop(index=drop_idx)
    same_day = df[has_lic.reindex(df.index, fill_value=False)].duplicated(subset=["license_number", "inspection_date", "inspection_type"], keep=False)
    note("Same licence, date and type but different result/violations", "license_number", same_day.sum(), "Retain and flag",
         "Different content means they may be separate visits (e.g. morning and afternoon); cannot be proven duplicates.")
    df["is_same_day_repeat"] = False
    df.loc[same_day[same_day].index, "is_same_day_repeat"] = True

    # ---- invalid codes / standardisation
    bad_results = (~df["results"].isin(DOCUMENTED_RESULTS)).sum()
    note("Result value not in documented list", "results", bad_results, "Map to Not Completed (none found)" if bad_results == 0 else "Investigate",
         "Results are checked against the source documentation.")
    all_risk = (df["risk"] == "All").sum()
    note("Invalid risk code 'All'", "risk", all_risk, "Map to Unknown member", "Only Risk 1/2/3 are documented, so 'All' is not a real category.")
    miss_risk = df["risk"].isna().sum()
    note("Missing risk", "risk", miss_risk, "Map to Unknown member", "Facts are kept; excluding them would bias counts.")
    df["risk_category"] = df["risk"].where(df["risk"].isin(DOCUMENTED_RISK), "Unknown")
    df["risk_group"] = df["risk_category"].map(RISK_GROUP).fillna("Unknown")

    miss_ft = df["facility_type"].isna().sum()
    note("Missing facility type", "facility_type", miss_ft, "Map to Unknown member", "Facts are kept; type is not needed for counts.")
    df["facility_type_clean"] = df["facility_type"].fillna("Unknown").str.strip().str.title().str.replace(r"'S\b", "'s", regex=True)
    df["facility_group"] = df["facility_type"].map(facility_group)
    note("Free-text facility types (distinct raw spellings)", "facility_type", df["facility_type"].nunique(),
         "Title-case + keyword grouping into FacilityGroup",
         "Raw type is free text with spelling variants; the group is a DERIVED attribute, the clean type keeps the original wording.")

    city_fix = df["city"].str.upper().isin(["CCHICAGO"]).sum()
    note("Misspelt city (CCHICAGO)", "city", city_fix, "Correct to CHICAGO", "Obvious typo; coordinates confirm Chicago.")
    df["city"] = df["city"].str.upper().replace({"CCHICAGO": "CHICAGO"})
    non_il = (df["state"].notna() & (df["state"] != "IL")).sum()
    note("State other than IL", "state", non_il, "Retain and flag", "Coordinates are checked separately; state may be a data-entry error.")
    note("Missing city/state", "city, state", int((df["city"].isna() | df["state"].isna()).sum()), "Retain (not used as a key)", "Location is analysed via ZIP and coordinates.")
    miss_zip = df["zip"].isna().sum()
    note("Missing ZIP", "zip", miss_zip, "Map to 'Unknown'", "Facts are kept.")
    df["zip"] = df["zip"].fillna("Unknown")
    odd_zip = (~df["zip"].str.match(r"^606\d\d$") & (df["zip"] != "Unknown")).sum()
    note("ZIP outside the 606xx Chicago range", "zip", odd_zip, "Retain and flag", "Could be a real suburb address or a typo; not removed.")

    # ---- facility identity
    no_lic = (df["license_number"].isna() | (df["license_number"] == "0")).sum()
    note("Missing or zero licence number", "license_number", no_lic, "Identify facility by name + address instead",
         "Licence 0 is a placeholder; such facilities are excluded from repeat-inspection analysis only.")
    lic_ok = df["license_number"].notna() & (df["license_number"] != "0")
    df["facility_id_source"] = np.where(lic_ok, "License", "NameAddress")
    df["facility_nk"] = np.where(lic_ok, "L" + df["license_number"].fillna(""),
                                 "N|" + df["dba_name"].fillna("").str.upper() + "|" + df["address"].fillna("").str.upper())

    # ---- coordinates
    miss_geo = (df["latitude"].isna() | df["longitude"].isna()).sum()
    note("Missing coordinates", "latitude, longitude", miss_geo, "Keep row; LocationKey -> Unknown area", "ZIP is still available for these rows.")
    box = ~(df["latitude"].between(*CHICAGO_BOX["lat"]) & df["longitude"].between(*CHICAGO_BOX["lon"])) & df["latitude"].notna()
    note("Coordinates outside Chicago bounding box", "latitude, longitude", box.sum(), "Set to missing (none found)" if box.sum() == 0 else "Set to missing",
         "Impossible for a Chicago establishment; the box is a quality check, not the exact city boundary.")
    df.loc[box, ["latitude", "longitude"]] = np.nan

    # ---- dates
    df["is_weekend"] = df["inspection_date"].dt.dayofweek >= 5
    note("Inspection on Saturday/Sunday", "inspection_date", df["is_weekend"].sum(), "Retain and flag",
         "Possible but rare; no evidence of error.")
    note("Time of day not available", "inspection_date", len(df), "No hourly analysis possible",
         "All timestamps are 00:00:00 in the source, so hourly patterns are NOT derived or invented.")

    # ---- violations
    codes = df["violations"].map(violation_codes)
    df["violation_text_missing"] = df["violations"].isna()
    df["violation_count_raw"] = codes.map(len)
    completed = df["results"].isin(COMPLETED_RESULTS)
    # Pass with no text = no violation was cited; Fail / Pass w/ Conditions without text are inconsistent -> unknown
    inconsistent = completed & df["violation_text_missing"] & df["results"].isin(["Fail", "Pass w/ Conditions"])
    note("Fail / Pass w/ Conditions without violation text", "violations", inconsistent.sum(), "ViolationCount = NULL (unknown)",
         "These results require at least one cited violation, so zero would be wrong; the row is kept for counts.")
    pass_none = completed & df["violation_text_missing"] & (df["results"] == "Pass")
    note("Pass with no violation text", "violations", pass_none.sum(), "ViolationCount = 0", "A passing inspection with nothing recorded cited no violations.")
    df["violation_count"] = np.where(~completed, np.nan, np.where(inconsistent, np.nan, df["violation_count_raw"].astype(float)))
    q1, q3 = df.loc[completed, "violation_count"].quantile([.25, .75])
    outl = (df["violation_count"] > q3 + 1.5 * (q3 - q1)).sum()
    note("Extreme violation count (above Q3 + 1.5 x IQR)", "violation_count", outl, "Retain and flag",
         "Large counts are plausible for badly failing premises; capping would hide the very inspections of interest.")
    df["is_extreme_violation_count"] = df["violation_count"] > q3 + 1.5 * (q3 - q1)
    neg = (df["violation_count"] < 0).sum()
    note("Negative or impossible violation count", "violation_count", neg, "None found", "A count cannot be negative.")
    df["violation_codes"] = codes.map(lambda c: ",".join(map(str, c)))

    # ---- completed vs not completed
    nc = (~completed).sum()
    note("Result is not a completed inspection (Out of Business, No Entry, Not Ready, Business Not Located)", "results", nc,
         "Keep in curated/staging data, exclude from FactInspection",
         "The fact grain is one COMPLETED inspection; these rows are status outcomes with no assessment.")
    df["is_completed"] = completed

    # ---- derived attributes
    d = df["inspection_date"]
    df["year"] = d.dt.year
    df["quarter"] = d.dt.quarter
    df["month"] = d.dt.month
    df["day_of_week"] = d.dt.day_name()
    df["result_group"] = df["results"].map(RESULT_GROUP).fillna("Not Completed")
    df["inspection_type_group"] = df["inspection_type"].map(inspection_type_group)
    df["has_violations"] = np.where(df["violation_count"].isna(), np.nan, (df["violation_count"] > 0).astype(float))
    df["is_failed_inspection"] = (df["results"] == "Fail").astype(int)
    df["high_violation_flag"] = np.where(df["violation_count"].isna(), 0, (df["violation_count"] >= HIGH_VIOLATION_THRESHOLD).astype(int))
    df["violation_band"] = df["violation_count"].map(violation_band)
    df["season"] = df["month"].map(season)
    df["geographic_area_group"] = [area_group(a, b) for a, b in zip(df["latitude"], df["longitude"])]
    df["latitude_band"] = (np.floor(df["latitude"] / 0.05) * 0.05).round(2)
    df["longitude_band"] = (np.floor(df["longitude"] / 0.05) * 0.05).round(2)

    note("Rows before / after curation", "-", n0 - len(df), f"{n0:,} raw rows -> {len(df):,} curated rows", "Row reconciliation (rows removed = exact + id + logical duplicates).")
    cols = ["inspection_id", "dba_name", "aka_name", "license_number", "facility_nk", "facility_id_source", "facility_type_clean", "facility_group",
            "risk_category", "risk_group", "address", "city", "state", "zip", "inspection_date", "inspection_type", "inspection_type_group",
            "results", "result_group", "is_completed", "is_failed_inspection", "violation_count", "has_violations", "high_violation_flag",
            "violation_band", "violation_codes", "latitude", "longitude", "latitude_band", "longitude_band", "geographic_area_group",
            "year", "quarter", "month", "day_of_week", "is_weekend", "season", "is_same_day_repeat", "is_extreme_violation_count"]
    return df[cols].sort_values(["inspection_date", "inspection_id"]).reset_index(drop=True), pd.DataFrame(log)


# ----------------------------------------------------------------------------- documentation of derived attributes
DERIVED_ATTRIBUTES = [
    ("Year", "YEAR(inspection_date)", "-", "None"),
    ("Quarter", "QUARTER(inspection_date)", "1-4", "None"),
    ("Month", "MONTH(inspection_date)", "1-12", "None"),
    ("DayOfWeek", "Day name of inspection_date", "Monday-Sunday", "None"),
    ("IsWeekend", "DayOfWeek in (Saturday, Sunday)", "TRUE/FALSE", "None"),
    ("ViolationCount", "Number of numbered items ('34. FLOORS ...') in the Violations text", "Completed inspections only. Pass without text = 0. Fail / Pass w/ Conditions without text = NULL (unknown). Not completed = NULL", "None"),
    ("HasViolations", "ViolationCount > 0", "NULL when ViolationCount is NULL", "None"),
    ("ResultGroup", "Mapping of Results", "Pass -> Pass; Pass w/ Conditions -> Conditional Pass; Fail -> Fail; Out of Business, No Entry, Not Ready, Business Not Located -> Not Completed", "None"),
    ("RiskGroup", "Mapping of Risk", "Risk 1 (High) -> High; Risk 2 (Medium) -> Medium; Risk 3 (Low) -> Low; 'All', missing -> Unknown", "None"),
    ("FacilityGroup", "Ordered keyword rules on lower-cased Facility Type", "Restaurant & Food Service; Schools & Childcare; Healthcare & Residential Care; Mobile, Catering & Events; Retail Food & Grocery; Other; missing -> Unknown", "None (rules are in etl/curation.py)"),
    ("InspectionTypeGroup", "Rules on Inspection Type", "contains 're-inspection' -> Re-inspection; Canvass -> Routine (Canvass); License -> License; Complaint / Food Poisoning -> Complaint / Illness; else Other", "None"),
    ("IsFailedInspection", "Results = 'Fail'", "1 / 0", "None"),
    ("HighViolationFlag", "ViolationCount >= 6", "Threshold 6 is just above the 75th percentile (5) of completed inspections; NULL count -> 0", "None"),
    ("ViolationBand", "Banding of ViolationCount", "None (0); Low (1-2); Medium (3-5); High (6-9); Very High (10+); Unknown", "None"),
    ("Season", "Month -> season", "Dec-Feb Winter; Mar-May Spring; Jun-Aug Summer; Sep-Nov Autumn", "None"),
    ("GeographicAreaGroup", "Quadrant of the coordinates relative to the origin of the Chicago street grid (State St and Madison St, 41.8820, -87.6278)", "Northwest / Northeast / Southwest / Southeast; missing coordinates -> Unknown", "External reference: location of the street-grid origin only. No external dataset joined."),
    ("LatitudeBand / LongitudeBand", "FLOOR(coordinate / 0.05) x 0.05", "0.05 degree cells (about 5 km)", "None"),
    ("FacilityNK (facility natural key)", "'L' + licence number; if licence is missing or 0: 'N|' + DBA name + '|' + address", "Used to build DimFacility", "None"),
]
