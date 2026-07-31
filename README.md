# AI team product template

A starting point for a product built by an agent team, with the decisions written down
where both the humans and the agents can find them.

## What is in here

```
VISION.md                        the product's north star — you write this first
product/prd/                     product requirements (PRD), YAML
architecture/adr/                architecture decision records (ADR), YAML
architecture/components/         components register, Markdown
architecture/data-model/         entities, tables and relations, YAML
architecture/interfaces/         interfaces between components, YAML
.claude/agents/                  the six agents that run the project
.claude/skills/records-query/    query the registers from the CLI
```

Every register ships a `TEMPLATE.*.example` file next to the records documenting its
schema. Files ending in `.example` are ignored by tooling, so they never show up in
query results.

## Getting started

1. Write `VISION.md`: the problem, who has it, what success looks like, what is out of
   scope. The Product Manager asks for it and will not invent it for you.
2. Describe what you want built. The Product Manager decides whether it is a product
   decision (→ PRD), an architectural one (→ Architect and an ADR), or neither (→ a
   GitHub issue straight to the Coder).
3. Everything after that arrives as a pull request.

## The team

| Agent | Owns | Does |
| --- | --- | --- |
| **Product Manager** | the PRD | Decides scope and priority, deprecates requirements, routes work, writes the issues. |
| **Architect** | ADRs, components, data model, interfaces | Makes and records architectural decisions, keeps the registers consistent, creates implementation issues. |
| **Coder** | the code | Implements issues under DRY / KISS / hexagonal architecture, with tests, and opens the PR. |
| **Code Reviewer** | — | Reviews the diff for practice, structure and test quality. |
| **Security Reviewer** | — | Reviews code and proposed architecture; its findings go into the PR description. |
| **Tester** | — | Runs the app in Docker and exercises the change end to end. |

Three rules bind all of them: **changes only via pull request**, **never install
anything outside the project folder**, and **dependencies and the app itself run in
Docker**.

## Querying the records

```bash
# what has been decided, and what superseded it
python3 .claude/skills/records-query/scripts/records_query.py adr \
  --where status=accepted --fields id,date,short_description --sort date

# live product scope
python3 .claude/skills/records-query/scripts/records_query.py prd \
  --where status=active --fields id,title,priority

# anything, anywhere, mentioning a topic
python3 .claude/skills/records-query/scripts/records_query.py all --search "password reset"
```

Registers: `adr`, `prd`, `components`, `data-model`, `interfaces`, `all`. Filters combine
with `--where key=value`, `key!=value`, `key~=substring` and `key!~substring`, over
dotted paths (`comments.commenter.role=human`). `--fields` narrows the output, `--format
json` switches it. Full option list: `--help`, or `.claude/skills/records-query/SKILL.md`.

Python 3.9+ and nothing else — PyYAML is used if present, otherwise a built-in parser
handles the files. Tests:

```bash
python3 -m unittest discover -s .claude/skills/records-query/tests
```
