# Plan limits and prices are product values (#474)

*2026-09-16T21:47:02Z*

AC1/AC5: the decided tiers live in ADR-003. This is the table the guard test parses.

```bash
sed -n '/^## Decision/,/^Worst-case/p' docs/architecture/ADR-003-plan-limits-and-pricing.md | grep '^|'
```

```output
| Tier | Price | training_runs | predictions | uploads | ai_calls |
|---|---|---|---|---|---|
| FREE | $0 | 5 | 1 000 | 10 | 30 |
| PRO | $49 / month | 100 | 100 000 | 200 | 400 |
| ENTERPRISE | contact us | unlimited | unlimited | unlimited | 5 000 |
```

AC4: the code defaults equal the ADR table, and the guard test proves it. The conftest hides the pass count on this repo, so the exit code is the evidence.

```bash
cd apps/backend && PYTHONPATH=. uv run pytest tests/test_billing/test_plan_limits_are_the_product_values.py -q -p no:cacheprovider 2>&1 | grep -E 'passed|failed|error'; echo exit=${PIPESTATUS[0]}
```

```output
exit=0
```

The same numbers read straight from the module: the limits as the running app resolves them.

```bash
cd apps/backend && uv run python -c "from app.billing.plans import PLAN_LIMITS
for t, l in PLAN_LIMITS.items(): print(t.name, {m: getattr(l, m) for m in ('training_runs','predictions','uploads','ai_calls')})"
```

```output
FREE {'training_runs': 5, 'predictions': 1000, 'uploads': 10, 'ai_calls': 30}
PRO {'training_runs': 100, 'predictions': 100000, 'uploads': 200, 'ai_calls': 400}
ENTERPRISE {'training_runs': -1, 'predictions': -1, 'uploads': -1, 'ai_calls': 5000}
```

Mutation check: change one code default and the ADR guard fails naming the metric, then revert.

```bash
cd apps/backend && sed -i 's/"PLAN_FREE_AI_CALLS", 30)/"PLAN_FREE_AI_CALLS", 31)/' app/billing/plans.py; PYTHONPATH=. uv run pytest tests/test_billing/test_plan_limits_are_the_product_values.py::test_code_defaults_match_adr_003 -q -p no:cacheprovider 2>&1 | grep -E '^E ' | head -2; sed -i 's/"PLAN_FREE_AI_CALLS", 31)/"PLAN_FREE_AI_CALLS", 30)/' app/billing/plans.py && git diff --quiet app/billing/plans.py && echo reverted-clean
```

```output
E   AssertionError: FREE.ai_calls: plans.py default differs from ADR-003; change the ADR and the code together (#474).
E   assert 31 == 30
reverted-clean
```

AC4 (deployed == defaults): no deploy surface carries a PLAN_* override. The e2e runner is the one sanctioned exception (#550).

```bash
grep -rnE 'PLAN_(FREE|PRO|ENTERPRISE)_[A-Z_]+\s*[:=]' docker-compose*.yml .github/workflows .env* apps/backend/.env* scripts 2>/dev/null || echo 'no overrides in deploy surfaces'; grep -c 'PLAN_FREE' apps/frontend/test-e2e.sh
```

```output
no overrides in deploy surfaces
4
```

A note on the mutation step: an edit and its revert inside the same second leave a stale .pyc (same mtime, same size), so the file is touched before reading it again.

```bash
touch apps/backend/app/billing/plans.py && cd apps/backend && uv run python -c "from app.billing.plans import PLAN_LIMITS
from app.models.subscription import PlanTier
print('FREE ai_calls after revert:', PLAN_LIMITS[PlanTier.FREE].ai_calls)"
```

```output
FREE ai_calls after revert: 30
```

AC6: the FREE worst case, priced at the gpt-4 unit costs in ADR-003, stays within the ≈ \$5/month acquisition budget.

```bash
cd apps/backend && uv run python -c "from app.billing.plans import PLAN_LIMITS
from app.models.subscription import PlanTier
c={'ai_calls':0.12,'uploads':0.12,'training_runs':0.04,'predictions':0.00001}
f=PLAN_LIMITS[PlanTier.FREE]
print('FREE worst case: $%.2f/month' % sum(getattr(f,m)*u for m,u in c.items()))"
```

```output
FREE worst case: $5.01/month
```

Model default: every call site reads openai_model(); blank env counts as unset (staging passes optional vars as empty strings), and no gpt-* literal survives outside the factory.

```bash
cd apps/backend && OPENAI_MODEL= uv run python -c "import os
from app.utils.openai_client import openai_model
print('blank ->', openai_model()); os.environ['OPENAI_MODEL']='gpt-4'; print('override ->', openai_model())"; grep -rnE "['\"]gpt-" app --include=*.py | grep -v utils/openai_client.py || echo 'no model literals outside app/utils/openai_client.py'
```

```output
blank -> gpt-4o-mini
override -> gpt-4
no model literals outside app/utils/openai_client.py
```

AC3: ENTERPRISE is sales-led. The billing page renders a mailto Contact us link on paid-enabled deployments and never an Enterprise checkout button; on the Enterprise tier itself the link is absent. The rendered assertions, verbatim from the suite:

```bash
cd apps/frontend && npx jest __tests__/app/settings/billing.page.test.tsx --verbose 2>&1 | grep -E '✓|✕|Tests:'
```

```output
Tests:       11 passed, 11 total
```

```bash
grep -n -A4 'sales-led (#474' apps/frontend/app/settings/billing/page.tsx
```

```output
214:      {/* ENTERPRISE is sales-led (#474 AC3): a contact link, never a dead tier. */}
215-      {status.configured && status.tier !== 'enterprise' && (
216-        <p className="text-sm text-muted-foreground">
217-          Need unlimited training, predictions and uploads?{' '}
218-          <a
```

AC2 (operator): the Stripe Price objects are created in the dashboard; the steps are in ADR-003 and staging provisioning is #598. Nothing in code blocks it: the checkout route already maps PRO/ENTERPRISE to the two env vars.

```bash
grep -n 'STRIPE_PRICE_' apps/backend/app/api/routes/billing.py docker-compose.staging.yml | head -6
```

```output
apps/backend/app/api/routes/billing.py:118:        PlanTier.PRO: "STRIPE_PRICE_PRO",
apps/backend/app/api/routes/billing.py:119:        PlanTier.ENTERPRISE: "STRIPE_PRICE_ENTERPRISE",
docker-compose.staging.yml:120:      STRIPE_PRICE_PRO: ${STRIPE_PRICE_PRO:-}
docker-compose.staging.yml:121:      STRIPE_PRICE_ENTERPRISE: ${STRIPE_PRICE_ENTERPRISE:-}
```

Demo complete: the limits are decided, recorded, guarded against drift, sized against the free-tier budget, and the model default is one constant.
