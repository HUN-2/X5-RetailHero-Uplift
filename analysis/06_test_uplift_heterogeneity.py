"""STEP 6-6 | X5 RetailHero: 포인트 사용 집단별 SMS 전환율 차이의 이질성 검정."""

import csv
from itertools import combinations
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
from scipy.stats import chi2, norm


# BigQuery STEP 6-6-1 집계 결과
SEGMENTS = [
    {"group": "0% (미사용)", "n_control": 39192, "y_control": 19682, "n_sms": 38892, "y_sms": 20734},
    {"group": "0~5%", "n_control": 15351, "y_control": 12955, "n_sms": 15464, "y_sms": 13259},
    {"group": "5~10%", "n_control": 21100, "y_control": 14622, "n_sms": 21177, "y_sms": 15366},
    {"group": "10~20%", "n_control": 16813, "y_control": 9794, "n_sms": 16853, "y_sms": 10453},
    {"group": "20% 초과", "n_control": 7494, "y_control": 3263, "n_sms": 7458, "y_sms": 3758},
]

OUT_DIR = Path(__file__).resolve().parent / "results"
OUT_DIR.mkdir(exist_ok=True)


def save_csv(path, rows, columns):
    # 결과 CSV 보관
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


# 분율 차이와 분산 추정
segment_results = []
for row in SEGMENTS:
    p_control = row["y_control"] / row["n_control"]
    p_sms = row["y_sms"] / row["n_sms"]
    uplift = p_sms - p_control
    variance = (
        p_sms * (1 - p_sms) / row["n_sms"]
        + p_control * (1 - p_control) / row["n_control"]
    )
    se = np.sqrt(variance)
    segment_results.append({
        "group": row["group"],
        "n_control": row["n_control"],
        "y_control": row["y_control"],
        "n_sms": row["n_sms"],
        "y_sms": row["y_sms"],
        "control_rate_pct": p_control * 100,
        "sms_rate_pct": p_sms * 100,
        "uplift_pp": uplift * 100,
        "ci_lower_pp": (uplift - 1.96 * se) * 100,
        "ci_upper_pp": (uplift + 1.96 * se) * 100,
        "uplift": uplift,
        "variance": variance,
    })

# 전체 이질성 검정: 공통 위험차이 가설
weights = np.array([1 / r["variance"] for r in segment_results])
effects = np.array([r["uplift"] for r in segment_results])
weighted_mean = np.average(effects, weights=weights)
q = float(np.sum(weights * (effects - weighted_mean) ** 2))
df = len(segment_results) - 1
p_omnibus = float(chi2.sf(q, df))

print("\n[전체 이질성 검정: 5개 집단의 전환율 차이가 같은가?]")
print(f"Q({df}) = {q:.4f}, p = {p_omnibus:.8g}")
print("방법: 역분산 가중 Q 통계량, 카이제곱 근사")

print("\n[집단별 SMS 전환율 차이와 95% 신뢰구간]")
for r in segment_results:
    print(f"{r['group']:11s}: {r['uplift_pp']:+.2f}%p "
          f"[{r['ci_lower_pp']:.2f}, {r['ci_upper_pp']:.2f}]")

# 집단 간 차이의 차이: 독립 표본 정규근사
contrasts = []
for i, j in combinations(range(len(segment_results)), 2):
    a, b = segment_results[i], segment_results[j]
    diff = b["uplift"] - a["uplift"]  # 뒤 집단 - 앞 집단
    se_diff = np.sqrt(a["variance"] + b["variance"])
    z = diff / se_diff
    p = float(2 * norm.sf(abs(z)))
    contrasts.append({
        "contrast": f"{b['group']} - {a['group']}",
        "diff_pp": diff * 100,
        "ci_lower_pp": (diff - 1.96 * se_diff) * 100,
        "ci_upper_pp": (diff + 1.96 * se_diff) * 100,
        "z": float(z),
        "p_raw": p,
    })

# Holm 다중비교 보정: 모든 10개 쌍별 비교
p_values = np.array([r["p_raw"] for r in contrasts])
sorted_indices = np.argsort(p_values)
m = len(contrasts)
previous = 0.0
for rank, idx in enumerate(sorted_indices):
    previous = max(previous, (m - rank) * p_values[idx])
    contrasts[idx]["p_holm"] = float(min(previous, 1.0))

print("\n[쌍별 차이의 차이: Holm 보정 p값]")
for r in contrasts:
    print(f"{r['contrast']:24s}: {r['diff_pp']:+.2f}%p "
          f"[{r['ci_lower_pp']:.2f}, {r['ci_upper_pp']:.2f}], "
          f"p={r['p_raw']:.6g}, Holm p={r['p_holm']:.6g}")

# 결과 파일 저장
save_csv(
    OUT_DIR / "06_segment_uplift_summary.csv",
    [{k: v for k, v in r.items() if k not in ("uplift", "variance")}
     for r in segment_results],
    ["group", "n_control", "y_control", "n_sms", "y_sms",
     "control_rate_pct", "sms_rate_pct", "uplift_pp", "ci_lower_pp", "ci_upper_pp"],
)
save_csv(
    OUT_DIR / "06_pairwise_contrasts_holm.csv",
    contrasts,
    ["contrast", "diff_pp", "ci_lower_pp", "ci_upper_pp", "z", "p_raw", "p_holm"],
)
save_csv(
    OUT_DIR / "06_heterogeneity_test.csv",
    [{"method": "Inverse-variance Q test", "Q": q, "df": df, "p_value": p_omnibus}],
    ["method", "Q", "df", "p_value"],
)

# 포트폴리오 그림 생성
# 운영체제별 한글 폰트 선택
for font_name in ("Malgun Gothic", "NanumSquare", "Noto Sans CJK KR"):
    try:
        font_manager.findfont(font_name, fallback_to_default=False)
        plt.rcParams["font.family"] = font_name
        break
    except ValueError:
        continue
plt.rcParams["axes.unicode_minus"] = False
labels = [r["group"] for r in segment_results]
y = np.arange(len(labels))
centers = np.array([r["uplift_pp"] for r in segment_results])
lowers = np.array([r["ci_lower_pp"] for r in segment_results])
uppers = np.array([r["ci_upper_pp"] for r in segment_results])

fig, ax = plt.subplots(figsize=(9, 5.3))
ax.errorbar(
    centers, y,
    xerr=np.vstack([centers - lowers, uppers - centers]),
    fmt="o", capsize=5, linewidth=2,
)
ax.axvline(0, linestyle="--", linewidth=1)
ax.set_yticks(y, labels)
ax.invert_yaxis()
ax.set_xlabel("SMS 구매 전환율 차이 (%p)")
ax.set_title("포인트 사용 수준별 SMS 전환율 차이 (95% 신뢰구간)")
ax.grid(axis="x", alpha=0.22)
ax.set_xlim(-0.5, 9.0)
for yy, r in zip(y, segment_results):
    ax.text(r["ci_upper_pp"] + 0.14, yy, f"{r['uplift_pp']:+.2f}%p", va="center")
fig.tight_layout()
image_path = OUT_DIR / "06_segment_uplift_forest.png"
fig.savefig(image_path, dpi=200, bbox_inches="tight")
plt.close(fig)

print("\n[저장 파일]")
for path in sorted(OUT_DIR.glob("06_*")):
    print(path)
print("\n주의: 비조정 탐색적 분석. 그룹 정의 탐색성·독립 이항 근사·무작위 처치 가정 확인 필요.")
