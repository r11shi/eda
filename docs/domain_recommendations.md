# Final Domain Recommendations for the Public-Health Department

Each recommendation points to the finding or experiment that supports it (`docs/ten_findings.md`, notebooks 07-09, `docs/architecture_comparison.md`).

## Operations
1. **Triage complaint inspections first.** Full complaint inspections fail 37.6% of the time against 25.0% for routine canvass inspections (finding 5).
2. **Keep the short re-inspection cycle and escalate repeat failures.** After a failed inspection the next visit passes 79.4% of the time, on average 13 days later; the 12.9% that fail again belong on an escalation list (finding 8).
3. **Set 10 or more violations as an automatic follow-up trigger.** 69% of these inspections end in a fail, three times the normal rate; 43% do at 6-9 violations (finding 9).
4. **Use the failure rate to target outreach, and the failure count to size capacity.** ZIP codes 60617, 60620, 60628, 60619 and 60636 have the highest rates (31-37%); 60614, 60608 and 60617 have the most failures (finding 7).
5. **Base inspector training and owner guidance on the five most cited violations,** which are about premises and cleanliness (rules 55, 47, 49, 10 and 51) and appear in 21-67% of all inspections (finding 6).
6. **Plan capacity on a steady workload of about 1,300-1,650 inspections a month,** because there is no stable seasonal peak (finding 1).
7. **Do not rely on the risk category alone to predict failure.** The fail rate is about the same for high, medium and low risk (finding 4).

## Using predictions
8. **Use the models only as a ranking aid.** The failure tree has an AUC of 0.64 and the violation regression an R-squared of 0.12; together with the facility's history and inspector judgement they can help to order the work, but not to decide a result (finding 10).

## Data and platform
9. **Improve the data at the source:** record the time of day of each inspection, keep violations as a separate table (one row per violation) so that rule-level analysis is possible, use a stable establishment identifier for every record (210 records have licence 0), and remove the undocumented risk code `All`.
10. **Build on a batch warehouse first** and add streaming and distribution only when a real need appears (`docs/architecture_comparison.md`).
