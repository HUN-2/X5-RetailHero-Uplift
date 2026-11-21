"""STEP 13 | STEP 9 결과를 Tableau D04용 집계 CSV로 변환.

입력: results/09_test_strategy_differences_bootstrap.csv
      results/09_test_qini_summary.csv
출력: results/13_strategy_difference_ci.csv
      results/13_qini_area_summary.csv

주의: 기존 분석 결과의 재구성만 수행. 모델 학습/부트스트랩 재실행 없음.
"""
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
BOOTSTRAP_INPUT = RESULTS / "09_test_strategy_differences_bootstrap.csv"
QINI_INPUT = RESULTS / "09_test_qini_summary.csv"

LABELS = {
    "uplift_t_learner": "T-Learner",
    "point_rate_rule": "Point Usage Rule",
    "purchase_propensity": "Purchase Propensity",
}
COMPARISONS = [
    ("uplift_t_learner", "purchase_propensity"),
    ("uplift_t_learner", "point_rate_rule"),
    ("point_rate_rule", "purchase_propensity"),
]
COMPARISON_LABELS_KO = {
    ("uplift_t_learner", "purchase_propensity"): "T-Learner vs 구매확률 기준",
    ("uplift_t_learner", "point_rate_rule"): "T-Learner vs 포인트 사용률 규칙",
    ("point_rate_rule", "purchase_propensity"): "포인트 사용률 규칙 vs 구매확률 기준",
}
STRATEGY_ORDER = ["uplift_t_learner", "point_rate_rule", "purchase_propensity"]
EXPECTED_TEST_N = 39_959
EXPECTED_TARGET_FRACTION = 0.20
EXPECTED_SELECTED = 7_992


def read_csv_checked(path: Path, required: set[str]) -> pd.DataFrame:
    # 입력 파일과 필수 열 검사
    if not path.is_file():
        raise FileNotFoundError(f"STEP 9 결과 파일을 찾을 수 없음: {path}")
    df = pd.read_csv(path)
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"필수 열 누락 ({path.name}): {sorted(missing)}")
    return df


def export_strategy_difference() -> Path:
    # 전략 간 paired bootstrap 결과 로딩
    df = read_csv_checked(BOOTSTRAP_INPUT, {
        "strategy_A", "strategy_B", "top_fraction", "selected_customers_each",
        "uplift_diff_A_minus_B_pp", "bootstrap_ci_lower_pp", "bootstrap_ci_upper_pp",
    })
    if len(df) != len(COMPARISONS):
        raise ValueError(f"전략 쌍 3개 기대: 현재 {len(df)}행")
    result = []
    for i, (a, b) in enumerate(COMPARISONS, start=1):
        found = df.loc[(df.strategy_A == a) & (df.strategy_B == b)]
        if len(found) != 1:
            raise ValueError(f"전략 쌍의 유일성 오류: {a} vs {b}")
        x = found.iloc[0]
        if not np.isclose(float(x.top_fraction), EXPECTED_TARGET_FRACTION):
            raise ValueError(f"선정 비율 불일치: {a} vs {b}")
        if int(x.selected_customers_each) != EXPECTED_SELECTED:
            raise ValueError(f"선정 고객 수 불일치: {a} vs {b}")
        point = float(x.uplift_diff_A_minus_B_pp)
        lo = float(x.bootstrap_ci_lower_pp)
        hi = float(x.bootstrap_ci_upper_pp)
        if not np.isfinite([point, lo, hi]).all() or not (lo <= hi):
            raise ValueError(f"추정값·신뢰구간 오류: {a} vs {b}")
        # Tableau 표기용 반올림 및 신뢰구간 너비
        point, lo, hi = round(point, 3), round(lo, 3), round(hi, 3)
        result.append({
            "comparison_en": f"{LABELS[a]} vs {LABELS[b]}",
            "comparison_ko": COMPARISON_LABELS_KO[(a, b)],
            "difference_pp": point,
            "ci_lower_pp": lo,
            "ci_upper_pp": hi,
            "ci_width_pp": round(hi - lo, 3),
            "comparison_order": i,
            "ci_includes_zero": "Yes" if lo <= 0 <= hi else "No",
            "target_fraction": EXPECTED_TARGET_FRACTION,
            "test_customers": EXPECTED_TEST_N,
            "selected_customers": EXPECTED_SELECTED,
            "ci_method": "paired bootstrap 95% CI",
        })
    path = RESULTS / "13_strategy_difference_ci.csv"
    pd.DataFrame(result).to_csv(path, index=False, encoding="utf-8-sig")
    return path


def export_qini_summary() -> Path:
    # 전략별 Qini 면적 결과 로딩
    df = read_csv_checked(QINI_INPUT, {"strategy", "area_above_random_baseline"})
    if len(df) != len(STRATEGY_ORDER) or df.strategy.duplicated().any():
        raise ValueError("전략별 Qini 결과가 정확히 3행이어야 함")
    result = []
    for i, strategy in enumerate(STRATEGY_ORDER, start=1):
        found = df.loc[df.strategy == strategy]
        if len(found) != 1:
            raise ValueError(f"전략 Qini 결과 누락: {strategy}")
        area = float(found.iloc[0].area_above_random_baseline)
        if not np.isfinite(area):
            raise ValueError(f"Qini 값 오류: {strategy}")
        result.append({
            "strategy_en": LABELS[strategy],
            "qini_area_above_random": round(area, 2),
            "strategy_order": i,
            "test_customers": EXPECTED_TEST_N,
            "note": "Qini curve area above random baseline; internal test",
        })
    path = RESULTS / "13_qini_area_summary.csv"
    pd.DataFrame(result).to_csv(path, index=False, encoding="utf-8-sig")
    return path


def main():
    # 기존 STEP 9 결과에서 D04 Tableau 파일 생성
    for output in (export_strategy_difference(), export_qini_summary()):
        print(f"saved: {output}")
    print("validation: PASS")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[STEP 13 ERROR] {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
