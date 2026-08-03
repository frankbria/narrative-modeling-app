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
  "${AWS[@]}" s3api head-bucket --bucket "$BUCKET" >/dev/null 2>&1 || return 0

  # TWO passes, and both are required. A versioned bucket is empty only once every
  # object VERSION and every DELETE-MARKER is gone; clearing one kind leaves the
  # other and `delete-bucket` fails with BucketNotEmpty.
  #
  # Queried per-kind rather than with a bare `[]` on the response.
  # list-object-versions returns an OBJECT, and JMESPath's flatten on a non-array
  # evaluates to null, which short-circuits the projection. An earlier version did
  # exactly that: deleted nothing, leaked a bucket on every run, and said in this
  # very comment that it did not. Confirmed by listing buckets after a run.
  local kind kv k v
  for kind in Versions DeleteMarkers; do
    kv="$("${AWS[@]}" s3api list-object-versions --bucket "$BUCKET" \
      --query "${kind}[].[Key,VersionId]" --output text 2>/dev/null)"
    [[ -z "$kv" || "$kv" == "None" ]] && continue
    while IFS=$'\t' read -r k v; do
      [[ -z "$k" || "$k" == "None" ]] && continue
      "${AWS[@]}" s3api delete-object --bucket "$BUCKET" --key "$k" \
        --version-id="$v" >/dev/null 2>&1
    done <<< "$kv"
  done

  if ! "${AWS[@]}" s3api delete-bucket --bucket "$BUCKET" >/dev/null 2>&1; then
    # Loud, not silent. A leaked versioned bucket bills forever, and the previous
    # version hid exactly this behind a redirect.
    echo "WARNING: could not delete drill bucket '$BUCKET' — remove it manually." >&2
  fi
}

trap cleanup EXIT

echo "drill bucket: $BUCKET"
[[ -n "$ENDPOINT" ]] && echo "endpoint:     $ENDPOINT (procedure validation, not a production drill)"

# Every AWS write goes through this. An unchecked call turns an infrastructure
# failure (bad credentials, throttling) into a bogus PROCEDURAL failure two steps
# later — "NO delete-marker" when the truth is "the delete never ran" — which is
# the exact ambiguity this drill exists to remove.
aws_do() {
  local what="$1"; shift
  local err
  err="$("${AWS[@]}" "$@" 2>&1 >/dev/null)" && return 0
  bad "$what — AWS call failed: $(printf '%s' "$err" | tr -d '\n' | head -c 200)"
  return 1
}

step "1. Create the drill bucket and enable versioning"
# us-east-1 must NOT get a LocationConstraint; every other region must.
REGION="${AWS_DEFAULT_REGION:-$(aws configure get region 2>/dev/null)}"
REGION="${REGION:-us-east-1}"
if [[ "$REGION" == "us-east-1" ]]; then
  "${AWS[@]}" s3api create-bucket --bucket "$BUCKET" >/dev/null 2>&1
else
  "${AWS[@]}" s3api create-bucket --bucket "$BUCKET" \
    --create-bucket-configuration "LocationConstraint=$REGION" >/dev/null 2>&1
fi || { echo "could not create the drill bucket in $REGION (credentials?)" >&2; exit 2; }

aws_do "enable versioning" s3api put-bucket-versioning --bucket "$BUCKET" \
  --versioning-configuration Status=Enabled
state="$("${AWS[@]}" s3api get-bucket-versioning --bucket "$BUCKET" --query Status --output text)"
[[ "$state" == "Enabled" ]] && ok "versioning enabled" || bad "versioning is '$state'"

step "2. Write the canary object"
TMP="$(mktemp)"
printf '%s' "$CONTENT" > "$TMP"
aws_do "write canary" s3api put-object --bucket "$BUCKET" --key "$KEY" --body "$TMP"
OUT="$(mktemp)"
"${AWS[@]}" s3api get-object --bucket "$BUCKET" --key "$KEY" "$OUT" >/dev/null 2>&1
[[ "$(cat "$OUT")" == "$CONTENT" ]] && ok "object readable before deletion" || bad "content mismatch before deletion"

step "3. Delete it (as the cascade erasure would)"
aws_do "delete canary" s3api delete-object --bucket "$BUCKET" --key "$KEY"
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
  aws_do "remove delete-marker" s3api delete-object --bucket "$BUCKET" --key "$KEY" --version-id="$MARKER"
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
