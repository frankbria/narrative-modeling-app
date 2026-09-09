# Issue #457 — the Stripe configuration reaches the staging backend

Every acceptance criterion, with the outcome rather than the exit code. AC5 is
the exception and is stated as such at the bottom: it needs real Stripe test keys
written into `.env.staging` on the box, which is an operator step.

## AC1 — the four variables reach the backend service

`docker compose config` resolves the real compose file against a fully populated
env file. This is what the container is actually created with:

```
$ docker compose -f docker-compose.staging.yml --env-file .env.staging config \
    | sed -n '/^  backend:/,/^  frontend:/p' | grep STRIPE_
      STRIPE_PRICE_ENTERPRISE: price_DEMO_ENTERPRISE
      STRIPE_PRICE_PRO: price_DEMO_PRO
      STRIPE_SECRET_KEY: sk_test_DEMO_KEY
      STRIPE_WEBHOOK_SECRET: whsec_DEMO_SECRET
```

Before this change the same command printed nothing — the issue's own evidence
from inside the running container (`printenv | grep STRIPE_` → empty) is the
deployed form of that.

> `docker compose up -d` recreates a container whose resolved config changed, so
> a normal deploy picks these up. A bare `docker restart` would not — compose
> injects environment at container **creation**.

## AC2 — optional (`${VAR:-}`), not required (`${VAR:?}`)

Chosen deliberately. `scripts/deploy/preflight_staging_env.sh` derives its
required set from the `${VAR:?}` guards in the compose file, and `deploy.yml`
runs it before `docker compose up`. Guarding a key that is not yet in
`.env.staging` would fail the next deploy and take staging down — which the issue
explicitly asks not to do until real values exist.

With the Stripe variables **absent** from the env file, the deploy is unaffected:

```
$ grep -v '^STRIPE_' .env.staging > .env.nostripe
$ bash scripts/deploy/preflight_staging_env.sh docker-compose.staging.yml .env.nostripe
preflight: OK — all required variables present in .env.nostripe

$ docker compose ... --env-file .env.nostripe config | grep STRIPE_
      STRIPE_PRICE_ENTERPRISE: ""
      STRIPE_PRICE_PRO: ""
      STRIPE_SECRET_KEY: ""
      STRIPE_WEBHOOK_SECRET: ""
```

and it still fails closed on a variable that *is* required:

```
$ grep -v '^NEXTAUTH_SECRET=' .env.staging > .env.broken
$ bash scripts/deploy/preflight_staging_env.sh docker-compose.staging.yml .env.broken
preflight: .env.broken is missing 1 required variable(s):
  - NEXTAUTH_SECRET
(exit 1)
```

**Switching them on later is one line each** — `:-` becomes `:?` in
`docker-compose.staging.yml`, and `test_stripe_variables_do_not_block_the_deploy_before_keys_exist`
is written to be updated in the same commit.

### A bug this demo found

The first version of that compose comment contained a literal `${VAR:?}` while
explaining the pattern. `preflight_staging_env.sh` grepped the raw file with no
comment-awareness, so it immediately began demanding a variable literally named
`VAR`:

```
preflight: .env.staging is missing 1 required variable(s):
  - VAR
```

That would have failed the very next deploy, with an error naming a variable that
appears nowhere in the file. Fixed in the script (comments are stripped before
the guards are derived) rather than by rewording the comment — any compose file
documenting the pattern hits it. Covered by the script's `--self-check`, which CI
now runs.

## AC3 — both env examples document all four

`.env.staging.example` and `apps/backend/.env.example` each carry a billing
section naming every variable, what its absence costs, and where the webhook URL
goes (`/webhooks/stripe/webhook`, outside `/api/v1` — #367/#456).
`test_staging_billing_env.py` parses the real files, so deleting one fails the
build.

## AC4 — `PLAN_*` is not passed; `plans.py` holds the intended limits

Stated rather than implemented, which the AC allows. The defaults are
placeholders (ADR-002, #474), and the fix for that is real numbers in
`app/billing/plans.py` — one place that applies to every environment. Twelve env
passthroughs would add twelve ways for this box, whose config is partly
hand-maintained (#594), to disagree silently with the code.

## Behaviour: what the four variables actually buy

The real app against real Mongo. No Stripe network call (the SDK call is stubbed
at that one boundary), but the webhook signature is a real HMAC computed the way
Stripe computes it, and the `Subscription` is read back out of the database.

```
========================================================================
STATE 1 — what staging is today: no STRIPE_* in the container
========================================================================
startup log  : Stripe is not configured (unset: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET,
               STRIPE_PRICE_PRO, STRIPE_PRICE_ENTERPRISE). POST /billing/checkout answers
               503, webhooks are rejected, and every tenant stays on FREE limits.
GET  /billing/status           -> 200 configured = False
POST /billing/checkout         -> 503
POST /webhooks/stripe/webhook  -> 400 {'detail': 'signature verification failed'}
Subscription rows for the tenant: 0

========================================================================
STATE 2 — the dangerous middle: secret key set, webhook secret NOT
========================================================================
startup log  : Stripe is only PARTIALLY configured (unset: STRIPE_WEBHOOK_SECRET).
               Checkout is live and can charge a customer, but the events that would
               entitle a paying customer are rejected.
GET  /billing/status           -> 200 configured = True   <-- and checkout really does sell
POST /webhooks/stripe/webhook  -> 400                     <-- money in, nobody entitled
Subscription rows for the tenant: 0

========================================================================
STATE 3 — all four set, i.e. what this PR lets .env.staging deliver
========================================================================
startup log  : (nothing — clean)
GET  /billing/status           -> 200 configured = True
POST /billing/checkout         -> 200 {'url': 'https://checkout.stripe.com/c/pay/cs_test_demo'}
   (resolved price='price_DEMO_PRO' from STRIPE_PRICE_PRO)
POST /webhooks/stripe/webhook                          -> 200 {'received': True, 'handled': True}
POST /webhooks/stripe/webhook (subscription.updated)   -> 200 {'received': True, 'handled': True}

Subscription in Mongo: tier=pro status=active effective_tier=pro stripe_customer_id=cus_demo
GET  /billing/status  -> tier=pro status=active limits={'training_runs': 200,
                                                        'predictions': 100000, 'uploads': 500}
```

STATE 2 is why the startup line exists at all. `is_configured()` is one boolean
about one key and reports `true` there, while the customer is charged and never
entitled — strictly worse than no Stripe. It was also the state the first version
of the warning described incorrectly ("checkout answers 503"), caught by
`codex review`.

## AC5 — NOT closed by this PR

`GET /api/v1/billing/status` returning `configured: true` **on staging**, and a
test-mode checkout producing an entitled `Subscription` there, needs two things
this PR cannot supply: real Stripe test keys written into `.env.staging` on the
box, and a deploy. Everything above is the code half.

Operator steps, in order:

1. Stripe dashboard → Developers → API keys → copy the **test** secret key.
2. Stripe dashboard → Developers → Webhooks → add endpoint
   `https://dev.briaanalytics.com/webhooks/stripe/webhook`, subscribing to at
   least `checkout.session.completed`, `customer.subscription.updated` and
   `customer.subscription.deleted`. Copy the signing secret.
3. Product catalogue → copy the **`price_...`** ids for pro and enterprise (not
   the `prod_...` ids).
4. Append all four to `.env.staging` on the box (see `.env.staging.example`).
5. `docker compose -f docker-compose.staging.yml --env-file .env.staging up -d`
   — `up`, not `restart`; compose injects env at container creation.
6. Confirm: `docker logs narrative-staging-backend | grep 'Billing:'` should say
   `Stripe configured`. Anything else names exactly which variable is still unset.
7. Confirm end to end: `GET /api/v1/billing/status` → `"configured": true`, then
   a test-mode checkout, then check the `Subscription` row is `active`.

Tracked as its own issue so it is not lost when this one closes.
