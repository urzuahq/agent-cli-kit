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
| Gate | A command that judges something | The base, plus `blocking`, `findings`, `examined` |

A tool also answers `<tool> describe`, and a gate writes a receipt for each run. Both are in the
RFC.

## How a tool conforms

Validate the tool's own output against the files in [`schemas/`](schemas), in the tool's own tests:
`report.schema.json` for a base report, `gate-report.schema.json` for a gate report,
`describe.schema.json` for `describe`. The schemas have a `$id` under
`https://raw.githubusercontent.com/urzuahq/agent-cli-kit/main/schemas/`, and they `$ref` each other
by relative path. [`examples/`](examples) shows what passes and what does not.

## Run the check locally

```sh
make check
```

This validates every file in `examples/valid/` and confirms that every file in `examples/invalid/`
is rejected. The schema is chosen from the filename: `<schema>.<case>.json`. It needs `uvx` or
`pipx`, and runs a pinned `check-jsonschema`.

## Deferred

No Rust crate, no shared library, and no conformance runner that executes a tool. Both are
deliberately left until a second Rust tool, and a third conforming tool, justify them. See the open
questions in the RFC.
