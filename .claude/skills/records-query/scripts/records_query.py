#!/usr/bin/env python3
"""Filter, search and present the project's decision records.

Registers covered:
  adr          architecture/adr/*.yaml            (ADRs)
  prd          product/prd/*.yaml                 (product requirements)
  components   architecture/components/*.md       (components register)
  data-model   architecture/data-model/*.yaml     (entities)
  interfaces   architecture/interfaces/*.yaml     (interfaces register)
  questions    product/questions/*.yaml           (open questions)

Output is YAML (or JSON with --format json).

PyYAML is used when importable; otherwise a small built-in parser handles the
YAML subset these records are written in. No third-party install required.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

try:  # optional fast path
    import yaml as _pyyaml
except ImportError:  # pragma: no cover - depends on environment
    _pyyaml = None


# --------------------------------------------------------------------------
# Register definitions
# --------------------------------------------------------------------------

REGISTERS = {
    "adr": {"dir": "architecture/adr", "glob": "*.yaml", "root": "adr", "kind": "yaml"},
    "prd": {"dir": "product/prd", "glob": "*.yaml", "root": "prd", "kind": "yaml"},
    "components": {
        "dir": "architecture/components",
        "glob": "*.md",
        "root": "components",
        "kind": "markdown",
    },
    "data-model": {
        "dir": "architecture/data-model",
        "glob": "*.yaml",
        "root": "model",
        "kind": "yaml",
    },
    "interfaces": {
        "dir": "architecture/interfaces",
        "glob": "*.yaml",
        "root": "interface",
        "kind": "yaml",
    },
    "questions": {
        "dir": "product/questions",
        "glob": "*.yaml",
        "root": "questions",
        "kind": "yaml",
    },
}

ALIASES = {
    "adrs": "adr",
    "decisions": "adr",
    "prds": "prd",
    "requirements": "prd",
    "component": "components",
    "datamodel": "data-model",
    "data_model": "data-model",
    "entities": "data-model",
    "interface": "interfaces",
    "question": "questions",
}


class RecordError(Exception):
    """Raised for malformed records or bad CLI input."""


# --------------------------------------------------------------------------
# Minimal YAML reader (fallback when PyYAML is unavailable)
# --------------------------------------------------------------------------


class _Line:
    __slots__ = ("indent", "text", "raw", "no", "blank")

    def __init__(self, raw: str, no: int):
        self.raw = raw.rstrip("\n")
        self.no = no
        stripped = self.raw.strip()
        self.blank = not stripped or stripped.startswith("#")
        self.text = _strip_comment(self.raw).rstrip()
        self.indent = len(self.raw) - len(self.raw.lstrip(" "))


def _strip_comment(text: str) -> str:
    quote = None
    for i, ch in enumerate(text):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "#" and (i == 0 or text[i - 1] in " \t"):
            return text[:i]
    return text


_INT_RE = re.compile(r"^[-+]?\d+$")
_FLOAT_RE = re.compile(r"^[-+]?(\d+\.\d*|\.\d+)([eE][-+]?\d+)?$")


def _scalar(token: str):
    token = token.strip()
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "'\"":
        body = token[1:-1]
        if token[0] == '"':
            return body.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")
        return body.replace("''", "'")
    if token in ("", "~", "null", "Null", "NULL"):
        return None
    if token in ("true", "True", "TRUE"):
        return True
    if token in ("false", "False", "FALSE"):
        return False
    if _INT_RE.match(token):
        return int(token)
    if _FLOAT_RE.match(token):
        return float(token)
    if token.startswith("[") and token.endswith("]"):
        return [_scalar(p) for p in _split_flow(token[1:-1])] if token[1:-1].strip() else []
    if token.startswith("{") and token.endswith("}"):
        out = {}
        for part in _split_flow(token[1:-1]):
            k, _, v = part.partition(":")
            out[_scalar(k)] = _scalar(v)
        return out
    return token


def _split_flow(body: str) -> list[str]:
    parts, depth, quote, buf = [], 0, None, ""
    for ch in body:
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(buf)
            buf = ""
            continue
        buf += ch
    if buf.strip():
        parts.append(buf)
    return [p.strip() for p in parts]


def _split_key(text: str):
    """Split ``key: value`` -> (key, value). Returns None when not a mapping."""
    quote = None
    for i, ch in enumerate(text):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == ":" and (i + 1 == len(text) or text[i + 1] == " "):
            key = text[:i].strip()
            if not key:
                return None
            if len(key) >= 2 and key[0] == key[-1] and key[0] in "'\"":
                key = key[1:-1]
            return key, text[i + 1 :].strip()
    return None


class _MiniYaml:
    """Parses the block-style YAML subset used by the record files."""

    BLOCK_MARKERS = ("|", ">", "|-", ">-", "|+", ">+")

    def __init__(self, text: str, source: str):
        self.source = source
        self.lines = [_Line(raw, n) for n, raw in enumerate(text.splitlines(), 1)]
        for ln in self.lines:
            if not ln.blank and "\t" in ln.raw[: ln.indent + 1]:
                raise RecordError(f"{source}:{ln.no}: tabs are not allowed for indentation")

    def parse(self):
        i = self._skip(0)
        if i >= len(self.lines):
            return None
        value, _ = self._node(i, self.lines[i].indent)
        return value

    # -- helpers ---------------------------------------------------------
    def _skip(self, i: int) -> int:
        while i < len(self.lines) and self.lines[i].blank:
            i += 1
        return i

    def _node(self, i: int, indent: int):
        i = self._skip(i)
        if i >= len(self.lines) or self.lines[i].indent < indent:
            return None, i
        if self._is_seq_entry(self.lines[i]):
            return self._sequence(i, self.lines[i].indent)
        return self._mapping(i, self.lines[i].indent)

    @staticmethod
    def _is_seq_entry(line: _Line) -> bool:
        body = line.text.strip()
        return body == "-" or body.startswith("- ")

    def _sequence(self, i: int, indent: int):
        items = []
        while True:
            i = self._skip(i)
            if i >= len(self.lines):
                break
            line = self.lines[i]
            if line.indent != indent or not self._is_seq_entry(line):
                break
            rest = line.text.strip()[1:].strip()
            if not rest:
                value, i = self._node(i + 1, indent + 1)
            elif _split_key(rest):
                # `- key: value` — re-read the entry as a mapping starting at
                # the column of the first key, so sibling keys line up.
                after_dash = line.text[line.indent + 1 :]
                col = line.indent + 1 + (len(after_dash) - len(after_dash.lstrip(" ")))
                self.lines[i] = _Line(" " * col + rest, line.no)
                value, i = self._mapping(i, col)
            else:
                value, i = _scalar(rest), i + 1
            items.append(value)
        return items, i

    def _mapping(self, i: int, indent: int):
        result: dict = {}
        while True:
            i = self._skip(i)
            if i >= len(self.lines):
                break
            line = self.lines[i]
            if line.indent != indent or self._is_seq_entry(line):
                break
            pair = _split_key(line.text.strip())
            if pair is None:
                raise RecordError(f"{self.source}:{line.no}: expected 'key: value'")
            key, rest = pair
            if rest in self.BLOCK_MARKERS:
                value, i = self._block_scalar(i + 1, indent, rest)
            elif rest == "":
                value, i = self._node(i + 1, indent + 1)
            else:
                value, i = _scalar(rest), i + 1
            result[key] = value
        return result, i

    def _block_scalar(self, i: int, indent: int, marker: str):
        raw_lines, base = [], None
        while i < len(self.lines):
            line = self.lines[i]
            body = line.raw.strip()
            if not body:
                raw_lines.append("")
                i += 1
                continue
            if line.indent <= indent:
                break
            if base is None:
                base = line.indent
            raw_lines.append(line.raw[base:])
            i += 1
        while raw_lines and not raw_lines[-1]:
            raw_lines.pop()
        if marker[0] == "|":
            text = "\n".join(raw_lines)
        else:  # folded
            chunks, buf = [], []
            for raw in raw_lines:
                if raw:
                    buf.append(raw.strip())
                else:
                    chunks.append(" ".join(buf))
                    buf = []
            chunks.append(" ".join(buf))
            text = "\n".join(chunks)
        if not marker.endswith("-") and text:
            text += "\n"
        return text, i


def load_yaml(path: Path):
    text = path.read_text(encoding="utf-8")
    if _pyyaml is not None:
        try:
            return _pyyaml.safe_load(text)
        except _pyyaml.YAMLError as exc:  # pragma: no cover - message passthrough
            raise RecordError(f"{path}: {exc}") from exc
    return _MiniYaml(text, str(path)).parse()


# --------------------------------------------------------------------------
# YAML writer (stable output regardless of PyYAML being present)
# --------------------------------------------------------------------------

_PLAIN_SAFE = re.compile(r"^[A-Za-z0-9_./@+][^:#\n]*$")


def _dump_scalar(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if "\n" in text:
        return ""  # handled by caller as a block scalar
    if (
        not text
        or not _PLAIN_SAFE.match(text)
        or text.strip() != text
        or text.rstrip().endswith(":")
        or _INT_RE.match(text)
        or _FLOAT_RE.match(text)
        or text in ("true", "false", "null", "~")
    ):
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text


def dump_yaml(value, indent: int = 0) -> str:
    pad = " " * indent
    if isinstance(value, dict):
        if not value:
            return pad + "{}\n"
        out = []
        for key, item in value.items():
            head = f"{pad}{_dump_scalar(str(key))}:"
            out.append(_dump_entry(head, item, indent))
        return "".join(out)
    if isinstance(value, list):
        if not value:
            return pad + "[]\n"
        out = []
        for item in value:
            if isinstance(item, (dict, list)) and item:
                body = dump_yaml(item, indent + 2)
                out.append(pad + "-" + body[indent + 1 :])
            else:
                out.append(_dump_entry(f"{pad}-", item, indent))
        return "".join(out)
    return pad + _dump_scalar(value) + "\n"


def _dump_entry(head: str, item, indent: int) -> str:
    if isinstance(item, (dict, list)):
        if not item:
            return f"{head} {'{}' if isinstance(item, dict) else '[]'}\n"
        return head + "\n" + dump_yaml(item, indent + 2)
    text = str(item) if item is not None else ""
    if item is not None and not isinstance(item, (bool, int, float)) and "\n" in text:
        # `|` keeps a single trailing newline, `|-` strips it, so round-trips are exact.
        marker = "|" if text.endswith("\n") and not text.endswith("\n\n") else "|-"
        body = "\n".join(" " * (indent + 2) + ln if ln else "" for ln in text.rstrip("\n").split("\n"))
        return f"{head} {marker}\n{body}\n"
    return f"{head} {_dump_scalar(item)}\n"


# --------------------------------------------------------------------------
# Loading records
# --------------------------------------------------------------------------

_MD_FIELD_ALIASES = {
    "used technology": "technology",
    "technology": "technology",
    "specific requirements": "requirements",
    "requirements": "requirements",
    "description": "description",
    "type": "type",
    "dependencies": "dependencies",
    "name": "name",
}


def parse_component_markdown(path: Path) -> dict:
    """Parse a component register entry (`# Name` + `## Section` blocks)."""
    record: dict = {}
    section, buffer = None, []

    def flush():
        if section is None:
            return
        body = "\n".join(buffer).strip()
        bullets = [ln.strip()[2:].strip() for ln in body.splitlines() if ln.strip().startswith(("- ", "* "))]
        record[section] = bullets if bullets and len(bullets) == len(body.splitlines()) else body

    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            flush()
            section, buffer = None, []
            record["name"] = line[2:].strip()
        elif line.startswith("## "):
            flush()
            title = line[3:].strip().lower()
            section, buffer = _MD_FIELD_ALIASES.get(title, title.replace(" ", "_")), []
        else:
            buffer.append(line)
    flush()
    record.setdefault("name", path.stem)
    return record


def load_register(root: Path, register: str) -> list[dict]:
    spec = REGISTERS[register]
    directory = root / spec["dir"]
    if not directory.is_dir():
        return []
    records = []
    for path in sorted(directory.glob(spec["glob"])):
        if path.name.startswith("."):
            continue
        rel = str(path.relative_to(root))
        if spec["kind"] == "markdown":
            items = [parse_component_markdown(path)]
        else:
            data = load_yaml(path)
            if data is None:
                continue
            if isinstance(data, dict):
                items = data.get(spec["root"], data)
            else:
                items = data
            if isinstance(items, dict):
                items = [items]
            if not isinstance(items, list):
                raise RecordError(f"{rel}: expected a list under '{spec['root']}:'")
        for item in items:
            if not isinstance(item, dict):
                raise RecordError(f"{rel}: every record must be a mapping, got {type(item).__name__}")
            item = dict(item)
            item["_file"] = rel
            records.append(item)
    return records


# --------------------------------------------------------------------------
# Filtering / projection
# --------------------------------------------------------------------------


def resolve_path(record, path: str) -> list:
    """Resolve a dotted path, fanning out over lists. Returns all matches."""
    values = [record]
    for part in path.split("."):
        nxt = []
        for value in values:
            if isinstance(value, list):
                value_list = value
            else:
                value_list = [value]
            for entry in value_list:
                if isinstance(entry, dict) and part in entry:
                    nxt.append(entry[part])
        values = nxt
        if not values:
            return []
    out = []
    for value in values:
        out.extend(value if isinstance(value, list) else [value])
    return out


_OPS = ("!~", "!=", "~=", "=")


def parse_where(expr: str):
    for op in _OPS:
        idx = expr.find(op)
        if idx > 0:
            return expr[:idx].strip(), op, expr[idx + len(op) :].strip()
    raise RecordError(f"invalid --where expression: {expr!r} (use key=value, key~=text or key!=value)")


def matches(record: dict, key: str, op: str, wanted: str) -> bool:
    values = resolve_path(record, key)
    texts = [str(v).lower() for v in values if v is not None]
    wanted_l = wanted.lower()
    if op == "=":
        return wanted_l in texts
    if op == "!=":
        return wanted_l not in texts
    if op == "~=":
        return any(wanted_l in t for t in texts)
    return not any(wanted_l in t for t in texts)  # !~


def contains_text(record: dict, needle: str) -> bool:
    return needle.lower() in json.dumps(record, default=str).lower()


def project(record: dict, fields: list[str]) -> dict:
    out = {}
    for field in fields:
        if "." not in field:
            if field in record:
                out[field] = record[field]
            continue
        values = resolve_path(record, field)
        if values:
            out[field] = values
    return out


def sort_key(record: dict, field: str):
    values = resolve_path(record, field)
    return (1, "") if not values else (0, str(values[0]).lower())


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def find_root(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env).resolve()
    here = Path.cwd().resolve()
    for candidate in [here, *here.parents]:
        if (candidate / ".git").exists() or (candidate / "architecture").is_dir():
            return candidate
    return here


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="records_query.py",
        description="Filter, search and present ADR / PRD / component / data-model / interface / question records.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  records_query.py adr --where status=accepted --fields id,short_description\n"
            "  records_query.py prd --where priority=high --where status!=deprecated\n"
            "  records_query.py interfaces --where between~=browser --fields id,name,endpoints\n"
            "  records_query.py all --search 'password reset' --fields id,_file\n"
        ),
    )
    parser.add_argument(
        "register",
        help="register to query: " + ", ".join(sorted(REGISTERS)) + ", or 'all'",
    )
    parser.add_argument("--root", help="project root (default: git root / CLAUDE_PROJECT_DIR / cwd)")
    parser.add_argument("--id", action="append", default=[], metavar="ID", help="keep records with this id (repeatable)")
    parser.add_argument(
        "--where",
        action="append",
        default=[],
        metavar="EXPR",
        help="filter: key=value, key!=value, key~=substring, key!~substring (repeatable, ANDed; dotted paths supported)",
    )
    parser.add_argument("--search", metavar="TEXT", help="free-text search across the whole record")
    parser.add_argument("--fields", metavar="A,B", help="output only these fields (dotted paths supported)")
    parser.add_argument("--sort", metavar="FIELD", help="sort records by this field")
    parser.add_argument("--limit", type=int, metavar="N", help="return at most N records")
    parser.add_argument("--count", action="store_true", help="print only the number of matches")
    parser.add_argument("--files", action="store_true", help="print only the source files of matches")
    parser.add_argument("--format", choices=("yaml", "json"), default="yaml", help="output format (default: yaml)")
    return parser


def collect(root: Path, register: str) -> list[tuple[str, dict]]:
    names = sorted(REGISTERS) if register == "all" else [register]
    return [(name, record) for name in names for record in load_register(root, name)]


def run(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    register = ALIASES.get(args.register.lower(), args.register.lower())
    if register != "all" and register not in REGISTERS:
        raise RecordError(f"unknown register {args.register!r}; expected one of: " + ", ".join(sorted(REGISTERS)) + ", all")

    root = find_root(args.root)
    pairs = collect(root, register)

    wheres = [parse_where(expr) for expr in args.where]
    wanted_ids = {i.lower() for i in args.id}
    selected = []
    for name, record in pairs:
        if wanted_ids and str(record.get("id", "")).lower() not in wanted_ids:
            continue
        if any(not matches(record, key, op, value) for key, op, value in wheres):
            continue
        if args.search and not contains_text(record, args.search):
            continue
        selected.append((name, record))

    if args.sort:
        selected.sort(key=lambda pair: sort_key(pair[1], args.sort))
    if args.limit is not None:
        selected = selected[: args.limit]

    if args.count:
        print(len(selected))
        return 0
    if args.files:
        for path in dict.fromkeys(record.get("_file", "") for _, record in selected):
            print(path)
        return 0

    fields = [f.strip() for f in args.fields.split(",") if f.strip()] if args.fields else None
    grouped: dict[str, list] = {}
    for name, record in selected:
        grouped.setdefault(REGISTERS[name]["root"], []).append(project(record, fields) if fields else record)

    payload = grouped if register == "all" else {REGISTERS[register]["root"]: grouped.get(REGISTERS[register]["root"], [])}
    if args.format == "json":
        print(json.dumps(payload, indent=2, default=str))
    else:
        sys.stdout.write(dump_yaml(payload))
    return 0


def main() -> int:
    try:
        return run(sys.argv[1:])
    except RecordError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
