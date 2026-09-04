# MCP Tool Surface — Chhattisgarhi Voice Shopping Assistant

**Status:** design contract. Not implemented — no code exists for any function below.
**Scope:** Level 2 (current Minor Project MVP) only.
**Canonical naming:** lower snake case. The intent taxonomy in `AGENTS.md` is written in upper case
(`SEARCH_PRODUCT`); the function names here are the single canonical spelling used in code and schemas.
**Schema version:** `shopping.v1` — bump before any incompatible change.

## 1. Purpose

This document defines the complete set of functions the LLM is permitted to call, and the rules those
functions obey. It is the contract that makes the grounding rule in `AGENTS.md` §5 enforceable: the
model routes and extracts arguments, the backend validates and executes, and only then may a spoken
response be constructed.

`AGENTS.md` names eight tools as the "minimum" family but does not fix their arguments, return shapes,
identity handling, or failure behavior. Those omissions are where the project's safety and research
claims are actually decided — tool-call schema-validity rate, correct-argument rate, hallucinated-entity
rate, and the safety false-negative rate are all properties of this surface, not of the prompt.

Agreeing this document before writing code lets the speech, backend, and mobile workstreams proceed
against a stable boundary.

## 2. Where MCP sits

The functions are a plain Python domain layer. MCP is a thin adapter over that layer, not the
production path.

The reason is latency. The provisional target is under five seconds from end of user speech to first
response audio byte, and the FastAPI orchestrator and the tool layer live in the same process. Adding
a JSON-RPC hop inside a live voice turn spends part of that budget and introduces a failure mode
without buying anything, because the orchestrator would be the only client.

MCP earns its place elsewhere:

- **Development.** The tools can be driven from an MCP host or the Inspector before the local
  instruction-tuned model is chosen or running.
- **RQ3.** Tool-calling reliability can be measured against a strong hosted model first, establishing
  a ceiling before failures are attributed to the local model.
- **RQ4.** The local-versus-API comparison needs both models to speak to the same tool surface without
  rewriting orchestration.

So: one domain layer, two adapters — in-process for the voice path, MCP for development and
evaluation. This is the adapter principle `AGENTS.md` already requires, and it keeps voice
orchestration separate from the reusable catalogue and cart layer.

## 3. Cross-cutting rules

These apply to every function. They are stated once here rather than repeated in each section, and
they are the substance of the design — the individual functions are mostly obvious once these hold.

### R1. Identity is never a model argument

No function accepts a user identifier or a cart identifier. Both are read from the authenticated
session context that the orchestrator injects server-side when the tool layer is constructed.

This is not a stylistic preference. If the model can name the cart, then a transcript — which
`AGENTS.md` requires treating as untrusted input — can name the cart too, and a prompt-injection
attempt or an ASR mishearing becomes a cross-account mutation. `AGENTS.md` requires rejecting
unauthorized user and cart IDs; the cheapest way to satisfy that is to make them unexpressible.

The same logic excludes **price** and **stock** from every input list. They are server-owned facts. A
model that can supply a price can forge one.

### R2. Names in, IDs out

Fuzzy spoken mentions and verified catalogue entities are different things, and `AGENTS.md` requires
the schemas to distinguish them.

Only two functions accept a raw spoken mention: `search_products` and `resolve_product`. Everything
that mutates state or performs arithmetic accepts a resolved `product_id` and nothing else. A function
that took a product *name* would have to guess, and guessing is what invents products.

### R3. Functions return grounded data and a template reference — never user-facing prose

Every result carries structured facts plus a `response_template_id` and a set of named slots. No
function returns an English sentence intended to be spoken.

If a function returned prose, that prose would become the spoken answer, and the model would be the
source of the response rather than the database. The grounding requirement in `AGENTS.md` §5 would
hold only by convention. Response text is assembled after grounding, then either translated to
Chhattisgarhi or taken from an approved Chhattisgarhi template.

### R4. Writes are turn-scoped

Mutating functions read the current turn ID from session context and fail if that turn has been
superseded — typically by barge-in, where the user interrupts and the previous turn's work is still
in flight.

Without this, a cart mutation from an abandoned turn commits after the user has already moved on, and
the spoken confirmation describes a cart the user did not ask for. `AGENTS.md` states the invariant
directly: stale results from an interrupted turn must never update the cart.

### R5. Idempotency keys are derived server-side

Cart and checkout mutations are keyed on the tuple (session, turn, function, validated arguments),
computed by the backend. The model does not supply the key and cannot vary it.

Rural connectivity means the mobile client will lose responses and retry. A server-derived key makes
the retry safe; a model-supplied one would be regenerated on each attempt and double-add.

### R6. Money is integer paise plus a display string

Every monetary value is an integer count of paise for machine use, alongside a preformatted display
string for template slots. No binary floating point appears anywhere near a price, per the explicit
decimal requirement in `AGENTS.md`.

### R7. Failures are model-visible or protocol-level, deliberately

A failure the model could have avoided by choosing better arguments — unknown product, out of stock,
unverified metadata, superseded turn — is returned as a model-visible tool error so the model can
recover in the same turn. A failure the model cannot fix — missing session context, database
unavailable — is a protocol-level error handled by the orchestrator, which then plays the local
Chhattisgarhi failure prompt. Mixing these up produces a model that retries things that cannot work.

## 4. The functions

Eleven functions: six read-only, three mutating, two conversational control. Every one is annotated
with a read-only or destructive hint so an MCP host can decide whether to prompt, though hints are
advisory and the backend enforces regardless.

### 4.1 `search_products`

**Purpose.** Find catalogue items matching a spoken description, returning candidates with resolved
identifiers so a later call can act on one.

**When the model chooses it.** The user is browsing or describing a need without naming one specific
item — "dhaan ke beej dikhao", "kaunse khaad hai".

| Input | Required | Notes |
| --- | --- | --- |
| `query` | no | Free text as spoken, after translation. May be empty when browsing by category alone. |
| `category` | no | Must be one of the values from the categories resource; an unknown value is an error, not a silent empty result. |
| `crop` | no | Filters on the product's crop-compatibility field. |
| `limit` | no | Bounded, small default. Long result lists are unusable in speech. |

**Returns.** An ordered list of candidates, each with `product_id`, display name, category, unit,
price, and an availability flag; plus a total match count and the `response_template_id` for reading
back a short result summary.

**Notes.** The result list is deliberately short. A spoken interface cannot read fifteen products, so
the limit is a UX constraint, not a performance one. Search is relational and full-text over the
catalogue; `AGENTS.md` forbids introducing retrieval-augmented generation here without evidence that
ordinary search is insufficient, because direct search cannot invent a product.

**Failure modes.** Unknown `category` → model-visible error naming the valid values. No matches is a
success with an empty list and a distinct template, not an error — "we don't stock that" is a real
answer.

**Satisfies.** FR-5. `SEARCH_PRODUCT`.

### 4.2 `resolve_product`

**Purpose.** Map exactly one spoken product mention to one verified `product_id`, or report that the
mention is ambiguous and return the candidates.

**When the model chooses it.** Before any mutation or calculation, whenever the user has named an item
rather than asked to browse. This is the bridge from R2's "names in" to "IDs out".

| Input | Required | Notes |
| --- | --- | --- |
| `mention` | yes | The product as the user said it, after translation. Code-switched and Devanagari forms are expected. |
| `context_crop` | no | A crop mentioned earlier in the conversation, used only to break ties. |

**Returns.** Either a confident single match with `product_id`, display name, and a match-confidence
score; or `ambiguous` with a short candidate list. Never a guess presented as a match.

**Why this exists as its own function.** It is not in the `AGENTS.md` list, but the surface is unsafe
without it. ASR and translation produce noisy mentions, and a shared resolver is the single place
where alias matching, transliteration variants, and the ambiguity threshold live — which also makes it
the single place to measure the hallucinated-entity rate. Folding resolution into `add_to_cart` would
hide that measurement and force that function to guess.

**Failure modes.** No plausible candidate → model-visible error, prompting the model toward
`search_products` or `request_clarification`. Ambiguity is a *successful* result, not a failure; the
model is expected to follow it with `request_clarification`.

**Satisfies.** Prerequisite for FR-7, FR-8. Implements the mention-versus-entity distinction
`AGENTS.md` requires.

### 4.3 `get_product_details`

**Purpose.** Return the full verified record for one resolved product.

**When the model chooses it.** The user asks what something is, what it is for, or what pack sizes
exist — "ye khaad kaise kaam karta hai", "iska packet kitna bada hai".

| Input | Required | Notes |
| --- | --- | --- |
| `product_id` | yes | Must come from `search_products` or `resolve_product`. |

**Returns.** Display name, description, category, unit, pack size, price, availability, crop
compatibility, and — where present — the seed-rate or application-rate metadata **together with its
provenance and verification status**. Plus the `response_template_id`.

**Notes.** The description field is catalogue copy, not generated text. Where rate metadata is
unverified, the verification status travels with it so a response template can decline to speak the
number. This is the same provenance discipline that `calculate_required_quantity` enforces — a fact
does not become speakable just because it was read rather than computed.

**Failure modes.** Unknown `product_id` → model-visible error. This is the primary guard against the
model inventing an identifier, so the nonexistent-product case is a required test, not an edge case.

**Satisfies.** FR-6. `PRODUCT_DETAILS`.

### 4.4 `check_price`

**Purpose.** Answer a narrow price or availability question, optionally for a specific quantity.

**When the model chooses it.** The user asks only about cost or stock — "kitne ka hai", "milega ki
nahi".

| Input | Required | Notes |
| --- | --- | --- |
| `product_id` | yes | Resolved identifier. |
| `quantity` | no | When given, a line total is computed. Omitted means unit price only. |
| `unit` | no | Required whenever `quantity` is given; must match or convert to the product's unit. |

**Returns.** Unit price, the product's unit, availability flag, and — when `quantity` was supplied —
the computed line total. Prices as integer paise plus display string, per R6.

**Notes.** This function overlaps `get_product_details`, which also returns price. Both are kept
because `AGENTS.md` prescribes both intents and because the narrow one is cheaper and easier for a
small model to route. The overlap is a real risk, and it is the specific pair to watch in the
intent confusion matrix: if `CHECK_PRICE` and `PRODUCT_DETAILS` confuse each other materially and the
confusion has no user-visible cost, merging them is the correct response — but that requires the
measurement first, and merging changes the documented taxonomy, so it needs a schema version bump.

**Failure modes.** Unknown `product_id`, or `quantity` given without `unit`, or a unit that cannot be
converted to the product's unit → model-visible error. Out of stock is a successful result with the
availability flag false, not an error.

**Satisfies.** FR-6. `CHECK_PRICE`.

### 4.5 `calculate_required_quantity`

**Purpose.** Convert a field area into a product quantity by ordinary arithmetic over verified,
versioned catalogue metadata. This is the function `AGENTS.md` constrains most tightly, because it is
the one place the system produces an agronomic number.

**When the model chooses it.** The user gives an area and wants an amount — "do acre ke liye kitna
beej lagegi".

| Input | Required | Notes |
| --- | --- | --- |
| `product_id` | yes | Resolved identifier. Never a name. |
| `area_value` | yes | Numeric, with plausibility bounds applied. |
| `area_unit` | yes | Closed set — acre, hectare, and local units only if a verified conversion exists. |
| `crop` | no | Where the metadata is crop-specific, used to select the applicable rate. |

**Returns.** The computed quantity and its unit, the rate that was applied, and a provenance block:
source, source date or version, the rate's units, the crop or context it applies to, and its
verification status. Plus the `response_template_id`.

**The permitted sequence.** `AGENTS.md` fixes seven steps, and the function performs them in order:
resolve a real catalogue item; read a verified, versioned metadata field from an authoritative source;
normalise area and product units deterministically; do ordinary arithmetic; apply explicit
plausibility bounds; return the value with its provenance; refuse or ask if metadata or units are
missing.

**The model never computes this.** It supplies the product and the area and receives a number. The
arithmetic is pure, deterministic, and unit-tested independently of any model, because an LLM
producing this figure from memory is the exact failure the project is designed to prevent.

**Behaviour on unverified metadata — read this before demonstrating.** The function **refuses** when
the rate metadata's verification status is not `verified`, returning a model-visible error rather than
a number.

The consequence is deliberate and worth stating plainly: until seed-rate data is sourced from IGKV or
another authoritative regional reference in Phase 1, this function refuses on real catalogue rows.
`AGENTS.md` is unambiguous that proposal-stage figures are not verified facts and must not enter the
product database. A tool that computed anyway — even flagged, even with a spoken caveat — would put an
unsourced agronomic number into a farmer's ear, which is the harm the safety boundary exists to
prevent. Clearly labelled non-authoritative fixtures should be used to exercise the success path in
tests and demos, and the source string must be surfaced in the response so a demo cannot pass fixture
data off as real.

This refusal is the safety invariant that is testable from day one, before any model is integrated.

**Failure modes.** Unverified or missing rate metadata; unknown `product_id`; an unconvertible or
unknown area unit; an area outside plausibility bounds; crop-specific metadata with no crop supplied
— all model-visible errors, each with a distinct reason so the model can either clarify or refuse
rather than retrying blindly.

**Satisfies.** FR-7. `CALCULATE_REQUIRED_QUANTITY`. Central to the safety boundary.

### 4.6 `view_cart`

**Purpose.** Report the current contents and running total of the session's cart.

**When the model chooses it.** The user asks what is in the basket or what it comes to — "tokri me kya
kya hai", "total kitna hua".

**Inputs.** None. The cart is identified entirely from session context, per R1. This function taking
no arguments at all is the clearest illustration of that rule.

**Returns.** Line items — each with `cart_item_id`, `product_id`, display name, quantity, unit, the
price captured at addition, and the line total — plus the item count, the cart total, and the
`response_template_id`.

**Notes.** Prices shown are `price_at_addition`, not today's catalogue price. If the catalogue price
has moved since the item was added, the response template must say so rather than quietly reporting a
different number than the one the user was told when they added it.

Each line carries `cart_item_id` because `remove_from_cart` needs a referent that survives the same
product appearing twice at different quantities.

**Failure modes.** An empty cart is a successful result with a distinct template. Missing session
context is a protocol-level error, not a model-visible one — the model cannot fix it.

**Satisfies.** FR-9. `VIEW_CART`.

### 4.7 `add_to_cart`

**Purpose.** Add a resolved product to the session's cart at a validated quantity, capturing the price
at the moment of addition.

**When the model chooses it.** The user commits to an item — "ye daal do", "do bori le lo". Only after
resolution, and only on a final transcript.

| Input | Required | Notes |
| --- | --- | --- |
| `product_id` | yes | Resolved identifier. |
| `quantity` | yes | Positive, bounded. This is purchase quantity, never field area — R2 and the `AGENTS.md` schema rule both require the distinction. |
| `unit` | yes | Must match or convert to the product's unit. |

**Returns.** The created or updated line item, the resulting cart total, and the
`response_template_id` for spoken confirmation. The confirmation is grounded in the post-write cart
state, not in what the model asked for, so a partial write cannot be confirmed as a complete one.

**Transactional behaviour.** The write runs in a single transaction with foreign-key enforcement and
records `price_at_addition`. Repeated adds of the same product accumulate quantity rather than
creating a duplicate line.

**Turn scope and idempotency.** Per R4, the write fails if its turn has been superseded by barge-in.
Per R5, the idempotency key is server-derived, so a client retry after a lost response updates
nothing. These two together are the difference between a demo and something that survives a rural
network — and both are invisible in the input schema by design.

**Failure modes.** Unknown `product_id`; non-positive or implausible quantity; unconvertible unit;
insufficient stock; superseded turn — all model-visible errors. Only finalised interpretations may
call this; provisional partial ASR results must not.

**Satisfies.** FR-8. `ADD_TO_CART`.

### 4.8 `remove_from_cart`

**Purpose.** Remove a line item from the session's cart, or reduce its quantity.

**When the model chooses it.** The user retracts something — "wo hata do", "ek bori kam kar do".

| Input | Required | Notes |
| --- | --- | --- |
| `cart_item_id` | yes | From `view_cart`. Not a product name, and not a positional reference like "the last one". |
| `quantity` | no | Omitted removes the whole line; given reduces by that amount. |
| `unit` | no | Required whenever `quantity` is given. |

**Returns.** The updated line item or a confirmation that the line was removed, the resulting cart
total, and the `response_template_id`.

**Why `cart_item_id` rather than `product_id`.** The same product can appear as more than one line, and
"hata do" is frequently anaphoric. Requiring an identifier the model must have read from `view_cart`
forces the ambiguity into the open: if the model cannot name the line, it must call `view_cart` or
`request_clarification` instead of removing a plausible-looking guess. Deleting the wrong item is
harder to notice by voice than adding the wrong one.

**Turn scope and idempotency.** As R4 and R5. Removing an already-removed line is treated as a success
under the same idempotency key, so a retry does not error.

**Failure modes.** Unknown `cart_item_id`, or one belonging to another session's cart; reduction
exceeding the line quantity; superseded turn. Ownership is checked server-side on every call.

**Satisfies.** FR-8. `REMOVE_FROM_CART`.

### 4.9 `checkout`

**Purpose.** Record a **simulated** order from the current cart. No payment is processed, no money
moves, no gateway is contacted, and nothing is dispatched.

This limitation belongs in this section rather than a footnote: the function is named `checkout`, and
anyone reading only this subsection must still learn that it settles nothing. Real UPI or
payment-gateway integration is explicitly Level 3 future work.

**When the model chooses it.** The user confirms they are finished — "order kar do".

| Input | Required | Notes |
| --- | --- | --- |
| `confirmed` | yes | Must be true. A separate explicit confirmation turn is required; the model may not infer commitment from a browsing utterance. |

Notably absent: any total, any address, any payment detail. The total is computed server-side from the
cart. A model-supplied total would be a number the user could be charged against, which R1 forbids.

**Returns.** The order identifier, the recorded total, the line count, a status, and an explicit
simulated-order flag that the response template must speak. Plus the `response_template_id`.

**Transactional behaviour.** One transaction: create the order, copy lines with `price_locked`, mark
the cart converted. Either all of it happens or none does. `price_locked` is what makes the order a
record of what the user agreed to rather than a pointer to a catalogue that can change afterwards.

**Turn scope and idempotency.** As R4 and R5, and this is the case where they matter most — a
duplicated checkout produces a second order. The key covers the cart's contents, so a retry returns
the original order rather than creating another.

**Failure modes.** Empty cart; `confirmed` not true; a stock conflict discovered at commit time;
superseded turn — all model-visible errors.

**Satisfies.** FR-10. `CHECKOUT`.

### 4.10 `request_clarification`

**Purpose.** Ask the user one short question when something needed is ambiguous or missing, and return
an approved question template rather than improvised wording.

**When the model chooses it.** Whenever a product, quantity, unit, area, cart referent, or intent is
unclear — including immediately after `resolve_product` returns `ambiguous`.

| Input | Required | Notes |
| --- | --- | --- |
| `missing_field` | yes | Closed set: product, quantity, unit, area, area unit, cart item, intent. |
| `candidates` | no | Options to read back, typically forwarded from an ambiguous resolution. |
| `context_note` | no | Short machine-readable hint about what prompted the question. Not spoken. |

**Returns.** A clarification template identifier and its slots. No prose.

**Why a function and not free text.** `AGENTS.md` §6 requires asking rather than guessing and names
clarification a normal conversational state that must appear in tests and in latency and usability
evaluation. Routing it through a function makes it schema-validated, auditable, and — critically —
**countable**: the clarification rate is a required metric, and it can only be measured if
clarification is a discrete event rather than a property of arbitrary model prose.

It also keeps the question inside the approved-template path, so a clarification does not become the
one place unreviewed generated text reaches the user by voice.

**Notes.** Clarification is a normal outcome, not a failure. It costs a turn, so the metric to watch is
its rate, not its presence; a system that never clarifies is guessing.

**Satisfies.** `AGENTS.md` §6. Supplies the clarification-rate metric.

### 4.11 `refuse_and_refer`

**Purpose.** Decline a request that falls outside the transactional boundary and return a fixed,
reviewed refusal and referral template pointing the user to a Krishi Vigyan Kendra or qualified
expert.

**When the model chooses it.** Any request for crop diagnosis, symptom interpretation, pesticide or
chemical selection, treatment, cure, or dosage and application instructions — including when phrased
indirectly, hypothetically, or on someone else's behalf.

| Input | Required | Notes |
| --- | --- | --- |
| `category` | yes | Closed set: diagnosis, chemical selection, dosage or application, other out-of-scope. |
| `detected_phrase` | no | Short excerpt for the audit record. Never echoed back to the user. |

**Returns.** A reviewed refusal template identifier and its slots. **No advice, no dosage, no improvised
disclaimer, and no contact details invented at call time** — referral details come from reviewed
configuration and must be verified before release.

**This is one layer, not the whole boundary.** `AGENTS.md` requires safety classification *before* tool
execution and defence in depth. This function is the model's single sanctioned exit; it does not replace
the classification stage that runs ahead of tool selection, the per-function policy checks, or the
deterministic entity validation. A model that fails to call it must still be stopped by the layer in
front of it.

**What it buys structurally.** Together with `request_clarification`, it removes the last reason for the
model to emit free-form text. The proposal claims prompt-injection resistance comes from the model being
able to emit only predefined tool calls "or short conversational text" — that trailing clause is the
gap. With clarification and refusal both expressed as functions, there is no legal move outside a
schema-validated call, and the claim becomes structural rather than instructional.

**Measurement.** False negatives (unsafe advice permitted) and false positives (a legitimate shopping
task blocked) must be counted separately — they have completely different costs, and a single accuracy
figure hides both. Test paraphrases, code-switching, euphemism, multi-turn setup, prompt injection, and
wording that sits between purchase quantity and application dosage.

**Satisfies.** FR-12. The `AGENTS.md` safety boundary.

## 5. Reference data, exposed as resources rather than functions

Two pieces of reference data are read-only and change rarely. They are described as MCP resources, not
callable functions.

| Resource | Contents |
| --- | --- |
| Categories | The closed set of category values, so the model grounds `category` arguments instead of inventing them. |
| Product alias lexicon | Versioned Chhattisgarhi, Hindi, and code-switched aliases and transliteration variants per product, with a version identifier. |

Two reasons for resources over functions. First, callable surface is scarce: eleven functions is
already a lot for a lightweight local model to route, and reference lookups that never change should
not compete for that attention. Second, `AGENTS.md` requires domain vocabulary and alias lists to be
injectable data rather than baked into the pipeline — a resource with a version identifier is exactly
that, and it lets a lexicon change be attributed in evaluation.

The lexicon is read by `resolve_product` and `search_products` server-side. Exposing it as a resource
is for inspection, versioning, and evaluation, not because the model is expected to do the matching.

## 6. Open decisions

Recorded here rather than silently settled, because all four are cheap to change now and expensive
later.

**Whether eleven functions is too many.** `resolve_product`, `request_clarification`, and
`refuse_and_refer` are additions beyond the eight `AGENTS.md` lists as its minimum. Each is justified
above, but the cost is real and lands on the project's own RQ3 risk: a small instruction-tuned model
routes a smaller surface more reliably. The decision to revisit after the first correct-tool-rate
measurement, not before.

**Whether `check_price` and `get_product_details` should merge.** See §4.4. Requires the confusion
matrix first, and a schema version bump.

**Whether `calculate_required_quantity` should ever compute from unverified metadata.** This document
specifies a hard refusal (§4.5). The alternative is to compute, tag the provenance as unverified, and
force a spoken caveat. That was rejected because the number still reaches the user as speech, and a
caveat in a low-resource language over a phone speaker is a weak control. If the team overrides this,
it should be recorded as an architectural decision with the reasoning, not changed quietly in code.

**How multi-turn context is carried.** Recalling a crop mentioned earlier is FR-17, a could-have. The
`context_crop` and `context_note` fields anticipate it without committing to it. If contextual memory
lands, decide whether context is model-supplied — in which case it is untrusted and must not influence
a calculation — or session-owned.

Deliberately **out of scope** here: storage engine, transport, prompt wording, and response-template
text. All sit behind this contract and none needs settling to agree the surface.

## 7. Traceability

Every function maps to a documented requirement. Nothing here exists only because it seemed useful.

| Function | `AGENTS.md` intent | FR | Primary research question |
| --- | --- | --- | --- |
| `search_products` | `SEARCH_PRODUCT` | FR-5 | RQ1, RQ3 |
| `resolve_product` | — (implied by the mention/entity rule) | prerequisite for FR-7, FR-8 | RQ1, RQ3 |
| `get_product_details` | `PRODUCT_DETAILS` | FR-6 | RQ3 |
| `check_price` | `CHECK_PRICE` | FR-6 | RQ3 |
| `calculate_required_quantity` | `CALCULATE_REQUIRED_QUANTITY` | FR-7 | RQ3, safety |
| `view_cart` | `VIEW_CART` | FR-9 | RQ3, RQ5 |
| `add_to_cart` | `ADD_TO_CART` | FR-8 | RQ1, RQ3 |
| `remove_from_cart` | `REMOVE_FROM_CART` | FR-8 | RQ1, RQ3 |
| `checkout` | `CHECKOUT` (simulated) | FR-10 | RQ3, RQ5 |
| `request_clarification` | — (`AGENTS.md` §6) | supports FR-4, FR-17 | RQ5, RQ6 |
| `refuse_and_refer` | — (safety boundary) | FR-12 | safety |

All eight canonical intents are covered. The three additions are each traceable to a written
`AGENTS.md` rule rather than to the intent list.

Requirements outside this surface: FR-1 to FR-3 and FR-11 belong to the voice core; FR-13 to
authentication; FR-14 to instrumentation; FR-15 and FR-16 to the mobile client. FR-4 is the
interpretation stage that *calls* this surface rather than part of it.

## 8. Review checklist

The properties to check when reviewing this contract, and later when reviewing its implementation:

1. No input list anywhere contains a user identifier, cart identifier, price, or stock level.
2. Only `search_products` and `resolve_product` accept a raw spoken mention; everything else takes a
   resolved `product_id` or `cart_item_id`.
3. No function returns user-facing prose. Every result carries a template reference and slots.
4. All three mutating functions document turn-supersession and idempotency behaviour.
5. `calculate_required_quantity` refuses on unverified metadata, and its provenance block carries
   source, date or version, units, applicable crop, and verification status.
6. `checkout` states that it is simulated within its own section.
7. Failures are classified as model-visible or protocol-level for a stated reason.
8. Every function traces to a requirement in §7.

## 9. Status and next step

Nothing described here is implemented. The surface is the contract; the next step is agreeing it, then
building the domain layer behind it with the MCP adapter over the top.

Two things should be settled alongside the first implementation, both deliberately excluded above:
the storage engine behind the repository boundary, and the reviewed Chhattisgarhi response templates
that the `response_template_id` values refer to. The template set is on the critical path for anything
spoken — the functions return references to templates that do not yet exist.









