// frontend/app/lib/db.ts

// This approach is taken from https://github.com/vercel/next.js/tree/canary/examples/with-mongodb
import { MongoClient, ServerApiVersion } from "mongodb"

// Allow missing MONGODB_URI in CI environments only
const isCI = process.env.CI === 'true'

if (!process.env.MONGODB_URI && !isCI) {
  throw new Error('Invalid/Missing environment variable: "MONGODB_URI"')
}

// Use a mock URI for CI environments
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
  const globalWithMongo = global as typeof globalThis & {
    _mongoClient?: MongoClient
  }

  if (!globalWithMongo._mongoClient) {
    globalWithMongo._mongoClient = isCI
      ? {} as MongoClient  // Mock client in CI
      : new MongoClient(uri, options)
  }
  client = globalWithMongo._mongoClient
} else {
  // In production mode, it's best to not use a global variable.
  client = isCI
    ? {} as MongoClient  // Mock client in CI
    : new MongoClient(uri, options)
}

// Export a module-scoped MongoClient. By doing this in a
// separate module, the client can be shared across functions.
export default client
