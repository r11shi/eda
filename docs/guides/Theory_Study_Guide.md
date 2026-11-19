# Theory Study Guide: Association Rules, FP-Growth, Decision Trees, Regression
**For Rushikesh Maddewad (Roll 353)**. Each topic: the idea in one line, a small worked example you can redo on a board, how my project used it, and the questions a professor asks. Study in this order: association rules, then FP-Growth, then decision tree, then regression, then the "other advanced topics" table.

**To be honest about difficulty:** besides these four, the project has several other technical topics (SQL window functions, a stored procedure, Citus sharding, Kafka and Spark windows, evaluation metrics). They are in Part 5. None is beyond what you can explain at a viva after reading it once.

---

## Part 1. Association rules (Apriori)

**One line:** find items that often occur *together*, then turn them into "if X then Y" rules. The classic example is "customers who buy diapers also buy beer".

**In my project:** one *transaction* = one inspection. The *items* are its labels: `FacilityType=Restaurant`, `Risk=High`, `Violations=Very High (10+)`, `Result=Fail`, `Season=Summer`, `Area=Southwest`. A rule like `Violations=10+ => Result=Fail` says inspections with 10+ violations tend to fail.

### The three numbers (memorise)
| Measure | Formula | Meaning |
|---|---|---|
| **Support**(X) | (transactions containing X) / (all transactions) | How common the pattern is. |
| **Confidence**(X => Y) | support(X and Y) / support(X) | Of the transactions with X, what share also has Y. |
| **Lift**(X => Y) | confidence(X => Y) / support(Y) | How much more often than chance. **1 = unrelated, above 1 = positive, below 1 = negative.** |

### Worked example (5 shopping baskets)
| T | Items |
|---|---|
| T1 | bread, milk |
| T2 | bread, diaper, beer, eggs |
| T3 | milk, diaper, beer, cola |
| T4 | bread, milk, diaper, beer |
| T5 | bread, milk, diaper, cola |

Minimum support 60% (= at least 3 of 5 baskets).

1. **Count single items:** bread 4, milk 4, diaper 4, beer 3, cola 2, eggs 1. Keep those with count 3 or more: bread, milk, diaper, beer.
2. **Candidate pairs** (only from the survivors): bread-milk 3 (yes), bread-diaper 3 (yes), bread-beer 2 (no), milk-diaper 3 (yes), milk-beer 2 (no), diaper-beer 3 (yes).
3. **Candidate triples** (from frequent pairs): bread-milk-diaper has count 2 (no). Stop.
4. **Rule diaper => beer:** support = 3/5 = 0.60; confidence = 3/4 = 0.75; lift = 0.75 / (3/5) = **1.25**. So buyers of diapers are 25% more likely than average to buy beer.
5. **Rule beer => diaper:** confidence = 3/3 = 1.00; lift = 1.00 / (4/5) = 1.25. (Lift is symmetric; confidence is not.)

### The Apriori principle (the key idea)
*If an itemset is frequent, all its subsets are frequent. So if {bread, beer} is not frequent, no larger set containing it can be.* Apriori uses this to **prune** candidates: it builds itemsets level by level and never counts a set that has an infrequent subset. Weakness: it scans the data many times and creates many candidates.

### Project numbers
Minimum support 2%, confidence 30%, lift 1.3. 1,198 frequent itemsets. Best rule: `Violations=Very High (10+) => Result=Fail`, support 5.4%, confidence 69%, lift 3.0.

### Likely questions
- *Why is high confidence not enough?* Because the right side may simply be common. Lift corrects that: if 90% of all inspections pass, "X => Pass" at 90% confidence has lift 1, meaning no real relation.
- *Does a rule mean causation?* No. It only says the items co-occur. Violations do not "cause" a fail label in a rule sense; fail is partly defined by violations.
- *How do you handle a numeric column?* Discretise it. I made violation bands (0, 1-2, 3-5, 6-9, 10+) from the quartiles.
- *Why did you remove some rules?* Definitional or redundant ones (for example a rule that just restates the result group).
- *What are the limits?* Many rules appear for low supports; you must filter by support, confidence and lift and interpret them.

---

## Part 2. FP-Growth and the FP-tree

**One line:** find the same frequent itemsets as Apriori, but **without generating candidates**, by compressing the data into a tree and mining the tree. It scans the data only twice.

### How it works (four steps)
1. **Scan 1:** count each item; drop items below minimum support; sort items by frequency (highest first).
2. **Scan 2:** for each transaction keep only frequent items in that order and insert it into a **prefix tree**. Transactions sharing a start share a branch, and each node keeps a count. A header table links all nodes of the same item.
3. **For each item (from the least frequent):** collect its **conditional pattern base** (the prefix paths leading to it, with counts).
4. **Build a conditional tree from that base and mine it recursively.**

### Worked example (same 5 baskets, minimum count 3)
Frequent items in order: bread 4, milk 4, diaper 4, beer 3. Remove eggs and cola. Ordered transactions:

| T | After filter and sort |
|---|---|
| T1 | bread, milk |
| T2 | bread, diaper, beer |
| T3 | milk, diaper, beer |
| T4 | bread, milk, diaper, beer |
| T5 | bread, milk, diaper |

The FP-tree (item:count):
```
root
├─ bread:4
│   ├─ milk:3
│   │   └─ diaper:2
│   │       └─ beer:1
│   └─ diaper:1
│       └─ beer:1
└─ milk:1
    └─ diaper:1
        └─ beer:1
```
Mining for **beer**: its prefix paths are {bread, milk, diaper}:1, {bread, diaper}:1, {milk, diaper}:1. Counting items in these paths: diaper 3, bread 2, milk 2. Only diaper reaches 3, so the frequent pattern is **{diaper, beer}** with count 3. This matches the Apriori result, found without ever listing candidates.

### Apriori vs FP-Growth
| | Apriori | FP-Growth |
|---|---|---|
| Idea | Generate candidates level by level and count them | Compress into an FP-tree, mine it recursively |
| Data scans | One per level | Two |
| Candidate generation | Yes (expensive) | No |
| Memory | Low per level but many candidates | Needs the tree in memory |
| Speed | Slower on many items or low support | Faster in general |

In my project both gave **identical itemsets** (1,198 at 2% support); I checked that, and timed both.

### Likely questions
- *Why sort items by frequency?* So that common items sit near the root and more transactions share prefixes, which compresses the tree.
- *What is the header table?* A list linking every node of an item, used to collect its prefix paths quickly.
- *When is FP-Growth not better?* On very sparse data with huge trees, or when the tree does not fit in memory; for small data the speed difference is negligible.
- *What did ECLAT/multilevel mean?* (Only in Assignment 5, not the project.) ECLAT uses a vertical layout (item -> set of transaction ids) and intersects sets. Multilevel mining uses a concept hierarchy (for example Restaurant -> Food service) and mines at several levels.

---

## Part 3. Decision trees

**One line:** a flowchart learned from data. Each internal node asks a yes/no question about one feature; each leaf gives a prediction. It answers "which questions split the data into the purest groups?"

**In my project:** predict `FailedInspection` (1 if the result is Fail) from facts known *before* the visit: facility type, risk, inspection type, month, area, and **prior history** (previous result, previous violation count, days since last inspection).

### Impurity: how "mixed" a node is
- **Entropy** = -sum p log2 p.  **Gini** = 1 - sum p².  Both are 0 for a pure node and largest when classes are 50/50.
- Example node with 9 "yes" and 5 "no" (14 rows): entropy = **0.940**; Gini = **0.459**.

### Information gain (ID3) and Gini (CART)
- **Information gain** = entropy(parent) - weighted average entropy(children). Pick the split with the largest gain.
- Worked example (the classic "play tennis" table, 9 yes, 5 no): splitting on Outlook gives gain **0.247**, Humidity 0.152, Wind 0.048, Temperature 0.029. So the root is **Outlook**.
- **C4.5** fixes ID3's bias to many-valued attributes using **gain ratio** = gain / split information, and handles numbers and missing values.
- **CART** uses **Gini**, makes **binary splits** only, handles numbers and can do regression trees. **scikit-learn's `DecisionTreeClassifier` is CART**, which is what my project uses.

| | ID3 | C4.5 | CART |
|---|---|---|---|
| Split criterion | information gain | gain ratio | Gini (or entropy) |
| Splits | multi-way | multi-way | binary |
| Numeric features | no | yes | yes |
| Pruning | none | pessimistic pruning | cost-complexity pruning |

### Overfitting and pruning
A tree grown until every leaf is pure memorises the training data and fails on new data. Controls (all used in my notebook): **max_depth**, **min_samples_split**, **min_samples_leaf**, and **cost-complexity pruning (`ccp_alpha`)**: trade the tree's error against its number of leaves, with larger alpha giving a smaller tree. I chose settings by **validation-year AUC**, never the test year.

### Evaluation
| Metric | Meaning |
|---|---|
| Accuracy | share of correct predictions (misleading with imbalance: 79% of inspections pass, so "always pass" is 79% accurate) |
| Precision | of those predicted Fail, how many really failed |
| Recall | of the real Fails, how many I caught |
| F1 | balance of precision and recall |
| **ROC-AUC** | chance the model ranks a random failed inspection above a random passed one (0.5 = coin flip) |

### My results (test year 2025)
- Baseline "always pass": accuracy 0.789, recall 0.
- Tree at the default threshold 0.5: accuracy 0.784, **recall 0.04** (it almost never predicts fail), **AUC 0.635**.
- Tree with a threshold chosen on validation data (0.217): recall **0.61**, precision 0.29, accuracy 0.60.
- Top features: prior result = Fail (29%), Complaint inspection (15%), prior violation count (13%), days since prior inspection (10%).
- **Interpretation:** the past is the best predictor, but overall the model is weak (AUC 0.64). It can help rank inspections, not decide them.

### Likely questions
- *Why not use the number of violations as a feature?* That is **data leakage**: it is known only after the inspection and decides the result.
- *Why a chronological split?* Real use predicts the future. Random splitting would let future data leak into training.
- *Why lower the threshold?* Failures are rare (about 21%). The default 0.5 cut-off almost never predicts "fail", so recall is 4%. A lower cut-off finds more failures but gives more false alarms. The right trade-off depends on the cost of a missed failure.
- *What is feature importance?* How much a feature reduced impurity across the tree, summed.
- *Why not a random forest?* The brief asks for a decision tree; a single tree is interpretable, which is the point.

---

## Part 4. Regression

**One line:** fit a line (or hyperplane) that predicts a number. In my project: predict the **number of violations** found in an inspection.

### Simple linear regression
y = b0 + b1 x. Choose b0, b1 to minimise the sum of squared errors (**least squares**).

Worked example: x = prior violations (1,2,3,4,5), y = violations (2,4,5,4,5).
- mean x = 3, mean y = 4. Slope b1 = sum((x-3)(y-4)) / sum((x-3)²) = 6 / 10 = **0.6**. Intercept b0 = 4 - 0.6 x 3 = **2.2**.
- Predictions: 2.8, 3.4, 4.0, 4.6, 5.2. Residuals (y - prediction): -0.8, 0.6, 1.0, -0.6, -0.2.
- SSE = 2.4, SST = 6, so **R-squared = 1 - 2.4/6 = 0.60**; MAE = 0.64; RMSE = sqrt(2.4/5) = 0.69.

### Multiple regression
y = b0 + b1 x1 + b2 x2 + ... . Categorical variables become 0/1 **dummy columns (one-hot encoding)**. My model has about 102 columns after encoding (facility type, risk, inspection type, month, weekday, ZIP, prior result, prior violation count).

### Metrics
| Metric | Meaning |
|---|---|
| **MAE** | average absolute error, in violations |
| **RMSE** | root of average squared error, penalises big misses |
| **R-squared** | share of the variation explained (0 = no better than the average; 1 = perfect) |

### Assumptions and diagnostics I ran
- **Multicollinearity (VIF):** predictors highly correlated with each other make coefficients unstable. VIF above 5 is a warning; only 5 of 102 features were above 5.
- **Heteroscedasticity (Breusch-Pagan test):** the error variance should be constant. The test showed it is not, so p-values and confidence intervals should be read with care.
- **Outliers:** 1.9% of points produced 25% of the squared error (a few inspections with very many violations).
- **Train vs test:** train R-squared 0.25, test 0.12 (a gap that suggests over-fitting and a change between years).

### My results
Baseline (always predict the training average): MAE 2.71, R-squared about 0. Multiple linear regression: MAE **2.45**, RMSE 3.28, R-squared **0.12**. **Interpretation:** a modest gain; most of the variation in violations is not explained by information available before the visit.

### Likely questions
- *R-squared is only 0.12. Is the model useless?* It beats the baseline, but it shows the outcome is mostly driven by things not in the data (what the inspector actually finds). That is an honest result.
- *What is leakage and how did you prevent it?* Using information the model would not have at prediction time. I use only earlier inspections for history features and I never use the current result or band; the split is chronological (train 2022-2024, test 2025).
- *Why not use R-squared alone?* It does not tell the size of errors in real units; MAE does.
- *Why one-hot encode?* A regression needs numbers; one-hot avoids inventing an order between categories.
- *What does a coefficient mean?* Holding the other features fixed, one unit increase changes the predicted violation count by that coefficient.
- *Is the target a count? Why not Poisson regression?* Violation counts are non-negative integers, so Poisson or negative binomial regression is a natural extension; the project asks for linear regression, so I kept it and report the limits.

---

## Part 5. Other advanced topics in the project (so you are not surprised)

| Topic | One-sentence explanation | Where |
|---|---|---|
| **Window functions** (`lag`, running count) | Compute a value from earlier rows of the same group without collapsing rows; I used them to get each facility's *previous* inspection. | `sql/08_analytics_mart.sql` |
| **Stored procedure (PL/pgSQL)** | A program stored in the database; one procedure does the whole load so it is atomic and repeatable. | `sql/02_load_batch.sql` |
| **Transaction / atomic load** | All-or-nothing: if a load fails midway, nothing changes. | `etl/fault_test.py` |
| **Idempotent load** | Loading the same month twice adds nothing, because already-loaded IDs are rejected. | `run_etl.py` |
| **ROLLUP / CUBE / GROUPING SETS** | SQL for subtotals at several levels (CUBE = all combinations). | `sql/07_olap_queries.sql` |
| **Sharding and hash distribution (Citus)** | Rows are spread over shards by a hash of the distribution key; queries run on all shards in parallel and are merged. | Part D |
| **Shard skew** | If one shard gets many more rows, it becomes the bottleneck; I measured max/mean = 1.10 for FacilityKey. | Part D |
| **Kafka topic, partition, offset** | A log of events split into partitions; consumers remember how far they have read (offset), so they can resume. | Part E |
| **Windowing and watermark (Spark)** | Group events into time windows (10 s); the watermark says how late data may arrive before a window is finalised. | `spark_stream.py` |
| **Dead-letter table** | Where invalid events are stored with a reason instead of being lost. | Part E |
| **ClickHouse MergeTree** | A column-oriented table engine for fast aggregation; ReplacingMergeTree removes duplicate rows during background merges. | Part E |
| **Chronological split / leakage** | Train on the past, test on the future, so the evaluation is realistic. | Parts G, I |

If a professor goes deeper than you can answer: *"That detail is beyond what I implemented, but my understanding is ..."* then say the one sentence from this table. Do not guess numbers; open `results/` or the report.

---

## Part 6. 15-minute study plan for today
1. **10 min:** Part 1 table and the 5-basket example (redo the count of support, confidence, lift once with a pen).
2. **10 min:** Part 2: draw the FP-tree from memory once.
3. **10 min:** Part 3: entropy/Gini, ID3 vs C4.5 vs CART table, the three metrics, and the threshold story.
4. **10 min:** Part 4: redo the 5-point regression (slope 0.6, R-squared 0.6) and say what MAE/R-squared mean.
5. **5 min:** the 10 numbers in `Presenter_Guide.pdf`, Part 4.
6. **5 min:** read Part 5's table once.
