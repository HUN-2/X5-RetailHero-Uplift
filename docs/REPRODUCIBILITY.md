# Reproducibility and data lineage

## Dataset and grain

- Public source: https://ods.ai/competitions/x5-retailhero-uplift-modeling/data
- Campaign analysis sample: 199,794 cleaned customers (from original 200,039 training customer IDs; 245 anomalous first-use dates excluded).
- Purchase feed: 45,786,568 product/SKU rows; 8,045,229 customer–transaction groups before conservative ambiguity exclusion; 8,045,173 after excluding 56 groups whose transaction IDs were reused across clients.
- Selected feature cutoff: 2019-03-18, the last recorded purchase date, **not a verified SMS-send date**.
- D01 / D03 / D04: 39,959 internal test customers; D02: all cleaned 199,794.

## Execution sequence and file dependencies

| Step | Script | Local inputs | Outputs |
|:--|:--|:--|:--|
| 1–3 | `sql/01_data_quality.sql`, `02_baseline_eda.sql`, `03_cleaned_customers.sql` | BigQuery raw `uplift_train`, `clients` | BigQuery `cleaned_customers` |
| 4 | `analysis/04_purchases_quality.py`, `04_full_transaction_validation.py`, `04_create_transactions.py` | private `purchases.csv.gz` | private `retailhero.duckdb` / `transactions_clean` |
| 5 | `analysis/05_create_customer_features.py` | DuckDB `transactions_clean` | DuckDB customer features and private CSV |
| 5 | `sql/05_analysis_customers.sql` | BigQuery `cleaned_customers`, uploaded customer features | BigQuery `analysis_customers` |
| 6 | `sql/06_exploratory_analysis.sql`, `sql/06_segment_uplift_counts.sql` | BigQuery `analysis_customers` | group summaries and balance diagnostics |
| 6 | `analysis/06_test_uplift_heterogeneity.py` | published historic group-count constants | heterogeneity/pairwise summaries (`analysis/results/`) |
| 7 | `analysis/07_prepare_model_data.py` | private clients/uplift_train CSVs + DuckDB features | private `07_analysis_model_data.csv` |
| 7 | `analysis/07_adjusted_uplift_logistic.py` | private `07_analysis_model_data.csv` | `analysis/results/07_adjusted_uplift_by_segment.csv` and regression diagnostics |
| 7 | `analysis/07_continuous_point_interaction.py` | private `07_analysis_model_data.csv` | continuous interaction diagnostics |
| 8 | `analysis/08_targeting_benchmark.py` | private `07_analysis_model_data.csv` | private `08_test_predictions_LOCAL_ONLY.csv`; validation selection summary |
| 9 | `analysis/09_targeting_policy_evaluation.py` | private scores + selected strategy | `09_test_targeting_kpis.csv`; bootstrap + Qini outputs |
| 10 | `analysis/10_export_tableau_segments.py` | private 07 model data + 07 adjusted output | public aggregated D02 CSV |
| 13 | `analysis/13_export_tableau_data.py` | STEP 9 bootstrap + Qini summaries | D04 CSVs in `analysis/results` (review then copy into `tableau/data`) |

**Important:** Python scripts retain original *step-based, single-folder input conventions*. Place raw inputs in `analysis/` locally, not in the repository. `analysis/results/` is intentionally ignored.

## Included verified artifacts

- Existing final-step scripts and static aggregates copied from conversation files; source scripts were syntax-compiled when preparing this package.
- `10_customer_insights_segments.csv`: five aggregated behavioral segments from previously verified user results.
- `13_strategy_difference_ci.csv` and `13_qini_area_summary.csv`: original D04 public aggregate inputs.
- Newly added `sql/06_segment_uplift_counts.sql` and `analysis/10_export_tableau_segments.py` are **prepared derivations**, not independently checked against a full raw-data pipeline. Do not present their correctness as tested end-to-end.
- `tableau/data/09_test_targeting_kpis.csv`, `09_test_strategy_differences_bootstrap.csv`, and `09_test_qini_summary.csv` **included**, supplied as actual STEP 9 aggregate exports. Their arithmetic, comparison reconciliation, and lengths were validated.
- Latest four-scene Story-containing `.twbx` **included** at `tableau/workbook/Who_Should_We_Persuade_public.twbx` (1200 × 900); metadata/embedded-aggregate schema and ZIP integrity were inspected. Full Tableau application-level open-test remains outstanding.
- STEP 13 D04 CSV format was aligned with Tableau's existing aggregate extract by adding a descriptive Korean comparison label; numeric estimates are unchanged. STEP 13 conversion was checked using the supplied STEP 9 bootstrap and Qini summary CSVs. The entire original-data-to-model workflow was not rerun here.

## Evaluation definition

- Stratified, non-overlapping 60/20/20 customer train / validation / internal-test split (seed 42); strategy selected on validation at top 20%.
- T-Learner: two HistGradientBoostingClassifier models trained by treatment arm; score is `p_sms − p_control`.
- Purchase propensity baseline: predicted control-arm purchase probability (`p_control`).
- Point-rate rule: fraction of historical purchase transactions using any points.
- At top-k selected customers, the observed difference is \(\mathrm{CVR}_{SMS} - \mathrm{CVR}_{control}\), computed within the selected set.
- The estimated extra conversions use `n_selected × observed_diff`; 20% / T-Learner = 7,992 × 7.00% ≈ 559.4 (statistical scenario, not observed sales).
- Bootstrap comparison draws are paired by resampling the same treatment-stratified customer sample for all strategies (600 replicates), **without refitting the predictive models**.
- Qini is the area of the cumulative estimated SMS-scale gain over the straight random ranking line; this is an unnormalized test-sample-specific quantity.

## Data privacy and publication

Before committing any file, verify that it contains **only aggregated rows and no customer IDs**. Never commit `purchases.csv.gz`, `uplift_train.csv`, `clients.csv`, `07_analysis_model_data.csv`, `08_test_predictions_LOCAL_ONLY.csv`, customer feature exports, DuckDB files, credentials, or raw archives. The `.gitignore` is defense-in-depth, not a substitute for reviewing Git status before pushing. In particular, `.twbx` can contain an embedded Hyper extract: review packaged data, dashboard tooltips, custom SQL, and source paths before public publishing.

## Causal language

Uplift is the convention used for the observed SMS–control difference and the T-Learner ranking score. The retrospective evaluation cannot by itself confirm a causal incremental purchase effect without additional treatment assignment and design assumptions, nor does it supply observed profit/ROI.
