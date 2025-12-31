"""
This module contains analysis bootstrap functions for data profiling and analysis suitability checks.

Function input conventions:
    - Functions step_1_overview, step_2_schema, step_3_sample, step_6_data_quality_check,
      step_7_uniqueness_check, and step_8_null_profile expect (con, source: str, ...) as arguments.
    - Functions step_4_grain_detection, step_5_available_analyses, and derive_analysis_blacklist
      expect a Pandas DataFrame (schema_df) as input, or in the case of derive_analysis_blacklist,
      (grains: list, schema_df).

Note on 'source':
    - The `source` parameter must be a string path to a CSV file that is readable by DuckDB.
      (e.g., "/path/to/file.csv"). Do not pass a DataFrame or database table name.
"""
import duckdb


def step_1_overview(con: duckdb.DuckDBPyConnection, source: str) -> dict:
    """
    Step 1: 資料是不是活的？
    回傳列數與時間範圍（如果有時間欄位）
    """
    result = {}

    # row count
    result["row_count"] = con.execute(
        f"SELECT COUNT(*) FROM '{source}'"
    ).fetchone()[0]

    # 嘗試找時間欄位
    time_candidates = ["purchase_time", "created_at", "paid_at"]
    for col in time_candidates:
        try:
            min_max = con.execute(
                f"""
                SELECT
                    MIN({col}) AS min_time,
                    MAX({col}) AS max_time
                FROM '{source}'
                """
            ).fetchone()
            if min_max[0] is not None:
                result["time_column"] = col
                result["time_range"] = {
                    "min": min_max[0],
                    "max": min_max[1],
                }
                break
        except Exception:
            continue

    return result


def step_2_schema(con: duckdb.DuckDBPyConnection, source: str):
    """
    Step 2: 欄位結構
    """
    return con.execute(
        f"DESCRIBE SELECT * FROM '{source}'"
    ).fetchdf()


def step_3_sample(con: duckdb.DuckDBPyConnection, source: str, limit: int = 5):
    """
    Step 3: 抽樣資料，對齊語意
    """
    return con.execute(
        f"SELECT * FROM '{source}' LIMIT {limit}"
    ).fetchdf()


def step_4_grain_detection(schema_df) -> list:
    """
    Step 4: 嘗試判斷資料粒度
    只做 heuristic，不保證正確
    Expects:
        schema_df: Pandas DataFrame with a 'column_name' column, typically from step_2_schema.
    """
    columns = schema_df["column_name"].tolist()
    grains = []

    if "order_id" in columns:
        grains.append("order")
    if "product_id" in columns:
        grains.append("item")
    if "member_id" in columns:
        grains.append("member")

    return grains


def step_5_available_analyses(schema_df) -> list:
    """
    Step 5: 根據欄位，推測可做的分析類型
    Expects:
        schema_df: Pandas DataFrame with a 'column_name' column, typically from step_2_schema.
    """
    columns = schema_df["column_name"].tolist()
    analyses = []

    if "order_total_amount" in columns:
        analyses.append("total_amount_by_dimension")

    if "purchase_time" in columns:
        analyses.append("time_series_trend")

    if "member_id" in columns:
        analyses.append("member_ranking")

    return analyses


# Step 6: Data quality check
def step_6_data_quality_check(con: duckdb.DuckDBPyConnection, source: str, schema_df):
    """
    Step 6: 資料品質檢查
    檢查每個欄位的 null 值比例和基本統計。
    """
    columns = schema_df["column_name"].tolist()
    stats = {}
    for col in columns:
        try:
            # Null ratio
            nulls = con.execute(
                f"SELECT COUNT(*) FROM '{source}' WHERE {col} IS NULL"
            ).fetchone()[0]
            total = con.execute(
                f"SELECT COUNT(*) FROM '{source}'"
            ).fetchone()[0]
            null_ratio = nulls / total if total > 0 else None
            # Basic stats for numeric columns
            dtype = schema_df[schema_df["column_name"] == col]["column_type"].values[0]
            stat = {"null_ratio": null_ratio}
            if dtype.lower() in ["integer", "bigint", "double", "float", "numeric", "decimal"]:
                res = con.execute(
                    f"SELECT MIN({col}), MAX({col}), AVG({col}), STDDEV_POP({col}) FROM '{source}'"
                ).fetchone()
                stat.update({
                    "min": res[0],
                    "max": res[1],
                    "avg": res[2],
                    "stddev": res[3]
                })
            stats[col] = stat
        except Exception:
            stats[col] = {"error": "Could not compute stats"}
    return stats


# Step 7: Uniqueness check
def step_7_uniqueness_check(con: duckdb.DuckDBPyConnection, source: str, schema_df):
    """
    Step 7: 檢查每個欄位的唯一值數量
    """
    columns = schema_df["column_name"].tolist()
    unique_counts = {}
    for col in columns:
        try:
            count = con.execute(
                f"SELECT COUNT(DISTINCT {col}) FROM '{source}'"
            ).fetchone()[0]
            unique_counts[col] = count
        except Exception:
            unique_counts[col] = None
    return unique_counts


# Step 8: Null profile
def step_8_null_profile(con: duckdb.DuckDBPyConnection, source: str, schema_df):
    """
    Step 8: Null profile
    回傳每個欄位的 null 數量與比例
    """
    columns = schema_df["column_name"].tolist()
    null_profile = []
    total = con.execute(f"SELECT COUNT(*) FROM '{source}'").fetchone()[0]
    for col in columns:
        try:
            nulls = con.execute(
                f"SELECT COUNT(*) FROM '{source}' WHERE {col} IS NULL"
            ).fetchone()[0]
            null_profile.append({
                "column": col,
                "null_count": nulls,
                "null_ratio": nulls / total if total > 0 else None
            })
        except Exception:
            null_profile.append({
                "column": col,
                "error": "Could not compute null profile"
            })
    return null_profile


def derive_analysis_blacklist(grains: list, schema_df):
    """
    分析黑名單規則推導
    根據資料粒度（grains）與欄位結構（schema_df）
    推導出「一定會算錯」或「高風險」的分析組合。
    回傳黑名單規則列表，供 CLI / FastAPI 使用。
    Expects:
        grains: list of detected grains (e.g., from step_4_grain_detection)
        schema_df: Pandas DataFrame with a 'column_name' column, typically from step_2_schema.
    """
    blacklist = []
    columns = schema_df["column_name"].tolist()

    # 規則一：商品粒度使用訂單層金額（一定會重複計算）
    if "item" in grains and "order_total_amount" in columns:
        blacklist.append({
            "grain": "item",
            "metric": "order_total_amount",
            "reason": "訂單層金額在商品粒度下會被重複計算",
            "severity": "block",
        })

    # 規則二：訂單粒度使用商品層小計（語意錯誤）
    if "order" in grains and "item_subtotal" in columns:
        blacklist.append({
            "grain": "order",
            "metric": "item_subtotal",
            "reason": "商品層金額在訂單粒度下會失去原本語意",
            "severity": "block",
        })

    # 規則三：會員粒度直接使用原始金額欄位（需先聚合）
    raw_amount_columns = ["order_total_amount", "item_subtotal"]
    if "member" in grains and any(col in columns for col in raw_amount_columns):
        blacklist.append({
            "grain": "member",
            "metric": [col for col in raw_amount_columns if col in columns],
            "reason": "會員層分析需先進行聚合，直接使用原始金額容易造成誤解",
            "severity": "warning",
        })

    # 規則四：付款時間存在缺值，需搭配訂單狀態使用
    if "paid_at" in columns:
        blacklist.append({
            "grain": "all",
            "metric": "paid_at",
            "reason": "付款時間欄位存在缺值，進行分析時需搭配訂單狀態使用",
            "severity": "warning",
        })

    return blacklist