# TODO - Narrative Modeling App

## 🚨 Critical Blockers (Must Fix First)

### Testing & CI/CD
- [x] **Fix backend test suite** - Tests can now run with `uv run pytest` ✅
- [ ] **Complete GitHub Actions CI/CD pipeline** - Partial configuration exists
- [ ] **Implement E2E testing with Playwright** - No E2E tests exist

### Test Suite Completion
- [ ] **Properly fix backend test suite**
  - [ ] Fix 19 failing unit tests (mostly threshold and edge case issues)
  - [ ] Create MongoDB fixtures for integration tests
  - [ ] Create Redis fixtures for cache tests
  - [ ] Mock AWS S3 for upload tests
  - [ ] Enable and fix all integration tests
  - [ ] Add missing test coverage for API endpoints

## 🎯 Core Feature Gaps

### 8-Stage Workflow Navigation System ✅ (Completed 2025-06-21)
- [x] **Create unified 8-stage workflow bar** ✅
  - [x] Persistent navigation showing all 8 stages
  - [x] Progress indicators for completed/current/locked stages
  - [x] Stage validation before progression
  - [x] Smooth stage transition animations with Framer Motion
  - [x] Mobile-responsive workflow UI
- [x] **Integrate existing features into workflow stages** ✅
  - [x] Stage 1: Data Loading (upload page with drag & drop)
  - [x] Stage 2: Data Profiling (explore page with workflow integration)
  - [x] Stage 3: Data Preparation (prepare page ready for transformation UI)
  - [x] Stage 4: Feature Engineering (features page with AI suggestions)
  - [x] Stage 5: Model Training (model page with AutoML)
  - [x] Stage 6: Model Evaluation (evaluate page with metrics)
  - [x] Stage 7: Prediction (predict page with single/batch)
  - [x] Stage 8: Deployment (deploy page with one-click API)
- [x] **Workflow state management** ✅
  - [x] Save workflow progress per dataset (localStorage + API ready)
  - [x] Allow jumping to completed stages
  - [x] Enforce dependencies between stages
  - [x] Clear visual indicators of stage status
- [ ] **Remaining Integration Tasks**
  - [ ] Connect transformation pipeline UI to prepare page
  - [x] Transformation pipeline backend-frontend integration ✅ (2025-06-21)
  - [ ] Add backend workflow persistence API
  - [ ] Test end-to-end workflow with real data

### Data Transformation UI ✅ (Completed 2025-06-21)
- [x] **Backend transformation engine** ✅
  - [x] Core transformation framework with extensible design
  - [x] Remove duplicates, trim whitespace, fill missing transformations
  - [x] Preview and apply functionality with history tracking
  - [x] Validation system with suggestions
  - [x] Recipe manager for saving/sharing pipelines
  - [x] Comprehensive API endpoints
  - [x] Export recipes to Python code
  - [x] Unit tests (7/7 passing)
- [x] **Build visual transformation pipeline frontend** ✅ (2025-06-20)
  - [x] Drag-and-drop transformation interface (react-flow)
  - [x] Real-time preview panel with before/after view
  - [x] Transformation library sidebar with categories
  - [x] Recipe browser for discovering community recipes
  - [x] Integration with backend API endpoints ✅ (2025-06-21)
  - [x] NextAuth authentication integration ✅ (2025-06-21)
  - [x] TypeScript transformation service layer ✅ (2025-06-21)
  - [ ] Node parameter editing UI
  - [ ] Connect to Stage 3 of workflow
- [ ] **Add advanced transformations**
  - [ ] Date/time transformations (extract parts, calculate age)
  - [ ] Type conversions (numeric, string, datetime, boolean)
  - [ ] Encoding transformations (one-hot, label encoding)
  - [ ] Custom formula builder with expression editor
  - [ ] Conditional logic support (if/then/else)
  - [ ] Regular expression transformations

### Machine Learning Algorithms
- [ ] **Implement time series tools**
  - [ ] ARIMA Tool
  - [ ] Prophet Tool
  - [ ] Seasonal Decomposition Tool
  - [ ] Trend Analysis Tool
- [ ] **Add clustering algorithms**
  - [ ] KMeans Tool
  - [ ] DBSCAN Tool
  - [ ] Hierarchical Clustering Tool
  - [ ] Gaussian Mixture Tool
- [ ] **Advanced classification tools**
  - [ ] Neural Network Classifier
  - [ ] Naive Bayes Tool
  - [ ] Ensemble Voting Tool (automated)

### Model Interpretability
- [ ] **SHAP integration** - Advanced model explanations
- [ ] **Partial dependence plots** - Feature impact visualization
- [ ] **Example-based explanations** - Show similar cases
- [ ] **Add evaluation visualizations to UI**
  - [ ] Learning curves
  - [ ] Confusion matrices
  - [ ] ROC curves

### Production Features
- [ ] **Scheduling system**
  - [ ] Cron-based scheduler
  - [ ] Dependency management
  - [ ] Failure recovery
  - [ ] Notification system
- [ ] **Alerting system**
  - [ ] Configurable thresholds
  - [ ] Multi-channel notifications (email, Slack)
  - [ ] Escalation policies
  - [ ] Alert suppression
- [ ] **Enhanced drift detection**
  - [ ] Complete feature drift algorithms
  - [ ] Automated drift alerts
  - [ ] Drift visualization

## 🔧 Enhancement Priorities

### Accessibility & UX
- [ ] **Complete WCAG 2.1 AA compliance**
  - [ ] Full keyboard navigation
  - [ ] Screen reader optimization
  - [ ] High contrast mode
  - [ ] Focus indicators
- [ ] **Power user features**
  - [ ] Keyboard shortcuts
  - [ ] Custom themes
  - [ ] Power user mode
  - [ ] Batch operations

### Integrations
- [ ] **Database connectors**
  - [ ] PostgreSQL connector
  - [ ] MySQL connector
  - [ ] MongoDB direct connection
  - [ ] BigQuery connector
- [ ] **BI tool integrations**
  - [ ] Tableau connector
  - [ ] Power BI integration
  - [ ] Excel/Sheets plugins
  - [ ] Zapier integration
- [ ] **SDK generators**
  - [ ] Python SDK
  - [ ] JavaScript SDK
  - [ ] R package

### Advanced Analytics
- [ ] **What-if analysis tools**
  - [ ] Sensitivity charts
  - [ ] Scenario comparison
  - [ ] Optimization suggestions
  - [ ] Parameter impact analysis
- [ ] **Streaming predictions**
  - [ ] WebSocket support
  - [ ] Real-time data ingestion
  - [ ] Stream processing
- [ ] **GPU support**
  - [ ] GPU detection and allocation
  - [ ] Memory management UI
  - [ ] Performance monitoring
  - [ ] Multi-GPU support

### Data Management
- [ ] **Complete data versioning**
  - [ ] Diff visualization
  - [ ] Rollback capabilities
  - [ ] Version comparison tools
  - [ ] Branch/merge for datasets
- [ ] **Enhanced feature store**
  - [ ] Feature versioning UI
  - [ ] Feature lineage tracking
  - [ ] Feature sharing across projects

## 📚 Documentation & Testing

### Documentation
- [ ] **Comprehensive user guides** - Step-by-step tutorials
- [ ] **Video tutorials** - Screen recordings for key workflows
- [ ] **API client examples** - Sample code in multiple languages
- [ ] **Best practices guide** - ML workflow recommendations

### Testing & Quality
- [ ] **Performance benchmarking suite**
- [ ] **Load testing** - Simulate 1000+ concurrent users
- [ ] **Chaos testing** - Failure scenario testing
- [ ] **Security audit** - Penetration testing
- [ ] **Regression test suite** - Automated feature testing

### Infrastructure
- [ ] **Spark integration** - Distributed processing
- [ ] **Enhanced load balancing** - Multi-region support
- [ ] **CDN configuration** - Global asset delivery
- [ ] **Backup automation** - Scheduled backups with testing

## 🚀 Quick Wins (Can do anytime)

- [ ] Add smooth stage transition animations
- [ ] Implement Bayesian optimization for hyperparameters
- [ ] Add model lineage visualization
- [ ] Create FAQ system
- [ ] Add email notifications for job completion
- [ ] Implement data retention UI
- [ ] Add fine-grained permissions UI
- [ ] Build admin dashboard

## 📊 Progress Tracking

### Completed Recently
- ✅ Core ML infrastructure with AutoML
- ✅ Comprehensive data profiling and statistics
- ✅ Model deployment with API generation
- ✅ A/B testing framework
- ✅ Redis caching layer
- ✅ PII detection and security
- ✅ Model export (PMML, ONNX, Python)
- ✅ Interactive onboarding system
- ✅ **Backend Transformation Engine (2025-06-20)**
  - Transformation framework with preview/apply
  - Recipe manager for saving/sharing pipelines
  - Validation system with AI suggestions
  - Export transformations to Python code
  - 15+ RESTful API endpoints
  - Comprehensive unit tests
- ✅ **Frontend Transformation UI (2025-06-20)**
  - React Flow drag-and-drop pipeline builder
  - Real-time transformation preview
  - Recipe browser with community sharing
  - Transformation library with categories
  - Before/after comparison views
  - NOT YET integrated into 8-stage workflow
- ✅ **NextAuth Migration (2025-06-21)**
  - Replaced Clerk with NextAuth
  - Google and GitHub OAuth providers
  - Development bypass mode (SKIP_AUTH)
  - Custom sign-in page
  - User dropdown menu in sidebar
  - Backend JWT validation
  - Migration documentation
- ✅ **8-Stage Workflow Navigation System (2025-06-21)**
  - WorkflowProvider context for state management
  - WorkflowBar component with progress indicators
  - Stage validation and auto-progression
  - Smooth animations with Framer Motion
  - All 8 stage pages created/updated
  - Workflow state persistence
  - Mobile-responsive design
  - Ready for transformation pipeline integration

- ✅ **Transformation Pipeline Integration (2025-06-21)**
  - Completed full stack integration between frontend and backend
  - Fixed authentication from Clerk to NextAuth in transformation endpoints
  - Created TransformationService TypeScript class with type-safe API calls
  - Updated transform page and RecipeBrowser components
  - Added transformation routes to FastAPI main app
  - Added database models (TransformationRecipe, RecipeExecutionHistory) to initialization
  - Development mode works with SKIP_AUTH environment variable

### Next Sprint Priorities
1. Add backend workflow persistence API (next critical priority)
2. Connect transformation pipeline UI to workflow Stage 3 (prepare page)
3. Fix testing infrastructure (blocking development progress)
4. Complete GitHub Actions CI/CD pipeline (medium priority)
5. Add time series tools (user requested feature)
6. Implement scheduling system (production requirement)
7. Complete accessibility compliance (legal requirement)
8. **backend/app/api/deps.py: Implement get_current_user_id for NextAuth**
  - Replace the current mock implementation with real NextAuth token validation and user extraction.