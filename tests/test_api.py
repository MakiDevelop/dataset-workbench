"""
Integration tests for all API endpoints using FastAPI TestClient.

Tests the full request/response cycle including file upload,
bootstrap analysis, and all analysis endpoints with chart specs.
"""

from __future__ import annotations


class TestHealthAndMeta:
    def test_ping(self, test_client):
        resp = test_client.get("/analysis/ping")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_root(self, test_client):
        resp = test_client.get("/")
        assert resp.status_code == 200

    def test_capabilities(self, test_client):
        resp = test_client.get("/analysis/capabilities")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 5
        keys = {item["key"] for item in data}
        assert keys == {"time_trend", "top_products", "top_members", "aov", "new_vs_returning"}
        for item in data:
            assert "chart" in item

    def test_ui_pages(self, test_client):
        for path in ["/ui", "/overview", "/reduce"]:
            resp = test_client.get(path)
            assert resp.status_code == 200


class TestBootstrap:
    def test_bootstrap_csv(self, test_client, small_csv):
        with open(small_csv, "rb") as f:
            resp = test_client.post(
                "/analysis/bootstrap",
                files={"file": ("test.csv", f, "text/csv")},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "analysis_id" in data
        assert "overview" in data
        assert "schema" in data
        assert "preview" in data
        assert "grains" in data
        assert "available_analyses" in data
        assert "blacklist" in data
        assert data["overview"]["row_count"] == 50
        assert len(data["preview"]) <= 100

    def test_bootstrap_unsupported_format(self, test_client):
        resp = test_client.post(
            "/analysis/bootstrap",
            files={"file": ("test.txt", b"hello", "text/plain")},
        )
        assert resp.status_code == 400


class TestOverview:
    def test_overview(self, test_client, uploaded_analysis_id):
        resp = test_client.post(
            "/analysis/overview",
            json={"analysis_id": uploaded_analysis_id},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["analysis_id"] == uploaded_analysis_id
        ov = data["overview"]
        assert ov["row_count"] == 50
        assert ov["column_count"] > 0
        assert "generated_at" in ov

    def test_overview_missing_id(self, test_client):
        resp = test_client.post(
            "/analysis/overview",
            json={},
        )
        assert resp.status_code == 422  # Pydantic validation error

    def test_overview_not_found(self, test_client):
        resp = test_client.post(
            "/analysis/overview",
            json={"analysis_id": "nonexistent-id"},
        )
        assert resp.status_code == 404


class TestDailyOrders:
    def test_daily_orders(self, test_client, uploaded_analysis_id):
        resp = test_client.post(
            "/analysis/overview/daily-orders",
            json={"analysis_id": uploaded_analysis_id},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "series" in data
        assert "time_column" in data
        assert "chart" in data
        if data["chart"]:
            assert "data" in data["chart"]
            assert "layout" in data["chart"]


class TestTimeTrend:
    def test_time_trend_day(self, test_client, uploaded_analysis_id):
        resp = test_client.post(
            "/analysis/time-trend",
            json={"analysis_id": uploaded_analysis_id, "granularity": "day"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["granularity"] == "day"
        assert data["metric"] == "order_total_amount"
        assert isinstance(data["series"], list)
        assert data["chart"] is not None
        assert data["chart"]["data"][0]["type"] == "scatter"

    def test_time_trend_month(self, test_client, uploaded_analysis_id):
        resp = test_client.post(
            "/analysis/time-trend",
            json={"analysis_id": uploaded_analysis_id, "granularity": "month"},
        )
        assert resp.status_code == 200
        assert resp.json()["granularity"] == "month"

    def test_time_trend_invalid_granularity(self, test_client, uploaded_analysis_id):
        resp = test_client.post(
            "/analysis/time-trend",
            json={"analysis_id": uploaded_analysis_id, "granularity": "week"},
        )
        assert resp.status_code == 422  # Pydantic pattern validation


class TestTopProducts:
    def test_top_products(self, test_client, uploaded_analysis_id):
        resp = test_client.post(
            "/analysis/top-products",
            json={"analysis_id": uploaded_analysis_id, "limit": 5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["dimension"] == "product_name"
        assert data["limit"] == 5
        assert len(data["items"]) <= 5
        assert data["chart"] is not None
        assert data["chart"]["data"][0]["type"] == "bar"

    def test_top_products_default_limit(self, test_client, uploaded_analysis_id):
        resp = test_client.post(
            "/analysis/top-products",
            json={"analysis_id": uploaded_analysis_id},
        )
        assert resp.status_code == 200
        assert resp.json()["limit"] == 10


class TestTopMembers:
    def test_top_members(self, test_client, uploaded_analysis_id):
        resp = test_client.post(
            "/analysis/top-members",
            json={"analysis_id": uploaded_analysis_id, "limit": 3},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["dimension"] == "member_id"
        assert data["limit"] == 3
        assert len(data["items"]) <= 3
        assert data["chart"] is not None


class TestAOV:
    def test_aov_day(self, test_client, uploaded_analysis_id):
        resp = test_client.post(
            "/analysis/aov",
            json={"analysis_id": uploaded_analysis_id, "granularity": "day"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["metric"] == "aov"
        assert isinstance(data["series"], list)
        assert data["chart"] is not None

    def test_aov_month(self, test_client, uploaded_analysis_id):
        resp = test_client.post(
            "/analysis/aov",
            json={"analysis_id": uploaded_analysis_id, "granularity": "month"},
        )
        assert resp.status_code == 200


class TestNewVsReturning:
    def test_new_vs_returning(self, test_client, uploaded_analysis_id):
        resp = test_client.post(
            "/analysis/new-vs-returning",
            json={"analysis_id": uploaded_analysis_id},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["dimension"] == "customer_type"
        assert len(data["items"]) == 2
        keys = {item["key"] for item in data["items"]}
        assert keys == {"new", "returning"}
        assert data["chart"] is not None
        assert data["chart"]["data"][0]["type"] == "pie"


class TestReduceEndpoints:
    def test_upload_and_preview(self, test_client, small_csv):
        with open(small_csv, "rb") as f:
            resp = test_client.post(
                "/api/reduce/upload",
                files={"file": ("test.csv", f, "text/csv")},
            )
        assert resp.status_code == 200
        data = resp.json()
        dataset_id = data["dataset_id"]

        # Preview
        resp = test_client.get(f"/api/reduce/{dataset_id}/preview?limit=10")
        assert resp.status_code == 200

    def test_distinct_values(self, test_client, small_csv):
        with open(small_csv, "rb") as f:
            resp = test_client.post(
                "/api/reduce/upload",
                files={"file": ("test.csv", f, "text/csv")},
            )
        dataset_id = resp.json()["dataset_id"]

        resp = test_client.get(f"/api/reduce/{dataset_id}/distinct?column=platform")
        assert resp.status_code == 200
        data = resp.json()
        assert data["column"] == "platform"
        assert isinstance(data["values"], list)

    def test_preview_query(self, test_client, small_csv):
        with open(small_csv, "rb") as f:
            resp = test_client.post(
                "/api/reduce/upload",
                files={"file": ("test.csv", f, "text/csv")},
            )
        dataset_id = resp.json()["dataset_id"]

        resp = test_client.post(
            f"/api/reduce/{dataset_id}/preview_query",
            json={
                "logic": "AND",
                "filters": [
                    {"column": "platform", "op": "=", "value": "web"},
                ],
            },
        )
        assert resp.status_code == 200

    def test_export_csv(self, test_client, small_csv):
        with open(small_csv, "rb") as f:
            resp = test_client.post(
                "/api/reduce/upload",
                files={"file": ("test.csv", f, "text/csv")},
            )
        dataset_id = resp.json()["dataset_id"]

        resp = test_client.post(
            f"/api/reduce/{dataset_id}/export",
            json={
                "format": "csv",
                "logic": "AND",
                "filters": [],
            },
        )
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")
