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

- **Frontend:** Next.js, Tailwind CSS, Clerk (Auth)
- **Backend:** FastAPI, Python, Pydantic
- **Modeling:** scikit-learn, pandas, XGBoost, SHAP
- **Database:** MongoDB (or Postgres w/ Prisma in future)
- **Auth:** Clerk.dev
- **Dev Tools:** GitHub, Evernote (planning), Linear (issue tracking), MS Copilot, ChatGPT

---

## 🧪 Getting Started

> ⚠️ Project is in active solo development. Contributions and deployment tooling will be part of Phase 2+.

### To run the backend (FastAPI):
```bash
cd apps/backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### To run the frontend (placeholder):
```bash
cd apps/frontend
npm install
npm run dev
```

---

## 📌 Status

✅ Sprint 0 in progress:  
- Backend scaffold ✅  
- File upload + schema parsing pipeline 🚧  
- Data preview UI planned next

---

## 📚 License

Copyright © Frank Bria  
Future deployment engine intended for release under an open-source license (MIT or Apache 2.0 TBD)

---

## ✍️ Author

**Frank Bria**  
Building solo with help from ChatGPT & GitHub Copilot  
[frankbria.com](https://frankbria.com)
