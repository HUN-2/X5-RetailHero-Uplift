# Who Should We Persuade?

**Loyalty Point Usage and Heterogeneous Marketing Effects**  
X5 RetailHero | CRM uplift modeling and targeting strategy | Personal data analytics portfolio

**[▶ Explore the interactive Tableau Story](https://public.tableau.com/app/profile/sanghun.kim7566/viz/WhoShouldWePersuadeCRMUpliftAnalysis/S01_CRM_Targeting_Story)**  
[View analysis code and documentation](https://github.com/HUN-2/X5-RetailHero-Uplift/tree/main/analysis) · [Download the packaged Tableau workbook](tableau/workbook/Who_Should_We_Persuade_public.twbx)

> **Decision in brief:** Targeting customers solely by predicted purchase probability may miss customers with larger *observed differences* between SMS-treated and untreated purchase rates. On the internal test set, a T-Learner ranked candidate customers more effectively than a propensity baseline at a fixed 20% reach. This is evidence for an **online randomized pilot**, not proof of incremental sales or ROI.

## 1. Business question

If SMS delivery has a cost, *who should we contact?* A customer likely to purchase is not necessarily a customer whose probability of purchase increases substantially after receiving SMS. This project asks whether **past loyalty point usage** is associated with heterogeneous SMS responses, then compares targeting policies at an equal audience size.

## 2. Dataset and workflow

- **Dataset:** [X5 RetailHero uplift modeling competition](https://ods.ai/competitions/x5-retailhero-uplift-modeling/data). Source data are obtained separately; this repository does **not** redistribute the original customer-level dataset.
- **Cohort:** 200,039 customers with treatment/outcome labels; 245 excluded for a first-redemption date preceding first-issue date; **199,794** retained for exploratory/customer-feature analyses.
- **Historical transactions:** 45,786,568 product-level rows; transformed into transaction-level histories, removing 56 customer-transaction combinations associated with 28 reused transaction IDs. Customer-level purchase frequency, spending, recency, and point-use transaction rate were generated.
- **Core behavior metric:** `any_point_use_rate` = number of historical purchase transactions where either point type was used / number of historical purchase transactions.
- **Evaluation split:** Train **119,876**, Validation **39,959**, internal Test **39,959**. Candidate models were developed/selected before scoring the internal Test.
- **Tools:** Google BigQuery (SQL), DuckDB, Python (statistical modeling/uplift evaluation), Tableau (interactive storytelling).

## 3. Key findings

### Behavioral heterogeneity — exploratory analysis

The 0–5% point-use group had a **84.39%** purchase rate among untreated customers and an **adjusted SMS–control difference of +1.29 percentage points**, while the >20% group had **43.54%** and **+6.95 pp**, respectively. These estimates are covariate-adjusted and are **not** the same as unadjusted group differences. Point usage is an *observed consumer behavior*, not a direct measure of reward sensitivity, price sensitivity, or other psychological traits.

### Internal Test — matched targeting reach of 20% (7,992 selected customers)

| Selection strategy | Observed SMS–control difference | Scenario-estimated extra conversions |
|:--|--:|--:|
| Purchase propensity | +1.45 pp | 115.8 |
| Point-use rate rule | +5.07 pp | 405.2 |
| **T-Learner** | **+7.00 pp** | **559.4** |

At the same reach, T-Learner minus propensity was **+5.55 pp** (paired bootstrap 95% CI **[+3.37, +8.15] pp**, 600 bootstrap iterations), corresponding to approximately **444 more scenario-estimated conversions**. T-Learner minus the simple point-use rule was **+1.93 pp**, but its CI **[-0.56, +4.55] pp** includes zero; superiority over the rule is therefore not established.

**Qini area above random baseline (non-normalized implementation):** propensity **-58.80**, point-use rule **+46.25**, T-Learner **+115.85**. These are *area scores*, not percentages.

## 4. Tableau story

**Who Should We Persuade?** is a 4-scene story, saved at 1200 × 900 px:

1. Campaign Overview — overall SMS/control conversion-rate difference
2. Customer Insights — purchase propensity versus behavioral heterogeneity
3. Targeting Performance — three policies, reach-dependent metrics
4. Business Decision — paired bootstrap comparisons, Qini, pilot proposal

**[Open the published interactive Story on Tableau Public](https://public.tableau.com/app/profile/sanghun.kim7566/viz/WhoShouldWePersuadeCRMUpliftAnalysis/S01_CRM_Targeting_Story)** to explore the four scenes and adjust the *Target Reach* control. The [packaged Tableau workbook](tableau/workbook/Who_Should_We_Persuade_public.twbx) is also available for reproducibility and includes four aggregate Hyper extracts. The workbook copy removes local computer directory paths from its metadata. The published web view was supplied by the author; independently inspecting all interactive web behavior and the complete embedded extract rows remains outside this repository-level QA.

## 5. Reproducibility and repository layout

```text
sql/                         # BigQuery data-quality, cohort, EDA queries (6 scripts)
analysis/                    # Python preprocessing, modeling, evaluation (13 scripts)
tableau/
  data/
    09_test_targeting_kpis.csv
    09_test_strategy_differences_bootstrap.csv
    09_test_qini_summary.csv
  workbook/
    Who_Should_We_Persuade_public.twbx
scripts/
  verify_public_results.py   # Public aggregate-result QA
figures/                     # Optional dashboard screenshots
docs/                        # Methods, reproducibility, publication checklist
requirements.txt             # Python dependencies
.gitignore                   # Raw data and customer-level files excluded
```

This repository now contains the SQL/Python analysis scripts, reviewed aggregate exports and packaged Story workbook. **Raw input files are not included**: obtain them separately from the dataset owner, follow [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md), and review data/credentials locally. Because the large raw files are not included here, **the full end-to-end pipeline has not been rerun independently in this publication package**. STEP 13 transformations have been checked against the supplied real STEP 9 aggregate input files; the additional Korean label column in `13_strategy_difference_ci.csv` matches Tableau's packaged schema without changing any numeric results.

Quick check of the public aggregate exports:

```bash
python scripts/verify_public_results.py
```

## 6. How to read the KPIs

- **Selected customers:** the number selected *by a simulated ranking policy*, not the number actually sent SMS in the test dataset.
- **Observed uplift (pp):** observed SMS-treated customer conversion rate minus observed untreated customer conversion rate within the selected group.
- **Scenario-estimated extra conversions:** selected customer count × observed uplift (pp) / 100. This is **not** a counted number of purchases caused by SMS.
- **Target reach:** population share ranked highest by each policy, not an established profit-maximizing reach.

## 7. Limitations and next step

The dataset's actual campaign assignment mechanism, SMS contents, commercial margins, and sending costs are not established here. The exploratory heterogeneity analysis preceded a later internal holdout split, so the internal Test is **not a completely untouched external confirmation** of every exploratory decision. Claims of causal treatment effects or realized ROI require stronger design verification and a prospective randomized holdout.

**Recommended next action:** pilot T-Learner targeting against the simple point-usage rule and existing propensity selection with randomized untreated holdouts, measuring incremental conversions, campaign cost, and practical model complexity before scaling.

## Data sources

- [Official X5 RetailHero competition/data](https://ods.ai/competitions/x5-retailhero-uplift-modeling/data)
- [X5 RetailHero public dataset index](https://huggingface.co/datasets/pytorch-lifestream/retailhero-uplift/tree/main/data)

*Portfolio study; not affiliated with or endorsed by X5 Retail Group.*
