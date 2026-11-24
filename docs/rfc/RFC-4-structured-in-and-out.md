---
Stable-Id: 01M85CY0G84WNWK7AGGYXNAQDJ
Status: Accepted
Date: 2026-11-23
Accepted-on: 2026-11-24
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
- **The log.** When a caller asks for it, stderr carries one JSON object per line (§2.1).

Anything else is outside the contract and a tool does not rely on it: free text on stderr,
`--help`, prompts, colour, and behaviour that depends on a terminal.

### 2. stderr

A command that prints a report writes nothing to stderr, unless its caller asked for the log of
§2.1. That holds for a report that blocks, for a `not-run` report, and for `describe`. A command
that speaks a host's protocol, and a hook script a tool installs, are apart from this: their
streams belong to the host, and §5 says what goes on them.

- **A top-level handler.** A tool catches its own failures, an internal error or a panic included,
  and prints a `not-run` report with exit code 2. It also silences the message its runtime would
  print for a panic.
- **What is left.** Only what a tool cannot catch: a kill by a signal, or a failure to write to
  stdout. A reader therefore reads stdout first. If it is one JSON object, that is the report, and
  the exit code is read with it. If it is not, the command could not run, whatever the exit code
  was or whether there was one. The reader treats it as `not-run`, may keep any stderr text as a
  diagnostic, and never parses it.
- **A log, on request, and structured.** A tool may have a diagnostic log. It is off unless the
  caller turns it on, and when it is on, stderr carries the log and nothing else. The rules are in
  §2.1.
- **Whoever wrote it counts.** A warning from a runtime or a dependency is the tool's to silence
  or capture. A tool that runs other tools captures their output and passes none of it through.
- **A warning about the tool's own environment** is an entry of `notices`, as urzua's deprecated
  alias already is.

#### 2.1 The log

A log is for whoever is debugging the tool. A reader of the report never needs it: nothing a
reader acts on is only in the log.

- **Off by default.** With no request, a command writes nothing to stderr, as above.
- **Turned on by a declared input.** `describe` carries `log` at the top level: null when the tool
  has no log, or an object that names the one input that turns it on. `{"arg": "--log"}` names a
  flag in the tool's top-level `args`. `{"env": "URZUA_LOG"}` names a variable in `env`, which
  turns the log on when it is set to `1`. The named flag or variable is one the tool declares
  there.
- **One JSON object per line.** With the log on, every line the command writes to stderr is one JSON
  object, and `schemas/log-line.schema.json` describes it. It has three required keys: `time` (RFC
  3339 in UTC, written with `Z`, as a receipt's times are), `level` (`debug`, `info`, `warning` or
  `error`, the words a finding's severity uses, with `debug` added) and `message` (text, never
  parsed). A tool may add keys of its own.
- **The report is unchanged.** stdout is the same one JSON object and the exit code is the same,
  with the log on or off.

Neither tool has a log today, so this costs nothing until one wants it.

Cost of the rest of §2: urzua already catches panics and prints `not-run`, with the text under a key
of its own that moves to `error`. garita wraps one command and extends that to the rest. Both called
it small.

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
- **A command to run.** A command is data, and a shell string makes a reader parse quoting to get
  it back. From 1.1 a command is also printed as its arguments. §4.1 says how.

#### 4.1 A command as its arguments

`next_action` stays the string RFC-1 defined, so a reader written for 1.0 keeps working. Beside it
a report carries the same command as data.

| Key | Type | Meaning |
|---|---|---|
| `next_action_argv` | array of strings, or null | The command as one program and its arguments: the first element is the program, each further element is one argument, with no shell quoting. Null exactly when `next_action` is null. |
| `index`, on each entry of `next_action_inputs` | integer, 0 or more | The position in `next_action_argv` of the element the caller replaces. |

- **A placeholder is a whole element.** The element at `index` is exactly the entry's
  `placeholder`, such as `<record>`. A reader replaces that element with the value and runs the
  array. It never searches a string for `<...>`.
- **One process.** The command is one program run once: no pipe, no `&&`, no redirection, no
  variable or glob for a shell to expand. RFC-1 already says `next_action` is one command.
- **The two forms agree.** `next_action` is `next_action_argv` joined by spaces, with each element
  quoted for a POSIX shell where it needs to be. Splitting the string as a POSIX shell would gives
  the array back.
- **A placeholder is quoted in the string.** `<` and `>` mean redirection to a shell, so in
  `next_action` a placeholder is written `'<record>'`. urzua prints three forms today, single
  quotes, double quotes and bare, and RFC-1's own example has it bare; from 1.1 it is quoted.
  A reader of the array never meets the question.
- **The array is never empty.** When it is not null it has at least the program.
- **A finding's `fix`** gets the same treatment: `fix_argv`, an array of strings, beside `fix`. A
  `fix` carries no placeholders. It runs as printed.

A tool that prints `contract_version` `"1.1"` prints `next_action_argv` in every report, gives
every input an `index`, and prints `fix_argv` wherever it prints `fix`. A report does not carry
the contract version, so the schema makes these keys optional and ties them together when they are
present, and the runner checks that a 1.1 tool prints them (§8).

Cost: garita builds its command from arguments before joining them, so this is cheap there. urzua
builds some of its actions as strings and reported about a day's work to build them all from
arguments.

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
  `environment`, `next_action`, `next_action_reason` and `next_action_argv` null, and an empty
  `next_action_inputs`.
- **A hook that cannot run its tool blocks.** §5.1 states the rule.

#### 5.1 A hook that cannot run its tool blocks

A hook exists so that something does not happen unless the tool has looked at it. If the tool
could not look, the hook does not let it happen. This is one rule for every tool.

- **When it applies.** The hook could not get a verdict: the tool's binary is missing or cannot
  start, the tool died without printing a report, or the tool answered with a `not-run` report.
- **Which hooks.** Every hook a tool installs or answers that the host consults before it acts,
  and whose answer can stop the action. A git `pre-commit` or `pre-push` hook is one. So is an
  agent harness hook that runs before an edit or a command.
- **What block means** is the host's to define, and the tool uses the host's way of saying no. For
  a git hook it is exit status 2, the same number a command uses for `not-run`; git stops on any
  status but 0, so a hook that ran and found something blocking exits 1 and one that could not run
  exits 2. For an agent harness hook it is the answer in that host's format that refuses the
  action.
- **A hook that runs after the fact cannot block.** It prints the `not-run` report in the host's
  format and that is all it can do. A git `post-commit` hook is one, and so is an agent harness
  hook that runs after a command.
- **Nothing turns this off:** no configuration key, no flag and no environment variable. A tool's
  flags and configuration are its own interface, as RFC-3 records, and they decide what the tool
  judges and how strictly. This rule is about something else: what a hook does when the tool
  could not judge at all. What a tool does when it ran and has no opinion on a change is a
  different question again, and stays the tool's. urzua's `on_unjudged: allow` option is of that
  second kind, and the maintainer confirmed it is outside this rule.
- **The host's own way round is the host's.** `git commit --no-verify` skips a hook, and this rule
  says nothing about it.

Cost: garita's hooks already exit 2 here. urzua's git hooks exit 0 today and leave CI as the
guarantee, by a decided choice in its own records. Reversing it is a small edit to protected hook
files, a flipped test, a new decision record that supersedes the old choice, and an amendment to
two more. urzua put it at about a day plus the maintainer's edit. A fresh clone of urzua then
cannot commit until the tool is built. urzua's agent harness hook already refuses in a governed
session, with one case that is let through with a notice and would now refuse.

Cost of the rest of §5: garita's hook already prints only the report when it blocks, and needs a new
hook format for the missing-binary case, installed once per repository. urzua's git hooks print a
banner and a closing line that go, and the prose its harness hook prints when the binary is missing
becomes the same `not-run` literal, in the form that host accepts. An install script is not a
command of the tool and is outside the contract: it is a shell script a person or a CI job runs once
to put the tool on a machine.

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

**The log.** The tool carries `log`, null or the object of §2.1.

`system` is unchanged, by the maintainer's decision. It describes the tool's own computation. A tool
that runs others, and whose own work is deterministic, is `0`, and each tool it runs declares its
own.

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
   checks what the schema cannot: that argument names are unique, that every name in
   `conflicts_with` and `requires` exists, and that the flag or variable `log` names is declared.
2. For every command that `describe` marks `safe` and that is not `exempt`, it runs the command
   with the arguments in `example`, or with none. A command that needs an argument and has no
   `example` answers with a `not-run` report whose `error_kind` is `usage`, and that is a pass.
3. For each run it checks: stdout is one JSON object and validates against the schema of the
   command's profile; stderr is empty; and the exit code is 2 exactly when `status` is `not-run`.
   For the gate and run profiles, whose reports carry `blocking`, the exit code is otherwise 1
   exactly when `blocking` is true. For the base profile it is otherwise 0 or 1.
4. For a tool that prints `contract_version` `"1.1"` it also checks, in every report, what the
   schema leaves optional or cannot state: `next_action_argv` is present, is not empty when it is
   not null, and is what splitting `next_action` as a POSIX shell gives; every entry of
   `next_action_inputs` has an `index`, and the element there is the entry's `placeholder`; and
   every finding with a `fix` has a `fix_argv` that agrees with it in the same way.
5. If `describe` declares a `log`, it runs one safe command again with the log turned on, and
   checks that every line on stderr validates against `log-line.schema.json` and that stdout and
   the exit code are what they were with the log off.
6. It runs `<tool> --version` and checks the one line of §3.

The runner starts every command with the log's variable unset, so that a log left on in the caller's
environment does not fail the empty-stderr check. The runner does not run hooks. The rule of §5.1 is
one each tool tests itself, with its binary taken away.

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

- answers `describe` with exit code 0, and its `describe` declares `args`, `env`, `stdin`,
  `config` and `log` as §6 says, and a `protocol` for each `exempt` command (§5);
- writes nothing to stderr unless its log was asked for (§2), prints every command as its
  arguments (§4.1), blocks in a hook that cannot run it (§5.1), and follows §3, §4, §5 and §7;
- passes the runner of §8 in its CI.

A tool that prints `"1.0"` is held to RFC-1 as it stood at `v1.0.0`. Nothing that conformed to 1.0
stops conforming.

Version 1.1 is taken whole. A tool that uses the run profile prints `"1.1"`, and so takes on
everything in this list. No tool has released against 1.1 yet, which is why this can still be
settled as one version.

### 10. What rides with 1.1 and what waits

| Point | Decision | Version |
|---|---|---|
| stderr empty, top-level handler | Taken | 1.1 |
| A log on request, one JSON object per line | Taken | 1.1 |
| `--version` fixed, `--help` outside the contract | Taken | 1.1 |
| Which strings are text and which are data | Taken | 1.1 |
| `error_kind` | Taken, optional key | 1.1 |
| `output_tail` and `output` on a check entry | Taken, optional keys | 1.1 |
| `protocol` on an `exempt` command; hooks print the report | Taken | 1.1 |
| A hook that cannot run its tool blocks | Taken | 1.1 |
| A command as its arguments: `next_action_argv`, `index`, `fix_argv` | Taken | 1.1 |
| `describe` declares `args`, `env`, `stdin`, `config` | Taken | 1.1 |
| No prompts, no dependence on a terminal | Taken | 1.1 |
| The conformance runner | Taken | 1.1 |
| A JSON Schema for a tool's configuration | Optional key now; required is deferred | later |
| garita's picked-out lines of a failing output | Not taken; garita's own extended key | when a second tool wants it |

`v1.1.0` waits for this RFC. The run profile of RFC-3 is already in `v1.1.0-rc.2`, and garita's
reports validate against it. This RFC's schema changes ship as a further release candidate, and
`v1.1.0` is tagged when both tools pass the runner against it. The maintainer's priority is a
contract that stays put, and one settled 1.1 serves that better than a 1.1 followed at once by a
1.2.

### 11. What changes in the schemas and in RFC-1

- `describe.schema.json`: `args` at the top level and per command, `env`, `stdin`, `config`,
  `example`, `log` and `protocol`, each required as §6 and §5 say when `contract_version` is not
  `"1.0"`.
- `report.schema.json`: optional `error_kind`; optional `next_action_argv`, null exactly when
  `next_action` is null; optional `index` on an entry of `next_action_inputs`. The example
  `report.next-action.json` quotes its placeholder.
- `finding.schema.json`: optional `fix_argv`.
- `log-line.schema.json`, new: one line of a log.
- `run-report.schema.json`: optional `output_tail` and `output` on a check entry.
- `scripts/conform.py`, and `make check` runs it against a small fixture tool so that the runner
  itself is tested.
- The examples follow. `examples/valid/describe.run-profile.json` prints `"1.1"` and gains its
  inputs, and each new rule gets a valid and an invalid example. The `"1.0"` examples are
  unchanged and stay valid.
- RFC-1 §1, §3 and §6 are brought into line, with a revision row pointing here. §1 also says that
  its exit codes are those of a command that prints its report on stdout: a hook's exit status is
  the host's (§5). The draft amendment on stderr is replaced by §2 above. RFC-1 §4's rule on new
  JSON Schema keywords is a separate amendment and is unaffected.

No JSON Schema keyword outside the checked list is needed.

### 12. What each tool changes

**urzua**: ships `describe` with its inputs, `log` and a `protocol` for each `exempt` command; moves
a panic's text to `error` and sets `error_kind`; builds a usage error's message without the parser's
usage block; removes the menu in `init`; drops the banner and closing line from its git hooks and
the prose from its harness hook's missing-binary case; makes its git hooks exit 2 when the tool
cannot run, with the records that decision touches, and its harness hook refuse in the one case it
lets through today; builds every `next_action` from arguments, with `next_action_argv`, an `index`
on each input and `fix_argv`, and quotes its placeholders one way; runs the runner in CI.

**garita**: extends its panic handler to every command; declares `log` in `describe`, and a
`protocol` when it has an `exempt` command; sets `error_kind`; moves captured output from `message`
to `output_tail` and `output` on the check; adds `args`, `env`, `stdin` and `config` to `describe`;
ships a hook format that prints a `not-run` report when the binary is missing; prints
`next_action_argv`, an `index` on each input and `fix_argv`; runs the runner in CI.

## Open questions

None. The maintainer answered the four questions this record first asked, and then read and
accepted the three passages written from their answers (see Revisions).

## Revisions

| Date | Change |
|---|---|
| 2026-11-23 | The maintainer answered the open questions, by voice. The transcription is rough; bracketed words are the relay's reading. "let's build the runner now. And it's going to be required for 1.1. Um, we can do STD [logging] on request. In fact, actually, we could do a structured logging output. [...] Next action should actually be structured. Maybe we just decide on that now! Yeah, let's standardize the [exit of the] hook. With the block. And yeah, let's decide on the system value is [zero]. And then I'll accept [RFC-4]." So: the runner is built now and passing it is required for 1.1 (§8, §9, unchanged); a log is allowed on request and is structured (§2.1, new; §2 had allowed none); a command is printed as its arguments in 1.1 (§4.1, new; it had been deferred); a hook that cannot run its tool blocks, for every tool (§5.1, new; §5 had left it to each tool); `system` is 0 for a tool that runs others (§6, unchanged). §2.1, §4.1 and §5.1 are text the maintainer has not yet read. This record stays Draft until they have. |
| 2026-11-24 | Accepted by the maintainer, who had read §2.1, §4.1 and §5.1 and the additions an independent review made to them. Asked "Do you accept RFC-4 as it now reads?" and "Does urzua's `on_unjudged: allow` option sit outside the hook rule?", they said: "I accept RFC, and yes allow option can be outside rule". RFC-1's rule on new JSON Schema keywords was proposed separately and is not part of this acceptance. |

## Non-goals

- Saying what a tool's flags, variables or configuration keys are. The contract says how they are
  declared.
- A human-readable output mode, in any form.
- Running tools other than the one under test.

## References

- RFC-1, the agent CLI contract
- RFC-3, the run profile
- urzua ADR-46; garita RFC-1 and RFC-2
