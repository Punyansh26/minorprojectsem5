# Visual Assets Guide for Presentation Slides

**Purpose:** Recommendations for creating clear, presentation-ready diagrams  
**Tools:** Use draw.io, Figma, PowerPoint SmartArt, or Mermaid Live Editor

---

## 🎨 Design Principles

### For All Visuals
- **High contrast:** Dark text on light background (or vice versa)
- **Large fonts:** Minimum 18pt for labels, 24pt for titles
- **Color palette:** Use 3-4 colors max (consistency across slides)
- **Whitespace:** Don't cram—leave breathing room
- **Accessibility:** Avoid red-green combinations (colorblind-friendly)

### Recommended Color Palette
```
Primary:   #2563eb (Blue - for main components)
Success:   #16a34a (Green - for improvements/benefits)
Warning:   #ea580c (Orange - for problems/bottlenecks)
Neutral:   #64748b (Gray - for supporting elements)
Accent:    #7c3aed (Purple - for highlights)
```

---

## 📊 Diagram 1: Simplified System Architecture (Slide 3)

**Purpose:** High-level overview showing CPU-GPU decoupling  
**Complexity:** 7-9 boxes maximum  
**Timing:** Should be explainable in 90 seconds

### Layout Structure
```
┌─────────────────────────────────────────────────────────┐
│                   User Interface                        │
│              (Microphone → Speaker)                     │
└────────────────┬───────────────────────┬────────────────┘
                 ▼                       ▼
         ┌───────────────┐       ┌──────────────┐
         │   CPU LAYER   │       │  GPU LAYER   │
         │   (Speech)    │       │    (LLM)     │
         └───────────────┘       └──────────────┘
                 │                       │
         ┌───────┴───────┐       ┌──────┴───────┐
         │ VAD + ASR     │       │  Qwen 9B     │
         │ (Whisper/MMS) │       │ Q4_K_M Quant │
         └───────┬───────┘       └──────┬───────┘
                 │                       │
         ┌───────┴───────┐       ┌──────┴───────┐
         │  TTS + Voice  │       │ Hybrid Store │
         │  (VITS/Edge)  │       │ E5+BM25+SQL  │
         └───────────────┘       └──────────────┘
                                         │
                                 ┌───────┴───────┐
                                 │  Grounding    │
                                 │  Verification │
                                 └───────────────┘
```

### Visual Elements
- **CPU box:** Light blue background, 32GB RAM label
- **GPU box:** Orange background, 8GB VRAM label, "Exclusive" badge
- **Arrows:** Solid for data flow, dashed for validation
- **Annotations:** Small badges showing timing (e.g., "1.85s", "7.18s")

### Key Callouts (Text Boxes)
1. "Speech on CPU prevents VRAM crashes"
2. "GPU dedicated to LLM for max throughput"
3. "Two-pass safety: Generation → Verification"

---

## 📊 Diagram 2: Hybrid Retrieval Comparison (Slide 4)

**Purpose:** Show why hybrid approach beats naive vector search  
**Complexity:** Side-by-side comparison  
**Timing:** Should be explainable in 60 seconds

### Layout Structure
```
┌─────────────────────────────────────────────────────────────┐
│         Traditional Vector RAG    │    Our Hybrid RAG       │
├─────────────────────────────────────────────────────────────┤
│                                   │                         │
│  Query: "CSE SC cutoff 2026"      │  Query: "CSE SC cutoff" │
│           ↓                       │           ↓             │
│    [Dense mE5 Only]               │    [3-Way Fusion]       │
│           ↓                       │      ↙   ↓   ↘         │
│    Cosine similarity              │  Dense  BM25  SQL       │
│           ↓                       │      ↘   ↓   ↙         │
│  ❌ Returns ECE cutoff            │    [RRF Merge]          │
│  ❌ Returns 2025 data             │           ↓             │
│  ❌ Fuzzy rank match              │  ✅ Exact program       │
│                                   │  ✅ Exact year          │
│  Recall: 10.75% ⚠️                │  Recall: 98.92% ✅      │
└─────────────────────────────────────────────────────────────┘
```

### Visual Elements
- **Left side:** Red/orange tones (problems)
- **Right side:** Green/blue tones (solutions)
- **Icons:** ❌ for failures, ✅ for successes
- **Bottom comparison:** Large bold numbers with color coding

### Key Annotations
- "Semantic similarity fails on program codes"
- "BM25 catches keyword mismatches"
- "SQL for exact numerical queries"

---

## 📊 Diagram 3: Two-Pass Grounding Flow (Slide 5)

**Purpose:** Show how verification prevents hallucinations  
**Complexity:** Sequential flowchart with decision point  
**Timing:** Should be explainable in 75 seconds

### Layout Structure
```
┌──────────────┐
│ User Query   │
└──────┬───────┘
       ▼
┌──────────────────────┐
│  Hybrid Retrieval    │
│ (Top-6 Chunks)       │
└──────┬───────────────┘
       ▼
┌──────────────────────┐
│ PASS 1: Generation   │
│ LLM drafts answer    │
│ with citations       │
└──────┬───────────────┘
       ▼
┌──────────────────────┐
│ PASS 2: Review       │
│ Verify quotes exist  │
│ in source chunks     │
└──────┬───────────────┘
       ▼
    ◇─────────◇  Decision Point
    │         │
    ▼         ▼
┌───────┐  ┌──────────────┐
│Verified│  │ Unverified   │
│Answer ✅│  │ Abstain ❌   │
└───┬───┘  └──────┬───────┘
    │             │
    ▼             ▼
Display      "I don't know"
+ Cache      + Draft Ticket
```

### Visual Elements
- **Pass 1 box:** Blue, labeled "Generation (7.18s)"
- **Pass 2 box:** Purple, labeled "Verification (7.41s)"
- **Decision diamond:** Yellow, bold text "Quote Found?"
- **Verified path:** Green arrow, thick line
- **Rejected path:** Red arrow, dashed line

### Key Statistics Box
```
┌────────────────────────────────┐
│ Results (316 Tests):           │
│ ✅ Verified: 88 cases          │
│ ❌ Abstained: 28 cases         │
│ 🚫 Hallucinations: 0 cases     │
└────────────────────────────────┘
```

---

## 📊 Chart 1: Cost Comparison Bar Chart (Slide 8)

**Purpose:** Dramatic cost difference visualization  
**Type:** Horizontal or vertical bar chart  
**Timing:** Should be understandable in 45 seconds

### Data to Visualize
```
Commercial Cloud APIs: $409.25
├─ GPT-4o tokens:  $165.25
├─ Whisper API:     $10.00
└─ ElevenLabs TTS: $234.00

Our Local System:   $0.60
└─ Electricity only
```

### Visual Design
- **Commercial bar:** Red/orange, very tall
- **Our system bar:** Green, barely visible (emphasizes difference)
- **Label placement:** Dollar amounts at top of each bar
- **Savings callout:** Large "682× CHEAPER" text with arrow

### Alternative: Infographic Style
```
Commercial APIs          Our System
    💰💰💰                   💰
    💰💰💰                   
    💰💰💰              vs   $0.60/month
    $409/mo
    
    [Arrow pointing down]
    "Save $408.65/month"
    "ROI: Break-even after first month"
```

---

## 📊 Chart 2: Retrieval Recall Comparison (Slide 4)

**Purpose:** Show dramatic improvement in retrieval accuracy  
**Type:** Side-by-side bar chart  
**Timing:** Should be understandable in 30 seconds

### Data to Visualize
```
                 Traditional    Our Hybrid
                 Vector RAG     System
                 ─────────      ──────────
Recall@6         10.75%         98.92%
                 [Small bar]    [Nearly full bar]
```

### Visual Design
- **Y-axis:** 0% to 100%
- **Bars:** Traditional (red, 10.75%), Ours (green, 98.92%)
- **Annotation:** "+88.17 pp improvement" with arrow
- **Context note:** "On 117-case benchmark (English, Hindi, Hinglish)"

---

## 📊 Chart 3: Latency Gantt Chart (Slide 7)

**Purpose:** Show stage-by-stage latency breakdown  
**Type:** Stacked bar chart or Gantt chart  
**Timing:** Should be explainable in 60 seconds

### Data to Visualize (Cold Turn)
```
Stage               Duration    Cumulative
─────────────────────────────────────────
ASR                 1.85s       1.85s
Routing             3.80s       5.65s
Retrieval           0.05s       5.70s
Generation          7.18s      12.88s
Grounding Review    7.41s      20.29s
TTS (parallel)      1.65s       —
─────────────────────────────────────────
Perceived (text)   18.68s
Total (with audio) 21.20s
```

### Visual Design
- **Horizontal bars:** One per stage, color-coded
- **ASR:** Light blue
- **Routing:** Orange (bottleneck highlight)
- **Retrieval:** Green (fast)
- **Generation:** Purple
- **Review:** Dark purple
- **TTS:** Gray (parallel, dashed)
- **Vertical line:** At 18.68s labeled "Text Displayed"
- **Callout:** "User reads 4-15s before hearing audio"

### Comparison: Warm Cache
```
Warm Cache Turn:
─────────────────
Cache Hit + Review: 2.64s [Green bar, very short]
"86% faster on repeated queries"
```

---

## 📊 Diagram 4: VRAM Allocation Comparison (Slide 6)

**Purpose:** Show why naive approach crashes and ours doesn't  
**Type:** Memory allocation diagram  
**Timing:** Should be explainable in 60 seconds

### Layout Structure
```
┌─────────────────────────────────────────────────┐
│     Naive Approach (❌ CRASHES)                 │
├─────────────────────────────────────────────────┤
│  0GB                                      8GB   │
│  ├────────┬──┬─┬─────────────────────────┤▲    │
│  │  LLM   │A│T│    (Overflow)           ││    │
│  │ 6.4GB  │S│T│                         ││    │
│  │        │R│S│                         │OOM  │
│  │        │1│1│                         ││    │
│  │        │.│.│                         ││    │
│  │        │5│2│                         │▼    │
│  └────────┴──┴─┴─────────────────────────┘     │
│   Total: 9.1GB > 8GB Available ⚠️              │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│     Our Decoupled Approach (✅ STABLE)          │
├─────────────────────────────────────────────────┤
│         GPU VRAM (8GB)                          │
│  ├──────────────────────────────┬────┐          │
│  │      LLM Qwen 9B             │KV  │          │
│  │      6.3GB + Display         │0.8 │          │
│  └──────────────────────────────┴────┘          │
│   Used: 7.95GB / 8GB (Safe margin) ✅           │
│                                                  │
│         CPU RAM (32GB)                          │
│  ├──┬───┬────┬─────────────────────┐            │
│  │W │MMS│VIT │      Free           │            │
│  │H │   │S   │      Space          │            │
│  │I │1.9│    │                     │            │
│  │S │GB │1.2 │                     │            │
│  │P │   │GB  │                     │            │
│  │1.2│   │    │                     │            │
│  └──┴───┴────┴─────────────────────┘            │
│   Used: 3.9GB / 32GB (Plenty of room) ✅        │
└─────────────────────────────────────────────────┘
```

### Visual Elements
- **Naive diagram:** Red tones, overflow visualization
- **Our diagram:** Green tones, clear separation
- **GPU section:** Darker background
- **CPU section:** Lighter background
- **Annotations:** "Exclusive GPU access" badge on LLM

---

## 🎯 Icon & Badge Recommendations

### Status Badges
- ✅ Success: Green circle with checkmark
- ❌ Failure: Red circle with X
- ⚠️ Warning: Orange triangle with exclamation
- 💡 Insight: Yellow lightbulb
- 🚀 Innovation: Rocket icon
- 💰 Cost: Dollar sign or money bag
- ⚡ Speed: Lightning bolt
- 🔒 Privacy: Lock icon

### Component Icons
- 🎤 Microphone: Input/ASR
- 🔊 Speaker: Output/TTS
- 🧠 Brain: LLM/Reasoning
- 📚 Books: Knowledge base
- ✓ Checkmark: Verification
- 🔄 Circular arrows: Iteration
- 📊 Chart: Metrics/Results

---

## 🖼️ Screenshot Recommendations

### If Including System Screenshots (Slide 13)

1. **Web Interface:**
   - Show audio recording interface
   - Display text-first answer rendering
   - Highlight citation/source display

2. **Terminal/Console:**
   - Show latency breakdown logs
   - Display grounding verification output
   - Capture cache hit indicators

3. **Metrics Dashboard:**
   - Show test suite results (316 passing)
   - Display recall percentages
   - Show cost tracking

### Screenshot Guidelines
- **Resolution:** Minimum 1920x1080
- **Annotations:** Add arrows/highlights for key elements
- **Cropping:** Remove irrelevant UI elements
- **Contrast:** Ensure text is readable when projected

---

## 🎨 Slide Background Recommendations

### Color Scheme
- **Title slides:** Dark background (navy/dark gray) + white text
- **Content slides:** White/light gray background + dark text
- **Comparison slides:** Split background (light left, dark right)
- **Highlight slides:** Accent color background for key stats

### Avoid
- ❌ Gradients (look dated, reduce readability)
- ❌ Busy patterns (distract from content)
- ❌ Low contrast combinations (red on green, yellow on white)
- ❌ Too many colors (stick to 3-4 palette colors)

---

## 🔧 Tools for Creating Visuals

### Online (Free)
1. **Mermaid Live Editor** (mermaid.live)
   - Great for flowcharts, sequence diagrams
   - Export as SVG/PNG
   - Easy syntax

2. **draw.io / diagrams.net**
   - Comprehensive diagramming tool
   - Templates available
   - Exports to multiple formats

3. **Canva** (canva.com)
   - Infographic templates
   - Easy icon library
   - Presentation templates

### Desktop
1. **Microsoft PowerPoint**
   - SmartArt graphics
   - Built-in charts
   - Direct integration with slides

2. **Figma** (figma.com)
   - Professional design tool
   - Collaboration features
   - Component libraries

3. **Inkscape** (inkscape.org)
   - Free vector graphics
   - SVG native format
   - Full control over design

---

## ✅ Visual Assets Checklist

### Before Creating
- [ ] Identify key message for each visual
- [ ] Choose appropriate diagram type
- [ ] Gather exact data/numbers
- [ ] Select consistent color palette

### While Creating
- [ ] Use minimum 18pt font for labels
- [ ] Include legend/key if needed
- [ ] Add annotations for key insights
- [ ] Test visibility at distance (projector simulation)
- [ ] Export at high resolution (minimum 1080p)

### After Creating
- [ ] Review with peer (is it understandable?)
- [ ] Test on actual presentation screen
- [ ] Have backup text explanation ready
- [ ] Save source files for future edits

---

## 💡 Pro Tips

### For Flowcharts
- **Left-to-right** is easier than top-to-bottom for wide screens
- **Limit to 3-4 levels** of hierarchy
- **Use consistent shapes** (rectangles=processes, diamonds=decisions)

### For Comparisons
- **Side-by-side** works better than overlaid
- **Use color** to emphasize difference (red=bad, green=good)
- **Add percentage** improvement labels

### For Data Charts
- **Start Y-axis at zero** (don't truncate to exaggerate)
- **Label every data point** for clarity
- **Use horizontal bar charts** if labels are long

### For Architecture Diagrams
- **Top = user-facing**, **bottom = backend**
- **Group related components** with boxes
- **Use dashed lines** for optional/parallel paths

---

## 🎯 Final Recommendations

### Must-Have Visuals (Priority Order)
1. **Simplified architecture diagram** (Slide 3) — Critical for understanding
2. **Cost comparison chart** (Slide 8) — Most dramatic result
3. **Hybrid retrieval comparison** (Slide 4) — Key innovation
4. **Two-pass flow** (Slide 5) — Safety differentiator
5. **VRAM allocation** (Slide 6) — Hardware constraint solution

### Nice-to-Have Visuals
- Latency Gantt chart (if time permits)
- Recall percentage chart (can use table instead)
- Demo screenshots (if high quality available)
- Research timeline (optional)

### Can Skip if Rushed
- Detailed sequence diagrams (use in backup)
- Complex mathematical formulas (verbal explanation)
- Code snippets (not presentation-appropriate)

---

**Remember:** A good diagram is instantly understandable. If it takes >30 seconds to explain, simplify it.

**Golden rule:** Each visual should support ONE key message. Don't try to show everything in one diagram.

Good luck creating your visuals! 🎨
