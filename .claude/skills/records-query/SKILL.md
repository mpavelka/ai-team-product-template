---
name: records-query
description: Filter, search and present the project's decision records — ADRs (architecture/adr), PRDs (product/prd), the components register (architecture/components), the data model (architecture/data-model) and the interfaces register (architecture/interfaces). Use whenever a question asks what was decided, what is required, which components or interfaces exist, or what an entity looks like — e.g. "which ADRs cover auth?", "what's still active in the PRD?", "which interfaces touch the browser?", "show me the User entity". Prefer this over grepping the YAML by hand.
---

# Query the decision records

All five registers are queried through one script:

`.claude/skills/records-query/scripts/records_query.py`

It needs Python 3.9+ and nothing else — PyYAML is used when importable, otherwise a
built-in parser handles these files. Never install packages to make it run.

## Usage

```bash
python3 .claude/skills/records-query/scripts/records_query.py <register> [options]
```

Registers: `adr`, `prd`, `components`, `data-model`, `interfaces`, or `all`.

| Option | Effect |
| --- | --- |
| `--where EXPR` | Filter. `key=value` (exact), `key!=value`, `key~=text` (contains), `key!~text`. Repeatable, ANDed. Case-insensitive. Dotted paths fan out over lists: `comments.commenter.role=human`. |
| `--id ID` | Keep records with this `id`. Repeatable. |
| `--search TEXT` | Free-text search across the whole record. |
| `--fields A,B` | Return only these fields. Dotted paths allowed (`links.url`). |
| `--sort FIELD` | Sort by a field. |
| `--limit N` | Cap the number of records. |
| `--count` | Print the number of matches only. |
| `--files` | Print the source files of matches only. |
| `--format` | `yaml` (default) or `json`. |
| `--root PATH` | Project root. Defaults to `$CLAUDE_PROJECT_DIR`, the git root, or cwd. |

Output is always keyed by the register's own root key (`adr:`, `prd:`, `components:`,
`model:`, `interface:`), so it can be piped straight back into other tooling. Each
record carries `_file` with its source path unless `--fields` narrows it away.

## Reading ADRs without burning context

An ADR's `decision` is long prose; its `key_points` is the same decision as a handful of
bullets. Query `key_points` first and only fall through to `decision` for the ADRs whose
rationale you actually need. `--search` still covers the whole record, `decision`
included, so narrowing the output never narrows what you can find.

## Recipes

```bash
# Accepted ADRs, one line each
python3 .claude/skills/records-query/scripts/records_query.py adr \
  --where status=accepted --fields id,date,short_description --sort date

# What the accepted ADRs actually constrain — the cheap read before `decision`
python3 .claude/skills/records-query/scripts/records_query.py adr \
  --where status=accepted --fields id,short_description,key_points --sort date

# What is superseded, and by what
python3 .claude/skills/records-query/scripts/records_query.py adr \
  --where status=superseded --fields id,short_description,links.url

# Live product scope, highest priority first
python3 .claude/skills/records-query/scripts/records_query.py prd \
  --where status=active --where priority=high --fields id,title,description

# Components that depend on postgres
python3 .claude/skills/records-query/scripts/records_query.py components \
  --where dependencies~=postgres --fields name,type,technology

# Interfaces the browser talks to, with their endpoints
python3 .claude/skills/records-query/scripts/records_query.py interfaces \
  --where between~=browser --fields id,name,type,endpoints

# An entity's fields and relations
python3 .claude/skills/records-query/scripts/records_query.py data-model \
  --where entity=User --fields entity,table,fields,relations

# Everything mentioning password reset, anywhere
python3 .claude/skills/records-query/scripts/records_query.py all --search "password reset"
```

## Presenting results

Answer from the records, then cite the `_file` paths you used so the human can open
them. When a query returns nothing, say so plainly and check whether the register is
empty or the filter was too narrow (`--count` with fewer filters settles it) — never
fill the gap by guessing at a decision that was never recorded.

## Maintaining the script

Tests: `python3 -m unittest discover -s .claude/skills/records-query/tests`.
Schemas for each register live next to the records in `TEMPLATE.*.example` files; if a
schema changes, update the template, the loader in `records_query.py`, and the tests
together.
