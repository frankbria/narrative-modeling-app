# 🧠 Narrative Modeling App

[![Follow on X](https://img.shields.io/twitter/follow/FrankBria18044?style=social)](https://x.com/FrankBria18044)

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
- **Feature Store** - Centralized feature repository with versioning and reusability
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
│   ├── backend/          # FastAPI backend for ML orchestration
│   └── mcp/              # MCP server for advanced data processing
├── scripts/              # Utility scripts for development
├── docs/                 # Project documentation
├── .github/              # GitHub Actions / CI workflows
├── README.md
└── .gitignore
```

---

## 📦 Tech Stack

- **Frontend:** Next.js, Tailwind CSS, NextAuth v5 (Auth), React Flow
- **Backend:** FastAPI, Python, Pydantic, Beanie ODM
- **Modeling:** scikit-learn, pandas, XGBoost, SHAP
- **Database:** MongoDB Atlas (cloud-hosted) with Redis caching
- **Storage:** AWS S3
- **Auth:** NextAuth with Google/GitHub providers
- **Dev Tools:** GitHub (issues + Actions CI/CD), uv (Python), Docker

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
- **Backend**: Copy `.env.example` to `.env` and configure
  - MongoDB Atlas connection required (no local MongoDB needed)
  - Set `MONGODB_URI` to your Atlas connection string
  - Configure AWS S3 credentials for file storage
- **Frontend**: Copy `.env.local.example` to `.env.local` and configure
  - Set `NEXT_PUBLIC_API_URL` to backend URL
- **Development**: Set `SKIP_AUTH=true` to bypass authentication (requires `ENVIRONMENT=development` or `test` — backend startup fails hard otherwise)

---

## 📌 Status

Actively developed. Core platform is functional end-to-end: data ingestion,
automated EDA, feature engineering, model training/explainability, and a
production inference surface.

- ✅ **Test suite** — 1,400+ backend tests passing at 85%+ coverage
- ✅ **CI/CD** — GitHub Actions is the merge gate (backend lint/typecheck/tests,
  frontend lint/build/jest, MCP, integration, and an e2e smoke run)
- ✅ **Model training & explainability** — real trained-model surface under
  `/api/v1/ml/`, with SHAP-based interpretability
- ✅ **Production deployment** — model deploy + inference API
- ✅ **MongoDB Atlas** — cloud-hosted, with Redis caching and AWS S3 storage

---

## 📚 Documentation

For comprehensive documentation, see **[DOCUMENTATION_INDEX.md](docs/DOCUMENTATION_INDEX.md)**

Quick links:
- [Local Development Setup](docs/development/LOCAL_DEVELOPMENT.md)
- [Current Sprint (Sprint 12)](docs/sprints/sprint-12/SPRINT_12.md)
- [Sprint History](docs/sprints/)
- [User Stories](USER_STORIES.md)
- [Production Deployment](docs/deployment/PRODUCTION_DEPLOYMENT.md)
- [Production API Guide](docs/deployment/PRODUCTION_API_GUIDE.md)

## 📚 License

This project is licensed under the **GNU Affero General Public License v3.0 or later** (`AGPL-3.0-or-later`).

Copyright © 2025-2026 Noatak Enterprises, LLC, dba Bria Strategy Group

Because the AGPL covers network use (§13), the complete corresponding source code
of the deployed service is available at
<https://github.com/frankbria/narrative-modeling-app>. See [LICENSE](LICENSE) for the full terms.

---

## ✍️ Author

**Frank Bria**  
Building solo with help from ChatGPT & GitHub Copilot  
[frankbria.com](https://frankbria.com)
