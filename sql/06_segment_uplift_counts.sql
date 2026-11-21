-- STEP 6-6-1 | Point-use segments x SMS: counts for heterogeneity test
-- BigQuery Standard SQL. Segment boundaries consistent with STEP 7-1.
-- Output may be exported to supply a non-hardcoded input for analysis/06_test_uplift_heterogeneity.py.
WITH segments AS (
    SELECT
        CASE
            WHEN any_point_use_transactions = 0 THEN 1
            WHEN any_point_use_rate <= 0.05 THEN 2
            WHEN any_point_use_rate <= 0.10 THEN 3
            WHEN any_point_use_rate <= 0.20 THEN 4
            ELSE 5
        END AS segment_order,
        treatment_flg,
        target
    FROM `x5-retailhero-analysis.x5_retailhero.analysis_customers`
), counts AS (
    SELECT segment_order, treatment_flg,
           COUNT(*) AS n, COUNTIF(target = 1) AS purchasers
    FROM segments
    GROUP BY segment_order, treatment_flg
)
SELECT
    c.segment_order,
    CASE c.segment_order
        WHEN 1 THEN 'Never used'
        WHEN 2 THEN '0-5%'
        WHEN 3 THEN '5-10%'
        WHEN 4 THEN '10-20%'
        WHEN 5 THEN 'Over 20%'
    END AS segment_label_en,
    c.n AS n_control, c.purchasers AS y_control,
    s.n AS n_sms, s.purchasers AS y_sms
FROM counts c
JOIN counts s USING (segment_order)
WHERE c.treatment_flg = 0 AND s.treatment_flg = 1
ORDER BY segment_order;
