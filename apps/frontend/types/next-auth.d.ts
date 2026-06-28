import { DefaultSession } from "next-auth"

declare module "next-auth" {
  interface Session {
    user: {
      id: string
    } & DefaultSession["user"]
    accessToken?: string
    /** Backend-verifiable HS256 JWT (sub=userId) for API Authorization. */
    apiToken?: string
  }
}