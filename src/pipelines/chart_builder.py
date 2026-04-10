"""
chart_builder.py

為每種分析結果產生 Plotly chart spec（data + layout）。
前端用 Plotly.newPlot(div, spec.data, spec.layout) 即可渲染。

設計原則：
- 純函式，不碰 I/O
- 回傳 dict（可直接被 Pydantic ChartSpec serialize）
- 支援：line（時間趨勢）、bar（排行）、pie（占比）
"""

from __future__ import annotations
from typing import Any


def build_time_series_chart(
    series: list[dict],
    metric_label: str,
    granularity: str = "day",
    chart_title: str | None = None,
    fill: bool = False,
) -> dict[str, Any]:
    """折線圖：時間序列趨勢（time-trend, AOV, daily-orders）"""
    time_key = "time" if "time" in (series[0] if series else {}) else "date"
    x = [p[time_key] for p in series]
    y = [p["value"] for p in series]

    trace = {
        "x": x,
        "y": y,
        "type": "scatter",
        "mode": "lines+markers",
        "name": metric_label,
        "line": {"width": 2, "shape": "spline"},
        "marker": {"size": 4},
        "hovertemplate": "%{x}<br>%{y:,.0f}<extra></extra>",
    }
    if fill:
        trace["fill"] = "tozeroy"
        trace["fillcolor"] = "rgba(37, 99, 235, 0.1)"

    layout = {
        "title": chart_title,
        "xaxis": {"title": "日期" if granularity == "day" else "月份", "type": "category"},
        "yaxis": {"title": metric_label, "tickformat": ",.0f"},
        "template": "plotly_white",
        "height": 400,
        "margin": {"l": 60, "r": 30, "t": 50, "b": 50},
        "hovermode": "x unified",
    }

    return {"data": [trace], "layout": layout}


def build_ranking_chart(
    items: list[dict],
    dimension_label: str,
    metric_label: str,
    chart_title: str | None = None,
) -> dict[str, Any]:
    """水平長條圖：排行（top-products, top-members）"""
    # 倒序讓最高的在上面
    keys = [str(item["key"]) for item in reversed(items)]
    values = [item["value"] for item in reversed(items)]

    trace = {
        "x": values,
        "y": keys,
        "type": "bar",
        "orientation": "h",
        "name": metric_label,
        "marker": {"color": "rgba(37, 99, 235, 0.8)"},
        "text": [f"{v:,.0f}" for v in values],
        "textposition": "outside",
        "hovertemplate": "%{y}<br>%{x:,.0f}<extra></extra>",
    }

    layout = {
        "title": chart_title,
        "xaxis": {"title": metric_label, "tickformat": ",.0f"},
        "yaxis": {"title": dimension_label, "automargin": True},
        "template": "plotly_white",
        "height": max(300, len(items) * 35 + 100),
        "margin": {"l": 140, "r": 60, "t": 50, "b": 50},
        "hovermode": "closest",
    }

    return {"data": [trace], "layout": layout}


def build_pie_chart(
    items: list[dict],
    chart_title: str | None = None,
) -> dict[str, Any]:
    """圓餅圖：占比（new-vs-returning）"""
    labels = [str(item["key"]) for item in items]
    values = [item["value"] for item in items]

    # 自訂顏色：new=藍, returning=橘
    color_map = {"new": "#2563eb", "returning": "#f59e0b"}
    colors = [color_map.get(l, "#94a3b8") for l in labels]

    # 中文 label
    label_map = {"new": "新客", "returning": "回購客"}
    display_labels = [label_map.get(l, l) for l in labels]

    trace = {
        "labels": display_labels,
        "values": values,
        "type": "pie",
        "hole": 0.4,
        "marker": {"colors": colors},
        "textposition": "inside",
        "hovertemplate": "%{label}<br>%{value:,} 筆 (%{percent})<extra></extra>",
    }

    layout = {
        "title": chart_title,
        "template": "plotly_white",
        "height": 400,
        "margin": {"l": 30, "r": 30, "t": 50, "b": 30},
        "showlegend": True,
    }

    return {"data": [trace], "layout": layout}
