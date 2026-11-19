# Guide 3: Decision Trees (ID3, C4.5, CART) in simple words
**Part I of the project (and Assignment 6).** No background needed. After this guide you can explain how a tree learns, why we prune it, and read every number in the results.

---

## 1. What is a decision tree?
**A decision tree is a flowchart of yes/no questions that ends in a prediction.** It is exactly like the game "20 questions".

Our question: **will this inspection FAIL?** (yes/no). This is **classification** (predict a category), unlike regression (predict a number).

A tiny piece of our real tree, in plain words:
```
Was the previous inspection a Fail?
 ├─ No → Is this a Complaint inspection?
 │         ├─ Yes → Did the previous inspection have more than 6 violations?
 │         │          ├─ Yes → ... more than 147 days since the last visit? → FAIL RATE 55-58%
 ...
 └─ Yes → ...  (a quick re-inspection soon after a fail) → FAIL RATE only 4-5%
```
- The boxes with questions are **nodes**. The first one is the **root**.
- The last boxes with an answer are **leaves**.
- Each leaf says "% of inspections here that failed". We predict "fail" when that share is high.

**Why trees are popular:** you can read them. A manager can follow the path and understand the reason.

## 2. How does the tree choose its questions?
It tries all possible questions and picks the one that makes the groups **purest**. A "pure" group is one where almost everyone has the same answer (nearly all pass, or nearly all fail).

### Measuring mixture (impurity)
Two common measures. Both are **0 for a pure group** and **largest for a 50/50 mix**.

- **Gini** = 1 − (share of class A)² − (share of class B)²
- **Entropy** = −Σ share × log₂(share)

**Example group:** 9 inspections pass, 5 fail (14 in total).
- Share pass = 9/14 = 0.643, share fail = 5/14 = 0.357.
- Gini = 1 − 0.413 − 0.128 = **0.459**
- Entropy = **0.940**
A group of 14 passes only would have Gini 0 and entropy 0.

### Information gain (used by ID3)
> Gain = impurity before the split − weighted average impurity after the split

The question with the **biggest gain** wins. Classic textbook example (the "play tennis" table, 9 yes / 5 no): splitting by *Outlook* gives gain **0.247**, *Humidity* 0.152, *Wind* 0.048, *Temperature* 0.029. So the root is **Outlook**. Then the process repeats inside each branch until the groups are pure or a stop rule applies.

## 3. ID3, C4.5 and CART: what is the difference?

| | **ID3** | **C4.5** | **CART** |
|---|---|---|---|
| Split score | Information gain (entropy) | **Gain ratio** (gain divided by how many pieces the split makes) | **Gini** |
| Branches | one per category (many) | one per category, or a threshold for numbers | always **two** (yes/no) |
| Numbers (like age) | no, categories only | yes (picks a threshold) | yes (picks a threshold) |
| Missing values | no | yes | yes |
| Pruning | none | yes (pessimistic pruning) | yes (cost-complexity pruning) |
| Also does regression? | no | no | yes |

**Why gain ratio?** Information gain likes attributes with many values (like an ID number, which splits into pure single-case groups but is useless). C4.5 divides by the number of pieces to fix this.

**In the project:** the Python library scikit-learn builds **CART**, so our tree is CART. (In Assignment 6 I also wrote ID3 and C4.5 from scratch to compare.)

## 4. Overfitting and pruning (very important)
If you let the tree keep asking questions until every leaf is pure, it **memorises** the old data. It scores nearly perfectly on the old data and badly on new data. That is **over-fitting**.

**Our evidence:** a fully grown tree had a training score (AUC) of **0.995** but a validation score of only **0.525**, almost random.

**Pruning means stopping the tree from growing too much.** We used four controls:
| Control | Meaning |
|---|---|
| `max_depth` | Maximum number of questions in a row |
| `min_samples_split` | A group needs at least this many cases before it can be split |
| `min_samples_leaf` | Every leaf must keep at least this many cases |
| `ccp_alpha` (cost-complexity pruning) | Penalty for each extra leaf; a bigger value gives a smaller tree |

**How we chose them:** we split time into three parts:
- **Train 2022–2023**: build the tree.
- **Validation 2024**: try many settings and pick the best one.
- **Test 2025**: use **once** at the end for the honest score.

Chosen settings: **max_depth 8, min_samples_split 200, min_samples_leaf 200**. Validation AUC was 0.636, and many settings gave about the same, so the choice is not fragile. Finally we refitted on 2022–2024 and tested on 2025.

**Leakage:** we did not use the current violation count or result (they are only known after the visit and decide the outcome). We used only facts known before the visit: facility type, risk, inspection type, month, area, and **history** (previous result, previous violation count, days since the previous inspection, number of earlier inspections).

## 5. How good is a classifier? The confusion matrix

Every prediction is one of four kinds:
| | Predicted FAIL | Predicted PASS |
|---|---|---|
| **Really failed** | **TP** (caught) | **FN** (missed) |
| **Really passed** | **FP** (false alarm) | **TN** (correct) |

| Measure | Formula in words | Meaning |
|---|---|---|
| **Accuracy** | correct predictions / all | Be careful: 79% of inspections pass, so "always say pass" scores 79%! |
| **Precision** | TP / (TP + FP) | Of those I called fail, how many really failed |
| **Recall** | TP / (TP + FN) | Of the real fails, how many did I catch |
| **F1** | mix of precision and recall | One balanced number |
| **ROC-AUC** | chance that a random failed inspection gets a higher fail-score than a random passed one | 0.5 = coin flip, 1.0 = perfect |

### Our test results (2025: 16,052 inspections, 3,391 real fails)
| Version | TP | FN | FP | TN | Accuracy | Precision | Recall | AUC |
|---|---|---|---|---|---|---|---|---|
| Always "pass" (lazy baseline) | 0 | 3,391 | 0 | 12,661 | 0.789 | 0 | 0 | 0.50 |
| Tree, normal cut-off 0.5 | 131 | 3,260 | 214 | 12,447 | 0.784 | 0.38 | **0.04** | 0.635 |
| Tree, tuned cut-off 0.217 | 2,071 | 1,320 | 5,093 | 7,568 | 0.600 | 0.29 | **0.61** | 0.635 |

**How to explain this:**
- The tree gives each inspection a **fail probability**. The **cut-off (threshold)** decides when we say "fail".
- At the normal cut-off 0.5 the tree almost never says "fail" (recall only 4%). Failures are the minority (about 21%), so the probability rarely passes 50%.
- We chose a lower cut-off (0.217) **using the validation year**. Now the tree catches 61% of real fails, but raises many false alarms (precision 29%), and accuracy drops. That is the **trade-off**: catch more fails or avoid false alarms. The right choice depends on what a missed fail costs.
- **AUC 0.635** does not change with the cut-off. It says the ranking ability is **weak**.

## 6. What did the tree learn?
Most important inputs (share of the tree's decisions):
| Input | Importance |
|---|---|
| Previous result was a Fail | 29% |
| Inspection type = Complaint | 15% |
| Previous violation count | 13% |
| Days since the previous inspection | 10% |
| ZIP 60617, Re-inspection type, School | about 4–5% each |

**Three actual paths (from the notebook):**
- **Highest risk:** previous result not a fail, complaint inspection, previous count above 6, and more than 147 days since the last visit → **55–58% fail**.
- **Lowest risk:** previous result was a fail, but now a quick re-check (within 36 days), few earlier violations, few earlier inspections → only **4–5% fail** (follow-ups work).
- **Largest group:** about 10,757 ordinary inspections → about **27% fail** (close to the average).

**Conclusion to say:** the past is the best clue (a previous fail, a complaint, a long gap), but overall the tree is a **weak** predictor (AUC 0.64). It can help to **rank** which inspections deserve attention first, never to decide a result.

## 7. Words to remember
| Word | Meaning |
|---|---|
| Node / root / leaf | A question / the first question / a final answer |
| Split | A yes/no question on one input |
| Impurity (Gini, entropy) | How mixed a group is |
| Information gain | How much a split reduces impurity |
| Gain ratio | Gain corrected for splits with many branches (C4.5) |
| Over-fitting | Memorising the training data |
| Pruning | Limiting or trimming the tree |
| Threshold / cut-off | Probability above which we say "fail" |
| Validation set | Data used to choose settings |
| Test set | Data used once for the final score |

## 8. Five sentences you can say
1. "A decision tree asks yes/no questions and each leaf gives a fail probability."
2. "scikit-learn builds CART trees using Gini; ID3 uses information gain and C4.5 uses gain ratio."
3. "I controlled over-fitting with depth and leaf-size limits chosen on the 2024 validation year, and tested only once on 2025."
4. "AUC is 0.64, so it ranks inspections only weakly; with the tuned cut-off it catches 61% of fails but has many false alarms."
5. "The most important clues are a previous fail, a complaint inspection and a long gap since the last visit."
