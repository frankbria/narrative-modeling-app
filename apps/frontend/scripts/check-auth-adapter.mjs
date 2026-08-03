// Does @auth/mongodb-adapter actually work on the installed mongodb driver? (#344)
//
// WHY THIS EXISTS. The adapter declares `peerDependencies: { mongodb: "^6" }`, and
// we run mongodb 7 with an `overrides` entry that forces a single copy into the
// tree. That override is the whole reason the 6 -> 7 bump was possible — the peer
// range turned out to be a conservative maintainer claim, not a real
// incompatibility, and every adapter method NextAuth uses passes against a real
// mongod on 7.x.
//
// The cost of overriding a peer range is that npm will no longer warn us when the
// claim becomes true. This script is what replaces that warning: it exercises the
// adapter's real methods against a real database, so a future driver or adapter
// bump that genuinely breaks fails here loudly instead of in production sign-in.
//
// Cannot be a jest test: the adapter is ESM-only (an `import` condition and no
// `require`), and next/jest's own transformIgnorePatterns matches all of
// node_modules, so no moduleNameMapper or transform override in our config can
// reach it. A standalone node script is the shortest thing that actually runs.
//
// Usage: npm run check:adapter    (needs mongod on localhost:27017)
import { MongoClient, ServerApiVersion } from 'mongodb'
import { MongoDBAdapter } from '@auth/mongodb-adapter'

const DB = 'nma_adapter_compat_probe'
const URI = process.env.TEST_MONGODB_URI ?? 'mongodb://localhost:27017'
const client = new MongoClient(URI, {
  serverApi: { version: ServerApiVersion.v1, strict: false, deprecationErrors: true },
  serverSelectionTimeoutMS: 3000,
})

const ok = (label, cond) => {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${label}`)
  if (!cond) process.exitCode = 1
}

await client.connect()
console.log('driver:', (await import('mongodb/package.json', { with: { type: 'json' } })).default.version)
console.log('adapter peer range: mongodb ^6 (overridden deliberately — see above)')
console.log('')

try {
  const adapter = MongoDBAdapter(client, { databaseName: DB })
  const email = `probe-${Date.now()}@example.com`

  const user = await adapter.createUser({ id: 'x', email, emailVerified: null, name: 'Probe' })
  ok('createUser returns a 24-hex id', /^[0-9a-f]{24}$/.test(user.id))

  const fetched = await adapter.getUser(user.id)
  ok('getUser round-trips', fetched?.email === email)

  const byEmail = await adapter.getUserByEmail(email)
  ok('getUserByEmail round-trips', byEmail?.id === user.id)

  await adapter.linkAccount({
    userId: user.id, type: 'oauth', provider: 'github',
    providerAccountId: 'gh-123', access_token: 'tok',
  })
  const byAccount = await adapter.getUserByAccount({ provider: 'github', providerAccountId: 'gh-123' })
  ok('getUserByAccount (every repeat sign-in)', byAccount?.id === user.id)

  const updated = await adapter.updateUser({ id: user.id, name: 'Renamed' })
  ok('updateUser', updated.name === 'Renamed')

  await adapter.createSession({ sessionToken: 't1', userId: user.id, expires: new Date(Date.now() + 60000) })
  const sess = await adapter.getSessionAndUser('t1')
  ok('getSessionAndUser (every authed request)', sess?.user?.id === user.id)

  await adapter.updateSession({ sessionToken: 't1', expires: new Date(Date.now() + 120000) })
  ok('updateSession', !!(await adapter.getSessionAndUser('t1')))

  await adapter.deleteSession('t1')
  ok('deleteSession', (await adapter.getSessionAndUser('t1')) === null)

  // BSON handling is the thing a driver major is most likely to move.
  const raw = await client.db(DB).collection('users').findOne({ email })
  ok('_id stored as a real ObjectId', raw?._id?.toHexString?.() === user.id)

  await adapter.unlinkAccount({ provider: 'github', providerAccountId: 'gh-123' })
  ok('unlinkAccount', (await adapter.getUserByAccount({ provider: 'github', providerAccountId: 'gh-123' })) === null)

  await adapter.deleteUser(user.id)
  ok('deleteUser', (await adapter.getUser(user.id)) === null)
} finally {
  // Drop and disconnect even when an assertion throws. In CI the mongod is an
  // ephemeral service container so it would not matter, but the script accepts
  // TEST_MONGODB_URI precisely so it can be pointed at a long-lived instance —
  // and there a failed run would otherwise leave this database behind forever.
  await client.db(DB).dropDatabase().catch(() => {})
  await client.close().catch(() => {})
}
console.log(process.exitCode ? '\nRESULT: adapter is NOT compatible' : '\nRESULT: adapter works on this driver')
