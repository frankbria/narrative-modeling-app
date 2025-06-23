// frontend/components/sign-in.tsx

"use client"

import { signIn } from "next-auth/react";
import { SiGithub, SiGoogle } from "@icons-pack/react-simple-icons";

export default function SignIn() {
  return (
    <>
      <button onClick={() => signIn("google")}>
        <SiGoogle title="Google" className="w-5 h-5" />
        Sign In with Google
      </button>
      <button onClick={() => signIn("github")}>
        <SiGithub title="GitHub" className="w-5 h-5" />
        Sign In with GitHub
      </button>
    </>
  );
}