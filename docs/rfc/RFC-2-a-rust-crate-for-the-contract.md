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

- `ActionInput { placeholder, flag, means }` and `NextAction { command, reason, inputs }`, plain
  data a tool builds
- `NextActionKeys`, built from an `Option<NextAction>`. It always serializes all three keys,
  `next_action`, `next_action_reason` and `next_action_inputs`, byte for byte what urzua prints
  today: two nulls and an empty array when there is no action. The crate flattens nothing itself.
  A tool may serialize `NextActionKeys` as it is, or copy its three values into fields of its own,
  as urzua's one wrapper does under its ADR-46 amendment
- `Severity`: `error`, `warning`, `info`, ordered so that `error` is greater than `warning` and
  `warning` greater than `info`
- `Examined`: a map from a unit name to a count
- `CheckKind`: `lint`, `format`, `types`, `test`, `build`, `records`, `other`
- `Profile`: `base`, `gate`, `exempt`
- `System`: 0, 1 or 2, as `describe` prints it
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
fields. The crate has no generic `Finding<X>`: urzua pointed out that it would be the rejected
envelope under another name. A tool may also ignore `Finding` and keep its own struct, as urzua
will.

**The receipt**, behind a feature named `unstable-receipt`: `Receipt<R>`, `ReceiptCheck` and
`ResultWord`. The receipt schema is a draft, and the feature name says the types can change in any
release until it is not. `Receipt` is generic over the report it embeds, a check's `status` is a
string and its `scope` is a JSON object with a `kind`, so that no tool's own types enter the crate.

**The schemas as text.** The crate embeds the five schema files and exposes each as a `&'static str`
constant, with the version they came from. This needs no dependency. A tool's lockfile then pins the
schemas, and a tool's test can write them to a directory for a validator outside Cargo.

**Two test helpers.**

- `assert_contract(profile, &value, exit_code)` checks the contract's own rules on a serialized
  report, with no validator. For either profile: `status` and the three next-action keys are
  present; `next_action_reason` is null exactly when `next_action` is; `error` appears only on a
  `not-run` report; the exit code is 2 exactly when `status` is `not-run`. For the gate profile it
  adds: `blocking`, `findings` and `examined` are present unless the report is `not-run`; `blocking`
  is true exactly when the exit code is 1; a `not-run` report is not blocking. The rules that tie a
  report to its exit code are ones no schema can express. Each rule comes from RFC-1 §1 or §2. One
  is read from two sentences there: a `not-run` report exits 2, and exit code 2 means the command
  could not run.
- `assert_conforms(Schema::GateReport, &value)`, behind a feature named `validate`, validates a
  value against the embedded schemas with a JSON Schema 2020-12 validator and prints its errors. The
  feature is off by default, and a tool turns it on only as a dev-dependency. It is not in the first
  release (§3).

**No report type and no report trait.** A tool's report stays its own struct. Both tools were asked
and both said no to a trait. garita said it saves less code than it costs. urzua has its own, tied
to its own notice type, and said two traits would be worse than none. The crate has no generic
report or envelope type.

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

Default features depend on `serde` and `serde_json` and nothing else: no C dependency, and no
build script of the crate's own. The crate declares `#![forbid(unsafe_code)]`, as every urzua crate
does. Its minimum Rust version is 1.87 and its edition is 2021, which both tools can build. Its
licence is MIT, the repository's. Both tools run a check for unused dependencies, so the crate
declares nothing it does not use.

The `validate` feature may add a validator only if every crate it pulls in is under a licence both
tools allow (MIT, Apache-2.0, Apache-2.0 WITH LLVM-exception or Unicode-3.0) and builds on Rust
1.87. Both tools check licences and sources for dev-dependencies too.

The validator considered was the `boon` crate, version 0.6, which the urzua thread named. Its
dependency tree was resolved on 2026-11-23 and does not meet those conditions as it stands. One
crate in it, `borrow-or-share`, is under MIT-0 alone, which neither tool's licence list allows. The
newest `icu` crates it resolves to need Rust 1.88. A tool can work around both in its own
repository, with a licence exception and a pinned lockfile, and that is each tool's decision. The
crate cannot make that decision for them, so the first release has no `validate` feature. It ships
the schema text and `assert_contract`, and each tool goes on validating its output in its own way.
The feature is added when a validator's tree passes both tools' checks unchanged.

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
- A schema release never waits for a crate release. The schemas are tagged first. The crate follows
  with a release that embeds the new files. A pull request that changes a schema does keep the
  crate's code and tests passing (§6), which is a change in the same pull request, not a
  publication.
- A crate release may only embed schema files that are identical to a tagged schema release or
  release candidate. CI checks this against `schemas/SHA256SUMS` at that tag.

### 6. How it stays in step with the schemas

The crate is tested against the schemas. It is not generated from them.

The crate's own tests use a JSON Schema validator as a dev-dependency of this repository, with the
versions pinned in a committed lockfile. A dev-dependency is not part of what a consuming tool
builds or checks, so the limits of §3 do not apply to it. The minimum Rust version is checked by
building the library alone, without its tests.

- Every value the crate's own types can serialize is validated against the embedded schema: the
  `not-run` report, `describe`, the finding, the receipt, and each leaf type inside a minimal
  report.
- Every `describe` and `receipt` file in `examples/valid/` must deserialize into the crate's type
  and serialize back to the same JSON.
- Every finding inside a valid gate-report example must deserialize into `Finding`. A tool's extra
  keys are ignored there, so this checks the contract's keys and not a round trip.
- `assert_contract` must pass on every valid report example, base and gate, with the exit code its
  `status` and `blocking` imply, and must fail on a report built to break each of its rules.
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
serialize to the contract.

urzua has said what it would take: `ActionInput` and `NextAction`, the exit-code mapping, the
`not-run` word and report, `Examined`, and every `describe` type, which its planned `describe`
command would build on. It takes `Severity` if the type is ordered, because its own has a
comparison the kit's must support. Its finding, its suggested actions, its notices, every report
struct and its `Report` trait stay its own. It would move its conformance test from the vendored
copy to the embedded schemas once a release carries them.

### 8. Order of work

1. This RFC is accepted.
2. The crate lands in this repository at `0.1.0`, unpublished, with the tests of §6.
3. garita and urzua each try it from a local path on a branch and report what is wrong. Neither can
   merge that branch, because both deny any source but crates.io.
4. `0.1.0` is published. Each tool then depends on it with a requirement on the `0.1` series, so a
   breaking change is a new minor. A tool's release that needs a kit version waits until that
   version is on crates.io.

The schemas' `v1.0.0` tag does not depend on any step here.

## Open questions

- **Who publishes.** Publishing to crates.io claims a public name and cannot be undone. The
  maintainer decides whether to publish, under which account, and how CI is trusted to do it.
- **A shared fingerprint function.** garita hashes the rule, the file and the message, never the
  line or the column, and offered the function. urzua keeps its own finding, so one tool would use
  it. It is left out until a second tool wants the same fingerprints.
- **The `validate` feature.** Added when a validator's dependency tree passes both tools' licence
  and Rust version checks unchanged (§3).
- **When the receipt types lose `unstable`.** With the receipt schema, when RFC-1's draft marker is
  removed. garita writes real receipts now and reports three things from use: `tool_version` is
  always null so far, a check that never ran still needs an `output` path, and computing `worktree`
  has a cost that may make it optional.
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
