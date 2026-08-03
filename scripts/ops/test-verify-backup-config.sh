#!/usr/bin/env bash
#
# Tests for verify-backup-config.sh, with a stub `aws` on PATH.
#
# WHY. This script's entire job is telling the truth about backup state, and it
# has now got that wrong twice:
#
#   1. `2>/dev/null || echo "None"` reported AccessDenied as "not configured" —
#      a confident negative about a bucket it was not allowed to read.
#   2. The first fix special-cased AccessDenied and let every OTHER error
#      (throttling, ExpiredToken, wrong region) fall through to "no lifecycle
#      configuration at all", narrowing the same bug rather than removing it.
#
# Both were found by a human reading it. The rule the tests encode is:
# **absence must be proven, never inferred from a failure.**
#
# Run: ./scripts/ops/test-verify-backup-config.sh

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$HERE/verify-backup-config.sh"
FAILED=0

pass() { printf '  \033[32mPASS\033[0m  %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; FAILED=1; }

# $1 = versioning behaviour, $2 = lifecycle behaviour.
#
# The chosen behaviour is baked into the generated stub rather than branched on at
# stub runtime. An earlier version used an unquoted heredoc, which expanded the
# modes at generation time anyway — producing `case "denied" in` against dead
# branches while reading as though the stub inspected a variable. Same result,
# but the code lied about how it worked.
emit_versioning() {
  case "$1" in
    enabled)  echo "echo '{\"Status\":\"Enabled\",\"MFADelete\":\"Disabled\"}'" ;;
    absent)   echo "echo '{}'" ;;
    denied)   echo "echo 'An error occurred (AccessDenied) ... not authorized to perform: s3:GetBucketVersioning' >&2; exit 254" ;;
    throttle) echo "echo 'An error occurred (SlowDown) when calling GetBucketVersioning' >&2; exit 254" ;;
    garbage)  echo "echo 'not json at all'" ;;
    noisy)    echo "echo 'warning: a benign CLI notice' >&2; echo '{\"Status\":\"Enabled\",\"MFADelete\":\"Disabled\"}'" ;;
  esac
}

emit_lifecycle() {
  case "$1" in
    ok)      echo "echo '{\"Rules\":[{\"ID\":\"expire-noncurrent\",\"Status\":\"Enabled\",\"AbortIncompleteMultipartUpload\":{\"DaysAfterInitiation\":7}}]}'" ;;
    norule)  echo "echo '{\"Rules\":[{\"ID\":\"something-else\",\"Status\":\"Enabled\"}]}'" ;;
    none)    echo "echo 'An error occurred (NoSuchLifecycleConfiguration) ...' >&2; exit 254" ;;
    denied)  echo "echo 'An error occurred (AccessDenied) ... not authorized to perform: s3:GetLifecycleConfiguration' >&2; exit 254" ;;
    expired) echo "echo 'An error occurred (ExpiredToken) when calling GetBucketLifecycleConfiguration' >&2; exit 254" ;;
  esac
}

make_stub() {
  local dir
  dir="$(mktemp -d)"
  {
    echo '#!/usr/bin/env bash'
    echo 'case "$*" in'
    echo '  *"head-bucket"*) exit 0 ;;'
    echo '  *"get-bucket-versioning"*)'
    echo "    $(emit_versioning "$1") ;;"
    echo '  *"get-bucket-lifecycle-configuration"*)'
    echo "    $(emit_lifecycle "$2") ;;"
    echo 'esac'
  } > "$dir/aws"
  chmod +x "$dir/aws"
  echo "$dir"
}

run() {
  local dir="$1"
  PATH="$dir:$PATH" AWS_BUCKET_NAME=test-bucket bash "$SCRIPT" 2>&1
}

# expect_out <desc> <vmode> <lmode> <must-contain> [must-not-contain]
expect_out() {
  local desc="$1" v="$2" l="$3" want="$4" avoid="${5:-}" dir out
  dir="$(make_stub "$v" "$l")"
  out="$(run "$dir")"
  rm -rf "$dir"
  if ! grep -qi -- "$want" <<<"$out"; then
    fail "$desc — expected output matching '$want'"; echo "$out" | sed 's/^/        /'; return
  fi
  if [[ -n "$avoid" ]] && grep -qi -- "$avoid" <<<"$out"; then
    fail "$desc — output wrongly claimed '$avoid'"; echo "$out" | sed 's/^/        /'; return
  fi
  pass "$desc"
}

echo "=== the original bug: denied must never read as absent ==="
expect_out "AccessDenied on versioning says UNKNOWN" \
  denied ok "versioning.*UNKNOWN" "versioning is 'None'"
expect_out "AccessDenied on lifecycle says UNKNOWN" \
  enabled denied "lifecycle.*UNKNOWN" "no lifecycle configuration at all"

echo
echo "=== the partial fix: NON-AccessDenied errors must also be UNKNOWN ==="
expect_out "throttling on versioning is UNKNOWN, not 'None'" \
  throttle ok "UNKNOWN" "versioning is 'None'"
expect_out "ExpiredToken on lifecycle is UNKNOWN, not 'no lifecycle at all'" \
  enabled expired "UNKNOWN" "no lifecycle configuration at all"

echo
echo "=== unparseable output must be UNKNOWN, not a confident negative ==="
expect_out "garbage JSON is UNKNOWN, not 'None'" \
  garbage ok "UNKNOWN" "versioning is 'None'"
expect_out "stderr noise on a SUCCESS does not corrupt the read" \
  noisy ok "versioning enabled" "UNKNOWN"

echo
echo "=== true negatives must still be reported as negatives ==="
expect_out "NoSuchLifecycleConfiguration really does mean absent" \
  enabled none "no lifecycle configuration at all"
expect_out "versioning genuinely off is reported off" \
  absent ok "versioning is 'None'"
expect_out "lifecycle without our rule is reported" \
  enabled norule "no 'expire-noncurrent' rule"

echo
echo "=== the fully-configured case still passes ==="
expect_out "versioning + lifecycle + abort = PASS" \
  enabled ok "lifecycle rule 'expire-noncurrent' present" "UNKNOWN"

echo
if [[ $FAILED -eq 0 ]]; then
  echo "All verify-backup-config.sh tests passed."
else
  echo "verify-backup-config.sh tests FAILED." >&2
fi
exit $FAILED
