// frontend/app/lib/db.ts

// This approach is taken from https://github.com/vercel/next.js/tree/canary/examples/with-mongodb
import { MongoClient, ServerApiVersion } from "mongodb"

// Allow missing MONGODB_URI in test/CI environments with SKIP_AUTH
const skipAuth = process.env.SKIP_AUTH === 'true' || process.env.CI === 'true'

if (!process.env.MONGODB_URI && !skipAuth) {
  throw new Error('Invalid/Missing environment variable: "MONGODB_URI"')
}

// Use a mock URI for test environments when auth is skipped
const uri = process.env.MONGODB_URI || 'mongodb://localhost:27017/test'
const options = {
  serverApi: {
    version: ServerApiVersion.v1,
    strict: true,
    deprecationErrors: true,
  },
}

let client: MongoClient

if (process.env.NODE_ENV === "development") {
  // In development mode, use a global variable so that the value
  // is preserved across module reloads caused by HMR (Hot Module Replacement).
  let globalWithMongo = global as typeof globalThis & {
    _mongoClient?: MongoClient
  }

  if (!globalWithMongo._mongoClient) {
    globalWithMongo._mongoClient = skipAuth
      ? {} as MongoClient  // Mock client when auth is skipped
      : new MongoClient(uri, options)
  }
  client = globalWithMongo._mongoClient
} else {
  // In production mode, it's best to not use a global variable.
  client = skipAuth
    ? {} as MongoClient  // Mock client when auth is skipped
    : new MongoClient(uri, options)
}

// Export a module-scoped MongoClient. By doing this in a
// separate module, the client can be shared across functions.
export default client
