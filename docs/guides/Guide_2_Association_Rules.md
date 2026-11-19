# Guide 2: Association Rules, Apriori and FP-Growth (from zero, in simple words)
**Part H of the project.** No maths background needed. After this guide you can explain support, confidence, lift, Apriori and FP-Growth, and read every rule in the project.

---

## 1. What is it?
**Association rule mining finds things that happen together.**

The famous example is a shop: *"people who buy bread and butter also buy milk"*. The shop owner uses this to arrange shelves and offers.

A **rule** looks like this: **IF (left side) THEN (right side)**, written `X => Y`.

In our project the "shop" is the list of inspections, and the "basket" is **one inspection**. Each inspection has labels (called **items**), for example:

> `FacilityType=Restaurant`, `Risk=High`, `InspectionType=Complaint`, `Season=Summer`, `Area=Southwest`, `Violations=Very High (10+)`, `Result=Fail`

A rule we found: **`Violations=Very High (10+)  =>  Result=Fail`**. Meaning: when an inspection has 10 or more violations, it usually ends in a fail.

**Our data:** 61,185 inspections (baskets), 35 different items, and each inspection has exactly 7 items (one for each of the 7 attributes).
Numbers (like the violation count) cannot be items, so we turned them into **bands**: None (0), Low (1–2), Medium (3–5), High (6–9), Very High (10+).

## 2. The three numbers you must know

Use this tiny shop (5 baskets) for every example in this guide:

| Basket | Items |
|---|---|
| 1 | bread, milk |
| 2 | bread, diaper, beer, eggs |
| 3 | milk, diaper, beer, cola |
| 4 | bread, milk, diaper, beer |
| 5 | bread, milk, diaper, cola |

### Support = "how common is it?"
> support(X) = (baskets containing X) / (all baskets)

- {diaper, beer} appears in baskets 2, 3, 4 = 3 of 5 → **support = 3/5 = 0.60 (60%)**.

Support protects us from rules based on a handful of cases.

### Confidence = "when the left side happens, how often does the right side happen too?"
> confidence(X => Y) = support(X and Y) / support(X)

- Rule `diaper => beer`: diaper is in 4 baskets, and 3 of those also have beer → **confidence = 3/4 = 0.75 (75%)**.

### Lift = "is this more than a coincidence?"
> lift(X => Y) = confidence(X => Y) / support(Y)

- Beer appears in 3 of 5 baskets (60%). Confidence of `diaper => beer` is 75%. So lift = 0.75 / 0.60 = **1.25**.

How to read lift:
| Lift | Meaning |
|---|---|
| **1** | No relation. Y is just as common anyway. |
| **above 1** | Positive link: X makes Y more likely than normal. |
| **below 1** | Negative link: X makes Y less likely. |

**Why lift matters:** if 90% of all inspections pass, then "anything => Pass" will have high confidence, but it tells us nothing new. Lift catches this.
Example from the shop: `bread => milk` has confidence 75%, but milk is in 80% of baskets, so lift = 0.75 / 0.80 = **0.94**: bread buyers are slightly *less* likely than normal to buy milk. High confidence but no real link.

## 3. How do we find the frequent patterns? Apriori

We first need all item sets that are **frequent** (support at least a chosen minimum). Then we make rules from them.

**Apriori's key idea (the Apriori principle):**
> If a set of items is rare, then every bigger set that contains it must also be rare.

So we can skip a huge number of combinations. Steps on the 5-basket shop with **minimum support 60% (at least 3 baskets)**:

**Step 1. Count single items.** bread 4, milk 4, diaper 4, beer 3, cola 2, eggs 1. Keep those with 3 or more: **bread, milk, diaper, beer**. (Cola and eggs are thrown away.)

**Step 2. Make pairs from the survivors and count them.**

| Pair | Baskets | Keep? |
|---|---|---|
| bread + milk | 3 | yes |
| bread + diaper | 3 | yes |
| milk + diaper | 3 | yes |
| diaper + beer | 3 | yes |
| bread + beer | 2 | no |
| milk + beer | 2 | no |

**Step 3. Make triples only from the surviving pairs.** bread + milk + diaper appears in 2 baskets, so it fails. Nothing survives, so we **stop**.

**Step 4. Make rules** from the frequent sets (for example from {diaper, beer}): `diaper => beer` (confidence 75%, lift 1.25) and `beer => diaper` (confidence 100%, lift 1.25).

**Weakness of Apriori:** it scans the data again and again (once for each size) and creates many candidates. With a big list this is slow.

## 4. FP-Growth (the faster way) and the "FP-tree"

**FP-Growth finds the same frequent sets as Apriori, but without creating candidates.** It squeezes the data into a compact tree (the **FP-tree**, "frequent pattern tree") and reads the patterns from the tree. It reads the data only **twice**.

**Steps** (same shop, minimum 3 baskets):

**Pass 1.** Count the items. Keep the frequent ones, ordered by count: bread 4, milk 4, diaper 4, beer 3.

**Pass 2.** For each basket, keep only the frequent items in that order, and add the basket to the tree as a path. Baskets that start with the same items share the same branch, and the numbers on the branch count them.

| Basket | Cleaned and ordered |
|---|---|
| 1 | bread, milk |
| 2 | bread, diaper, beer |
| 3 | milk, diaper, beer |
| 4 | bread, milk, diaper, beer |
| 5 | bread, milk, diaper |

The tree (item:count):

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

**Mine the tree, starting from the rarest item (beer).** Follow every path that ends in beer: {bread, milk, diaper}, {bread, diaper}, {milk, diaper} (each once). Count the items on these paths: diaper 3, bread 2, milk 2. Only diaper reaches 3, so the frequent pair is **{diaper, beer}**. This is the same answer as Apriori, found without listing candidates.

| | Apriori | FP-Growth |
|---|---|---|
| Idea | Build candidates level by level and count them | Compress data into a tree and read patterns from it |
| Scans of the data | many | 2 |
| Speed | slower | faster |
| Result | same | same |

**In our project:** both gave **exactly the same 1,198 frequent item sets**. I used the Python library `mlxtend` (`apriori`, `fpgrowth`, `association_rules`) and timed both.

## 5. Our settings and what we found

- **Minimum support 2%**, **minimum confidence 30%**, we kept rules with **lift ≥ 1.3**.
- The computer produces many rules, including obvious or repeated ones (for example, a rule that only restates the result group). We removed those and kept **14 meaningful rules**.

### The best rules, in plain English
| Rule | Support | Confidence | Lift | What it says |
|---|---|---|---|---|
| Risk=Low => Grocery Store | 2.5% | 62% | 6.5 | Low-risk inspections are mostly grocery stores. |
| **Violations=Very High (10+) => Fail** | 5.4% | **69%** | **3.0** | With 10+ violations, 7 in 10 inspections fail. |
| Restaurant & License inspection & Pass => No violations | 2.2% | 49% | 2.8 | Licence inspections that pass are often completely clean. |
| Restaurant & High risk & No violations => Re-inspection | 4.3% | 50% | 2.1 | Clean results often come from re-inspections: follow-ups work. |
| Fail => Violations High (6–9) | 7.1% | 31% | 1.9 | Failed inspections often sit in the 6–9 band. |
| School => Routine (Canvass) inspection | 5.3% | 73% | 1.4 | Schools are inspected mostly in routine rounds. |

**How to use them (business meaning):** treat 10+ violations as a trigger for an early re-inspection; plan low-risk routes around grocery stores; fast-track licence checks that were clean before.

## 6. Warnings (examiners like these)
- **Association is not cause.** The rule shows two things appear together, not that one causes the other. (Also, a fail is partly *defined* by the violations, so that rule is expected.)
- **Always read support, confidence and lift together.** A rule with high lift but tiny support may be luck.
- **Choose thresholds carefully.** Too low gives thousands of useless rules; too high hides interesting ones.

## 7. Other algorithms (only if asked; they were in Assignment 5)
- **ECLAT:** stores for each item the list of baskets that contain it, and finds common sets by overlapping those lists. No tree, no repeated scans.
- **Multilevel association mining:** uses a hierarchy (for example Restaurant → Food service → All) and finds rules at several levels.

## 8. Words to remember
| Word | Meaning |
|---|---|
| Item | One label, e.g. `Result=Fail` |
| Transaction / basket | One inspection with its 7 items |
| Item set | A group of items |
| Frequent item set | Support at least the minimum |
| Rule | `X => Y`, "if X then Y" |
| Support / Confidence / Lift | How common / how often right / how much more than chance |
| Apriori principle | A rare set cannot have a frequent bigger set |
| FP-tree | The compact tree used by FP-Growth |
| Discretisation | Turning numbers into bands |

## 9. Five sentences you can say
1. "Each inspection is a basket of 7 labels, so I looked for labels that occur together."
2. "Support says how common a pattern is, confidence how often the rule is right, and lift how much better than chance."
3. "Apriori builds candidate sets level by level and prunes rare ones; FP-Growth compresses the data into a tree and avoids candidates."
4. "Both gave the same 1,198 frequent sets, so I used FP-Growth's speed as a cross-check."
5. "The strongest rule is 10 or more violations implies Fail: 69% confidence, lift 3.0."
