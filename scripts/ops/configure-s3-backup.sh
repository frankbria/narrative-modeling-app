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
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

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

LIFECYCLE=$(cat <<JSON
{
  "Rules": [
    {
      "ID": "expire-noncurrent",
      "Status": "Enabled",
      "Filter": {"Prefix": ""},
      "NoncurrentVersionExpiration": {"NoncurrentDays": ${NONCURRENT_DAYS}},
      "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": ${ABORT_MPU_DAYS}}
    }
  ]
}
JSON
)

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
echo "lifecycle: expire-noncurrent (${NONCURRENT_DAYS}d) + abort-incomplete-mpu (${ABORT_MPU_DAYS}d)"
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
