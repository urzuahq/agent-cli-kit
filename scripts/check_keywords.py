"""Fail when a schema uses a JSON Schema keyword outside the list consumers were told about."""
import json
import pathlib
import sys

# A consumer may interpret the schemas with its own code and stop on a keyword it does not know.
# Adding one here is a change consumers are told about before the release that carries it.
ANNOTATIONS = {"$schema", "$id", "title", "description"}
ASSERTIONS = {
    "type", "enum", "const", "required", "pattern", "format",
    "minimum", "minLength", "maxLength",
}
ONE_SCHEMA = {"items", "additionalProperties", "if", "then", "else"}
SCHEMA_LIST = {"allOf"}
SCHEMA_MAP = {"properties", "$defs"}
KNOWN = ANNOTATIONS | ASSERTIONS | ONE_SCHEMA | SCHEMA_LIST | SCHEMA_MAP | {"$ref"}


def unknown(schema, where):
    if not isinstance(schema, dict):
        return
    for key, value in schema.items():
        here = f"{where}/{key}"
        if key not in KNOWN:
            yield here
        elif key in ONE_SCHEMA:
            yield from unknown(value, here)
        elif key in SCHEMA_LIST:
            for index, item in enumerate(value):
                yield from unknown(item, f"{here}/{index}")
        elif key in SCHEMA_MAP:
            for name, item in value.items():
                yield from unknown(item, f"{here}/{name}")


failed = False
for path in sorted(pathlib.Path(sys.argv[1]).glob("*.schema.json")):
    for where in unknown(json.loads(path.read_text()), ""):
        print(
            f"FAIL  {path.name} uses a keyword consumers were not told about: {where}",
            file=sys.stderr,
        )
        failed = True
sys.exit(1 if failed else 0)
