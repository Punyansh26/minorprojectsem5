# 15-Minute Presentation Structure & Slide Guide

**Target Audience:** Faculty evaluators, industry practitioners, fellow students  
**Presentation Goal:** Demonstrate technical depth while maintaining accessibility  
**Total Slides:** 12-15 slides (excluding title/acknowledgments)

---

## Slide-by-Slide Structure

### Slide 1: Title (30 seconds)
**Title:** Cost-Efficient Voice-to-Voice RAG for Edge Deployment  
**Subtitle:** Zero-Cloud Conversational AI for Institutional Helpdesks  
**Visual:** System architecture icon + hardware spec badge (8GB GPU)

**Speaker Notes:**
- Emphasize "zero-cloud" and "edge deployment"
- Mention 316 passing tests, $682× cost savings upfront

---

### Slide 2: The Problem—Why This Matters (60 seconds)
**Title:** Real-World Problem: Voice AI That Works Without Internet  

**Content (3 bullets + visual):**
- ❌ **Commercial APIs fail**: $400/month, no rural dialects, privacy risks
- ❌ **Naive RAG hallucinates**: 18% false claims on admission cutoffs
- ✅ **Our solution**: $0.60/month, Chhattisgarhi support, zero hallucinations

**Visual:** Before/After comparison or cost bar chart

**Speaker Notes:**
- Story: "A rural student asks about SC category cutoffs. Commercial system fabricates a rank. Our system verifies or abstains."
- Ground the problem in high-stakes scenarios

---

### Slide 3: System Overview—What We Built (90 seconds)
**Title:** Architecture: CPU-GPU Decoupled Voice RAG Pipeline

**Visual:** Simplified architecture diagram (not the 20-step sequence!)
```
Microphone → VAD → ASR (CPU) → LangGraph Router
                                    ↓
                            Hybrid Retrieval
                         (Vector + BM25 + SQLite)
                                    ↓
                              LLM Generation → Grounding Review
                                    ↓
                         Text Display → TTS (CPU)
```

**Key Metrics Box:**
- 8GB GPU (consumer laptop)
- 98.9% retrieval recall
- 0 hallucinations in 316 tests
- $682× cheaper than cloud

**Speaker Notes:**
- Emphasize decoupling: "GPU only for LLM, everything else on CPU"
- "Hybrid retrieval" and "grounding review" are key innovations

---

### Slide 4: Innovation #1—Hybrid Retrieval (60 seconds)
**Title:** Solving the "Vector Search Fails on Numbers" Problem

**Content:**
```
Traditional Vector RAG:         Our Hybrid Approach:
Dense embeddings only           Dense (mE5) + Sparse (BM25) + Relational (SQLite)
10.8% recall on cutoffs  →      98.9% recall
Fuzzy matches confuse ranks     Exact SQL for numerical queries
```

**Visual:** Side-by-side comparison with recall chart

**Speaker Notes:**
- Example: "Traditional vector search retrieves 'CSE cutoff' when asked for 'ECE cutoff'"
- "We combine semantic search with exact database lookups"

---

### Slide 5: Innovation #2—Two-Pass Grounding (75 seconds)
**Title:** Zero Hallucinations Through Verification

**Visual:** Flowchart
```
Query → Retrieval → Generation → ⚠️ Grounding Review → ✓ Verified Answer
                                        ↓ (if fails)
                                  ❌ "I don't know" + Ticket
```

**Content:**
1. **Generation pass**: LLM drafts answer with citations
2. **Review pass**: Second LLM verifies every claim exists verbatim in sources
3. **Result**: 0/120 hallucinations vs 18% in traditional systems

**Speaker Notes:**
- "This doubles latency but eliminates risk in high-stakes counseling"
- "Better to say 'I don't know' than give wrong admission deadlines"

---

### Slide 6: Innovation #3—8GB VRAM Solution (60 seconds)
**Title:** Making It Work on Consumer Hardware

**Visual:** VRAM allocation diagram
```
Traditional (CRASH):           Our Decoupled Design:
[LLM 6.4GB + ASR 1.5GB + TTS 1.2GB = 9.1GB] ❌
                               [GPU: LLM only 6.3GB] ✓
                               [CPU: ASR, TTS, Embeddings]
```

**Key Points:**
- Naive stacking crashes on 8GB GPUs
- We isolate LLM to GPU, speech to CPU
- 100% uptime, deployable on $800 laptops

**Speaker Notes:**
- "This constraint drove architectural innovation, not limitation"

---

### Slide 7: Quantitative Results—Latency (60 seconds)
**Title:** Performance Breakdown

**Visual:** Gantt chart or stacked bar chart showing:
```
Cold Turn (18.68s):
├─ ASR: 1.85s
├─ Routing: 3.80s
├─ Retrieval: 0.05s
├─ Generation: 7.18s
├─ Grounding: 7.41s
└─ TTS: 1.65s (parallel)

Warm Cache (2.64s):
└─ Cached result + verification
```

**Text-First UX callout:** "Users see answer 4-15s before audio completes"

---

### Slide 8: Quantitative Results—Cost (45 seconds)
**Title:** Financial Comparison (10,000 queries/month)

**Visual:** Bar chart
```
Commercial APIs: $409.25
  ├─ Input tokens: $131
  ├─ Output tokens: $34
  ├─ Whisper API: $10
  └─ ElevenLabs TTS: $234

Our System: $0.60 (electricity only)
```

**Highlight:** **$682× cheaper**

---

### Slide 9: Vernacular Support—Chhattisgarhi (60 seconds)
**Title:** Supporting Rural Dialects Commercial APIs Ignore

**Content:**
- **Meta MMS-1B** with `hne` (Chhattisgarhi) adapter
- Custom Coqui VITS checkpoints trained on regional speech
- **Result:** 12% WER vs 45% on commercial ASR

**Visual:** Audio waveform + transcription example (if possible)

**Speaker Notes:**
- "First complete speech-to-speech system for Chhattisgarhi"
- "Deployment target: IIIT-NR helpdesk + rural admission counseling centers"

---

### Slide 10: Peer-Reviewed Foundations (60 seconds)
**Title:** Standing on Research Shoulders

**Content (timeline or citation boxes):**
- **FrugalGPT** (Stanford, NeurIPS 2023): LLM cascades, 98% cost reduction
- **RouteLLM** (UC Berkeley, 2024): Dynamic routing
- **Adaptive-RAG** (KAIST, NAACL 2024): Query complexity routing
- **VITS** (Kim et al., ICML 2021): End-to-end TTS
- **Laya/JEV** (Convaiinnovations, 2026): System 1 decision models

**Speaker Notes:**
- "Every architectural decision grounded in peer-reviewed research"
- "We extended these to edge constraints and zero-hallucination guarantees"

---

### Slide 11: Limitations & Future Work (60 seconds)
**Title:** What We're Working On Next

**Current Limitations:**
- ❌ Cold turn latency: 15-18s
- ❌ Single-speaker TTS
- ❌ No streaming audio

**Roadmap (with clear timelines):**
1. **Immediate:** Laya System 1 router (3.8s → 33ms routing)
2. **Near-term:** Sentence-chunked streaming TTS (TTFA <1.5s)
3. **Medium-term:** Speculative RAG drafting (36% speedup)
4. **Research:** Cross-lingual retrieval (Chhattisgarhi → English docs)

**Speaker Notes:**
- "Being honest about limitations strengthens credibility"
- "Clear roadmap shows this is production-ready with evolution path"

---

### Slide 12: Key Takeaways (45 seconds)
**Title:** What We Learned—Engineering AI Systems

**Content (3 bullets):**
1. **Constraints drive innovation**: 8GB VRAM forced CPU-GPU decoupling
2. **Correctness over speed**: Two-pass verification prevents hallucinations
3. **Edge-first architecture**: $682× cost reduction, privacy, offline support

**Visual:** Project metrics summary box
```
✓ 316 automated tests passing
✓ 98.9% retrieval recall
✓ 0 hallucinations in 120 cases
✓ $0.60/month operational cost
✓ Supports Chhattisgarhi dialect
```

---

### Slide 13: Demo / Screenshots (Optional, 30-60 seconds)
**Title:** System in Action

**Visual:** Screenshots or video clips showing:
- Web interface with audio input
- Text-first display of verified answer
- Audio playback controls
- Citation/source display

**Alternative:** Live demo if stable network available

---

### Slide 14: Thank You / Questions (Hold for Q&A)
**Title:** Questions?

**Contact & Links:**
- Repository: github.com/Punyansh26/minorprojectsem5
- Documentation: [dossier path]
- [Student contact info]

---

## Presentation Timing Guide

| Section | Slides | Time | Cumulative |
|---------|---------|------|------------|
| Problem & Motivation | 1-2 | 90s | 1:30 |
| System Overview | 3 | 90s | 3:00 |
| Technical Innovations | 4-6 | 195s | 6:15 |
| Results | 7-8 | 105s | 8:00 |
| Vernacular & Research | 9-10 | 120s | 10:00 |
| Limitations & Future | 11 | 60s | 11:00 |
| Takeaways | 12 | 45s | 11:45 |
| Demo (optional) | 13 | 60s | 12:45 |
| Buffer for Q&A setup | - | 2:15 | 15:00 |

---

## Presenter Tips

### Do's
✅ **Start with impact**: Open with cost savings and zero hallucinations  
✅ **Use concrete examples**: "Student asks SC cutoff, system verifies or abstains"  
✅ **Show, don't just tell**: Use diagrams, not text walls  
✅ **Acknowledge limitations**: Builds credibility  
✅ **Ground in research**: Cite papers to show depth  

### Don'ts
❌ **Don't dive into math first**: Save equations for Q&A  
❌ **Don't explain every component**: Focus on innovations  
❌ **Don't read slides**: Slides are visual aids, not scripts  
❌ **Don't ignore the "so what"**: Always tie tech to user benefit  
❌ **Don't oversell**: Be honest about current limitations  

---

## Backup Slides (For Q&A)

Prepare 5-8 additional slides covering:
1. Mathematical formulations (latency cascade, cost function)
2. Detailed VRAM allocation breakdown
3. Retrieval algorithm pseudocode
4. Full 20-step sequence diagram
5. Test coverage breakdown (316 tests by category)
6. Literature review deep dive
7. Laya/JEV integration architecture
8. Deployment architecture (Docker, systemd services)

These provide technical depth for expert questions without overwhelming the main presentation.
