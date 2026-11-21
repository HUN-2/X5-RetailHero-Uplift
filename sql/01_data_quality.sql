-- ============================================================
-- X5 RetailHero | 01_data_quality.sql
-- BigQuery GoogleSQL
-- 프로젝트: x5-retailhero-analysis
-- 데이터셋: x5_retailhero
-- 범위: uplift_train, clients 원본 품질 검증
-- 분석 기준일 후보: 2019-03-18 (실제 SMS 발송일 미확인)
-- 제외 기준: first_redeem_date < first_issue_date
-- 실행 방법: STEP별 SELECT 구문만 선택 후 실행
-- 원본 테이블 변경 없음
-- ============================================================

-- STEP 1-1 | 컬럼명, 자료형, NULL 허용 여부
SELECT
    table_name,
    column_name,
    data_type,
    is_nullable
FROM `x5-retailhero-analysis.x5_retailhero.INFORMATION_SCHEMA.COLUMNS`
WHERE table_name IN ('uplift_train', 'clients')
ORDER BY table_name, ordinal_position;


-- STEP 1-2 | uplift_train 중복, 결측, 이진 변수 범위
SELECT
    COUNT(*) AS total_rows,
    COUNT(DISTINCT client_id) AS unique_customers,
    COUNTIF(client_id IS NULL) AS missing_id,
    COUNTIF(treatment_flg IS NULL) AS missing_treatment,
    COUNTIF(target IS NULL) AS missing_target,
    COUNTIF(treatment_flg NOT IN (0, 1)) AS invalid_treatment,
    COUNTIF(target NOT IN (0, 1)) AS invalid_target,
    MIN(treatment_flg) AS min_treatment,
    MAX(treatment_flg) AS max_treatment,
    MIN(target) AS min_target,
    MAX(target) AS max_target
FROM `x5-retailhero-analysis.x5_retailhero.uplift_train`;


-- STEP 1-3 | clients 연령, 날짜, 성별 범위 및 결측
-- 유효 연령 후보: 11~99세
SELECT
    COUNT(*) AS total_rows,
    COUNT(DISTINCT client_id) AS unique_customers,
    COUNTIF(client_id IS NULL) AS missing_id,
    COUNTIF(age IS NULL) AS missing_age,
    MIN(age) AS min_age,
    MAX(age) AS max_age,
    COUNTIF(age <= 10 OR age >= 100) AS age_outside_range,
    COUNTIF(gender IS NULL) AS missing_gender,
    COUNT(DISTINCT gender) AS gender_categories,
    MIN(first_issue_date) AS min_issue_date,
    MAX(first_issue_date) AS max_issue_date,
    MIN(first_redeem_date) AS min_redeem_date,
    MAX(first_redeem_date) AS max_redeem_date,
    COUNTIF(first_issue_date IS NULL) AS missing_issue_date,
    COUNTIF(first_redeem_date IS NULL) AS missing_redeem_date
FROM `x5-retailhero-analysis.x5_retailhero.clients`;


-- STEP 1-4 | 성별 코드 분포
-- U: Unknown 취급 / 주 분석에서 제외
SELECT
    gender,
    COUNT(*) AS customer_count
FROM `x5-retailhero-analysis.x5_retailhero.clients`
GROUP BY gender
ORDER BY customer_count DESC;


-- STEP 1-5 | 학습 고객 연령·최초 사용일 분포
-- 기준일 후보: 2019-03-18
-- 날짜 역전 고객: 기타 분류와 중복 가능
SELECT
    COUNT(*) AS total_customers,
    COUNTIF(c.age <= 10) AS age_10_or_under,
    COUNTIF(c.age BETWEEN 11 AND 99) AS valid_age,
    COUNTIF(c.age >= 100) AS age_100_or_over,
    COUNTIF(c.first_redeem_date IS NULL) AS missing_redeem,
    COUNTIF(DATE(c.first_redeem_date) <= DATE '2019-03-18')
        AS redeem_before_or_on_cutoff,
    COUNTIF(DATE(c.first_redeem_date) > DATE '2019-03-18')
        AS redeem_after_cutoff,
    COUNTIF(c.first_redeem_date < c.first_issue_date)
        AS redeem_before_issue
FROM `x5-retailhero-analysis.x5_retailhero.uplift_train` AS u
LEFT JOIN `x5-retailhero-analysis.x5_retailhero.clients` AS c
    ON u.client_id = c.client_id;


-- STEP 1-6 | 날짜 오류 제외 전후 코호트 수
-- 제외: first_redeem_date < first_issue_date
-- 최초 사용일 NULL: 유지
-- 예상 제외 245명 / 최종 199,794명 (실행 전 미검증)
SELECT
    COUNT(*) AS original_customers,
    COUNTIF(c.first_redeem_date < c.first_issue_date)
        AS excluded_date_error,
    COUNTIF(
        c.first_redeem_date IS NULL
        OR c.first_redeem_date >= c.first_issue_date
    ) AS eligible_customers,
    COUNTIF(c.client_id IS NULL) AS unmatched_customers
FROM `x5-retailhero-analysis.x5_retailhero.uplift_train` AS u
LEFT JOIN `x5-retailhero-analysis.x5_retailhero.clients` AS c
    ON u.client_id = c.client_id;
