#!/usr/bin/env bash
#
# S3 restore drill (#299 / AC3 of #259).
#
# Executes the drill from runbook section 3 as a script instead of a paragraph:
# versioning on, write an object, delete it, confirm the delete-marker, restore by
# removing the marker, confirm the bytes come back intact.
#
# WHY SCRIPTED. A drill described in prose is validated for the first time during
# an incident, which is the worst possible moment to discover a step is wrong.
# This runs the real S3 API calls, so the procedure is proven rather than assumed.
#
# TARGET. Defaults to a THROWAWAY bucket it creates and deletes itself. Against
# LocalStack (`--endpoint http://localhost:4566`) it proves the procedure with zero
# cloud cost or risk; against real S3 it is a genuine drill. It never touches the
# app bucket — a drill that runs against production data is not a drill.
#
# Usage:
#   ./scripts/ops/drill-s3-restore.sh                                   # real S3
#   ./scripts/ops/drill-s3-restore.sh --endpoint http://localhost:4566  # LocalStack

set -uo pipefail

ENDPOINT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --endpoint) ENDPOINT="${2:?--endpoint needs a URL}"; shift 2 ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

AWS=(aws)
if [[ -n "$ENDPOINT" ]]; then
  AWS=(aws --endpoint-url "$ENDPOINT")
  # AWS CLI v2 attaches a streaming checksum trailer (`x-amz-trailer`) to uploads
  # by default. LocalStack 3.0.2 predates that and rejects the request outright,
  # which fails the drill for a reason unrelated to the restore procedure. Only
  # set for the LocalStack path — against real S3 the checksums are wanted.
  export AWS_REQUEST_CHECKSUM_CALCULATION=when_required
  export AWS_RESPONSE_CHECKSUM_VALIDATION=when_required
fi

# A distinct name per run so a previous failed drill cannot silently be reused.
BUCKET="nma-restore-drill-$(date -u +%Y%m%d%H%M%S)-$$"
KEY="drill/canary.txt"
CONTENT="restore-drill canary $(date -u +%FT%TZ)"

FAILED=0
step() { printf '\n\033[1m%s\033[0m\n' "$1"; }
ok()   { printf '  \033[32mPASS\033[0m  %s\n' "$1"; }
bad()  { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; FAILED=1; }

cleanup() {
  rm -f "${TMP:-}" "${OUT:-}" "${RESTORED:-}" 2>/dev/null
  # Always tear the bucket down, including on failure — a drill that leaves
  # billable buckets behind stops being run.
  if "${AWS[@]}" s3api head-bucket --bucket "$BUCKET" >/dev/null 2>&1; then
    "${AWS[@]}" s3api delete-objects --bucket "$BUCKET" --delete "$(
      "${AWS[@]}" s3api list-object-versions --bucket "$BUCKET" \
        --query '{Objects: [].{Key:Key,VersionId:VersionId}}' --output json 2>/dev/null \
        | python3 -c "
import json,sys
d=json.load(sys.stdin)
objs=[o for o in (d.get('Objects') or []) if o.get('Key')]
print(json.dumps({'Objects':objs}) if objs else '{\"Objects\":[]}')
" 2>/dev/null
    )" >/dev/null 2>&1
    "${AWS[@]}" s3api delete-bucket --bucket "$BUCKET" >/dev/null 2>&1
  fi
}
trap cleanup EXIT

echo "drill bucket: $BUCKET"
[[ -n "$ENDPOINT" ]] && echo "endpoint:     $ENDPOINT (procedure validation, not a production drill)"

step "1. Create the drill bucket and enable versioning"
"${AWS[@]}" s3api create-bucket --bucket "$BUCKET" >/dev/null 2>&1 \
  || { echo "could not create the drill bucket (credentials?)" >&2; exit 2; }
"${AWS[@]}" s3api put-bucket-versioning --bucket "$BUCKET" \
  --versioning-configuration Status=Enabled >/dev/null
state="$("${AWS[@]}" s3api get-bucket-versioning --bucket "$BUCKET" --query Status --output text)"
[[ "$state" == "Enabled" ]] && ok "versioning enabled" || bad "versioning is '$state'"

step "2. Write the canary object"
TMP="$(mktemp)"
printf '%s' "$CONTENT" > "$TMP"
"${AWS[@]}" s3api put-object --bucket "$BUCKET" --key "$KEY" --body "$TMP" >/dev/null
OUT="$(mktemp)"
"${AWS[@]}" s3api get-object --bucket "$BUCKET" --key "$KEY" "$OUT" >/dev/null 2>&1
[[ "$(cat "$OUT")" == "$CONTENT" ]] && ok "object readable before deletion" || bad "content mismatch before deletion"

step "3. Delete it (as the cascade erasure would)"
"${AWS[@]}" s3api delete-object --bucket "$BUCKET" --key "$KEY" >/dev/null
if "${AWS[@]}" s3api head-object --bucket "$BUCKET" --key "$KEY" >/dev/null 2>&1; then
  bad "object still readable after delete — versioning is not behaving as expected"
else
  ok "object no longer readable (as expected)"
fi

step "4. Confirm a delete-marker, not destruction"
MARKER="$("${AWS[@]}" s3api list-object-versions --bucket "$BUCKET" --prefix "$KEY" \
  --query 'DeleteMarkers[0].VersionId' --output text 2>/dev/null)"
if [[ -n "$MARKER" && "$MARKER" != "None" ]]; then
  ok "delete-marker present ($MARKER)"
else
  bad "NO delete-marker — the object was destroyed, not marked. Restore is impossible."
fi

step "5. Restore by removing the delete-marker"
if [[ -n "$MARKER" && "$MARKER" != "None" ]]; then
  # `--version-id=` with an equals sign, NOT a space. S3 version IDs are
  # base64-ish and can begin with `-`, at which point the CLI parses the value as
  # another flag and dies with "expected one argument". This bit here first, and
  # it would bite identically during a real restore — the runbook's prose form
  # has the same hazard.
  "${AWS[@]}" s3api delete-object --bucket "$BUCKET" --key "$KEY" --version-id="$MARKER" >/dev/null
  RESTORED="$(mktemp)"
  "${AWS[@]}" s3api get-object --bucket "$BUCKET" --key "$KEY" "$RESTORED" >/dev/null 2>&1
  if [[ "$(cat "$RESTORED")" == "$CONTENT" ]]; then
    ok "object restored, bytes identical"
  else
    bad "restored content differs from the original"
  fi
else
  bad "skipped — no delete-marker to remove"
fi

echo
if [[ $FAILED -eq 0 ]]; then
  echo "RESULT: the documented S3 restore procedure works."
  echo "Record this run in docs/deployment/DATA_ERASURE_AND_BACKUP_RUNBOOK.md section 5."
else
  echo "RESULT: the S3 restore procedure DID NOT work as documented." >&2
fi
exit $FAILED
