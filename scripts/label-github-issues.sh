#!/bin/bash
# Script to label GitHub issues for beta readiness prioritization
# Generated: 2026-01-01
# Usage: ./scripts/label-github-issues.sh

set -e  # Exit on error

echo "=============================================="
echo "GitHub Issue Labeling for Beta Prioritization"
echo "=============================================="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Step 1: Create labels if they don't exist
echo -e "${BLUE}Step 1: Creating labels...${NC}"
echo ""

# Priority labels
echo "Creating priority labels..."
gh label create "P0-Critical" --description "Beta blocker - must fix/build before beta" --color "b60205" --force || true
gh label create "P1-High" --description "Beta critical - should have for quality beta" --color "d93f0b" --force || true
gh label create "P2-Medium" --description "Post-beta V2 - high value enhancements" --color "fbca04" --force || true
gh label create "P3-Low" --description "Future enhancements - V3+" --color "0e8a16" --force || true

# Type labels
echo "Creating type labels..."
gh label create "bug" --description "Something isn't working" --color "d73a4a" --force || true
gh label create "security" --description "Security vulnerability or concern" --color "ee0701" --force || true
gh label create "enhancement" --description "New feature or request" --color "a2eeef" --force || true
gh label create "documentation" --description "Improvements or additions to documentation" --color "0075ca" --force || true

# Area labels
echo "Creating area labels..."
gh label create "frontend" --description "Frontend (Next.js) work" --color "bfdadc" --force || true
gh label create "backend" --description "Backend (FastAPI) work" --color "c5def5" --force || true
gh label create "ml-core" --description "Core ML features (AutoML, training, predictions)" --color "d4c5f9" --force || true
gh label create "deployment" --description "Deployment and infrastructure" --color "c2e0c6" --force || true
gh label create "testing" --description "Testing infrastructure or test fixes" --color "fef2c0" --force || true

echo -e "${GREEN}✓ Labels created${NC}"
echo ""

# Step 2: Label P0 issues (Beta Blockers)
echo -e "${BLUE}Step 2: Labeling P0 - Beta Blockers...${NC}"
echo ""

echo "Issue #125: Fix 23 failing E2E smoke tests"
gh issue edit 125 --add-label "P0-Critical,bug,frontend,testing"

echo "Issue #132: Feature Store security sandboxing"
gh issue edit 132 --add-label "P0-Critical,security,backend,ml-core"

echo "Issue #75: Core AutoML Engine"
gh issue edit 75 --add-label "P0-Critical,enhancement,backend,ml-core"

echo "Issue #79: Comprehensive Model Evaluation Dashboard"
gh issue edit 79 --add-label "P0-Critical,enhancement,frontend,backend,ml-core"

echo "Issue #82: Single Record and Batch Prediction Interface"
gh issue edit 82 --add-label "P0-Critical,enhancement,frontend,backend,ml-core"

echo -e "${GREEN}✓ P0 issues labeled (5 issues)${NC}"
echo ""

# Step 3: Label P1 issues (Beta Critical)
echo -e "${BLUE}Step 3: Labeling P1 - Beta Critical...${NC}"
echo ""

echo "Issue #76: Real-Time Training Monitoring"
gh issue edit 76 --add-label "P1-High,enhancement,frontend,backend,ml-core"

echo "Issue #80: Model Interpretability Tools (SHAP)"
gh issue edit 80 --add-label "P1-High,enhancement,backend,ml-core"

echo "Issue #83: Prediction Confidence Scores and Explanations"
gh issue edit 83 --add-label "P1-High,enhancement,backend,ml-core"

echo "Issue #87: Backend Workflow Persistence"
gh issue edit 87 --add-label "P1-High,enhancement,backend"

echo "Issue #88: Seamless Stage Transitions with Data Persistence"
gh issue edit 88 --add-label "P1-High,enhancement,frontend"

echo -e "${GREEN}✓ P1 issues labeled (5 issues)${NC}"
echo ""

# Step 4: Label P2 issues (Post-Beta V2)
echo -e "${BLUE}Step 4: Labeling P2 - Post-Beta V2...${NC}"
echo ""

echo "Issue #77: Automated Hyperparameter Tuning"
gh issue edit 77 --add-label "P2-Medium,enhancement,backend,ml-core"

echo "Issue #78: Model Versioning and History Tracking"
gh issue edit 78 --add-label "P2-Medium,enhancement,backend,ml-core"

echo "Issue #81: Error Analysis with Pattern Detection"
gh issue edit 81 --add-label "P2-Medium,enhancement,backend,ml-core"

echo "Issue #84: One-Click REST API Deployment"
gh issue edit 84 --add-label "P2-Medium,enhancement,backend,deployment"

echo "Issue #85: Deployment Monitoring Dashboard"
gh issue edit 85 --add-label "P2-Medium,enhancement,frontend,deployment"

echo "Issue #86: Integration Tools (Client SDKs, Postman)"
gh issue edit 86 --add-label "P2-Medium,enhancement,backend,deployment,documentation"

echo "Issue #89: AI Decision Engine for Tool Selection"
gh issue edit 89 --add-label "P2-Medium,enhancement,backend,ml-core"

echo "Issue #90: Comprehensive AI Integration Points"
gh issue edit 90 --add-label "P2-Medium,enhancement,backend,ml-core"

echo "Issue #101: Progressive Model Training Mode"
gh issue edit 101 --add-label "P2-Medium,enhancement,backend,ml-core"

echo "Issue #102: Data Quality Scoring System"
gh issue edit 102 --add-label "P2-Medium,enhancement,backend"

echo -e "${GREEN}✓ P2 issues labeled (10 issues)${NC}"
echo ""

# Step 5: Label P3 issues (Future Enhancements)
echo -e "${BLUE}Step 5: Labeling P3 - Future Enhancements...${NC}"
echo ""

echo "Issue #91: Role-Based Access Control (RBAC)"
gh issue edit 91 --add-label "P3-Low,enhancement,backend"

echo "Issue #92: Comprehensive Audit Logging System"
gh issue edit 92 --add-label "P3-Low,enhancement,backend"

echo "Issue #93: Database Connectors for Live Data Sources"
gh issue edit 93 --add-label "P3-Low,enhancement,backend"

echo "Issue #94: Cloud Storage Integrations"
gh issue edit 94 --add-label "P3-Low,enhancement,backend"

echo "Issue #95: Data Drift Detection"
gh issue edit 95 --add-label "P3-Low,enhancement,backend,ml-core"

echo "Issue #96: Model Performance Degradation Detection"
gh issue edit 96 --add-label "P3-Low,enhancement,backend,ml-core"

echo "Issue #97: Domain-Specific Feature Engineering Templates"
gh issue edit 97 --add-label "P3-Low,enhancement,backend,ml-core"

echo "Issue #98: Plugin Architecture"
gh issue edit 98 --add-label "P3-Low,enhancement,backend"

echo "Issue #99: Data Governance Features"
gh issue edit 99 --add-label "P3-Low,enhancement,backend"

echo "Issue #100: A/B Testing Framework"
gh issue edit 100 --add-label "P3-Low,enhancement,backend,deployment"

echo -e "${GREEN}✓ P3 issues labeled (10 issues)${NC}"
echo ""

# Step 6: Label special cases
echo -e "${BLUE}Step 6: Labeling special cases...${NC}"
echo ""

echo "Issue #35: E2E Test Failures (7 tests) - needs investigation"
gh issue edit 35 --add-label "bug,frontend,testing" || echo -e "${YELLOW}Warning: Issue #35 not found or already closed${NC}"

echo -e "${GREEN}✓ Special cases labeled${NC}"
echo ""

# Summary
echo "=============================================="
echo -e "${GREEN}Labeling Complete!${NC}"
echo "=============================================="
echo ""
echo "Summary:"
echo "  P0-Critical:  5 issues (Beta blockers)"
echo "  P1-High:      5 issues (Beta critical)"
echo "  P2-Medium:   10 issues (Post-beta V2)"
echo "  P3-Low:      10 issues (Future enhancements)"
echo "  Special:      1 issue  (Needs investigation)"
echo "  ─────────────────────────────────"
echo "  Total:       31 issues labeled"
echo ""
echo "Next steps:"
echo "  1. Review labels on GitHub"
echo "  2. Investigate if #35 is duplicate of #125"
echo "  3. Create GitHub Project board (see instructions below)"
echo "  4. Start work on #125 (E2E tests)"
echo ""
echo "View labeled issues:"
echo "  gh issue list --label P0-Critical"
echo "  gh issue list --label P1-High"
echo "  gh issue list --label P2-Medium"
echo "  gh issue list --label P3-Low"
echo ""
