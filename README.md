# Smart Attendance System

An enterprise-grade, AI-powered web platform for educational institutions that automates student attendance tracking using computer vision and browser-based face recognition with robust manual fallbacks.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0%2B-black.svg)](https://flask.palletsprojects.com/)
[![OpenCV](https://img.shields.io/badge/OpenCV-LBPH%20%26%20Haar-green.svg)](https://opencv.org/)
[![TailwindCSS](https://img.shields.io/badge/TailwindCSS-CDN-38bdf8.svg)](https://tailwindcss.com/)
[![Tests](https://img.shields.io/badge/Tests-36%20Passed%20(100%25)-success.svg)](https://pytest.org/)

---

## 📑 Table of Contents

- [Overview](#-overview)
- [System Architecture](#-system-architecture)
- [Key Features](#-key-features)
- [Technology Stack](#-technology-stack)
- [Face Recognition Engine & Fallback Architecture](#-face-recognition-engine--fallback-architecture)
- [Installation & Quickstart](#-installation--quickstart)
- [Demo Accounts](#-demo-accounts)
- [REST API Reference](#-rest-api-reference)
- [Security & Biometric Data Privacy](#-security--biometric-data-privacy)
- [Automated Testing Suite](#-automated-testing-suite)
- [Production Deployment](#-production-deployment)
- [License](#-license)

---

## 🌟 Overview

The **Smart Attendance System** modernizes institutional roll-call operations. It eliminates manual record-keeping errors and proxy attendance through an end-to-end web interface.

- **For Administrators:** Manage academic departments, classrooms, subjects, faculty allocations, timetable slots, student rosters, biometric enrollment, audit logging, system settings, database hot-backups, and diagnostic telemetry.
- **For Teachers:** Launch scheduled live webcam attendance sessions, conduct instant automated recognition, perform manual roll-call when cameras are unavailable, submit justifiable attendance overrides, and inspect real-time shortage analytics.
- **For Students:** Self-service attendance portal with subject-wise percentages, calendar views, daily history, shortage warnings (<75%), and biometric consent control.

---

## 🏛 System Architecture

```mermaid
graph TD
    subgraph Client Browser
        UI[Tailwind CSS & Jinja2 UI]
        Webcam[Webcam Video Stream\nnavigator.mediaDevices.getUserMedia]
        Fetch[Frame Payload Dispatcher\nBase64 JPEG via fetch POST]
        Charts[Chart.js Visualizations]
    end

    subgraph Flask Application Layer
        Auth[Auth Blueprint & Flask-Login]
        AdminBP[Admin Blueprint & RBAC]
        AttendBP[Attendance Blueprint & Session Manager]
        ReportBP[Reports Blueprint & OpenPyXL Exporter]
        AnalyticsBP[Analytics Blueprint & Aggregations]
        StudentBP[Student Blueprint & Audit Guards]
    end

    subgraph Face Biometrics Engine
        Detector[Haar Cascade / HOG Face Detector]
        Quality[Quality & Liveness Heuristics\nBlur, Brightness, Temporal Continuity]
        Matcher[Matcher Engine\nOpenCV-LBPH / Dlib ResNet]
        Tracker[Consecutive Match Tracker\n2 Successive Frame Verifications]
    end

    subgraph Persistence Layer
        DB[(SQLAlchemy ORM / SQLite / PostgreSQL)]
        Storage[(Biometric Vectors & Hot Backups)]
        AuditLogs[(Immutable Security Audit Trail)]
    end

    Webcam --> Fetch
    Fetch --> AttendBP
    AttendBP --> Quality
    Quality --> Detector
    Detector --> Matcher
    Matcher --> Tracker
    Tracker --> DB
    AdminBP --> DB
    AdminBP --> Storage
    AdminBP --> AuditLogs
    ReportBP --> DB
    AnalyticsBP --> DB
    StudentBP --> DB
    DB --> UI
    AnalyticsBP --> Charts
```

---

## 🚀 Key Features

### 1. Computer Vision & Live Face Attendance
- **Browser-Side Capture:** No server-side video streaming overhead; frames are captured in the browser via `navigator.mediaDevices.getUserMedia()` and sent asynchronously via `fetch()` as base64 JPEG strings.
- **Quality & Pre-Flight Validation:** Laplacian variance blur detection ($>45.0$), luminance verification (range 40–225), and bounding-box area ratios ($>0.04$).
- **Anti-Spoofing & Stability:** Temporal continuity checks with a `ConsecutiveMatchTracker` requiring 2 consecutive matching frames before a student is flagged `Present`.
- **Duplicate & Race-Condition Safe:** Atomic SQLite/PostgreSQL transactions with unique database constraints `(session_id, student_id)`.

### 2. Manual Roll-Call & Justified Overrides
- When lighting or cameras fail, teachers can conduct 1-click grid roll-calls.
- Status overrides (`Present`, `Absent`, `Late`, `Excused`) require written justifications that are permanently recorded in the immutable `AuditLog` table.

### 3. Comprehensive Analytics & Reporting
- **Interactive Visualizations:** Overall attendance trends, subject-wise comparisons, weekday distribution heatmaps, and top absentee rankings rendered with Chart.js.
- **Shortage Projection Calculator:** Predicts how many future consecutive classes a student must attend to cross the 75% minimum threshold.
- **Instant Document Exports:** Formatted Excel workbooks (`.xlsx`) with headers, color styling, and date/status filters, along with standard CSV exports.

### 4. Administrative Governance & Telemetry
- **Role-Based Access Control:** Strict decorators `@admin_required`, `@teacher_required`, and `@student_required`.
- **Bulk Data Ingestion:** CSV student roster import with row-by-row error diagnostics and downloadable CSV template.
- **Database Hot Backups:** 1-click administrative database snapshot generation stored in `data/backups/`.
- **Live Diagnostics:** Real-time `/health` check and system diagnostic panel displaying CPU, Python, database, and active biometric engine status.

---

## 🛠 Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Backend** | Python 3.10+, Flask 3.0, Flask-SQLAlchemy, Flask-Login, Flask-WTF, Werkzeug |
| **Database** | SQLite (Default Dev/Testing) / PostgreSQL Compatible SQLAlchemy 2.0 ORM |
| **Biometrics** | OpenCV 4.10+ (Haar Cascade & LBPH Recognizer), Optional Dlib / `face_recognition` |
| **Data & Reports** | Pandas, OpenPyXL, NumPy, Pillow |
| **Frontend** | Jinja2 Templates, Tailwind CSS (CDN), Vanilla JavaScript (ES6+), Chart.js (CDN) |
| **Testing** | Pytest, Pytest-Flask |

---

## 🔍 Face Recognition Engine & Fallback Architecture

The platform uses a pluggable **Engine Abstraction Pattern** (`FaceRecognitionEngine`) that automatically discovers the available computer vision runtime at startup:

1. **Primary Engine (`Dlib-CNN / Dlib-HOG`):** Utilizes `dlib` 128-dimensional deep metric embeddings if installed.
2. **Native Fallback Engine (`OpenCV-LBPH`):** Native OpenCV Local Binary Patterns Histograms (LBPH) with Haar cascade face detection. Runs cross-platform without requiring C++ compilation toolchains.

> ℹ️ **Current Active Engine:** `OpenCV-LBPH` (Detected and fully functional).

---

## ⚡ Installation & Quickstart

### Prerequisites
- Python 3.10, 3.11, or 3.12
- Git

### 1. Clone & Set Up Environment

```bash
# Clone the repository
git clone https://github.com/your-institution/smart-attendance.git
cd smart-attendance

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Windows (cmd.exe):
.venv\Scripts\activate.bat
# Linux / macOS:
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Copy `.env.example` to `.env`:

```bash
# Windows:
copy .env.example .env
# Linux / macOS:
cp .env.example .env
```

### 4. Seed Database with Realistic Demo Data

Populates 30 students, 3 classrooms, 9 course subjects, timetable slots, holidays, and 60 days of historical attendance:

```bash
python seed.py
```

### 5. Start the Web Server

```bash
python run.py
```

Navigate to **`http://127.0.0.1:5000`** in your web browser.

---

## 🔑 Demo Accounts

The database comes pre-seeded with the following credentials:

| Role | Email | Password | Access Scope |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin@example.com` | `Admin@123` | Full institutional configuration & audit |
| **Teacher 1** | `dr.sarah@example.com` | `Teacher@123` | CSE-3A & CSE-3B classes, live session launch |
| **Teacher 2** | `prof.robert@example.com` | `Teacher@123` | ECE-2A & CSE courses, live session launch |
| **Student** | `aarav.sharma@example.edu` | `Student@123` | Read-only student attendance dashboard |

---

## 📡 REST API Reference

### Health & Monitoring
- `GET /health` — Returns JSON health telemetry, database status, active face engine, and app version.

### Face Recognition & Frame Ingestion
- `POST /attendance/api/session/<id>/verify-frame` — Live webcam frame inference against enrolled class roster.
- `POST /admin/api/students/<id>/enroll-frame` — Biometric sample capture and feature vector storage.

### Analytics Data APIs
- `GET /analytics/api/summary` — Institutional attendance KPIs and aggregate percentage.
- `GET /analytics/api/trend` — Time-series daily attendance rates.
- `GET /analytics/api/classwise` — Class-by-class attendance breakdown.
- `GET /analytics/api/subjectwise` — Subject-level attendance percentages.
- `GET /analytics/api/heatmap` — Weekday period distribution matrix.
- `GET /analytics/api/distribution` — Student tier distribution (>=85%, 75-84%, 65-74%, <65%).
- `GET /analytics/api/top-absent` — Ranked roster of chronic absentees.

### Reporting & Exports
- `GET /reports/export/csv` — Filterable attendance export in standard CSV format.
- `GET /reports/export/xlsx` — Formatted Excel workbook (`.xlsx`) with colored metric headers.

---

## 🛡 Security & Biometric Data Privacy

1. **Biometric Privacy Compliance:**
   - Raw face photographs are processed into numerical feature histograms/encodings.
   - Explicit student consent (`biometric_consent`) is required before enrollment.
   - Right-to-be-forgotten: Biometric records can be permanently purged at any time from the Student or Admin profile.
2. **Credential Security:** Passwords hashed with Werkzeug scrypt/pbkdf2 salts.
3. **Cross-Site Request Forgery (CSRF):** Protected via Flask-WTF CSRF tokens across all form submissions.
4. **Audit Trail:** Immutable logging of all logins, logouts, session launches, manual overrides, CSV imports, settings adjustments, and data exports.

---

## 🧪 Automated Testing Suite

The project includes unit, integration, and end-to-end test suites with 100% test passing rate.

```bash
# Run full unit & integration test suite
pytest -v

# Run comprehensive end-to-end application smoke test
python tests/smoke_test.py
```

### Test Coverage Summary
- `test_auth.py`: Login, logout, password hashing, password change, inactive account locking.
- `test_permissions.py`: Role-based route containment for Admin, Teacher, and Student.
- `test_students.py`: Student creation, validation, unique roll numbers, soft-deletion.
- `test_classes.py`: Classroom, subject, and timetable slot scheduling.
- `test_attendance.py`: Session start, duplicate prevention, manual marking, status override, end-session bulk absent marking.
- `test_face_service.py`: Base64 frame decoding, consecutive match tracker, blur/brightness validation, liveness heuristics.
- `test_imports.py`: CSV template generation, row-by-row roster ingestion, error diagnostics.
- `test_reports.py`: Attendance percentage calculations, shortage projections, CSV and Excel workbook generation.
- `test_analytics.py`: JSON aggregations and metric summaries.
- `smoke_test.py`: 10-step full live application verification.

---

## 🌐 Production Deployment

For production deployments on Linux/Ubuntu:

```bash
# 1. Install Gunicorn
pip install gunicorn

# 2. Configure PostgreSQL URI in .env:
# DATABASE_URL=postgresql://user:password@localhost:5432/smart_attendance

# 3. Launch with Gunicorn WSGI:
gunicorn -w 4 -b 0.0.0.0:8000 "app:create_app('production')"
```

Configure Nginx as a reverse proxy with SSL termination for HTTPS to enable browser `getUserMedia()` webcam access in production.

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
