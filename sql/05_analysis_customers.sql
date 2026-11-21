-- STEP 5-3 | 고객 정보와 구매 행동 피처 결합
-- BigQuery Standard SQL
-- 프로젝트: x5-retailhero-analysis
-- 데이터셋: x5_retailhero

-- STEP 5-3-1 | 고객별 구매 피처 매칭 검증
SELECT
    COUNT(*) AS total_customers,
    COUNT(DISTINCT c.client_id) AS unique_customers,
    COUNTIF(f.client_id IS NOT NULL) AS matched_customers,
    COUNTIF(f.client_id IS NULL) AS unmatched_customers
FROM `x5-retailhero-analysis.x5_retailhero.cleaned_customers` AS c
LEFT JOIN `x5-retailhero-analysis.x5_retailhero.customer_purchase_features` AS f
USING (client_id);

-- STEP 5-3-2 | 최종 분석 고객 테이블 생성
CREATE OR REPLACE TABLE `x5-retailhero-analysis.x5_retailhero.analysis_customers` AS
SELECT
    c.*,
    f.* EXCEPT (client_id)
FROM `x5-retailhero-analysis.x5_retailhero.cleaned_customers` AS c
LEFT JOIN `x5-retailhero-analysis.x5_retailhero.customer_purchase_features` AS f
USING (client_id);

-- STEP 5-3-3 | 최종 분석 데이터 품질 확인
SELECT
    COUNT(*) AS total_customers,
    COUNT(DISTINCT client_id) AS unique_customers,
    COUNTIF(transaction_count IS NULL) AS missing_purchase_features,
    SUM(transaction_count) AS total_transactions,
    SUM(any_point_use_transactions) AS point_use_transactions,
    MIN(any_point_use_rate) AS min_point_use_rate,
    MAX(any_point_use_rate) AS max_point_use_rate,
    COUNTIF(days_since_last_point_use IS NULL) AS customers_without_point_use
FROM `x5-retailhero-analysis.x5_retailhero.analysis_customers`;

-- STEP 5-3-3 | 실행 결과 (2026-11-15)
-- total_customers: 199794
-- unique_customers: 199794
-- missing_purchase_features: 0
-- total_transactions: 4022321
-- point_use_transactions: 251096
-- min_point_use_rate: 0.0
-- max_point_use_rate: 1.0
-- customers_without_point_use: 78084
