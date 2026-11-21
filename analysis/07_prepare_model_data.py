"""STEP 7-1 | X5 RetailHero 고객별 조절효과 분석 데이터 구성."""

from pathlib import Path
import duckdb


# 로컬 파일 및 데이터베이스
WORK_DIR = Path(__file__).resolve().parent
DB_PATH = WORK_DIR / "retailhero.duckdb"
OUTPUT_PATH = WORK_DIR / "07_analysis_model_data.csv"


def find_csv(stem: str) -> Path:
    # CSV 또는 gzip 압축본 탐색
    for name in (f"{stem}.csv.gz", f"{stem}.csv"):
        path = WORK_DIR / name
        if path.is_file():
            return path
    raise FileNotFoundError(
        f"{stem}.csv.gz 또는 {stem}.csv 파일 없음: {WORK_DIR}\n"
        "공개 X5 데이터에서 파일 다운로드 후 같은 폴더에 저장 필요"
    )


def duckdb_path(path: Path) -> str:
    # SQL 문자열용 경로 이스케이프
    return path.as_posix().replace("'", "''")


if not DB_PATH.is_file():
    raise FileNotFoundError(f"DuckDB 데이터베이스 없음: {DB_PATH}")

CLIENTS_PATH = find_csv("clients")
TRAIN_PATH = find_csv("uplift_train")

con = duckdb.connect(str(DB_PATH))

# BigQuery STEP 3 전처리 규칙의 로컬 재현
con.execute(f"""
CREATE OR REPLACE TABLE analysis_model_data AS
WITH clients_src AS (
    SELECT
        CAST(client_id AS VARCHAR) AS client_id,
        TRY_CAST(age AS INTEGER) AS age,
        TRY_CAST(first_issue_date AS TIMESTAMP) AS first_issue_date,
        TRY_CAST(first_redeem_date AS TIMESTAMP) AS first_redeem_date
    FROM read_csv('{duckdb_path(CLIENTS_PATH)}',
                  sample_size = 10000,
                  types = {{'client_id': 'VARCHAR'}})
),
train_src AS (
    SELECT
        CAST(client_id AS VARCHAR) AS client_id,
        CAST(treatment_flg AS INTEGER) AS treatment_flg,
        CAST(target AS INTEGER) AS target
    FROM read_csv('{duckdb_path(TRAIN_PATH)}',
                  sample_size = 10000,
                  types = {{'client_id': 'VARCHAR'}})
),
cleaned AS (
    SELECT
        u.client_id,
        u.treatment_flg,
        u.target,
        CASE WHEN c.age BETWEEN 11 AND 99
             THEN c.age ELSE NULL END AS age_clean,
        CASE WHEN CAST(c.first_redeem_date AS DATE) <= DATE '2019-03-18'
             THEN 1 ELSE 0 END AS redeem_history_before_cutoff
    FROM train_src AS u
    INNER JOIN clients_src AS c USING (client_id)
    WHERE c.first_redeem_date IS NULL
       OR c.first_redeem_date >= c.first_issue_date
)
SELECT
    c.client_id,
    c.treatment_flg,
    c.target,
    c.age_clean,
    c.redeem_history_before_cutoff,
    f.transaction_count,
    f.total_purchase_sum,
    f.avg_purchase_sum,
    f.any_point_use_transactions,
    f.any_point_use_rate,
    f.regular_use_rate,
    f.express_use_rate,
    f.days_since_last_purchase,
    f.days_since_last_point_use,
    CASE
        WHEN f.any_point_use_transactions = 0 THEN 1
        WHEN f.any_point_use_rate <= 0.05 THEN 2
        WHEN f.any_point_use_rate <= 0.10 THEN 3
        WHEN f.any_point_use_rate <= 0.20 THEN 4
        ELSE 5
    END AS point_segment_id
FROM cleaned AS c
LEFT JOIN customer_purchase_features AS f USING (client_id);
""")

# BigQuery STEP 3, STEP 5 재현 검증
result = con.execute("""
SELECT
    COUNT(*) AS customer_rows,
    COUNT(DISTINCT client_id) AS unique_customers,
    COUNT(*) FILTER (WHERE transaction_count IS NULL) AS missing_purchase_features,
    COUNT(*) FILTER (WHERE age_clean IS NULL) AS missing_age,
    SUM(transaction_count) AS transaction_count_sum,
    SUM(any_point_use_transactions) AS point_use_transactions_sum,
    SUM(redeem_history_before_cutoff) AS redeem_history_customers,
    COUNT(*) FILTER (WHERE days_since_last_point_use IS NULL) AS never_used_customers,
    COUNT(*) FILTER (WHERE treatment_flg = 0) AS control_customers,
    COUNT(*) FILTER (WHERE treatment_flg = 1) AS sms_customers,
    COUNT(*) FILTER (WHERE treatment_flg = 0 AND target = 1) AS control_purchases,
    COUNT(*) FILTER (WHERE treatment_flg = 1 AND target = 1) AS sms_purchases
FROM analysis_model_data;
""")
metrics = dict(zip([d[0] for d in result.description], result.fetchone()))
print("[STEP 7-1 | 로컬 분석 데이터 검증]")
for key, value in metrics.items():
    print(f"{key}: {value}")

expected = {
    "customer_rows": 199794,
    "unique_customers": 199794,
    "missing_purchase_features": 0,
    "missing_age": 733,
    "transaction_count_sum": 4022321,
    "point_use_transactions_sum": 251096,
    "redeem_history_customers": 159648,
    "never_used_customers": 78084,
    "control_customers": 99950,
    "sms_customers": 99844,
    "control_purchases": 60316,
    "sms_purchases": 63570,
}
issues = [f"{key}: 실제 {metrics[key]}, 예상 {value}"
          for key, value in expected.items() if metrics[key] != value]
if issues:
    con.close()
    raise ValueError("BigQuery 결과와 불일치:\n" + "\n".join(issues))

# 분석 입력 데이터 CSV 저장
con.execute(f"""
COPY analysis_model_data TO '{duckdb_path(OUTPUT_PATH)}'
(FORMAT CSV, HEADER TRUE);
""")
con.close()
print("validation: PASS")
print(f"saved_database: {DB_PATH}")
print(f"saved_csv: {OUTPUT_PATH}")
print(f"csv_size_mb: {OUTPUT_PATH.stat().st_size / (1024 ** 2):.2f}")
