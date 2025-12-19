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
│   ├── backend/          # FastAPI backend for ML orchestration
│   └── mcp/              # MCP server for advanced data processing
├── ml/                   # Python modeling scripts & training logic
├── shared/               # Shared types, constants, and utilities
├── infrastructure/       # Infrastructure as code (deployment configs)
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
- **Backend**: Copy `.env.example` to `.env` and configure
  - MongoDB Atlas connection required (no local MongoDB needed)
  - Set `MONGODB_URI` to your Atlas connection string
  - Configure AWS S3 credentials for file storage
- **Frontend**: Copy `.env.local.example` to `.env.local` and configure
  - Set `NEXT_PUBLIC_API_URL` to backend URL
- **Development**: Set `SKIP_AUTH=true` to bypass authentication

---

## 📌 Status

✅ **Sprint 11 Complete:** Data Model Refactoring & Performance Benchmarking
- ✅ **Model Architecture Refactoring** - UserData split into DatasetMetadata, TransformationConfig, ModelConfig
- ✅ **Data Versioning Foundation** - Content-based hashing, lineage tracking, S3 integration
- ✅ **Migration Testing Infrastructure** - Volume testing, rollback procedures, data integrity verification
- ✅ **Performance Benchmarking** - pytest-benchmark framework with throughput targets
- ✅ **100% Test Pass Rate** - 214/214 tests passing with 85%+ coverage

🟢 **Sprint 12: 87% Complete** - API Integration & Production Readiness (33/38 story points)
- ✅ **API Integration** - Version API routes with 23/23 tests passing
- ✅ **Data Versioning API** - Version tracking, lineage, recipe management
- ✅ **Production Deployment** - Model deployment API with 45/45 tests passing
- ✅ **MongoDB Atlas Migration** - Integration tests now use cloud-hosted Atlas
- ✅ **Critical Bug Fixes** (2025-11-11) - Fixed 11 runtime bugs + 1 critical security vulnerability (PR #48)
- 🚧 **AutoML Integration** - In progress
- 🚧 **CI/CD Pipeline** - Integration tests migrated to Atlas

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

Copyright © Frank Bria
Future deployment engine intended for release under an open-source license (MIT or Apache 2.0 TBD)

---

## ✍️ Author

**Frank Bria**  
Building solo with help from ChatGPT & GitHub Copilot  
[frankbria.com](https://frankbria.com)
