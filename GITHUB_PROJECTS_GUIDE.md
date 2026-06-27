# GitHub Projects Guide - Beta Roadmap Tracking

## What is GitHub Projects?

GitHub Projects is a built-in project management tool (like Trello or Jira, but integrated with GitHub). It helps you:

- **Visualize your work** in kanban boards, tables, or roadmap views
- **Track progress** across multiple issues and PRs
- **Filter and group** issues by labels, assignees, milestones, etc.
- **Automate workflows** (e.g., move issues to "In Progress" when you start work)
- **See the big picture** of your beta roadmap

Think of it as a **dashboard for your GitHub issues**.

---

## Why Use GitHub Projects for Beta Roadmap?

Instead of manually checking 31 individual issues, you'll have:

1. **Visual Board** - See all P0, P1, P2, P3 issues in columns
2. **Progress Tracking** - See % complete for each priority level
3. **Timeline View** - See when issues are planned vs. actual progress
4. **Filtering** - Quickly view only "frontend" or "ml-core" issues
5. **Automation** - Issues auto-move when you start/finish work

**Example View**:
```
┌─────────────┬─────────────┬─────────────┬──────────────┬──────┐
│   Backlog   │  P0 Ready   │ In Progress │  In Review   │ Done │
├─────────────┼─────────────┼─────────────┼──────────────┼──────┤
│ #75 AutoML  │ #125 E2E    │             │              │      │
│ #79 Eval    │ #132 Sec    │             │              │      │
│ #82 Predict │             │             │              │      │
│ #76 Monitor │             │             │              │      │
│ ... (27)    │             │             │              │      │
└─────────────┴─────────────┴─────────────┴──────────────┴──────┘
```

---

## Setting Up Your Beta Roadmap Project

### Step 1: Create a New Project

#### Option A: Via GitHub Website (Easiest)
1. Go to your repo: https://github.com/frankbria/narrative-modeling-app
2. Click **"Projects"** tab (next to "Actions")
3. Click **"New project"** (green button)
4. Choose **"Board"** template (kanban-style)
5. Name it: **"Beta Roadmap - Narrative Modeling App"**
6. Click **"Create"**

#### Option B: Via GitHub CLI
```bash
gh project create --owner frankbria --title "Beta Roadmap - Narrative Modeling App" --format board
```

---

### Step 2: Customize Your Board Columns

By default, you'll get: **Todo**, **In Progress**, **Done**

Let's customize for beta roadmap:

1. Click **"..."** on each column → **"Rename"** or **"Delete"**
2. Create these columns (in order):

| Column Name | Description | Auto-move Rule |
|-------------|-------------|----------------|
| **📋 Backlog (P2-P3)** | Post-beta and future issues | None |
| **🎯 P0 Ready** | Beta blockers ready to start | When issue labeled `P0-Critical` |
| **🔥 P1 Ready** | Beta critical ready to start | When issue labeled `P1-High` |
| **🚧 In Progress** | Currently being worked on | When PR linked to issue |
| **👀 In Review** | Awaiting code review | When PR opened |
| **✅ Done** | Completed and merged | When PR merged or issue closed |

To create a column:
- Click **"+ Add column"**
- Enter name
- (Optional) Set automation in column settings

---

### Step 3: Add Issues to Your Project

#### Option A: Add All Issues at Once
1. In your project, click **"Add items"** (bottom of any column)
2. Search for repo: `frankbria/narrative-modeling-app`
3. Filter by label: `P0-Critical` (add all 5)
4. Repeat for `P1-High`, `P2-Medium`, `P3-Low`

#### Option B: Via GitHub CLI
```bash
# Get your project ID first
gh project list --owner frankbria

# Add issues to project (replace PROJECT_ID)
gh project item-add PROJECT_ID --owner frankbria --url https://github.com/frankbria/narrative-modeling-app/issues/125
gh project item-add PROJECT_ID --owner frankbria --url https://github.com/frankbria/narrative-modeling-app/issues/132
# ... repeat for all issues
```

#### Option C: Automatic (after labeling)
Once you run `./scripts/label-github-issues.sh`, you can set up automation:
- **Settings** → **Workflows** → **Add workflow**
- **When**: Issue labeled `P0-Critical`
- **Then**: Add to project in "P0 Ready" column

---

### Step 4: Add Custom Fields (Optional but Useful)

GitHub Projects supports custom fields for tracking more info:

1. Click **"..."** (top right) → **"Settings"**
2. Scroll to **"Custom fields"**
3. Add these fields:

| Field Name | Type | Options/Values |
|------------|------|----------------|
| **Priority** | Single select | P0-Critical, P1-High, P2-Medium, P3-Low |
| **Estimate** | Number | Days (e.g., 3, 5, 7) |
| **Area** | Single select | Frontend, Backend, ML-Core, Testing |
| **Has Plan?** | Single select | ✅ Yes, ⚠️ Needs Plan, 🚧 Planning |
| **Blocks Others?** | Text | Issue numbers (e.g., "#79, #82") |
| **Sprint** | Single select | Phase 1, Phase 2, Phase 3, Phase 4 |

These fields help you:
- Filter by area: "Show me only Frontend issues"
- Track estimates: "How many days of P0 work remaining?"
- See blockers: "Which issues can't start until #75 is done?"

---

### Step 5: Set Up Views

GitHub Projects supports multiple views of the same data:

#### View 1: Kanban Board (Default)
- Best for: Daily work, seeing current progress
- Shows: Issues moving through columns

#### View 2: Table View
1. Click **"+ New view"** → **"Table"**
2. Name: "All Issues - Detail View"
3. Columns to show: Title, Priority, Estimate, Area, Has Plan?, Status
4. Best for: Seeing all details at once, sorting/filtering

#### View 3: Roadmap View
1. Click **"+ New view"** → **"Roadmap"**
2. Name: "Beta Timeline"
3. Group by: Sprint (Phase 1-4)
4. Best for: Timeline visualization, seeing dependencies

#### View 4: Priority-Focused Board
1. Duplicate your main board view
2. Name: "P0 + P1 Only"
3. Filter: `label:P0-Critical,P1-High`
4. Best for: Focus on beta-critical work only

---

## Example Project Configuration

Here's what your final project might look like:

### Board View:
```
┌──────────────┬──────────────┬──────────────┬──────────────┬──────┐
│ Backlog      │ P0 Ready     │ In Progress  │ In Review    │ Done │
│ (P2-P3)      │              │              │              │      │
├──────────────┼──────────────┼──────────────┼──────────────┼──────┤
│ #77 Hyperparam│ #125 E2E    │              │              │      │
│ #78 Versioning│   ↳ 3-5d    │              │              │      │
│ #81 ErrorAnal│   ↳ Frontend│              │              │      │
│ #84 API Deploy│   ↳ ✅ Plan │              │              │      │
│ #85 Monitoring│              │              │              │      │
│ #86 SDKs     │ #132 Security│              │              │      │
│ ... (16 more)│   ↳ 3-5d    │              │              │      │
│              │   ↳ Backend │              │              │      │
│              │   ↳ ✅ Plan │              │              │      │
│              │              │              │              │      │
│              │ #75 AutoML  │              │              │      │
│              │   ↳ 7-10d   │              │              │      │
│              │   ↳ ML-Core │              │              │      │
│              │   ↳ ⚠️ Plan  │              │              │      │
│              │              │              │              │      │
│              │ #79 Eval    │              │              │      │
│              │ #82 Predict │              │              │      │
└──────────────┴──────────────┴──────────────┴──────────────┴──────┘
```

### Table View:
```
┌────────┬───────────────────┬──────────┬──────────┬────────────┬───────────┐
│ Issue  │ Title             │ Priority │ Estimate │ Area       │ Has Plan? │
├────────┼───────────────────┼──────────┼──────────┼────────────┼───────────┤
│ #125   │ Fix E2E tests     │ P0       │ 3-5d     │ Frontend   │ ✅ Yes    │
│ #132   │ Security sandbox  │ P0       │ 3-5d     │ Backend    │ ✅ Yes    │
│ #75    │ AutoML Engine     │ P0       │ 7-10d    │ ML-Core    │ ⚠️ Needs  │
│ #79    │ Eval Dashboard    │ P0       │ 5-7d     │ Frontend   │ ⚠️ Needs  │
│ #82    │ Prediction UI     │ P0       │ 5-7d     │ Frontend   │ ⚠️ Needs  │
│ ...    │                   │          │          │            │           │
└────────┴───────────────────┴──────────┴──────────┴────────────┴───────────┘
```

---

## Automation Workflows to Set Up

### Workflow 1: Auto-add labeled issues
**When**: Issue is labeled with `P0-Critical`, `P1-High`, `P2-Medium`, or `P3-Low`
**Then**: Add to project in appropriate column

### Workflow 2: Move to In Progress
**When**: PR is created that links to an issue
**Then**: Move issue to "In Progress" column

### Workflow 3: Move to In Review
**When**: PR is opened
**Then**: Move issue to "In Review" column

### Workflow 4: Move to Done
**When**: PR is merged OR issue is closed
**Then**: Move issue to "Done" column

To set up:
1. Project settings → **Workflows**
2. Click **"Add workflow"**
3. Choose trigger and action
4. Save

---

## Using Your Project Day-to-Day

### Morning Standup
1. Open your project board
2. Check "In Progress" - What's being worked on?
3. Check "P0 Ready" - What can start next?
4. Move your current work to "In Progress"

### During Work
1. Link PRs to issues: `Closes #125` in PR description
2. Issues auto-move as you work
3. Add notes/comments directly on project cards

### Weekly Review
1. Switch to "Table View"
2. Filter by Sprint/Phase
3. Check estimates vs. actual
4. Adjust priorities if needed

### Beta Launch Tracking
1. Use "Roadmap View"
2. See Phase 1-4 timeline
3. Track: Are we on schedule for beta?
4. Identify blockers early

---

## Pro Tips

### Tip 1: Use Milestones for Phases
Create GitHub milestones:
- **Phase 1: Make It Work** (due: Week 1)
- **Phase 2: Build ML Core** (due: Week 3)
- **Phase 3: Predictions** (due: Week 4)
- **Phase 4: Beta Prep** (due: Week 5)

Then filter project by milestone to see phase progress.

### Tip 2: Use Draft Issues for Planning
Create draft issues for each phase:
- "Plan #75 AutoML implementation"
- "Design evaluation dashboard UI"

Track these in your project until plans are ready.

### Tip 3: Link Related Issues
In issue descriptions, use:
- `Blocks #79, #82` (this issue blocks others)
- `Depends on #75` (this issue needs another first)

GitHub will show these relationships visually!

### Tip 4: Use Project Insights
Projects have built-in analytics:
- Burndown charts
- Velocity tracking
- Time in each column

Access: Project → "Insights" tab

### Tip 5: Mobile App
GitHub mobile app supports Projects - check progress on the go!

---

## Quick Start Commands

After running `./scripts/label-github-issues.sh`, run these:

```bash
# Create project
gh project create --owner frankbria --title "Beta Roadmap - Narrative Modeling App"

# Get project number (shown after creation, or list projects)
gh project list --owner frankbria

# Add all P0 issues (replace PROJECT_NUMBER)
gh project item-add PROJECT_NUMBER --owner frankbria --url https://github.com/frankbria/narrative-modeling-app/issues/125
gh project item-add PROJECT_NUMBER --owner frankbria --url https://github.com/frankbria/narrative-modeling-app/issues/132
gh project item-add PROJECT_NUMBER --owner frankbria --url https://github.com/frankbria/narrative-modeling-app/issues/75
gh project item-add PROJECT_NUMBER --owner frankbria --url https://github.com/frankbria/narrative-modeling-app/issues/79
gh project item-add PROJECT_NUMBER --owner frankbria --url https://github.com/frankbria/narrative-modeling-app/issues/82

# View project
gh project view PROJECT_NUMBER --owner frankbria --web
```

Or just do it via web interface - it's easier for first-time setup!

---

## Example: Your First Week

**Monday**:
- Create project
- Add all issues
- Set up columns
- Move #125 to "In Progress"

**Tuesday-Friday**:
- Work on #125
- Update project as you go (or auto-updates via workflows)
- Link PRs to issue

**Friday**:
- #125 moves to "Done" when PR merged
- Review board
- Move #132 to "In Progress" for next week

**Benefit**: At a glance, you see:
- ✅ 1/5 P0 issues complete (20% done)
- 🚧 1 in progress (#132)
- 📋 3 waiting (#75, #79, #82)
- Clear: #75 needs a plan before it can start

---

## Resources

- **GitHub Docs**: https://docs.github.com/en/issues/planning-and-tracking-with-projects
- **Video Tutorial**: https://www.youtube.com/watch?v=yFQ-p6wMS_Y (GitHub Projects overview)
- **Template Gallery**: https://github.com/orgs/community/discussions/categories/project-templates

---

## Summary

**GitHub Projects** = Visual dashboard for your 31 issues

**Why use it?**
- See progress at a glance
- Track beta roadmap phases
- Filter by priority, area, sprint
- Automate status updates
- Share with team/stakeholders

**Time to set up**: 15-30 minutes
**Time saved**: Hours per week (vs. manually tracking issues)

**Next Step**: Visit https://github.com/frankbria/narrative-modeling-app/projects and click "New project"!
