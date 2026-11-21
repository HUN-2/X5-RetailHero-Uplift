# Final publication QA — 2026-11-22

## Source and scope

- Previous `X5-RetailHero-Uplift_GitHub_Prep(1).zip`: 6 BigQuery SQL scripts, 13 Python scripts and 4 reviewed aggregate CSVs.
- Current supplied final `Who Should We Persuade.twbx` plus 3 actual STEP 9 summary CSVs, integrated from the verified add-on copy.
- Final package: 7 reviewed aggregate Tableau CSVs, code, docs and workbook. No source/customer-level data copied into the repository.

## Validation

- Public STEP 9 KPI rows: 15 = 3 strategies × 5 audience sizes; observed lift and estimated scenario-conversion arithmetic checked.
- Paired bootstrap comparisons: 3 strategy pairs and 600 bootstrap iterations; observed difference reconciles with 20% KPI values.
- Qini summary: 3 strategies and numeric area scores.
- STEP 13 exporter: actual STEP 9 input files used to recreate D04 tables and compare output metrics with the published aggregates. An existing Tableau schema-only `comparison_ko` field was added to both the CSV and the export script; no underlying metrics changed.
- Tableau TWBX archive ZIP integrity, Story 4 captions, 1200 × 900 size, 14 sheets, 4 aggregate Hyper files and source field names checked. Removed original absolute local data-source directory paths from workbook XML.
- Workbook/extract field schemas have no customer ID column. Extract row payloads were not exhaustively decoded with Tableau Hyper API; an application-level open/privacy test remains before broad publication.
- Python syntax compilation, source file scan and `.gitignore` policy checked.

## Scope of reproducibility

The local Python and SQL code can be reviewed and the supplied aggregate CSVs cross-checked without source data. Full reconstruction of all metrics from the original large raw dataset has **not** been rerun for this release. STEP 10 Tableau aggregation depends on private customer-level and model output inputs and remains a prepared derivation rather than end-to-end independently replicated analysis.

## Publication state

Uploaded to the `main` branch of the **private** GitHub repository [`HUN-2/X5-RetailHero-Uplift`](https://github.com/HUN-2/X5-RetailHero-Uplift) on 2026-11-22. Repository tree and all 37 file contents were checked against the final ZIP using a matching Git tree SHA (`50205736cdca94db53cc75351bdebb45be77b5e6`). A missing `.gitignore` was added via a separate commit. **The repository has not been made public.** Tableau Desktop/Public application-level open/privacy checks remain before changing visibility.
