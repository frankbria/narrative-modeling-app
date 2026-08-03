#!/usr/bin/env bash
#
# Audit the backup posture — S3 and Atlas (#299 / AC3 of #259).
#
# Read-only. Exits non-zero if anything required is missing, so it works as a
# quarterly check (the runbook asks for quarterly drills) and as evidence when
# closing #299: paste its output rather than asserting "backups are on".
#
# Checks what is actually checkable over an API. MFA-delete and the Atlas
# compliance policy are reported when visible and flagged as manual otherwise —
# a verifier that quietly skips what it cannot see is worse than one that says so.
#
# Usage:
#   AWS_BUCKET_NAME=my-bucket ./scripts/ops/verify-backup-config.sh
#
# Atlas checks additionally need (Atlas Admin API, digest auth):
#   ATLAS_PUBLIC_KEY / ATLAS_PRIVATE_KEY / ATLAS_GROUP_ID / ATLAS_CLUSTER_NAME
# Absent, the Atlas section reports SKIP and the S3 checks still run.
#
# Credentials are read from the environment and the ambient AWS CLI config. This
# script never prints a credential, never writes one anywhere, and never passes
# one as a command-line argument (argv is readable by other local users).

set -uo pipefail

FAILED=0
pass() { printf '  \033[32mPASS\033[0m  %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; FAILED=1; }
skip() { printf '  \033[33mSKIP\033[0m  %s\n' "$1"; }
manual() { printf '  \033[33mMANUAL\033[0m %s\n' "$1"; }

echo "=== S3 ==="
BUCKET="${AWS_BUCKET_NAME:-}"
if [[ -z "$BUCKET" ]]; then
  fail "AWS_BUCKET_NAME is not set — cannot verify the app bucket"
elif ! command -v aws >/dev/null; then
  fail "aws CLI not found on PATH"
elif ! aws s3api head-bucket --bucket "$BUCKET" >/dev/null 2>&1; then
  fail "bucket '$BUCKET' not reachable (credentials or permissions)"
else
  echo "  bucket: $BUCKET"

  versioning="$(aws s3api get-bucket-versioning --bucket "$BUCKET" \
    --query 'Status' --output text 2>/dev/null || echo "None")"
  if [[ "$versioning" == "Enabled" ]]; then
    pass "bucket versioning enabled"
  else
    fail "bucket versioning is '$versioning' — cascade erasure destroys history immediately without it"
  fi

  mfa="$(aws s3api get-bucket-versioning --bucket "$BUCKET" \
    --query 'MFADelete' --output text 2>/dev/null || echo "None")"
  if [[ "$mfa" == "Enabled" ]]; then
    pass "MFA-delete enabled"
  else
    # Not a FAIL: it needs root + an MFA token, so it is a console step by
    # construction and a non-prod bucket may legitimately not have it.
    manual "MFA-delete not enabled (runbook 3.4 — needs root account + MFA token)"
  fi

  if lifecycle="$(aws s3api get-bucket-lifecycle-configuration --bucket "$BUCKET" 2>/dev/null)"; then
    if grep -q '"ID": *"expire-noncurrent"' <<<"$lifecycle" \
       || grep -q '"ID":"expire-noncurrent"' <<<"$lifecycle"; then
      pass "lifecycle rule 'expire-noncurrent' present"
    else
      fail "lifecycle exists but has no 'expire-noncurrent' rule — versioning will grow unbounded"
    fi
    if grep -q 'AbortIncompleteMultipartUpload' <<<"$lifecycle"; then
      pass "incomplete multipart uploads are aborted"
    else
      fail "no AbortIncompleteMultipartUpload rule — failed uploads bill forever"
    fi
  else
    fail "no lifecycle configuration at all (run configure-s3-backup.sh)"
  fi
fi

echo
echo "=== MongoDB Atlas ==="
if [[ -z "${ATLAS_PUBLIC_KEY:-}" || -z "${ATLAS_PRIVATE_KEY:-}" \
   || -z "${ATLAS_GROUP_ID:-}" || -z "${ATLAS_CLUSTER_NAME:-}" ]]; then
  skip "Atlas API credentials not set — checked by hand per runbook section 2"
  echo "       (ATLAS_PUBLIC_KEY / ATLAS_PRIVATE_KEY / ATLAS_GROUP_ID / ATLAS_CLUSTER_NAME)"
else
  API="https://cloud.mongodb.com/api/atlas/v2"
  HDR="Accept: application/vnd.atlas.2023-02-01+json"

  # Credentials go to curl on STDIN via `-K -`, never in argv. Command-line
  # arguments are world-readable through `ps` and /proc for the life of the
  # process, so `-u "$KEY:$SECRET"` would leak the Atlas API secret to every other
  # user on the box — and would have made this script's own "never prints a
  # credential" claim false.
  atlas_get() {
    curl -s --digest -H "$HDR" -K - "$1" <<CURLCFG
user = "${ATLAS_PUBLIC_KEY}:${ATLAS_PRIVATE_KEY}"
CURLCFG
  }

  cluster="$(atlas_get "${API}/groups/${ATLAS_GROUP_ID}/clusters/${ATLAS_CLUSTER_NAME}" 2>/dev/null)"

  if [[ -z "$cluster" ]] || grep -q '"error"' <<<"$cluster"; then
    fail "Atlas API call failed for cluster '${ATLAS_CLUSTER_NAME}'"
  else
    if grep -q '"backupEnabled" *: *true' <<<"$cluster"; then
      pass "Cloud Backup enabled"
    else
      fail "Cloud Backup is NOT enabled on '${ATLAS_CLUSTER_NAME}'"
    fi
    if grep -q '"pitEnabled" *: *true' <<<"$cluster"; then
      pass "Point-in-Time Restore enabled"
    else
      fail "Point-in-Time Restore is NOT enabled — RPO is the snapshot interval"
    fi

    policy="$(atlas_get "${API}/groups/${ATLAS_GROUP_ID}/clusters/${ATLAS_CLUSTER_NAME}/backup/schedule" 2>/dev/null)"
    for freq in hourly daily weekly; do
      if grep -q "\"frequencyType\" *: *\"${freq}\"" <<<"$policy"; then
        pass "snapshot policy has a ${freq} item"
      else
        fail "snapshot policy has no ${freq} item (runbook 2.2)"
      fi
    done
  fi
fi

echo
if [[ $FAILED -eq 0 ]]; then
  echo "Backup posture OK. Record the run in the drill log:"
  echo "  docs/deployment/DATA_ERASURE_AND_BACKUP_RUNBOOK.md section 4"
else
  echo "Backup posture INCOMPLETE — see FAIL lines above." >&2
fi
exit $FAILED
