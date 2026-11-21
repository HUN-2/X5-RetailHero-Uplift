from pathlib import Path
import duckdb

# STEP 4-5 | 전체 거래 단위 일관성 검증

data_file = Path(__file__).resolve().parent / "purchases.csv.gz"
if not data_file.exists():
    raise FileNotFoundError(f"파일 확인 필요: {data_file}")

# Windows 경로 및 SQL 문자열 처리
csv_path = data_file.as_posix().replace("'", "''")

query = f"""
WITH transaction_check AS (
    SELECT
        client_id,
        transaction_id,
        COUNT(*) AS product_rows,

        MIN(purchase_sum) AS min_purchase,
        MAX(purchase_sum) AS max_purchase,

        MIN(regular_points_received) AS min_reg_received,
        MAX(regular_points_received) AS max_reg_received,
        MIN(regular_points_spent) AS min_reg_spent,
        MAX(regular_points_spent) AS max_reg_spent,

        MIN(express_points_received) AS min_exp_received,
        MAX(express_points_received) AS max_exp_received,
        MIN(express_points_spent) AS min_exp_spent,
        MAX(express_points_spent) AS max_exp_spent
    FROM read_csv('{csv_path}', sample_size=10000)
    GROUP BY client_id, transaction_id
)
SELECT
    COUNT(*) AS total_transactions,
    SUM(product_rows) AS total_product_rows,
    COUNT(*) FILTER (
        WHERE product_rows > 1
    ) AS multi_product_transactions,
    MAX(product_rows) AS max_product_rows,

    COUNT(*) FILTER (
        WHERE min_purchase <> max_purchase
    ) AS inconsistent_purchase,
    COUNT(*) FILTER (
        WHERE min_reg_received <> max_reg_received
    ) AS inconsistent_reg_received,
    COUNT(*) FILTER (
        WHERE min_reg_spent <> max_reg_spent
    ) AS inconsistent_reg_spent,
    COUNT(*) FILTER (
        WHERE min_exp_received <> max_exp_received
    ) AS inconsistent_exp_received,
    COUNT(*) FILTER (
        WHERE min_exp_spent <> max_exp_spent
    ) AS inconsistent_exp_spent
FROM transaction_check;
"""

con = duckdb.connect()
try:
    con.execute("SET preserve_insertion_order = false")
    result = con.execute(query)
    columns = [column[0] for column in result.description]
    values = result.fetchone()
    for name, value in zip(columns, values):
        print(f"{name}: {value:,}" if isinstance(value, int) else f"{name}: {value}")
finally:
    con.close()
