from __future__ import annotations

"""
analysis.py

所有交易資料分析相關 API routes。

【重要結構規則】
- router = APIRouter() 必須在任何 @router.* 裝飾器之前定義
- 本檔案只能存在一個 router
- 所有分析皆為「安全分析」，刻意限制自由度以避免錯誤解讀
"""

import uuid
from pathlib import Path
from datetime import datetime

import duckdb
import pandas as pd
from fastapi import APIRouter, UploadFile, File, HTTPException, Body

from pipelines.analysis_bootstrap import (
    step_1_overview,
    step_2_schema,
    step_3_sample,
    step_4_grain_detection,
    step_5_available_analyses,
    derive_analysis_blacklist,
)

# === Router 一定要先定義（否則 decorator 會 NameError） ===
router = APIRouter()

# === 使用者上傳檔案的存放位置 ===
DATA_INPUT_DIR = Path("data/input")
DATA_INPUT_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/ping")
def ping():
    """健康檢查用 endpoint。"""
    return {"status": "ok"}


@router.post("/bootstrap")
async def bootstrap(file: UploadFile = File(...)):
    """
    上傳 CSV / XLS / XLSX 並執行 bootstrap 分析：
    - 統一將檔案轉為 CSV
    - 回傳資料結構、黑名單、前 100 筆 preview（供 UI 使用）
    """
    filename = file.filename or ""
    ext = filename.split(".")[-1].lower()
    if ext not in ("csv", "xls", "xlsx"):
        raise HTTPException(status_code=400, detail="Unsupported file type")

    analysis_id = str(uuid.uuid4())
    save_path = DATA_INPUT_DIR / f"{analysis_id}.csv"

    if ext == "csv":
        save_path.write_bytes(await file.read())
    else:
        df = pd.read_excel(await file.read())
        df.to_csv(save_path, index=False)

    conn = duckdb.connect()

    overview = step_1_overview(conn, str(save_path))
    schema_df = step_2_schema(conn, str(save_path))
    preview_df = step_3_sample(conn, str(save_path), limit=100)
    grains = step_4_grain_detection(schema_df)
    available_analyses = step_5_available_analyses(schema_df)
    blacklist = derive_analysis_blacklist(grains, schema_df)

    return {
        "analysis_id": analysis_id,
        "overview": overview,
        "schema": schema_df.to_dict(orient="records"),
        "preview": preview_df.to_dict(orient="records"),
        "grains": grains,
        "available_analyses": available_analyses,
        "blacklist": blacklist,
    }


@router.post("/time-trend")
async def time_trend(payload: dict = Body(...)):
    """
    安全的時間序列趨勢分析
    - 時間欄位：purchase_time
    - 指標：SUM(order_total_amount)
    - granularity：day / month
    """
    analysis_id = payload.get("analysis_id")
    if not analysis_id:
        raise HTTPException(status_code=400, detail="analysis_id is required")

    granularity = payload.get("granularity", "day")
    if granularity not in ("day", "month"):
        raise HTTPException(status_code=400, detail="granularity must be 'day' or 'month'")

    csv_path = DATA_INPUT_DIR / f"{analysis_id}.csv"
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="Analysis data not found")

    conn = duckdb.connect()
    query = f"""
        SELECT
            DATE_TRUNC('{granularity}', purchase_time) AS time,
            SUM(order_total_amount) AS value
        FROM read_csv_auto('{str(csv_path)}')
        GROUP BY time
        ORDER BY time
    """
    rows = conn.execute(query).fetchall()

    series = [
        {
            "time": r[0].strftime("%Y-%m-%d") if granularity == "day" else r[0].strftime("%Y-%m"),
            "value": r[1],
        }
        for r in rows
    ]

    return {
        "analysis_id": analysis_id,
        "granularity": granularity,
        "time_column": "purchase_time",
        "metric": "order_total_amount",
        "series": series,
    }


@router.post("/top-products")
async def top_products(payload: dict = Body(...)):
    """
    熱門商品排行（安全分析）
    - 維度：product_name
    - 指標：SUM(item_subtotal)
    """
    analysis_id = payload.get("analysis_id")
    if not analysis_id:
        raise HTTPException(status_code=400, detail="analysis_id is required")

    limit = int(payload.get("limit", 10))
    if limit <= 0:
        limit = 10

    csv_path = DATA_INPUT_DIR / f"{analysis_id}.csv"
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="Analysis data not found")

    conn = duckdb.connect()
    query = f"""
        SELECT
            product_name AS key,
            SUM(item_subtotal) AS value
        FROM read_csv_auto('{str(csv_path)}')
        GROUP BY product_name
        ORDER BY value DESC
        LIMIT {limit}
    """
    rows = conn.execute(query).fetchall()

    return {
        "analysis_id": analysis_id,
        "dimension": "product_name",
        "metric": "item_subtotal",
        "limit": limit,
        "items": [{"key": r[0], "value": r[1]} for r in rows],
    }


@router.post("/top-members")
async def top_members(payload: dict = Body(...)):
    """
    高貢獻會員排行（安全分析）
    - 維度：member_id
    - 指標：SUM(order_total_amount)
    """
    analysis_id = payload.get("analysis_id")
    if not analysis_id:
        raise HTTPException(status_code=400, detail="analysis_id is required")

    limit = int(payload.get("limit", 10))
    if limit <= 0:
        limit = 10

    csv_path = DATA_INPUT_DIR / f"{analysis_id}.csv"
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="Analysis data not found")

    conn = duckdb.connect()
    query = f"""
        SELECT
            member_id AS key,
            SUM(order_total_amount) AS value
        FROM read_csv_auto('{str(csv_path)}')
        GROUP BY member_id
        ORDER BY value DESC
        LIMIT {limit}
    """
    rows = conn.execute(query).fetchall()

    return {
        "analysis_id": analysis_id,
        "dimension": "member_id",
        "metric": "order_total_amount",
        "limit": limit,
        "items": [{"key": r[0], "value": r[1]} for r in rows],
    }


@router.post("/aov")
async def aov(payload: dict = Body(...)):
    """
    平均客單價（AOV）
    - 計算方式：SUM(order_total_amount) / COUNT(DISTINCT order_id)
    - granularity：day / month
    """
    analysis_id = payload.get("analysis_id")
    if not analysis_id:
        raise HTTPException(status_code=400, detail="analysis_id is required")

    granularity = payload.get("granularity", "day")
    if granularity not in ("day", "month"):
        raise HTTPException(status_code=400, detail="granularity must be 'day' or 'month'")

    csv_path = DATA_INPUT_DIR / f"{analysis_id}.csv"
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="Analysis data not found")

    conn = duckdb.connect()
    query = f"""
        SELECT
            DATE_TRUNC('{granularity}', purchase_time) AS time,
            SUM(order_total_amount) * 1.0 / COUNT(DISTINCT order_id) AS value
        FROM read_csv_auto('{str(csv_path)}')
        GROUP BY time
        ORDER BY time
    """
    rows = conn.execute(query).fetchall()

    series = [
        {
            "time": r[0].strftime("%Y-%m-%d") if granularity == "day" else r[0].strftime("%Y-%m"),
            "value": r[1],
        }
        for r in rows
    ]

    return {
        "analysis_id": analysis_id,
        "granularity": granularity,
        "metric": "aov",
        "series": series,
    }


@router.post("/new-vs-returning")
async def new_vs_returning(payload: dict = Body(...)):
    """
    新客 vs 回購客占比分析
    - 維度：first_purchase_flag
    - 指標：訂單數
    """
    analysis_id = payload.get("analysis_id")
    if not analysis_id:
        raise HTTPException(status_code=400, detail="analysis_id is required")

    csv_path = DATA_INPUT_DIR / f"{analysis_id}.csv"
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="Analysis data not found")

    conn = duckdb.connect()
    query = f"""
        SELECT
            CASE WHEN first_purchase_flag THEN 'new' ELSE 'returning' END AS key,
            COUNT(DISTINCT order_id) AS value
        FROM read_csv_auto('{str(csv_path)}')
        GROUP BY key
    """
    rows = conn.execute(query).fetchall()

    counts = {r[0]: r[1] for r in rows}
    return {
        "analysis_id": analysis_id,
        "dimension": "customer_type",
        "items": [
            {"key": "new", "value": counts.get("new", 0)},
            {"key": "returning", "value": counts.get("returning", 0)},
        ],
    }


@router.get("/capabilities")
def capabilities():
    """
    系統支援的分析能力清單（前端請以此為準）
    """
    return [
        {
            "key": "time_trend",
            "label": "時間序列趨勢分析",
            "description": "依日期或月份聚合銷售金額，觀察時間趨勢。",
            "chart": "line",
        },
        {
            "key": "top_products",
            "label": "熱門商品排行",
            "description": "依商品名稱彙總銷售金額，列出銷售額最高的商品。",
            "chart": "bar",
        },
        {
            "key": "top_members",
            "label": "高貢獻會員排行",
            "description": "依會員彙總訂單金額，找出貢獻最高的客戶。",
            "chart": "bar",
        },
        {
            "key": "aov",
            "label": "平均客單價（AOV）",
            "description": "計算每筆訂單的平均消費金額。",
            "chart": "line",
        },
        {
            "key": "new_vs_returning",
            "label": "新客與回購客占比",
            "description": "比較新客與回購客的訂單數量占比。",
            "chart": "pie",
        },
    ]