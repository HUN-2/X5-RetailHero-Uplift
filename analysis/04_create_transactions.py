from pathlib import Path
import duckdb

# STEP 4-8 | 거래 단위 정제 테이블 생성
work_dir = Path(__file__).resolve().parent
source_path = work_dir / "purchases.csv.gz"
database_path = work_dir / "retailhero.duckdb"

if not source_path.is_file():
    raise FileNotFoundError(f"원본 파일 없음: {source_path}")

# Windows 경로 호환 및 SQL 문자열 이스케이프
source_sql = source_path.as_posix().replace("'", "''")

con = duckdb.connect(str(database_path))

query = f"""
CREATE OR REPLACE TABLE transactions_clean AS
WITH transaction_level AS (
    SELECT
        client_id,
        transaction_id,
        MIN(transaction_datetime) AS transaction_datetime,
        MIN(purchase_sum) AS purchase_sum,
        MIN(regular_points_received) AS regular_points_received,
        MIN(regular_points_spent) AS regular_points_spent,
        MIN(express_points_received) AS express_points_received,
        MIN(express_points_spent) AS express_points_spent,
        COUNT(*) AS product_rows
    FROM read_csv('{source_sql}', sample_size=10000)
    GROUP BY client_id, transaction_id
),
transaction_id_check AS (
    SELECT
        *,
        COUNT(*) OVER (PARTITION BY transaction_id) AS id_customer_count
    FROM transaction_level
)
SELECT
    client_id,
    transaction_id,
    transaction_datetime,
    purchase_sum,
    regular_points_received,
    -regular_points_spent AS regular_points_used,
    express_points_received,
    -express_points_spent AS express_points_used,
    product_rows
FROM transaction_id_check
WHERE id_customer_count = 1;
"""

# 전체 상품행 → 거래 단위 집계, 중복 거래 ID 제외
con.execute(query)

# 정제 결과 검증
result = con.execute("""
SELECT
    COUNT(*) AS total_transactions,
    COUNT(DISTINCT client_id) AS unique_customers,
    SUM(product_rows) AS retained_product_rows,
    COUNT(*) FILTER (
        WHERE regular_points_used > 0
    ) AS regular_point_use_transactions,
    COUNT(*) FILTER (
        WHERE express_points_used > 0
    ) AS express_point_use_transactions,
    COUNT(*) FILTER (
        WHERE regular_points_used > 0 OR express_points_used > 0
    ) AS any_point_use_transactions,
    MIN(transaction_datetime) AS first_transaction,
    MAX(transaction_datetime) AS last_transaction
FROM transactions_clean;
""")

columns = [col[0] for col in result.description]
values = result.fetchone()
for name, value in zip(columns, values):
    print(f"{name}: {value}")

con.close()
print(f"saved_database: {database_path}")
