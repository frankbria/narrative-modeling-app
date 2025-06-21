# 🧠 Narrative Modeling App

An intuitive, AI-guided modeling platform that helps non-expert analysts build, explore, and deploy machine learning models—without writing a line of code.

This project aims to **democratize modeling** by combining powerful ML automation, storytelling-driven user experience, and visual workflows, wrapped in a seamless SaaS front end. The long-term vision includes a fully open-source deployment engine and intelligent model lifecycle management.

---

## 🚀 Phase 1: MVP SaaS Modeling Platform

### ✨ Key Features
- **Drag-and-drop data ingestion** (CSV/XLSX)
- **Automated EDA & visual insights**
- **AI-powered model recommendations**
- **Narrative-driven workflow guidance**
- **Feature engineering & preprocessing**
- **Model training and explainability tools**

Future phases will include:
- **Open-source deployment layer**
- **Automated model monitoring & retraining**
- **Data integration & streaming pipelines**

---

## 🏗️ Project Structure

```
narrative-modeling-app/
├── apps/
│   ├── frontend/         # Next.js + Tailwind UI
│   └── backend/          # FastAPI backend for orchestrating modeling
├── ml/                   # Python modeling scripts & training logic
├── shared/               # Shared types, constants, and utilities
├── .github/              # GitHub Actions / CI setup
├── README.md
└── .gitignore
```

---

## 📦 Tech Stack

- **Frontend:** Next.js, Tailwind CSS, NextAuth v5 (Auth), React Flow
- **Backend:** FastAPI, Python, Pydantic, Beanie ODM
- **Modeling:** scikit-learn, pandas, XGBoost, SHAP
- **Database:** MongoDB with Redis caching
- **Storage:** AWS S3
- **Auth:** NextAuth with Google/GitHub providers
- **Dev Tools:** GitHub, Linear (issue tracking), uv (Python), Docker

---

## 🧪 Getting Started

> ⚠️ Project is in active solo development. Contributions and deployment tooling will be part of Phase 2+.

### To run the backend (FastAPI):
```bash
cd apps/backend
uv sync  # Install dependencies
uvicorn app.main:app --reload
```

### To run the frontend:
```bash
cd apps/frontend
npm install
npm run dev
```

### Environment Setup:
- Backend: Copy `.env.example` to `.env` and configure
- Frontend: Copy `.env.local.example` to `.env.local` and configure
- For development: Set `SKIP_AUTH=true` to bypass authentication

---

## 📌 Status

✅ **Sprint 6+ Complete:** Advanced features phase
- ✅ **8-Stage Workflow System** - Complete ML pipeline navigation
- ✅ **Data Transformation Pipeline** - Visual drag-and-drop with backend integration
- ✅ **NextAuth Migration** - Google/GitHub OAuth with JWT validation
- ✅ **Redis Caching Layer** - Performance optimization
- ✅ **Model Export System** - PMML, ONNX, Python code generation
- ✅ **Docker Infrastructure** - Production-ready containerization

🚧 **Current Focus:**
- Backend workflow persistence API
- Advanced ML algorithms (time series, clustering)
- CI/CD pipeline completion
- Test suite stabilization (87% passing)

---

## 📚 License

Copyright © Frank Bria  
Future deployment engine intended for release under an open-source license (MIT or Apache 2.0 TBD)

---

## ✍️ Author

**Frank Bria**  
Building solo with help from ChatGPT & GitHub Copilot  
[frankbria.com](https://frankbria.com)
