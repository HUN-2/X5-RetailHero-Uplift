-- X5 RetailHero | STEP 6 고객 행동 EDA 및 SMS 사전 특성 균형
-- 실행 환경: Google BigQuery Standard SQL
-- 입력 테이블: x5-retailhero-analysis.x5_retailhero.analysis_customers
-- 분석 단위: 고객 1명당 1행
-- 보관 범위: 실제 실행 및 사용자 검증 완료 STEP 6-1 ~ 6-3-2
-- 실행 방법: 원하는 쿼리 하나씩 선택 실행

-- STEP 6-1 | 고객별 포인트 사용률 분포
SELECT
    COUNT(*) AS total_customers,
    COUNTIF(any_point_use_transactions = 0) AS never_used_customers,
    COUNTIF(any_point_use_transactions > 0) AS ever_used_customers,
    COUNTIF(any_point_use_rate = 1) AS always_used_customers,
    COUNTIF(transaction_count = 1) AS single_transaction_customers,
    ROUND(AVG(transaction_count), 2) AS avg_transaction_count,
    APPROX_QUANTILES(transaction_count, 100)[OFFSET(50)] AS median_transaction_count,
    ROUND(AVG(any_point_use_rate), 4) AS avg_customer_use_rate,
    APPROX_QUANTILES(any_point_use_rate, 100)[OFFSET(25)] AS p25_use_rate,
    APPROX_QUANTILES(any_point_use_rate, 100)[OFFSET(50)] AS median_use_rate,
    APPROX_QUANTILES(any_point_use_rate, 100)[OFFSET(75)] AS p75_use_rate,
    APPROX_QUANTILES(any_point_use_rate, 100)[OFFSET(90)] AS p90_use_rate
FROM `x5-retailhero-analysis.x5_retailhero.analysis_customers`;

-- STEP 6-2 | 구매 거래 수 구간별 포인트 사용 행동
WITH transaction_groups AS (
    SELECT
        client_id,
        transaction_count,
        any_point_use_transactions,
        any_point_use_rate,
        CASE
            WHEN transaction_count = 1 THEN '1'
            WHEN transaction_count BETWEEN 2 AND 4 THEN '2-4'
            WHEN transaction_count BETWEEN 5 AND 9 THEN '5-9'
            WHEN transaction_count BETWEEN 10 AND 19 THEN '10-19'
            WHEN transaction_count BETWEEN 20 AND 49 THEN '20-49'
            ELSE '50+'
        END AS transaction_group
    FROM `x5-retailhero-analysis.x5_retailhero.analysis_customers`
)
SELECT
    transaction_group,
    COUNT(*) AS customer_count,
    ROUND(AVG(transaction_count), 2) AS avg_transaction_count,
    COUNTIF(any_point_use_transactions = 0) AS never_used_customers,
    COUNTIF(any_point_use_transactions = transaction_count) AS always_used_customers,
    ROUND(AVG(any_point_use_rate), 4) AS avg_customer_use_rate,
    ROUND(
        SAFE_DIVIDE(SUM(any_point_use_transactions), SUM(transaction_count)),
        4
    ) AS transaction_weighted_use_rate
FROM transaction_groups
GROUP BY transaction_group
ORDER BY MIN(transaction_count);

-- STEP 6-3-1 | SMS 수신 여부별 사전 고객 특성
SELECT
    treatment_flg,
    COUNT(*) AS customer_count,
    ROUND(AVG(transaction_count), 2) AS avg_transaction_count,
    APPROX_QUANTILES(transaction_count, 100)[OFFSET(50)] AS median_transaction_count,
    ROUND(AVG(any_point_use_rate), 4) AS avg_point_use_rate,
    ROUND(AVG(IF(any_point_use_transactions > 0, 1.0, 0.0)), 4) AS ever_point_use_rate,
    ROUND(AVG(total_purchase_sum), 2) AS avg_total_purchase_sum,
    ROUND(AVG(days_since_last_purchase), 2) AS avg_purchase_recency,
    ROUND(AVG(age_clean), 2) AS avg_age,
    COUNTIF(age_clean IS NULL) AS missing_age,
    ROUND(AVG(redeem_history_before_cutoff), 4) AS redeem_history_rate
FROM `x5-retailhero-analysis.x5_retailhero.analysis_customers`
GROUP BY treatment_flg
ORDER BY treatment_flg;

-- STEP 6-3-2 | SMS 수신 여부별 표준화 평균 차이(SMD)
WITH long_data AS (
    SELECT
        treatment_flg,
        metric.metric_name,
        metric.metric_value
    FROM `x5-retailhero-analysis.x5_retailhero.analysis_customers`
    CROSS JOIN UNNEST([
        STRUCT('transaction_count' AS metric_name, CAST(transaction_count AS FLOAT64) AS metric_value),
        STRUCT('point_use_rate', CAST(any_point_use_rate AS FLOAT64)),
        STRUCT('ever_point_use', IF(any_point_use_transactions > 0, 1.0, 0.0)),
        STRUCT('total_purchase_sum', CAST(total_purchase_sum AS FLOAT64)),
        STRUCT('purchase_recency', CAST(days_since_last_purchase AS FLOAT64)),
        STRUCT('age', CAST(age_clean AS FLOAT64)),
        STRUCT('missing_age', IF(age_clean IS NULL, 1.0, 0.0)),
        STRUCT('redeem_history', CAST(redeem_history_before_cutoff AS FLOAT64))
    ]) AS metric
),
group_stats AS (
    SELECT
        treatment_flg,
        metric_name,
        AVG(metric_value) AS mean_value,
        STDDEV_SAMP(metric_value) AS sd_value
    FROM long_data
    GROUP BY treatment_flg, metric_name
)
SELECT
    c.metric_name,
    ROUND(c.mean_value, 4) AS control_mean,
    ROUND(s.mean_value, 4) AS sms_mean,
    ROUND(
        SAFE_DIVIDE(
            s.mean_value - c.mean_value,
            SQRT((POW(s.sd_value, 2) + POW(c.sd_value, 2)) / 2)
        ),
        4
    ) AS smd
FROM group_stats AS c
JOIN group_stats AS s
    ON c.metric_name = s.metric_name
    AND c.treatment_flg = 0
    AND s.treatment_flg = 1
ORDER BY ABS(smd) DESC;
