#!/bin/bash
# The repo's GitHub label taxonomy, as code. Idempotent — safe to re-run.
#
# Originally generated 2026-01-01 as a one-time beta-triage migration; tracked and
# reduced to the taxonomy in PR #791 (see the note at the bottom for why).
#
# Usage: ./scripts/label-github-issues.sh

set -e  # Exit on error

echo "=============================================="
echo "GitHub Label Taxonomy"
echo "=============================================="
echo ""

# Color codes for output. No RED: nothing here reports a failure in colour —
# every `gh label create` ends in `|| true` because re-running is normal.
GREEN='\033[0;32m'
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

# Gating labels. These say WHO the issue is waiting on, which is not the same as
# priority: a P0 waiting on a trademark clearance is not startable and a P3 script
# run is. The issue-lifecycle `--next` discovery excludes both, so an agent picking
# the next issue stops re-deriving "can I actually start this?" from the comment
# threads every run.
echo "Creating gating labels..."
gh label create "needs-owner" --description "Blocked on a product/business decision; an agent must not invent it" --color "5319e7" --force || true
gh label create "needs-operator" --description "Requires box/production access an agent session cannot reach" --color "1d76db" --force || true

# Area labels
echo "Creating area labels..."
gh label create "frontend" --description "Frontend (Next.js) work" --color "bfdadc" --force || true
gh label create "backend" --description "Backend (FastAPI) work" --color "c5def5" --force || true
gh label create "ml-core" --description "Core ML features (AutoML, training, predictions)" --color "d4c5f9" --force || true
gh label create "deployment" --description "Deployment and infrastructure" --color "c2e0c6" --force || true
gh label create "testing" --description "Testing infrastructure or test fixes" --color "fef2c0" --force || true
gh label create "data-integrity" --description "Data correctness, consistency, and loss" --color "5319e7" --force || true
gh label create "perf" --description "Performance and scalability" --color "1d76db" --force || true

# Status labels. `blocked` is not decoration: the issue-lifecycle `--next` discovery
# excludes it along with the two gating labels above, so a repo where this script ran
# but `blocked` was never created has an exclusion rule that silently matches nothing.
echo "Creating status labels..."
gh label create "blocked" --description "Cannot proceed: needs external access, credentials, or upstream release" --color "B60205" --force || true

echo -e "${GREEN}✓ Labels created${NC}"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# This script creates the LABEL TAXONOMY and nothing else. It is idempotent and
# safe to re-run: every create ends in `|| true` because "already exists" is the
# normal case.
#
# It used to carry Steps 2-6, a one-time January 2026 migration that applied
# priorities to 31 specific issues by number. That was removed when the script was
# tracked (PR #791): all 31 have since closed, and several were re-triaged (#75 is
# P2.1 today, the script re-added P0-Critical), so re-running it would have stacked
# contradictory priority labels onto closed issues. Per-issue triage belongs in the
# issues, not frozen in a script.
#
# Priority lives in the issue TITLE as a `PX.Y` prefix; the PX-* labels mirror the
# tier. `needs-owner` / `needs-operator` / `blocked` are read by the issue-lifecycle
# `--next` discovery to skip what an agent cannot start.

echo "=============================================="
echo -e "${GREEN}Label taxonomy applied${NC}"
echo "=============================================="
echo ""
echo "Verify against what is live:"
echo "  gh label list --limit 100"
echo ""
echo "Labels that gate issue selection:"
echo "  gh issue list --label needs-owner      # waiting on a product decision"
echo "  gh issue list --label needs-operator   # waiting on box/production access"
echo "  gh issue list --label blocked          # waiting on something external"
echo ""
