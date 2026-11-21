"""X5 RetailHero | STEP 2 — 구매율 차이 검정"""

from statsmodels.stats.proportion import (
    proportions_ztest,
    confint_proportions_2indep,
)

# SMS 발송(1), 미발송(0) 집계값
purchase_count = [63570, 60316]
customer_count = [99844, 99950]

# 표본 확인
assert sum(customer_count) == 199794
assert all(0 <= x <= n for x, n in zip(purchase_count, customer_count))

rate_sent = purchase_count[0] / customer_count[0]
rate_unsent = purchase_count[1] / customer_count[1]
rate_diff_pp = (rate_sent - rate_unsent) * 100

# 독립된 두 비율의 양측 z 검정
z_stat, p_value = proportions_ztest(
    count=purchase_count,
    nobs=customer_count,
    alternative="two-sided",
)

# 구매율 차이의 95% 신뢰구간 — Newcombe 방법
ci_lower, ci_upper = confint_proportions_2indep(
    count1=purchase_count[0],
    nobs1=customer_count[0],
    count2=purchase_count[1],
    nobs2=customer_count[1],
    compare="diff",
    method="newcomb",
    alpha=0.05,
)

print(f"발송 구매율: {rate_sent * 100:.3f}%")
print(f"미발송 구매율: {rate_unsent * 100:.3f}%")
print(f"관찰된 구매율 차이: +{rate_diff_pp:.3f}%p")
print(f"z 통계량: {z_stat:.3f}")
print(f"양측 p-value: {p_value:.3e}")
print(f"95% 신뢰구간: [{ci_lower * 100:.3f}, {ci_upper * 100:.3f}]%p")

# 해석 참고: 차이의 유의성 != 인과효과 확정
# 인과 해석: 처치 배정 방식 및 실험 설계 검토 필요
