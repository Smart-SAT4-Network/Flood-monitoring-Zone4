#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backfill_storage.py
====================
ดึงข้อมูลอ่างเก็บน้ำ/เขื่อนย้อนหลังจาก API ที่รองรับ /public/{date}
  https://app.rid.go.th/reservoir/api/dam/public/{YYYY-MM-DD}

ใช้ตอนตั้งโปรเจกต์ใหม่ครั้งแรก เพื่อให้กราฟมีเส้นย้อนหลังหลายวันทันที
(ข้อมูลโทรมาตรน้ำท่า C13/C29B/ป่าสัก/พระรามหก ไม่มี endpoint ย้อนหลังแบบนี้
ให้ปล่อยให้ GitHub Actions สะสมข้อมูลไปทีละวันแทน)

วิธีใช้:
    python scripts/backfill_storage.py --days 30
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_data import (  # noqa: E402
    DATA_DIR, STORAGE_HISTORY_PATH, HEADERS, TIMEOUT, flatten_records,
    load_json, save_json,
)
import requests  # noqa: E402

DAM_API_BY_DATE = "https://app.rid.go.th/reservoir/api/dam/public/{date}"


def fetch_for_date(date_str):
    url = DAM_API_BY_DATE.format(date=date_str)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[WARN] {date_str}: {e}", file=sys.stderr)
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30, help="จำนวนวันย้อนหลังที่จะดึง")
    args = parser.parse_args()

    history = load_json(STORAGE_HISTORY_PATH, [])
    if not isinstance(history, list):
        history = []
    existing_dates = {h.get("date") for h in history}

    today = datetime.utcnow() + timedelta(hours=7)
    for i in range(args.days, -1, -1):
        d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        if d in existing_dates:
            print(f"[SKIP] {d} มีอยู่แล้ว")
            continue
        payload = fetch_for_date(d)
        records = flatten_records(payload)
        dams = [{
            "id": r.get("id"), "name": r.get("name"),
            "percent_storage": r.get("percent_storage"),
            "volume": r.get("volume"), "inflow": r.get("inflow"),
            "outflow": r.get("outflow"),
        } for r in records if isinstance(r, dict)]
        history.append({"date": d, "dams": dams})
        print(f"[OK] {d}: {len(dams)} เขื่อน")
        time.sleep(0.5)  # เว้นจังหวะ ไม่ยิงถี่เกินไป

    history = [h for h in history if h.get("date")]
    history.sort(key=lambda h: h["date"])
    save_json(STORAGE_HISTORY_PATH, history)
    print("[INFO] บันทึก data/storage_history.json เรียบร้อย")


if __name__ == "__main__":
    main()
