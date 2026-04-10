"""
Unit tests for pipeline modules:
- analysis_bootstrap (step 1-8)
- dataset_overview
- chart_builder
"""

from __future__ import annotations

import duckdb
import pandas as pd
import pytest

from pipelines.analysis_bootstrap import (
    step_1_overview,
    step_2_schema,
    step_3_sample,
    step_4_grain_detection,
    step_5_available_analyses,
    step_6_data_quality_check,
    step_7_uniqueness_check,
    step_8_null_profile,
    derive_analysis_blacklist,
)
from pipelines.dataset_overview import generate_dataset_overview
from pipelines.chart_builder import (
    build_time_series_chart,
    build_ranking_chart,
    build_pie_chart,
)


# ============================================================
# analysis_bootstrap tests
# ============================================================

class TestBootstrapPipeline:
    def test_step_1_overview(self, small_csv):
        conn = duckdb.connect()
        result = step_1_overview(conn, str(small_csv))
        assert "row_count" in result
        assert result["row_count"] == 50
        # time_column is optional — depends on DuckDB auto-detection of datetime columns
        if "time_column" in result:
            assert result["time_column"] in ("purchase_time", "created_at", "paid_at")

    def test_step_2_schema(self, small_csv):
        conn = duckdb.connect()
        df = step_2_schema(conn, str(small_csv))
        assert isinstance(df, pd.DataFrame)
        assert "column_name" in df.columns
        assert len(df) > 0
        expected_cols = {"order_id", "member_id", "product_id", "order_total_amount"}
        actual_cols = set(df["column_name"].tolist())
        assert expected_cols.issubset(actual_cols)

    def test_step_3_sample(self, small_csv):
        conn = duckdb.connect()
        df = step_3_sample(conn, str(small_csv), limit=5)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 5

    def test_step_3_sample_limit(self, small_csv):
        conn = duckdb.connect()
        df = step_3_sample(conn, str(small_csv), limit=10)
        assert len(df) == 10

    def test_step_4_grain_detection(self, small_csv):
        conn = duckdb.connect()
        schema_df = step_2_schema(conn, str(small_csv))
        grains = step_4_grain_detection(schema_df)
        assert isinstance(grains, list)
        assert "order" in grains
        assert "member" in grains

    def test_step_5_available_analyses(self, small_csv):
        conn = duckdb.connect()
        schema_df = step_2_schema(conn, str(small_csv))
        analyses = step_5_available_analyses(schema_df)
        assert isinstance(analyses, list)
        assert "total_amount_by_dimension" in analyses
        assert "time_series_trend" in analyses
        assert "member_ranking" in analyses

    def test_step_6_data_quality_check(self, small_csv):
        conn = duckdb.connect()
        schema_df = step_2_schema(conn, str(small_csv))
        stats = step_6_data_quality_check(conn, str(small_csv), schema_df)
        assert isinstance(stats, dict)
        assert "order_id" in stats
        assert "null_ratio" in stats["order_id"]

    def test_step_7_uniqueness_check(self, small_csv):
        conn = duckdb.connect()
        schema_df = step_2_schema(conn, str(small_csv))
        uniques = step_7_uniqueness_check(conn, str(small_csv), schema_df)
        assert isinstance(uniques, dict)
        assert uniques["order_id"] > 0

    def test_step_8_null_profile(self, small_csv):
        conn = duckdb.connect()
        schema_df = step_2_schema(conn, str(small_csv))
        profile = step_8_null_profile(conn, str(small_csv), schema_df)
        assert isinstance(profile, list)
        assert len(profile) > 0
        assert "column" in profile[0]
        assert "null_count" in profile[0]

    def test_derive_analysis_blacklist(self, small_csv):
        conn = duckdb.connect()
        schema_df = step_2_schema(conn, str(small_csv))
        grains = step_4_grain_detection(schema_df)
        blacklist = derive_analysis_blacklist(grains, schema_df)
        assert isinstance(blacklist, list)


# ============================================================
# dataset_overview tests
# ============================================================

class TestDatasetOverview:
    def test_generate_overview(self, small_csv):
        df = pd.read_csv(small_csv)
        overview = generate_dataset_overview(df, file_size_bytes=1024)
        assert overview["row_count"] == 50
        assert overview["column_count"] > 0
        assert overview["file_size_bytes"] == 1024
        assert overview["file_size_mb"] is not None
        assert "column_type_summary" in overview
        assert "generated_at" in overview

    def test_overview_detects_orders(self, small_csv):
        df = pd.read_csv(small_csv)
        overview = generate_dataset_overview(df)
        assert overview["order_count"] is not None
        assert overview["order_count"] > 0

    def test_overview_detects_members(self, small_csv):
        df = pd.read_csv(small_csv)
        overview = generate_dataset_overview(df)
        assert overview["member_count"] is not None
        assert overview["member_count"] > 0

    def test_overview_detects_products(self, small_csv):
        df = pd.read_csv(small_csv)
        overview = generate_dataset_overview(df)
        assert overview["product_count"] is not None
        assert overview["product_count"] > 0

    def test_overview_empty_dataframe(self):
        df = pd.DataFrame()
        overview = generate_dataset_overview(df)
        assert overview["row_count"] == 0
        assert overview["column_count"] == 0


# ============================================================
# chart_builder tests
# ============================================================

class TestChartBuilder:
    def test_time_series_chart_structure(self):
        series = [
            {"time": "2024-01-01", "value": 100},
            {"time": "2024-01-02", "value": 200},
            {"time": "2024-01-03", "value": 150},
        ]
        chart = build_time_series_chart(series, metric_label="Sales")
        assert "data" in chart
        assert "layout" in chart
        assert len(chart["data"]) == 1
        assert chart["data"][0]["type"] == "scatter"
        assert chart["data"][0]["x"] == ["2024-01-01", "2024-01-02", "2024-01-03"]
        assert chart["data"][0]["y"] == [100, 200, 150]

    def test_time_series_chart_with_date_key(self):
        series = [
            {"date": "2024-01-01", "value": 50},
            {"date": "2024-01-02", "value": 80},
        ]
        chart = build_time_series_chart(series, metric_label="Orders")
        assert chart["data"][0]["x"] == ["2024-01-01", "2024-01-02"]

    def test_time_series_chart_fill(self):
        series = [{"time": "2024-01-01", "value": 10}]
        chart = build_time_series_chart(series, metric_label="Test", fill=True)
        assert chart["data"][0].get("fill") == "tozeroy"

    def test_ranking_chart_structure(self):
        items = [
            {"key": "Product A", "value": 500},
            {"key": "Product B", "value": 300},
            {"key": "Product C", "value": 100},
        ]
        chart = build_ranking_chart(items, dimension_label="Product", metric_label="Sales")
        assert len(chart["data"]) == 1
        trace = chart["data"][0]
        assert trace["type"] == "bar"
        assert trace["orientation"] == "h"
        # reversed order (highest on top)
        assert trace["y"] == ["Product C", "Product B", "Product A"]
        assert trace["x"] == [100, 300, 500]

    def test_ranking_chart_dynamic_height(self):
        items = [{"key": f"P{i}", "value": i * 10} for i in range(20)]
        chart = build_ranking_chart(items, dimension_label="P", metric_label="V")
        assert chart["layout"]["height"] >= 300

    def test_pie_chart_structure(self):
        items = [
            {"key": "new", "value": 60},
            {"key": "returning", "value": 40},
        ]
        chart = build_pie_chart(items)
        assert len(chart["data"]) == 1
        trace = chart["data"][0]
        assert trace["type"] == "pie"
        assert trace["hole"] == 0.4
        assert trace["labels"] == ["新客", "回購客"]
        assert trace["values"] == [60, 40]

    def test_pie_chart_custom_keys(self):
        items = [
            {"key": "online", "value": 70},
            {"key": "offline", "value": 30},
        ]
        chart = build_pie_chart(items, chart_title="Channel Split")
        assert chart["layout"]["title"] == "Channel Split"
        assert chart["data"][0]["labels"] == ["online", "offline"]
