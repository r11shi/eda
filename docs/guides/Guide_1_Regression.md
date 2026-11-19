# Guide 1: Regression (from zero, in simple words)
**Part G of the project.** Read this slowly once. You need no maths background. At the end you can explain every number in the regression notebook.

---

## 1. What is regression?
**Regression means: predict a number.**

Examples from daily life: predict a house price from its size, or an exam mark from the hours studied.
In our project: **predict how many violations an inspection will find**, before the inspector arrives.

The idea is simple: look at old cases, find the pattern, then use the pattern on a new case.

## 2. The simplest version: one input, one line

Imagine a graph. Each dot is one old inspection:
- left to right (x): how many violations the **previous** inspection of that restaurant found
- up (y): how many violations **this** inspection found

The dots are scattered, but they slope upwards a bit. Regression draws the **best straight line** through the dots. The line is written as:

> **predicted violations = a + b × (previous violations)**

- **a** (intercept) = the prediction when the previous count is 0.
- **b** (slope) = how much the prediction goes up for each extra previous violation.

**Our real result** (from the notebook):

> **violations = 2.737 + 0.209 × previous violations**

Read it in plain words: *a restaurant with no earlier violations is predicted to get about 2.7 violations. Every extra earlier violation adds about 0.2.* A restaurant that had 10 earlier violations is predicted to get 2.737 + 0.209 × 10 = **4.8**.

### How does it find the "best" line?
It tries lines and keeps the one where the **total of the squared misses** is smallest. A "miss" (called a **residual** or error) is the actual value minus the predicted value. This method is called **least squares**. You do not need to calculate it by hand.

### Tiny example you can redo on paper
| Previous violations (x) | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| Actual violations (y) | 2 | 4 | 5 | 4 | 5 |

- Average x = 3, average y = 4.
- Slope b = 0.6, intercept a = 2.2. So the line is **y = 2.2 + 0.6 x**.
- Predictions: 2.8, 3.4, 4.0, 4.6, 5.2. Misses: -0.8, +0.6, +1.0, -0.6, -0.2.
- The average size of the misses (ignoring + or -) = (0.8+0.6+1.0+0.6+0.2) / 5 = **0.64**. This is the **MAE**.
- **R-squared = 0.60**: the line explains 60% of the ups and downs in y.

## 3. Many inputs: multiple regression
One input is rarely enough. We use eight kinds of input:

| Input | Example |
|---|---|
| Facility type | Restaurant, School, Grocery Store ... |
| Risk category | High, Medium, Low |
| Inspection type | Complaint, Canvass, Re-inspection ... |
| Month, day of week | October, Tuesday |
| ZIP code | 60617 |
| Previous result | Pass / Fail / Pass with conditions / None |
| Previous violation count | 7 |

The line becomes a sum: **prediction = a + b1·(input 1) + b2·(input 2) + ...**. Each input gets its own weight (called a **coefficient**), which the computer finds.

### How do you put words (like "Restaurant") into a sum? One-hot encoding
A computer can only multiply numbers. So each category becomes its own 0/1 column:

| Facility | is_Restaurant | is_School | is_Grocery |
|---|---|---|---|
| Restaurant | 1 | 0 | 0 |
| School | 0 | 1 | 0 |

(We drop one category as the reference, and group very rare categories as "infrequent".) After this step our model has **102 numeric columns**. Do not be scared by 102: it is just the same idea repeated.

## 4. How good is the prediction? Three numbers

| Name | In plain words | Better is |
|---|---|---|
| **MAE** (mean absolute error) | On average, the prediction is this many violations away from the truth. | smaller |
| **RMSE** | Like MAE, but big misses count extra. | smaller |
| **R-squared (R²)** | The share of the ups and downs the model explains. 0 = no better than guessing the average, 1 = perfect. | bigger |

**The baseline** is the lazy model: always predict the average number of violations. A model is only useful if it beats the baseline.

## 5. Why we split the data in time (very important)
We must test the model on inspections it has **never seen**. We trained on **2022–2024** and tested on **2025**. This is a **chronological split**: train on the past, test on the future, like real life.

**Data leakage** means accidentally giving the model information it would not have in real life. Example: if we gave it "the current inspection failed", it would predict violations very well, but that fact is only known after the inspection. So we did **not** use the current result, band or fail flag. For "previous" information we used only **earlier** inspections of the same facility.

## 6. Our results (test year 2025, 15,919 inspections)

| Model | MAE | RMSE | R² |
|---|---|---|---|
| Baseline: always the average | 2.71 | 3.51 | -0.01 |
| Simple line: previous violations only | 2.50 | 3.36 | 0.05 |
| **Multiple regression (final)** | **2.45** | **3.28** | **0.12** |

**What this means (say it in your own words):**
- On average we are off by about **2.45 violations**; the lazy baseline is off by 2.71. So we **improved a little**.
- **R² = 0.12** means the model explains only **12%** of why violation counts differ. The other 88% depends on things the data does not contain (how clean the kitchen is on that day, the staff, the inspector).
- So the honest conclusion: **violations are hard to predict before the visit.** That is a valid finding, not a failure.

**On training data R² was 0.25, on test data 0.12.** The gap means the model fits the past better than the future: some over-fitting, and 2025 behaves a little differently from 2022–2024.

### Which inputs mattered? (largest coefficients)
- Some ZIP codes push the prediction up by a lot: **60617, 60633, 60620, 60636, 60628** (about +3.8 to +4.6 violations compared with the reference ZIP).
- Re-inspections have far fewer violations; complaint inspections have more.
- Very rare facility types (for example "Shared Kitchen User") show large negative numbers, but they have few cases, so do not trust them.

## 7. The checks we ran (and what they mean)

| Check | Question it answers | Our result | Plain meaning |
|---|---|---|---|
| **VIF** (variance inflation factor) | Are some inputs just copies of each other? | Only 5 of 102 had VIF above 5 | Almost no problem. |
| **Breusch-Pagan test** | Are the misses equally spread everywhere? | p-value 0 (the spread is **not** equal) | The model is more wrong for some cases than others; treat confidence intervals with care. |
| **Outliers** | Do a few extreme cases dominate? | 1.9% of inspections have more than 14 violations, causing about 25% of all the squared error | A few terrible inspections hurt the score. |
| **Negative predictions** | Can the model predict nonsense? | 304 of 15,919 predictions were below zero | A count cannot be negative. This is a limit of a straight line. |

## 8. Limits and what you would do next (say this if asked)
- A straight line is not ideal for **counts**. The next step would be **Poisson regression** (made for counts that cannot be negative).
- Important causes (staff training, equipment, kitchen size) are not in the data.
- The model is too weak to decide anything alone. It can only help to **rank** inspections for attention.

## 9. Words to remember
| Word | Meaning |
|---|---|
| Target (y) | What we predict (violation count) |
| Feature / input (x) | What we use to predict |
| Coefficient | Weight of one input |
| Intercept | Prediction when all inputs are 0 |
| Residual | Actual minus predicted |
| Train / test | Learn on one part, check on another |
| Baseline | The lazy "always the average" model |
| Over-fitting | Fits the training data too closely and does worse on new data |
| Leakage | Using information not available at prediction time |

## 10. Five sentences you can say
1. "I used regression to predict how many violations an inspection will find, using only facts known before the visit."
2. "The model has 102 inputs after turning categories into 0/1 columns."
3. "I trained on 2022 to 2024 and tested on 2025, so there is no peeking at the future."
4. "The average error is 2.45 violations against 2.71 for the lazy baseline, and R-squared is 0.12."
5. "That means the outcome is mostly decided by things not in the data, so the model is only a ranking aid."
