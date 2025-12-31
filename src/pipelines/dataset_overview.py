from __future__ import annotations

import pandas as pd
from typing import Dict, Any, Optional
from datetime import datetime

# === Dataset scale column candidates ===
ORDER_ID_CANDIDATES = ["order_id", "order_no"]
ORDER_ITEM_STATUS_EXCLUDE = ["cancel", "cancelled", "refunded"]
MEMBER_ID_CANDIDATES = ["member_id"]
PRODUCT_ID_CANDIDATES = ["product_id"]

# === Datetime detection candidates (ordered by priority) ===
DATETIME_CANDIDATES = [
    "purchase_time",
    "order_time",
    "created_at",
    "created_time",
    "order_date",
]


def generate_dataset_overview(
    df: pd.DataFrame,
    file_size_bytes: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Generate high-level overview for a dataset.

    Design principles:
    - Single pass mindset (avoid expensive operations when possible)
    - No visualization
    - No I/O
    - No API / UI concern
    - Pure dataset signals

    Parameters
    ----------
    df : pd.DataFrame
        Input dataset already loaded in memory.
    file_size_bytes : Optional[int]
        Original file size in bytes, if known (e.g. from upload metadata).

    Returns
    -------
    dict
        Structured overview information for the dataset.
    """

    overview: Dict[str, Any] = {}

    # --- Basic shape ---
    row_count = len(df)
    column_count = len(df.columns)

    overview["row_count"] = row_count
    overview["column_count"] = column_count

    # --- File size estimate ---
    if file_size_bytes is not None:
        overview["file_size_bytes"] = file_size_bytes
        overview["file_size_mb"] = round(file_size_bytes / 1024 / 1024, 2)
    else:
        overview["file_size_bytes"] = None
        overview["file_size_mb"] = None

    # --- Column type summary ---
    dtype_summary: Dict[str, int] = {}
    for dtype in df.dtypes.astype(str):
        dtype_summary[dtype] = dtype_summary.get(dtype, 0) + 1

    overview["column_type_summary"] = dtype_summary

    # --- Missing value analysis ---
    if row_count > 0:
        missing_ratio = (df.isna().sum() / row_count).sort_values(ascending=False)
        top_missing = (
            missing_ratio[missing_ratio > 0]
            .head(5)
            .round(4)
            .to_dict()
        )
    else:
        top_missing = {}

    overview["missing_value_top_columns"] = top_missing

    # --- Dataset scale metrics ---

    # 1. 訂單張數（order-level distinct）
    order_count = None
    order_item_count = None

    for col in ORDER_ID_CANDIDATES:
        if col in df.columns:
            order_count = df[col].dropna().nunique()
            break

    # 2. 訂單明細數（排除特定狀態）
    if order_count is not None:
        order_item_df = df

        # 嘗試排除取消 / 退款狀態
        if "status" in df.columns:
            order_item_df = df[
                ~df["status"].astype(str).str.lower().isin(ORDER_ITEM_STATUS_EXCLUDE)
            ]

        order_item_count = len(order_item_df)

    overview["order_count"] = order_count
    overview["order_item_count"] = order_item_count

    # 3. 會員數（僅計算有 member_id）
    member_count = None
    for col in MEMBER_ID_CANDIDATES:
        if col in df.columns:
            member_count = df[col].dropna().nunique()
            break

    overview["member_count"] = member_count

    # 4. 商品數（distinct product_id）
    product_count = None
    for col in PRODUCT_ID_CANDIDATES:
        if col in df.columns:
            product_count = df[col].dropna().nunique()
            break

    overview["product_count"] = product_count

    # --- Datetime detection & range (optimized) ---

    datetime_columns = []
    date_ranges: Dict[str, Dict[str, Optional[str]]] = {}

    for col in DATETIME_CANDIDATES:
        if col not in df.columns:
            continue

        try:
            # 只抽樣極少量資料做判斷
            sample = df[col].dropna().head(50)
            if sample.empty:
                continue

            # 若 sample 能成功 parse，才視為時間欄位
            pd.to_datetime(sample, errors="raise")

            parsed_col = pd.to_datetime(df[col], errors="coerce")

            if parsed_col.notna().any():
                datetime_columns.append(col)
                date_ranges[col] = {
                    "start": parsed_col.min().isoformat(),
                    "end": parsed_col.max().isoformat(),
                }
                break  # 命中第一個時間欄位就停

        except Exception:
            continue

    overview["datetime_columns"] = datetime_columns
    overview["date_range"] = date_ranges

    # --- Metadata ---
    overview["generated_at"] = datetime.utcnow().isoformat() + "Z"

    return overview