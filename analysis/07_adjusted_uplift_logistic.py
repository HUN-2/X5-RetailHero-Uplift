"""STEP 7-2 | 공변량 조정 SMS 효과 이질성: 로지스틱 회귀와 확률척도 효과."""

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import statsmodels.api as sm
import statsmodels.formula.api as smf
from patsy import build_design_matrices, dmatrix
from scipy.special import expit
from scipy.stats import chi2, norm

# 파일 경로
WORK_DIR = Path(__file__).resolve().parent
SOURCE = WORK_DIR / "07_analysis_model_data.csv"
OUTPUT_DIR = WORK_DIR / "results"
OUTPUT_DIR.mkdir(exist_ok=True)

if not SOURCE.is_file():
    raise FileNotFoundError(f"분석용 CSV 파일 없음: {SOURCE}")

# 통계 모델 변수
required_cols = [
    "treatment_flg", "target", "point_segment_id",
    "transaction_count", "total_purchase_sum", "days_since_last_purchase",
    "age_clean", "redeem_history_before_cutoff",
]
df = pd.read_csv(SOURCE, usecols=required_cols)
if len(df) != 199_794:
    raise ValueError(f"고객 수 불일치: {len(df):,}명")
if df[required_cols].isna().drop(columns="age_clean").any().any():
    raise ValueError("연령 외 모델 변수에 결측 발생")
if not df["treatment_flg"].isin([0, 1]).all():
    raise ValueError("SMS 그룹의 0/1 범위 오류")
if not df["target"].isin([0, 1]).all():
    raise ValueError("구매 전환값의 0/1 범위 오류")
if set(df["point_segment_id"].unique()) != {1, 2, 3, 4, 5}:
    raise ValueError("포인트 사용률 그룹의 범주 오류")
if (df["transaction_count"] < 1).any():
    raise ValueError("구매 거래 수의 범위 오류")
if (df["total_purchase_sum"] < 0).any():
    raise ValueError("총구매금액의 음수 발견")
if (df["days_since_last_purchase"] < 0).any():
    raise ValueError("최근 구매 경과일의 음수 발견")

# 연령 결측 처리: 중위수 대체 + 결측 지표
age_median = float(df["age_clean"].median())
df["age_missing"] = df["age_clean"].isna().astype(int)
df["age_filled"] = df["age_clean"].fillna(age_median)

# 치우친 거래 수·금액에 로그 변환
# log1p(x) = log(1 + x)
df["log_transaction_count"] = np.log1p(df["transaction_count"])
df["log_total_purchase_sum"] = np.log1p(df["total_purchase_sum"])

# 이항 로지스틱 회귀: SMS × 포인트 사용률 그룹
# 참조 그룹: 포인트 미사용(point_segment_id=1)
formula = (
    "target ~ treatment_flg * C(point_segment_id, Treatment(reference=1))"
    " + log_transaction_count + log_total_purchase_sum"
    " + days_since_last_purchase + age_filled + age_missing"
    " + redeem_history_before_cutoff"
)
model = smf.glm(formula=formula, data=df, family=sm.families.Binomial())
fit = model.fit(cov_type="HC3", maxiter=100)
if not fit.converged:
    raise RuntimeError("로지스틱 모형 수렴 실패")

# 로지스틱 회귀 상호작용 전체 Wald 검정: 로그 오즈 척도
names = list(fit.params.index)
interaction_terms = [
    name for name in names
    if "treatment_flg:" in name and "point_segment_id" in name
]
if len(interaction_terms) != 4:
    raise RuntimeError(f"상호작용 항 4개 예상, 실제: {interaction_terms}")
R = np.zeros((len(interaction_terms), len(names)))
for i, name in enumerate(interaction_terms):
    R[i, names.index(name)] = 1
logit_test = fit.wald_test(R, scalar=True)

# 그룹별 공변량 표준화: 각 그룹의 실제 사전 특성 분포 기준
# SMS=1 및 SMS=0 가상 예측의 평균 차이 (risk difference)
beta = fit.params.to_numpy(dtype=float)
cov = fit.cov_params().to_numpy(dtype=float)
# 모형식으로부터 예측 설계정보 재구성: statsmodels 버전 차이 회피
# 모든 포인트 사용 범주가 포함된 5행으로 설계정보 생성
representatives = (
    df.groupby("point_segment_id", sort=True)
    .head(1)
    .copy()
)
rhs_formula = formula.split("~", 1)[1].strip()
design_info = dmatrix(
    rhs_formula,
    data=representatives,
    return_type="dataframe",
).design_info
if list(design_info.column_names) != names:
    raise RuntimeError(
        "예측 설계행렬 열 순서 불일치: "
        f"모형={names}, 예측={list(design_info.column_names)}"
    )
segment_labels = {
    1: "0% (미사용)",
    2: "0~5%",
    3: "5~10%",
    4: "10~20%",
    5: "20% 초과",
}
rows = []
gradients = []

for segment_id, label in segment_labels.items():
    sub = df.loc[df["point_segment_id"] == segment_id].copy()
    sms = sub.copy()
    control = sub.copy()
    sms["treatment_flg"] = 1
    control["treatment_flg"] = 0

    X1 = np.asarray(build_design_matrices([design_info], sms)[0], dtype=float)
    X0 = np.asarray(build_design_matrices([design_info], control)[0], dtype=float)
    p1 = expit(X1 @ beta)
    p0 = expit(X0 @ beta)
    adjusted_rd = float(np.mean(p1 - p0))

    # 델타 방법: 조정된 확률 차이의 표준오차
    grad = np.mean(
        (p1 * (1 - p1))[:, None] * X1
        - (p0 * (1 - p0))[:, None] * X0,
        axis=0,
    )
    gradients.append(grad)
    se = float(np.sqrt(max(grad @ cov @ grad, 0)))

    y0 = sub.loc[sub["treatment_flg"] == 0, "target"].mean()
    y1 = sub.loc[sub["treatment_flg"] == 1, "target"].mean()
    rows.append({
        "point_segment": label,
        "customer_count": len(sub),
        "observed_uplift_pp": 100 * float(y1 - y0),
        "adjusted_uplift_pp": 100 * adjusted_rd,
        "ci_95_lower_pp": 100 * (adjusted_rd - 1.96 * se),
        "ci_95_upper_pp": 100 * (adjusted_rd + 1.96 * se),
    })

# 조정된 구매 확률 차이의 집단 간 전체 Wald 검정
# 주의: 각 집단 내 공변량 분포에서 평균한 marginal RD 비교
G = np.vstack(gradients)
D = G[1:] - G[0]
rd = np.array([r["adjusted_uplift_pp"] / 100 for r in rows])
diff = rd[1:] - rd[0]
contrast_cov = D @ cov @ D.T
risk_wald = float(diff @ np.linalg.pinv(contrast_cov) @ diff)
risk_p = float(chi2.sf(risk_wald, 4))

# 결과 저장
segment_df = pd.DataFrame(rows)
segment_df.to_csv(
    OUTPUT_DIR / "07_adjusted_uplift_by_segment.csv",
    index=False, encoding="utf-8-sig", float_format="%.8f",
)
wald_df = pd.DataFrame([
    {
        "test": "logit_interaction_robust_wald",
        "chi_square": float(logit_test.statistic),
        "df": len(interaction_terms),
        "p_value": float(logit_test.pvalue),
    },
    {
        "test": "marginal_risk_difference_heterogeneity_delta_wald",
        "chi_square": risk_wald,
        "df": 4,
        "p_value": risk_p,
    },
])
wald_df.to_csv(
    OUTPUT_DIR / "07_adjusted_heterogeneity_tests.csv",
    index=False, encoding="utf-8-sig", float_format="%.10g",
)
coefs = pd.DataFrame({
    "term": names,
    "coef_log_odds": fit.params.to_numpy(),
    "robust_se": fit.bse.to_numpy(),
    "p_value": fit.pvalues.to_numpy(),
})
coefs.to_csv(
    OUTPUT_DIR / "07_logistic_coefficients.csv",
    index=False, encoding="utf-8-sig", float_format="%.8g",
)

# 조정 효과 그래프
fig, ax = plt.subplots(figsize=(10, 5.6))
levels = np.arange(len(segment_df))
values = segment_df["adjusted_uplift_pp"].to_numpy()
lower = values - segment_df["ci_95_lower_pp"].to_numpy()
upper = segment_df["ci_95_upper_pp"].to_numpy() - values
ax.errorbar(values, levels, xerr=np.vstack([lower, upper]), fmt="o", capsize=4)
ax.axvline(0, linestyle="--", linewidth=1)
# 그래프 축 라벨: 로컬 한글 글꼴 설치 여부와 무관한 영문 표기
chart_labels = ["No prior use", "0-5%", "5-10%", "10-20%", "Over 20%"]
ax.set_yticks(levels, chart_labels)
ax.invert_yaxis()
ax.set_xlabel("Adjusted SMS purchase-rate difference (percentage points)")
ax.set_title("Covariate-adjusted SMS effect by prior point-usage segment")
ax.grid(axis="x", alpha=0.2)
fig.tight_layout()
fig.savefig(OUTPUT_DIR / "07_adjusted_uplift_forest.png", dpi=180)
plt.close(fig)

print("[STEP 7-2 | 로지스틱 회귀: 공변량 조정 효과 이질성]")
print(f"customer_rows: {len(df)}")
print(f"missing_age_imputed: {int(df['age_missing'].sum())}")
print(f"age_median_used: {age_median:.2f}")
print(f"model_converged: {fit.converged}")
print(
    f"logit_interaction_wald_chi2({len(interaction_terms)}): "
    f"{float(logit_test.statistic):.4f}, p={float(logit_test.pvalue):.6g}"
)
print(f"adjusted_risk_diff_wald_chi2(4): {risk_wald:.4f}, p={risk_p:.6g}")
print("\n[집단별 관찰 효과 및 공변량 조정 효과: %p]")
for r in rows:
    print(
        f"{r['point_segment']:<12} n={r['customer_count']:>6,} "
        f"raw={r['observed_uplift_pp']:+.2f} "
        f"adjusted={r['adjusted_uplift_pp']:+.2f} "
        f"95%CI=[{r['ci_95_lower_pp']:.2f}, {r['ci_95_upper_pp']:.2f}]"
    )
print(f"\nresults_dir: {OUTPUT_DIR}")
print("validation: PASS")
