/**
 * Right-to-erasure response types (#482), mirroring the backend
 * `app/schemas/erasure.py` (DeletionManifest / EraseResponse). Change both
 * together — see CLAUDE.md "Schema ↔ type mirrors".
 */

/** What an erasure actually removed — the honest record of a best-effort cascade. */
export interface DeletionManifest {
  target_type: string;
  target_id: string;
  subject_user_id: string;
  erasure_id: string | null;
  documents_deleted: Record<string, number>;
  s3_objects_deleted: string[];
  redis_keys_evicted: number;
  /** Non-empty => an incomplete erasure that needs an idempotent re-run. */
  failures: string[];
  /** Informational context, e.g. retained billing state. */
  notes: string[];
  idempotent_noop: boolean;
  completed_at: string;
  total_documents_deleted: number;
  /** "completed" | "completed_with_residuals". */
  status: string;
}

export interface EraseResponse {
  erasure_id: string | null;
  status: string;
  manifest: DeletionManifest;
}

/** True when the cascade reported at least one failure — do NOT report success. */
export function hasResiduals(manifest: DeletionManifest): boolean {
  return manifest.failures.length > 0 || manifest.status === 'completed_with_residuals';
}
