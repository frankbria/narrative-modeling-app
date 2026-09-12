import { DefaultSession } from "next-auth"

declare module "next-auth" {
  interface Session {
    user: {
      id: string
    } & DefaultSession["user"]
    /** Backend-verifiable HS256 JWT (sub=userId) for API Authorization. */
    apiToken?: string
    /** Email is on ADMIN_EMAILS (#477); computed server-side, UX-only. */
    isAdmin?: boolean
  }
}
