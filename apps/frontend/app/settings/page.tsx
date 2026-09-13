'use client';

/**
 * Settings landing page (#482). The sidebar links here; before this it 404'd
 * (#528). Hosts links to the settings sub-pages and the account-level
 * right-to-erasure action — a real, actionable "delete my account and data"
 * (GDPR), which the backend has implemented since #259 but nothing called.
 */
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ErasureConfirmDialog } from '@/components/settings/ErasureConfirmDialog';
import { erasureApi } from '@/lib/services/erasure';

export default function SettingsPage() {
  const router = useRouter();
  const [open, setOpen] = useState(false);

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 space-y-6">
      <h1 className="text-2xl font-semibold text-foreground">Settings</h1>

      <Card>
        <CardHeader>
          <CardTitle>Account</CardTitle>
          <CardDescription>Manage billing and API access.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-3">
          <Link href="/settings/billing">
            <Button variant="outline">Billing &amp; usage</Button>
          </Link>
          <Link href="/settings/api">
            <Button variant="outline">API keys</Button>
          </Link>
        </CardContent>
      </Card>

      <Card className="border-destructive/50">
        <CardHeader>
          <CardTitle className="text-destructive">Danger zone</CardTitle>
          <CardDescription>
            Permanently delete all of your data. This cannot be undone.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button
            variant="destructive"
            onClick={() => setOpen(true)}
            data-testid="delete-account"
          >
            Delete my account data
          </Button>
        </CardContent>
      </Card>

      <ErasureConfirmDialog
        open={open}
        onOpenChange={setOpen}
        title="Delete my account and data"
        confirmWord="DELETE"
        confirmLabel="Delete everything"
        onConfirm={erasureApi.eraseCurrentUser}
        onErased={() => {
          // Data is gone; send them to the dashboard, which will re-render empty.
          router.push('/dashboard');
          router.refresh();
        }}
        body={
          <div className="space-y-2">
            <p>
              This permanently deletes <strong>all datasets, trained models, transformations,
              recipes, feature-store entries, and API keys</strong> you own. Your API keys stop
              working immediately. The cascade runs across stored files (S3) and cached data too.
            </p>
            <p>
              <strong>Retained:</strong> your billing records (subscription and usage) are kept —
              your account stays active and is billed as normal, and the authoritative record lives
              with our payment processor. This deletes your data, not the account itself.
            </p>
          </div>
        }
      />
    </div>
  );
}
