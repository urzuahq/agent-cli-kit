"""Cases for the runner's reading of a command string as one process."""
import importlib.util
import pathlib
import sys

path = pathlib.Path(__file__).resolve().parent / "conform.py"
spec = importlib.util.spec_from_file_location("conform", path)
conform = importlib.util.module_from_spec(spec)
spec.loader.exec_module(conform)

SPLITS = {
    "tool apply --ids '<record>'": ["tool", "apply", "--ids", "<record>"],
    'tool apply --ids "<record>"': ["tool", "apply", "--ids", "<record>"],
    "git add -- :/docs/rfc/a.md": ["git", "add", "--", ":/docs/rfc/a.md"],
    "tool --reason '<what changed in the pinned file>'": ["tool", "--reason", "<what changed in the pinned file>"],
    "tool run style --files 'my file.ts'": ["tool", "run", "style", "--files", "my file.ts"],
    "tool it\\'s": ["tool", "it's"],
    "tool \"a 'b' c\"": ["tool", "a 'b' c"],
    "tool '$HOME'": ["tool", "$HOME"],
    'tool "b\\$c"': ["tool", "b$c"],
    "tool --base=origin/main a~1": ["tool", "--base=origin/main", "a~1"],
    "tool ''": ["tool", ""],
    "tool  two   spaces": ["tool", "two", "spaces"],
    "tool a#b": ["tool", "a#b"],
}
REFUSED = [
    "tool apply --ids <record>",
    "a && b",
    "a | b",
    "a ; b",
    "tool > out",
    "tool $HOME",
    'tool "$HOME"',
    'tool "$(id)"',
    'tool "`id`"',
    "tool `id`",
    "tool *.md",
    "tool a?",
    "tool [ab]",
    "tool {b,c}",
    "tool ~/x",
    "tool #x",
    "a\nb",
    "X=1 tool",
    "tool 'unterminated",
    "tool (x)",
    "tool \\",
]

wrong = [f"{string!r} gave {conform.split_one_process(string)!r}" for string, argv in SPLITS.items()
         if conform.split_one_process(string) != argv]
wrong += [f"{string!r} was accepted" for string in REFUSED if conform.split_one_process(string) is not None]
for line in wrong:
    print(f"FAIL  command splitting: {line}", file=sys.stderr)
sys.exit(1 if wrong else 0)
