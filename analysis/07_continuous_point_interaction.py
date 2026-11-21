"""STEP 7-4 | 포인트 사용률 연속변수 기반 SMS 상호작용 민감도 분석."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy.special import expit
from scipy.stats import norm


# 입력 파일 및 결과 폴더
ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "07_analysis_model_data.csv"
RESULTS = ROOT / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

if not SOURCE.is_file():
    raise FileNotFoundError(f"고객별 데이터 파일 없음: {SOURCE}")

# 필수 변수 확인
columns = [
    "treatment_flg", "target", "any_point_use_rate", "transaction_count",
    "total_purchase_sum", "days_since_last_purchase", "age_clean",
    "redeem_history_before_cutoff",
]
df = pd.read_csv(SOURCE, usecols=columns)
if len(df) != 199_794:
    raise ValueError(f"분석 고객 수 불일치: {len(df):,}")
if df.drop(columns="age_clean").isna().any().any():
    raise ValueError("연령 이외 변수에서 결측 발견")
if not df["treatment_flg"].isin([0, 1]).all() or not df["target"].isin([0, 1]).all():
    raise ValueError("SMS 및 전환 라벨은 0 또는 1 필요")
if not df["any_point_use_rate"].between(0, 1).all():
    raise ValueError("포인트 사용률 범위 오류: 0~1 필요")
if (df["transaction_count"] < 1).any():
    raise ValueError("구매 거래 수의 범위 오류")
if (df["total_purchase_sum"] < 0).any() or (df["days_since_last_purchase"] < 0).any():
    raise ValueError("구매 금액 또는 구매 최근성에 음수 발견")

# 10%p 단위 변환: 0.1 포인트 사용률 변화 = 1 단위
# 해석 예: 0.05(5%) -> point_use_10pp 0.5
point_use = df["any_point_use_rate"]
df["point_use_10pp"] = 10.0 * point_use

# 기존 STEP 7-2와 동일한 공변량 처리
age_median = float(df["age_clean"].median())
df["age_missing"] = df["age_clean"].isna().astype(int)
df["age_filled"] = df["age_clean"].fillna(age_median)
df["log_transaction_count"] = np.log1p(df["transaction_count"])
df["log_total_purchase_sum"] = np.log1p(df["total_purchase_sum"])

# SMS × 연속 포인트 사용률 상호작용
formula = (
    "target ~ treatment_flg * point_use_10pp"
    " + log_transaction_count + log_total_purchase_sum"
    " + days_since_last_purchase + age_filled + age_missing"
    " + redeem_history_before_cutoff"
)
model = smf.glm(formula, data=df, family=sm.families.Binomial())
fit = model.fit(cov_type="HC3", maxiter=100)
if not fit.converged:
    raise RuntimeError("이항 로지스틱 회귀 수렴 실패")

# 상호작용 계수 검정: 로그 오즈 척도, 포인트 사용률 10%p 증가당
term = "treatment_flg:point_use_10pp"
if term not in fit.params.index:
    raise RuntimeError("예상 상호작용 계수 부재")
b_int = float(fit.params[term])
se_int = float(fit.bse[term])
p_int = float(fit.pvalues[term])
ci_b = (b_int - 1.96 * se_int, b_int + 1.96 * se_int)

# 계수 표: 로지스틱 계수 및 오즈비
coef_df = pd.DataFrame({
    "term": fit.params.index,
    "log_odds_coef": fit.params.to_numpy(dtype=float),
    "robust_se": fit.bse.to_numpy(dtype=float),
    "odds_ratio": np.exp(fit.params.to_numpy(dtype=float)),
    "ci_95_lower_odds_ratio": np.exp(fit.params.to_numpy(dtype=float) - 1.96 * fit.bse.to_numpy(dtype=float)),
    "ci_95_upper_odds_ratio": np.exp(fit.params.to_numpy(dtype=float) + 1.96 * fit.bse.to_numpy(dtype=float)),
    "p_value": fit.pvalues.to_numpy(dtype=float),
})
coef_df.to_csv(RESULTS / "07_continuous_coefficients.csv", index=False, encoding="utf-8-sig")

# 공통 고객 구성에서의 예측확률 표준화
# 모든 고객의 기타 공변량은 그대로 유지, 포인트 사용률과 SMS 조건만 변경
beta = fit.params.to_numpy(dtype=float)
V = fit.cov_params().to_numpy(dtype=float)
names = list(fit.params.index)
idx_t = names.index("treatment_flg")
idx_p = names.index("point_use_10pp")
idx_int = names.index(term)
base = np.asarray(model.exog, dtype=float)


def standardized_at(point_fraction):
    """주어진 포인트 사용률에서 평균 예측확률, Uplift, 델타 방법 기울기."""
    point_scaled = 10.0 * point_fraction
    X0 = base.copy()
    X0[:, idx_t] = 0.0
    X0[:, idx_p] = point_scaled
    X0[:, idx_int] = 0.0

    # SMS 조건만 변경한 두 가지 가상 예측
    eta0 = X0 @ beta
    eta1 = eta0 + beta[idx_t] + beta[idx_int] * point_scaled
    p0 = expit(eta0)
    p1 = expit(eta1)

    # 델타 방법: 예측확률 차이의 표준오차
    # X1 = X0 + SMS 열의 1 + 상호작용 열의 현재 포인트 사용률
    w0 = p0 * (1.0 - p0)
    w1 = p1 * (1.0 - p1)
    g0 = (X0.T @ w0) / len(df)
    g1 = (X0.T @ w1) / len(df)
    g1[idx_t] += w1.mean()
    g1[idx_int] += point_scaled * w1.mean()
    grad = g1 - g0

    rd = float(np.mean(p1 - p0))
    se = float(np.sqrt(max(grad @ V @ grad, 0.0)))
    return {
        "point_use_rate_pct": 100.0 * point_fraction,
        "control_pred_rate_pct": 100.0 * float(p0.mean()),
        "sms_pred_rate_pct": 100.0 * float(p1.mean()),
        "adjusted_uplift_pp": 100.0 * rd,
        "ci_95_lower_pp": 100.0 * (rd - 1.96 * se),
        "ci_95_upper_pp": 100.0 * (rd + 1.96 * se),
    }, grad


# 표시 범위: 0~20%, 원본 분포의 상위 10% 전후까지
curve_rows = []
grads = {}
for pct in range(0, 21):
    row, grad = standardized_at(pct / 100.0)
    curve_rows.append(row)
    grads[pct] = grad
curve = pd.DataFrame(curve_rows)
curve.to_csv(RESULTS / "07_continuous_uplift_curve.csv", index=False, encoding="utf-8-sig")

# 0% 대비 20%에서 Uplift의 변화: 확률척도 추가 점검
r0 = curve.iloc[0]["adjusted_uplift_pp"] / 100.0
r20 = curve.iloc[20]["adjusted_uplift_pp"] / 100.0
contrast = float(r20 - r0)
g_contrast = grads[20] - grads[0]
se_contrast = float(np.sqrt(max(g_contrast @ V @ g_contrast, 0.0)))
p_contrast = float(2.0 * norm.sf(abs(contrast / se_contrast))) if se_contrast > 0 else np.nan

# 분석 요약 수치
summary = pd.DataFrame([
    {"metric": "customer_rows", "value": len(df)},
    {"metric": "age_missing_imputed", "value": int(df["age_missing"].sum())},
    {"metric": "point_rate_median_pct", "value": 100.0 * float(point_use.median())},
    {"metric": "point_rate_p90_pct", "value": 100.0 * float(point_use.quantile(0.90))},
    {"metric": "logit_interaction_coef_per_10pp", "value": b_int},
    {"metric": "logit_interaction_or_per_10pp", "value": float(np.exp(b_int))},
    {"metric": "logit_interaction_ci_lower_or", "value": float(np.exp(ci_b[0]))},
    {"metric": "logit_interaction_ci_upper_or", "value": float(np.exp(ci_b[1]))},
    {"metric": "logit_interaction_p", "value": p_int},
    {"metric": "adjusted_uplift_at_0pct_pp", "value": 100.0 * r0},
    {"metric": "adjusted_uplift_at_20pct_pp", "value": 100.0 * r20},
    {"metric": "adjusted_uplift_20minus0_pp", "value": 100.0 * contrast},
    {"metric": "adjusted_uplift_20minus0_ci_lower_pp", "value": 100.0 * (contrast - 1.96 * se_contrast)},
    {"metric": "adjusted_uplift_20minus0_ci_upper_pp", "value": 100.0 * (contrast + 1.96 * se_contrast)},
    {"metric": "adjusted_uplift_20minus0_p", "value": p_contrast},
])
summary.to_csv(RESULTS / "07_continuous_sensitivity_summary.csv", index=False, encoding="utf-8-sig")

# 그래프 1: 동일한 고객 구성을 기준으로 한 예측 구매율
fig, ax = plt.subplots(figsize=(9.5, 5.7))
ax.plot(curve["point_use_rate_pct"], curve["control_pred_rate_pct"], marker="o", markevery=5, label="Control (no SMS)")
ax.plot(curve["point_use_rate_pct"], curve["sms_pred_rate_pct"], marker="o", markevery=5, label="SMS")
ax.set_xlabel("Prior point-usage transaction rate (%)")
ax.set_ylabel("Covariate-standardized predicted purchase rate (%)")
ax.set_title("Predicted purchase rates by continuous point-usage rate")
ax.set_xticks([0, 5, 10, 15, 20])
ax.legend()
ax.grid(alpha=0.2)
fig.tight_layout()
fig.savefig(RESULTS / "07_continuous_response_curves.png", dpi=180)
plt.close(fig)

# 그래프 2: 조정된 구매율 차이와 95% 신뢰구간
fig, ax = plt.subplots(figsize=(9.5, 5.7))
x = curve["point_use_rate_pct"].to_numpy(dtype=float)
y = curve["adjusted_uplift_pp"].to_numpy(dtype=float)
lo = curve["ci_95_lower_pp"].to_numpy(dtype=float)
hi = curve["ci_95_upper_pp"].to_numpy(dtype=float)
ax.plot(x, y, marker="o", markevery=5, label="Adjusted SMS uplift")
ax.fill_between(x, lo, hi, alpha=0.2, label="95% CI (delta method)")
ax.axhline(0, linestyle="--", linewidth=1)
ax.set_xlabel("Prior point-usage transaction rate (%)")
ax.set_ylabel("Predicted SMS purchase-rate difference (percentage points)")
ax.set_title("Continuous point usage and modeled SMS uplift")
ax.set_xticks([0, 5, 10, 15, 20])
ax.legend()
ax.grid(alpha=0.2)
fig.tight_layout()
fig.savefig(RESULTS / "07_continuous_uplift_curve.png", dpi=180)
plt.close(fig)

print("[STEP 7-4 | 연속 포인트 사용률 × SMS 상호작용]")
print(f"customer_rows: {len(df)}")
print(f"model_converged: {fit.converged}")
print(f"point_use_rate_median: {100.0 * point_use.median():.2f}%")
print(f"point_use_rate_p90: {100.0 * point_use.quantile(.9):.2f}%")
print(f"logit_interaction_coef_per_10pp: {b_int:+.6f}")
print(f"logit_interaction_or_per_10pp: {np.exp(b_int):.4f}")
print(f"logit_interaction_p: {p_int:.6g}")
print("\n[같은 고객 구성에서 표준화한 SMS 전환율 차이]")
for pct in [0, 5, 10, 15, 20]:
    r = curve.iloc[pct]
    print(
        f"point_use={pct:>2}%: uplift={r['adjusted_uplift_pp']:+.2f}%p "
        f"95%CI=[{r['ci_95_lower_pp']:.2f}, {r['ci_95_upper_pp']:.2f}]"
    )
print("\n[0% 대비 20% 포인트 사용률에서의 Uplift 차이]")
print(f"uplift_20minus0_pp: {100.0 * contrast:+.3f}")
print(f"uplift_20minus0_ci_95_pp: [{100.0 * (contrast - 1.96 * se_contrast):.3f}, {100.0 * (contrast + 1.96 * se_contrast):.3f}]")
print(f"uplift_20minus0_p: {p_contrast:.6g}")
print(f"results_dir: {RESULTS}")
print("validation: PASS")
