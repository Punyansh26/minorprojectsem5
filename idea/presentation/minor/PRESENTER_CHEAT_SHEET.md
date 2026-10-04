# Presenter Cheat Sheet—Quick Reference for Defense

**Print this page and keep it with your notes during presentation/viva**

---

## 🎯 Core Thesis (One Sentence)
*"We built a zero-cost, privacy-preserving voice assistant that runs on a laptop GPU, supports rural dialects, and eliminates hallucinations through two-pass verification."*

---

## 📊 Headline Numbers (Memorize These)

| Metric | Value | Context |
|--------|-------|---------|
| **Cost Savings** | **682×** | $409/month → $0.60/month |
| **Retrieval Recall** | **98.9%** | vs 10.8% for naive vector RAG |
| **Hallucinations** | **0** | in 316 automated tests |
| **VRAM Budget** | **8GB** | Consumer laptop GPU |
| **Languages** | **3** | Hindi, English, Chhattisgarhi |
| **Warm Cache Latency** | **2.64s** | Text display (perceived) |
| **Test Coverage** | **316** | Passing unit + integration tests |
| **Data Rows** | **611** | Official JoSAA cutoffs (2022-2026) |

---

## 🔑 Three Key Innovations (30 seconds each)

### 1. Hybrid Retrieval (Dense + Sparse + Relational)
**Problem:** Vector search fails on numerical queries  
**Example:** "CSE cutoff" retrieves "ECE cutoff" (wrong program)  
**Solution:** Combine mE5 embeddings + BM25 + exact SQL for numbers  
**Result:** 10.8% → 98.9% recall (+88.17 percentage points)

### 2. Two-Pass Grounding Verification
**Problem:** LLMs hallucinate admission facts (18% error rate)  
**Example:** Fabricates closing rank or deadline  
**Solution:** Generation → Mandatory quote verification → Accept/Reject  
**Result:** 0 hallucinations in 120-case live benchmark

### 3. CPU-GPU Decoupled Architecture
**Problem:** Stacking LLM+ASR+TTS crashes 8GB GPUs  
**Example:** 6.4GB + 1.5GB + 1.2GB = 9.1GB (OOM)  
**Solution:** GPU only for LLM (6.3GB), CPU for speech (32GB RAM)  
**Result:** 100% uptime, deployable on consumer laptops

---

## 🛡️ Defense Responses to Critical Questions

### Q: "What's novel? Isn't this just standard RAG?"
**Response:** "Three novelties: (1) Hybrid retrieval solving the numbers problem, (2) Two-pass verification eliminating hallucinations, (3) Edge optimization for 8GB constraint. Standard RAG gets 10.8% recall and 18% hallucinations—we achieve 98.9% recall and 0% hallucinations."

### Q: "Why not use OpenAI/Google APIs?"
**Response:** "Three reasons: (1) Cost—$682× cheaper. (2) Privacy—campus data stays local. (3) Dialects—Chhattisgarhi has 45% WER on commercial APIs vs 12% on our system."

### Q: "Your latency is 15-18 seconds. Commercial systems do 2 seconds."
**Response:** "Two points: (1) We prioritize correctness over speed—better to take 15s than give wrong admission info. (2) Text-first UX shows answers in 2.6s (warm cache) while audio synthesizes—users read before hearing."

### Q: "What are the limitations?"
**Response:** "Four current limitations: (1) Cold turn latency 15-18s—roadmap includes Laya router (33ms). (2) Single-speaker TTS—no voice cloning. (3) Hindi/Chhattisgarhi only—English needs new checkpoints. (4) No streaming—implementing sentence-chunked TTS next."

### Q: "Has this been deployed?"
**Response:** "Validated on 120-case live benchmark with 316 automated tests. Deployment target: IIIT-NR helpdesk starting next counseling season. Current status: production-ready, awaiting infrastructure approval."

---

## 📚 Research Foundations (When Asked About Depth)

**Cite these papers to show academic grounding:**

1. **FrugalGPT** (Stanford, NeurIPS 2023): LLM cascades, 98% cost reduction
2. **RouteLLM** (UC Berkeley, 2024): Dynamic routing with preference data
3. **Adaptive-RAG** (KAIST, NAACL 2024): Query-complexity based retrieval
4. **VITS** (Kim et al., ICML 2021): End-to-end neural TTS
5. **Laya/JEV** (Convaiinnovations, 2026): System 1 decision models (33ms)

---

## ⚠️ Common Pitfalls to Avoid

❌ **Don't** read slides word-for-word  
✅ **Do** use slides as visual aids, explain in your words

❌ **Don't** start with mathematical formulations  
✅ **Do** start with user scenario and impact

❌ **Don't** claim perfection ("this solves everything")  
✅ **Do** acknowledge limitations and future work

❌ **Don't** get defensive when questioned  
✅ **Do** welcome questions and reframe to strengths

❌ **Don't** use jargon without explanation  
✅ **Do** define technical terms on first use

---

## 🎬 Opening Statement (Memorize This)

*"We built a zero-cost, privacy-preserving voice assistant for institutional helpdesks that runs entirely on a laptop GPU. Unlike commercial solutions costing $400/month, our system operates at $0.60/month while supporting rural dialects like Chhattisgarhi that commercial APIs fail on. The key innovation is a two-pass verification architecture that eliminates hallucinations—critical for admission counseling where incorrect cutoff information could misguide students."*

**Timing:** 30 seconds  
**Goal:** Hook audience with impact, not tech

---

## 🏁 Closing Statement (Memorize This)

*"This project demonstrates that production AI is an architectural discipline. By grounding every decision in peer-reviewed research, implementing rigorous verification, and working within real hardware constraints, we've built a system that's deployable today for institutional helpdesks and has a clear roadmap to sub-second conversational latency through System 1 decision models."*

**Timing:** 20 seconds  
**Goal:** Reinforce learning, show maturity

---

## 🔧 Technical Details (For Deep Dive Questions)

### VRAM Allocation
- **GPU:** Qwen3.5:9B Q4_K_M (6.3GB) + KV cache (0.85GB) + Display (0.8GB) = 7.95GB
- **CPU:** Whisper int8 (1.2GB) + VITS (1.9GB) + mE5 (0.8GB) = 3.9GB host RAM

### Latency Breakdown (Cold Turn)
- ASR: 1.85s | Routing: 3.80s | Retrieval: 0.05s  
- Generation: 7.18s | Grounding: 7.41s | TTS: 1.65s (parallel)  
- **Total perceived (text):** 18.68s | **Total with audio:** 21.2s

### Retrieval Architecture
- **Dense:** mE5-small (384d, cosine space, 350-token chunks)
- **Sparse:** Rank-BM25 (k1=2.5, b=0.75)
- **Relational:** SQLite (611 JoSAA rows, exact queries)
- **Fusion:** Reciprocal Rank Fusion (RRF)

### Two-Pass Flow
1. **Generation:** Ollama 9B drafts answer with citations
2. **Review:** Second pass verifies quotes exist verbatim in sources
3. **Accept:** If verified → display + cache
4. **Reject:** If unverified → abstain + draft ticket

---

## 📍 Where to Find Evidence

| Claim | Evidence Location |
|-------|-------------------|
| 682× cost savings | Doc 3, Section 3 (Financial Economics) |
| 98.9% recall | Doc 3, Section 4 (Retrieval Benchmarks) |
| Zero hallucinations | Doc 3, Section 4 (Hallucinated Citations row) |
| VRAM allocation | Doc 3, Section 5 (Hardware Constraints) |
| Two-pass architecture | Doc 2, Section 3.4 (Grounding Verification) |
| Chhattisgarhi WER | Doc 1, Literature Review (MMS section) |
| Latency breakdown | Doc 3, Section 2 (Stage Latency Table) |
| System 1 routing | Doc 4, Section 2 (Laya Integration) |

---

## 🎯 Presentation Timing Checkpoints

| Time | Checkpoint | Slide Range |
|------|-----------|-------------|
| 1:30 | Finished problem statement | Slides 1-2 |
| 3:00 | Completed system overview | Slide 3 |
| 6:15 | Explained all 3 innovations | Slides 4-6 |
| 8:00 | Shown quantitative results | Slides 7-8 |
| 11:00 | Covered vernacular + research | Slides 9-10 |
| 12:45 | Completed roadmap + takeaways | Slides 11-12 |
| 15:00 | Ready for Q&A | - |

**If running over time:** Skip detailed architecture (Slide 3 details), go straight to innovations.

---

## 💡 Confidence Boosters

### You Have Strong Evidence
- 316 automated tests passing (quantifiable quality)
- 120-case live benchmark (real-world validation)
- Peer-reviewed research foundations (academic rigor)
- Clear limitations discussion (intellectual honesty)

### You Solved Real Problems
- Cost barrier: $409 → $0.60
- Dialect gap: 45% WER → 12% WER
- Hallucinations: 18% → 0%
- Hardware constraints: Crashes → 100% uptime

### You Have a Clear Vision
- Current: Production-ready institutional helpdesk
- Near-term: Laya router (99.1% latency reduction)
- Medium-term: Streaming TTS (TTFA <1.5s)
- Long-term: Cross-lingual retrieval

---

## 🎤 Final Reminders

1. **Breathe.** Pause between slides.
2. **Make eye contact.** Don't stare at screen.
3. **Welcome questions.** They show engagement.
4. **Acknowledge when you don't know.** Better than making up answers.
5. **Stay calm.** You know this material better than anyone in the room.

**You've built something real. Show them why it matters.**

---

## 📞 Emergency Contact (If Presenting Remotely)

- Backup laptop ready?
- Mobile hotspot active?
- Slides downloaded locally (not cloud)?
- Demo video pre-recorded?
- Phone number shared with organizers?

---

**Good luck! You've got this. 🚀**
