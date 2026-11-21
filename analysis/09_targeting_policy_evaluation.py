"""STEP 9 | CRM 타깃팅 정책: 발송 규모별 성과, Qini, 전략 간 부트스트랩 비교.

입력: STEP 8의 results/08_test_predictions_LOCAL_ONLY.csv
      results/08_model_selection_summary.csv
출력: results/09_*.csv, results/09_*.png
주의: 관찰된 전환율 차이에 기반한 추정. 실제 증분구매·매출의 관측값 아님.
"""
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "results"
PREDICTIONS = OUT / "08_test_predictions_LOCAL_ONLY.csv"
SELECTION = OUT / "08_model_selection_summary.csv"
SEED = 42
BOOT_SEED = 20261115
N_BOOTSTRAP = 600
TARGET_FRACTIONS = (0.10, 0.20, 0.30, 0.50, 1.00)
MODELS = {
    "purchase_propensity": "score_purchase_propensity",
    "point_rate_rule": "score_point_rate",
    "uplift_t_learner": "score_uplift_t_learner",
}
LABELS = {
    "purchase_propensity": "Purchase propensity",
    "point_rate_rule": "Point usage rule",
    "uplift_t_learner": "Uplift T-Learner",
}


def read_inputs():
    # STEP 8에서 저장한 평가군 예측 점수 로딩
    for path in (PREDICTIONS, SELECTION):
        if not path.is_file():
            raise FileNotFoundError(f"필수 입력 파일 없음: {path}")
    cols = ["client_id", "treatment_flg", "target", *MODELS.values()]
    df = pd.read_csv(PREDICTIONS, usecols=cols, dtype={"client_id": "string"})
    selection = pd.read_csv(SELECTION)
    if len(df) != 39_959 or df["client_id"].nunique() != len(df):
        raise ValueError("고객 수 또는 client_id 중복 오류: 내부 Test 39,959명 기대")
    if not df["treatment_flg"].isin([0, 1]).all() or not df["target"].isin([0, 1]).all():
        raise ValueError("treatment_flg 또는 target의 0/1 이외 값 확인")
    if not np.isfinite(df[list(MODELS.values())].to_numpy(dtype=float)).all():
        raise ValueError("예측 점수에 결측 또는 무한값")
    if len(selection) != 1 or "selected_strategy_by_validation" not in selection:
        raise ValueError("STEP 8 검증군 선정 전략 파일 형식 오류")
    chosen = str(selection.loc[0, "selected_strategy_by_validation"])
    if chosen not in MODELS:
        raise ValueError(f"알 수 없는 검증군 선정 전략: {chosen}")
    if int((df["treatment_flg"] == 1).sum()) < 1000 or int((df["treatment_flg"] == 0).sum()) < 1000:
        raise ValueError("처치군 또는 대조군 고객 수 부족")
    return df, chosen


def ranking(scores, tie_keys):
    # 동일한 점수는 STEP 8과 동일한 고정 난수로 순위 결정
    return np.lexsort((tie_keys, -scores))


def subset_metrics(t, y, order, fracs=TARGET_FRACTIONS):
    # 처치별 누적 구매율: 상위 k 비율 내부 차이
    ts, ys = t[order], y[order]
    c1 = np.cumsum(ts == 1, dtype=np.int64)
    c0 = np.cumsum(ts == 0, dtype=np.int64)
    y1 = np.cumsum((ts == 1) & (ys == 1), dtype=np.int64)
    y0 = np.cumsum((ts == 0) & (ys == 1), dtype=np.int64)
    rows = []
    for k in fracs:
        n = max(1, int(np.ceil(len(t) * k)))
        nt, nc = int(c1[n - 1]), int(c0[n - 1])
        if nt < 30 or nc < 30:
            raise ValueError(f"처치/대조군 수 부족: k={k}, SMS={nt}, Control={nc}")
        pt, pc = float(y1[n - 1] / nt), float(y0[n - 1] / nc)
        rd = pt - pc
        rows.append({
            "top_fraction": k,
            "selected_customers": n,
            "sms_customers": nt,
            "control_customers": nc,
            "sms_cvr_pct": 100.0 * pt,
            "control_cvr_pct": 100.0 * pc,
            "uplift_pp": 100.0 * rd,
            "estimated_extra_conversions": n * rd,
            "estimated_extra_per_1000": 1000.0 * rd,
        })
    return rows


def qini_points(t, y, order, steps=350):
    # Qini(k): 누적 SMS 전환 수 − 대조군 전환 수×(누적 SMS 수/누적 대조군 수)
    ts, ys = t[order], y[order]
    ct = np.cumsum(ts == 1, dtype=np.int64)
    cc = np.cumsum(ts == 0, dtype=np.int64)
    yt = np.cumsum((ts == 1) & (ys == 1), dtype=np.int64)
    yc = np.cumsum((ts == 0) & (ys == 1), dtype=np.int64)
    n = len(t)
    positions = np.unique(np.r_[np.arange(200, n + 1, steps), n])
    rows = [{"target_fraction": 0.0, "qini_gain": 0.0, "estimated_extra_all_treated": 0.0}]
    for k in positions:
        nt, nc = ct[k - 1], cc[k - 1]
        if min(nt, nc) < 30:
            continue
        p1, p0 = yt[k - 1] / nt, yc[k - 1] / nc
        gain = yt[k - 1] - yc[k - 1] * nt / nc
        rows.append({"target_fraction": k / n, "qini_gain": float(gain),
                     "estimated_extra_all_treated": float(k * (p1 - p0))})
    return rows


def bootstrap_pairs(df, scores, ties, selected_model):
    # 동일 평가 고객의 재표집: 전략별 결과를 함께 계산하는 paired bootstrap
    t = df["treatment_flg"].to_numpy(dtype=np.int8)
    y = df["target"].to_numpy(dtype=np.int8)
    ctr_ids = np.flatnonzero(t == 0)
    sms_ids = np.flatnonzero(t == 1)
    rng = np.random.default_rng(BOOT_SEED)
    original = {}
    for name, score in scores.items():
        original[name] = subset_metrics(t, y, ranking(score, ties), fracs=(0.20,))[0]

    pairs = [(selected_model, "purchase_propensity"),
             (selected_model, "point_rate_rule"),
             ("point_rate_rule", "purchase_propensity")]
    # 동일 전략 쌍 제거
    pairs = list(dict.fromkeys(pair for pair in pairs if pair[0] != pair[1]))
    store = {pair: [] for pair in pairs}
    for _ in range(N_BOOTSTRAP):
        sample_idx = np.r_[rng.choice(ctr_ids, size=len(ctr_ids), replace=True),
                           rng.choice(sms_ids, size=len(sms_ids), replace=True)]
        bt, by, b_ties = t[sample_idx], y[sample_idx], ties[sample_idx]
        metrics = {}
        for name, score in scores.items():
            ranks = ranking(score[sample_idx], b_ties)
            metrics[name] = subset_metrics(bt, by, ranks, fracs=(0.20,))[0]
        for a, b in pairs:
            store[(a, b)].append(metrics[a]["uplift_pp"] - metrics[b]["uplift_pp"])

    n_selected = original[selected_model]["selected_customers"]
    out = []
    for (a, b), differences in store.items():
        draws = np.asarray(differences)
        delta = original[a]["uplift_pp"] - original[b]["uplift_pp"]
        lo, hi = np.quantile(draws, [.025, .975])
        out.append({
            "strategy_A": a,
            "strategy_B": b,
            "top_fraction": 0.20,
            "selected_customers_each": n_selected,
            "uplift_diff_A_minus_B_pp": delta,
            "bootstrap_ci_lower_pp": lo,
            "bootstrap_ci_upper_pp": hi,
            "estimated_extra_diff_A_minus_B": n_selected * delta / 100,
            "bootstrap_extra_ci_lower": n_selected * lo / 100,
            "bootstrap_extra_ci_upper": n_selected * hi / 100,
            "bootstrap_positive_fraction": float(np.mean(draws > 0)),
            "bootstrap_iterations": N_BOOTSTRAP,
        })
    return pd.DataFrame(out)


def create_charts(kpis, qini, qini_summary, test_total, baseline):
    # Uplift@k 점수: 고정된 발송 규모별 비교
    f, ax = plt.subplots(figsize=(10, 6))
    for name in MODELS:
        sub = kpis.loc[(kpis.strategy == name) & (kpis.top_fraction < 1.0)]
        ax.plot(100 * sub.top_fraction, sub.uplift_pp, marker="o", linewidth=2, label=LABELS[name])
    ax.axhline(100 * baseline, color="gray", linestyle="--", label="Overall test uplift")
    ax.set(xlabel="Share of customers targeted (%)", ylabel="Observed SMS vs Control difference (pp)",
           title="CRM targeting efficiency | Retrospective holdout")
    ax.grid(alpha=0.25)
    ax.legend()
    f.tight_layout()
    f.savefig(OUT / "09_uplift_at_k_comparison.png", dpi=170)
    plt.close(f)

    # 누적 Qini gain: 표본 내 treatment수 규모의 추가 반응량
    f, ax = plt.subplots(figsize=(10, 6))
    for name in MODELS:
        sub = qini.loc[qini.strategy == name]
        ax.plot(100 * sub.target_fraction, sub.qini_gain, linewidth=2, label=LABELS[name])
    full = qini_summary.iloc[0]["qini_gain_all_test"]
    ax.plot([0, 100], [0, full], linestyle="--", color="gray", label="Random ranking baseline")
    ax.set(xlabel="Share of customers targeted (%)", ylabel="Qini gain (SMS-scale)",
           title="Qini curves | Test customer ranking")
    ax.grid(alpha=0.25)
    ax.legend()
    f.tight_layout()
    f.savefig(OUT / "09_qini_curve.png", dpi=170)
    plt.close(f)

    # 7,992명 타깃 가정 아래 전환 기대값과 비교
    top20 = kpis.loc[np.isclose(kpis.top_fraction, 0.2)]
    f, ax = plt.subplots(figsize=(10, 5.5))
    values = [float(top20.loc[top20.strategy == name, "estimated_extra_conversions"].iloc[0]) for name in MODELS]
    bars = ax.bar([LABELS[name] for name in MODELS], values)
    for bar, v in zip(bars, values):
        ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+8, f"{v:.1f}", ha="center", fontsize=11)
    ax.set(ylabel="Estimated extra conversions (not observed)",
           title="Top 20% audience | Same audience size by strategy")
    ax.set_ylim(0, max(values)*1.20)
    ax.grid(axis="y", alpha=0.2)
    f.tight_layout()
    f.savefig(OUT / "09_top20_conversion_scenario.png", dpi=170)
    plt.close(f)


def main():
    OUT.mkdir(exist_ok=True)
    df, selected = read_inputs()
    t = df.treatment_flg.to_numpy(dtype=np.int8)
    y = df.target.to_numpy(dtype=np.int8)
    scores = {name: df[col].to_numpy(dtype=float) for name, col in MODELS.items()}
    # 기존 STEP 8과 동일한 타이브레이크 난수
    ties = np.random.default_rng(SEED).random(len(df))
    baseline = float(y[t == 1].mean() - y[t == 0].mean())
    kpis, qini_rows, auc_rows = [], [], []
    for name, score in scores.items():
        ix = ranking(score, ties)
        metrics = subset_metrics(t, y, ix)
        kpis.extend([{"strategy": name, **r} for r in metrics])
        gains = qini_points(t, y, ix)
        qini_rows.extend([{"strategy": name, **r} for r in gains])
        gg = np.array([g["qini_gain"] for g in gains])
        xx = np.array([g["target_fraction"] for g in gains])
        qini_endpoint = float(gg[-1])
        # NumPy 2.x 호환 사다리꼴 적분
        excess_area = float(np.trapezoid(gg - xx * qini_endpoint, x=xx))
        auc_rows.append({"strategy": name, "qini_gain_all_test": qini_endpoint,
                         "area_above_random_baseline": excess_area})
    kpis = pd.DataFrame(kpis)
    qini = pd.DataFrame(qini_rows)
    auc = pd.DataFrame(auc_rows)
    kpis.to_csv(OUT / "09_test_targeting_kpis.csv", index=False, encoding="utf-8-sig", float_format="%.8f")
    qini.to_csv(OUT / "09_test_qini_curve.csv", index=False, encoding="utf-8-sig", float_format="%.8f")
    auc.to_csv(OUT / "09_test_qini_summary.csv", index=False, encoding="utf-8-sig", float_format="%.8f")

    print("[STEP 9 | 내부 Test 타깃팅 KPI]")
    print(f"test_customers: {len(df):,}")
    print(f"strategy_locked_by_validation: {selected}")
    print(f"overall_test_observed_lift_pp: {100 * baseline:+.3f}")
    for k in TARGET_FRACTIONS:
        print(f"\n[상위 {k:.0%}: 동일 발송 규모 비교]")
        for row in kpis.loc[np.isclose(kpis.top_fraction, k)].itertuples(index=False):
            print(f"{row.strategy:23s} n={row.selected_customers:,} "
                  f"uplift={row.uplift_pp:+.3f}%p extra={row.estimated_extra_conversions:+.1f} "
                  f"per_1000={row.estimated_extra_per_1000:+.1f}")

    print("\n[STEP 9 | 고정된 상위 20% 전략 간 paired bootstrap]")
    diffs = bootstrap_pairs(df, scores, ties, selected)
    diffs.to_csv(OUT / "09_test_strategy_differences_bootstrap.csv", index=False,
                 encoding="utf-8-sig", float_format="%.8f")
    for row in diffs.itertuples(index=False):
        print(f"{row.strategy_A} - {row.strategy_B}: "
              f"difference={row.uplift_diff_A_minus_B_pp:+.3f}%p "
              f"95%bootstrapCI=[{row.bootstrap_ci_lower_pp:+.3f},"
              f"{row.bootstrap_ci_upper_pp:+.3f}]%p; "
              f"estimated_extra_difference={row.estimated_extra_diff_A_minus_B:+.1f}")
    print("\n[STEP 9 | Qini curve area above random baseline]")
    for row in auc.itertuples(index=False):
        print(f"{row.strategy:23s} area={row.area_above_random_baseline:.2f}")
    create_charts(kpis, qini, auc, len(df), baseline)
    print("\nvalidation: PASS")
    print(f"results_dir: {OUT}")
    print("notes: fixed trained models, retrospective test holdout; bootstrap only captures test-sample uncertainty")
    print("notes: strategy comparison is not randomized intervention; no actual revenue or ROI observed")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[STEP 9 ERROR] {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
