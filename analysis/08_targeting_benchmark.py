"""STEP 8 | X5 CRM 타깃팅 전략 비교: 구매확률, 포인트 규칙, T-Learner.

로컬 입력: 07_analysis_model_data.csv (STEP 7-1 결과)
외부 공개 불가: 고객별 예측 파일 및 분할 원자료
실험 설계: train 60% / validation 20% / test 20%, seed=42
모델 선택: validation top-20% 관찰 Uplift, 최종 test 성과 보고
"""

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score


ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "07_analysis_model_data.csv"
OUT = ROOT / "results"
OUT.mkdir(parents=True, exist_ok=True)
SEED = 42
TOP_K = (0.10, 0.20, 0.30, 0.50, 1.00)
STRATEGIES = ("purchase_propensity", "point_rate_rule", "uplift_t_learner")
EXPECTED_N = 199_794
FEATURES = (
    "log_transaction_count",
    "log_total_purchase_sum",
    "log_avg_purchase_sum",
    "log_point_use_transactions",
    "any_point_use_rate",
    "regular_use_rate",
    "express_use_rate",
    "days_since_last_purchase",
    "days_since_last_point_use",
    "age_clean",
    "age_missing",
    "redeem_history_before_cutoff",
)
RAW = (
    "client_id", "treatment_flg", "target",
    "transaction_count", "total_purchase_sum", "avg_purchase_sum",
    "any_point_use_transactions", "any_point_use_rate",
    "regular_use_rate", "express_use_rate", "days_since_last_purchase",
    "days_since_last_point_use", "age_clean", "redeem_history_before_cutoff",
)


def load_data() -> pd.DataFrame:
    # 입력 파일 및 필수 열 확인
    if not INPUT.is_file():
        raise FileNotFoundError(f"STEP 7-1 입력 CSV를 찾을 수 없음: {INPUT}")
    data = pd.read_csv(INPUT, usecols=list(RAW), dtype={"client_id": "string"})
    if len(data) != EXPECTED_N or data["client_id"].nunique() != EXPECTED_N:
        raise ValueError(f"행 수 또는 고객 중복 오류: {len(data):,}")
    if data["treatment_flg"].isna().any() or data["target"].isna().any():
        raise ValueError("처치 또는 구매 결과 결측")
    if not data["treatment_flg"].isin((0, 1)).all():
        raise ValueError("treatment_flg 값이 0/1이 아님")
    if not data["target"].isin((0, 1)).all():
        raise ValueError("target 값이 0/1이 아님")
    core = ["transaction_count", "total_purchase_sum", "avg_purchase_sum",
            "any_point_use_transactions", "any_point_use_rate",
            "regular_use_rate", "express_use_rate", "days_since_last_purchase",
            "redeem_history_before_cutoff"]
    if data[core].isna().any().any():
        raise ValueError("연령/최근 포인트 사용일 이외의 설명변수에 결측")
    if ((data["transaction_count"] <= 0)
            | (data["total_purchase_sum"] < 0)
            | (data["avg_purchase_sum"] < 0)
            | (data["any_point_use_transactions"] < 0)
            | (~data["any_point_use_rate"].between(0, 1))
            | (~data["regular_use_rate"].between(0, 1))
            | (~data["express_use_rate"].between(0, 1))
            | (data["days_since_last_purchase"] < 0)).any():
        raise ValueError("주요 구매/포인트 변수의 범위 오류")
    # 로그 변환 및 연령 결측 표시
    for orig, new in (
        ("transaction_count", "log_transaction_count"),
        ("total_purchase_sum", "log_total_purchase_sum"),
        ("avg_purchase_sum", "log_avg_purchase_sum"),
        ("any_point_use_transactions", "log_point_use_transactions"),
    ):
        data[new] = np.log1p(data[orig].to_numpy(dtype=float))
    data["age_missing"] = data["age_clean"].isna().astype(int)
    # HGB 분류기는 최근 포인트 사용일/연령 결측을 자체 처리
    if data[list(FEATURES)].replace([np.inf, -np.inf], np.nan).isna().sum().sum() != (
        data["age_clean"].isna().sum() + data["days_since_last_point_use"].isna().sum()
    ):
        raise ValueError("허용된 두 변수 이외에 결측 또는 무한값")
    return data


def partition(data: pd.DataFrame):
    # 고객 단위 비중복 분리: 처치×구매결과 분포 층화
    strata = data["treatment_flg"].astype(str) + "_" + data["target"].astype(str)
    trainval_idx, test_idx = train_test_split(
        np.arange(len(data)), test_size=0.20, stratify=strata, random_state=SEED,
    )
    train_idx, valid_idx = train_test_split(
        trainval_idx, test_size=0.25, stratify=strata.iloc[trainval_idx], random_state=SEED + 1,
    )
    pieces = {
        "train": data.iloc[train_idx].copy().reset_index(drop=True),
        "validation": data.iloc[valid_idx].copy().reset_index(drop=True),
        "test": data.iloc[test_idx].copy().reset_index(drop=True),
    }
    ids = [set(v["client_id"]) for v in pieces.values()]
    if len(set.union(*ids)) != len(data) or any(ids[i] & ids[j] for i in range(3) for j in range(i + 1, 3)):
        raise RuntimeError("학습/검증/평가 고객 중복")
    summary = []
    for name, subset in pieces.items():
        summary.append({
            "split": name,
            "customers": len(subset),
            "control": int((subset["treatment_flg"] == 0).sum()),
            "sms": int((subset["treatment_flg"] == 1).sum()),
            "control_cvr_pct": 100 * subset.loc[subset["treatment_flg"] == 0, "target"].mean(),
            "sms_cvr_pct": 100 * subset.loc[subset["treatment_flg"] == 1, "target"].mean(),
        })
    pd.DataFrame(summary).to_csv(OUT / "08_split_summary.csv", index=False, encoding="utf-8-sig")
    return pieces


def make_model() -> HistGradientBoostingClassifier:
    # 동일한 알고리즘/설정으로 처치군 및 대조군 학습
    return HistGradientBoostingClassifier(
        learning_rate=0.07,
        max_iter=110,
        max_leaf_nodes=16,
        min_samples_leaf=80,
        l2_regularization=5.0,
        early_stopping=False,
        random_state=SEED,
    )


def fit_scores(pieces):
    # T-Learner: SMS=0, SMS=1 별도의 구매확률 모델
    train = pieces["train"]
    train_x = train.loc[:, list(FEATURES)].astype("float32")
    y = train["target"].to_numpy(dtype=int)
    t = train["treatment_flg"].to_numpy(dtype=int)
    m0, m1 = make_model(), make_model()
    print("model_training: control purchase probability")
    m0.fit(train_x.loc[t == 0], y[t == 0])
    print("model_training: SMS purchase probability")
    m1.fit(train_x.loc[t == 1], y[t == 1])

    scores = {}
    for name in ("validation", "test"):
        sub = pieces[name]
        x = sub.loc[:, list(FEATURES)].astype("float32")
        p0 = m0.predict_proba(x)[:, 1]
        p1 = m1.predict_proba(x)[:, 1]
        scores[name] = {
            "purchase_propensity": p0,
            "point_rate_rule": sub["any_point_use_rate"].to_numpy(dtype=float),
            "uplift_t_learner": p1 - p0,
        }
        if not all(np.isfinite(a).all() for a in scores[name].values()):
            raise RuntimeError(f"예측 점수 오류: {name}")
    ctrl_test = pieces["test"].loc[pieces["test"]["treatment_flg"] == 0]
    test_auc = roc_auc_score(ctrl_test["target"], m0.predict_proba(ctrl_test[list(FEATURES)].astype("float32"))[:, 1])
    return scores, test_auc


def rank_order(score: np.ndarray) -> np.ndarray:
    # 동일 점수는 고정 난수로 순서 결정: 고객 결과와 무관한 타이브레이크
    tie = np.random.default_rng(SEED).random(len(score))
    return np.lexsort((tie, -score))


def metrics_by_topk(sub: pd.DataFrame, score: np.ndarray, model: str, part: str):
    t = sub["treatment_flg"].to_numpy(dtype=int)
    y = sub["target"].to_numpy(dtype=int)
    ix = rank_order(score)
    n = len(sub)
    full_control_rate = float(y[t == 0].mean())
    full_sms_rate = float(y[t == 1].mean())
    random_lift = full_sms_rate - full_control_rate
    output = []
    for f in TOP_K:
        n_sel = min(n, max(1, int(np.ceil(n * f))))
        select = ix[:n_sel]
        t_s, y_s = t[select], y[select]
        nt = int(t_s.sum())
        nc = n_sel - nt
        if min(nt, nc) < 30:
            raise RuntimeError(f"평가 대상 처치군/대조군 수 부족: {model}, {part}, {f}")
        p1 = float(y_s[t_s == 1].mean())
        p0 = float(y_s[t_s == 0].mean())
        rd = p1 - p0
        se = float(np.sqrt(p1 * (1 - p1) / nt + p0 * (1 - p0) / nc))
        extra = n_sel * rd
        output.append({
            "split": part,
            "strategy": model,
            "top_fraction": f,
            "selected_customers": n_sel,
            "sms_in_selected": nt,
            "control_in_selected": nc,
            "sms_cvr_pct": 100 * p1,
            "control_cvr_pct": 100 * p0,
            "uplift_at_k_pp": 100 * rd,
            "ci95_lower_pp": 100 * (rd - 1.96 * se),
            "ci95_upper_pp": 100 * (rd + 1.96 * se),
            "estimated_extra_conversions": extra,
            "estimated_extra_conversions_per_1000": 1000 * rd,
            "random_baseline_uplift_pp": 100 * random_lift,
            "difference_vs_random_pp": 100 * (rd - random_lift),
        })
    return output


def cumulative_curve(sub: pd.DataFrame, score: np.ndarray, name: str):
    # 발송 상위 k명 모두에게 적용할 경우의 누적 기대 추가 전환
    idx = rank_order(score)
    tt = sub["treatment_flg"].to_numpy(dtype=int)[idx]
    yy = sub["target"].to_numpy(dtype=int)[idx]
    nt = np.cumsum(tt == 1)
    nc = np.cumsum(tt == 0)
    yt = np.cumsum((tt == 1) & (yy == 1))
    yc = np.cumsum((tt == 0) & (yy == 1))
    n = len(tt)
    positions = np.unique(np.r_[np.arange(500, n + 1, 500), n])
    rows = [{"strategy": name, "target_fraction": 0., "estimated_extra_conversions": 0.}]
    for k in positions:
        if nt[k - 1] < 30 or nc[k - 1] < 30:
            continue
        rd = yt[k - 1] / nt[k - 1] - yc[k - 1] / nc[k - 1]
        rows.append({"strategy": name, "target_fraction": k / n,
                     "estimated_extra_conversions": k * rd})
    return rows


def charts(test_metrics: pd.DataFrame, curves: pd.DataFrame, test_n: int, random_rd: float):
    # 그림 1: 발송 비중에 따른 누적 기대 추가 전환
    fig, ax = plt.subplots(figsize=(10, 6))
    for name in STRATEGIES:
        part = curves.loc[curves["strategy"] == name]
        ax.plot(100 * part["target_fraction"], part["estimated_extra_conversions"], label=name)
    ax.plot([0, 100], [0, test_n * random_rd], linestyle="--", label="random targeting baseline")
    ax.set(xlabel="Share of customers targeted (%)", ylabel="Estimated incremental conversions",
           title="STEP 8 | Targeting efficiency on retrospective holdout")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "08_incremental_conversion_curve.png", dpi=170)
    plt.close(fig)

    # 그림 2: 상위 k% 대상 관찰 전환율 차이
    fig, ax = plt.subplots(figsize=(10, 5.6))
    for name in STRATEGIES:
        part = test_metrics.loc[(test_metrics["strategy"] == name) & (test_metrics["top_fraction"] < 1)]
        ax.plot(100 * part["top_fraction"], part["uplift_at_k_pp"], marker="o", label=name)
    ax.axhline(100 * random_rd, linestyle="--", label="overall test uplift")
    ax.set(xlabel="Share of customers targeted (%)", ylabel="Observed uplift in top-k (pp)",
           title="STEP 8 | Uplift@k by targeting strategy")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "08_uplift_at_k.png", dpi=170)
    plt.close(fig)


def main():
    data = load_data()
    pieces = partition(data)
    print("[STEP 8 | 고객 분리 검증]")
    for part, sub in pieces.items():
        print(f"{part}: n={len(sub):,}, SMS={int(sub['treatment_flg'].sum()):,}, "
              f"control={int((sub['treatment_flg']==0).sum()):,}")
    scores, control_auc = fit_scores(pieces)

    all_metrics = {}
    for part in ("validation", "test"):
        entries = []
        for name in STRATEGIES:
            entries.extend(metrics_by_topk(pieces[part], scores[part][name], name, part))
        result = pd.DataFrame(entries)
        result.to_csv(OUT / f"08_{part}_strategy_metrics.csv", index=False, encoding="utf-8-sig", float_format="%.8f")
        all_metrics[part] = result

    # 모델 선택은 validation만 사용 (test 확인 전 결정)
    val20 = all_metrics["validation"].query("top_fraction == 0.20")
    selected = val20.sort_values("uplift_at_k_pp", ascending=False, kind="mergesort").iloc[0]["strategy"]
    test20 = all_metrics["test"].query("top_fraction == 0.20")
    print("\n[STEP 8 | Validation 상위 20% 전략 비교]")
    for r in val20.itertuples():
        print(f"{r.strategy:23s} uplift@20={r.uplift_at_k_pp:+.3f}%p, "
              f"estimated_extra={r.estimated_extra_conversions:+.1f}")
    print(f"selected_strategy_by_validation: {selected}")
    print("\n[STEP 8 | Test 상위 20% 최종 결과]")
    for r in test20.itertuples():
        print(f"{r.strategy:23s} n={r.selected_customers:,}, "
              f"uplift@20={r.uplift_at_k_pp:+.3f}%p "
              f"95%CI=[{r.ci95_lower_pp:+.3f},{r.ci95_upper_pp:+.3f}]%p, "
              f"estimated_extra={r.estimated_extra_conversions:+.1f}")
    print(f"purchase_propensity_control_auc: {control_auc:.4f} (secondary diagnostic)")

    test = pieces["test"]
    t = test["treatment_flg"].to_numpy(dtype=int)
    y = test["target"].to_numpy(dtype=int)
    baseline_rd = float(y[t == 1].mean() - y[t == 0].mean())
    curve_rows = []
    for model in STRATEGIES:
        curve_rows.extend(cumulative_curve(test, scores["test"][model], model))
    curves = pd.DataFrame(curve_rows)
    curves.to_csv(OUT / "08_test_cumulative_targeting_curve.csv", index=False, encoding="utf-8-sig", float_format="%.8f")
    charts(all_metrics["test"], curves, len(test), baseline_rd)

    # 고객별 예측/실제 반응 기록: 로컬 재현 용도, GitHub 업로드 제외
    scores_test = pd.DataFrame({
        "client_id": test["client_id"].astype(str),
        "treatment_flg": t,
        "target": y,
        "score_purchase_propensity": scores["test"]["purchase_propensity"],
        "score_point_rate": scores["test"]["point_rate_rule"],
        "score_uplift_t_learner": scores["test"]["uplift_t_learner"],
    })
    scores_test.to_csv(OUT / "08_test_predictions_LOCAL_ONLY.csv", index=False, encoding="utf-8-sig", float_format="%.8f")
    pd.DataFrame([{
        "selected_strategy_by_validation": selected,
        "validation_selection_top_fraction": 0.20,
        "test_customers": len(test),
        "test_overall_uplift_pp": 100 * baseline_rd,
        "purchase_propensity_control_auc": control_auc,
        "seed": SEED,
        "warning": "Retrospective holdout; prior EDA used full labels; assignment ignorability unverified",
    }]).to_csv(OUT / "08_model_selection_summary.csv", index=False, encoding="utf-8-sig")
    print("\nvalidation: PASS")
    print(f"results_dir: {OUT}")
    print("note: 08_test_predictions_LOCAL_ONLY.csv must NOT be uploaded to GitHub")
    print("note: extra conversions are statistical estimates, NOT observed incremental purchases")


if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        print(f"[STEP 8 error] {type(err).__name__}: {err}", file=sys.stderr)
        raise
