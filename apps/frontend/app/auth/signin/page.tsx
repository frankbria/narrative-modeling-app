// frontend/app/auth/signin/page.tsx

'use client';

import { signIn, useSession } from "next-auth/react";
import { useState, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Mail, Loader2 } from "lucide-react";
import { SiGithub, SiGoogle } from "@icons-pack/react-simple-icons";

export default function SignInPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState('test@narrativeml.com');
  const [password, setPassword] = useState('test-password-123');
  const isDevelopment = process.env.NODE_ENV === 'development';

  // Get callback URL from search params or default to /upload
  const callbackUrl = searchParams.get('callbackUrl') || '/upload';
  
  useEffect(() => {
    // If already authenticated, redirect to callback URL
    if (status === 'authenticated') {
      router.push(callbackUrl);
    }
  }, [status, router, callbackUrl]);
  
  // Show loading while checking auth status
  if (status === 'loading') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <div className="flex items-center space-x-2">
          <Loader2 className="h-6 w-6 animate-spin" />
          <span>Checking authentication...</span>
        </div>
      </div>
    );
  }
  
  // If authenticated, show loading while redirecting
  if (status === 'authenticated') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <div className="flex items-center space-x-2">
          <Loader2 className="h-6 w-6 animate-spin" />
          <span>Redirecting to application...</span>
        </div>
      </div>
    );
  }
  
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl font-bold">Sign In</CardTitle>
          <CardDescription>
            Choose your preferred sign-in method to access the Narrative Modeling App
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {isDevelopment && (
            <>
              <div className="p-4 bg-blue-50 border border-blue-200 rounded-md">
                <p className="text-sm text-blue-800 font-medium">Test User Login</p>
                <p className="text-xs text-blue-600 mt-1">Use test credentials for E2E testing and development</p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="test@narrativeml.com"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="test-password-123"
                />
              </div>

              <Button
                onClick={() => signIn('credentials', {
                  email,
                  password,
                  callbackUrl
                })}
                className="w-full flex items-center justify-center gap-2"
                variant="default"
              >
                <Mail className="w-5 h-5" />
                Sign In with Test User
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
            onClick={() => signIn('google', { callbackUrl })}
            className="w-full flex items-center justify-center gap-2"
            variant="outline"
          >
            <SiGoogle title="Google" className="w-5 h-5" />
            Continue with Google
          </Button>
          
          <Button
            onClick={() => signIn('github', { callbackUrl })}
            className="w-full flex items-center justify-center gap-2"
            variant="outline"
          >
            <SiGithub title="GitHub" className="w-5 h-5" />
            Continue with GitHub
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}