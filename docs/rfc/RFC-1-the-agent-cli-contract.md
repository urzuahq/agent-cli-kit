---
Stable-Id: 01M838QGHE1E3K5ZB49PWEXY6V
Status: Draft
Date: 2026-11-23
Author: beauwilliams
---
# 1 — The agent CLI contract

## Summary

This RFC states one contract for the command line tools an agent runs, and ships it as JSON Schemas
and a corpus of example reports. The contract has two layers. The **base layer** applies to any
command that reports a result: stdout is one JSON object, the exit code is 0, 1 or 2, and three
`next_action` keys say what to do next. The **gate profile** applies to a command that judges
something: it adds `blocking`, `findings` and `examined`. A tool also answers `describe`, which
names its commands, their profile and whether they write. A **receipt** is the record a gate writes
for each run.

The contract is urzua's existing output shape, written down. Version 1.0 is schema-only. A tool
conforms by validating its own output against the schemas in its own tests.

## Motivation

**Two tools, one spirit, different details.** urzua and garita both print JSON reports for agents
and both use the exit code as the gate. They agree on what a report is for and differed in the
details: urzua counts what it looked at in `files_examined` where garita's first design wrote
`examined`, and that design gave exit codes 1 and 2 the opposite meanings. Each difference is small
and each one costs a parser.

**A control plane needs one stated contract.** garita runs tools and returns one verdict. To read a
tool's output unchanged, without an adapter per tool, it needs to know which keys are always there,
what they mean, and what an exit code promises. Today that knowledge lives in urzua's reference
pages, which is prose, not something a test can check.

**Start from what ships.** urzua 0.4.13 already prints `status`, `next_action`,
`next_action_reason`, `next_action_inputs`, `blocking` and `findings`, and exits 0, 1 or 2. The
contract takes those as they are. The released tool then changes only by addition, and every
existing consumer keeps working.

## Proposal

### 1. The base layer

Every command that reports a result obeys these rules.

- **Output.** stdout is exactly one JSON object, including when the command fails. Everything else
  goes to stderr. No flag is needed to get JSON. A command that streams or serves is exempt: a
  long-running server, a line-per-event stream, a command whose product is a file or a page. Such a
  command is declared `exempt` in `describe`.
- **Exit codes.** `0`: ran, and nothing blocks. `1`: ran, and something blocks. `2`: could not run.
- **Required keys.**

  | Key | Type | Meaning |
  |---|---|---|
  | `status` | string | Tool-defined per command, except `not-run`, which is reserved: the command could not run, and it exits 2. |
  | `next_action` | string or null | One command to run next. |
  | `next_action_reason` | string or null | Why, from counts. `null` exactly when `next_action` is `null`. |
  | `next_action_inputs` | array of objects | One entry per `<...>` placeholder the command carries. Empty when it runs as printed. |

  Each entry of `next_action_inputs` has three required strings: `placeholder` (the word as printed
  in `next_action`, always written `<...>`), `flag` (the option it belongs to, such as `--reason`)
  and `means` (what to put there).

- **Optional keys.** `error` (string): present when `status` is `not-run` because the run could not
  start. `notices`: an array of `{severity, subject, message}`. `schema_version`: an integer, the
  tool's own report schema. `tool`: `{name, version}`.
- **Unknown keys** are allowed and readers ignore them. This is what lets a tool keep its own fields
  beside the contract's.

`schemas/report.schema.json` encodes the two conditional rules: `next_action_reason` is null exactly
when `next_action` is null, and `error` present requires `status` to be `not-run`.
`examples/valid/report.urzua-inputs.json` is a report urzua 0.4.13 printed, with one input.

### 2. The gate profile

A command that judges something adds three keys to the base. All three are required unless `status`
is `not-run`: a gate that could not run has judged nothing, so it may print the base report alone,
as urzua does (`examples/valid/gate-report.urzua-not-run.json`). A `not-run` report never carries
`blocking: true`, because it exits 2 and `blocking` is true exactly when the exit code is 1.

- `blocking`: boolean, true exactly when the exit code is 1.
- `findings`: an array of findings.
- `examined`: an object mapping a unit name (`files`, `tests`, `packages`, `records`) to a
  non-negative integer. An object whose counts are all zero means the command ran on nothing, which
  a reader must not take as a pass.

A finding has required `rule` (a stable id), `severity` (`error`, `warning` or `info`) and
`message`. It has optional `file` (repository-relative, or null), `line` and `column` (integers of
at least 1, or null), `fix` (the tool's own command that fixes it) and `fingerprint` (stable across
runs for the same finding).

Whether a finding blocks is the tool's decision, reported only through `blocking` and the exit code.
`status` stays tool-defined. Findings are open like reports: a tool may add keys.

### 3. describe

`<tool> describe` prints one JSON object:

- `name`, `version`
- `contract_version`: a string `"<major>.<minor>"`, here `"1.0"`
- `system`: 0, 1 or 2. 0 is deterministic compute, 1 a decision model, 2 LLM inference
- `commands`: an array of `{name, profile, safe, scopes, metrics}`, where `profile` is `base`,
  `gate` or `exempt`; `safe` is true when the command writes nothing; `scopes` lists what it accepts
  (`paths`, `base-ref`); and `metrics` lists the numbers it reports (`duration_ms`, `files`)

`safe` is what lets a future checker run a command without risk: it runs only commands marked safe.

### 4. Versioning

A reader compares the major of the tool's `contract_version` with its own. A different major means
the reader reports the tool as `not-run` and does not guess. A minor release only adds optional
keys, so a reader written for 1.0 reads 1.3 output unchanged.

### 5. The receipt

A receipt is the record a gate writes for each run. It is a draft and is expected to change while
garita's first phase is built.

The field list follows garita RFC-1 §8: `receipt_version` (integer), `run_id` (a ULID),
`started_at` and `finished_at` (RFC 3339 UTC), `trigger`, `commit` (string or null), `tree` (a git
tree hash), `worktree` (a tree hash computed from the working files, which is what the checks saw),
`dirty` (boolean), `config_hash`, `machine`, `tool` (`{name, version}`), `result`, `checks` and
`report`.

`worktree` is how a reader tells whether a check ran after the last edit: it did if the working
files still hash to the receipt's `worktree`. That answer needs no comparison of clocks.

`result` is `PASSED`, `WARNED` or `FAILED`, the vocabulary of the in-toto test-result predicate, so
a receipt can later be wrapped in a signed statement. Each entry of `checks` has `name`, `command`,
`scope` (an object with a `kind`, such as `{"kind": "affected", "packages": [...]}`), `tool_version`
(string or null), `started_at`, `finished_at`, `duration_ms`, `exit_code` (the check's own exit
code, or null when it was killed or never started), `status` and `examined`. `report` is the
gate-profile report the run printed.

A run that could not run still writes a receipt. Its `report` has `status` `not-run` and its
`result` is `FAILED`: a gate that could not run is not evidence of a pass.

### 6. Conformance

Conformance is two artifacts and no runner. `schemas/` holds JSON Schema 2020-12 files for the base
report, the finding, the gate report, `describe` and the receipt. `examples/` holds a corpus: valid
examples that must validate, and invalid examples that must not, each violating one rule and named
for it. CI in this repository checks that the corpus behaves as stated.

Each tool validates its own output against the schemas in its own tests. The contract does not
execute other people's binaries: commands can write, and a runner that executes arbitrary commands
is unsafe.

### 7. What each tool changes

**urzua**, additively, in a minor release:

- `examined: {files: N}` beside the existing `files_examined`
- `schema_version`
- a `describe` command

Nothing is renamed or removed. `examples/valid/gate-report.urzua-shape.json` is a report in
urzua's current shape with those additions.

**garita** adopts the contract from its first release. Its `status` words are `pass`, `warn`,
`fail` and `not-run`.

## Open questions

- Does `examined` replace `files_examined` in a later major version of urzua's report?
- Should a base-layer command carry `tool` and `schema_version` as required keys? They are optional
  in 1.0 because urzua does not print `tool` today.
- What is the receipt's final shape?
- When is a shared library justified? Proposed trigger: a second Rust tool would copy the same types
  verbatim.
- When is a live conformance checker justified? Proposed trigger: a third conforming tool.

## Non-goals

- A shared `status` enum. Status is tool-defined.
- A shared code library in version 1, in Rust or any other language. The schemas are the contract.
- A runner that executes arbitrary binaries.
- Anything about how a tool computes its findings.

## References

- urzua RFC-3 and ADR-46
- garita RFC-1 and RFC-2
