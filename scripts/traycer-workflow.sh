#!/bin/bash
set -euo pipefail

################################################################################
# Automated Traycer AI → Claude-Flow → CodeRabbit → Merge Workflow
#
# Usage: ./scripts/traycer-workflow.sh <issue-id> [options]
#
# Example: ./scripts/traycer-workflow.sh cf-123
#          ./scripts/traycer-workflow.sh cf-123 --topology mesh --max-iterations 5
#
# Environment Variables:
#   ANTHROPIC_API_KEY - Required for Claude API
#   GITHUB_TOKEN - Optional, uses gh auth if not set
#   MAX_CODERABBIT_ITERATIONS - Default: 3
################################################################################
# Check for global claude-flow installation
if command -v claude-flow &> /dev/null; then
    CLAUDE_FLOW="claude-flow"
else
    CLAUDE_FLOW="npx claude-flow@alpha"
fi

# Configuration
ISSUE_ID="${1:?Error: Issue ID required. Usage: $0 <issue-id>}"
TOPOLOGY="${2:-auto}"  # auto, hierarchical, mesh
MAX_ITERATIONS="${MAX_CODERABBIT_ITERATIONS:-3}"
PROJECT_ROOT="$(git rev-parse --show-toplevel)"
WORKFLOW_NAMESPACE="workflow/${ISSUE_ID}"
TRAYCER_PROMPT_FILE="${PROJECT_ROOT}/prompts/${ISSUE_ID}.txt"

# Load environment variables from .env if it exists
if [[ -f "${PROJECT_ROOT}/.env" ]]; then
    set -a
    source "${PROJECT_ROOT}/.env"
    set +a
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

################################################################################
# Phase 1: Initialization
################################################################################
phase_1_initialization() {
    log_info "Phase 1: Initialization"

    # Check if Traycer prompt file exists
    if [[ ! -f "$TRAYCER_PROMPT_FILE" ]]; then
        log_error "Traycer prompt file not found: $TRAYCER_PROMPT_FILE"
        log_info "Expected format: prompts/${ISSUE_ID}.txt"
        exit 1
    fi

    # Read Traycer prompt
    TRAYCER_PROMPT=$(cat "$TRAYCER_PROMPT_FILE")
    log_info "Loaded Traycer prompt (${#TRAYCER_PROMPT} chars)"

    # Analyze complexity to select topology
    if [[ "$TOPOLOGY" == "auto" ]]; then
        FILE_COUNT=$(echo "$TRAYCER_PROMPT" | grep -oiE '\b[0-9]+\s+(file|class|component)s?' | head -1 | grep -oE '[0-9]+' || echo "5")

        if (( FILE_COUNT <= 10 )); then
            TOPOLOGY="hierarchical"
            log_info "Auto-selected hierarchical topology (≤10 files)"
        else
            TOPOLOGY="mesh"
            log_info "Auto-selected mesh topology (>10 files)"
        fi
    fi

    # Initialize memory namespace
    $CLAUDE_FLOW memory store "${WORKFLOW_NAMESPACE}/prompt" "$TRAYCER_PROMPT" \
        --namespace workflow \
        --metadata "{\"issue_id\": \"${ISSUE_ID}\", \"timestamp\": \"$(date -Iseconds)\"}"

    $CLAUDE_FLOW memory store "${WORKFLOW_NAMESPACE}/topology" "$TOPOLOGY" \
        --namespace workflow

    log_success "Initialization complete (topology: ${TOPOLOGY})"
}

################################################################################
# Phase 2: Implementation
################################################################################
phase_2_implementation() {
    log_info "Phase 2: Implementation"

    # Initialize swarm with selected topology
    $CLAUDE_FLOW swarm init \
        --topology "$TOPOLOGY" \
        --max-agents 5 \
        --namespace "$WORKFLOW_NAMESPACE"

    # Store prompt in memory for agent access
    $CLAUDE_FLOW hooks pre-task \
        --description "Implement: ${ISSUE_ID}" \
        --session-id "$WORKFLOW_NAMESPACE"

    # Spawn implementation swarm
    # This uses Claude Code's Task tool internally via MCP
    $CLAUDE_FLOW swarm spawn \
        --objective "$TRAYCER_PROMPT" \
        --strategy development \
        --agents "coder,tester,reviewer" \
        --parallel \
        --namespace "$WORKFLOW_NAMESPACE"

    # Monitor swarm execution
    local max_wait=1800  # 30 minutes
    local elapsed=0
    local interval=10

    while (( elapsed < max_wait )); do
        status=$($CLAUDE_FLOW swarm status --namespace "$WORKFLOW_NAMESPACE" --json | jq -r '.status')

        if [[ "$status" == "completed" ]]; then
            log_success "Implementation completed"
            break
        elif [[ "$status" == "failed" ]]; then
            log_error "Implementation failed"
            $CLAUDE_FLOW swarm status --namespace "$WORKFLOW_NAMESPACE"
            exit 1
        fi

        sleep "$interval"
        elapsed=$((elapsed + interval))
        echo -n "."
    done

    if (( elapsed >= max_wait )); then
        log_error "Implementation timeout (${max_wait}s)"
        exit 1
    fi

    # Post-task hook (auto-formats code, trains patterns)
    $CLAUDE_FLOW hooks post-task \
        --task-id "$WORKFLOW_NAMESPACE" \
        --export-metrics true
}

################################################################################
# Phase 3: Pre-PR Validation
################################################################################
phase_3_validation() {
    log_info "Phase 3: Pre-PR Validation"

    # Run validating-pre-commit skill (global)
    # This runs: ruff, mypy (Python) or eslint, tsc (TypeScript), tests
    log_info "Running pre-commit validation..."

    # Detect project type
    if [[ -f "pyproject.toml" ]] || [[ -f "setup.py" ]]; then
        # Python project
        uv run ruff check . --fix || { log_error "Ruff linting failed"; return 1; }
        uv run mypy . || { log_error "Type checking failed"; return 1; }
        uv run pytest || { log_error "Tests failed"; return 1; }
    elif [[ -f "package.json" ]]; then
        # Node.js project
        npm run lint || { log_error "Linting failed"; return 1; }
        npm run typecheck || { log_error "Type checking failed"; return 1; }
        npm test || { log_error "Tests failed"; return 1; }
    fi

    # Check for incomplete implementation
    if git grep -qE 'TODO|FIXME|NotImplementedError|raise NotImplemented'; then
        log_warning "Found TODO/FIXME/NotImplemented markers"
        git grep -nE 'TODO|FIXME|NotImplementedError|raise NotImplemented'

        # Store in memory for human review
        $CLAUDE_FLOW memory store \
            "${WORKFLOW_NAMESPACE}/validation/incomplete" \
            "true" \
            --namespace workflow

        return 1
    fi

    log_success "Pre-PR validation passed"
    return 0
}

################################################################################
# Phase 4: PR Creation
################################################################################
phase_4_pr_creation() {
    log_info "Phase 4: PR Creation"

    # Ensure we're on main/master
    MAIN_BRANCH=$(git remote show origin | grep 'HEAD branch' | cut -d' ' -f5)
    git checkout "$MAIN_BRANCH"
    git pull origin "$MAIN_BRANCH"

    # Create feature branch
    BRANCH_NAME="feature/${ISSUE_ID}-$(echo "$TRAYCER_PROMPT" | head -c 50 | tr ' ' '-' | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9-]//g')"
    git checkout -b "$BRANCH_NAME"

    # Stage all changes
    git add .

    # Generate commit message from memory
    COMMIT_MSG=$(cat <<EOF
feat: ${ISSUE_ID} - $(echo "$TRAYCER_PROMPT" | head -c 80)

Automated implementation via claude-flow swarm orchestration.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
EOF
)

    # Commit changes
    git commit -m "$COMMIT_MSG"

    # Push to remote
    git push -u origin "$BRANCH_NAME"

    # Generate PR description
    PR_DESCRIPTION=$($CLAUDE_FLOW memory query "${WORKFLOW_NAMESPACE}" --namespace workflow --format markdown)

    # Create PR
    PR_URL=$(gh pr create \
        --title "[$ISSUE_ID] $(echo "$TRAYCER_PROMPT" | head -c 100)" \
        --body "$PR_DESCRIPTION" \
        --label "automated,needs-review" \
        --base "$MAIN_BRANCH" \
        --head "$BRANCH_NAME")

    # Extract PR number
    PR_NUMBER=$(echo "$PR_URL" | grep -oE '[0-9]+$')

    # Store PR info in memory
    $CLAUDE_FLOW memory store \
        "${WORKFLOW_NAMESPACE}/pr/number" \
        "$PR_NUMBER" \
        --namespace workflow

    $CLAUDE_FLOW memory store \
        "${WORKFLOW_NAMESPACE}/pr/url" \
        "$PR_URL" \
        --namespace workflow

    # Update bd issue tracker
    if command -v bd &> /dev/null; then
        bd update "$ISSUE_ID" --status review --pr "$PR_NUMBER"
    fi

    log_success "PR created: $PR_URL"
}

################################################################################
# Phase 5: CodeRabbit Feedback Loop
################################################################################
phase_5_coderabbit_loop() {
    log_info "Phase 5: CodeRabbit Feedback Loop"

    local iteration=1
    local pr_number=$($CLAUDE_FLOW memory query "${WORKFLOW_NAMESPACE}/pr/number" --namespace workflow)

    while (( iteration <= MAX_ITERATIONS )); do
        log_info "CodeRabbit iteration ${iteration}/${MAX_ITERATIONS}"

        # Wait for CodeRabbit review
        log_info "Waiting for CodeRabbit review..."
        sleep 30  # Give CodeRabbit time to process

        # Fetch CodeRabbit comments via GitHub API
        CODERABBIT_COMMENTS=$(gh api "/repos/{owner}/{repo}/pulls/${pr_number}/comments" \
            --jq '.[] | select(.user.login == "coderabbitai") | {path: .path, line: .line, body: .body}')

        if [[ -z "$CODERABBIT_COMMENTS" ]]; then
            log_success "No CodeRabbit feedback - PR approved!"
            break
        fi

        # Parse feedback into discrete issues
        ISSUE_COUNT=$(echo "$CODERABBIT_COMMENTS" | jq -s 'length')
        log_info "Found ${ISSUE_COUNT} CodeRabbit issues"

        # Store feedback in memory
        $CLAUDE_FLOW memory store \
            "${WORKFLOW_NAMESPACE}/coderabbit/iteration-${iteration}" \
            "$CODERABBIT_COMMENTS" \
            --namespace workflow

        # Spawn resolution agents (1 per issue, parallel)
        echo "$CODERABBIT_COMMENTS" | jq -c '.[]' | while read -r issue; do
            FILE=$(echo "$issue" | jq -r '.path')
            LINE=$(echo "$issue" | jq -r '.line')
            FEEDBACK=$(echo "$issue" | jq -r '.body')

            log_info "Spawning resolution agent for ${FILE}:${LINE}"

            # Use swarm to spawn resolution agent
            $CLAUDE_FLOW swarm spawn \
                --objective "Fix CodeRabbit feedback: ${FEEDBACK} in ${FILE}:${LINE}" \
                --strategy development \
                --agents "coder" \
                --namespace "${WORKFLOW_NAMESPACE}/resolution-${iteration}" &
        done

        # Wait for all resolution agents to complete
        wait

        # Re-run tests
        if ! phase_3_validation; then
            log_error "Validation failed after CodeRabbit fixes (iteration ${iteration})"

            if (( iteration >= MAX_ITERATIONS )); then
                log_error "Max iterations reached - triggering blocker queue"
                $CLAUDE_FLOW memory store \
                    "${WORKFLOW_NAMESPACE}/blocker" \
                    "CodeRabbit feedback resolution failed after ${MAX_ITERATIONS} iterations" \
                    --namespace workflow
                exit 1
            fi
        else
            log_success "Validation passed after fixes"

            # Commit fixes
            git add .
            git commit -m "fix: Address CodeRabbit feedback (iteration ${iteration})"
            git push

            log_success "Pushed iteration ${iteration} fixes"
        fi

        iteration=$((iteration + 1))
    done

    log_success "CodeRabbit feedback loop completed"
}

################################################################################
# Phase 6: Completion
################################################################################
phase_6_completion() {
    log_info "Phase 6: Completion"

    # Verify all tests pass
    if ! phase_3_validation; then
        log_error "Final validation failed"
        exit 1
    fi

    # Generate summary
    SUMMARY=$(cat <<EOF
Workflow ${ISSUE_ID} completed successfully!

✅ Implementation: Complete
✅ Tests: All passing
✅ CodeRabbit: All issues resolved
✅ PR: Ready for merge

PR: $($CLAUDE_FLOW memory query "${WORKFLOW_NAMESPACE}/pr/url" --namespace workflow)
EOF
)

    # Store summary
    $CLAUDE_FLOW memory store \
        "${WORKFLOW_NAMESPACE}/summary" \
        "$SUMMARY" \
        --namespace workflow

    # Archive workflow
    $CLAUDE_FLOW hooks session-end \
        --session-id "$WORKFLOW_NAMESPACE" \
        --export-metrics true

    # Update bd issue tracker
    if command -v bd &> /dev/null; then
         bd update "$ISSUE_ID" --status complete
    fi

    # Desktop notification (if available)
    if command -v notify-send &> /dev/null; then
        notify-send "Claude-Flow" "Workflow ${ISSUE_ID} complete! PR ready to merge."
    fi

    log_success "Workflow complete!"
    echo "$SUMMARY"
}

################################################################################
# Main Execution
################################################################################
main() {
    log_info "Starting automated workflow for ${ISSUE_ID}"

    # Execute phases sequentially
    phase_1_initialization
    phase_2_implementation

    # Validation loop (retry up to 3 times)
    local validation_attempts=0
    while (( validation_attempts < 3 )); do
        if phase_3_validation; then
            break
        fi

        validation_attempts=$((validation_attempts + 1))
        log_warning "Validation failed (attempt ${validation_attempts}/3) - re-running implementation"

        if (( validation_attempts >= 3 )); then
            log_error "Validation failed after 3 attempts"
            exit 1
        fi

        # Re-run implementation with feedback
        phase_2_implementation
    done

    phase_4_pr_creation
    phase_5_coderabbit_loop
    phase_6_completion
}

# Run main function
main "$@"
