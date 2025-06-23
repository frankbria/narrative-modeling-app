'use client';

import { signIn } from "next-auth/react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Mail } from "lucide-react";
import { SiGithub, SiGoogle } from "@icons-pack/react-simple-icons";
import Link from "next/link";

export default function SignInPage() {
  const [email, setEmail] = useState('dev@example.com');
  const isDevelopment = process.env.NODE_ENV === 'development';
  const skipAuth = process.env.NEXT_PUBLIC_SKIP_AUTH === 'true';
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl font-bold">Sign In</CardTitle>
          <CardDescription>
            Choose your preferred sign-in method to access the Narrative Modeling App
            {`isDevelopment Mode: ${isDevelopment ? 'Enabled' : 'Disabled'}`}<br />
            {`skipAuth: ${skipAuth ? 'Enabled' : 'Disabled'}`}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {isDevelopment && skipAuth && (
            <>
              <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-md">
                <p className="text-sm text-yellow-800 font-medium">Development Mode</p>
                <p className="text-xs text-yellow-600 mt-1">Authentication is bypassed. Enter any email to continue.</p>
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="dev@example.com"
                />
              </div>
              
              <Button
                onClick={() => signIn('credentials', { 
                  email, 
                  callbackUrl: '/' 
                })}
                className="w-full flex items-center justify-center gap-2"
                variant="default"
              >
                <Mail className="w-5 h-5" />
                Continue with Development Account
              </Button>
              
              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <span className="w-full border-t" />
                </div>
                <div className="relative flex justify-center text-xs uppercase">
                  <span className="bg-white px-2 text-muted-foreground">Or use OAuth</span>
                </div>
              </div>
            </>
          )}
          
          <Button
            onClick={() => signIn('google', { callbackUrl: '/' })}
            className="w-full flex items-center justify-center gap-2"
            variant="outline"
          >
            <SiGoogle title="Google" className="w-5 h-5" />
            Continue with Google
          </Button>
          
          <Button
            onClick={() => signIn('github', { callbackUrl: '/' })}
            className="w-full flex items-center justify-center gap-2"
            variant="outline"
          >
            <SiGithub title="GitHub" className="w-5 h-5" />
            Continue with GitHub
          </Button>
          
          <div className="text-center pt-4">
            <p className="text-sm text-muted-foreground">
              Don&apos;t have an account?{' '}
              <Link href="/auth/new-user" className="text-primary hover:underline">
                Sign Up Here
              </Link>
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}