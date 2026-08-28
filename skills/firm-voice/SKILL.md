---
name: firm-voice
description: House writing style for customer-facing proposal responses and RFP replies. Use when drafting, structuring, or editing the final proposal document — covers tone, section structure, how to phrase gaps and concessions, banned phrasings, and the standard document skeleton. Trigger on any request to write, assemble, polish, or restructure a proposal response, executive summary, or customer-facing deal document.
---

# Firm Voice

> **PLACEHOLDER.** This is a generic B2B enterprise voice, written so the demo produces a
> plausible document without claiming to represent any real firm. Before using this for real work,
> replace it with your own — see **Making it yours** at the bottom. Everything above that section is
> meant to be overwritten.

## 1. Stance

Write as a senior partner who has already decided this deal is worth winning and is now being
straight with the customer about how it will go. Confident, specific, unhurried. Never breathless.

The reader is a procurement lead and a technical lead reading six of these. What earns their
attention is precision and candour, not enthusiasm.

## 2. Structure

Every proposal response uses this skeleton, in this order:

1. **Executive summary** — three bullets, no more. Each bullet is a claim plus the evidence for it.
2. **Our understanding of your need** — restate their problem in their words before offering
   anything. If this section could have been written without reading their RFP, rewrite it.
3. **Why we fit** — capability against their stated requirements, including where we do not fit.
4. **Commercial proposal** — numbers, term, payment. No ranges where a number is possible.
5. **Contract approach** — our position on the terms they asked for, including what we will not do.
6. **Risks and mitigations** — named risks with named mitigations.

## 3. How to phrase a gap

This is the part most proposals get wrong. A gap stated plainly, early, with a mitigation reads as
competence. The same gap discovered by the customer in week three reads as a bait-and-switch.

- **Lead with the gap, not the cushion.** "Our standard tier is 99.95%, not the 99.99% you asked
  for" — then the options. Not "we offer industry-leading availability including options up to
  99.99%".
- **Price the fix if there is one.** A gap with a number attached is a decision. A gap without one
  is a worry.
- **Recommend, do not upsell.** If they probably do not need the add-on, say so. It is the single
  most credible thing in the document.

## 4. How to phrase a refusal

When declining a term, give the reason, then the counter. Never decline without countering.

> "We can't accept uncapped breach liability — our cyber policy would not cover it, which leaves you
> with an indemnity that is unfunded rather than one that is capped. We propose 24 months of fees
> plus our $5M cyber cover, with the carve-outs you'd expect for gross negligence and IP."

## 5. Banned

- Superlatives without evidence: "world-class", "industry-leading", "best-in-class", "cutting-edge",
  "seamless", "turnkey", "robust".
- Hedges that commit to nothing: "we would likely be able to", "in most cases", "generally".
- Claiming a tested figure as a production figure, or rounding a tier up.
- Any sentence that would be equally true of every competitor. Delete it or make it specific.
- Exclamation marks.

## 6. Mechanics

- British English.
- Numbers as digits from ten up; currency always with the unit ("$1.35M", not "1.35 million").
- Tables for anything with more than three parallel items.
- No bold inside body sentences — bold is for labels and headings only.
- Every section stands alone: a reader who opens at "Commercial proposal" should not need section 2.

---

## Making it yours

This skill is the swap point. To put your own firm's voice in, edit only this file — nothing in the
pipeline references its contents, so no script changes are needed:

1. Replace sections 1–5 with your own stance, structure, and phrasing rules.
2. Keep section 5 (banned list) concrete. "Be professional" is not actionable; a list of specific
   phrases you never want to see is.
3. Keep the frontmatter `description` trigger-rich — that string is the entire basis on which the
   model decides to load this skill.
4. Re-run `python3 upload_skills.py` to push the new version. It tracks each skill by the ID
   recorded in `.skill_ids.json` and fingerprints the bundle, so it uploads a new version only when
   the content actually changed — and never adopts a same-named skill belonging to someone else.

Leave the `PLACEHOLDER` banner in place until you have actually done this, so nobody mistakes the
sample voice for a real house style.
