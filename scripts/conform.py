#!/usr/bin/env python3
"""Check one tool against the agent CLI contract by running its own safe commands.

usage: conform.py BINARY [--schemas DIR] [--timeout SECONDS]

Run it in the tool's own repository, against the tool's own binary. It runs
`BINARY describe`, then every command `describe` marks safe and not exempt, in
the current directory. It prints one gate report on stdout and exits 0 when the
tool conforms, 1 when it does not, and 2 when the check could not run.
"""
import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

VALIDATOR = "check-jsonschema==0.39.0"
SCHEMA_OF_PROFILE = {"base": "report", "gate": "gate-report", "run": "run-report"}
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

findings = []


def fail(rule, message, command=None):
    finding = {"rule": f"conform/{rule}", "severity": "error", "message": message}
    if command is not None:
        finding["check"] = command
    findings.append(finding)


class CannotRun(Exception):
    kind = "environment"


class Usage(CannotRun):
    kind = "usage"


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Usage(message)


def validator_command():
    if shutil.which("uvx"):
        return ["uvx", VALIDATOR]
    if shutil.which("pipx"):
        return ["pipx", "run", "--spec", VALIDATOR, "check-jsonschema"]
    raise CannotRun("neither uvx nor pipx is installed, and one is needed to validate")


def validate(schemas, schema, instances):
    """Validate {label: value} against one schema; return {label: [messages]}."""
    if not instances:
        return {}
    with tempfile.TemporaryDirectory() as tmp:
        label_of = {}
        for number, (label, value) in enumerate(instances.items()):
            path = pathlib.Path(tmp) / f"{number}.json"
            path.write_text(json.dumps(value))
            label_of[str(path)] = label
        done = subprocess.run(
            validator_command()
            + ["--output-format", "json", "--base-uri", schemas.resolve().as_uri() + "/"]
            + ["--schemafile", str(schemas / f"{schema}.schema.json")]
            + list(label_of),
            capture_output=True,
            text=True,
        )
        try:
            result = json.loads(done.stdout)
        except json.JSONDecodeError:
            raise CannotRun(f"the validator did not answer: {done.stderr.strip()[:300]}")
        errors = {}
        for error in result.get("errors", []) + result.get("parse_errors", []):
            label = label_of.get(error.get("filename"), schema)
            errors.setdefault(label, []).append(f"{error.get('path', '$')}: {error.get('message')}")
        if result.get("status") != "ok" and not errors:
            raise CannotRun(f"the validator failed on {schema}: {done.stdout.strip()[:300]}")
        return errors


def run(argv, timeout, env):
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return None
    except OSError as error:
        raise CannotRun(f"could not start {argv[0]}: {error}")


def one_object(text):
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def split_one_process(string):
    """Split a command as a POSIX shell would, or return None when a shell would do
    anything but run one program with literal arguments: an operator, an expansion,
    a comment, an assignment or a second line."""
    words, word, quote, started = [], [], None, False
    i = 0
    while i < len(string):
        char = string[i]
        if quote == "'":
            if char == "'":
                quote = None
            else:
                word.append(char)
        elif quote == '"':
            if char == '"':
                quote = None
            elif char == "\\" and i + 1 < len(string) and string[i + 1] in '$`"\\':
                word.append(string[i + 1])
                i += 1
            elif char in "$`":
                return None
            else:
                word.append(char)
        elif char in "'\"":
            quote, started = char, True
        elif char == "\\":
            if i + 1 >= len(string) or string[i + 1] == "\n":
                return None
            word.append(string[i + 1])
            started = True
            i += 1
        elif char in " \t":
            if started:
                words.append("".join(word))
                word, started = [], False
        elif char in "\n<>|&;()$`*?[]{}" or (char in "~#" and not started):
            return None
        else:
            word.append(char)
            started = True
        i += 1
    if quote is not None:
        return None
    if started:
        words.append("".join(word))
    if words and ASSIGNMENT.match(string.lstrip()):
        return None
    return words


def agrees(string, argv):
    return split_one_process(string) == argv


def check_describe(describe):
    """Check what the schema cannot, and return whether a usable log is declared."""
    top = describe.get("args", [])
    env = [entry["name"] for entry in describe.get("env", [])]
    top_names = [arg["name"] for arg in top]
    scopes = [(None, top, top_names)]
    for command in describe["commands"]:
        own = command.get("args", [])
        scopes.append((command["name"], own, top_names + [arg["name"] for arg in own]))
    for name, args, names in scopes:
        repeated = sorted({n for n in names if names.count(n) > 1})
        if repeated and (name is not None or not describe["commands"]):
            fail("arg-name-repeated", f"argument names are not unique: {repeated}", name)
        for arg in args:
            if arg["kind"] == "flag" and "type" in arg:
                fail("arg-flag-type", f"{arg['name']} is a flag and has a type", name)
            for key in ("conflicts_with", "requires"):
                for other in arg.get(key, []):
                    if name is not None and other not in names:
                        fail("arg-name-unknown", f"{arg['name']} names {other} in {key}, which is not declared", name)
    log = describe.get("log")
    if log is None:
        return False
    if len(log) != 1:
        fail("log-declaration", "log names exactly one of arg or env")
    elif "arg" in log and log["arg"] not in [arg["name"] for arg in top if arg["kind"] == "flag"]:
        fail("log-declaration", f"log names {log['arg']}, which is not a top-level flag")
    elif "env" in log and log["env"] not in env:
        fail("log-declaration", f"log names {log['env']}, which is not declared in env")
    else:
        return True
    return False


def check_exit_code(profile, report, code, command):
    not_run = report.get("status") == "not-run"
    if not_run != (code == 2):
        fail("exit-code", f"status is {report.get('status')!r} and the exit code is {code}", command)
    elif not not_run and profile in ("gate", "run"):
        if (code == 1) != (report.get("blocking") is True):
            fail("exit-code", f"blocking is {report.get('blocking')!r} and the exit code is {code}", command)
    elif not not_run and code not in (0, 1):
        fail("exit-code", f"the exit code is {code}", command)


def check_commands_as_arguments(report, command):
    """Only called on a report that already validated against its schema."""
    if "next_action_argv" not in report:
        fail("argv-missing", "the report has no next_action_argv", command)
        return
    argv = report["next_action_argv"]
    if argv is not None:
        if not argv:
            fail("argv-empty", "next_action_argv is empty", command)
        elif not agrees(report["next_action"], argv):
            fail("argv-disagrees", "next_action is not next_action_argv as one shell command", command)
    for entry in report["next_action_inputs"]:
        index = entry.get("index")
        if index is None:
            fail("input-index-missing", f"the input {entry['placeholder']} has no index", command)
        elif argv is None or index >= len(argv) or argv[index] != entry["placeholder"]:
            fail("input-index-wrong", f"the element at index {index} is not {entry['placeholder']}", command)
    for finding in report.get("findings", []):
        if "fix" in finding and "fix_argv" not in finding:
            fail("fix-argv-missing", f"the finding {finding['rule']} has a fix and no fix_argv", command)
        elif "fix_argv" in finding and "fix" not in finding:
            fail("fix-argv-orphan", f"the finding {finding['rule']} has a fix_argv and no fix", command)
        elif "fix" in finding and not agrees(finding["fix"], finding["fix_argv"]):
            fail("fix-argv-disagrees", f"the fix of {finding['rule']} is not its fix_argv", command)


def shape(report, code):
    """What must not change when the log is turned on. Durations and times may."""
    return (
        code,
        report.get("status"),
        report.get("blocking"),
        sorted(report),
        len(report.get("findings", [])),
        len(report.get("notices", [])),
    )


def main(arguments):
    parser = Parser(add_help=False)
    parser.add_argument("binary")
    parser.add_argument("--schemas", default=str(pathlib.Path(__file__).resolve().parent.parent / "schemas"))
    parser.add_argument("--timeout", type=float, default=60)
    options = parser.parse_args(arguments)
    schemas = pathlib.Path(options.schemas)
    binary, timeout = options.binary, options.timeout
    if not (schemas / "describe.schema.json").is_file():
        raise CannotRun(f"no schemas in {schemas}")

    env = dict(os.environ)
    done = run([binary, "describe"], timeout, env)
    if done is None:
        fail("timeout", f"did not finish in {timeout:g} seconds", "describe")
        return 0
    describe = one_object(done.stdout)
    if describe is None or done.returncode != 0:
        fail("describe", f"describe exited {done.returncode} and did not print one JSON object")
        return 0
    for message in validate(schemas, "describe", {"describe": describe}).get("describe", []):
        fail("describe-schema", message)
    if findings:
        return 0
    strict = describe["contract_version"] != "1.0"
    log = describe.get("log") or {}
    if log.get("env") in env:
        del env[log["env"]]
        done = run([binary, "describe"], timeout, env)
    has_log = False
    if strict:
        if done is None or done.stderr:
            fail("stderr", "describe wrote to stderr", "describe")
        has_log = check_describe(describe)

    runnable = [c for c in describe["commands"] if c["safe"] and c["profile"] != "exempt"]
    ran = {}
    for command in runnable:
        name = command["name"]
        argv = [binary] + name.split(" ") + command.get("example", [])
        done = run(argv, timeout, env)
        if done is None:
            fail("timeout", f"did not finish in {timeout:g} seconds", name)
            continue
        report = one_object(done.stdout)
        if report is None:
            fail("stdout", "stdout is not one JSON object", name)
            continue
        if strict and done.stderr:
            fail("stderr", "wrote to stderr", name)
        ran[name] = (command, argv, report, done.returncode)

    valid = {}
    for profile, schema in SCHEMA_OF_PROFILE.items():
        of_profile = {name: r[2] for name, r in ran.items() if r[0]["profile"] == profile}
        errors = validate(schemas, schema, of_profile)
        for name, messages in errors.items():
            for message in messages:
                fail("report-schema", message, name)
        valid.update({name: ran[name] for name in of_profile if name not in errors})
    for name, (command, argv, report, code) in valid.items():
        check_exit_code(command["profile"], report, code, name)
        if strict:
            check_commands_as_arguments(report, name)

    first = next((c["name"] for c in runnable if c["name"] in valid), None)
    if has_log and first is not None:
        name, (command, argv, report, code) = first, valid[first]
        log_env, log_argv = dict(env), list(argv)
        if "arg" in log:
            log_argv.insert(1 + len(name.split(" ")), log["arg"])
        else:
            log_env[log["env"]] = "1"
        done = run(log_argv, timeout, log_env)
        if done is None:
            fail("timeout", f"did not finish in {timeout:g} seconds with the log on", name)
        else:
            lines = {}
            for number, line in enumerate(done.stderr.splitlines(), start=1):
                value = one_object(line)
                if value is None:
                    fail("log-line", f"line {number} of the log is not one JSON object", name)
                else:
                    lines[f"line {number}"] = value
            for label, messages in validate(schemas, "log-line", lines).items():
                for message in messages:
                    fail("log-line", f"{label} of the log: {message}", name)
            logged = one_object(done.stdout)
            if logged is None or shape(logged, done.returncode) != shape(report, code):
                fail("log-changes-report", "the report or the exit code changed with the log on", name)

    if strict:
        done = run([binary, "--version"], timeout, env)
        expected = f"{describe['name']} {describe['version']}\n"
        if done is None or done.returncode != 0 or done.stdout != expected:
            fail("version-line", f"--version did not print exactly {expected!r} and exit 0")
        elif done.stderr:
            fail("stderr", "--version wrote to stderr")
    return len(runnable)


def emit(report, code):
    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")
    sys.exit(code)


def not_run(error, kind):
    emit(
        {
            "status": "not-run",
            "error": error,
            "error_kind": kind,
            "next_action": None,
            "next_action_reason": None,
            "next_action_argv": None,
            "next_action_inputs": [],
        },
        2,
    )


if __name__ == "__main__":
    try:
        commands = main(sys.argv[1:])
    except CannotRun as error:
        not_run(str(error), error.kind)
    except Exception as error:
        not_run(f"the runner failed: {type(error).__name__}: {error}", "internal")
    emit(
        {
            "status": "fail" if findings else "pass",
            "blocking": bool(findings),
            "findings": findings,
            "examined": {"commands": commands},
            "next_action": None,
            "next_action_reason": None,
            "next_action_argv": None,
            "next_action_inputs": [],
        },
        1 if findings else 0,
    )
