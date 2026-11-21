from pathlib import Path
import duckdb

# STEP 4-9 | 고객별 구매·포인트 행동 변수 생성
work_dir = Path(__file__).resolve().parent
database_path = work_dir / "retailhero.duckdb"
output_path = work_dir / "customer_purchase_features.csv"

if not database_path.is_file():
    raise FileNotFoundError(f"DuckDB 파일 없음: {database_path}")

con = duckdb.connect(str(database_path))

# 거래 단위 → 고객 단위 집계
con.execute("""
CREATE OR REPLACE TABLE customer_purchase_features AS
WITH customer_summary AS (
    SELECT
        client_id,
        COUNT(*) AS transaction_count,
        SUM(purchase_sum) AS total_purchase_sum,
        AVG(purchase_sum) AS avg_purchase_sum,

        COUNT(*) FILTER (
            WHERE regular_points_used > 0
        ) AS regular_use_transactions,
        COUNT(*) FILTER (
            WHERE express_points_used > 0
        ) AS express_use_transactions,
        COUNT(*) FILTER (
            WHERE regular_points_used > 0 OR express_points_used > 0
        ) AS any_point_use_transactions,

        SUM(regular_points_used) AS total_regular_points_used,
        SUM(express_points_used) AS total_express_points_used,

        MIN(transaction_datetime) AS first_transaction,
        MAX(transaction_datetime) AS last_transaction,
        MAX(transaction_datetime) FILTER (
            WHERE regular_points_used > 0 OR express_points_used > 0
        ) AS last_point_use_transaction
    FROM transactions_clean
    GROUP BY client_id
)
SELECT
    client_id,
    transaction_count,
    ROUND(total_purchase_sum, 2) AS total_purchase_sum,
    ROUND(avg_purchase_sum, 2) AS avg_purchase_sum,
    regular_use_transactions,
    express_use_transactions,
    any_point_use_transactions,

    ROUND(
        1.0 * regular_use_transactions / NULLIF(transaction_count, 0), 4
    ) AS regular_use_rate,
    ROUND(
        1.0 * express_use_transactions / NULLIF(transaction_count, 0), 4
    ) AS express_use_rate,
    ROUND(
        1.0 * any_point_use_transactions / NULLIF(transaction_count, 0), 4
    ) AS any_point_use_rate,

    ROUND(total_regular_points_used, 2) AS total_regular_points_used,
    ROUND(total_express_points_used, 2) AS total_express_points_used,

    CAST(first_transaction AS DATE) AS first_purchase_date,
    CAST(last_transaction AS DATE) AS last_purchase_date,
    DATE_DIFF('day', CAST(last_transaction AS DATE), DATE '2019-03-18')
        AS days_since_last_purchase,
    DATE_DIFF('day', CAST(last_point_use_transaction AS DATE), DATE '2019-03-18')
        AS days_since_last_point_use
FROM customer_summary;
""")

# 고객 단위 검증
result = con.execute("""
SELECT
    COUNT(*) AS customer_rows,
    COUNT(DISTINCT client_id) AS unique_customers,
    SUM(transaction_count) AS total_transactions_recovered,
    SUM(any_point_use_transactions) AS point_use_transactions_recovered,
    COUNT(*) FILTER (
        WHERE any_point_use_rate < 0 OR any_point_use_rate > 1
    ) AS invalid_use_rate,
    COUNT(*) FILTER (
        WHERE days_since_last_purchase < 0
    ) AS invalid_purchase_recency,
    COUNT(*) FILTER (
        WHERE days_since_last_point_use < 0
    ) AS invalid_point_recency
FROM customer_purchase_features;
""")

columns = [column[0] for column in result.description]
values = result.fetchone()
for name, value in zip(columns, values):
    print(f"{name}: {value}")

# 고객 단위 CSV 내보내기
output_sql = output_path.as_posix().replace("'", "''")
con.execute(f"""
COPY customer_purchase_features
TO '{output_sql}'
(FORMAT CSV, HEADER TRUE);
""")
con.close()

print(f"saved_database: {database_path}")
print(f"saved_csv: {output_path}")
print(f"csv_size_mb: {output_path.stat().st_size / (1024 ** 2):.2f}")
