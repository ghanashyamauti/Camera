# 🎯 Camera Thing Detector

Real-time IP camera streaming with interactive Region of Interest (ROI) zone monitoring, AI object detection (YOLOv8), automated occupancy status (Green when occupied / Red when empty), and snapshot capture storage.

---

## 📁 Project Architecture

```text
Camera thing detector/
├── backend/
│   ├── venv/                       # Python Virtual Environment
│   ├── .env                        # Backend environment settings
│   ├── yolov8n.pt                  # YOLOv8 neural network weights
│   ├── requirements.txt            # Python dependencies
│   ├── app/
│   │   ├── main.py                 # FastAPI endpoints & MJPEG live stream
│   │   ├── camera.py               # RTSP / Webcam / Synthetic stream manager
│   │   ├── detector.py             # YOLOv8 object detection & Red/Green zone logic
│   │   ├── storage.py              # Snapshot capture & SQLite event logger
│   │   ├── models.py               # Pydantic schemas
│   │   └── config.py               # Environment configuration
│   └── storage/
│       ├── detector.db             # SQLite detection history
│       └── snapshots/              # Saved JPEG captures
│
├── frontend/
│   ├── .env                        # VITE_API_URL=http://localhost:8000
│   ├── package.json                # React + Tailwind CSS + Lucide
│   └── src/
│       ├── App.jsx                 # Minimal light-shade modern UI
│       ├── components/
│       │   ├── Navbar.jsx          # Top bar with live status indicators
│       │   ├── StatsCards.jsx      # Real-time occupancy radar cards
│       │   ├── VideoZonePlayer.jsx # Stream player with interactive drag-to-mark box
│       │   ├── SnapshotsDrawer.jsx # Saved captures drawer & download gallery
│       │   └── SettingsModal.jsx   # Camera RTSP config & network scanner
│       └── index.css
│
├── run_backend.bat                 # 1-Click backend launcher
├── run_frontend.bat                # 1-Click frontend launcher
└── start_all.bat                   # 1-Click complete system launcher
```

---

## 🚀 Quick Start (1-Click)

Simply double click **`start_all.bat`** in this folder!

It will:
1. Start the FastAPI backend on `http://localhost:8000`
2. Start the React frontend on `http://localhost:5173`
3. Automatically open `http://localhost:5173` in your default browser.

Or manually start in two terminal tabs:
```bash
# Terminal 1 (Backend):
cd backend
.\venv\Scripts\activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 (Frontend):
cd frontend
npm run dev
```

---

## 🔌 Connecting to Your CP PLUS Camera & TP-Link Router

From your hardware:
* **Camera**: CP PLUS (`CP-UNC-TC61L5C-VMD-LQ`, MAC: `F8:20:97:3D:68:FA`)
* **Router**: TP-Link Aginet (`EC220-G5`)

### Step 1: Ensure Power
* Plug the **12V power supply** into the camera (standard routers do not provide PoE power).

### Step 2: Connect PC to the Router Network
* Open your PC Wi-Fi menu and connect to **`TP-Link_B2B7`**.
* Password: **`17009690`**.

### Step 3: Stream in the App
1. Open the UI at `http://localhost:5173`.
2. Click **Camera Settings** in the top right.
3. Select the **CP PLUS RTSP** preset or click **Scan Network** to detect your camera's IP on the router.
   * Default CP PLUS stream URL:
     ```text
     rtsp://admin:admin123@192.168.1.250:554/cam/realmonitor?channel=1&subtype=1
     ```
   *(If you customized your camera password during setup, replace `admin123` with your password)*.

---

## 🟢 Zone Detection Logic (Green / Red)

* **Interactive Marking**: Click **Draw Zone Box** and drag across any part of the video stream (over a chair, a parking spot, a desk, a doorway, etc.).
* **Occupied (GREEN)**: When any object (person, chair, car, bottle, backpack, etc.) is inside your marked zone, the box glows **GREEN** and shows the object label and confidence.
* **Empty (RED)**: When no object is inside your marked zone, the box turns **RED** (`Zone Clear / Empty`).
* **Auto-Snapshots**: Every time an object enters the zone, a high-resolution snapshot is automatically saved to `backend/storage/snapshots/` and cataloged in the drawer.
