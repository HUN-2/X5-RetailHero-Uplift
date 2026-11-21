"""X5 RetailHero | purchases.csv.gz 전체 품질 검증

실행 예시:
    python 04_purchases_quality.py --check profile
    python 04_purchases_quality.py --check transactions
    python 04_purchases_quality.py --check all

입력 파일: 스크립트와 같은 폴더의 purchases.csv.gz
원본 파일 변경 없음
"""

import argparse
from pathlib import Path
import duckdb


PROFILE_QUERY = """
SELECT
    COUNT(*) AS total_rows,
    COUNT(*) FILTER (WHERE client_id IS NULL OR TRIM(client_id) = '') AS missing_client_id,
    COUNT(*) FILTER (WHERE transaction_id IS NULL OR TRIM(transaction_id) = '') AS missing_transaction_id,
    COUNT(*) FILTER (WHERE store_id IS NULL OR TRIM(store_id) = '') AS missing_store_id,
    COUNT(*) FILTER (WHERE product_id IS NULL OR TRIM(product_id) = '') AS missing_product_id,
    COUNT(*) FILTER (WHERE transaction_datetime IS NULL) AS missing_datetime,
    MIN(transaction_datetime) AS min_datetime,
    MAX(transaction_datetime) AS max_datetime,
    MIN(regular_points_received) AS min_regular_received,
    MAX(regular_points_received) AS max_regular_received,
    MIN(regular_points_spent) AS min_regular_spent,
    MAX(regular_points_spent) AS max_regular_spent,
    MIN(express_points_received) AS min_express_received,
    MAX(express_points_received) AS max_express_received,
    MIN(express_points_spent) AS min_express_spent,
    MAX(express_points_spent) AS max_express_spent,
    COUNT(*) FILTER (WHERE regular_points_spent < 0) AS negative_regular_spent,
    COUNT(*) FILTER (WHERE regular_points_spent > 0) AS positive_regular_spent,
    COUNT(*) FILTER (WHERE express_points_spent < 0) AS negative_express_spent,
    COUNT(*) FILTER (WHERE express_points_spent > 0) AS positive_express_spent,
    MIN(purchase_sum) AS min_purchase_sum,
    MAX(purchase_sum) AS max_purchase_sum,
    MIN(product_quantity) AS min_quantity,
    MAX(product_quantity) AS max_quantity,
    MIN(trn_sum_from_iss) AS min_trn_iss,
    MAX(trn_sum_from_iss) AS max_trn_iss,
    MIN(trn_sum_from_red) AS min_trn_red,
    MAX(trn_sum_from_red) AS max_trn_red,
    COUNT(*) FILTER (WHERE regular_points_received IS NULL) AS missing_regular_received,
    COUNT(*) FILTER (WHERE regular_points_spent IS NULL) AS missing_regular_spent,
    COUNT(*) FILTER (WHERE express_points_received IS NULL) AS missing_express_received,
    COUNT(*) FILTER (WHERE express_points_spent IS NULL) AS missing_express_spent,
    COUNT(*) FILTER (WHERE purchase_sum IS NULL) AS missing_purchase_sum,
    COUNT(*) FILTER (WHERE product_quantity IS NULL) AS missing_product_quantity,
    COUNT(*) FILTER (WHERE trn_sum_from_iss IS NULL) AS missing_trn_iss,
    COUNT(*) FILTER (WHERE trn_sum_from_red IS NULL) AS missing_trn_red,
    COUNT(*) FILTER (WHERE trn_sum_from_iss IS NULL AND trn_sum_from_red IS NULL) AS missing_both_trn
FROM read_csv('__CSV_PATH__', sample_size=10000);
"""


TRANSACTION_QUERY = """
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
    FROM read_csv('__CSV_PATH__', sample_size=10000)
    GROUP BY client_id, transaction_id
)
SELECT
    COUNT(*) AS total_transactions,
    SUM(product_rows) AS total_product_rows,
    COUNT(*) FILTER (WHERE product_rows > 1) AS multi_product_transactions,
    MAX(product_rows) AS max_product_rows,
    COUNT(*) FILTER (WHERE min_purchase <> max_purchase) AS inconsistent_purchase,
    COUNT(*) FILTER (WHERE min_reg_received <> max_reg_received) AS inconsistent_reg_received,
    COUNT(*) FILTER (WHERE min_reg_spent <> max_reg_spent) AS inconsistent_reg_spent,
    COUNT(*) FILTER (WHERE min_exp_received <> max_exp_received) AS inconsistent_exp_received,
    COUNT(*) FILTER (WHERE min_exp_spent <> max_exp_spent) AS inconsistent_exp_spent
FROM transaction_check;
"""


def print_result(con, query):
    result = con.execute(query)
    names = [col[0] for col in result.description]
    values = result.fetchone()
    for name, value in zip(names, values):
        displayed = f"{value:,}" if isinstance(value, int) else value
        print(f"{name}: {displayed}")


def main():
    parser = argparse.ArgumentParser(description="X5 구매 이력 품질 검증")
    parser.add_argument("--check", choices=["profile", "transactions", "all"], default="profile")
    parser.add_argument("--file", type=Path, default=Path(__file__).resolve().parent / "purchases.csv.gz")
    args = parser.parse_args()

    csv_file = args.file.resolve()
    if not csv_file.is_file():
        raise FileNotFoundError(f"원본 파일 확인 필요: {csv_file}")

    # SQL 경로 이스케이프
    csv_path = csv_file.as_posix().replace("'", "''")

    with duckdb.connect() as con:
        con.execute("SET preserve_insertion_order = false")

        # STEP 4-2/4-3 | 컬럼별 범위·결측 확인
        if args.check in ("profile", "all"):
            print("=== 원본 컬럼 품질 ===")
            print_result(con, PROFILE_QUERY.replace("__CSV_PATH__", csv_path))

        # STEP 4-5 | 전체 거래별 금액·포인트 반복 검증
        if args.check in ("transactions", "all"):
            print("=== 거래 단위 검증 ===")
            print_result(con, TRANSACTION_QUERY.replace("__CSV_PATH__", csv_path))


if __name__ == "__main__":
    main()
