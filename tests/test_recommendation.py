"""
Tests for the recommendation engine and insight generator.
"""

from __future__ import annotations

from pipelines.recommendation import recommend_analyses, generate_insight


class TestRecommendAnalyses:
    def _base_overview(self):
        return {
            "row_count": 1000,
            "time_column": "purchase_time",
            "time_range": {"min": "2024-01-01", "max": "2024-12-31"},
            "member_count": 50,
        }

    def _base_columns(self):
        return [
            "order_id", "member_id", "product_id", "product_name",
            "order_total_amount", "item_subtotal", "purchase_time",
            "first_purchase_flag",
        ]

    def test_all_recommended_with_full_data(self):
        recs = recommend_analyses(
            overview=self._base_overview(),
            grains=["order", "item", "member"],
            schema_columns=self._base_columns(),
            blacklist=[],
        )
        assert len(recs) == 5
        # All should be recommended with full data
        for r in recs:
            assert r["score"] > 0
            assert r["status"] in ("recommended", "caution")
            assert r["reason"]

    def test_sorted_by_score_descending(self):
        recs = recommend_analyses(
            overview=self._base_overview(),
            grains=["order", "item", "member"],
            schema_columns=self._base_columns(),
            blacklist=[],
        )
        scores = [r["score"] for r in recs]
        assert scores == sorted(scores, reverse=True)

    def test_blocked_by_blacklist(self):
        blacklist = [{
            "grain": "item",
            "metric": "order_total_amount",
            "reason": "訂單層金額在商品粒度下會被重複計算",
            "severity": "block",
        }]
        recs = recommend_analyses(
            overview=self._base_overview(),
            grains=["order", "item", "member"],
            schema_columns=self._base_columns(),
            blacklist=blacklist,
        )
        blocked = [r for r in recs if r["status"] == "blocked"]
        assert len(blocked) >= 1
        blocked_keys = {r["key"] for r in blocked}
        assert "time_trend" in blocked_keys or "aov" in blocked_keys

    def test_low_score_without_required_columns(self):
        # Remove purchase_time and product_name
        columns = ["order_id", "member_id", "order_total_amount"]
        recs = recommend_analyses(
            overview={"row_count": 100},
            grains=["order"],
            schema_columns=columns,
            blacklist=[],
        )
        rec_map = {r["key"]: r for r in recs}
        assert rec_map["time_trend"]["score"] <= 20
        assert rec_map["top_products"]["score"] <= 20

    def test_caution_from_warning_blacklist(self):
        blacklist = [{
            "grain": "all",
            "metric": "paid_at",
            "reason": "付款時間欄位存在缺值",
            "severity": "warning",
        }]
        recs = recommend_analyses(
            overview=self._base_overview(),
            grains=["order", "item", "member"],
            schema_columns=self._base_columns(),
            blacklist=blacklist,
        )
        time_rec = next(r for r in recs if r["key"] == "time_trend")
        assert time_rec["status"] == "caution"
        assert "注意" in time_rec["reason"]


class TestGenerateInsight:
    def test_time_trend_insight(self):
        data = {
            "series": [
                {"time": "2024-01-01", "value": 100},
                {"time": "2024-01-02", "value": 200},
                {"time": "2024-01-03", "value": 150},
            ]
        }
        text = generate_insight("time_trend", data)
        assert "銷售額" in text
        assert "450" in text

    def test_aov_insight(self):
        data = {
            "series": [
                {"time": "2024-01", "value": 500},
                {"time": "2024-02", "value": 600},
            ]
        }
        text = generate_insight("aov", data)
        assert "客單價" in text

    def test_top_products_insight(self):
        data = {
            "items": [
                {"key": "Product A", "value": 500},
                {"key": "Product B", "value": 300},
            ]
        }
        text = generate_insight("top_products", data)
        assert "Product A" in text
        assert "%" in text

    def test_new_vs_returning_insight(self):
        data = {
            "items": [
                {"key": "new", "value": 30},
                {"key": "returning", "value": 70},
            ]
        }
        text = generate_insight("new_vs_returning", data)
        assert "新客" in text
        assert "回購客" in text

    def test_empty_data(self):
        text = generate_insight("time_trend", {"series": []})
        assert text  # should return something, not empty


class TestRecommendAPI:
    def test_recommend_endpoint(self, test_client, uploaded_analysis_id):
        resp = test_client.post(
            "/analysis/recommend",
            json={"analysis_id": uploaded_analysis_id},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "recommendations" in data
        assert len(data["recommendations"]) == 5
        # Should be sorted by score
        scores = [r["score"] for r in data["recommendations"]]
        assert scores == sorted(scores, reverse=True)

    def test_recommend_not_found(self, test_client):
        resp = test_client.post(
            "/analysis/recommend",
            json={"analysis_id": "nonexistent"},
        )
        assert resp.status_code == 404

    def test_insight_endpoint(self, test_client, uploaded_analysis_id):
        resp = test_client.post(
            "/analysis/insight",
            json={
                "analysis_id": uploaded_analysis_id,
                "analysis_key": "new_vs_returning",
                "result_data": {
                    "items": [
                        {"key": "new", "value": 10},
                        {"key": "returning", "value": 40},
                    ]
                },
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["insight"]
        assert "新客" in data["insight"]
