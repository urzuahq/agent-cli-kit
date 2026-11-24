#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

tool="tests/fixture/fixturetool"
failed=0

rules_of() {
  python3 -c 'import json,sys; print(" ".join(sorted({f["rule"] for f in json.load(sys.stdin).get("findings", [])})))'
}

expect() {
  local fault="$1" code="$2" rules="$3" out got status=0
  out="$(FIXTURE_FAULT="$fault" python3 scripts/conform.py "$tool" 2>&1)" || status=$?
  got="$(printf '%s' "$out" | rules_of 2>/dev/null || echo "not JSON")"
  if [ "$status" -eq "$code" ] && [ "$got" = "$rules" ]; then
    echo "ok    conform, fault '${fault}': exit $status${rules:+, $rules}"
  else
    echo "FAIL  conform, fault '${fault}': expected exit $code with '$rules', got exit $status with '$got'" >&2
    failed=1
  fi
}

expect "" 0 ""
expect stderr 1 "conform/log-line conform/stderr"
expect stdout 1 "conform/stdout"
expect exit 1 "conform/exit-code"
expect blocking 1 "conform/exit-code"
expect schema 1 "conform/report-schema"
expect argv-missing 1 "conform/argv-missing"
expect argv-bare 1 "conform/argv-disagrees"
expect index 1 "conform/input-index-wrong"
expect fix-argv 1 "conform/fix-argv-missing"
expect version 1 "conform/version-line"
expect describe-duplicate 1 "conform/arg-name-repeated"
expect describe-log 1 "conform/log-declaration"
expect log-text 1 "conform/log-line"

status=0
out="$(python3 scripts/conform.py tests/fixture/no-such-tool 2>&1)" || status=$?
if [ "$status" -eq 2 ] && printf '%s' "$out" | grep -q '"status": "not-run"'; then
  echo "ok    conform, missing binary: exit 2, not-run"
else
  echo "FAIL  conform, missing binary: expected exit 2 and a not-run report, got exit $status" >&2
  failed=1
fi

exit "$failed"
