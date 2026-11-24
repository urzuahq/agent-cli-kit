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
import shlex
import shutil
import subprocess
import sys
import tempfile

VALIDATOR = "check-jsonschema==0.39.0"
SCHEMA_OF_PROFILE = {"base": "report", "gate": "gate-report", "run": "run-report"}

findings = []


def fail(rule, message, command=None):
    finding = {"rule": f"conform/{rule}", "severity": "error", "message": message}
    if command is not None:
        finding["check"] = command
    findings.append(finding)


class CannotRun(Exception):
    pass


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
        done = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return None
    except OSError as error:
        raise CannotRun(f"could not start {argv[0]}: {error}")
    return done


def one_object(text):
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def check_describe_names(describe):
    top = [arg.get("name") for arg in describe.get("args", [])]
    env = [entry.get("name") for entry in describe.get("env", [])]
    for command in describe["commands"]:
        names = top + [arg.get("name") for arg in command.get("args", [])]
        repeated = sorted({name for name in names if names.count(name) > 1})
        if repeated:
            fail("arg-name-repeated", f"argument names are not unique: {repeated}", command["name"])
        for arg in command.get("args", []) + describe.get("args", []):
            for key in ("conflicts_with", "requires"):
                for other in arg.get(key, []):
                    if other not in names:
                        fail(
                            "arg-name-unknown",
                            f"{arg.get('name')} names {other} in {key}, which is not declared",
                            command["name"],
                        )
    log = describe.get("log")
    if log is not None:
        if len(log) != 1:
            fail("log-declaration", "log names exactly one of arg or env")
        elif "arg" in log:
            flags = [a.get("name") for a in describe.get("args", []) if a.get("kind") == "flag"]
            if log["arg"] not in flags:
                fail("log-declaration", f"log names {log['arg']}, which is not a top-level flag")
        elif log["env"] not in env:
            fail("log-declaration", f"log names {log['env']}, which is not declared in env")


def check_exit_code(profile, report, code, command):
    not_run = report.get("status") == "not-run"
    if not_run != (code == 2):
        fail("exit-code", f"status is {report.get('status')!r} and the exit code is {code}", command)
    elif not not_run and profile in ("gate", "run"):
        if (code == 1) != (report.get("blocking") is True):
            fail("exit-code", f"blocking is {report.get('blocking')!r} and the exit code is {code}", command)
    elif not not_run and code not in (0, 1):
        fail("exit-code", f"the exit code is {code}", command)


def unquoted_operator(string):
    """Whether a shell would read part of the string as an operator, not as an argument."""
    quote = None
    skip = False
    for char in string:
        if skip:
            skip = False
        elif quote == "'":
            quote = None if char == "'" else quote
        elif char == "\\":
            skip = True
        elif quote == '"':
            quote = None if char == '"' else quote
        elif char in "'\"":
            quote = char
        elif char in "<>|&;()`$":
            return True
    return False


def agrees(string, argv):
    if unquoted_operator(string):
        return False
    try:
        return shlex.split(string) == argv
    except ValueError:
        return False


def check_commands_as_arguments(report, command):
    if "next_action_argv" not in report:
        fail("argv-missing", "the report has no next_action_argv", command)
        return
    argv = report["next_action_argv"]
    action = report.get("next_action")
    if argv is not None:
        if not argv:
            fail("argv-empty", "next_action_argv is empty", command)
        elif not isinstance(action, str) or not agrees(action, argv):
            fail("argv-disagrees", "next_action does not split into next_action_argv", command)
    for entry in report.get("next_action_inputs", []):
        index = entry.get("index")
        if index is None:
            fail("input-index-missing", f"the input {entry.get('placeholder')} has no index", command)
        elif argv is None or index >= len(argv) or argv[index] != entry.get("placeholder"):
            fail(
                "input-index-wrong",
                f"the element at index {index} is not {entry.get('placeholder')}",
                command,
            )
    for finding in report.get("findings", []):
        if "fix" in finding:
            if "fix_argv" not in finding:
                fail("fix-argv-missing", f"the finding {finding.get('rule')} has a fix and no fix_argv", command)
            elif not agrees(finding["fix"], finding["fix_argv"]):
                fail("fix-argv-disagrees", f"the fix of {finding.get('rule')} does not split into fix_argv", command)


def main():
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("binary")
    parser.add_argument("--schemas", default=str(pathlib.Path(__file__).resolve().parent.parent / "schemas"))
    parser.add_argument("--timeout", type=float, default=60)
    options = parser.parse_args()
    schemas = pathlib.Path(options.schemas)
    binary = options.binary
    if not (schemas / "describe.schema.json").is_file():
        raise CannotRun(f"no schemas in {schemas}")

    env = dict(os.environ)
    done = run([binary, "describe"], options.timeout, env)
    if done is None:
        raise CannotRun("describe did not finish in time")
    describe = one_object(done.stdout)
    if describe is None or done.returncode != 0:
        fail("describe", f"describe exited {done.returncode} and did not print one JSON object")
        return 0
    for message in validate(schemas, "describe", {"describe": describe}).get("describe", []):
        fail("describe-schema", message)
    if findings:
        return 0
    strict = describe["contract_version"] != "1.0"
    if strict and done.stderr:
        fail("stderr", "describe wrote to stderr", "describe")
    check_describe_names(describe)

    log = describe.get("log") or {}
    if "env" in log:
        env.pop(log["env"], None)

    runnable = [c for c in describe["commands"] if c["safe"] and c["profile"] != "exempt"]
    reports = {profile: {} for profile in SCHEMA_OF_PROFILE}
    first = None
    for command in runnable:
        name = command["name"]
        argv = [binary] + name.split(" ") + command.get("example", [])
        done = run(argv, options.timeout, env)
        if done is None:
            fail("timeout", f"did not finish in {options.timeout:g} seconds", name)
            continue
        report = one_object(done.stdout)
        if report is None:
            fail("stdout", "stdout is not one JSON object", name)
            continue
        reports[command["profile"]][name] = report
        check_exit_code(command["profile"], report, done.returncode, name)
        if strict:
            if done.stderr:
                fail("stderr", "wrote to stderr", name)
            check_commands_as_arguments(report, name)
        if first is None:
            first = (command, argv, report, done.returncode)
    for profile, by_name in reports.items():
        for name, messages in validate(schemas, SCHEMA_OF_PROFILE[profile], by_name).items():
            for message in messages:
                fail("report-schema", message, name)

    if log and first is not None:
        command, argv, report, code = first
        log_env = dict(env)
        log_argv = list(argv)
        if "arg" in log:
            log_argv.insert(1 + len(command["name"].split(" ")), log["arg"])
        else:
            log_env[log["env"]] = "1"
        done = run(log_argv, options.timeout, log_env)
        name = command["name"]
        if done is None:
            fail("timeout", "did not finish in time with the log on", name)
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
            if logged is None or logged.get("status") != report.get("status") or done.returncode != code:
                fail("log-changes-report", "the status or the exit code changed with the log on", name)

    done = run([binary, "--version"], options.timeout, env)
    expected = f"{describe['name']} {describe['version']}\n"
    if done is None or done.returncode != 0 or done.stdout != expected:
        fail("version-line", f"--version did not print exactly {expected!r} and exit 0")
    elif strict and done.stderr:
        fail("stderr", "--version wrote to stderr")
    return len(runnable)


def emit(report, code):
    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")
    sys.exit(code)


if __name__ == "__main__":
    try:
        commands = main()
    except CannotRun as error:
        emit(
            {
                "status": "not-run",
                "error": str(error),
                "error_kind": "environment",
                "next_action": None,
                "next_action_reason": None,
                "next_action_argv": None,
                "next_action_inputs": [],
            },
            2,
        )
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
