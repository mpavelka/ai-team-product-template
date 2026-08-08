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
.claude/skills/                  the three roles you act as, in the conversation
.claude/agents/                  the three sub-agents you spawn for independent review
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

Six roles, in two kinds.

**Skills** — the assistant loads these and acts as them in your conversation. You see
every step and can redirect at any point.

| Skill | Owns | Does |
| --- | --- | --- |
| **Product Manager** | the PRD | Decides scope and priority, deprecates requirements, routes work, writes the issues. |
| **Architect** | ADRs, components, data model, interfaces | Makes and records architectural decisions, keeps the registers consistent, creates implementation issues. |
| **Coder** | the code | Implements issues under DRY / KISS / hexagonal architecture, with tests, and opens the PR. |

**Sub-agents** — spawned into a separate context, asked first, and reporting back a
verdict. Independence is the point: a reviewer that watched the code get written is
biased towards approving it.

| Sub-agent | Does |
| --- | --- |
| **Code Reviewer** | Reviews the diff for practice, structure and test quality. |
| **Security Reviewer** | Reviews code and proposed architecture; its findings go into the PR description. |
| **Tester** | Runs the app in Docker and exercises the change end to end. |

The Coder asks before spawning any of the three — on a one-line fix all three are waste,
on anything touching auth or data integrity skipping them is negligence. You decide.

Three rules bind all six: **changes only via pull request**, **never install anything
outside the project folder**, and **dependencies and the app itself run in Docker**.

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
