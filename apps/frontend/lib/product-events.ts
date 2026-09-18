import type { MongoClient } from 'mongodb'

/**
 * Record `account_created` for the funnel (#769) when NextAuth creates a user.
 *
 * Written straight into the backend's `product_events` collection through the
 * adapter's own client — the one place that knows a user was just created. The
 * document shape mirrors `apps/backend/app/models/product_event.py`; `dedupe_key`
 * makes a repeat a duplicate-key no-op there. Never throws: signup must not fail
 * because telemetry did.
 */
export async function recordAccountCreated(client: MongoClient, userId: string): Promise<void> {
  try {
    await client
      .db(process.env.MONGODB_DB)
      .collection('product_events')
      .insertOne({
        user_id: userId,
        event: 'account_created',
        timestamp: new Date(),
        properties: {},
        dedupe_key: 'account_created',
      })
  } catch (err) {
    console.error('[auth] could not record account_created:', err)
  }
}
