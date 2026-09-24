#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_data.py
=============
ดึงข้อมูลปริมาณน้ำจาก 2 กลุ่ม API ของกรมชลประทาน (RID) แล้วบันทึกเป็นไฟล์ JSON
ในโฟลเดอร์ data/ ให้หน้าเว็บ (index.html) อ่านไปวาดกราฟ

กลุ่ม API ที่ใช้:
  1) โทรมาตรน้ำท่า (SWOC) — ให้ค่าปริมาณน้ำไหลผ่าน หน่วย ลบ.ม./วินาที ตรงกับ
     สถานี C13 / C29B / เขื่อนป่าสัก / เขื่อนพระรามหก ตามภาพตัวอย่าง
       - https://swoc-api-service.rid.go.th/api/pier-hii-data
       - https://swoc-api-service.rid.go.th/api/pier-hyd-get-hourly-from-hydro-id
     (พบจากเอกสาร API สาธารณะของกรมชลประทาน: bigdata-api.rid.go.th/swoc_opendatadict.pdf)

  2) อ่างเก็บน้ำ/เขื่อนขนาดกลาง-ใหญ่ (ตามลิงก์ที่ผู้ใช้แนบมาโดยตรง) — ให้ % เก็บกัก,
     inflow, outflow หน่วยล้าน ลบ.ม. ใช้ทำแดชบอร์ดเสริมเรื่องปริมาณน้ำในอ่าง
       - https://app.rid.go.th/reservoir/api/dam/public
       - https://app.rid.go.th/reservoir/api/reservoir/public

⚠️ หมายเหตุสำคัญ: endpoint กลุ่มที่ 1 (swoc-api-service) เป็น API ที่พบจากเอกสารทางการ
แต่ยังไม่สามารถทดสอบเรียกจริงได้จากสภาพแวดล้อมที่เขียนสคริปต์นี้ (ถูกบล็อกเครือข่าย)
เมื่อรันบน GitHub Actions ครั้งแรก ให้ตรวจโครงสร้างข้อมูลจริงในไฟล์
data/_debug_raw_swoc.json ที่สคริปต์บันทึกไว้ แล้วปรับ field ในฟังก์ชัน
extract_discharge() ให้ตรงกับของจริงหากจำเป็น
"""

import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone, timedelta

try:
    import requests
except ImportError:
    print("ต้องติดตั้ง requests ก่อน: pip install requests", file=sys.stderr)
    raise

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
CONFIG_PATH = os.path.join(ROOT, "config", "stations.json")
HISTORY_PATH = os.path.join(DATA_DIR, "history.json")
STORAGE_HISTORY_PATH = os.path.join(DATA_DIR, "storage_history.json")
DEBUG_SWOC_PATH = os.path.join(DATA_DIR, "_debug_raw_swoc.json")
DEBUG_DAM_PATH = os.path.join(DATA_DIR, "_debug_raw_dam.json")

SWOC_BASE = "https://swoc-api-service.rid.go.th/api"
SWOC_PIER_HII = f"{SWOC_BASE}/pier-hii-data"
SWOC_HYD_STATION_LIST = f"{SWOC_BASE}/pier-hyd-get-hourly-station-list"
SWOC_HYD_HOURLY = f"{SWOC_BASE}/pier-hyd-get-hourly-from-hydro-id"

DAM_API = "https://app.rid.go.th/reservoir/api/dam/public"
RESERVOIR_API = "https://app.rid.go.th/reservoir/api/reservoir/public"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; water-dashboard-bot/1.0; +https://github.com/)",
    "Accept": "application/json",
}
TIMEOUT = 25

# วันที่ปัจจุบันตามเวลาไทย (UTC+7) เพื่อให้ตรงกับรอบข้อมูลของ RID
TH_TZ = timezone(timedelta(hours=7))


def today_str():
    return datetime.now(TH_TZ).strftime("%Y-%m-%d")


def normalize(text):
    """ตัดช่องว่าง จุด และแปลงเป็นตัวพิมพ์เดียวกัน เพื่อให้จับคู่ชื่อสถานีง่ายขึ้น"""
    if text is None:
        return ""
    text = unicodedata.normalize("NFKC", str(text))
    text = text.replace(".", "").replace(" ", "").lower()
    return text


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def safe_get(url, params=None):
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[WARN] ดึงข้อมูลจาก {url} ไม่สำเร็จ: {e}", file=sys.stderr)
        return None


def flatten_records(payload):
    """API ของ RID บางตัวห่อ record ไว้ในคีย์ต่าง ๆ กัน (data, result, items, ...) — พยายามหาลิสต์ record ให้เจอ"""
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "result", "items", "rows", "records"):
            if key in payload and isinstance(payload[key], list):
                return payload[key]
        # กรณี dam/reservoir API ของกรมชลประทานที่แนบมา: {"data":[{"region":..,"dam":[...]}, ...]}
        if "data" in payload and isinstance(payload["data"], list):
            out = []
            for region_block in payload["data"]:
                for key in ("dam", "reservoir"):
                    if isinstance(region_block, dict) and key in region_block:
                        out.extend(region_block[key])
            if out:
                return out
    return []


def match_station(record, keywords):
    """เทียบชื่อ/รหัสสถานีในเรคคอร์ดกับคำค้นที่ตั้งไว้ใน config"""
    candidate_fields = [
        "tele_station_name", "tele_station_name_th", "name", "station_name",
        "station_name_thai", "tele_station_oldcode", "code", "stationcode",
    ]
    haystacks = []
    for field in candidate_fields:
        if field in record and record[field]:
            haystacks.append(normalize(record[field]))
    if not haystacks:
        # ลองรวมทุกค่า string ในเรคคอร์ดเป็น fallback สุดท้าย
        haystacks = [normalize(v) for v in record.values() if isinstance(v, str)]

    for kw in keywords:
        nkw = normalize(kw)
        for h in haystacks:
            if nkw and nkw in h:
                return True
    return False


def extract_discharge(record):
    """หาค่าปริมาณน้ำไหลผ่าน (ลบ.ม./วินาที) จากฟิลด์ที่เป็นไปได้หลายชื่อ"""
    for field in ("discharge", "flow_rate", "qvalues", "q_values", "qavrvalues"):
        if field in record and record[field] not in (None, ""):
            try:
                return float(record[field])
            except (TypeError, ValueError):
                continue
    return None


def fetch_swoc_discharge(basins_config):
    """ดึงข้อมูลปริมาณน้ำไหลผ่านจาก SWOC (pier-hii-data) แล้วจับคู่กับสถานีใน config"""
    payload = safe_get(SWOC_PIER_HII)
    records = flatten_records(payload)

    # เก็บ raw response ไว้ debug (เขียนทับทุกครั้ง ไม่สะสม เพื่อไม่ให้ repo บวม)
    save_json(DEBUG_SWOC_PATH, {"fetched_at": today_str(), "sample": records[:20] if records else payload})

    values = {}
    for basin in basins_config["basins"]:
        for series in basin["series"]:
            found_value = None
            for rec in records:
                if isinstance(rec, dict) and match_station(rec, series["match"]):
                    v = extract_discharge(rec)
                    if v is not None:
                        found_value = v
                        break
            values[series["id"]] = found_value
    return values


def fetch_dam_storage():
    """ดึงข้อมูลอ่างเก็บน้ำขนาดใหญ่/เขื่อน (API ที่ผู้ใช้แนบมา) เก็บ % เก็บกัก/inflow/outflow"""
    payload = safe_get(DAM_API)
    records = flatten_records(payload)
    save_json(DEBUG_DAM_PATH, {"fetched_at": today_str(), "sample": records[:10] if records else payload})

    result = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        result.append({
            "id": rec.get("id"),
            "name": rec.get("name"),
            "percent_storage": rec.get("percent_storage"),
            "volume": rec.get("volume"),
            "inflow": rec.get("inflow"),
            "outflow": rec.get("outflow"),
        })
    return result


def append_history(path, date_key, entry):
    history = load_json(path, [])
    if not isinstance(history, list):
        history = []
    # ลบของวันเดียวกันที่มีอยู่แล้ว (เผื่อรันซ้ำในวันเดียวกัน) แล้วค่อยเติมใหม่
    history = [h for h in history if h.get("date") != date_key]
    history.append(entry)
    history.sort(key=lambda h: h.get("date", ""))
    save_json(path, history)
    return history


def main():
    date_key = today_str()
    print(f"[INFO] เริ่มดึงข้อมูล ณ วันที่ {date_key} (เวลาไทย)")

    basins_config = load_config()

    discharge_values = fetch_swoc_discharge(basins_config)
    print(f"[INFO] ค่าปริมาณน้ำไหลผ่านที่ดึงได้: {discharge_values}")
    append_history(HISTORY_PATH, date_key, {"date": date_key, "values": discharge_values})

    dam_records = fetch_dam_storage()
    print(f"[INFO] ดึงข้อมูลเขื่อน/อ่างเก็บน้ำได้ {len(dam_records)} รายการ")
    append_history(STORAGE_HISTORY_PATH, date_key, {"date": date_key, "dams": dam_records})

    print("[INFO] เสร็จสิ้น")


if __name__ == "__main__":
    main()
