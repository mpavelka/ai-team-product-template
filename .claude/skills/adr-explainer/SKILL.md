---
name: adr-explainer
description: Turn a decision record into a short, plain-language explainer with simple diagrams, published as an Artifact. Use whenever an ADR is written or amended, or when a human says a record is confusing, overwhelming, dense or too long — "explain this ADR", "summarise ADR-011", "what does this record actually say", "make this readable". Also covers PRDs and component records. Produces the explainer only; it never edits the record.
---

# Explain a decision record

Our records are long on purpose. An ADR carries the argument, the rejected options, the
dated corrections and the accepted risks, because a decision nobody can audit later is
not a decision. That is the right shape for a record and the wrong shape for a reader who
just needs to know what we do about email.

This skill produces the second thing: one page, plain language, a diagram or two, read in
under three minutes.

## Rules

1. **Never edit the record.** This skill is read-only against `architecture/` and
   `product/`. If reading it surfaces a contradiction or a stale fact, say so in the chat
   and let the human route it to the `architect` skill. Do not fix it here and do not fix
   it in the explainer by quietly writing what the record should have said.
2. **The record is the authority.** The page says so in its footer. A reader who acts on
   the explainer alone must still land in the right place.
3. **Do not soften.** Where the record admits a weak spot, an unverified claim or an open
   TODO, the explainer says it too. An explainer that only carries the good news is worse
   than no explainer, because it gets trusted.
4. **Do not invent.** Every claim traces to the record. No filled-in rationale, no
   plausible-sounding numbers, no tidy conclusion the record did not reach.

## Step 1 — read the whole record, comments first

Records are layered, and the layers disagree on purpose:

- `decision:` is the original argument, as its first readers saw it.
- `comments:` amend it in date order. A later comment can overturn the body's central
  claim, move the status, or close a risk.
- In-place corrections carry a dated parenthetical — `*(Corrected 2026-08-29, issue
  #94 …)*`. The sentence around one has already been rewritten once.

So read `comments:` **first**, oldest to newest, then read the body knowing what has been
overturned. Reading in file order means writing an explainer of a superseded argument.

Check `status` before anything else. `proposed`, `accepted` and `superseded` are three
different pages. A proposed record is explained as a proposal, including what is still
gating acceptance.

## Step 2 — find the spine

Every record worth explaining turns on one load-bearing fact. Name it in a sentence.

The test: **if that fact were false, would the decision change?** If yes, it is the spine.
In ADR-011 it is "SES sandbox status belongs to an AWS account, not to an IAM user" —
everything else in six hundred lines follows from it.

Records usually flag their own spine with a heading like `## The constraint that settles
it`, or with a comment that verifies one premise more carefully than the rest. If you
cannot find a single spine, the record may genuinely hold several decisions; explain the
one the human asked about and say which ones you left out.

The spine is the centre of the page and normally the first diagram.

## Step 3 — the section spine

Use these sections, in this order. Each carries a short lowercase eyebrow label naming
its job, so the page can be scanned rather than read.

| Eyebrow | What it answers | Where it comes from |
| --- | --- | --- |
| *(a short-version box, before everything)* | what do we actually do | the decision, in three sentences |
| `the question` | why did anyone have to decide this | `## Context` |
| `the constraint` | the one fact that settles it | the spine from step 2 |
| `the options` | what was chosen, over what | `## Options considered` |
| `the design` | how it actually works | the decision body |
| `the guardrails` | what stops the obvious mistakes | the failure-mode section |
| `the trade` | what was given up, and where it is paid back | accepted risks + the compensating control |
| `still open` | honest loose ends | open TODOs, unverified claims, issues in other repos |

Drop any section the record has nothing for. Never pad one to keep the shape.

Two of these carry most of the value and are the easiest to skip, so do not skip them:

- **`the options`** — a rejected option with the reason it was rejected is what stops
  someone re-proposing it next quarter. Say which one is the recorded upgrade path, if
  the record names one.
- **`still open`** — this is where the explainer earns its trust.

## Step 4 — writing it

- One idea per sentence. If a sentence has two clauses joined by "and", it is usually two
  sentences.
- Name things the way a person would, then give the identifier once, in `code`. "A
  throwaway inbox in Docker" before `Mailpit`; "the function every part of the app calls
  to send mail" before `sendEmail()`.
- Cut the hedges. The record carries the nuance; the explainer carries the claim.
- **Keep the record's own good lines.** The sharpest sentence on the page is often
  already in the ADR — architects write well when they are annoyed. Quote it.
- Explain a rejection by its actual reason, not a polite one. "Rejected on cost, not on
  merit" is information; "not the right fit" is not.
- Banned: "simply", "just", "obviously", "of course". They tell a confused reader the
  confusion is their fault.
- Target: under three minutes end to end.

## Step 5 — diagrams

**Load the `artifact-diagramming` skill before drawing.** Two figures at most. Each has to
show a mechanism prose cannot; if a sentence says it faster, write the sentence.

Two shapes nearly always fit an ADR:

1. **The constraint.** Draw the assumption and the reality side by side, so the reader can
   point at the difference. This is the figure that makes a record click.
2. **The design.** The components, the arrows between them, and a label on every arrow.
   Draw the path that is blocked as well as the path that works — the dead end is half the
   decision.

Non-negotiables: hand-authored inline SVG, sized by `viewBox`, structure in
`currentColor` so both themes work, one meaningful hue reserved for the thing under
discussion, every arrow labelled, wrapped in `<figure>` with a `<figcaption>` stating what
the picture shows, and `role="img"` plus a matching `aria-label`.

## Step 6 — publish it

**Load the `artifact-design` skill before writing the page.** Utilitarian treatment: real
typographic hierarchy, considered spacing, a deliberate palette, no oversized hero.

Title it like a document someone will look for later — a short, specific noun phrase or
the question the page answers. "Where Dev Mail Goes", not "ADR-011 Summary" and not
"Architecture Overview".

Footer carries the record's path and one line saying the record is the authority.

**Updating an existing explainer:** call `Artifact` with `action: "list"`, find the page by
its title, and pass that `url` so it redeploys to the same link. Titles are therefore
stable — never rename an explainer once it is published, or the next amendment silently
creates a second page.

The explainer's URL is deliberately **not** written back into the record. The record's
`links` schema is `PRD | ADR | GitHub Issue`, and widening it is the architect's call, not
this skill's.

## When the trigger is an amendment

Rebuild the whole page. Do not bolt a changelog onto the end — a reader arriving for the
first time should not have to reconstruct the decision from a diff.

Then, in the chat rather than on the page, tell the human which sections moved and why.
That is what they actually need after an amendment lands.

## What this skill does not do

It is not the `architect` skill. It does not decide anything, does not touch records, does
not open pull requests against `architecture/`, and does not commission reviews. It reads
a decision somebody else made and makes it legible.
