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

### 8-Stage Workflow Navigation System
- [ ] **Create unified 8-stage workflow bar**
  - [ ] Persistent navigation showing all 8 stages
  - [ ] Progress indicators for completed/current/locked stages
  - [ ] Stage validation before progression
  - [ ] Smooth stage transition animations
  - [ ] Mobile-responsive workflow UI
- [ ] **Integrate existing features into workflow stages**
  - [x] Stage 1: Data Loading (exists but not in workflow)
  - [x] Stage 2: Data Profiling (exists but not in workflow)
  - [ ] Stage 3: Data Preparation (connect transformation UI)
  - [ ] Stage 4: Feature Engineering (partial backend, no UI)
  - [ ] Stage 5: Model Training (exists but not in workflow)
  - [ ] Stage 6: Model Evaluation (partial, not in workflow)
  - [ ] Stage 7: Prediction (exists but not in workflow)
  - [ ] Stage 8: Deployment (exists but not in workflow)
- [ ] **Workflow state management**
  - [ ] Save workflow progress per dataset
  - [ ] Allow jumping to completed stages
  - [ ] Enforce dependencies between stages
  - [ ] Clear visual indicators of stage status

### Data Transformation UI
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
  - [ ] Integration with backend API endpoints (needs auth)
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

### Next Sprint Priorities
1. Implement 8-stage workflow navigation system (critical UX gap)
2. Fix testing infrastructure (blocking development)
3. Complete Clerk authentication integration
4. Add time series tools (user requested feature)
5. Implement scheduling system (production requirement)
6. Complete accessibility compliance (legal requirement)