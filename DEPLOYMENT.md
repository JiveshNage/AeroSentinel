# AeroSentinel — Production Deployment Guide
**Intelligent AWS Anomaly Detection & Quality Control**
*SIH Problem Statement: SIH26073*

This document provides a comprehensive, production-grade deployment runbook for deploying AeroSentinel to:
- **Frontend**: Vercel (React + TypeScript + Vite SPA)
- **Backend**: Render (FastAPI + Python + Uvicorn)
- **Database & Cloud Services**: Supabase (PostgreSQL, Supabase Auth, Realtime CDC, Storage Buckets, Row Level Security)
- **ML Processing**: Retained natively in FastAPI (LSTM-Autoencoder, Isolation Forest, 3D KDTree QC Engine, Explainability)

---

## 1. System Architecture Overview

```
                          ┌───────────────────────────┐
                          │   Vercel Edge Network     │
                          │   React + Vite Frontend   │
                          └─────────────┬─────────────┘
                                        │
                 ┌──────────────────────┴──────────────────────┐
                 │ HTTPS (REST API)                            │ Realtime / Auth (WSS / HTTPS)
                 ▼                                             ▼
  ┌───────────────────────────────┐              ┌───────────────────────────┐
  │         Render.com            │              │      Supabase Cloud       │
  │    FastAPI Application        │              │  • PostgreSQL (Port 6543) │
  │  • QC Rules & 3D Spatial QC   ├─────────────►│  • Supabase Auth (JWT)    │
  │  • Isolation Forest & LSTM    │  SQLAlchemy  │  • Realtime (CDC)         │
  │  • Sub-second WebSockets      │              │  • Storage (Private)      │
  │  • Ingestion & Validation     │              │  • Row Level Security     │
  └───────────────────────────────┘              └───────────────────────────┘
```

---

## 2. Supabase Cloud Configuration

### 2.1 Database & Migrations
1. Go to your [Supabase Dashboard](https://supabase.com/dashboard) and create a project (e.g. `aerosentinel-prod`).
2. Obtain your **Database Connection String** from **Project Settings $\rightarrow$ Database $\rightarrow$ Connection Pooling**:
   - Connection Mode: **Transaction** (Port `6543`)
   - URI format:
     ```
     postgresql+psycopg2://postgres.<project-ref>:<db-password>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require
     ```
3. Execute the production database script in Supabase **SQL Editor**:
   - Open and copy the contents of `supabase/migrations/20260925_production_schema_and_rls.sql`.
   - Run the script in the SQL Editor.
   - This script creates:
     - All primary application tables (`profiles`, `stations`, `raw_readings`, `qc_results`, `alerts`, `system_tasks`, `data_uploads`, `qc_feedback`, `model_registry`).
     - Compatibility database views (`observations`, `anomalies`, `maintenance_tasks`).
     - Composite performance index: `idx_observations_station_time` on `raw_readings(station_id, timestamp DESC)`.
     - Automated `auth.users` $\rightarrow$ `profiles` registration trigger.
     - Row Level Security (RLS) policies enforcing role-based read/write access.
     - Storage bucket definitions (`aerosentinel-uploads`, `aerosentinel-reports`).
     - Supabase Realtime publication on `alerts`, `stations`, and `qc_results`.

### 2.2 Storage Buckets Setup
If the SQL script did not auto-create the buckets via SQL, configure them in the Supabase Dashboard:
1. Navigate to **Storage** $\rightarrow$ **New Bucket**.
2. Create bucket: `aerosentinel-uploads` (Public: **No / Private**).
3. Create bucket: `aerosentinel-reports` (Public: **No / Private**).
4. Restrict allowed MIME types:
   - `aerosentinel-uploads`: `text/csv`, `application/json`, `application/octet-stream`.
   - `aerosentinel-reports`: `application/pdf`, `application/json`, `text/csv`.

### 2.3 Authentication Settings
1. Navigate to **Authentication** $\rightarrow$ **Providers** $\rightarrow$ **Email**.
2. Enable **Email / Password** provider.
3. In **Email Templates**, customize confirmation emails if user verification is required.
4. Default role: New users registered via Supabase Auth are automatically assigned the **`viewer`** role. Elevated roles (`admin`, `qc_analyst`, `forecaster`, `field_technician`) must be granted by an Administrator in the **Administration $\rightarrow$ Users** panel or via Supabase dashboard.

---

## 3. Backend Deployment (Render)

### 3.1 Blueprint Deployment (Recommended)
AeroSentinel includes a predefined `render.yaml` specification at the repository root.
1. Connect your GitHub repository to [Render](https://dashboard.render.com).
2. Click **New +** $\rightarrow$ **Blueprint**.
3. Select the `AeroSentinel` repository. Render will automatically detect `render.yaml`.
4. Fill in the required environment variables:
   - `DATABASE_URL`: Supabase Transaction Pooler URI (see Section 2.1).
   - `SUPABASE_URL`: `https://<your-project-ref>.supabase.co`
   - `SUPABASE_ANON_KEY`: Supabase anon public key.
   - `SUPABASE_SERVICE_ROLE_KEY`: Supabase service role secret key.
   - `CORS_ORIGINS`: `https://<your-frontend>.vercel.app,http://localhost:5173`
   - `JWT_SECRET_KEY`: Random 32+ character hex string (`openssl rand -hex 32`).

### 3.2 Manual Web Service Configuration (Alternative)
If setting up manually without Blueprint:
- **Environment**: Python 3.11
- **Root Directory**: `backend`
- **Build Command**:
  ```bash
  pip install --upgrade pip && pip install -r requirements.txt && alembic upgrade head
  ```
- **Start Command**:
  ```bash
  uvicorn main:app --host 0.0.0.0 --port $PORT
  ```
- **Health Check Path**: `/health`
- **Auto-Deploy**: Yes (on git push to `main`)

### 3.3 Backend Environment Variables Matrix
| Variable | Description | Example / Safe Placeholder |
|---|---|---|
| `APP_ENV` | Application environment mode | `production` |
| `APP_DEBUG` | Enable verbose error traces | `false` |
| `API_V1_STR` | API route prefix | `/api` |
| `PORT` | Dynamic port allocated by Render | `8000` (set by host) |
| `DATABASE_URL` | Supabase PostgreSQL Pooler URI | `postgresql+psycopg2://postgres.<ref>:<pw>@...supabase.com:6543/postgres?sslmode=require` |
| `SUPABASE_URL` | Supabase project URL | `https://<project-ref>.supabase.co` |
| `SUPABASE_ANON_KEY` | Supabase client anon public key | `<sb_publishable_...>` |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase backend service role key | `<secret_key>` |
| `JWT_SECRET_KEY` | JWT signature key | `<random-32-char-string>` |
| `CORS_ORIGINS` | Allowed CORS origins (comma-delimited) | `https://aerosentinel.vercel.app,http://localhost:5173` |
| `OPEN_METEO_BASE_URL` | External historical weather API | `https://archive-api.open-meteo.com/v1/archive` |
| `MODEL_STORAGE_PATH` | Directory for trained models | `backend/ml_engine/models` |

---

## 4. Frontend Deployment (Vercel)

### 4.1 Deployment Setup
1. Import your GitHub repository to [Vercel](https://vercel.com/new).
2. Configure project settings:
   - **Framework Preset**: `Vite`
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
   - **Install Command**: `npm install`

### 4.2 Frontend Environment Variables
In Vercel **Project Settings $\rightarrow$ Environment Variables**, configure:
| Variable | Value | Notes |
|---|---|---|
| `VITE_API_URL` | `https://<your-render-backend>.onrender.com` | Production backend URL |
| `VITE_SUPABASE_URL` | `https://<your-project-ref>.supabase.co` | Browser-safe Supabase URL |
| `VITE_SUPABASE_ANON_KEY` | `<your-supabase-anon-key>` | Public publishable key |
| `VITE_CARTO_TILE_URL` | `https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png?key=...` | High-DPI Basemap tiles |

> **SECURITY NOTE**: Never define `SUPABASE_SERVICE_ROLE_KEY` in Vercel environment variables. Vite injects any variable prefixed with `VITE_` into client bundles.

---

## 5. Local Development Quickstart

### 5.1 Backend Setup
```bash
# Navigate to backend directory
cd backend

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start development server
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

### 5.2 Frontend Setup
```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start Vite dev server with proxy to backend
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## 6. Pre-Flight Verification & Smoke Testing Checklist

- [ ] **Health Endpoint**: `curl https://<backend>/health` returns `{"status": "healthy"}` with 200 OK.
- [ ] **Database Connection**: Backend logs show successful connection pool initialization to Supabase PostgreSQL.
- [ ] **CORS Verification**: API rejects requests from unauthorized origins with standard 403 or missing `Access-Control-Allow-Origin`.
- [ ] **Authentication**:
  - Sign in as Demo Admin (`admin@imd.gov.in`) or via Supabase Auth email.
  - Role badge in top header displays user clearance level.
- [ ] **Role-Based Navigation**:
  - `admin`: All sidebar sections visible (Overview, Monitoring, Operations, Administration).
  - `forecaster`: Forecasts and monitoring visible; administration views hidden.
  - `field_technician`: Routes directly to Fleet Map & Maintenance; administration hidden.
  - `viewer`: Read-only views active; modification controls disabled.
- [ ] **Realtime Streaming**:
  - Dual stream: Sub-second FastAPI WebSocket (`/api/alerts/ws`) and Supabase Realtime table channel (`realtime:alerts`) both receive events.
- [ ] **Documentation**:
  - Operational User Manual (`AeroSentinel_User_Manual.pdf`) and Technical Product Spec (`AeroSentinel_Technical_Product_Spec.pdf`) download and preview correctly in the Documentation console.
