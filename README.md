# agent-cli-kit

The agent CLI contract for the `urzuahq` tools: what a command line tool prints and returns so that
an agent, or a control plane such as `garita`, can read it without a per-tool parser. This
repository holds the contract record, JSON Schemas, example reports, and a CI check that the
examples validate. The record is
[RFC-1](docs/rfc/RFC-1-the-agent-cli-contract.md). The contract is version 1.0.

## The two layers

| Layer | Applies to | Required |
|---|---|---|
| Base | Any command that reports a result | `status`, `next_action`, `next_action_reason`, `next_action_inputs`; one JSON object on stdout; exit 0, 1 or 2 |
| Gate | A command that judges something | The base, plus `blocking`, `findings`, `examined` (not required when `status` is `not-run`) |

A tool also answers `<tool> describe`, and a gate writes a receipt for each run. Both are in the
RFC.

## How a tool conforms

Validate the tool's own output against the schemas, in the tool's own tests: `report.schema.json`
for a base report, `gate-report.schema.json` for a gate report, `describe.schema.json` for
`describe`. [`examples/`](examples) shows what passes and what does not.

Vendor the schemas from a release tag. Tests then run against the local copy and need no network.

```sh
(
  set -eu
  tag=v1.0.0
  dest=tests/contract
  tmp="$(mktemp -d)"
  git clone --quiet --depth 1 --branch "$tag" https://github.com/urzuahq/agent-cli-kit "$tmp"
  mkdir -p "$dest"
  rm -f "${dest:?}"/*.schema.json
  cp "$tmp"/schemas/*.schema.json "$tmp"/schemas/SHA256SUMS "$dest"/
  printf '%s %s\n' "$tag" "$(git -C "$tmp" rev-parse HEAD)" > "$dest/VERSION"
  rm -rf "$tmp"
)
```

The subshell stops at the first failure, so a tag that does not exist leaves the old copy in place.

The schemas `$ref` each other by relative path, so point the validator's base URI at the vendored
directory. Their `$id` is a name, not where a test should fetch from.

Check the copy in two places. Locally and offline, it must match its own checksums:

```sh
(cd tests/contract && sha256sum -- *.schema.json | diff - SHA256SUMS)
```

In CI, it must also match the release it claims to be:

```sh
cd tests/contract
read -r tag commit < VERSION
curl -fsSL "https://raw.githubusercontent.com/urzuahq/agent-cli-kit/$commit/schemas/SHA256SUMS" \
  | diff - SHA256SUMS
```

To move to a newer release, run the vendoring commands again with the new tag and commit the result.

## Releases

A release is a tag `v<major>.<minor>.<patch>`; `<major>.<minor>` is the `contract_version` a tool
prints. A patch changes nothing a schema accepts, a minor adds optional keys or list values, and a
major may break. The
receipt schema is a draft and may change in any release. The rules are in RFC-1 §4.

## Run the check locally

```sh
make check
```

This validates every file in `examples/valid/`, confirms that every file in `examples/invalid/`
is rejected, and checks `schemas/SHA256SUMS`. After changing a schema, run `make sums`. The schema
is chosen from the filename: `<schema>.<case>.json`. It needs `uvx` or `pipx`, and runs a pinned
`check-jsonschema`.

## Deferred

No Rust crate, no shared library, and no conformance runner that executes a tool. Both are
deliberately left until a second Rust tool, and a third conforming tool, justify them. See the open
questions in the RFC.
