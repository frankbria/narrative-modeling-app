'use client';

/**
 * The job-email switch on the settings page (#494): on by default, saved the moment it
 * is flipped. A save that fails puts the switch back, so it never shows a choice the
 * server does not hold.
 */
import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { useAsyncData } from '@/lib/hooks/useAsyncData';
import { notificationPreferencesApi } from '@/lib/services/notificationPreferences';

const LOAD_FAILED = 'We could not load your notification settings. Reload the page to try again.';
const SAVE_FAILED = 'We could not save that change. Try again.';

function useJobEmails() {
  const stored = useAsyncData(() => notificationPreferencesApi.get(), [], { errorMessage: LOAD_FAILED });
  const [chosen, setChosen] = useState<boolean | undefined>(undefined);
  const [saveError, setSaveError] = useState<string | null>(null);
  const checked = chosen ?? stored.data?.job_emails ?? true;

  async function choose(next: boolean) {
    setChosen(next);
    setSaveError(null);
    try {
      await notificationPreferencesApi.setJobEmails(next);
    } catch {
      setChosen(checked);
      setSaveError(SAVE_FAILED);
    }
  }

  return { checked, choose, ready: stored.data !== undefined, problem: stored.error ?? saveError };
}

function Problem({ message }: { message: string | null }) {
  return message && (
    <p role="alert" className="text-sm text-destructive">
      {message}
    </p>
  );
}

export function NotificationPreferences() {
  const jobEmails = useJobEmails();

  return (
    <Card>
      <CardHeader>
        <CardTitle>Notifications</CardTitle>
        <CardDescription>
          Training and batch predictions keep running after you leave the page.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-center justify-between gap-4">
          <Label htmlFor="job-emails">Email me when a job finishes or fails</Label>
          <Switch
            id="job-emails"
            checked={jobEmails.checked}
            disabled={!jobEmails.ready}
            onCheckedChange={jobEmails.choose}
          />
        </div>
        <Problem message={jobEmails.problem} />
      </CardContent>
    </Card>
  );
}
