#!/usr/bin/env bash
#
# Apply the S3 half of the backup posture (#299 / AC3 of #259).
#
# Replaces "click through the S3 console following section 3 of the runbook" with
# one idempotent command. Safe to re-run: enabling versioning that is already on
# is a no-op, and the lifecycle configuration is declared whole, so re-running
# converges rather than appending duplicate rules.
#
# It does NOT touch MFA-delete. That genuinely cannot be scripted here — S3
# requires the root account's MFA serial and a current token on the request, so it
# stays a console step in the runbook, deliberately.
#
# Usage:
#   AWS_BUCKET_NAME=my-bucket ./scripts/ops/configure-s3-backup.sh          # apply
#   AWS_BUCKET_NAME=my-bucket ./scripts/ops/configure-s3-backup.sh --dry-run
#
# Credentials come from the ambient AWS CLI configuration (profile, SSO, env, or
# instance role). This script never takes, prints, or stores a credential.

set -euo pipefail

BUCKET="${AWS_BUCKET_NAME:-}"
DRY_RUN=0
# Reject anything unrecognised rather than ignoring it. `--dryrun` silently
# falling through to a real run against a production bucket is the worst
# possible reading of a typo.
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) sed -n '2,22p' "$0"; exit 0 ;;
    *) echo "Unknown argument: $1 (did you mean --dry-run?)" >&2; exit 2 ;;
  esac
done

if [[ -z "$BUCKET" ]]; then
  echo "AWS_BUCKET_NAME is not set. Refusing to guess which bucket to configure." >&2
  exit 2
fi

command -v aws >/dev/null || { echo "aws CLI not found on PATH" >&2; exit 2; }

# Fail early and clearly on the two things that actually go wrong: no credentials,
# or the wrong account. A lifecycle rule applied to someone else's bucket is not
# the kind of mistake you want to discover from a 403 three commands later.
if ! ACCOUNT="$(aws sts get-caller-identity --query Account --output text 2>/dev/null)"; then
  echo "No usable AWS credentials. Configure the CLI first (aws sso login / profile)." >&2
  exit 2
fi
if ! aws s3api head-bucket --bucket "$BUCKET" >/dev/null 2>&1; then
  echo "Bucket '$BUCKET' is not reachable from account $ACCOUNT." >&2
  exit 2
fi

echo "account: $ACCOUNT"
echo "bucket:  $BUCKET"
[[ $DRY_RUN -eq 1 ]] && echo "mode:    DRY RUN (no changes)"
echo

# Retention windows come from runbook section 3 and are the numbers the drill log
# and the GDPR follow-up both refer to. Change them here and there together.
NONCURRENT_DAYS=30
ABORT_MPU_DAYS=7

OUR_RULE=$(cat <<JSON
{
  "ID": "expire-noncurrent",
  "Status": "Enabled",
  "Filter": {"Prefix": ""},
  "NoncurrentVersionExpiration": {"NoncurrentDays": ${NONCURRENT_DAYS}},
  "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": ${ABORT_MPU_DAYS}}
}
JSON
)

# put-bucket-lifecycle-configuration REPLACES the whole configuration — it does
# not merge. Declaring only our rule would silently delete any cost-tiering or
# prefix rules the bucket already has, which is a destructive surprise from a
# script whose job is protecting data. So: read what is there, drop only our own
# rule by ID (making a re-run converge rather than duplicate), keep the rest.
EXISTING="$(aws s3api get-bucket-lifecycle-configuration --bucket "$BUCKET" 2>/dev/null || echo '{"Rules":[]}')"

LIFECYCLE="$(python3 - "$EXISTING" "$OUR_RULE" <<'PYEOF'
import json, sys
existing = json.loads(sys.argv[1] or '{"Rules": []}').get("Rules", [])
ours = json.loads(sys.argv[2])
kept = [r for r in existing if r.get("ID") != ours["ID"]]
if kept:
    print("KEEPING:" + ",".join(r.get("ID", "<unnamed>") for r in kept), file=sys.stderr)
print(json.dumps({"Rules": kept + [ours]}))
PYEOF
)" || { echo "failed to merge lifecycle rules; refusing to apply" >&2; exit 2; }

current_versioning="$(aws s3api get-bucket-versioning --bucket "$BUCKET" \
  --query 'Status' --output text 2>/dev/null || echo "None")"
echo "versioning currently: $current_versioning"

if [[ "$current_versioning" == "Enabled" ]]; then
  echo "  already enabled, nothing to do"
elif [[ $DRY_RUN -eq 1 ]]; then
  echo "  WOULD enable bucket versioning"
else
  aws s3api put-bucket-versioning --bucket "$BUCKET" \
    --versioning-configuration Status=Enabled
  echo "  enabled"
fi

echo
preserved="$(python3 -c "
import json,sys
rules=json.loads(sys.argv[1]).get('Rules',[])
print(', '.join(r.get('ID','<unnamed>') for r in rules if r.get('ID')!='expire-noncurrent') or '(none)')
" "$LIFECYCLE")"
echo "lifecycle: expire-noncurrent (${NONCURRENT_DAYS}d) + abort-incomplete-mpu (${ABORT_MPU_DAYS}d)"
echo "  preserving existing rules: $preserved"
if [[ $DRY_RUN -eq 1 ]]; then
  echo "  WOULD apply:"
  echo "$LIFECYCLE"
else
  aws s3api put-bucket-lifecycle-configuration --bucket "$BUCKET" \
    --lifecycle-configuration "$LIFECYCLE"
  echo "  applied"
fi

echo
echo "Done. Verify with: ./scripts/ops/verify-backup-config.sh"
echo "Still manual (by design): MFA-delete — see runbook section 3.4."
