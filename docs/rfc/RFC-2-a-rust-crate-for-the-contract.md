---
Stable-Id: 01M83QAAQRMZYJAEP9PWXNY5WX
Status: Draft
Date: 2026-11-23
Author: beauwilliams
---
# 2 — A Rust crate for the contract

## Summary

This RFC adds a Rust crate, `agent-cli-kit`, to this repository. The crate holds the parts of the
contract that are the same in every Rust tool: the small types, the exit codes, the `describe`
output, the finding, the receipt, and helpers that check a tool's output against the contract. It
does not hold a report type. Each tool keeps its own report struct.

The schemas stay the source of truth. The crate embeds them, is tested against them, and is
versioned on its own so that it can follow a schema release and never has to hold one up.

This reverses one point of RFC-1, which deferred a shared library until a second Rust tool would
copy the same types. The maintainer decided on 2026-11-23 not to wait: urzua and garita are both
Rust and both emit the contract, and a consumer outside the org is ready to adopt it.

## Motivation

**The same types now exist twice.** garita wrote Rust types for the report and the receipt, and
urzua has its own. Both declare a next-action input with `placeholder`, `flag` and `means`. Both
declare the severity words, the count of what was examined, and the mapping from a result to exit
code 0, 1 or 2. urzua is about to write the `describe` types, and garita will need the same ones.
Each copy is a place where the two can drift from the schema and from each other.

**The schema catches a mismatch late.** Both mismatches fixed before the first release candidate
were found by running a real tool against the schemas. A type that cannot be built in a
non-conforming shape catches the same mistake when the tool compiles.

**Vendoring is manual for a Rust tool.** RFC-1 has each tool commit a copy of the schemas with a
checksum file and a version file, and compare checksums in CI. A crate that embeds the schemas is
pinned by the tool's lockfile, works offline, and needs no drift check.

## Proposal

### 1. What the crate holds

**Leaf types**, identical in every tool, each with `serde` support:

- `ActionInput { placeholder, flag, means }` and `NextAction { command, reason, inputs }`
- `Severity`: `error`, `warning`, `info`
- `Examined`: a map from a unit name to a count
- `CheckKind`: `lint`, `format`, `types`, `test`, `build`, `records`, `other`
- `Profile`: `base`, `gate`, `exempt`
- `ToolInfo { name, version }`
- `ObjectId`: a git object hash, 40 or 64 lowercase hex characters, checked when built and
  serialized as a plain string
- `ExitCode`: `Ok` is 0, `Blocking` is 1, `NotRun` is 2, and `exit_code(not_run, blocking)`, the one
  place the mapping is written
- `NOT_RUN`, the reserved status word, and `CONTRACT_VERSION`, the string a tool prints in
  `describe`

**The `not-run` report.** `NotRunReport { error, next_action }` is the one whole report the crate
owns, because its shape is the same in every tool: `status` is `not-run`, and it exits 2.

**`describe`.** `Describe` and `Command`, complete. RFC-1 says this repository owns the `describe`
field list, so these types are that list in Rust.

**The finding.** `Finding` has exactly the contract's keys: `rule`, `severity`, `message`, `file`,
`line`, `column`, `fix` and `fingerprint`. `line` and `column` are non-zero integers, so a zero
cannot be built. A tool that prints more keys puts `Finding` inside its own struct, beside its own
fields. The crate has no generic `Finding<X>`. It also offers `fingerprint(rule, file, message)`, so
that two tools can produce the same fingerprint for the same finding. Using it is a tool's choice;
the contract only asks that a fingerprint be stable across runs.

**The receipt**, behind a feature named `unstable-receipt`: `Receipt<R>`, `ReceiptCheck` and
`ResultWord`. The receipt schema is a draft, and the feature name says the types can change in any
release until it is not. `Receipt` is generic over the report it embeds, a check's `status` is a
string and its `scope` is a JSON value, so that no tool's own types enter the crate.

**The schemas as text.** The crate embeds the five schema files and exposes each as a `&'static str`
constant, with the version they came from. This needs no dependency. A tool's lockfile then pins the
schemas, and a script can still be pointed at them.

**Two test helpers.**

- `assert_contract(&value, exit_code)` checks the contract's own rules on a serialized report, with
  no validator: `blocking` is true exactly when the exit code is 1; `next_action_reason` is null
  exactly when `next_action` is; a `not-run` report has exit code 2 and is not blocking; `findings`
  and `examined` are present unless the report is `not-run`. Several of these tie the report to the
  exit code, which no schema can express.
- `assert_conforms(Schema::GateReport, &value)`, behind a feature named `conformance`, validates a
  value against the embedded schemas with a JSON Schema 2020-12 validator and prints its errors. The
  feature is off by default, and a tool turns it on only as a dev-dependency.

**No report type and no report trait.** A tool's report stays its own struct. garita was asked and
said a trait saves less code than it costs; what saves work is the two helpers above. The crate has
no generic report or envelope type, and nothing composed with `serde(flatten)`.

### 2. What it does not hold

- **A report struct or a generic envelope.** urzua tried one and rejected it in its ADR-46: a
  shared struct flattened into a report that already owns a `status` field printed the key twice.
- **A `status` enum.** Status is tool-defined in RFC-1, apart from `not-run`.
- **A tool's extra finding keys.** urzua's finding carries `suggested_action` and garita's carries
  `check`. Those stay in each tool. If a tool flattens `Finding` into its own struct, keeping its
  field names clear of the contract's is that tool's job, and a test in the tool pins it.
- **A tool's verdict.** Which outcome wins, what blocks, and how a re-run command is built are each
  tool's behaviour, not the contract's.
- **Printing or process exit.** The crate returns an `ExitCode`. Writing stdout and exiting is the
  tool's.
- **A runner.** RFC-1's rule stands: the kit does not execute other people's commands.

### 3. Dependencies and Rust version

Default features depend on `serde` and `serde_json` and nothing else: no build script and no C
dependency. The crate has no `unsafe` code. Its minimum Rust version is 1.87 and its edition is
2021, which both tools can build. Its licence is MIT, the repository's.

The `conformance` feature may add a validator only if every crate it pulls in is under MIT,
Apache-2.0, Apache-2.0 WITH LLVM-exception or Unicode-3.0, and builds on Rust 1.87. Both tools check
licences and sources for dev-dependencies too. If no validator meets that, the feature is dropped
and `assert_contract` and the schema text are what the crate offers.

### 4. How it is published

On crates.io, as `agent-cli-kit`. The name is free there today. A registry release is the only form
urzua or garita can depend on: both deny git sources and allow only crates.io. A release is
published from CI on a tag, never from a developer's machine.

The crate's manifest sits at the repository root, so that the package can include `schemas/` as it
is and the embedded files are the checked ones, not a copy.

### 5. How it is versioned against the schemas

The crate has its own version and its own tags, `crate-v<version>`. Schema releases keep the tags
`v<major>.<minor>.<patch>` from RFC-1 §4.

- The crate starts at `0.1.0`. Its Rust API will change while two tools adopt it, and a `0.x`
  version says so. It moves to `1.0.0` when both tools build on it and neither has asked for a
  breaking change for one release.
- Every crate release states the contract version it implements, in `CONTRACT_VERSION`, in its
  README, and in a table in this repository's README.
- A schema release never waits for the crate. The schemas are tagged first. The crate follows with
  a release that embeds the new files.
- A crate release may only embed schema files that are identical to a tagged schema release or
  release candidate. CI checks this against `schemas/SHA256SUMS` at that tag.

### 6. How it stays in step with the schemas

The crate is tested against the schemas. It is not generated from them.

- Every value the crate's own types can serialize is validated against the embedded schema: the
  `not-run` report, `describe`, the finding, the receipt, and each leaf type inside a minimal report.
- Every file in `examples/valid/` for a schema whose type the crate owns (`describe`, `finding`,
  `receipt`) must deserialize into that type and serialize back to the same JSON.
- Every file in `examples/invalid/` must be rejected by `assert_conforms`.
- `assert_contract` must pass on every valid report example and fail on a report built to break
  each of its rules.
- `make check` runs these with the schema checks, so a pull request that changes a schema and not
  the crate fails.

Generating the types from the schemas was considered and rejected. The schemas use `if`/`then`
rules and open objects, which generators turn into untyped values or drop. A generator would also be
a build-time dependency of every tool.

### 7. What each tool changes

Nothing, until it chooses to. The schemas and the vendored copy from RFC-1 §6 keep working, and a
tool in another language uses only those. A Rust tool that adopts the crate replaces its own leaf
types with the crate's, calls the helpers from its tests, and may replace its vendored schema
directory with the embedded schemas.

garita has said what it would take: the next-action input, `Severity`, `Examined`, `CheckKind`, the
exit-code mapping, `ObjectId`, the finding, every `describe` type, and the receipt types once they
are stable. Its report, its check entries, its status words, its trigger and scope and its verdict
logic stay its own. It keeps its committed example reports, which prove that its real types
serialize to the contract. urzua's answer is pending.

### 8. Order of work

1. This RFC is accepted, with the open questions below answered by urzua and garita.
2. The crate lands in this repository at `0.1.0`, unpublished, with the tests of §6.
3. garita, which has no released consumers, adopts it from a path or a pre-release and reports what
   is wrong.
4. `0.1.0` is published. urzua adopts it after its conformance test against the schemas has merged.

The schemas' `v1.0.0` tag does not depend on any step here.

## Open questions

- **urzua's answers.** garita has answered (§7). urzua has been asked the same questions: which
  types it would replace, whether the plain `Finding` suits a finding that carries
  `suggested_action`, and whether it wants anything beside its own `Report` trait. A type neither
  tool takes is left out.
- **The validator.** Which JSON Schema validator the `conformance` feature uses, if any meets the
  conditions in §3.
- **The fingerprint function.** garita hashes the rule, the file and the message, never the line or
  the column. Whether urzua can adopt the same function, or whether the crate should offer none,
  depends on what urzua's fingerprints must stay stable against.
- **Who publishes.** Publishing to crates.io claims a public name and cannot be undone. The
  maintainer decides whether to publish, under which account, and how CI is trusted to do it.
- **RFC-1's text.** RFC-1 lists a shared library as a non-goal of version 1 and names a trigger for
  it. When this RFC is accepted, RFC-1 gains a revision row pointing here. Its contract does not
  change.

## Non-goals

- Code in any language other than Rust. A tool in another language uses the schemas.
- Replacing the schemas as the contract. If the crate and a schema disagree, the crate is wrong.
- A shared `status` vocabulary, a generic report type, or a command runner.

## References

- RFC-1, the agent CLI contract
- urzua ADR-46
- garita RFC-1
