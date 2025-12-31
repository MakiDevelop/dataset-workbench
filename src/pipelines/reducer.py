import os
import shutil
import duckdb
import pandas as pd
from typing import List, Any, Tuple
from fastapi import UploadFile


# ----------------------------
# Utilities
# ----------------------------

def _find_input_file(dataset_id: str, input_dir: str) -> str:
    for fname in os.listdir(input_dir):
        if fname.startswith(dataset_id):
            return os.path.join(input_dir, fname)
    raise FileNotFoundError(f"Dataset {dataset_id} not found")


def _get_extension(filename: str) -> str:
    return os.path.splitext(filename)[1].lower()


# ----------------------------
# File handling
# ----------------------------

def save_upload_file(
    file: UploadFile,
    dataset_id: str,
    input_dir: str,
) -> str:
    ext = _get_extension(file.filename)
    if ext not in [".csv", ".xlsx", ".xls"]:
        raise ValueError("Only csv / xlsx / xls files are supported")

    save_path = os.path.join(input_dir, f"{dataset_id}{ext}")
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    return save_path


# ----------------------------
# Preview & schema
# ----------------------------

def get_preview(
    dataset_id: str,
    input_dir: str,
    limit: int = 200,
) -> dict:
    path = _find_input_file(dataset_id, input_dir)
    ext = _get_extension(path)

    con = duckdb.connect(database=":memory:")

    if ext == ".csv":
        con.execute(
            f"""
            CREATE VIEW v AS
            SELECT * FROM read_csv_auto('{path}', IGNORE_ERRORS=true)
            """
        )
    else:
        df = pd.read_excel(path)
        con.register("v", df)

    columns = [
        {"name": col[0], "type": col[1]}
        for col in con.execute("DESCRIBE v").fetchall()
    ]

    rows = con.execute(
        f"SELECT * FROM v LIMIT {limit}"
    ).fetchdf().to_dict(orient="records")

    total_rows = con.execute(
        "SELECT COUNT(*) FROM v"
    ).fetchone()[0]

    return {
        "columns": columns,
        "rows": rows,
        "total_rows": total_rows,
    }


# ----------------------------
# Distinct values
# ----------------------------

def get_distinct_values(
    dataset_id: str,
    input_dir: str,
    column: str,
    limit: int = 200,
) -> List[Any]:
    path = _find_input_file(dataset_id, input_dir)
    ext = _get_extension(path)

    con = duckdb.connect(database=":memory:")

    if ext == ".csv":
        con.execute(
            f"""
            CREATE VIEW v AS
            SELECT * FROM read_csv_auto('{path}', IGNORE_ERRORS=true)
            """
        )
    else:
        df = pd.read_excel(path)
        con.register("v", df)

    query = f"""
        SELECT DISTINCT "{column}"
        FROM v
        WHERE "{column}" IS NOT NULL
        LIMIT {limit}
    """

    result = con.execute(query).fetchall()
    return [r[0] for r in result]


# ----------------------------
# Filter & export
# ----------------------------

def _build_where_clause(filters, logic: str = "AND") -> Tuple[str, List[Any]]:
    clauses = []
    params = []

    for f in filters:
        col = f.column
        op = f.op.lower()
        val = f.value

        if op in ["=", "!=", ">", ">=", "<", "<="]:
            clauses.append(f"\"{col}\" {op} ?")
            params.append(val)

        elif op == "contains":
            clauses.append(f"\"{col}\" LIKE ?")
            params.append(f"%{val}%")

        elif op == "between":
            if not isinstance(val, list) or len(val) != 2:
                raise ValueError("between operator requires [start, end]")
            clauses.append(f"\"{col}\" BETWEEN ? AND ?")
            params.extend(val)

        elif op == "in":
            if not isinstance(val, list) or len(val) == 0:
                raise ValueError("in operator requires a non-empty list")
            placeholders = ",".join(["?"] * len(val))
            clauses.append(f"\"{col}\" IN ({placeholders})")
            params.extend(val)

        else:
            raise ValueError(f"Unsupported operator: {op}")

    if not clauses:
        return "", []

    joiner = " AND " if logic.upper() != "OR" else " OR "
    return "WHERE " + joiner.join(clauses), params


def preview_filtered_query(
    dataset_id: str,
    input_dir: str,
    filters,
    logic: str = "AND",
) -> dict:
    """
    Execute a COUNT(*) query with given filters to preview result size and catch SQL errors.
    Returns:
        {
            "ok": bool,
            "matched_rows": int | None,
            "elapsed_ms": int,
            "error": str | None
        }
    """
    import time

    start_time = time.time()

    try:
        path = _find_input_file(dataset_id, input_dir)
        ext = _get_extension(path)

        con = duckdb.connect(database=":memory:")

        if ext == ".csv":
            con.execute(
                f"""
                CREATE VIEW v AS
                SELECT * FROM read_csv_auto('{path}', IGNORE_ERRORS=true)
                """
            )
        else:
            df = pd.read_excel(path)
            con.register("v", df)

        where_sql, params = _build_where_clause(filters, logic)
        query = f"SELECT COUNT(*) FROM v {where_sql}"

        matched_rows = con.execute(query, params).fetchone()[0]

        elapsed_ms = int((time.time() - start_time) * 1000)

        return {
            "ok": True,
            "matched_rows": matched_rows,
            "elapsed_ms": elapsed_ms,
            "error": None,
        }

    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        return {
            "ok": False,
            "matched_rows": None,
            "elapsed_ms": elapsed_ms,
            "error": str(e),
        }


def export_filtered_data(
    dataset_id: str,
    input_dir: str,
    output_dir: str,
    export_format: str,
    filters,
    logic: str = "AND",
) -> Tuple[str, str]:
    path = _find_input_file(dataset_id, input_dir)
    ext = _get_extension(path)

    con = duckdb.connect(database=":memory:")

    if ext == ".csv":
        con.execute(
            f"""
            CREATE VIEW v AS
            SELECT * FROM read_csv_auto('{path}', IGNORE_ERRORS=true)
            """
        )
    else:
        df = pd.read_excel(path)
        con.register("v", df)

    where_sql, params = _build_where_clause(filters, logic)

    query = f"SELECT * FROM v {where_sql}"

    if export_format == "csv":
        filename = f"{dataset_id}_filtered.csv"
        output_path = os.path.join(output_dir, filename)

        con.execute(
            f"COPY ({query}) TO '{output_path}' (HEADER, DELIMITER ',')",
            params,
        )

    elif export_format == "xlsx":
        filename = f"{dataset_id}_filtered.xlsx"
        output_path = os.path.join(output_dir, filename)

        df_out = con.execute(query, params).fetchdf()
        df_out.to_excel(output_path, index=False)

    else:
        raise ValueError("export_format must be csv or xlsx")

    return output_path, filename