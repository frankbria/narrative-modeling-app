/**
 * account_created funnel event (#769 AC1).
 *
 * The document shape is a contract with the backend's ProductEvent model
 * (apps/backend/app/models/product_event.py): the backend reads, counts and erases
 * these rows, so a renamed field here silently drops every signup from the funnel.
 */
import type { MongoClient } from 'mongodb'
import { recordAccountCreated } from '@/lib/product-events'

function fakeClient(insertOne: jest.Mock) {
  const db = jest.fn(() => ({ collection: jest.fn((name: string) => ({ name, insertOne })) }))
  return { client: { db } as unknown as MongoClient, db }
}

describe('recordAccountCreated', () => {
  const previousDb = process.env.MONGODB_DB
  beforeEach(() => {
    process.env.MONGODB_DB = 'narrative'
  })
  afterAll(() => {
    process.env.MONGODB_DB = previousDb
  })

  it('writes the backend ProductEvent shape into product_events', async () => {
    const insertOne = jest.fn().mockResolvedValue({})
    const { client, db } = fakeClient(insertOne)

    await recordAccountCreated(client, 'user-1')

    expect(db).toHaveBeenCalledWith('narrative')
    const collection = (db.mock.results[0].value as { collection: jest.Mock }).collection
    expect(collection).toHaveBeenCalledWith('product_events')
    const doc = insertOne.mock.calls[0][0]
    expect(doc).toEqual({
      user_id: 'user-1',
      event: 'account_created',
      timestamp: expect.any(Date),
      properties: {},
      dedupe_key: 'account_created',
    })
  })

  it('never fails signup when the write fails', async () => {
    const spy = jest.spyOn(console, 'error').mockImplementation(() => {})
    const { client } = fakeClient(jest.fn().mockRejectedValue(new Error('mongo down')))

    await expect(recordAccountCreated(client, 'user-1')).resolves.toBeUndefined()
    expect(spy).toHaveBeenCalled()
    spy.mockRestore()
  })
})

// auth.ts wiring: NextAuth's events.createUser must record the event.
jest.mock('@auth/mongodb-adapter', () => ({ MongoDBAdapter: jest.fn(() => ({})) }), {
  virtual: true,
})
jest.mock('next-auth', () => ({
  __esModule: true,
  default: jest.fn(() => ({ handlers: {}, signIn: jest.fn(), signOut: jest.fn(), auth: jest.fn() })),
}))
const provider = { __esModule: true, default: jest.fn(() => ({ id: 'stub' })) }
jest.mock('next-auth/providers/google', () => provider, { virtual: true })
jest.mock('next-auth/providers/github', () => provider, { virtual: true })
jest.mock('next-auth/providers/credentials', () => provider, { virtual: true })
jest.mock('@/lib/db', () => ({ __esModule: true, default: { adapterClient: true } }))

describe('auth.ts createUser event', () => {
  it('records account_created through the adapter client', async () => {
    let config: { events?: { createUser?: (m: { user: { id?: string } }) => Promise<void> } } = {}
    const record = jest.fn()
    jest.isolateModules(() => {
      jest.doMock('@/lib/product-events', () => ({ recordAccountCreated: record }))
      const NextAuth = require('next-auth').default as jest.Mock
      NextAuth.mockClear()
      require('@/auth')
      config = NextAuth.mock.calls[0][0]
    })

    await config.events!.createUser!({ user: { id: 'user-9' } })

    expect(record).toHaveBeenCalledWith({ adapterClient: true }, 'user-9')
  })
})
