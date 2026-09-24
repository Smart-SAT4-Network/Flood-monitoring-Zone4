# รายงานสถานการณ์น้ำ ลุ่มเจ้าพระยา–ป่าสัก 🌊

เว็บไซต์แดชบอร์ดแสดงปริมาณน้ำไหลผ่านสถานีสำคัญของลุ่มน้ำเจ้าพระยาและลุ่มน้ำป่าสัก
เป็นกราฟเส้นเทียบเกณฑ์เฝ้าระวัง (ตามสไตล์ภาพต้นฉบับ) พร้อมตารางปริมาณน้ำในอ่างเก็บน้ำ/เขื่อน
ดึงข้อมูลอัตโนมัติทุกวันจาก API ของกรมชลประทาน (RID) ผ่าน GitHub Actions แล้วโฮสต์บน GitHub Pages

---

## ⚠️ อ่านก่อนใช้งาน — ข้อจำกัดสำคัญ

โปรเจกต์นี้ใช้ 2 กลุ่ม API ที่**แหล่งข้อมูลต่างกัน**:

| กลุ่มข้อมูล | Endpoint | สถานะ |
|---|---|---|
| ปริมาณน้ำไหลผ่านสถานีโทรมาตร (C13, C29B, เขื่อนป่าสัก, เขื่อนพระรามหก) หน่วย ลบ.ม./วินาที — ใช้ทำกราฟหลัก | `https://swoc-api-service.rid.go.th/api/pier-hii-data` และ endpoint อื่นในกลุ่ม SWOC (พบจากเอกสาร API สาธารณะของกรมชลประทาน) | **พบจากเอกสารทางการ แต่ยังไม่ได้ทดสอบเรียกจริง** เพราะสภาพแวดล้อมที่พัฒนาไม่มีสิทธิ์ออกอินเทอร์เน็ตไปโดเมนนี้ |
| ปริมาณน้ำในอ่างเก็บน้ำ/เขื่อนขนาดกลาง-ใหญ่ (ล้าน ลบ.ม., % เก็บกัก) — ใช้ทำตารางเสริม | `https://app.rid.go.th/reservoir/api/dam/public`<br>`https://app.rid.go.th/reservoir/api/reservoir/public` | **ทดสอบเรียกสำเร็จแล้ว** คืนข้อมูลจริง (ดูตัวอย่างได้ใน `data/_debug_raw_dam.json` หลังรันสคริปต์ครั้งแรก) |

**สิ่งที่ต้องทำหลัง deploy ครั้งแรก:**
1. รัน workflow "Update water data" ด้วยตนเองครั้งแรก (แท็บ Actions → เลือก workflow → Run workflow)
2. เปิดไฟล์ `data/_debug_raw_swoc.json` ที่ถูก commit กลับมา ดูว่าโครงสร้างข้อมูลจริงหน้าตาเป็นอย่างไร
3. ถ้าชื่อฟิลด์หรือชื่อสถานีไม่ตรงกับที่สคริปต์คาดไว้ ให้แก้ไขที่ไฟล์ `config/stations.json` (ปรับคำใน `match`)
   หรือแก้ฟังก์ชัน `extract_discharge()` / `match_station()` ใน `scripts/fetch_data.py`
4. ถ้า endpoint ถูกบล็อกหรือย้ายที่ ให้ค้นหาเอกสาร API ล่าสุดที่ `https://bigdata-api.rid.go.th/swoc_opendatadict.pdf`

หากพบว่า API เปลี่ยนแปลง เว็บจะยังไม่พัง — จะแสดงข้อความ "ยังไม่มีข้อมูลจริงจากสถานีนี้..." แทนกราฟเปล่า ๆ

---

## โครงสร้างโปรเจกต์

```
water-dashboard/
├── index.html              หน้าเว็บหลัก
├── css/style.css            สไตล์ (ธีมเหลือง-ส้ม-ฟ้าตามภาพต้นฉบับ)
├── js/
│   ├── config.js            พาธไฟล์ข้อมูล
│   └── app.js                โหลด JSON + วาดกราฟด้วย Chart.js
├── config/stations.json      ตั้งค่าสถานี/เกณฑ์เฝ้าระวัง (แก้ตรงนี้ได้โดยไม่ต้องแก้โค้ด)
├── data/
│   ├── history.json          ประวัติปริมาณน้ำไหลผ่าน (สร้าง/อัปเดตโดย fetch_data.py)
│   └── storage_history.json  ประวัติปริมาณน้ำในอ่าง/เขื่อน
├── scripts/
│   ├── fetch_data.py         สคริปต์ดึงข้อมูลประจำวัน (รันโดย GitHub Actions)
│   ├── backfill_storage.py   สคริปต์ดึงข้อมูลอ่าง/เขื่อนย้อนหลัง (รันครั้งเดียวตอนตั้งโปรเจกต์)
│   └── requirements.txt
└── .github/workflows/update-data.yml   ตั้งเวลาให้รันดึงข้อมูลอัตโนมัติทุกวัน
```

---

## วิธีติดตั้งบน GitHub

1. สร้างรีโปใหม่บน GitHub แล้วอัปโหลดไฟล์ทั้งหมดในโฟลเดอร์นี้ขึ้นไป
   ```bash
   git init
   git add .
   git commit -m "init: water dashboard"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<repo-name>.git
   git push -u origin main
   ```

2. เปิดสิทธิ์ให้ GitHub Actions commit กลับเข้ารีโปได้:
   Settings → Actions → General → Workflow permissions → เลือก **Read and write permissions** → Save

3. เปิดใช้งาน GitHub Pages:
   Settings → Pages → Build and deployment → Source: **Deploy from a branch** → Branch: `main` / `(root)` → Save
   รอ 1-2 นาที เว็บจะขึ้นที่ `https://<your-username>.github.io/<repo-name>/`

4. รัน workflow ครั้งแรกด้วยตนเอง (ไม่ต้องรอ cron):
   แท็บ **Actions** → เลือก **Update water data** → **Run workflow**
   เมื่อรันสำเร็จ ไฟล์ใน `data/` จะถูกอัปเดตและ commit กลับเข้ารีโปอัตโนมัติ

5. (ทางเลือก) ดึงข้อมูลอ่างเก็บน้ำย้อนหลังทันที ก่อน push ขึ้น GitHub:
   ```bash
   pip install -r scripts/requirements.txt
   python scripts/backfill_storage.py --days 30
   ```

จากนั้นระบบจะดึงข้อมูลใหม่ให้อัตโนมัติทุกวัน เวลา 10:30 น. (ตามเวลาไทย) ผ่าน GitHub Actions
โดยไม่ต้องเปิดคอมพิวเตอร์ของคุณทิ้งไว้เลย — และเว็บฝั่ง GitHub Pages จะไม่มีปัญหา CORS
เพราะอ่านข้อมูลจากไฟล์ JSON ในรีโปตัวเอง (ไม่ได้ยิง fetch ตรงไปที่ app.rid.go.th จากเบราว์เซอร์)

---

## ปรับแต่ง

- **เปลี่ยนเกณฑ์เฝ้าระวัง/ชื่อสถานี**: แก้ `config/stations.json`
- **เปลี่ยนเวลารันอัตโนมัติ**: แก้ค่า `cron` ใน `.github/workflows/update-data.yml` (เวลาในไฟล์เป็น UTC)
- **เปลี่ยนสีธีม**: แก้ตัวแปรใน `:root` ของ `css/style.css`
- **เพิ่มลุ่มน้ำ/สถานีอื่น**: เพิ่ม object ใหม่ในลิสต์ `basins` ของ `config/stations.json`
  (แล้ว fetch_data.py จะพยายามจับคู่ชื่อสถานีให้อัตโนมัติจากคำใน `match`)

## ทดสอบในเครื่องก่อน push

```bash
python -m http.server 8000
# แล้วเปิด http://localhost:8000
```

(ต้องรันผ่าน local server เพราะ `fetch()` ของเบราว์เซอร์บล็อกการเปิดไฟล์ตรงด้วย `file://`)
