"""Adds short notes to the five notebooks, written as what we did, plus a one-line comment at the top of each code cell.

Before every code cell: a markdown note "What we did here: ... Result: ...".
At the top of every code cell: one comment line "# ...".
Both are tagged, so running this again replaces them instead of adding copies.
    python build_docs/add_notebook_notes.py
"""
import json
from pathlib import Path

NB = Path(__file__).resolve().parents[1] / "notebooks"
TAG = "# >> "          # our comment lines start with this, so they can be found and replaced

# (what we did, the result, the one-line code comment) for every code cell, in order
NOTES = {
    "01_data_curation": [
        ("We loaded the raw Chicago file and our cleaning rules from `etl/curation.py`.", "73,630 rows, 17 columns, dated 2022-01-03 to 2025-12-31.", "load the raw file"),
        ("We counted the missing values in every column, before changing anything.", "gaps are mostly in violations (clean passes and visits that never happened have no text).", "profiling: missing values"),
        ("We listed the real values of the key columns to find wrong codes and spellings.", "visits that never happened (Out of Business, No Entry), a wrong risk value 'All', Chicago spelled 5 ways, 217 facility types.", "profiling: values of the key columns"),
        ("We applied every cleaning rule and kept a log of each one: the problem, how many rows, what we did and why.", "the cleaning-log table below.", "clean the data and keep a log of every rule"),
        ("We compared the counts before and after cleaning.", "every result keeps its count except the 29 duplicate reports we removed.", "check counts before vs after cleaning"),
        ("We listed the new columns we created and the rule behind each one.", "violation count and band, result group, risk group, facility group, area, season.", "the new (derived) columns and their rules"),
        ("We checked how the 217 facility types fell into our 7 groups.", "almost every row is in a real group; only a handful are 'Other'.", "check the facility groups"),
        ("We saved the clean file that the warehouse, the EDA and the real-time replay use.", "73,601 clean rows saved.", "save the clean file"),
    ],
    "02_eda": [
        ("We loaded the clean file and kept the completed inspections for the analysis.", "73,601 clean rows, 61,737 completed inspections.", "load the clean file"),
        ("We summarised the numbers: average, middle value, spread, quartiles.", "violations: average about 3.8, middle value 3, a long tail of high counts.", "numbers: summary statistics"),
        ("We drew histograms and box plots of the numbers.", "most inspections have 0-5 violations; fails have more than passes; the dots are outliers.", "numbers: histograms and box plots"),
        ("We counted how often each category appears.", "about half of all rows are passes; restaurants are by far the largest type.", "categories: counts and percentages"),
        ("We compared the result mix inside each facility group, risk group and inspection type.", "complaint inspections have a much larger share of fails.", "categories: result mix per group"),
        ("We looked at time: per year, quarter, month, week and weekday, and the fail rate per month.", "slow growth each year, empty weekends, no strong season.", "time: trends"),
        ("We checked the coordinates and counted inspections and fails per ZIP code.", "99.6% of inspections have valid coordinates inside Chicago.", "places: coordinates and ZIP codes"),
        ("We drew the map and compared ZIP codes by volume and fail rate.", "busy ZIP codes are not always the ones with the highest fail rate.", "places: map and ZIP comparison"),
        ("We compared counts with rates for each facility group.", "restaurants have the most fails because they have the most inspections, not the highest rate.", "outcomes: counts vs rates"),
    ],
    "07_regression": [
        ("We read the analytics table from the warehouse (not from the raw file).", "61,737 rows, each with the previous inspection of the same place.", "read the analytics table from the warehouse"),
        ("We kept inspections with a known violation count, filled missing history, and split by time: 2022-2024 to learn, 2025 to test.", "45,266 training and 15,919 test inspections.", "prepare the data and split by time"),
        ("We turned word columns into 0/1 columns and fitted the baseline (always the average) and the simple regression (previous violations only).", "violations = 2.737 + 0.209 × previous violations.", "baseline and simple regression"),
        ("We fitted the multiple regression on all inputs and scored every model on 2025.", "MAE 2.45 (model) vs 2.71 (guessing), R² 0.12.", "multiple regression and the scores"),
        ("We plotted actual against predicted values and the errors.", "points spread widely: the model is weak; errors centre near 0.", "charts of the predictions and errors"),
        ("We listed the inputs with the biggest effect.", "some ZIP codes and the previous inspection matter most.", "largest effects (coefficients)"),
        ("We checked whether inputs overlap too much (VIF) and whether the error size is even (Breusch-Pagan).", "only 5 of 102 inputs overlap noticeably; the error size is not even.", "diagnostics: overlap and error spread"),
        ("We measured how much the extreme counts affect the error.", "1.9% of inspections cause about 25% of the squared error.", "diagnostics: outliers"),
    ],
    "08_association_mining": [
        ("We read the analytics table from the warehouse.", "61,737 completed inspections.", "read the analytics table from the warehouse"),
        ("We turned each inspection into a basket of 7 items (type, risk, inspection type, result, violation band, area, season).", "61,185 baskets, 35 different items.", "build the baskets (transactions)"),
        ("We counted how often each single item appears.", "Risk=High 82%, Restaurant 69%, Pass 62%.", "how often each item appears (support)"),
        ("We ran Apriori with minimum support 2% and made rules with confidence of at least 30%.", "1,198 frequent item sets, 3,951 rules.", "Apriori and the rules"),
        ("We ran FP-Growth with the same settings and compared it with Apriori.", "the same 1,198 item sets ('identical to Apriori: True').", "FP-Growth, compared with Apriori"),
        ("We kept the useful rules: lift at least 1.3, no rules that are true by definition or repeat a shorter rule.", "275 → 41 → the 14 rules we report.", "select the meaningful rules"),
        ("We plotted every rule by support, confidence and lift.", "most rules are rare; the strongest ones stand out in colour.", "chart of all rules"),
        ("We wrote what each selected rule means and how it could be used.", "10+ violations ⇒ Fail (69%, lift 3.0); low risk ⇒ grocery store (62%, lift 6.5).", "the final rules and their meaning"),
    ],
    "09_decision_tree": [
        ("We read the analytics table from the warehouse.", "61,737 completed inspections.", "read the analytics table from the warehouse"),
        ("We kept inputs known before the visit and split by time: 2022-23 to learn, 2024 to tune, 2025 to test once.", "about 25%, 22% and 21% of inspections fail; always saying 'pass' is 78.9% accurate.", "prepare the inputs and the three-way time split"),
        ("We tried each tree setting on its own and scored it on 2024.", "deeper trees score higher on training data but lower on 2024 (overfitting).", "try each setting on its own"),
        ("We showed those results as tables and charts.", "the training and 2024 lines drift apart as the tree gets deeper.", "tables and charts of the settings"),
        ("We tried all 420 combinations of settings and kept the best one on 2024.", "depth 8, at least 200 inspections per leaf, 2024 AUC about 0.636.", "grid search: 420 combinations"),
        ("We retrained on 2022-2024, tested once on 2025, and chose the cut-off on 2024.", "AUC 0.635; 4% of fails caught at cut-off 0.5, 61% at 0.217.", "final model and the 2025 scores"),
        ("We drew the confusion matrices and the ROC curve.", "the 0.217 cut-off catches many more real fails.", "confusion matrices and ROC curve"),
        ("We listed which inputs the tree uses most.", "previous result = Fail, then complaint inspection, then previous violations.", "most important inputs"),
        ("We drew the top three levels of the tree.", "each box shows the question, how many inspections reach it, and how many failed.", "draw the tree"),
        ("We followed three real paths through the tree and checked them on 2025.", "highest-risk path fails 55-58%, lowest 4-5%.", "three real decision paths"),
    ],
}


def note_cell(did, result):
    return {"cell_type": "markdown", "metadata": {"plain_note": True},
            "source": [f"**What we did here:** {did}  \n", f"**Result:** {result}"]}


for name, notes in NOTES.items():
    path = NB / f"{name}.ipynb"
    nb = json.loads(path.read_text(encoding="utf-8"))
    cells = [c for c in nb["cells"] if not c.get("metadata", {}).get("plain_note")]
    code = [c for c in cells if c["cell_type"] == "code"]
    assert len(code) == len(notes), f"{name}: {len(code)} code cells, {len(notes)} notes"
    out, k = [], 0
    for c in cells:
        if c["cell_type"] == "code":
            did, result, comment = notes[k]; k += 1
            out.append(note_cell(did, result))
            src = "".join(c["source"]).split("\n")
            src = [l for l in src if not l.startswith(TAG)]                  # remove our old comment
            c["source"] = [l + "\n" for l in [TAG + comment] + src[:-1]] + [src[-1]] if src else [TAG + comment]
        out.append(c)
    nb["cells"] = out
    path.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{name}: {k} cells annotated")
