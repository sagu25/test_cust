# Custom Agent — Explanation Script

Use this to explain the custom agent and its evaluation system to anyone —
technical or non-technical.

---

## The One-Liner

> "We built our own AI agent that answers employee policy questions,
> and then we built an automated system that continuously tests it,
> scores every answer across 6 metrics, and catches problems before any user does —
> all without writing a single hardcoded expected answer."

---

## What We Are NOT Doing

Before explaining what it is — be clear about what it is **not**.

> "We are not testing someone else's agent like Blueverse.
> We built our own agent from scratch — we control the documents it knows,
> the instructions it follows, and the model it uses.
> The evaluation system then acts as a permanent QA auditor
> that probes our agent around the clock."

---

## Part 1 — The Custom Agent

### What It Is

The custom agent is a RAG (Retrieval-Augmented Generation) agent.

When it receives a question, it does three things in sequence:

```
Step 1 — RETRIEVE
  Search 6 policy documents for the 4 most relevant paragraphs
  (using TF-IDF — a mathematical relevance scoring formula)

Step 2 — AUGMENT
  Pack those 4 paragraphs into a prompt alongside the question

Step 3 — GENERATE
  Send the prompt to the LLM (Groq / Azure)
  LLM reads the context and writes an answer
  Return: answer + which paragraphs were used + which documents they came from
```

### What It Knows — The 6 Documents

The agent's entire knowledge base is these 6 company policy documents:

---

**1. Annual Leave Policy**
Key facts the agent knows:
- Full-time employees get **15 days** paid leave per year
- Leave accrues at **1.25 days per month**
- Maximum **5 days** can be carried forward to next year
- Must apply **5 working days** in advance
- Emergency leave can be applied retrospectively within **2 working days**
- Public holidays falling during leave are **not counted**

---

**2. Remote Work Policy**
Key facts the agent knows:
- Eligible after **6 months** of service
- Contract and probationary employees are **not eligible**
- Maximum **3 days remote** per week; minimum **2 days in office**
- Core hours: **10:00 AM to 4:00 PM** regardless of location
- Company provides a laptop; VPN required; no data on personal devices

---

**3. Code of Conduct**
Key facts the agent knows:
- Gift limit from clients/vendors: **$50 maximum**
- Harassment, discrimination, and bullying: **zero tolerance**
- Violations can result in **disciplinary action up to termination**
- A **formal investigation** must be conducted before any disciplinary action

---

**4. Employee Benefits Policy**
Key facts the agent knows:
- Health insurance: company pays **80%**, employee pays **20%**
- Dependents covered: spouse and children **under 21**
- 401(k) match: up to **5% of salary**; eligible after **3 months**
- Annual learning budget: **$1,500** per employee
- Monthly wellness allowance: **$100**
- Primary caregiver parental leave: **16 weeks**
- Secondary caregiver parental leave: **4 weeks**

---

**5. Performance Review Policy**
Key facts the agent knows:
- Reviews twice a year: **June and December**
- New employees: **90-day probationary review**
- 5-point rating scale (1 = Unsatisfactory to 5 = Exceptional)
- Rating 5 → up to **15% salary increase**
- Rating 4 → up to **10% salary increase**
- Rating 3 → up to **5% salary increase**
- Below 3 → **no salary increase**, placed on PIP
- PIP duration: **60 days**
- Appeal window: **10 working days** after receiving the rating

---

**6. Expense Reimbursement Policy**
Key facts the agent knows:
- Breakfast limit: **$15**; Lunch: **$25**; Dinner: **$50**
- Alcohol: **not reimbursable**
- Economy class for flights **under 6 hours**
- Business class for flights **over 6 hours** — requires **VP approval**
- Hotel limit: **$200 per night** without manager approval
- Home office equipment: up to **$500 per year** for remote workers
- All claims must be submitted within **30 days**
- Receipts required for all expenses **over $25**
- Reimbursement paid within **15 business days**

---

### How a Question Gets Answered — Walk Through an Example

**Question asked:** *"How many days of annual leave do full-time employees get?"*

```
Step 1 — RETRIEVE
  TF-IDF searches all 6 documents
  Top 4 chunks returned:
    [Annual Leave Policy] "All full-time employees are entitled to 15 days..."
    [Annual Leave Policy] "Leave accrues at a rate of 1.25 days per month..."
    [Annual Leave Policy] "Unused leave can be carried forward up to 5 days..."
    [Annual Leave Policy] "Employees must apply at least 5 working days in advance..."

Step 2 — AUGMENT
  Prompt sent to LLM:
    System: "You are a knowledgeable assistant. Answer strictly using the context.
             If the answer is not in the context, say so clearly."
    Context: [the 4 chunks above]
    Question: "How many days of annual leave do full-time employees get?"

Step 3 — GENERATE
  LLM answer: "Full-time employees are entitled to 15 days of paid annual
               leave per calendar year, accruing at 1.25 days per month."

  Returned to evaluator:
    answer:            "Full-time employees are entitled to 15 days..."
    retrieved_context: [4 chunks with source + text + relevance score]
    sources:           ["Annual Leave Policy", "Annual Leave Policy", ...]
```

---

## Part 2 — How the Agent Gets Tested

### The Automated Test Loop

The orchestrator runs a pipeline every **2 minutes**:

```
Every 2 minutes:
  ┌─────────────────────────────────────────────┐
  │  1. TEST AGENT picks 3 questions            │
  │     (prioritises ones the agent scored      │
  │      lowest on in previous runs)            │
  │                                             │
  │  2. Fires all 3 at the custom agent         │
  │     simultaneously (parallel)               │
  │                                             │
  │  3. Custom agent answers all 3              │
  │                                             │
  │  4. EVALUATOR AGENT scores every answer     │
  │     across 6 metrics                        │
  │                                             │
  │  5. Results saved to database               │
  │                                             │
  │  6. Dashboard auto-updates                  │
  └─────────────────────────────────────────────┘
```

### Where Test Questions Come From

The system generates its own questions — no human writes them.

On the first run, the test agent:
1. Probes the custom agent with 3 discovery questions ("what do you know?")
2. Takes the agent's response about its knowledge
3. Sends it to the LLM: "Generate 15 test questions from this content"
4. LLM generates questions across 5 types:

| Type | Example |
|---|---|
| Factual | "What is the maximum carry-forward limit for unused annual leave?" |
| Procedural | "What steps must an employee follow to request remote work?" |
| Eligibility | "Can contract employees work from home?" |
| Conditional | "What happens if a public holiday falls during annual leave?" |
| Adversarial | "If an employee books a 7-hour flight, are they entitled to business class without approval?" |

These 15 questions are saved permanently and reused across cycles.
Repeating the same question across cycles is how consistency is tested.

### Smart Question Prioritisation

The test agent does not pick questions randomly. It weights questions by performance:

```
Question never asked before       → weight 4.0  (highest priority)
Question with avg score < 0.60    → weight 3.0  (poor performer, test often)
Question flagged as inconsistent  → weight 2.5  (contradictory answers)
Question with avg score 0.60–0.80 → weight 1.0  (normal priority)
Question with avg score > 0.80    → weight 0.5  (doing well, test less often)
Question in failed retry queue    → weight 3.5  (previously errored)
```

Result: the agent's weak spots get tested roughly **6× more often** than its strong areas.

---

## Part 3 — How Every Answer Is Scored

Every answer goes through 4 evaluation layers. Here is what each one checks and how.

---

### Layer 0 — Retrieval Quality (Was the right context pulled?)

Before scoring the answer, the system checks whether the **retrieval step worked**.

**Context Precision** — Of the 4 chunks retrieved, how many were actually relevant?
```
Example:
  Question: "What is the remote work eligibility requirement?"
  4 chunks retrieved from:
    → Remote Work Policy (eligibility section)     ✓ relevant
    → Annual Leave Policy (accrual section)        ✗ not relevant
    → Remote Work Policy (equipment section)       ✓ relevant
    → Code of Conduct (social media section)       ✗ not relevant
  
  Precision = 2 relevant / 4 total = 0.50
```

**Context Recall** — Did the retrieved chunks contain everything needed?
```
Example:
  Golden answer mentions: "6 months service + manager approval + not contract staff"
  Retrieved chunks contain:  6 months ✓,  manager approval ✗,  contract exclusion ✓
  
  Recall = 0.67  ← missed "manager approval" — retrieval gap
```

**Why this matters:** If the overall score is low, these two metrics tell you whether
the problem is the **retrieval** (wrong chunks) or the **generation** (LLM made something up).

---

### Layer 1 — Factual Anchor Check (Pure Code — No LLM)

Extracts every number, dollar amount, percentage, and time period from the answer
using regex, then checks each one against the source documents.

```
Example — Correct answer:
  Answer says:  "Employees get $100/month wellness allowance and 16 weeks parental leave"
  Source has:   $100 ✓   16 weeks ✓
  Score: 2 supported / 2 total = 1.00

Example — Wrong answer (hallucination):
  Answer says:  "Employees get $200/month wellness allowance"
  Source has:   $100 (not $200)
  Score: 0 supported / 1 total = 0.00  ← CAUGHT WITHOUT ANY LLM CALL

Numbers from the question itself are excluded:
  Question: "If a flight is 7 hours, what class is allowed?"
  Answer:   "For a 7-hour flight, business class is permitted"
  "7" came from the question → not penalised, even though source says "over 6 hours"
```

**This is the only metric in the system that is 100% deterministic.**
No AI is involved. An LLM cannot argue with "99 is not in the source document."

---

### Layer 2 — Golden ROUGE-L (Pure Math Against Ground Truth)

The system auto-generates a **golden reference answer** for each question by sending
the full document (not just retrieved chunks) to the LLM. This golden answer is
generated once and cached forever as the benchmark.

Every agent answer is then compared to the golden answer using ROUGE-L —
the Longest Common Subsequence algorithm:

```
Golden:  "Full-time employees receive 15 days of paid annual leave per calendar year."
Answer:  "Employees are entitled to 15 days of paid leave annually."

LCS match: "employees ... 15 days ... paid ... leave"
ROUGE-L = 0.61  ← reasonable match

Wrong answer:
  Answer: "Employees get 30 days of paid vacation"
  LCS match: "employees ... days ... paid"  (very short)
  ROUGE-L = 0.22  ← LOW — wrong answer detected mathematically
```

**Key point:** Even if the agent gives consistently wrong answers every run,
ROUGE-L against the golden answer will always be low. Consistency alone
does not protect a wrong answer from this metric.

---

### Layer 3 — LLM Judge (3 Dimensions, Run in Parallel)

Three separate LLM calls run simultaneously, each grounded by the golden answer:

**Faithfulness** — Did the agent make up anything?
```
Prompt to LLM:
  "Here is the retrieved context.
   Here is the verified golden answer (ground truth).
   Here is the agent's answer.
   Does the agent's answer contradict the golden answer on any specific fact?
   Score: 1.0 = fully faithful, 0.0 = contradicts ground truth"

Catches: vague answers, misleading claims, semantic wrong turns that
         don't involve specific numbers (which Layer 1 already catches)
```

**Relevancy** — Did the agent actually answer what was asked?
```
Catches: answers that are factually correct but off-topic
Example: Question about remote work → agent answers about leave policy
         Factual Anchor score: 1.00 (numbers are correct)
         Relevancy score:      0.10 (answered the wrong question)
```

**Completeness** — Did the agent leave out important details?
```
Catches: answers that are correct but incomplete
Example: Question about expense submission process
         Agent says: "Submit within 30 days"
         Golden says: "Submit within 30 days. Receipts required for expenses
                       over $25. Submit via the expense management system."
         Completeness: 0.40  ← missing 2 of 3 required details
```

---

### The Final Score Formula

```
Overall Score =
  0.25 × Factual Anchor Score    ← Layer 1 — pure code, most reliable
+ 0.25 × Golden ROUGE-L          ← Layer 2 — math vs ground truth
+ 0.25 × Faithfulness            ← Layer 3 — grounded LLM judge
+ 0.15 × Relevancy               ← Layer 3 — grounded LLM judge
+ 0.10 × Completeness            ← Layer 3 — grounded LLM judge
─────────────────────────────────
  1.00   Total weight

HARD RULE: If Factual Anchor Score < 0.30
           → cap Overall at 0.45 (RED) regardless of other scores

Score bands:
  0.80 – 1.00 → GREEN  — Agent is answering correctly
  0.60 – 0.79 → YELLOW — Issues detected, investigate
  0.00 – 0.59 → RED    — Serious problem, fix immediately
```

---

### What Our Actual Runs Showed

From the evaluation runs already completed in this system:

| Question (shortened) | Overall | Factual | ROUGE-L | Faithful | Notes |
|---|---|---|---|---|---|
| Annual leave request extension | 0.69 | 1.00 | 0.30 | 0.80 | Good factual, missed some details |
| Contract employee benefits eligibility | 0.71 | 1.00 | 0.33 | 0.80 | Solid performance |
| Remote work vs flexible work | 0.64 | 1.00 | 0.15 | 0.80 | Low ROUGE-L — answer phrased differently |
| Expense deadline submission | 0.72 | 1.00 | 0.41 | 0.80 | Strong across all metrics |
| Performance review appeals | 0.78 | 1.00 | 0.60 | 0.80 | Best ROUGE-L in the set |
| Code of conduct violation process | 0.69 | 1.00 | 0.29 | 0.80 | Low context recall |
| Probationary period benefits | 0.43 | 1.00 | 0.13 | 0.00 | Low faith — agent was uncertain |

**What these results tell us:**
- Factual Anchor Score is 1.00 across all runs — the agent is not hallucinating numbers
- ROUGE-L varies — the agent sometimes phrases things differently from the golden answer
- One question (probationary period) has a faithfulness of 0.00 — the agent gave a vague or hedged answer that the LLM judge flagged as unfaithful
- This gives us a clear action: either improve the system prompt or add more context to the probationary period document

---

## Part 4 — How This Differs From Testing Any Other Agent

### vs. Blueverse or Any External Agent

| | External Agent (Blueverse) | Our Custom Agent |
|---|---|---|
| You control the knowledge | No — fixed by vendor | Yes — edit `documents.py` |
| You control the behaviour | No — fixed prompt | Yes — edit `CUSTOM_AGENT_SYSTEM_PROMPT` |
| You can debug wrong answers | No — black box | Yes — see exactly which chunk was retrieved |
| You can switch the LLM | No | Yes — one `.env` line |
| You can add documents | Depends on vendor | Yes — add to `documents.py` and restart |
| You see retrieval scores | No | Yes — context precision + recall per run |

### vs. Manual Testing

| | Manual QA | Our System |
|---|---|---|
| Test questions | Someone writes them | Auto-generated from document content |
| Frequency | When someone has time | Every 2 minutes, forever |
| Consistency check | Never done | Every run, pairwise across all prior answers |
| Hallucination detection | Human reads and guesses | Regex code — deterministic, instant |
| Focus on weak spots | Random | Lowest-scoring questions tested 6× more often |

### vs. Standard LLM Eval Tools (RAGAS, TruLens, LangSmith)

| | Single-layer eval tools | Our System |
|---|---|---|
| Hallucination detection | LLM guess | Pure code regex — cannot be fooled |
| Ground truth | Manual labels required | Auto-generated golden answers |
| Retrieval quality | Not measured | Context precision + recall per run |
| Consistency over time | Not tracked | Pairwise consistency + drift score |
| Scheduling | Manual trigger | Autonomous, every 2 minutes |
| WHERE errors come from | Unknown | Retrieval vs generation separated |

---

## Part 5 — How to Run It

Two terminals. That is all.

**Terminal 1:**
```bash
cd eval_system
python orchestrator.py
```
Fires 3 questions at the custom agent, evaluates the answers, repeats every 2 minutes.

**Terminal 2:**
```bash
cd eval_system
streamlit run dashboard.py
```
Opens at http://localhost:8501 — live scores, trend charts, consistency alerts.

---

## Common Questions

**Q: Why build a custom agent instead of just testing Blueverse?**
> "Because we own the full stack. When the agent gives a wrong answer, we can
> see exactly which document chunk was retrieved, what prompt was used, and why
> the LLM answered that way. With an external agent, you only see the output."

**Q: What happens when we want to change what the agent knows?**
> "Edit `documents.py` with the new content, restart the orchestrator.
> The TF-IDF index rebuilds automatically. The system will detect that
> it's answering questions differently and flag any inconsistencies."

**Q: What happens if the agent gives wrong answers consistently?**
> "Two things: the Factual Anchor Score will be low (if numbers are wrong),
> and the Golden ROUGE-L will be low (if the answer drifts from the reference).
> The hard cap rule means a factually wrong agent cannot score above 0.45
> no matter what the LLM judge says."

**Q: Can we point this at a different set of documents — HR policies, legal docs, etc.?**
> "Yes. Replace the content in `documents.py` with any documents you want.
> Clear the database so old questions are regenerated for the new content.
> The system self-configures — it reads the new documents and generates
> a fresh set of 15 grounded test questions automatically."

**Q: What would make this production-ready?**
> "Three things: swap SQLite for PostgreSQL, add Slack alerts when scores drop
> below 0.75, and hook it into the CI/CD pipeline so it runs automatically
> on every deployment. The evaluation logic itself is already production-quality."
