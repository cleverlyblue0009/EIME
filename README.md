# EIME / ACRE

## Overview
Executive Intent Modeling Engine (EIME) powers a dual-trace reasoning workflow measuring actual vs. intended execution, highlighting divergence nodes, and animating the execution graph inside a premium dashboard.

## Structure
- `backend/`: FastAPI services (AST parser, execution/intent/divergence engines, simulation endpoints)
- `frontend/`: Vite + React + Tailwind dashboard with Monaco, Framer Motion visualizations, and Zustand state

## Setup

### Backend
```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```
Endpoints:
* `POST /analyze`
* `POST /intent`
* `POST /divergence`
* `POST /simulate`

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Access the dashboard at `http://localhost:5173`

## Notes
- The frontend proxies API calls to the backend (`/analyze`, `/simulate`, etc.) but gracefully falls back to mock data when offline.
- Monaco editor, animated graphs, and divergence pulses highlight the earliest divergence node (“FIRST DIVERGENCE”) for patent-grade clarity.
