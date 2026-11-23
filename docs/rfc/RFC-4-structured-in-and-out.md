---
Stable-Id: 01M85CY0G84WNWK7AGGYXNAQDJ
Status: Draft
Date: 2026-11-23
Author: beauwilliams
---
# 4 — Structured in and out

## Summary

The tools this contract covers are driven by machines. This RFC states one principle for them and
applies it to every surface a tool has: **everything that goes into a tool or comes out of it is
structured and declared.** Nothing an agent needs is prose, and nothing a tool accepts is
undeclared.

RFC-1 fixed stdout and left the rest open: stderr, help text, text inside the JSON, hooks, flags,
environment variables, standard input and configuration. Each open surface is where a tool came to
differ. This RFC closes them in one pass, as part of contract version 1.1, and adds a runner that
checks a tool against the contract in one place.

The maintainer's words, 2026-11-23: "it's machine driven tool, structured in and out, no
unstructured in or out. Let's just make sure it's designed like that".

## Motivation

**Open surfaces drift.** RFC-1 said "Everything else goes to stderr", and a tool printed a second
report there for a person. urzua's usage errors put the argument parser's prose, with its "Usage:"
block, into the `error` key. garita packed a failing command's output into a finding's `message`
under headings. urzua's `init` shows a menu when its input is a terminal. None of these broke a
schema, and each is something an agent has to learn per tool.

**The input side is undeclared.** `describe` names a tool's commands and says nothing of their
arguments, so an agent learns them from `--help`, which is prose.

**Conformance is asserted, not checked.** Each tool tests itself in its own way. The first two
schema defects were found only when a real tool was run against the schemas.

**Nothing has shipped that this would break.** urzua 0.4.14 does not answer `describe` yet, and
garita's is on a branch. Both tools were asked what each rule here costs, and their answers are in
the sections below.

## Proposal

### 1. The principle, and what it allows

A tool has two readers: an agent, and the host that started it. Every channel is one of these.

- **The report.** One JSON object on stdout, and the exit code that goes with it, as RFC-1 says.
- **A file the report names.** A receipt, a check's full output, a log. The report gives its path.
- **A declared input.** An argument, an environment variable, standard input or a configuration
  file that `describe` names (§6).
- **A host's protocol.** A command that a host calls in the host's own format, declared as such
  (§5).
- **Text for the reader, inside the report.** A `message`, a reason, an `error`. A reader shows it
  or passes it on and never parses it (§4).
- **The version line.** `--version` prints one fixed line, for install scripts (§3).

Anything else is outside the contract and a tool does not rely on it: stderr, `--help`, prompts,
colour, and behaviour that depends on a terminal.

### 2. stderr

A command that prints a report writes nothing to stderr. That holds for a report that blocks, for
a `not-run` report, and for `describe`. A command that speaks a host's protocol, and a hook script
a tool installs, are the one case apart: their streams belong to the host, and §5 says what goes
on them.

- **A top-level handler.** A tool catches its own failures, an internal error or a panic included,
  and prints a `not-run` report with exit code 2. It also silences the message its runtime would
  print for a panic.
- **What is left.** Only what a tool cannot catch: a kill by a signal, or a failure to write to
  stdout. A reader therefore reads stdout first. If it is one JSON object, that is the report, and
  the exit code is read with it. If it is not, the command could not run, whatever the exit code
  was or whether there was one. The reader treats it as `not-run`, may keep any stderr text as a
  diagnostic, and never parses it.
- **No logging to stderr**, with or without a flag. Neither tool logs today. A tool that needs a
  log writes it to a file and names the file in its report.
- **Whoever wrote it counts.** A warning from a runtime or a dependency is the tool's to silence
  or capture. A tool that runs other tools captures their output and passes none of it through.
- **A warning about the tool's own environment** is an entry of `notices`, as urzua's deprecated
  alias already is.

Cost: urzua already catches panics and prints `not-run`, with the text under a key of its own that
moves to `error`. garita wraps one command and extends that to the rest. Both called it small.

### 3. `--help` and `--version`

Both stay, and neither is part of what an agent reads.

- **`--version`** prints exactly `<name> <version>` and a newline on stdout, and exits 0. This is
  the one fixed text output in the contract. It exists because install scripts compare it byte for
  byte, in both tools, and an installed script from an older release must keep recognising a newer
  binary. An agent reads the version from `describe`.
- **`--help`** is whatever the tool's argument parser prints. It is outside the contract, and the
  rule that makes it harmless is this: nothing an agent needs is only in `--help`. Everything it
  says about a command's inputs is in `describe` (§6).

Making both print JSON was considered. Both tools reported that it would break their release and
install scripts, for no gain to an agent that has `describe`.

### 4. Text inside the report

Some strings are text for the reader and some carry data. The contract says which is which.

**Text, never parsed, with no layout promised:** a finding's `message`, `next_action_reason`,
`error`, a notice's `message`, and an input's `means`. Each is one or a few plain sentences. None
carries a usage block, a heading, or another tool's output.

**Data, which gets a key:**

- **Why a command could not run.** A `not-run` report may carry `error_kind`, one of `usage` (the
  arguments were wrong), `config` (the configuration could not be loaded or is invalid),
  `environment` (something outside the tool is missing: a repository, a program, a directory) or
  `internal` (the tool failed). `error` stays one sentence. For `usage` it names the argument that
  was wrong and carries no usage block; the inputs are in `describe`. A run report that is
  `not-run` because a check's program could not start may carry `error_kind` beside its `checks`.
- **A wrapped tool's output.** In the run profile, each entry of `checks` may carry `output_tail`,
  the last 4,000 characters of the check's output, and `output`, the path of the full output: the
  same two keys a receipt's check has. A finding's `message` no longer carries them.
- **A command to run.** `next_action` and a finding's `fix` stay shell command strings, as RFC-1
  decided, with their `<...>` placeholders listed in `next_action_inputs`. An argv form is deferred
  (§10).

garita also prints a few lines it picks out of a failing command's output as the likely reason. A
tail cannot carry those. That list stays garita's own extended key until a second tool wants it.

### 5. Commands that speak a host's protocol

Some commands are called by a host in the host's format: a git hook, an agent harness hook, an MCP
server. They cannot print the contract's report on stdout, because stdout belongs to the host.

- **In `describe`** such a command has profile `exempt` and a required `protocol`, a word that
  names what it speaks: `mcp`, `git-hook`, `harness-hook`, `stream` for a line-per-event stream,
  or `file` for a command whose product is a file. A reader that does not know the word does not
  call the command.
- **Inside the protocol,** where the host gives the tool free text to show, the tool puts its
  report and nothing else, on whichever stream the host relays. A git hook that blocks prints the
  tool's JSON report, with no banner and no closing line. git shows a hook's stdout and its stderr
  alike, so either stream serves.
- **The list of `protocol` words is open.** A tool that speaks another host's format names it with
  a word of its own, and a reader that does not know the word does not call the command.
- **A hook script a tool installs** is part of the tool. When the tool's binary is missing, the
  script prints a `not-run` report as a literal: `status` `not-run`, an `error`, `error_kind`
  `environment`, `next_action` and `next_action_reason` null, and an empty `next_action_inputs`.
  What the script exits with is the host's protocol and the tool's own policy, not this contract's.

Cost: garita's hook already prints only the report when it blocks, and needs a new hook format for
the missing-binary case, installed once per repository. urzua's git hooks print a banner and a
closing line that go, and the prose its harness hook prints when the binary is missing becomes the
same `not-run` literal, in the form that host accepts. An install script is not a command of the
tool and is outside the contract: it is a shell script a person or a CI job runs once to put the
tool on a machine.

### 6. `describe` declares a tool's inputs

How a tool is invoked is its own interface. The contract does not say what a tool's flags are. It
says how a tool declares them, so that an agent reads them as data.

**Commands.** A command's `name` is its full path, words separated by one space, such as
`migrate ids`. Each command carries `args`, an array, empty when it takes none. The tool carries a
top-level `args` for options every command accepts. Those are accepted after the command's name; a
tool may accept them before it as well. `--help` and `--version` are not listed.

Each entry of `args`:

| Key | Type | Required | Meaning |
|---|---|---|---|
| `name` | string | yes | The option as typed, such as `--base`, or a positional argument's name. |
| `kind` | string | yes | `flag` (a switch), `option` (takes a value) or `positional`. |
| `type` | string | for an option or a positional | `string`, `integer` or `path`. A flag has no type. |
| `required` | boolean | yes | Whether the command refuses to run without it. |
| `repeatable` | boolean | yes | Whether it may be given more than once. |
| `means` | string | yes | What to put there, in a sentence. |
| `values` | array of strings | no | The closed list of values it accepts. |
| `format` | string | no | A narrower form of a string, such as `date` for `YYYY-MM-DD`. |
| `conflicts_with` | array of strings | no | The `name` of each argument it cannot be given with. |
| `requires` | array of strings | no | The `name` of each argument that must be given with it. |
| `after_separator` | boolean | no | True for positional arguments that are given after `--`. |

**Environment.** The tool carries `env`, an array of `{name, means}`, one entry per environment
variable that changes what the tool does. A variable the tool only passes on, such as `PATH`, is
not listed.

**Standard input.** A command carries `stdin`: null when it reads nothing, or `{format, means}`
with `format` `json` or `text`. A command reads standard input only when it says so here.

**Configuration.** The tool carries `config`, an array of `{path, format}` with `format` `yaml`,
`json` or `toml`, one entry per file it reads. An entry may carry `schema`, a JSON Schema for the
file. The schema is optional in this version: both tools validate their configuration in code with
rules a schema cannot carry, and deriving one is days of work for each.

**An example.** A command may carry `example`, an array of the arguments of one invocation that is
expected to run. The runner uses it (§8).

Names are unique within a command together with the tool's top-level `args`, and a name in
`conflicts_with` or `requires` is one of them. A schema cannot state either rule, so the runner
checks both (§8).

Both tools said they can generate `args` from their argument definitions. What their command lines
have that the first shape lacked is in the table above: nested commands, global options, exclusion
and requirement between arguments, a date, and arguments after `--`.

`system` is unchanged. It describes the tool's own computation. A tool that runs others, and whose
own work is deterministic, is `0`, and each tool it runs declares its own.

### 7. No prompts, and no dependence on a terminal

- A command never reads from a terminal and never waits for a person.
- A command's behaviour and output never depend on whether a stream is a terminal. No colour, no
  pager, no progress display.
- A command reads standard input only when `describe` says so.

Cost: garita has none of this left. urzua has one case, a menu in `init` when standard input is a
terminal, and the path without it already exists.

### 8. A conformance runner

The kit ships a script, `scripts/conform.py`, that a tool runs in its own CI against its own
binary. It is given the path of the binary and runs every command in the directory it was started
in. It does what an agent would do first, and checks the answers.

1. It runs `<tool> describe` and validates the result against `describe.schema.json`. It then
   checks what the schema cannot: that argument names are unique and that every name in
   `conflicts_with` and `requires` exists.
2. For every command that `describe` marks `safe` and that is not `exempt`, it runs the command
   with the arguments in `example`, or with none. A command that needs an argument and has no
   `example` answers with a `not-run` report whose `error_kind` is `usage`, and that is a pass.
3. For each run it checks: stdout is one JSON object and validates against the schema of the
   command's profile; stderr is empty; and the exit code is 2 exactly when `status` is `not-run`.
   For the gate and run profiles, whose reports carry `blocking`, the exit code is otherwise 1
   exactly when `blocking` is true. For the base profile it is otherwise 0 or 1.
4. It runs `<tool> --version` and checks the one line of §3.

Each run has a time limit, 60 seconds unless the caller sets another, and a run that exceeds it
fails. `safe` says a command writes nothing. A tool whose safe command is slow, or needs a network,
gives it an `example` that is neither.

Any result that agrees with itself passes, a `not-run` included, so a tool needs no fixture to run
it. A tool that wants a stronger test runs it in a directory where its commands have something to
do.

RFC-1 rejected a runner because a checker that executes arbitrary binaries is unsafe, since
commands write. This one runs only in a tool's own repository, against that tool's own binary, and
only the commands that tool has declared `safe`. It does not run other people's tools.

The script needs Python and the validator this repository's own check uses. It does not run inside
a tool's unit tests, and each tool keeps its vendored schemas and its own tests.

### 9. What conformance to 1.1 means

A tool that prints `contract_version` `"1.1"`:

- answers `describe` with exit code 0, and its `describe` declares `args`, `env`, `stdin` and
  `config` as §6 says;
- writes nothing to stderr (§2) and follows §3, §4, §5 and §7;
- passes the runner of §8 in its CI.

A tool that prints `"1.0"` is held to RFC-1 as it stood at `v1.0.0`. Nothing that conformed to 1.0
stops conforming.

Version 1.1 is taken whole. A tool that uses the run profile prints `"1.1"`, and so takes on
everything in this list. No tool has released against 1.1 yet, which is why this can still be
settled as one version.

### 10. What rides with 1.1 and what waits

| Point | Decision | Version |
|---|---|---|
| stderr empty, top-level handler, no logging | Taken | 1.1 |
| `--version` fixed, `--help` outside the contract | Taken | 1.1 |
| Which strings are text and which are data | Taken | 1.1 |
| `error_kind` | Taken, optional key | 1.1 |
| `output_tail` and `output` on a check entry | Taken, optional keys | 1.1 |
| `protocol` on an `exempt` command; hooks print the report | Taken | 1.1 |
| `describe` declares `args`, `env`, `stdin`, `config` | Taken | 1.1 |
| No prompts, no dependence on a terminal | Taken | 1.1 |
| The conformance runner | Taken | 1.1 |
| A JSON Schema for a tool's configuration | Optional key now; required is deferred | later |
| `next_action` as an argv array | Deferred: additive, and urzua reported a day's work to build every action from words | later minor |
| garita's picked-out lines of a failing output | Not taken; garita's own extended key | when a second tool wants it |

`v1.1.0` waits for this RFC. The run profile of RFC-3 is already in `v1.1.0-rc.2`, and garita's
reports validate against it. This RFC's schema changes ship as a further release candidate, and
`v1.1.0` is tagged when both tools pass the runner against it. The maintainer's priority is a
contract that stays put, and one settled 1.1 serves that better than a 1.1 followed at once by a
1.2.

### 11. What changes in the schemas and in RFC-1

- `describe.schema.json`: `args` at the top level and per command, `env`, `stdin`, `config`,
  `example`, and `protocol`, each required as §6 and §5 say when `contract_version` is not
  `"1.0"`.
- `report.schema.json`: optional `error_kind`.
- `run-report.schema.json`: optional `output_tail` and `output` on a check entry.
- `scripts/conform.py`, and `make check` runs it against a small fixture tool so that the runner
  itself is tested.
- The examples follow. `examples/valid/describe.run-profile.json` prints `"1.1"` and gains its
  inputs, and each new rule gets a valid and an invalid example. The `"1.0"` examples are
  unchanged and stay valid.
- RFC-1 §1, §3 and §6 are brought into line, with a revision row pointing here. The draft
  amendment on stderr is replaced by §2 above. RFC-1 §4's rule on new JSON Schema keywords is a
  separate amendment and is unaffected.

No JSON Schema keyword outside the checked list is needed.

### 12. What each tool changes

**urzua**: ships `describe` with its inputs; moves a panic's text to `error` and sets `error_kind`;
builds a usage error's message without the parser's usage block; removes the menu in `init`; drops
the banner and closing line from its git hooks and the prose from its harness hook's missing-binary
case; runs the runner in CI.

**garita**: extends its panic handler to every command; sets `error_kind`; moves captured output
from `message` to `output_tail` and `output` on the check; adds `args`, `env`, `stdin` and `config`
to `describe`; ships a hook format that prints a `not-run` report when the binary is missing; runs
the runner in CI.

## Open questions

- **A runner at all.** RFC-1 deferred a live conformance checker until a third tool conformed, by
  the maintainer's decision. §8 brings it forward and narrows it to a tool's own safe commands.
  That reversal is theirs to confirm.
- **Is passing the runner required for 1.1, or recommended?** §9 requires it. urzua notes that
  adding Python and a validator to its CI is a workflow change the maintainer approves there.
- **No logging to stderr even on request.** §2 allows none. If a tool's developers need a debug
  stream, the alternative is a log file named in the report.
- **What a hook exits with when the tool cannot run.** urzua's hook exits 0 and leaves CI as the
  guarantee; garita's exits 2 and stops the commit. §5 leaves this to each tool.

## Non-goals

- Saying what a tool's flags, variables or configuration keys are. The contract says how they are
  declared.
- A human-readable output mode, in any form.
- Running tools other than the one under test.

## References

- RFC-1, the agent CLI contract
- RFC-3, the run profile
- urzua ADR-46; garita RFC-1 and RFC-2
