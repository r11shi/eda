"""Adds a short plain-language note before every code cell of the five notebooks: what the cell does and what to look for.

The notes are markdown cells tagged with metadata {"plain_note": true}; running this again replaces them instead of adding copies.
    python build_docs/add_notebook_notes.py
"""
import json
from pathlib import Path

NB = Path(__file__).resolve().parents[1] / "notebooks"

NOTES = {
    "01_data_curation": [
        ("Load the tools and the raw file. `curation.py` holds all our cleaning rules, so the warehouse ETL uses exactly the same logic.",
         "73,630 rows and 17 columns; the date range 2022-01-03 to 2025-12-31."),
        ("**Profiling, step 1:** count the missing values in every column before changing anything.",
         "which columns have gaps (for example violations is empty for clean passes and for visits that never happened)."),
        ("**Profiling, step 2:** list the actual values of the key columns, to find invalid codes and spelling variants.",
         "results such as 'Out of Business' (not real inspections), risk 'All' (invalid), 'Chicago' spelled 5 ways, 217 facility types."),
        ("**Cleaning.** `cur.curate()` applies every rule and returns the clean data plus a log: one row per problem, with the count, the treatment and the reason.",
         "the cleaning-log table. This is the table to show when someone asks 'how did you clean the data?'."),
        ("**Reconciliation:** compare the counts before and after cleaning, so we can prove nothing disappeared without a reason.",
         "every result type keeps its count except the 29 removed duplicate reports."),
        ("**Derived attributes:** the new columns we created and the exact rule for each one (the brief asks us to document them).",
         "violation count, violation band, result group, risk group, facility group, area, season, and their formulas."),
        ("Check the facility grouping: how the 217 hand-typed facility types fall into 7 groups.",
         "almost every row lands in a real group; only a handful are 'Other'."),
        ("Save the clean file. Everything after this (the warehouse, EDA, the real-time replay) reads `data/curated/inspections_curated.csv`.",
         "'Saved 73,601 curated rows'."),
    ],
    "02_eda": [
        ("Load the clean file. `comp` = only the completed inspections (61,737), which is what we analyse.",
         "the row counts: 73,601 curated, 61,737 completed."),
        ("**Numerical analysis:** mean, median, quartiles, spread, skewness of the violation count and other numbers.",
         "violation count: mean about 3.8, median 3; strongly right-skewed (a long tail of high counts)."),
        ("Draw histograms and box plots of the numbers.",
         "most inspections have 0-5 violations; fails have clearly more violations than passes; dots = outliers."),
        ("**Categorical analysis:** how often each category appears (frequency and percentage).",
         "Pass is about half of all rows; restaurants dominate the facility types; many rare types."),
        ("Cross-tabulate categories with the result: the result mix inside each facility group, risk group and inspection type.",
         "complaint inspections have a much larger red (fail) share."),
        ("**Temporal analysis:** inspections per year, quarter, month, week and weekday, and the fail rate per month.",
         "volume grows a little each year; weekends are almost empty; no strong seasonal peak."),
        ("**Geographic analysis:** check the coordinates and count inspections and fails by ZIP code.",
         "99.6% of inspections have valid coordinates inside Chicago."),
        ("Draw the map of inspections and the ZIP volume-vs-fail-rate chart.",
         "busy ZIP codes are not always the ones with the highest fail rate."),
        ("**Outcome analysis:** compare absolute counts with rates per facility group (the brief asks us not to confuse volume with rate).",
         "restaurants have the most fails simply because they have the most inspections, not the highest rate."),
    ],
    "07_regression": [
        ("Load the tools and read the analytics table (the mart) **from the warehouse**, not from the raw file.",
         "'Mart rows: 61,737' and a preview of the columns, including the previous-inspection columns."),
        ("Prepare the data: keep inspections with a known violation count, fill missing history with 0 plus a 'no prior inspection' flag, and **split by time**: train 2022-2024, test 2025.",
         "45,266 training and 15,919 test inspections."),
        ("Define the encoder (words → 0/1 columns, one-hot) and fit the **baseline** (always predict the average) and the **simple regression** (one input: previous violation count).",
         "the simple equation: violations = 2.737 + 0.209 × previous violations."),
        ("Fit the **multiple regression** on all inputs and score both models on 2025 with MAE, MSE, RMSE and R².",
         "the results table: MAE 2.45 (model) vs 2.71 (guessing), R² 0.12."),
        ("Draw actual vs predicted, residuals vs predicted, and the distribution of the errors.",
         "points spread widely around the line = the model is weak; errors are centred near 0."),
        ("List the largest coefficients: which inputs push the predicted count up or down.",
         "some ZIP codes and the previous inspection's result/violations have the biggest effects."),
        ("**Diagnostics, part 1:** VIF checks whether inputs are too similar to each other (multicollinearity); Breusch-Pagan checks whether the error size is constant.",
         "only 5 of 102 inputs have VIF > 5 (acceptable); Breusch-Pagan p ≈ 0 means the error size changes (heteroscedasticity)."),
        ("**Diagnostics, part 2:** how much the extreme counts (outliers) affect the error.",
         "1.9% of inspections are outliers but cause about 25% of the squared error."),
    ],
    "08_association_mining": [
        ("Load the tools and read the analytics table from the warehouse.",
         "'Mart rows (completed inspections): 61,737'."),
        ("Build the **transactions**: each inspection becomes a basket of 7 items (facility type, risk, inspection type, result, violation band, area, season), then one-hot encode them (one True/False column per item).",
         "61,185 transactions, 35 different items, exactly 7 items per basket."),
        ("Count how often each single item appears (its **support**) and plot it.",
         "Risk=High 0.82, FacilityType=Restaurant 0.69, Result=Pass 0.62."),
        ("Run **Apriori** with minimum support 2% and make rules with minimum confidence 30%.",
         "1,198 frequent itemsets (28 singles, 223 pairs, 441 triples ...), 3,951 rules."),
        ("Run **FP-Growth** with the same settings and check that it finds exactly the same itemsets.",
         "'identical to Apriori: True' and the two run times."),
        ("**Select meaningful rules:** keep support ≥ 2%, confidence ≥ 30%, lift ≥ 1.3; remove rules that are true by definition (e.g. Fail ⇒ has violations) or that repeat a shorter rule.",
         "275 candidate rules → 41 after cleaning → the 14 we report."),
        ("Plot all rules by support (x), confidence (y) and lift (colour).",
         "most rules have low support; the high-lift rules are the bright dots."),
        ("The final rules with a plain-language interpretation and a possible use for each.",
         "10+ violations ⇒ Fail (69%, lift 3.0); Low risk ⇒ Grocery Store (62%, lift 6.5)."),
    ],
    "09_decision_tree": [
        ("Load the tools and read the analytics table from the warehouse.",
         "'Mart rows (completed inspections): 61,737'."),
        ("Prepare inputs known **before** the visit and **split by time**: train 2022-2023, validation 2024 (for tuning), test 2025 (used once at the end).",
         "the three sizes and fail rates (about 25%, 22%, 21%), and the baseline accuracy 0.789 of always saying 'not failed'."),
        ("Encode the inputs and test each tree setting **one at a time** (depth, minimum split size, minimum leaf size, pruning) on 2024.",
         "for max_depth: the training AUC keeps rising but the 2024 AUC peaks and then falls = **overfitting**."),
        ("Show the one-setting-at-a-time tables and plot training vs validation AUC.",
         "the gap between the blue (train) and orange (validation) lines growing with depth."),
        ("**Grid search:** try all 420 combinations of the four settings and keep the one with the best 2024 AUC.",
         "the best settings (depth 8, at least 200 rows per leaf) and a validation AUC of about 0.636."),
        ("**Final model:** refit on 2022-2024, score once on 2025 with the default cut-off 0.5 and with the cut-off chosen on 2024.",
         "AUC 0.635; recall 4% at cut-off 0.5 but 61% at cut-off 0.217."),
        ("Draw the two confusion matrices and the ROC curve.",
         "the 0.217 matrix catches many more real fails (bottom-right box)."),
        ("**Feature importance:** which inputs the tree uses most.",
         "previous result = Fail is the most important, then complaint inspection, then previous violation count."),
        ("Draw the top 3 levels of the trained tree.",
         "each box: the question, how many inspections reach it, and how many failed."),
        ("Print three real paths through the tree (highest fail rate, lowest, largest group) and check them on 2025.",
         "the highest-risk path fails 55-58% of the time; the lowest 4-5%."),
    ],
}


def note_cell(text, look):
    return {"cell_type": "markdown", "metadata": {"plain_note": True},
            "source": [f"> **In plain words:** {text}  \n", f"> **Look for:** {look}"]}


for name, notes in NOTES.items():
    path = NB / f"{name}.ipynb"
    nb = json.loads(path.read_text(encoding="utf-8"))
    cells = [c for c in nb["cells"] if not c.get("metadata", {}).get("plain_note")]
    code_idx = [i for i, c in enumerate(cells) if c["cell_type"] == "code"]
    assert len(code_idx) == len(notes), f"{name}: {len(code_idx)} code cells, {len(notes)} notes"
    out, k = [], 0
    for c in cells:
        if c["cell_type"] == "code":
            out.append(note_cell(*notes[k])); k += 1
        out.append(c)
    nb["cells"] = out
    path.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{name}: {k} notes")
