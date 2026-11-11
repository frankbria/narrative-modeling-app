# ADR-004: Transactional email — Resend, job notifications, and who sends dunning mail

- **Status:** Accepted (the dunning section is the standing default; see "Open to the owner")
- **Date:** 2026-11-11
- **Implements:** [#494](https://github.com/frankbria/narrative-modeling-app/issues/494)

## Context

Training and batch prediction run in the background, sometimes for minutes, and nothing
told the account when they ended. The product sent no email of any kind. A failed job was
learned of by looking, or not at all.

Stripe sends payment receipts itself. Whether it is also the one to chase a failed
renewal had never been written down, and a `PAST_DUE` subscription stays entitled for
`DUNNING_GRACE` (30 days, `app/models/subscription.py`) on the assumption that someone is
telling the customer.

## Decisions

### 1. Provider: Resend

Decided by the owner on #494 (2026-11-09). The backend calls Resend's HTTP API
(`POST https://api.resend.com/emails`) with the `httpx` it already depends on; no SDK is
added. All of it is in `app/services/email_service.py`.

### 2. Sending is optional, and configured lazily

`RESEND_API_KEY` and `EMAIL_FROM` are read on each send, and blank means unset. With
either missing the app runs exactly as before and sends nothing: a build with no secrets,
the test suite and a local stack need no provider. The startup log states which case a
process is in (`Email: …`). Compose passes both with `:-`. The sender domain is not
verified yet, so staging stays in the "not sending" state until both are provisioned;
guard them with `:?` once job mail is something customers rely on.

### 3. What is sent, and to whom

One plain-text message when a training or batch prediction job reaches COMPLETED or
FAILED, to the address the account signed in with (read from the NextAuth `users`
collection when the message is sent, stored nowhere else). Sign-in is Google or GitHub
only, so that address is one the provider has verified; a sign-in method that accepts an
unverified address would need its own check before mail is sent to it. A cancelled job sends nothing:
the person who cancelled it already knows. A job removed by an erasure sends nothing.

The message holds the job's label (the model name or dataset filename for training, the
record count for a batch), the stored failure reason, the app's address and how to stop
the mails. The failure reason is the one already shown in the app, from
`user_safe_failure_reason`, never exception text. No dataset content, storage location or
token is in it.

Three places end a job and all three notify: the training task, the batch run, and the
stale-job reaper. Each ending carries an idempotency key, so the task and the reaper
reporting the same failure send one message. Resend remembers a key for 24 hours, which
is far longer than the gap between two reports of one ending.

### 4. A notification cannot change a job

`job_notifications.job_finished` and `batch_job_finished` never raise, and they run after
the job's terminal state is written (for a batch job, after the run and outside its wall
clock, so a deadline cannot cancel the mail). A provider outage, a bad key or an unreachable
database costs the mail and nothing else. Failures are logged by exception class only,
because provider error bodies can quote the recipient.

### 5. Opt-out, default on

`NotificationPreference` holds one row per account that has chosen; no row means on. The
switch is on the settings page (`GET`/`PUT /api/v1/users/me/notification-preferences`).
Account erasure keeps the row: it holds no personal data, and deleting it would silently
opt the account back in.

### 6. Dunning mail stays with Stripe

Stripe's own emails (failed-payment and card-expiry notices, with its Smart Retries) are
the dunning channel. SheetPredict sends none. Stripe already holds the billing address
and the retry schedule and links to its hosted page for updating a card, and a second
sender would have to track the same schedule to avoid contradicting it.

This needs the customer emails switched on in the Stripe account's billing settings; that
is part of the go-live checklist in #771, not code.

## Consequences

- Resend is a sub-processor: it receives the address and the message. It is listed in
  `SUB_PROCESSORS` (`apps/frontend/lib/legal/company.ts`) and the Privacy Policy says what
  the address is used for.
- A new kind of message goes through `email_service.send` and decides its own opt-out.
  Nothing else sends mail.
- Messages are sent inline from the worker that ended the job, with a 10-second timeout
  and no retry. A message lost to a provider outage is not sent later.
- The link in a message is `PUBLIC_API_URL` without its `/api/v1`, which assumes the app
  and the API share an origin. They do on every deployment today.

## Open to the owner

- **Dunning (decision 6)** was recorded by the implementing agent as the existing
  behaviour, not chosen by the owner. If SheetPredict should send its own failed-payment
  mail, that is a new message on `invoice.payment_failed` in the webhook.
- Not built here, from the wider list on #494: a welcome message, an 80 % quota warning,
  and institution-email verification for an academic tier (#796).
