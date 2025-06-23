// frontend/app/api/auth/[...nextauth]/route.ts

import NextAuth from "next-auth"
import Google from "next-auth/providers/google"
import GitHubProvider from "next-auth/providers/github"
import { MongoDBAdapter } from "@auth/mongodb-adapter"
import client from "@/lib/db"

const handler = NextAuth({
  providers: [Google, GitHubProvider],
  adapter: process.env.SKIP_AUTH === 'true' ? undefined : MongoDBAdapter(client),
  theme: {
    colorScheme: "dark"
  },
  pages: {
    signIn: "/auth/signin",
    signOut: "/auth/signout",
    error: "/auth/error",
    verifyRequest: "/auth/verify-request",
    newUser: "/auth/new-user"
  },
})

export { handler as GET, handler as POST }