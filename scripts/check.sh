#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

version=0.39.0
if command -v uvx >/dev/null 2>&1; then
  run=(uvx "check-jsonschema==$version")
elif command -v pipx >/dev/null 2>&1; then
  run=(pipx run --spec "check-jsonschema==$version" check-jsonschema)
else
  echo "check.sh: neither uvx nor pipx is installed" >&2
  exit 2
fi

# The schemas' $id points at the published location; resolve $refs against the local copy.
base_uri="file://$root/schemas/"

validate() {
  "${run[@]}" --base-uri "$base_uri" --schemafile "schemas/$1.schema.json" "$2" 2>&1
}

schema_of() {
  local name
  name="$(basename "$1")"
  echo "${name%%.*}"
}

shopt -s nullglob
valid=(examples/valid/*.json)
invalid=(examples/invalid/*.json)

if [ ${#valid[@]} -eq 0 ] || [ ${#invalid[@]} -eq 0 ]; then
  echo "check.sh: no examples found (valid: ${#valid[@]}, invalid: ${#invalid[@]})" >&2
  exit 1
fi

failed=0

if ! (cd schemas && sha256sum -- *.schema.json | diff - SHA256SUMS >&2); then
  echo "FAIL  schemas/SHA256SUMS does not match the schemas; run 'make sums'" >&2
  failed=1
fi

# An example only exercises the $refs it reaches, so check every target exists.
while IFS=: read -r file ref; do
  target="${ref%%#*}"
  if [ -n "$target" ] && [ ! -f "schemas/$target" ]; then
    echo "FAIL  $file refers to $target, which is not in schemas/" >&2
    failed=1
  fi
done < <(grep -o '"\$ref": *"[^"]*"' schemas/*.schema.json | sed -E 's/"\$ref": *"([^"]*)"$/\1/')

for s in schemas/*.schema.json; do
  if ! out="$("${run[@]}" --check-metaschema "$s" 2>&1)"; then
    echo "FAIL  $s is not a valid schema" >&2
    echo "$out" >&2
    failed=1
  fi
done

for f in "${valid[@]}"; do
  s="$(schema_of "$f")"
  if out="$(validate "$s" "$f")"; then
    echo "ok    $f"
  else
    echo "FAIL  $f should validate against $s" >&2
    echo "$out" >&2
    failed=1
  fi
done

for f in "${invalid[@]}"; do
  s="$(schema_of "$f")"
  if out="$(validate "$s" "$f")"; then
    echo "FAIL  $f should be rejected by $s" >&2
    failed=1
  # A schema that cannot be loaded also fails; only a validation error counts as a rejection.
  elif [[ "$out" != *"Schema validation errors were encountered."* ]]; then
    echo "FAIL  $f was not validated against $s" >&2
    echo "$out" >&2
    failed=1
  else
    echo "ok    $f (rejected)"
  fi
done

if [ "$failed" -ne 0 ]; then
  exit 1
fi
echo "${#valid[@]} valid and ${#invalid[@]} invalid examples behave as expected"
