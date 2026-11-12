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
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const checked = chosen ?? stored.data?.job_emails ?? true;

  // One save at a time: two in flight can land in either order, and the switch would
  // then show whichever was clicked last while the server holds whichever arrived last.
  async function choose(next: boolean) {
    setSaving(true);
    setChosen(next);
    setSaveError(null);
    try {
      await notificationPreferencesApi.setJobEmails(next);
    } catch {
      setChosen(checked);
      setSaveError(SAVE_FAILED);
    }
    setSaving(false);
  }

  return {
    checked,
    choose,
    locked: saving || stored.data === undefined,
    problem: stored.error ?? saveError,
  };
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
            disabled={jobEmails.locked}
            onCheckedChange={jobEmails.choose}
          />
        </div>
        <p role="alert" hidden={!jobEmails.problem} className="text-sm text-destructive">
          {jobEmails.problem}
        </p>
      </CardContent>
    </Card>
  );
}
