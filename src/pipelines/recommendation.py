"""
recommendation.py

智慧分析推薦引擎。
根據 bootstrap 結果（overview, schema, grains, blacklist）推算每個分析的推薦分數與理由。

設計原則：
- 純函式，不碰 I/O
- 推薦分數 0~100，越高越推薦
- 每個推薦附帶中文理由
- blacklist severity=block 的分析直接排除
"""

from __future__ import annotations

from typing import Any


# 所有可推薦的分析 key，對應到 capabilities
ALL_ANALYSIS_KEYS = [
    "time_trend",
    "top_products",
    "top_members",
    "aov",
    "new_vs_returning",
]


def recommend_analyses(
    overview: dict[str, Any],
    grains: list[str],
    schema_columns: list[str],
    blacklist: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    根據 bootstrap 結果推薦分析。

    Returns:
        排序好的推薦清單，每個元素包含：
        - key: 分析 key
        - score: 0~100 推薦分數
        - reason: 推薦/不推薦理由
        - status: "recommended" | "caution" | "blocked"
    """
    blocked_keys = _get_blocked_keys(blacklist)
    caution_keys = _get_caution_keys(blacklist)

    recommendations = []

    for key in ALL_ANALYSIS_KEYS:
        if key in blocked_keys:
            recommendations.append({
                "key": key,
                "score": 0,
                "reason": blocked_keys[key],
                "status": "blocked",
            })
            continue

        score, reason = _score_analysis(key, overview, grains, schema_columns)

        if key in caution_keys:
            score = min(score, 60)
            reason += f"（注意：{caution_keys[key]}）"
            status = "caution"
        elif score >= 70:
            status = "recommended"
        else:
            status = "caution"

        recommendations.append({
            "key": key,
            "score": score,
            "reason": reason,
            "status": status,
        })

    # 按分數降序
    recommendations.sort(key=lambda x: x["score"], reverse=True)
    return recommendations


def generate_insight(
    analysis_key: str,
    result_data: dict[str, Any],
) -> str:
    """
    根據分析結果產生一句話文字摘要。
    """
    if analysis_key == "time_trend":
        return _insight_time_trend(result_data)
    elif analysis_key == "aov":
        return _insight_aov(result_data)
    elif analysis_key == "top_products":
        return _insight_ranking(result_data, "商品")
    elif analysis_key == "top_members":
        return _insight_ranking(result_data, "會員")
    elif analysis_key == "new_vs_returning":
        return _insight_new_vs_returning(result_data)
    return ""


# ============================================================
# Internal helpers
# ============================================================

def _get_blocked_keys(blacklist: list[dict]) -> dict[str, str]:
    """從 blacklist 取出 severity=block 的分析對應。"""
    blocked = {}
    for rule in blacklist:
        if rule.get("severity") != "block":
            continue
        reason = rule.get("reason", "")
        grain = rule.get("grain", "")
        metric = rule.get("metric", "")

        # 根據 metric 推斷受影響的分析
        if isinstance(metric, str):
            if "order_total_amount" in metric:
                if grain == "item":
                    blocked["time_trend"] = reason
                    blocked["aov"] = reason
            if "item_subtotal" in metric:
                if grain == "order":
                    blocked["top_products"] = reason

    return blocked


def _get_caution_keys(blacklist: list[dict]) -> dict[str, str]:
    """從 blacklist 取出 severity=warning 的分析對應。"""
    caution = {}
    for rule in blacklist:
        if rule.get("severity") != "warning":
            continue
        reason = rule.get("reason", "")
        metric = rule.get("metric", "")

        if isinstance(metric, list):
            for m in metric:
                if "order_total_amount" in m:
                    caution["time_trend"] = reason
                    caution["aov"] = reason
                if "item_subtotal" in m:
                    caution["top_products"] = reason
        elif isinstance(metric, str):
            if "paid_at" in metric:
                caution["time_trend"] = reason

    return caution


def _score_analysis(
    key: str,
    overview: dict,
    grains: list[str],
    columns: list[str],
) -> tuple[int, str]:
    """計算單一分析的推薦分數 + 理由。"""

    row_count = overview.get("row_count", 0)
    has_time = bool(overview.get("time_column") or overview.get("time_range"))

    if key == "time_trend":
        if "purchase_time" not in columns:
            return 10, "缺少 purchase_time 欄位，無法進行時間趨勢分析"
        if not has_time:
            return 20, "未偵測到有效時間範圍"
        if row_count < 30:
            return 50, "資料量偏少，趨勢分析參考價值有限"
        return 90, "有完整時間欄位，適合觀察銷售趨勢變化"

    elif key == "aov":
        if "order_total_amount" not in columns or "order_id" not in columns:
            return 10, "缺少計算客單價所需的欄位"
        if "purchase_time" not in columns:
            return 30, "缺少時間欄位，無法觀察客單價趨勢"
        if row_count < 30:
            return 50, "資料量偏少，客單價趨勢參考價值有限"
        return 85, "可計算客單價趨勢，適合觀察消費力變化"

    elif key == "top_products":
        if "product_name" not in columns:
            return 10, "缺少 product_name 欄位"
        if "item_subtotal" not in columns:
            return 30, "缺少 item_subtotal 欄位，無法計算商品銷售額"
        if "item" in grains:
            return 95, "資料為商品粒度，非常適合做商品排行分析"
        return 75, "有商品欄位，可進行排行分析"

    elif key == "top_members":
        if "member_id" not in columns:
            return 10, "缺少 member_id 欄位"
        if "order_total_amount" not in columns:
            return 30, "缺少金額欄位，無法計算會員貢獻"
        member_count = overview.get("member_count")
        if member_count and member_count < 5:
            return 40, "會員數過少，排行分析意義有限"
        return 80, "有會員與金額資料，適合找出高貢獻客戶"

    elif key == "new_vs_returning":
        if "first_purchase_flag" not in columns:
            return 10, "缺少 first_purchase_flag 欄位"
        if "order_id" not in columns:
            return 30, "缺少 order_id 欄位"
        return 85, "可分析新客與回購客結構，判斷客群健康度"

    return 50, "可執行但無特別推薦理由"


# ============================================================
# Insight generators
# ============================================================

def _insight_time_trend(data: dict) -> str:
    series = data.get("series", [])
    if not series:
        return "無趨勢資料"
    values = [p.get("value", 0) for p in series if p.get("value") is not None]
    if not values:
        return "無有效數值"
    total = sum(values)
    avg = total / len(values)
    latest = values[-1]
    trend = "上升" if latest > avg else "下降" if latest < avg * 0.8 else "持平"
    return f"期間總銷售額 {total:,.0f}，日均 {avg:,.0f}，近期趨勢{trend}"


def _insight_aov(data: dict) -> str:
    series = data.get("series", [])
    if not series:
        return "無客單價資料"
    values = [p.get("value", 0) for p in series if p.get("value") is not None]
    if not values:
        return "無有效數值"
    avg_aov = sum(values) / len(values)
    max_aov = max(values)
    min_aov = min(values)
    return f"平均客單價 {avg_aov:,.0f}，最高 {max_aov:,.0f}，最低 {min_aov:,.0f}"


def _insight_ranking(data: dict, dimension: str) -> str:
    items = data.get("items", [])
    if not items:
        return f"無{dimension}排行資料"
    top = items[0]
    total = sum(i.get("value", 0) for i in items)
    top_pct = (top.get("value", 0) / total * 100) if total > 0 else 0
    return f"第一名 {top.get('key', '?')} 佔 {top_pct:.1f}%（{top.get('value', 0):,.0f}），前 {len(items)} 名合計 {total:,.0f}"


def _insight_new_vs_returning(data: dict) -> str:
    items = data.get("items", [])
    if not items:
        return "無新客/回購客資料"
    counts = {i.get("key"): i.get("value", 0) for i in items}
    new_count = counts.get("new", 0)
    ret_count = counts.get("returning", 0)
    total = new_count + ret_count
    if total == 0:
        return "無訂單資料"
    new_pct = new_count / total * 100
    return f"新客 {new_count:,} 筆（{new_pct:.1f}%），回購客 {ret_count:,} 筆（{100-new_pct:.1f}%）"
