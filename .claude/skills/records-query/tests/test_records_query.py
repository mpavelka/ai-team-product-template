"""Unit tests for records_query.py — run with: python3 -m unittest discover .claude/skills/records-query/tests"""

from __future__ import annotations

import io
import contextlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import records_query as rq  # noqa: E402


ADR_YAML = """\
adr:
  - id: ADR-001
    status: accepted
    date: 2026-01-15
    short_description: Use PostgreSQL as the primary datastore
    decision: >
      We pick PostgreSQL because the data is relational.

      Read replicas come later.
    comments:
      - date: 2026-01-16
        commenter:
          role: human
          name: Miloslav
        comment: Agreed.  # inline comment must be stripped
    links:
      - type: PRD
        url: https://example.test/prd/1
  - id: ADR-002
    status: superseded
    date: 2026-02-02
    short_description: Session cookies over local storage
    decision: |
      Store the session JWT in an httpOnly cookie.
        Indented line is preserved.
    links: []
"""

PRD_YAML = """\
prd:
  - id: PRD-001
    title: Password reset
    priority: high
    status: active
    description: Users can reset a forgotten password.
    links:
      - type: ADR
        url: https://example.test/adr/2
"""

COMPONENT_MD = """\
# web-app

## Description

Next.js front end serving the customer UI.

## Type

Service

## Used Technology

- Next.js 15
- TypeScript

## Dependencies

- postgres

## Specific Requirements

Rate limiting: 100 req/min per IP.
"""


class Fixture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "architecture/adr").mkdir(parents=True)
        (self.root / "architecture/components").mkdir(parents=True)
        (self.root / "product/prd").mkdir(parents=True)
        (self.root / "architecture/adr/decisions.yaml").write_text(ADR_YAML)
        (self.root / "product/prd/password-reset.yaml").write_text(PRD_YAML)
        (self.root / "architecture/components/web-app.md").write_text(COMPONENT_MD)
        self.addCleanup(self._tmp.cleanup)

    def cli(self, *argv) -> str:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = rq.run([*argv, "--root", str(self.root)])
        self.assertEqual(code, 0)
        return buf.getvalue()


class TestMiniYaml(unittest.TestCase):
    def parse(self, text):
        return rq._MiniYaml(text, "<test>").parse()

    def test_nested_sequences_and_maps(self):
        data = self.parse(ADR_YAML)
        self.assertEqual([a["id"] for a in data["adr"]], ["ADR-001", "ADR-002"])
        self.assertEqual(data["adr"][0]["comments"][0]["commenter"]["name"], "Miloslav")
        self.assertEqual(data["adr"][0]["links"][0]["type"], "PRD")

    def test_inline_comment_stripped_but_url_kept(self):
        data = self.parse(ADR_YAML)
        self.assertEqual(data["adr"][0]["comments"][0]["comment"], "Agreed.")
        self.assertEqual(data["adr"][0]["links"][0]["url"], "https://example.test/prd/1")

    def test_folded_and_literal_block_scalars(self):
        data = self.parse(ADR_YAML)
        self.assertEqual(
            data["adr"][0]["decision"],
            "We pick PostgreSQL because the data is relational.\nRead replicas come later.\n",
        )
        self.assertEqual(
            data["adr"][1]["decision"],
            "Store the session JWT in an httpOnly cookie.\n  Indented line is preserved.\n",
        )

    def test_scalars_and_flow_collections(self):
        data = self.parse("a: 3\nb: true\nc: ~\nd: [x, y]\ne: 'quoted: value'\nf: []\n")
        self.assertEqual(data, {"a": 3, "b": True, "c": None, "d": ["x", "y"], "e": "quoted: value", "f": []})

    def test_tabs_rejected(self):
        with self.assertRaises(rq.RecordError):
            self.parse("adr:\n\t- id: X\n")

    def test_roundtrip_through_dumper(self):
        data = self.parse(ADR_YAML)
        self.assertEqual(self.parse(rq.dump_yaml(data)), data)


class TestComponentMarkdown(Fixture):
    def test_sections_become_fields(self):
        record = rq.parse_component_markdown(self.root / "architecture/components/web-app.md")
        self.assertEqual(record["name"], "web-app")
        self.assertEqual(record["type"], "Service")
        self.assertEqual(record["technology"], ["Next.js 15", "TypeScript"])
        self.assertEqual(record["dependencies"], ["postgres"])
        self.assertIn("100 req/min", record["requirements"])


class TestFilters(Fixture):
    def test_where_equals(self):
        out = self.cli("adr", "--where", "status=accepted")
        self.assertIn("ADR-001", out)
        self.assertNotIn("ADR-002", out)

    def test_where_not_equals_and_contains(self):
        self.assertIn("ADR-002", self.cli("adr", "--where", "status!=accepted"))
        self.assertIn("ADR-001", self.cli("adr", "--where", "short_description~=postgres"))
        self.assertNotIn("ADR-001", self.cli("adr", "--where", "short_description!~postgres"))

    def test_dotted_path_across_lists(self):
        out = self.cli("adr", "--where", "comments.commenter.role=human")
        self.assertIn("ADR-001", out)
        self.assertNotIn("ADR-002", out)

    def test_id_and_search(self):
        self.assertIn("ADR-002", self.cli("adr", "--id", "ADR-002"))
        self.assertIn("PRD-001", self.cli("all", "--search", "forgotten password"))

    def test_bad_where_expression(self):
        with self.assertRaises(rq.RecordError):
            rq.run(["adr", "--where", "nonsense", "--root", str(self.root)])


class TestOutput(Fixture):
    def test_field_selection_is_strict(self):
        out = self.cli("adr", "--fields", "id,status")
        self.assertIn("id: ADR-001", out)
        self.assertNotIn("decision", out)
        self.assertNotIn("_file", out)

    def test_dotted_field_selection(self):
        out = self.cli("adr", "--id", "ADR-001", "--fields", "id,links.url")
        self.assertIn("https://example.test/prd/1", out)

    def test_output_is_parseable_yaml_under_register_root(self):
        parsed = rq._MiniYaml(self.cli("prd"), "<out>").parse()
        self.assertEqual(parsed["prd"][0]["title"], "Password reset")

    def test_count_files_json_and_limit(self):
        self.assertEqual(self.cli("adr", "--count").strip(), "2")
        self.assertEqual(self.cli("adr", "--files").strip(), "architecture/adr/decisions.yaml")
        self.assertIn('"id": "ADR-001"', self.cli("adr", "--format", "json"))
        self.assertEqual(self.cli("adr", "--limit", "1", "--count").strip(), "1")

    def test_all_registers_grouped(self):
        out = self.cli("all")
        for root_key in ("adr:", "prd:", "components:"):
            self.assertIn(root_key, out)

    def test_sort(self):
        out = self.cli("adr", "--sort", "date", "--fields", "id")
        self.assertLess(out.index("ADR-001"), out.index("ADR-002"))

    def test_missing_register_directory_is_empty_not_an_error(self):
        self.assertEqual(self.cli("interfaces").strip(), "interface: []")

    def test_unknown_register_rejected(self):
        with self.assertRaises(rq.RecordError):
            rq.run(["nope", "--root", str(self.root)])


if __name__ == "__main__":
    unittest.main()
