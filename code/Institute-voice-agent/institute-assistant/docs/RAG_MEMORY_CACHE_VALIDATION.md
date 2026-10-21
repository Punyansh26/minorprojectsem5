# Conversation memory and RAG cache validation — 23 September 2026

The implementation uses up to 10 previous complete question/answer pairs, bounded by
12,000 serialized history characters. Routing, answer generation and grounding review
receive the same window. Reply metadata retains each resolved question. New sessions have
independent histories; the SQLite checkpoint mechanism is preserved.

The persistent SQLite cache stores verified retrieval results and reviewed answer drafts.
Exact keys include the active immutable release and effective inputs. A draft hit still
runs grounding review and quote validation. Entries expire after one hour, with a shared
2,000-entry LFU limit and a 128 KiB per-entry limit. Failed/action responses are excluded.

## Offline checks

**116 agent tests and 15 Demo 2 tests passed (131 total).** Both repositories also passed
`git diff --check`.

Run in the existing `minor` environment:

```bash
cd code/Institute-voice-agent/institute-assistant
python -m pytest -q
cd ../../demo2
python -m pytest -q
```

The agent suite covers complete-pair trimming, history character limits, legacy config,
English/Hindi/Hinglish history propagation to all model stages, resolved-query metadata,
new-session isolation, SQLite checkpoint reopening, missing query clarification, persistent
cache reuse, invalidation by inputs/release/date/model/prompts, expiry, frequency/age eviction,
size bounds, malformed JSON/schema/storage types, locked/unavailable cache fallback,
review rejection, invalid/blank quotes, provider failure and action exclusion.

Demo 2 checks include its real bridge-to-graph history/cache integration with fake providers,
independent browser sessions, data-directory isolation, and existing speech/retry behavior.
Tests use temporary storage and fake providers; they do not establish model rewrite quality.
Existing Chroma/LangChain Pydantic deprecation warnings remain.

## Live cache measurement

Run with the configured Groq model and the installed verified release:

```bash
LLM_RATE_LIMIT_MAX_WAIT_SECONDS=0 python evaluate_helpdesk.py --live \
  --case cache_exact --cache-benchmark --interval 35 \
  --output /tmp/minor-rag-cache-exact-live.json
```

Both runs answered the same fully specified public cutoff question in separate conversations.
The second graph instance reused the temporary persistent SQLite cache.

| Measurement | Cold | Warm |
| --- | ---: | ---: |
| Total answer time (seconds) | 5.122 | 2.641 |
| Logical model calls | 3 | 2 |
| Retrieval cache | miss | hit |
| Draft cache | miss | hit |
| Retrieval stage (milliseconds) | 2327.224 | 2.950 |
| Grounding review (milliseconds) | 961.892 | 1134.139 |

This is one cold/warm sample, excluding deliberate sleeps and all speech work. Cold retrieval
includes model/engine initialization. It is not a steady-state latency benchmark or evidence
of a universal percentage improvement. The warm run still contacted Groq for routing and review.

Earlier runs of a question omitting the institute name received different standalone rewrites
and therefore missed the exact cache. That is expected with conservative keys: equivalent
paraphrases are not merged. Fully specified English questions are prompted to retain their
wording. Model variation can still cause misses. A separate issue found by this live check—
integer `-1` versus reloaded float `-1.0` retrieval scores—was fixed by canonical serialization
and covered by the repeated-turn regression test.

## Follow-up evidence and limitations

The English live sequence asked for 2026 JoSAA round 5 CSE SC All India Gender-Neutral ranks,
then “And for ST?”, then “And round 4?”. The router correctly retained all unchanged
dimensions on both follow-ups. The ST reply returned 3215–3315. The final round-4 grounding
review hit a Groq rate limit and correctly returned `unavailable`; this run is not a full
multi-turn pass. Its initial SC answer was rejected as insufficient; subsequent standalone
SC checks answered correctly. The original rejected draft was not captured, so its precise
rejection cause is unconfirmed.

The successful SC replies (3627–4832) and ST reply (3215–3315) were checked against the saved
official HTML rows, not just mocked assertions. The source bytes matched SHA-256
`55c753899e0dec14e34c50885955ef50700c2187c0025ffceb68f14a645903b4` in the existing source audit.
Both rows specify CSE, AI quota and Gender-Neutral seats; the indexed evidence identifies
the numbers as category ranks. Source citations remain separate from speech text.

With 45-second spacing, the Hindi three-turn sequence passed all status, language and
resolved-dimension checks: the category changed from SC to ST, then round 5 changed to
round 4, while CSE/year/quota/seat pool remained intact. Both follow-up answers used Hindi.
The round-4 ST answer (3215–3315) was also checked against its original saved HTML row;
its bytes matched SHA-256 `a79f8c9cd822e9f8505fce11ef39db66c297f058ec18b67ffde8aac8bf6df059`.

The fixed public evaluation outputs are saved in [rag_memory_cache_live.json](rag_memory_cache_live.json).

### False-insufficient diagnosis

A traced Hinglish run reproduced two rejections despite correct retrieval and model reviews
returning `answered`. The model's multi-line quotations skipped the intervening
`Rank basis: Category rank` line. As a result, they were not contiguous source excerpts.
This explains a reproducible way that a supported follow-up can appear to lose its context.

The regression test reproduced `insufficient` before the repair and `answered` afterward.
For verified cutoff records only, the validator now expands ordered, uniquely matching
complete lines into their exact contiguous canonical source span. It restores omitted
source context, does not change the answer, and keeps the normal grounding review. Both
returned citations and cached drafts use the corrected quotation. No extra model call is
required. Reordered lines, changed numbers, partial lines, duplicate matches, translations,
legacy indexes and unstructured documents do not qualify for this repair.

Replaying the actual traced model outputs against the installed evidence changed quotation
validation for turns 1/2/3 from **fail/pass/fail** to **pass/pass/pass**. The restored source
spans include rank basis and remain exact source text. This deterministic replay establishes
the correction independently of another provider sample.

The original Hinglish sequence was then rerun live with 45-second spacing and all three
turns passed: SC round 5, ST round 5, then ST round 4. Both follow-ups retained CSE, 2026,
AI quota and Gender-Neutral seats and returned Hinglish answers with matching source rows.
Per-turn times excluding sleeps were 6.018, 3.670 and 3.304 seconds. This last model sample
used already contiguous quotations; the captured-output replay above specifically verifies
the omitted-line repair. The saved artifact retains both failed runs and the passing rerun.

The evaluator includes `followup_english`, `followup_hindi`, `followup_hinglish`,
`topic_switch`, and `unresolved_reference` cases. Chained cutoff checks validate the rewritten
dimensions as well as reply status. `--model-trace` can record validated model outputs for
these fixed public cases to inspect generation versus review; it never records exception
bodies. Live results require inspection against the original sources and remain subject to
provider quotas and model variation.

## Operation

Restart Demo 2 to load the changed modules and settings; no knowledge-base rebuild is needed.
Set `HISTORY_TURNS` to change k and `RAG_CACHE_ENABLED=false` to bypass the cache. Demo 2
stores its cache under `DEMO2_DATA_DIR`; the CLI uses `RAG_CACHE_DB_PATH`. The apps retain
their separate conversations and action databases. Active-state history trimming does not
delete older checkpoints. No database, source corpus, dependency stack or speech model was migrated.
