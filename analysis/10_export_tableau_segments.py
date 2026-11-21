"""STEP 10 | Export five aggregated segment rows for Tableau D02.

Private inputs (never commit):
  analysis/07_analysis_model_data.csv
  analysis/results/07_adjusted_uplift_by_segment.csv
Public output:
  tableau/data/10_customer_insights_segments.csv
"""
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "07_analysis_model_data.csv"
ADJUSTED = HERE / "results" / "07_adjusted_uplift_by_segment.csv"
DEST = HERE.parent / "tableau" / "data" / "10_customer_insights_segments.csv"
LABELS = {
    1: ("Never used", "0% (미사용)"),
    2: ("0–5%", "0~5%"),
    3: ("5–10%", "5~10%"),
    4: ("10–20%", "10~20%"),
    5: ("Over 20%", "20% 초과"),
}


def main():
    # 고객별 분석 데이터와 STEP 7-2 추정결과 연결
    for path in (DATA, ADJUSTED):
        if not path.is_file():
            raise FileNotFoundError(f"Missing local input: {path}")
    base = pd.read_csv(DATA, usecols=["point_segment_id", "treatment_flg", "target", "transaction_count"])
    adj = pd.read_csv(ADJUSTED)
    required = {"point_segment", "adjusted_uplift_pp", "ci_95_lower_pp", "ci_95_upper_pp"}
    if not required.issubset(adj):
        raise ValueError(f"Adjusted output missing columns: {required.difference(adj.columns)}")
    if len(base) != 199794 or set(base.point_segment_id.unique()) != set(LABELS):
        raise ValueError("Unexpected total customers or segment labels")
    if not base.treatment_flg.isin([0, 1]).all() or not base.target.isin([0, 1]).all():
        raise ValueError("Invalid binary treatment/target data")
    by_arm = base.groupby(["point_segment_id", "treatment_flg"], sort=True).agg(
        n=("target", "size"), purchases=("target", "sum")
    )
    rows=[]
    for i, (en, ko) in LABELS.items():
        sub=base.loc[base.point_segment_id.eq(i)]
        nc=int(by_arm.loc[(i,0),"n"]); ns=int(by_arm.loc[(i,1),"n"])
        yc=int(by_arm.loc[(i,0),"purchases"]); ys=int(by_arm.loc[(i,1),"purchases"])
        matched=adj.loc[adj.point_segment.eq(ko)]
        if len(matched) != 1:
            raise ValueError(f"Adjusted model row mismatch: {ko}")
        item=matched.iloc[0]
        pc=100*yc/nc; ps=100*ys/ns
        rows.append({
            "segment_order": i, "segment_label_en": en, "segment_label_ko": ko,
            "customer_count": len(sub), "control_customers": nc,
            "control_purchases": yc, "sms_customers": ns, "sms_purchases": ys,
            "avg_transaction_count": round(float(sub.transaction_count.mean()),2),
            "control_cvr_pct": round(pc,4), "sms_cvr_pct": round(ps,4),
            "observed_lift_pp": round(ps-pc,4),
            "adjusted_lift_pp": round(float(item.adjusted_uplift_pp),2),
            "adjusted_ci_lower_pp": round(float(item.ci_95_lower_pp),2),
            "adjusted_ci_upper_pp": round(float(item.ci_95_upper_pp),2),
            "analysis_population": "Exploratory full cohort (N=199794)",
        })
    out=pd.DataFrame(rows)
    if out.customer_count.sum() != 199794 or (out.control_customers+out.sms_customers != out.customer_count).any():
        raise ValueError("Customer totals mismatch")
    if not np.isfinite(out.select_dtypes(include='number').to_numpy(dtype=float)).all():
        raise ValueError("Non-finite output values")
    DEST.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(DEST,index=False,encoding="utf-8-sig")
    print(f"saved: {DEST}; segments={len(out)}; customers={out.customer_count.sum():,}")

if __name__ == "__main__":
    main()
