#!/usr/bin/env bash
#
# Tests for configure-s3-backup.sh, with a stub `aws` on PATH.
#
# WHY. The script justifies itself with "a typo here costs more than a typo in
# application code" — and then the trickiest part of it, merging our lifecycle
# rule into whatever the bucket already has, was covered by nothing but prose in a
# PR description. shellcheck catches syntax, not "this silently deleted the
# customer's cost-tiering rules".
#
# The stub records every aws invocation and replays canned responses, so the merge
# logic is exercised end to end without an AWS account. Run: ./test-configure-s3-backup.sh

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$HERE/configure-s3-backup.sh"
FAILED=0

pass() { printf '  \033[32mPASS\033[0m  %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; FAILED=1; }

# $1 = JSON the stub returns for get-bucket-lifecycle-configuration ("" = none)
make_stub() {
  local existing="$1" dir
  dir="$(mktemp -d)"
  cat > "$dir/aws" <<STUB
#!/usr/bin/env bash
# Records the call, then answers it.
echo "\$*" >> "$dir/calls.log"
case "\$*" in
  "sts get-caller-identity"*) echo "123456789012" ;;
  "s3api head-bucket"*) exit 0 ;;
  "s3api get-bucket-versioning"*) echo "Suspended" ;;
  "s3api get-bucket-lifecycle-configuration"*)
    if [[ -n '$existing' ]]; then echo '$existing'; else exit 254; fi ;;
  "s3api put-bucket-lifecycle-configuration"*)
    # Capture the payload that would reach AWS — the thing under test.
    printf '%s\n' "\$*" > "$dir/put-lifecycle.txt" ;;
  "s3api put-bucket-versioning"*) : ;;
esac
STUB
  chmod +x "$dir/aws"
  echo "$dir"
}

run_with_stub() {
  local dir="$1"; shift
  PATH="$dir:$PATH" AWS_BUCKET_NAME=test-bucket "$SCRIPT" "$@" 2>&1
}

echo "=== argument handling ==="

out="$(env -u AWS_BUCKET_NAME "$SCRIPT" 2>&1)"; rc=$?
if [[ $rc -eq 2 && "$out" == *"Refusing to guess"* ]]; then
  pass "missing AWS_BUCKET_NAME exits 2"
else
  fail "missing AWS_BUCKET_NAME: rc=$rc out=$out"
fi

d="$(make_stub "")"
out="$(run_with_stub "$d" --dryrun)"; rc=$?
if [[ $rc -eq 2 && "$out" == *"Unknown argument"* ]]; then
  pass "a typo'd --dry-run is rejected, not treated as a real run"
else
  fail "typo'd flag: rc=$rc out=$out"
fi

out="$(run_with_stub "$d" --dry-run)"
if [[ -f "$d/put-lifecycle.txt" ]]; then
  fail "--dry-run still called put-bucket-lifecycle-configuration"
else
  pass "--dry-run mutates nothing"
fi
rm -rf "$d"

echo
echo "=== lifecycle merge (the destructive-if-wrong part) ==="

# A bucket that already has an unrelated rule. Deleting it would be a silent,
# expensive regression for whoever owns that rule.
EXISTING='{"Rules":[{"ID":"cost-tiering","Status":"Enabled","Filter":{"Prefix":"archive/"},"Transitions":[{"Days":90,"StorageClass":"GLACIER"}]}]}'
d="$(make_stub "$EXISTING")"
run_with_stub "$d" >/dev/null

if [[ -f "$d/put-lifecycle.txt" ]]; then
  payload="$(cat "$d/put-lifecycle.txt")"
  if grep -q "cost-tiering" <<<"$payload"; then
    pass "an unrelated existing rule survives"
  else
    fail "unrelated rule 'cost-tiering' was DELETED by the apply"
  fi
  if grep -q "expire-noncurrent" <<<"$payload"; then
    pass "our rule is present"
  else
    fail "our rule is missing from the payload"
  fi
else
  fail "no lifecycle configuration was applied at all"
fi
rm -rf "$d"

# Re-running must converge, not stack duplicates of our own rule.
ALREADY_OURS='{"Rules":[{"ID":"expire-noncurrent","Status":"Enabled","Filter":{"Prefix":""},"NoncurrentVersionExpiration":{"NoncurrentDays":9999}}]}'
d="$(make_stub "$ALREADY_OURS")"
run_with_stub "$d" >/dev/null
payload="$(cat "$d/put-lifecycle.txt" 2>/dev/null || echo "")"
count="$(grep -o "expire-noncurrent" <<<"$payload" | wc -l)"
if [[ "$count" -eq 1 ]]; then
  pass "re-running replaces our rule rather than duplicating it"
else
  fail "expected exactly 1 'expire-noncurrent', found $count"
fi
# And the stale 9999-day retention must be gone, not merged alongside.
if grep -q "9999" <<<"$payload"; then
  fail "the previous rule's retention (9999d) survived — ours did not win"
else
  pass "our current retention replaces the stale one"
fi
rm -rf "$d"

echo
echo "=== no pre-existing configuration ==="
d="$(make_stub "")"
run_with_stub "$d" >/dev/null
payload="$(cat "$d/put-lifecycle.txt" 2>/dev/null || echo "")"
if grep -q "expire-noncurrent" <<<"$payload" && grep -q "AbortIncompleteMultipartUpload" <<<"$payload"; then
  pass "a bucket with no lifecycle gets both rules"
else
  fail "empty-bucket path did not apply the expected rules"
fi
rm -rf "$d"

echo
if [[ $FAILED -eq 0 ]]; then
  echo "All configure-s3-backup.sh tests passed."
else
  echo "configure-s3-backup.sh tests FAILED." >&2
fi
exit $FAILED
