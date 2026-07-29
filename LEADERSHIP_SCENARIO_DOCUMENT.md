# AI Agent Quality Testing — Leadership Briefing

**Audience:** Leadership, product owners, HR stakeholders  
**Purpose:** Explain what the automated evaluation system does, show three real scenarios from live data, and propose extending it to test the Blueverse agent

---

## What Is This System?

We built an automated testing framework that continuously interrogates an AI agent and scores the quality of its answers — without any human reviewer reading the responses.

Every 2 minutes, the system:
1. Picks a test question from a question bank (automatically generated from policy documents)
2. Fires the question at the AI agent and captures the answer
3. Scores the answer across 5 dimensions (factual accuracy, faithfulness, relevancy, completeness, consistency)
4. Logs everything to a database and displays live results on a dashboard

**What makes this different from simply asking the AI a question yourself:**  
Humans read the answer and think "that sounds right." This system checks whether the specific numbers, dates, and policy facts stated in the answer actually appear in the source document — using both code and an independent AI judge. It does not just validate tone; it validates substance.

**Current deployment:** Custom AI agent loaded with 6 employee policy documents  
**Total test runs (at time of writing):** 659+ runs across 15 test questions

---

## The Scoring System at a Glance

| Layer | Method | What It Checks |
|---|---|---|
| Layer 1 — Factual Anchor | Pure code (no AI) | Every number and dollar amount in the answer exists in the document |
| Layer 2 — ROUGE-L vs Golden | Mathematical formula | How closely does the answer match the ideal reference answer? |
| Layer 3 — LLM Judge | Independent AI evaluator | Faithfulness (no hallucination), Relevancy (answered the right question), Completeness (nothing important missing) |
| Layer 4 — Consistency | Cross-run comparison | Does the agent give the same answer every time, or does it contradict itself? |

**Overall Score = 0 to 1.** Above 0.80 is Good. Below 0.60 is a serious problem requiring investigation.

---

## Three Real Scenarios From 659 Live Test Runs

---

### Scenario 1: The Agent Gets It Exactly Right (Score: 1.00)

**Question asked:** *"What is the minimum number of days of annual leave that employees are entitled to?"*

**What happened:** The agent answered that the leave policy does not specify a minimum — it specifies 15 days of entitlement as a fixed number, not a minimum.

**Score breakdown:**
- Factual Anchor: 1.00 — all numbers verified in source
- ROUGE-L vs Golden: 1.00 — matched the reference answer
- Faithfulness: 1.00 — nothing invented
- Overall: **1.00**

**Why this matters to leadership:**  
This is the success case. The agent correctly understood a nuance — the question asked for a "minimum" but the policy only specifies a fixed entitlement. The AI did not guess or fabricate a floor. It accurately reflected the document.

**What the system confirmed automatically:** That the agent handles subtle phrasing without hallucinating a policy that does not exist.

---

### Scenario 2: The System Catches a Policy Contradiction (Score: 0.37)

**Question asked:** *"Can employees on probation take annual leave, and if so, how much?"*

**What happened:** The agent gave an answer about probationary leave. On different test runs, it gave inconsistent answers — sometimes saying employees accumulate leave during probation, sometimes saying they cannot access it. The system detected this contradiction automatically.

**Score breakdown:**
- Factual Anchor: 0.50 — some facts verified, some not confirmed in source
- ROUGE-L vs Golden: 0.20 — answer diverges significantly from the reference
- Faithfulness: 0.40 — contradiction detected vs golden answer
- Consistency: FLAGGED — answers contradict each other across runs
- Overall: **0.37 (our lowest-scoring question)**

**The automated alert the system raised:**
> "Contradiction detected between Run #14 and Run #41: Run 14 states employees begin accumulating leave during probation; Run 41 states leave may not be accessed during the probationary period. Both cannot be correct."

**Why this matters to leadership:**  
No human reviewer caught this — the system did. If this agent were deployed to employees, it would give different answers to the same question on different days. An employee asking "can I take leave during probation?" might get a Yes on Monday and a No on Friday.

**Business risk without this system:** Policy inconsistency that erodes trust in AI tooling and may result in incorrect leave decisions.

---

### Scenario 3: The System Finds a Document Gap (Score: 0.49)

**Question asked:** *"What must hourly employees submit to payroll for time tracking?"*

**What happened:** The agent was asked about payroll. The 6 policy documents loaded into the system do not include a payroll policy. The agent either said "I don't know" (correct behaviour) or fabricated a plausible-sounding answer about timesheets (hallucination).

**Score breakdown:**
- Factual Anchor: 0.00 — the specific claims made by the agent were not found in any document
- ROUGE-L vs Golden: 0.10 — golden answer says "document does not cover this topic"
- Relevancy: 0.00 — the agent answered a question it shouldn't have answered with made-up content
- Overall: **0.49**

**A second example of the same pattern:**
> Question: *"What rewards are referrers eligible for when their referral is hired?"*  
> No referral rewards policy exists in the documents.  
> Agent hallucinated a specific rewards structure.  
> Score: **0.34**

**Why this matters to leadership:**  
This is not a failure of the AI — it is a failure of **documentation coverage**. The evaluation system surfaced two entire policy areas (payroll and employee referrals) that employees might realistically ask an AI assistant about, but which are not documented. The system did not just score the agent; it gave us a **document gap report**.

The actionable outcome from this scenario is not to fix the agent — it is to either add the missing policy documents or configure the agent to redirect those question categories.

---

## Summary: What Did 659 Runs Tell Us?

| Finding | Implication |
|---|---|
| 2 contradictions automatically detected | Policy consistency issues caught without human reviewers |
| 2 document gaps surfaced (payroll, referrals) | Documentation coverage audit delivered as a by-product |
| Score range: 0.37 to 1.00 | The system distinguishes strong vs weak answers; not all questions pass |
| 15 questions actively monitored | Each question runs independently; a problem in one doesn't mask others |
| Fully automated — 24/7 | No human time spent reviewing AI answers |

**The four numbers to remember:**  
**659 runs. 2 contradictions caught. 0.37 worst score. 1.00 best score.**

---

## What "We Show the Ones That Didn't Work" Actually Means

Every AI demo shows you the answer that worked. This system shows you the answers that didn't — and tells you exactly what went wrong and why. That is the fundamental value: not confidence that the AI is good, but **evidence** of where it fails.

---

## Proposal: Extend This Framework to Test the Blueverse Agent

The testing framework was intentionally designed to be agent-agnostic. The agent under test is a configuration setting, not a hard-coded dependency.

**Current configuration (custom agent):**
```
RAG_APP_URL=custom
CUSTOM_AGENT_MODE=local
```

**To point the same framework at the Blueverse agent — one line change:**
```
RAG_APP_URL=https://blueverse-agent-endpoint.com/query
```

No code changes. The entire evaluation pipeline — question generation, 5-layer scoring, consistency tracking, dashboard — runs identically. The only difference is which agent receives the questions.

### What we would learn about the Blueverse agent in 48 hours

| Evaluation | What it tells us |
|---|---|
| Factual Anchor Score | Does Blueverse hallucinate specific numbers or dates? |
| ROUGE-L vs Golden | Does Blueverse answer match what the full document actually says? |
| Faithfulness | Does Blueverse invent facts not in the retrieved context? |
| Consistency | Does Blueverse give the same answer each time, or contradict itself? |
| Contradiction detection | Does Blueverse produce answers that conflict with each other across sessions? |

### The business case

- No manual question writing required — questions auto-generate from Blueverse's documents
- No human reviewers needed — evaluation runs 24/7 automatically
- Results are comparable — same scoring formula, so Blueverse scores can be directly compared to any other agent
- Documentation gaps surface automatically — same as what happened with the payroll/referral gap above

### What we need to start

1. The Blueverse API endpoint URL
2. The authentication method (API key, Bearer token, or SSO)
3. The format of the request body (which field name contains the question)
4. The format of the response (which field contains the answer)

That is all. The `.env.example` file already has all the variables to fill in:

```env
RAG_APP_URL=https://your-blueverse-endpoint.com/query
BLUEVERSE_API_KEY=your_key_here
CUSTOM_AGENT_REQUEST_FIELD=question
CUSTOM_AGENT_RESPONSE_FIELD=answer
```

Estimated time to first results: **under 2 hours from access to first dashboard.**

---

## Closing

This system treats AI quality the same way we treat software quality — with automated, continuous, measurable testing. The scenarios above demonstrate three things it can do that manual review cannot:

1. **Catch contradictions across time** — no reviewer reads every answer on every run
2. **Verify specific facts with code** — not "does this sound right" but "is this number in the document"
3. **Surface documentation gaps** — questions the AI cannot answer reveal policy areas not yet documented

The extension to Blueverse is not a new project. It is a configuration change.

---

*Document based on 659 live evaluation runs from the custom agent test deployment.*  
*Framework: eval_system — custom agent, TF-IDF retrieval, Groq LLM, SQLite, Streamlit dashboard.*
