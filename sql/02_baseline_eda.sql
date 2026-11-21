-- X5 RetailHero | STEP 2
-- SMS 발송 여부별 구매율 비교
-- 대상: 최초 사용일이 최초 발급일보다 빠른 고객 제외
-- 원본 테이블 변경 없음

SELECT
    u.treatment_flg,
    COUNT(*) AS customer_count,
    COUNTIF(u.target = 1) AS purchase_count,
    ROUND(
        SAFE_DIVIDE(COUNTIF(u.target = 1), COUNT(*)) * 100,
        2
    ) AS purchase_rate_pct
FROM `x5-retailhero-analysis.x5_retailhero.uplift_train` AS u
INNER JOIN `x5-retailhero-analysis.x5_retailhero.clients` AS c
    ON u.client_id = c.client_id
WHERE
    c.first_redeem_date IS NULL
    OR c.first_redeem_date >= c.first_issue_date
GROUP BY u.treatment_flg
ORDER BY u.treatment_flg;

-- 실행 결과 (2026-11-15)
-- treatment_flg = 0 | customer_count = 99950 | purchase_count = 60316 | purchase_rate_pct = 60.35
-- treatment_flg = 1 | customer_count = 99844 | purchase_count = 63570 | purchase_rate_pct = 63.67
-- 전체 = 199794명 | 제외 고객 = 245명
-- 정확한 차이 = 3.323%p | Python 통계 검정 대상
