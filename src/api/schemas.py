"""
Pydantic schemas for all API request/response models.

Design:
- Analysis endpoints: AnalysisRequest → 各自的 Response model
- Reduce endpoints: 已在 reduce.py 定義（FilterRule, ExportRequest）
- 所有 response_model 註冊後，FastAPI 自動產生 OpenAPI docs
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any, Optional


# ============================================================
# Common / Shared
# ============================================================

class AnalysisRequest(BaseModel):
    """所有需要 analysis_id 的 endpoint 共用 request body。"""
    analysis_id: str


class GranularityRequest(BaseModel):
    """帶有時間粒度的分析 request。"""
    analysis_id: str
    granularity: str = Field(default="day", pattern="^(day|month)$")


class RankingRequest(BaseModel):
    """排行類分析 request（top-products, top-members）。"""
    analysis_id: str
    limit: int = Field(default=10, gt=0)


# ============================================================
# Bootstrap
# ============================================================

class SchemaColumn(BaseModel):
    column_name: str
    column_type: str
    null: Optional[str] = None
    key: Optional[str] = None
    default: Optional[str] = None
    extra: Optional[str] = None


class BootstrapOverview(BaseModel):
    row_count: int
    time_column: Optional[str] = None
    time_range: Optional[dict[str, Any]] = None


class BlacklistRule(BaseModel):
    grain: str
    metric: Any  # str or list[str]
    reason: str
    severity: str


class BootstrapResponse(BaseModel):
    analysis_id: str
    overview: BootstrapOverview
    schema_: list[SchemaColumn] = Field(alias="schema")
    preview: list[dict[str, Any]]
    grains: list[str]
    available_analyses: list[str]
    blacklist: list[BlacklistRule]

    model_config = {"populate_by_name": True}


# ============================================================
# Overview
# ============================================================

class DateRange(BaseModel):
    start: Optional[str] = None
    end: Optional[str] = None


class DatasetOverviewData(BaseModel):
    row_count: int
    column_count: int
    file_size_bytes: Optional[int] = None
    file_size_mb: Optional[float] = None
    column_type_summary: dict[str, int]
    missing_value_top_columns: dict[str, float]
    order_count: Optional[int] = None
    order_item_count: Optional[int] = None
    member_count: Optional[int] = None
    product_count: Optional[int] = None
    datetime_columns: list[str] = []
    date_range: dict[str, DateRange] = {}
    generated_at: str


class DatasetOverviewResponse(BaseModel):
    analysis_id: str
    overview: DatasetOverviewData


# ============================================================
# Time Series (time-trend, aov, daily-orders)
# ============================================================

class TimeSeriesPoint(BaseModel):
    time: Optional[str] = None
    date: Optional[str] = None
    value: Any


class TimeTrendResponse(BaseModel):
    analysis_id: str
    granularity: str
    time_column: str
    metric: str
    series: list[TimeSeriesPoint]
    chart: Optional[ChartSpec] = None


class AOVResponse(BaseModel):
    analysis_id: str
    granularity: str
    metric: str = "aov"
    series: list[TimeSeriesPoint]
    chart: Optional[ChartSpec] = None


class DailyOrdersResponse(BaseModel):
    analysis_id: str
    time_column: str
    metric: str = "order_count"
    series: list[TimeSeriesPoint]
    chart: Optional[ChartSpec] = None


# ============================================================
# Ranking (top-products, top-members)
# ============================================================

class RankingItem(BaseModel):
    key: Any
    value: Any


class RankingResponse(BaseModel):
    analysis_id: str
    dimension: str
    metric: str
    limit: int
    items: list[RankingItem]
    chart: Optional[ChartSpec] = None


# ============================================================
# New vs Returning
# ============================================================

class NewVsReturningResponse(BaseModel):
    analysis_id: str
    dimension: str = "customer_type"
    items: list[RankingItem]
    chart: Optional[ChartSpec] = None


# ============================================================
# Capabilities
# ============================================================

class CapabilityItem(BaseModel):
    key: str
    label: str
    description: str
    chart: str


# ============================================================
# Chart spec (Epic 1: 視覺化引擎)
# ============================================================

class PlotlyTrace(BaseModel):
    """Single Plotly trace (data series)."""
    x: Optional[list[Any]] = None
    y: Optional[list[Any]] = None
    labels: Optional[list[Any]] = None
    values: Optional[list[Any]] = None
    type: str = "scatter"
    mode: Optional[str] = None
    name: Optional[str] = None
    marker: Optional[dict[str, Any]] = None
    text: Optional[list[str]] = None
    textposition: Optional[str] = None
    hovertemplate: Optional[str] = None
    hole: Optional[float] = None
    fill: Optional[str] = None
    line: Optional[dict[str, Any]] = None


class PlotlyLayout(BaseModel):
    """Plotly layout configuration."""
    title: Optional[str] = None
    xaxis: Optional[dict[str, Any]] = None
    yaxis: Optional[dict[str, Any]] = None
    template: str = "plotly_white"
    height: Optional[int] = None
    margin: Optional[dict[str, int]] = None
    showlegend: Optional[bool] = None
    hovermode: Optional[str] = "x unified"


class ChartSpec(BaseModel):
    """Complete Plotly chart spec, ready for Plotly.newPlot()."""
    data: list[PlotlyTrace]
    layout: PlotlyLayout


# ============================================================
# Recommendation (Epic 4: 智慧分析推薦)
# ============================================================

class RecommendationItem(BaseModel):
    key: str
    score: int
    reason: str
    status: str  # "recommended" | "caution" | "blocked"


class RecommendationResponse(BaseModel):
    analysis_id: str
    recommendations: list[RecommendationItem]


class InsightRequest(BaseModel):
    analysis_id: str
    analysis_key: str
    result_data: dict[str, Any]


class InsightResponse(BaseModel):
    analysis_id: str
    analysis_key: str
    insight: str
