// app/auth/signout/page.tsx
'use client';

import { signOut } from "next-auth/react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function SignOutPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl font-bold">Sign Out</CardTitle>
          <CardDescription>
            Are you sure you want to sign out?
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Button
            onClick={() => signOut({ callbackUrl: '/auth/signin' })}
            className="w-full"
            variant="destructive"
          >
            Yes, Sign Out
          </Button>
          
          <Button
            onClick={() => window.history.back()}
            className="w-full"
            variant="outline"
          >
            Cancel
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}