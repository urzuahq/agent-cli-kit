---
Stable-Id: 01M838QGHE1E3K5ZB49PWEXY6V
Status: Accepted
Date: 2026-11-23
Accepted-on: 2026-11-23
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

Version 1.1 adds a third profile on top of those two layers. The **run profile**, defined in RFC-3,
applies to a command that runs other checks and returns one verdict: it is the gate profile plus
the list of checks that ran.

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

- **Output.** stdout is exactly one JSON object, including when the command fails in a way it can
  report. No flag is needed to get JSON. A command that streams or serves, or that speaks a host's
  protocol, is exempt: a long-running server, a line-per-event stream, a hook, a command whose
  product is a file or a page. Such a command is declared `exempt` in `describe`.
- **stderr.** In version 1.0, everything but the report went to stderr. From version 1.1 a command
  that prints its report writes nothing to stderr, unless its caller asked for the tool's log.
  RFC-4 gives the rule and what is apart from it.
- **Exit codes.** `0`: ran, and nothing blocks. `1`: ran, and something blocks. `2`: could not run.
  These are the exit codes of a command that prints its report on stdout. What a hook exits with
  belongs to the host that called it, and RFC-4 says what that is.
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

- **Optional keys.** From version 1.1, `next_action_argv` (the same command as an array of its
  arguments, or null) and an `index` on each entry of `next_action_inputs`, which a 1.1 tool always
  prints, and `error_kinds` on a `not-run` report (an array of `usage`, `config`, `environment` and
  `internal`, each kind that applies). RFC-4 defines them. `error` (string): present when `status`
  is `not-run` because the run could not start. `notices`: an array of `{severity, subject,
  message}`. `schema_version`: an integer, the tool's own report schema. `tool`: `{name, version}`.
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
at least 1, or null), `fix` (the tool's own command that fixes it), `fingerprint` (stable across
runs for the same finding) and, from version 1.1, `check` (the name of the check that produced it,
in a report that lists its checks) and `fix_argv` (the `fix` command as an array of its arguments).

Whether a finding blocks is the tool's decision, reported only through `blocking` and the exit code.
`status` stays tool-defined. Findings are open like reports: a tool may add keys.

### 3. describe

`<tool> describe` prints one JSON object:

- `name`, `version`
- `contract_version`: a string `"<major>.<minor>"`: `"1.0"`, or `"1.1"` for a tool that uses
  anything version 1.1 added
- `system`: 0, 1 or 2. 0 is deterministic compute, 1 a decision model, 2 LLM inference
- `commands`: an array of `{name, profile, safe, scopes, metrics}`, where `profile` is `base`,
  `gate`, `exempt` or, from version 1.1, `run`; `safe` is true when the command writes nothing;
  `scopes` lists what it accepts (`paths`, `base-ref`); and `metrics` lists the numbers it reports
  (`duration_ms`, `files`). A command may also state its `kind`: `lint`, `format`, `types`, `test`,
  `build`, `records` or `other`, the same words a receipt uses for a check

From version 1.1, `describe` also declares the tool's inputs: `args` for the tool and for each
command, `env`, `stdin`, `config`, and `log`, with a `protocol` on each `exempt` command. RFC-4
defines them. A tool that prints `contract_version` `"1.0"` need not carry them.

`describe` is not itself a base report. On success it prints the object above, with no `status` and
no `next_action` keys, and exits 0. When it cannot run it behaves like any other command: it prints
a `not-run` base report and exits 2. A reader tells the two apart by the exit code.

`--help` and `--version` are exempt from the base layer. From version 1.1, `--version` prints
exactly `<name> <version>` and a newline, and nothing an agent needs is only in `--help`.

This record owns the `describe` field list. A tool may print other keys, as in any report, and one
that wants a key every reader can rely on proposes it here.

`safe` is what lets a future checker run a command without risk: it runs only commands marked safe.

### 4. Versioning

A reader compares the major of the tool's `contract_version` with its own. A different major means
the reader reports the tool as `not-run` and does not guess. A minor release adds only optional
keys and list values, so a reader written for 1.0 reads 1.3 output unchanged: it ignores a key it
does not know and does not guess the meaning of a list value it does not know. A reader does not
reject a tool's output for failing the reader's own, older copy of the schemas. Validation is the
producing tool's test (§6).

**Releases.** A release is a git tag `v<major>.<minor>.<patch>` on `main`. `<major>.<minor>` is the
`contract_version` a tool prints. The three numbers move as follows.

- **Patch**: nothing a schema accepts or rejects changes. A description, an example, the record's
  wording.
- **Minor**: a new optional key, or a new value in one of the contract's lists (`kind`, `profile`,
  `severity`, `system`). Output that conformed before, and used no key the contract had not yet
  defined, still conforms.
- **Major**: output that conformed, using only keys the contract defined, stops conforming, or a
  reader can no longer rely on a key it was promised. A key is renamed, made required or given a
  narrower type, or a required key stops being required.

Unknown keys are allowed, so one case sits between minor and major: a tool's own key whose name a
later minor defines with a different shape. That tool's output stops conforming although the
release is a minor. The cost is accepted and kept small: a new key is named in a pull request
against this record before it ships, and a tool that already prints that name objects there.

A schema whose title says `draft` is outside this promise: it may change in any release until the
word is removed. In 1.0 that is the receipt.

**What a change requires.** Every pull request that changes what a schema accepts adds at least one
valid example that the new rule admits and one invalid example that it rejects, named for the rule.
An invalid example must fail for that rule alone. `schemas/SHA256SUMS` is regenerated in the same
pull request, and CI fails when it is stale.

**A new JSON Schema keyword.** A tool may read the schemas with its own code, not a general
validator, and stop on a keyword it does not know. urzua's conformance test does. The schemas
therefore use a fixed list of keywords, held in `scripts/check_keywords.py`, and CI fails on any
other. A change that adds a keyword to that list is announced to the consuming tools before the
release that carries it, and that release is preceded by a release candidate. The same care applies
to a construct the schemas have not used before, such as a `null` inside an `enum`, which no check
enforces.

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
a receipt can later be wrapped in a signed statement. Each entry of `checks` has `name`, `kind`
(`lint`, `format`, `types`, `test`, `build`, `records` or `other`, so a reader knows what a pass
proves), `command`, `scope` (an object with a `kind`, such as
`{"kind": "affected", "packages": [...]}`), `tool_version` (string or null), `started_at`,
`finished_at`, `duration_ms`, `exit_code` (the check's own exit code, or null when it was killed or
never started), `status`, `examined`, `output_tail` (the last 4,000 characters of the check's
output) and `output` (the path of the full output, kept beside the receipt). `report` is the
gate-profile report the run printed.

A run that could not run still writes a receipt. Its `report` has `status` `not-run` and its
`result` is `FAILED`: a gate that could not run is not evidence of a pass.

### 6. Conformance

Conformance in version 1.0 is two artifacts and no runner. Version 1.1 adds one, described at the
end of this section. `schemas/` holds JSON Schema 2020-12 files for the base report, the finding,
the gate report, the run report, `describe`, the receipt and one line of a tool's log. `examples/`
holds a corpus: valid examples that must validate, and invalid examples that must not, each
violating one rule and named for it. CI in this repository checks that the corpus behaves as stated.

Each tool validates its own output against the schemas in its own tests. The contract does not
execute other people's binaries: commands can write, and a runner that executes arbitrary commands
is unsafe.

From version 1.1 the kit also ships `scripts/conform.py`, which a tool runs in its own CI against
its own binary. It runs only the commands that tool has declared `safe`, and checks what a schema
cannot: that stderr is empty, that the exit code agrees with the report, and that a command printed
as a string and as arguments is the same command. Passing it is part of conforming to 1.1. RFC-4
defines it.

**How a tool gets the schemas.** A tool vendors them: it commits a copy of `schemas/` from one
release tag into its own repository, together with `SHA256SUMS` and a `VERSION` file holding the tag
and the commit it points at. Its tests validate against that local copy, so they need no network and
pass in a locked, offline build. The schemas `$ref` each other by relative path, so the validator
must resolve references against the vendored directory, not against the `$id`.

Two checks keep the copy honest. Hashing the vendored schemas and comparing the result with the
vendored `SHA256SUMS` needs no network and catches a local edit or a stray schema. In CI the tool
also fetches `schemas/SHA256SUMS` at the commit named in `VERSION` and compares it with the vendored
one, which catches a copy that does not match its stated release. The commit is used, not the tag,
because a tag can be moved. Moving to a newer release is a deliberate commit that replaces the
vendored schemas.

Fetching the schemas at test time was rejected because it breaks offline builds, and a git
dependency was rejected because a tool's dependency policy may deny it. The README gives the
commands.

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
- When is a live conformance checker justified? Answered: RFC-4 brought one forward for version
  1.1, limited to a tool's own safe commands in its own CI.

## Non-goals

- A shared `status` enum. Status is tool-defined in the base layer and the gate profile. The run
  profile of version 1.1 fixes its own words (RFC-3).
- A shared code library in version 1, in Rust or any other language. The schemas are the contract.
- A runner that executes arbitrary binaries.
- Anything about how a tool computes its findings.

## Revisions

| Date | Change |
|---|---|
| 2026-11-23 | Accepted by the maintainer. Their words: "Move it to accepting? Let's unblock it". Asked directly which Status to record, they chose Accepted. The receipt (§5) stays a draft and the open questions stay open. |
| 2026-11-23 | Version 1.1, from RFC-3, accepted by the maintainer the same day: the run profile and its schema, `run` in the list of profiles, and an optional `check` on a finding. The Summary, §2, §3 and §6 say so. Nothing in the base layer or the gate profile changes. The run profile fixes its `status` words, by the maintainer's decision of the same day; `status` stays tool-defined in the base layer and the gate profile. |
| 2026-11-24 | Brought into line with RFC-4, accepted by the maintainer on 2026-11-24, which completes version 1.1. §1 now says stderr is empty from 1.1, that the exit codes are those of a command that prints its report, and names `next_action_argv`, `index` and `error_kind`; §2 names `fix_argv`; §3 says `describe` declares a tool's inputs and fixes the `--version` line; §6 names the log-line schema and the conformance runner, which reverses this record's earlier deferral of one. A tool that prints `contract_version` `"1.0"` is held to this record as it stood at `v1.0.0`. |
| 2026-11-24 | Amendment, accepted by the maintainer: new JSON Schema keywords. Asked about this rule together with an addition to RFC-4, they said: "Yes to both". §4 gains the rule that the schemas use a fixed list of keywords, checked in CI, and that adding one is announced to the consuming tools and ships in a release candidate first. The check and the README had carried it as practice since the keyword check was added. |
| 2026-11-24 | §1 names `error_kinds`, a list, where it named `error_kind`, following the amendment to RFC-4 that the maintainer accepted the same day. |

## References

- urzua RFC-3 and ADR-46
- garita RFC-1 and RFC-2
