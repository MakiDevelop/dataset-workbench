#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate a large synthetic ecommerce order-item dataset (1,000,000 rows) as CSV.

Goal: simulate "Excel can't open it" scale, while still looking realistic:
- One order_id can have multiple items (1~5 by default)
- Order status affects paid_at / completed_at, and refunded orders have negative net effect patterns
- Marketing attribution (utm/campaign) + platform/channel/device

Output: orders_items_1m.csv (or .csv.gz)
Writes in chunks to avoid blowing RAM.

Usage examples:
  python gen_orders_csv.py
  python gen_orders_csv.py --rows 1000000 --out orders_items_1m.csv.gz --gzip
  python gen_orders_csv.py --rows 2000000 --chunk 200000

Dependencies:
  pip install numpy faker
(Only standard library + numpy + faker. No pandas required.)
"""

import argparse
import csv
import gzip
import os
import random
import string
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np
from faker import Faker


# ----------------------------
# Config / Distributions
# ----------------------------

TZ = timezone(timedelta(hours=8))  # Asia/Taipei offset
DEFAULT_START = "2024-01-01"
DEFAULT_END = "2025-12-31"

CURRENCY = "TWD"

PLATFORMS = ["web", "ios", "android"]
DEVICE_TYPES = ["desktop", "mobile", "tablet"]
CHANNEL_TYPES = ["online", "offline", "omo"]

PAYMENT_METHODS = ["credit_card", "line_pay", "apple_pay", "atm", "cod"]
ORDER_STATUSES = ["created", "paid", "shipped", "completed", "cancelled", "refunded"]

TRAFFIC_SOURCES = ["organic", "facebook_ads", "google_ads", "line_oa", "email", "push", "affiliate", "direct"]
TRAFFIC_MEDIUMS = ["cpc", "social", "email", "push", "referral", "organic", "none"]

# A few "heavy hitter" campaigns to create realistic skew
CAMPAIGNS = [
    ("CAMP_0001", "NewYear_Sale"),
    ("CAMP_0002", "Member_Day"),
    ("CAMP_0003", "Flash_Deal"),
    ("CAMP_0004", "VIP_Exclusive"),
    ("CAMP_0005", "Summer_Sale"),
    ("CAMP_0006", "11_11"),
    ("CAMP_0007", "12_12"),
    ("CAMP_0008", "Brand_Collab"),
]

MEMBER_LEVELS = ["bronze", "silver", "gold", "vip"]

# Categories / Brands
CATEGORIES = [
    ("CAT_010", "skincare"),
    ("CAT_020", "cosmetics"),
    ("CAT_030", "health_supplement"),
    ("CAT_040", "fashion"),
    ("CAT_050", "home_living"),
    ("CAT_060", "electronics_accessory"),
]
BRANDS = [
    ("BR_001", "AURORA"),
    ("BR_002", "NEKO LAB"),
    ("BR_003", "SUNRISE"),
    ("BR_004", "CLOUD NINE"),
    ("BR_005", "URBAN LEAF"),
    ("BR_006", "NORTHWIND"),
]


@dataclass
class Product:
    product_id: str
    product_name: str
    category_id: str
    category_name: str
    brand_id: str
    brand_name: str
    base_price: int  # in TWD


def make_products(fake: Faker, n: int = 5000, seed: int = 42) -> list[Product]:
    random.seed(seed)
    products: list[Product] = []
    for i in range(1, n + 1):
        cat_id, cat_name = random.choice(CATEGORIES)
        br_id, br_name = random.choice(BRANDS)

        # Price skew: most items are affordable, some are premium
        base_price = int(np.clip(np.random.lognormal(mean=5.3, sigma=0.55), 100, 30000))
        # Clean up to something that looks like pricing
        base_price = int(round(base_price / 10) * 10)

        pid = f"P{i:07d}"
        pname = f"{br_name} {fake.word().title()} {cat_name.replace('_', ' ').title()}"

        products.append(
            Product(
                product_id=pid,
                product_name=pname,
                category_id=cat_id,
                category_name=cat_name,
                brand_id=br_id,
                brand_name=br_name,
                base_price=base_price,
            )
        )
    return products


def parse_date(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=TZ)


def random_dt(start: datetime, end: datetime) -> datetime:
    # uniform random datetime between start and end
    delta = int((end - start).total_seconds())
    sec = random.randint(0, max(delta, 1))
    return start + timedelta(seconds=sec)


def gen_order_id() -> str:
    # Example: O20251230-8F3K2M7Q
    date_part = datetime.now(TZ).strftime("%Y%m%d")
    rand_part = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
    return f"O{date_part}-{rand_part}"


def choose_status() -> str:
    # Typical ecommerce-ish distribution
    # created (unpaid) small, cancelled small, refunded smallish, completed dominant
    r = random.random()
    if r < 0.03:
        return "created"
    if r < 0.08:
        return "cancelled"
    if r < 0.13:
        return "refunded"
    if r < 0.25:
        return "paid"
    if r < 0.35:
        return "shipped"
    return "completed"


def member_level_from_id(member_id: str) -> str:
    # Deterministic-ish mapping for repeatability
    h = sum(ord(c) for c in member_id) % 100
    if h < 55:
        return "bronze"
    if h < 80:
        return "silver"
    if h < 95:
        return "gold"
    return "vip"


def member_type_and_recency(days_since_last: int) -> tuple[str, int, bool]:
    # Return member_type, days_since_last_purchase (clamped), first_purchase_flag
    if days_since_last >= 999:
        return ("new", 999, True)
    return ("returning", days_since_last, False)


def pick_campaign() -> tuple[str, str]:
    # Heavy skew to top campaigns
    r = random.random()
    if r < 0.55:
        return CAMPAIGNS[0]
    if r < 0.70:
        return CAMPAIGNS[1]
    if r < 0.80:
        return CAMPAIGNS[2]
    if r < 0.88:
        return CAMPAIGNS[3]
    # else random from rest
    return random.choice(CAMPAIGNS[4:])


def pick_traffic(platform: str) -> tuple[str, str]:
    # Slight coupling: push more likely for app, email more likely for web
    if platform in ("ios", "android"):
        source = random.choices(
            population=TRAFFIC_SOURCES,
            weights=[8, 18, 16, 22, 6, 20, 5, 5],
            k=1,
        )[0]
    else:
        source = random.choices(
            population=TRAFFIC_SOURCES,
            weights=[18, 18, 22, 8, 12, 6, 7, 9],
            k=1,
        )[0]

    medium_map = {
        "organic": "organic",
        "facebook_ads": "cpc",
        "google_ads": "cpc",
        "line_oa": "social",
        "email": "email",
        "push": "push",
        "affiliate": "referral",
        "direct": "none",
    }
    return source, medium_map.get(source, "none")


def pick_store_id(channel_type: str) -> str:
    # Keep it simple: offline/omo have more store variety
    if channel_type == "online":
        return "STORE_ONLINE"
    if channel_type == "offline":
        return f"STORE_{random.randint(1, 120):03d}"
    return f"STORE_{random.randint(1, 80):03d}"  # omo


def open_writer(path: str, use_gzip: bool):
    if use_gzip:
        f = gzip.open(path, "wt", newline="", encoding="utf-8")
    else:
        f = open(path, "w", newline="", encoding="utf-8")
    return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=1_000_000, help="Total rows (order-item rows) to generate")
    ap.add_argument("--out", type=str, default="orders_items_1m.csv", help="Output CSV path")
    ap.add_argument("--gzip", action="store_true", help="Write gzipped CSV (.csv.gz recommended)")
    ap.add_argument("--chunk", type=int, default=100_000, help="Rows per flush (controls memory and speed)")
    ap.add_argument("--seed", type=int, default=42, help="Random seed")
    ap.add_argument("--start", type=str, default=DEFAULT_START, help="Start date YYYY-MM-DD")
    ap.add_argument("--end", type=str, default=DEFAULT_END, help="End date YYYY-MM-DD")
    ap.add_argument("--members", type=int, default=250_000, help="Number of unique members to simulate")
    ap.add_argument("--products", type=int, default=5000, help="Number of products to simulate")
    args = ap.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)

    fake = Faker()
    fake.seed_instance(args.seed)

    start_dt = parse_date(args.start)
    end_dt = parse_date(args.end)

    # Pre-generate member ids
    member_ids = [f"M{idx:08d}" for idx in range(1, args.members + 1)]

    # Pre-generate products
    products = make_products(fake, n=args.products, seed=args.seed)

    # Simple member last purchase recency model:
    # Most members have some previous purchase; some are "new".
    # We'll assign each member a "last purchase days ago" with a skew.
    #  - 10% are new (days_since_last = 999)
    #  - others: lognormal-ish days, clamped to 365
    member_days_since_last = np.full(args.members, 999, dtype=np.int32)
    old_mask = np.random.rand(args.members) > 0.10
    old_count = int(old_mask.sum())
    sampled = np.clip(np.random.lognormal(mean=3.0, sigma=0.9, size=old_count), 1, 365).astype(np.int32)
    member_days_since_last[old_mask] = sampled

    fieldnames = [
        # Order level
        "order_id",
        "member_id",
        "store_id",
        "order_status",
        "platform",
        "channel_type",
        "device_type",
        "traffic_source",
        "traffic_medium",
        "campaign_id",
        "campaign_name",
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "payment_method",
        "currency",
        "discount_amount",
        "shipping_fee",
        "tax_amount",
        "order_total_amount",
        "created_at",
        "paid_at",
        "purchase_time",
        # Member attributes (snapshot)
        "member_type",
        "member_level",
        "first_purchase_flag",
        "days_since_last_purchase",
        # Item level
        "product_id",
        "product_name",
        "product_category_id",
        "product_category_name",
        "brand_id",
        "brand_name",
        "unit_price",
        "quantity",
        "item_subtotal",
        "is_bundle_item",
    ]

    out_path = args.out
    if args.gzip and not out_path.endswith(".gz"):
        out_path += ".gz"

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    with open_writer(out_path, args.gzip) as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        rows_written = 0

        # We generate by "orders", because we want realistic order_total_amount shared across items.
        # Each order will have 1~5 items (skewed).
        while rows_written < args.rows:
            # Decide items per order: mostly 1-2, sometimes more
            items_per_order = random.choices([1, 2, 3, 4, 5], weights=[48, 30, 12, 7, 3], k=1)[0]

            # Ensure we don't exceed target rows
            if rows_written + items_per_order > args.rows:
                items_per_order = args.rows - rows_written

            order_id = gen_order_id()
            member_idx = random.randrange(args.members)
            member_id = member_ids[member_idx]

            platform = random.choice(PLATFORMS)
            device_type = random.choices(DEVICE_TYPES, weights=[35, 55, 10], k=1)[0] if platform == "web" else random.choices(DEVICE_TYPES, weights=[10, 80, 10], k=1)[0]
            channel_type = random.choices(CHANNEL_TYPES, weights=[78, 12, 10], k=1)[0]

            store_id = pick_store_id(channel_type)
            order_status = choose_status()
            payment_method = random.choices(PAYMENT_METHODS, weights=[40, 25, 8, 10, 17], k=1)[0]

            traffic_source, traffic_medium = pick_traffic(platform)
            camp_id, camp_name = pick_campaign()

            utm_source = traffic_source
            utm_medium = traffic_medium
            utm_campaign = camp_name

            # Time generation
            created_at = random_dt(start_dt, end_dt)

            # paid_at depends on status
            if order_status in ("created", "cancelled"):
                paid_at = ""
            else:
                paid_at_dt = created_at + timedelta(minutes=random.randint(1, 6 * 60))
                paid_at = paid_at_dt.isoformat()

            # purchase_time: use paid time when available, otherwise created
            if paid_at:
                purchase_time = paid_at
            else:
                purchase_time = created_at.isoformat()

            created_at_str = created_at.isoformat()

            # Member snapshot fields
            days_since_last = int(member_days_since_last[member_idx])
            member_type, days_since_last_purchase, first_purchase_flag = member_type_and_recency(days_since_last)
            member_level = member_level_from_id(member_id)

            # Pick products for items (allow repeats rarely)
            chosen_products = random.sample(products, k=min(items_per_order, len(products)))

            # Compute item subtotals, then order-level amounts
            item_rows = []
            items_total = 0

            for p in chosen_products:
                # Unit price with small noise (promo, rounding)
                unit_price = int(max(10, round((p.base_price * random.uniform(0.85, 1.08)) / 10) * 10))
                quantity = random.choices([1, 2, 3, 4, 5], weights=[70, 18, 7, 3, 2], k=1)[0]
                item_subtotal = unit_price * quantity

                is_bundle_item = random.random() < 0.06

                items_total += item_subtotal

                item_rows.append(
                    (p, unit_price, quantity, item_subtotal, is_bundle_item)
                )

            # Discounts and fees
            # Discount: 0 for many, sometimes 5~25% off (cap)
            if random.random() < 0.55:
                discount_amount = 0
            else:
                discount_amount = int(min(items_total * random.uniform(0.05, 0.25), 5000))
                discount_amount = int(round(discount_amount / 10) * 10)

            # Shipping fee: 0 if high basket or offline/omo, else small fee
            if channel_type != "online" or items_total >= 1500 or random.random() < 0.25:
                shipping_fee = 0
            else:
                shipping_fee = random.choice([60, 80, 100, 120])

            # Tax: keep as 0 for TWD typical consumer price-included scenario
            tax_amount = 0

            order_total = max(0, items_total - discount_amount + shipping_fee + tax_amount)

            # Status effects:
            # cancelled: total 0-ish (keep row, but treat as cancelled order)
            if order_status == "cancelled":
                discount_amount = 0
                shipping_fee = 0
                tax_amount = 0
                order_total = 0

            # refunded: keep totals but mark as refunded (some businesses store as positive with status,
            # others store negative refund rows; we keep positive totals with refunded status).
            # If you want negative, flip here.
            # if order_status == "refunded":
            #     order_total = -order_total

            # Write item rows
            for (p, unit_price, quantity, item_subtotal, is_bundle_item) in item_rows:
                row = {
                    "order_id": order_id,
                    "member_id": member_id,
                    "store_id": store_id,
                    "order_status": order_status,
                    "platform": platform,
                    "channel_type": channel_type,
                    "device_type": device_type,
                    "traffic_source": traffic_source,
                    "traffic_medium": traffic_medium,
                    "campaign_id": camp_id,
                    "campaign_name": camp_name,
                    "utm_source": utm_source,
                    "utm_medium": utm_medium,
                    "utm_campaign": utm_campaign,
                    "payment_method": payment_method,
                    "currency": CURRENCY,
                    "discount_amount": discount_amount,
                    "shipping_fee": shipping_fee,
                    "tax_amount": tax_amount,
                    "order_total_amount": order_total,
                    "created_at": created_at_str,
                    "paid_at": paid_at,
                    "purchase_time": purchase_time,
                    "member_type": member_type,
                    "member_level": member_level,
                    "first_purchase_flag": str(bool(first_purchase_flag)).lower(),
                    "days_since_last_purchase": days_since_last_purchase,
                    "product_id": p.product_id,
                    "product_name": p.product_name,
                    "product_category_id": p.category_id,
                    "product_category_name": p.category_name,
                    "brand_id": p.brand_id,
                    "brand_name": p.brand_name,
                    "unit_price": unit_price,
                    "quantity": quantity,
                    "item_subtotal": item_subtotal,
                    "is_bundle_item": str(bool(is_bundle_item)).lower(),
                }
                writer.writerow(row)

            rows_written += items_per_order

            # Periodic flush for safety
            if rows_written % args.chunk == 0:
                f.flush()
                print(f"[progress] rows_written={rows_written:,}")

    print(f"[done] wrote {rows_written:,} rows to: {out_path}")


if __name__ == "__main__":
    main()