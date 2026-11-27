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
  shift 3
  out="$(FIXTURE_FAULT="$fault" python3 scripts/conform.py "$tool" "$@" 2>&1)" || status=$?
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
expect log-changes 1 "conform/log-changes-report"
expect argv-empty 1 "conform/argv-empty"
expect argv-expansion 1 "conform/argv-disagrees"
expect index-missing 1 "conform/input-index-missing"
expect fix-disagrees 1 "conform/fix-argv-disagrees"
expect fix-orphan 1 "conform/fix-argv-orphan"
expect inputs-malformed 1 "conform/report-schema"
expect describe-text 1 "conform/describe"
expect describe-schema 1 "conform/describe-schema"
expect arg-unknown 1 "conform/arg-name-unknown"
expect flag-type 1 "conform/arg-flag-type"
expect slow 1 "conform/timeout" --timeout 1
expect log-invalid 1 "conform/log-changes-report"
expect log-action 1 "conform/log-changes-report"
expect top-requires 1 "conform/arg-name-unknown"
expect index-float 0 ""
expect error-kinds-empty 1 "conform/error-kinds conform/not-run"
expect error-kinds-order 1 "conform/error-kinds conform/not-run"
expect error-kinds-repeat 1 "conform/error-kinds conform/not-run"
expect error-kind-old 1 "conform/error-kind-replaced conform/not-run"
expect requires-any-unknown 1 "conform/arg-name-unknown"
expect requires-any-empty 1 "conform/arg-rule"
expect required-unless-self 1 "conform/arg-rule"
expect required-unless-required 1 "conform/arg-required-unless"
expect conflicts-with-empty 1 "conform/arg-rule"
expect conflicts-with-self 1 "conform/arg-rule"
expect requires-empty 1 "conform/arg-rule"
expect requires-self 1 "conform/arg-rule"
expect requires-any-self 1 "conform/arg-rule"
expect required-unless-empty 1 "conform/arg-rule"
expect top-rule-self 1 "conform/arg-rule"
expect top-names-command 1 "conform/arg-name-unknown"
expect old-key-idle 1 "conform/error-kind-replaced"
expect contract-1.0 0 ""
expect no-example 0 "conform/not-run"
expect nothing-runs 0 "conform/not-run"
expect nothing-runs 1 "conform/not-run conform/nothing-ran" --require-run
expect "" 0 "" --require-run

not_run() {
  local label="$1" kind="$2" out status=0
  shift 2
  out="$(python3 scripts/conform.py "$@" 2>&1)" || status=$?
  if [ "$status" -eq 2 ] && printf '%s' "$out" | tr -d ' \n' | grep -q "\"error_kinds\":\[\"$kind\"\]"; then
    echo "ok    conform, $label: exit 2, not-run, $kind"
  else
    echo "FAIL  conform, $label: expected exit 2 and a not-run report of kind $kind, got exit $status" >&2
    failed=1
  fi
}

not_run "missing binary" environment tests/fixture/no-such-tool
not_run "no arguments" usage
not_run "a timeout of zero" usage "$tool" --timeout 0

if python3 scripts/test_split.py; then
  echo "ok    conform, command splitting"
else
  failed=1
fi

exit "$failed"
