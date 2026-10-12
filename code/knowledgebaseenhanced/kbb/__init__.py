"""KBB v2 — parser-first, verified-by-structure, multi-granularity knowledge-base builder.

Design reference: ``15_KNOWLEDGE_BASE_PIPELINE_V2.md`` (method) and
``14_KNOWLEDGE_BASE_METHODOLOGY_REVIEW.md`` (why).  Operating rules for agents and humans
are in ``AGENTS.md`` next to this package.

Invariant #1 of the whole package: *the source text is the evidence; nothing generated is.*
Every string that can be quoted to a user comes from a parser / OCR text layer (or a human
correction recorded in the review store).  LLM output is only ever used as a retrieval aid
(contextual prefixes, synthetic questions, propositions, summaries) or as validated
*structure* patches that cannot change characters.
"""

__version__ = "2.0.0"
PIPELINE_VERSION = "kbb-2.0"
