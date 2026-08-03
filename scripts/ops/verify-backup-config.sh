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

CHECKED_S3=0
CHECKED_ATLAS=0

echo "=== S3 ==="
BUCKET="${AWS_BUCKET_NAME:-}"
if [[ -z "$BUCKET" ]]; then
  # SKIP, not FAIL — symmetric with the Atlas half below. A deployment may
  # legitimately configure one and not the other, and the scheduled job (#299)
  # would otherwise report a red month for a half it was never asked to check.
  # "Nothing was checked at all" is still a failure; see the end of the file.
  skip "AWS_BUCKET_NAME is not set — S3 not checked"
elif ! command -v aws >/dev/null; then
  fail "aws CLI not found on PATH"
elif ! aws s3api head-bucket --bucket "$BUCKET" >/dev/null 2>&1; then
  fail "bucket '$BUCKET' not reachable (credentials or permissions)"
else
  CHECKED_S3=1
  echo "  bucket: $BUCKET"

  # Capture stderr and the exit code SEPARATELY from the value. `2>/dev/null ||
  # echo "None"` turned an AccessDenied into "None" — reporting a bucket we are
  # not allowed to inspect as definitively unconfigured. A verifier that cannot
  # tell "not there" from "not allowed to look" is worse than no verifier: it
  # produces a confident answer it has not earned, and both readings are
  # actionable in opposite directions.
  vraw="$(aws s3api get-bucket-versioning --bucket "$BUCKET" 2>&1)"
  if [[ $? -ne 0 ]]; then
    if grep -qi "AccessDenied\|not authorized" <<<"$vraw"; then
      fail "cannot read versioning — AccessDenied. This principal lacks s3:GetBucketVersioning; the backup state is UNKNOWN, not absent"
    else
      fail "cannot read versioning: $(tr -d '\n' <<<"$vraw" | head -c 160)"
    fi
    versioning="unknown"
    mfa="unknown"
  else
    versioning="$(python3 -c "
import json,sys
try: print(json.loads(sys.argv[1] or '{}').get('Status','None'))
except Exception: print('None')
" "$vraw")"
    mfa="$(python3 -c "
import json,sys
try: print(json.loads(sys.argv[1] or '{}').get('MFADelete','None'))
except Exception: print('None')
" "$vraw")"
    if [[ "$versioning" == "Enabled" ]]; then
      pass "bucket versioning enabled"
    else
      fail "bucket versioning is '$versioning' — cascade erasure destroys history immediately without it"
    fi
  fi
  if [[ "$mfa" == "Enabled" ]]; then
    pass "MFA-delete enabled"
  elif [[ "$mfa" == "unknown" ]]; then
    # Same trap one line down: reporting "not enabled" for something we could not
    # read is the identical false-confidence bug.
    manual "MFA-delete state UNKNOWN — could not read the bucket's versioning block"
  else
    # Not a FAIL: it needs root + an MFA token, so it is a console step by
    # construction and a non-prod bucket may legitimately not have it.
    manual "MFA-delete not enabled (runbook 3.4 — needs root account + MFA token)"
  fi

  lraw="$(aws s3api get-bucket-lifecycle-configuration --bucket "$BUCKET" 2>&1)"
  lrc=$?
  if [[ $lrc -ne 0 ]] && grep -qi "AccessDenied\|not authorized" <<<"$lraw"; then
    # Same distinction as versioning above. NoSuchLifecycleConfiguration genuinely
    # means "no rules"; AccessDenied means we do not know.
    fail "cannot read lifecycle — AccessDenied. This principal lacks s3:GetLifecycleConfiguration; the rules are UNKNOWN, not absent"
  elif [[ $lrc -eq 0 ]] && lifecycle="$lraw"; then
    if grep -q '"ID": *"expire-noncurrent"' <<<"$lifecycle" \
       || grep -q '"ID":"expire-noncurrent"' <<<"$lifecycle"; then
      pass "lifecycle rule 'expire-noncurrent' present"
    else
      fail "lifecycle exists but has no 'expire-noncurrent' rule — versioning will grow unbounded"
    fi
    # Scoped to OUR rule, not "appears anywhere in the document". We are the only
    # writer today, so an unscoped grep passes either way — but the moment someone
    # adds a second rule carrying an abort clause, an unscoped check would report
    # our rule as healthy when it has no abort clause at all.
    if python3 -c "
import json,sys
rules = json.load(sys.stdin).get('Rules', [])
ours = next((r for r in rules if r.get('ID') == 'expire-noncurrent'), None)
sys.exit(0 if ours and 'AbortIncompleteMultipartUpload' in ours else 1)
" <<<"$lifecycle" 2>/dev/null; then
      pass "incomplete multipart uploads are aborted (on the expire-noncurrent rule)"
    else
      fail "the expire-noncurrent rule has no AbortIncompleteMultipartUpload — failed uploads bill forever"
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
  CHECKED_ATLAS=1
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
if [[ $CHECKED_S3 -eq 0 && $CHECKED_ATLAS -eq 0 ]]; then
  # The one thing worse than a red check is a green one that verified nothing.
  # Skipping an unconfigured HALF is reasonable; skipping both means this ran and
  # told you nothing while looking like a pass.
  echo "Nothing was verified — neither S3 nor Atlas is configured." >&2
  echo "Set AWS_BUCKET_NAME and/or the ATLAS_* variables (see the header)." >&2
  exit 1
fi

echo "checked: S3=$( ((CHECKED_S3)) && echo yes || echo no ), Atlas=$( ((CHECKED_ATLAS)) && echo yes || echo no )"
if [[ $FAILED -eq 0 ]]; then
  echo "Backup posture OK. Record the run in the drill log:"
  echo "  docs/deployment/DATA_ERASURE_AND_BACKUP_RUNBOOK.md section 4"
else
  echo "Backup posture INCOMPLETE — see FAIL lines above." >&2
fi
exit $FAILED
