"""
Shared test fixtures for dataset-workbench.

Provides:
- small_csv: a 50-row realistic test CSV (uses csv_generator logic)
- test_client: FastAPI TestClient with the CSV pre-uploaded
"""

from __future__ import annotations

import csv
import random
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def small_csv(tmp_path_factory) -> Path:
    """Generate a small but realistic 50-row test CSV."""
    random.seed(42)
    out_dir = tmp_path_factory.mktemp("data")
    csv_path = out_dir / "test_50rows.csv"

    fieldnames = [
        "order_id", "member_id", "order_status", "platform",
        "channel_type", "payment_method", "currency",
        "discount_amount", "shipping_fee", "order_total_amount",
        "created_at", "paid_at", "purchase_time",
        "member_type", "member_level", "first_purchase_flag",
        "product_id", "product_name", "product_category_name",
        "brand_name", "unit_price", "quantity", "item_subtotal",
    ]

    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        members = [f"M{i:04d}" for i in range(1, 11)]
        products = [
            ("P001", "AURORA Cleanser", "skincare", "AURORA"),
            ("P002", "NEKO Lipstick", "cosmetics", "NEKO LAB"),
            ("P003", "SUNRISE Vitamin", "health_supplement", "SUNRISE"),
            ("P004", "CLOUD Jacket", "fashion", "CLOUD NINE"),
            ("P005", "URBAN Candle", "home_living", "URBAN LEAF"),
        ]

        base_date = "2024-06-"
        for i in range(50):
            day = (i % 28) + 1
            oid = f"O2024-{i:04d}"
            mid = random.choice(members)
            pid, pname, pcat, pbrand = random.choice(products)
            qty = random.randint(1, 3)
            price = random.choice([200, 350, 500, 800, 1200])
            subtotal = price * qty
            total = max(0, subtotal - random.choice([0, 0, 0, 50, 100]))
            status = random.choice(["completed", "completed", "paid", "shipped", "cancelled"])
            dt = f"{base_date}{day:02d}T10:{i % 60:02d}:00+08:00"
            is_new = i < 5

            writer.writerow({
                "order_id": oid,
                "member_id": mid,
                "order_status": status,
                "platform": random.choice(["web", "ios", "android"]),
                "channel_type": "online",
                "payment_method": "credit_card",
                "currency": "TWD",
                "discount_amount": max(0, total - subtotal) * -1 if total < subtotal else 0,
                "shipping_fee": 0,
                "order_total_amount": total,
                "created_at": dt,
                "paid_at": dt if status != "cancelled" else "",
                "purchase_time": dt if status != "cancelled" else dt,
                "member_type": "new" if is_new else "returning",
                "member_level": "bronze",
                "first_purchase_flag": str(is_new).lower(),
                "product_id": pid,
                "product_name": pname,
                "product_category_name": pcat,
                "brand_name": pbrand,
                "unit_price": price,
                "quantity": qty,
                "item_subtotal": subtotal,
            })

    return csv_path


@pytest.fixture(scope="session")
def test_client() -> TestClient:
    """FastAPI TestClient for integration tests."""
    from api.main import app
    return TestClient(app)


@pytest.fixture()
def uploaded_analysis_id(test_client, small_csv) -> str:
    """Upload the small CSV and return the analysis_id."""
    with open(small_csv, "rb") as f:
        resp = test_client.post(
            "/analysis/bootstrap",
            files={"file": ("test.csv", f, "text/csv")},
        )
    assert resp.status_code == 200
    return resp.json()["analysis_id"]
