---
Stable-Id: 01M85BC4GP8W2DRH6E7SFN6BD2
Status: Accepted
Date: 2026-11-23
Accepted-on: 2026-11-23
Author: beauwilliams
---
# 3 — The run profile: a gate that runs other checks

## Summary

This RFC adds a third profile to the contract, the **run profile**, for a command that runs other
checks and returns one verdict. It is the gate profile plus a list of the checks that ran and the
facts that say what the run was of. It also adds one optional key to the finding, names how a
wrapped tool's rule ids are written, and states how a command accepts the scopes it declares.

The maintainer ruled on 2026-11-23 that garita defines no output or input contract: the contracts
are this repository's, and garita implements them. garita's report already prints every key this
RFC defines. So the RFC takes what garita prints, decides it item by item, and gives it a schema.
It ships as contract version 1.1.

## Motivation

**A runner's report has no schema today.** garita's report carries `checks`, `trigger`, `commit`,
`tree`, `scope` and `receipt`, and a `check` on each finding. They validate only because the gate
profile allows unknown keys. Nothing tests them, and a second runner would have to copy them from
garita's records.

**They cannot be added to the gate profile.** urzua's report has its own `scope` key, with another
shape (`examples/valid/gate-report.urzua-shape.json`). A `scope` defined on the gate profile would
make urzua's conforming report stop conforming. A separate profile leaves every existing gate
report as it is.

**The receipt already holds the same list.** Each entry of the receipt's `checks` has a `name`,
`kind`, `status`, `duration_ms` and `examined`. The run report's entries hold the same five facts.

**Inputs are part of the contract too.** `describe` lets a command declare the scopes it accepts,
`paths` and `base-ref`, and says nothing about how they are passed. A runner that calls a native
tool needs that written once.

## Proposal

### 1. The run profile

A command whose `describe` profile is `run` prints a gate report with these keys added.
`schemas/run-report.schema.json` is the gate schema plus them. As in the gate profile, the keys
marked required are required unless `status` is `not-run`. The profile names the report a command
prints, not what the command does: a command that selects no checks of its own, such as one that
inspects the runner's setup, may print a run report whose `checks` is empty.

| Key | Type | Required | Meaning |
|---|---|---|---|
| `checks` | array | yes | One entry per check the run selected, skipped ones included, in the order the run took them. Empty when nothing was selected. |
| `trigger` | string or null | no | What started the run: `commit`, `push`, `ci` or `merge`. Null when the run could not start or the command has no trigger. |
| `commit` | string or null | no | The commit the run was of, a full hash, or null when there is none yet. |
| `tree` | string or null | no | The git tree the run was of, a full hash. Null when the run could not start. |
| `scope` | object or null | no | What the run was limited to (§2). Null when the run could not start. |
| `receipt` | string or null | no | The repository-relative path of the receipt this run wrote. Null when none was written. |

Each entry of `checks`:

| Key | Type | Required | Meaning |
|---|---|---|---|
| `name` | string | yes | The check's name in the runner's configuration. |
| `kind` | string | yes | `lint`, `format`, `types`, `test`, `build`, `records` or `other`. |
| `status` | string | yes | `pass`, `warn`, `fail`, `skipped` or `not-run`. |
| `duration_ms` | integer | yes | How long the check ran. |
| `examined` | object | yes | A count per unit, as in the gate profile. |
| `rerun` | string or null | no | The one command that runs this check again. |
| `suppressed` | object | no | Findings left out of the verdict, as a count per severity (§3). |

A run report's own `status` is `pass`, `warn`, `fail` or `not-run`. RFC-1 keeps `status`
tool-defined for the base and gate profiles, and that does not change. The run profile fixes the
words because a reader of a runner compares one check with another and one runner with another,
and cannot do that with words it has to learn per tool.

The maintainer decided this on 2026-11-23: the words are fixed (see Revisions). `skipped` is a
check's word only; a report is never `skipped`. This narrows RFC-1's tool-defined `status` for the
run profile alone. A command in the base or the gate profile still chooses its own words, so
urzua's reports are unaffected.

### 2. Scope

`scope` is an object with a required `kind`: `staged`, `changed`, `affected`, `all` or `named`.
`named` is a run whose caller listed the files itself, whatever the trigger; the other four say how
the runner chose them. It may carry `files`, an array of repository-relative paths, and `packages`,
an array of package names. The same shape is the `scope` of a receipt's check, which the draft
receipt schema already requires to be an object with a `kind`.

### 3. Suppressed findings

A runner may be configured to leave a check's findings below a severity out of the verdict. When it
does, the check's entry carries `suppressed`, an object from a severity (`error`, `warning`, `info`)
to the number of findings left out. The findings themselves are not printed.

This is taken into the contract, not left to the runner, for one reason: a reader must be able to
tell a check that found nothing from a check whose findings were hidden. RFC-1 already says a count
of zero must not be read as a pass. How a runner is configured to suppress is its own interface.

### 4. `check` on a finding

`finding.schema.json` gains one optional key, `check`, a string: the `name` of the entry in `checks`
that produced the finding. Any profile may use it. In the run profile, a `check` names an entry that
exists in the same report, and a finding about the run itself, which no check produced, has no
`check`. A schema cannot state the first rule, so it is one a tool's own tests check.

garita 0.1 prints `check: "garita"` on findings about the run itself. It stops doing so in the
release that adopts this profile. This is the one key the profile takes away from what garita
prints today.

### 5. Rule ids of a wrapped tool

A runner reports findings that the tools it wraps printed. Such a finding's `rule` is
`<source>/<rule>`. `<source>` is the runner's name for what produced the finding: the wrapped
tool's name, or the name of the parser that read its output when the runner does not know which
tool the command is. `<rule>` is the id as the tool prints it, which may itself contain `/`. The
prefix is required, because two tools may use the same id for different rules.

A finding the runner raises itself, about a tool's run or about the run as a whole, has a rule id
of the runner's own choosing, with a prefix or without. Those ids are the runner's content, as
urzua's rules are urzua's. The contract fixes the form above and no list. A reader cannot tell from
an id alone which kind of finding it is, and does not need to: the prefix exists so that ids from
different tools never collide.

### 6. How a command accepts its scopes

A command that declares a scope in `describe` accepts it as follows.

- `paths`: as trailing positional arguments, repository-relative. No paths means the command's own
  default.
- `base-ref`: as `--base <ref>`.

urzua's `check` already takes both this way. A runner that calls a command it knows only through
`describe` passes scopes in this form and no other. A command that takes paths in another form does
not declare `paths`. garita's `run` is one: its positional arguments are check names, so it takes
files through a flag and declares only `base-ref`.

### 7. What is not taken

Each of these was in garita's records or output as a shape or a convention. They are not part of
the shared contract, and garita's records stop presenting them as that.

Not taken does not mean removed. The maintainer refined the ruling on 2026-11-23: a tool may print
keys beyond its profile, and those are that tool's own extended contract, the tool's to define and
document. So garita may keep any item below, in its output and in its records, as long as its
records call it garita's and not the shared contract, and as long as it does not contradict the
base layer or the run profile. A key becomes shared when a second tool needs it, and is then
proposed here.

- **A risk object and a per-check verdict** (`risk`, `system`, `verdict`). Not built.
- **A plugin protocol** (JSON on stdin, a result on stdout). Not built.
- **A fingerprint algorithm.** The contract says a fingerprint is stable across runs and treats it
  as an opaque string. How a tool computes it is that tool's behaviour.
- **The layout of a finding's `message`.** A message is text for a reader. A tool may lay it out as
  it likes and promises no layout. Output a reader should parse gets a key.
- **What a tool's `next_action` holds and how its reason is worded.** RFC-1 says it is one command
  to run next. Which command is the tool's decision.
- **A list of `examined` unit names.** The map is open. RFC-1's names are examples.
- **A tool's own flags and configuration file, and how a runner invokes a tool through its own
  configuration.** A runner that wraps a tool with a configured command line, placeholders and
  added flags is using its own interface. §6 covers the other case only: a command called from
  what its `describe` declares.

### 8. The receipt

The receipt stays a draft, and this RFC does not change its schema. Its field list lives in RFC-1
§5 and `receipt.schema.json`, and no other record restates it. Its `report` stays a gate report,
which a run report also is, so a receipt written by a gate that runs no checks stays valid. A
runner's receipt embeds a run report, and each of its checks takes its `scope` from §2.

### 9. What changes in RFC-1

When this RFC is accepted, RFC-1 gains a revision row pointing here, and its text is brought into
line. Its Summary says the contract has two layers and then names a third profile. §3 lists `run`
among the profiles and says `contract_version` is `"1.1"` from this release. §6 lists
`run-report.schema.json` among the schemas. Nothing in RFC-1's base layer or gate profile changes.

Outside the record, `describe.schema.json` adds `run` to its `profile` list, `finding.schema.json`
adds `check`, and the README's table of layers and its statement of the contract's version follow.

### 10. Version and release

This is contract version 1.1: a new profile value, a new schema, and one optional key on the
finding. No output that conformed to 1.0 stops conforming. Every JSON Schema keyword the new schema
uses is already in the list of `scripts/check_keywords.py`.

It ships as a release candidate first. garita validates its report against the run schema, and
`v1.1.0` is tagged when that passes, as `v1.0.0` waited for urzua.

### 11. What each tool changes

**garita** adds `describe`, which it does not have yet, and declares each command that prints its
report type as profile `run`, including the two that select no checks. It validates its reports
against `run-report.schema.json`, drops `check` from findings about the run itself (§4), and
rewrites the parts of its records that restate or extend the contract to cite this repository. Its
output keeps every other key it prints today.

**urzua** changes nothing. Its `check` is a gate, not a runner.

## Open questions

- **Fixing the status words of a profile. Answered.** They are fixed for the run profile, as §1
  says (see Revisions).
- **Whether a tool's own flags and configuration are outside the contract. Answered.** They are
  the tool's interface, as §7 says (see Revisions).
- **`trigger` and `scope.kind` as closed lists.** They are garita's words today, and garita has
  confirmed it prints no others. A second runner with another trigger would need a minor release
  to add a value.

## Non-goals

- Changing the base or gate profile, or anything a 1.0 report must contain.
- Defining how a runner decides its verdict: which outcome wins, what blocks, what is demoted.
- A list of rule ids, units or messages.

## Revisions

| Date | Change |
|---|---|
| 2026-11-23 | Accepted by the maintainer. Their words, in answer to a numbered list whose first item was "Accept RFC-3": "I accept 1". Three points stay open and are theirs: whether the run profile fixes its status words (§1), whether a runner's own configuration and flags are outside the contract (§7), and whether the ruling that a tool defines no contract covers tools other than garita. The dates of the ruling and of this record were first written as 2026-11-24 in error and are corrected here. |
| 2026-11-23 | The maintainer refined the ruling behind this RFC. Their words: "each tool can have extra keys I guess, and that's that tool's specific extended contract", and "the CLI kit is for contract but yeah we would customise it per the one". The layers that answer was given against: the base contract is what every tool prints, and is this repository's; a profile is the base customised for one kind of command, also this repository's, written with the tool; a tool's extra keys are allowed and are that tool's own extended contract, which must not contradict the base or its profile; a tool's flags and configuration file are its interface. This applies to every tool, not to garita alone. §7 now says that an item not taken may stay in garita as garita's own. What this RFC took stays taken. Whether the run profile fixes its status words is still open. |
| 2026-11-23 | The maintainer decided the status words. Offered fixed words, free text as before, or a list that accepts other words, they chose fixed. Their words, dictated and transcribed, with the bracketed words supplied by the relay: "Maybe we don't do open strings and do [it properly] now. Just do fixed schema [for] now yeah". The run report's `status` is `pass`, `warn`, `fail` or `not-run`, and a check's adds `skipped`. `v1.1.0-rc.1` accepted any string; the lists are closed from `v1.1.0-rc.2`. |
| 2026-11-24 | **Proposed amendment, not yet accepted.** §2 gains a fifth `scope.kind`, `named`, for a run whose caller listed the files. garita's first conforming reports showed the gap: a run given `--files` printed `staged`, the trigger's word, for files that were not staged. Adding a value to this list before `v1.1.0` is tagged costs no released tool anything. |

## References

- RFC-1, the agent CLI contract
- garita's own RFC-1, RFC-2 and RFC-3
