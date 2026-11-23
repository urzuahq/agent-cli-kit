"""Fail when a $ref in schemas/ names a file or a JSON pointer that does not exist."""
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
docs = {p.name: json.loads(p.read_text()) for p in sorted(root.glob("*.schema.json"))}


def refs(node):
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str):
            yield ref
        for value in node.values():
            yield from refs(value)
    elif isinstance(node, list):
        for value in node:
            yield from refs(value)


def resolves(doc, pointer):
    node = doc
    for part in filter(None, pointer.split("/")):
        key = part.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict) and key in node:
            node = node[key]
        elif isinstance(node, list) and key.isdigit() and int(key) < len(node):
            node = node[int(key)]
        else:
            return False
    return True


failed = False
for name, doc in docs.items():
    for ref in refs(doc):
        target, _, pointer = ref.partition("#")
        target = target or name
        if target not in docs:
            print(f"FAIL  {name} refers to {target}, which is not in {root}/", file=sys.stderr)
            failed = True
        elif not resolves(docs[target], pointer):
            print(f"FAIL  {name} refers to {ref}, which does not resolve", file=sys.stderr)
            failed = True
sys.exit(1 if failed else 0)
