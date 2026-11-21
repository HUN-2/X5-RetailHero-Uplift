-- X5 RetailHero | STEP 3
-- 정제 고객 테이블 생성 및 검증
-- GoogleSQL (BigQuery)
-- 프로젝트: x5-retailhero-analysis
-- 데이터셋: x5_retailhero
-- 분석 기준일: 2019-03-18 (잠정)
-- 날짜 역전 고객 245명 제외
-- 원본 uplift_train / clients 보존


-- STEP 3-1 | 정제 고객 테이블 생성
-- age_clean: 11~99세만 유지
-- first_redeem_date_pre_cutoff: 잠정 기준일 이후 값 마스킹
-- redeem_history_before_cutoff: 기준일까지 최초 사용 기록 여부

CREATE OR REPLACE TABLE
    `x5-retailhero-analysis.x5_retailhero.cleaned_customers`
AS
SELECT
    u.client_id,
    u.treatment_flg,
    u.target,
    CASE
        WHEN c.age BETWEEN 11 AND 99 THEN c.age
        ELSE NULL
    END AS age_clean,
    c.first_issue_date,
    CASE
        WHEN DATE(c.first_redeem_date) <= DATE '2019-03-18'
        THEN c.first_redeem_date
        ELSE NULL
    END AS first_redeem_date_pre_cutoff,
    CASE
        WHEN DATE(c.first_redeem_date) <= DATE '2019-03-18'
        THEN 1
        ELSE 0
    END AS redeem_history_before_cutoff
FROM `x5-retailhero-analysis.x5_retailhero.uplift_train` AS u
INNER JOIN `x5-retailhero-analysis.x5_retailhero.clients` AS c
    ON u.client_id = c.client_id
WHERE
    c.first_redeem_date IS NULL
    OR c.first_redeem_date >= c.first_issue_date;


-- STEP 3-2 | 정제 고객 테이블 품질 확인
-- 예상 결과: 고객 199794명, 고유 고객 199794명
-- 확인 결과: 연령 결측 733명, 최초 사용 기록 159648명, 미래 날짜 0건

SELECT
    COUNT(*) AS total_customers,
    COUNT(DISTINCT client_id) AS unique_customers,
    COUNTIF(age_clean IS NULL) AS missing_age_clean,
    COUNTIF(redeem_history_before_cutoff = 1)
        AS customers_with_redeem_history,
    COUNTIF(
        DATE(first_redeem_date_pre_cutoff) > DATE '2019-03-18'
    ) AS future_date_errors
FROM `x5-retailhero-analysis.x5_retailhero.cleaned_customers`;


-- STEP 3-3 | 정제 테이블 구매율 재현
-- 미발송: 99950명 / 구매 60316명 / 60.35%
-- 발송: 99844명 / 구매 63570명 / 63.67%

SELECT
    treatment_flg,
    COUNT(*) AS customer_count,
    COUNTIF(target = 1) AS purchase_count,
    ROUND(100 * AVG(target), 2) AS purchase_rate_pct
FROM `x5-retailhero-analysis.x5_retailhero.cleaned_customers`
GROUP BY treatment_flg
ORDER BY treatment_flg;
