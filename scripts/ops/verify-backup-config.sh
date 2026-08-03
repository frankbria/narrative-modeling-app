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

  # Every read below follows the same rule, and it is the whole point of this
  # file: ABSENCE MUST BE PROVEN, never inferred from a failure.
  #
  # stdout and stderr are captured separately. Merging them (`2>&1`) means a
  # benign stderr line — a CLI deprecation notice, a proxy warning — lands in the
  # JSON, the parse fails, and the fallback reports "not configured". That is the
  # original bug rebuilt out of its own fix.
  s3_read() {
    local out err rc
    err="$(mktemp)"
    out="$(aws s3api "$@" --bucket "$BUCKET" 2>"$err")"; rc=$?
    S3_OUT="$out"; S3_ERR="$(cat "$err")"; rm -f "$err"
    return $rc
  }

  if s3_read get-bucket-versioning; then
    # One parse, both fields. A parse failure yields "unknown", NOT "None" —
    # unparseable output means we do not know, not that nothing is configured.
    read -r versioning mfa <<<"$(python3 -c '
import json, sys
try:
    d = json.loads(sys.argv[1] or "{}")
    print(d.get("Status", "None"), d.get("MFADelete", "None"))
except Exception:
    print("unknown unknown")
' "$S3_OUT")"
  else
    versioning="unknown"; mfa="unknown"
    if grep -Eqi "AccessDenied|not authorized" <<<"$S3_ERR"; then
      fail "cannot read versioning — AccessDenied (needs s3:GetBucketVersioning). State is UNKNOWN, not absent"
    else
      fail "cannot read versioning: $(tr -d '\n' <<<"$S3_ERR" | head -c 160). State is UNKNOWN, not absent"
    fi
  fi

  case "$versioning" in
    Enabled) pass "bucket versioning enabled" ;;
    unknown) : ;;  # already reported above
    *) fail "bucket versioning is '$versioning' — cascade erasure destroys history immediately without it" ;;
  esac

  case "$mfa" in
    Enabled) pass "MFA-delete enabled" ;;
    unknown) manual "MFA-delete state UNKNOWN — the versioning block could not be read" ;;
    *) manual "MFA-delete not enabled (runbook 3.4 — needs root account + MFA token)" ;;
  esac

  if s3_read get-bucket-lifecycle-configuration; then
    # Parsed as JSON, not grepped. A `grep '"ID"'` match is sensitive to key
    # ordering and whitespace in the response, and would also match an ID inside
    # some unrelated rule.
    lifecycle_state="$(python3 -c '
import json, sys
try:
    rules = json.loads(sys.argv[1] or "{}").get("Rules", [])
except Exception:
    print("unknown"); raise SystemExit
ours = next((r for r in rules if r.get("ID") == "expire-noncurrent"), None)
if ours is None:
    print("missing")
elif "AbortIncompleteMultipartUpload" not in ours:
    print("no-abort")
else:
    print("ok")
' "$S3_OUT")"
    case "$lifecycle_state" in
      ok)
        pass "lifecycle rule 'expire-noncurrent' present"
        pass "incomplete multipart uploads are aborted (on the expire-noncurrent rule)"
        ;;
      no-abort)
        pass "lifecycle rule 'expire-noncurrent' present"
        fail "the expire-noncurrent rule has no AbortIncompleteMultipartUpload — failed uploads bill forever"
        ;;
      missing)
        fail "lifecycle exists but has no 'expire-noncurrent' rule — versioning will grow unbounded"
        ;;
      *)
        fail "lifecycle response could not be parsed — state is UNKNOWN, not absent"
        ;;
    esac
  elif grep -Eqi "NoSuchLifecycleConfiguration" <<<"$S3_ERR"; then
    # INVERTED deliberately. This is the ONLY error that legitimately means "no
    # rules exist". Every other failure — throttling, ExpiredToken, wrong region,
    # AllAccessDisabled — is unknown. The previous version special-cased
    # AccessDenied and let everything else fall through to "no lifecycle at all",
    # which narrowed this bug rather than removing it.
    fail "no lifecycle configuration at all (run configure-s3-backup.sh)"
  elif grep -Eqi "AccessDenied|not authorized" <<<"$S3_ERR"; then
    fail "cannot read lifecycle — AccessDenied (needs s3:GetLifecycleConfiguration). Rules are UNKNOWN, not absent"
  else
    fail "cannot read lifecycle: $(tr -d '\n' <<<"$S3_ERR" | head -c 160). Rules are UNKNOWN, not absent"
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
