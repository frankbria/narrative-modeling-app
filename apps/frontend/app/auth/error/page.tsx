// app/auth/error/page.tsx
'use client';

import { useSearchParams } from 'next/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import Link from 'next/link';
import { AlertCircle } from 'lucide-react';

export default function AuthErrorPage() {
  const searchParams = useSearchParams();
  const error = searchParams.get('error');

  // Where rejected users request an invite. Configurable per deploy; falls back
  // to a mailto so the "request access" path always works (issue #261).
  const requestAccessUrl =
    process.env.NEXT_PUBLIC_INVITE_REQUEST_URL ?? 'mailto:beta@narrativeml.com?subject=Beta%20access%20request';

  const errorMessages: Record<string, string> = {
    Configuration: 'There is a problem with the server configuration.',
    AccessDenied:
      "This is a private, invite-only beta. The email you used isn't on the invite list yet.",
    Verification: 'The verification token has expired or has already been used.',
    OAuthSignin: 'Error in constructing an authorization URL.',
    OAuthCallback: 'Error in handling the response from OAuth provider.',
    OAuthCreateAccount: 'Could not create OAuth provider user in the database.',
    EmailCreateAccount: 'Could not create email provider user in the database.',
    Callback: 'Error in the OAuth callback handler route.',
    OAuthAccountNotLinked: 'This account is already associated with another user.',
    EmailSignin: 'Check if there is an issue with the email provider.',
    CredentialsSignin: 'Sign in failed. Check the details you provided are correct.',
    SessionRequired: 'Please sign in to access this page.',
    Default: 'An unexpected error occurred.',
  };

  const errorMessage = error ? (errorMessages[error] ?? errorMessages.Default) : errorMessages.Default;

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="mx-auto mb-4 w-12 h-12 rounded-full bg-red-100 flex items-center justify-center">
            <AlertCircle className="w-6 h-6 text-red-600" />
          </div>
          <CardTitle className="text-2xl font-bold">
            {error === 'AccessDenied' ? 'Invite Required' : 'Authentication Error'}
          </CardTitle>
          <CardDescription className="text-red-600">
            {errorMessage}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* asChild renders a single <a>/<Link> styled as a button — nesting a
              real <button> inside an anchor is invalid HTML and breaks a11y. */}
          {error === 'AccessDenied' && (
            <Button asChild className="w-full">
              <a href={requestAccessUrl}>Request access</a>
            </Button>
          )}
          <Button
            asChild
            variant={error === 'AccessDenied' ? 'outline' : 'default'}
            className="w-full"
          >
            <Link href="/auth/signin">Back to Sign In</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}