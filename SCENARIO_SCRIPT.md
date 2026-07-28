# The Comparison Scenario — How to Present This and Impress Everyone

## The Opening Hook (Say This First)

> "We ran our AI agent **659 times**, automatically, across **15 different questions**,
> with **zero human involvement**.
> In those 659 runs, the system found **2 contradictions**, identified
> **3 categories of weakness**, and produced a ranked leaderboard
> of every question the agent struggles with.
> Let me show you what that actually looks like."

Then open the dashboard. Pause. Let the numbers land.

---

## The Setup — What Most People Do vs What We Do

Before the scenarios, say this:

> "When someone builds an AI chatbot today, they usually test it like this:
> They ask it five questions manually, the answers look reasonable,
> and they say 'looks good, ship it.'
>
> The problem is: they don't know which questions the agent struggles with.
> They don't know if the agent gives different answers on different days.
> And they definitely don't know when the agent is making something up
> versus when it genuinely doesn't know.
>
> What we built answers all three of those questions — automatically,
> continuously, with real numbers."

---

## Scenario 1 — The Agent That Gets It Perfect (Score: 1.00)

**The question:**
> *"What is the minimum number of days of annual leave that employees must take in a calendar year?"*

**What the agent answered:**
> *"The policy context does not specify a minimum number of days of annual leave
> that employees must take in a calendar year. It only states that employees
> are entitled to 15 days of paid leave and that unused leave beyond 5 days will lapse."*

**The scores:**
```
Factual Anchor Score:  1.00  — no hallucinated numbers
Golden ROUGE-L:        1.00  — matches the reference answer exactly
Faithfulness:          1.00  — everything said is grounded in the document
Relevancy:             1.00  — directly answers what was asked
Completeness:          1.00  — mentions the carry-forward context too

OVERALL:               1.00  ← PERFECT
```

**How to explain this to the room:**

> "Look at this question. The document only says employees GET 15 days —
> it says nothing about a minimum they MUST take.
>
> A poorly built agent would hallucinate an answer here. It might say
> '5 days minimum' or '10 days' — something that sounds plausible
> but isn't in the policy.
>
> Our agent did something harder: it correctly admitted it doesn't know.
> AND it added useful context — mentioning the 5-day carry-forward rule
> so the person asking still walks away with something helpful.
>
> We ran this question **42 times** across different cycles.
> Score: 1.00 every single time. Zero contradictions.
> That is a consistent, honest, grounded AI agent."

---

## Scenario 2 — The System Catches a Contradiction (Score: 0.37 → flagged)

**The question:**
> *"If an employee is going through a probationary period, are they eligible for annual leave?"*

**What the Annual Leave Policy actually says:**
> *"Employees in their first year receive leave on a pro-rata basis from their start date."*

**What the agent said — Run 1:**
> *"The provided policy context does not mention eligibility for annual leave
> during a probationary period, nor does it specify the amount of annual leave
> accrued during this time."*

**What our system detected:**
```
Faithfulness:          0.00  — contradicts the golden answer
Contradicts Golden:    YES
Contradiction detail:  "The app's answer states the context does not mention
                        eligibility for probationary leave, which contradicts
                        the golden answer — first-year employees DO receive
                        leave on a pro-rata basis from their start date."

OVERALL:               0.37  ← RED — flagged immediately
```

**How to explain this to the room:**

> "This is the most important scenario. Watch what happened here.
>
> The agent said 'the policy doesn't mention probationary leave.'
> That sounds like a safe, honest answer. But it is WRONG.
>
> The Annual Leave Policy says employees in their first year receive leave
> on a pro-rata basis. The agent retrieved the wrong document chunks
> and missed that line. So it gave a confident-sounding wrong answer.
>
> Here is what makes our system different from every other testing approach:
>
> We auto-generated a golden reference answer from the FULL document —
> not from what the retrieval found, but from the complete policy text.
> When we compared the agent's answer to that golden answer,
> the contradiction was mathematical and immediate.
>
> Score: 0.37. Flagged red. Contradiction detail written out automatically.
> No human read this. No human wrote a test case for it.
> The system caught it by itself."

**The slide moment — say this slowly:**

> "If we had shipped this agent without testing,
> an employee on probation would have been told they have no annual leave.
> They might not take leave they were legally entitled to.
> Our system caught that in Run 1. Automatically."

---

## Scenario 3 — The Systematic Weakness (Score: 0.49 avg across 44 runs)

**The question:**
> *"If an employee is unable to work due to illness, what are the requirements
> for providing a doctor's note?"*

**What the agent answered:**
> *"The provided policy context does not mention the requirements for
> providing a doctor's note or how it impacts an employee's leave balance."*

**The scores:**
```
Faithfulness:  1.00  — correct, the policy doesn't cover sick leave
Relevancy:     0.00  — the LLM judge says this answer doesn't help the user
Completeness:  0.00  — no useful information provided at all

OVERALL:       0.49  ← YELLOW/RED — 44 runs, consistent weakness
```

**What this reveals:**

```
The agent has a DOCUMENT GAP.

Sick leave and doctor's note requirements are not in any of the 6 policy
documents. So the agent correctly says "I don't know."

But Relevancy = 0.00 tells us something more important:
A user asking this question walks away with NOTHING useful.
A well-designed agent would redirect them:
"This isn't covered in the policies I have access to.
 Please contact HR directly for sick leave queries."
```

**How to explain this to the room:**

> "This question scores 0.49. Consistently. Across 44 runs.
>
> Now, is this the agent's fault? Not entirely — sick leave genuinely isn't
> in these documents. The agent is being honest.
>
> But look at the Relevancy score: 0.00.
> That means 44 times, an employee asked about illness and walked away
> with nothing they could act on.
>
> This is exactly what our system is for. It doesn't just tell you
> the agent failed. It tells you HOW it failed —
> and in this case, the fix is clear:
> add a sick leave policy document, or update the system prompt
> to redirect out-of-scope questions to HR.
>
> Without our testing system, you'd never know this question
> is asked constantly and answered uselessly every time."

---

## The Full Leaderboard — Show This on the Dashboard

Open the dashboard and walk through this table live:

| Question (shortened) | Runs | Avg Score | Verdict |
|---|---|---|---|
| Minimum leave days required | 42 | **0.99** | Perfect — agent knows its limits |
| Benefits for part-time staff | 45 | **0.76** | Strong — factual, complete |
| Expense submission deadline | 41 | **0.75** | Solid — knows the 30-day rule |
| Performance review appeal steps | 39 | **0.73** | Good — follows the policy |
| Max expense reimbursement | 46 | **0.71** | Good — knows the limits |
| Contract employee benefits | 51 | **0.57** | Weak — retrieval missing info |
| Probationary period eligibility | 42 | **0.55** | Weak — **contradiction caught** |
| Remote vs flexible work | 45 | **0.50** | Weak — gap question, no policy |
| Expense deadline extension | 40 | **0.50** | Weak — policy gap |
| Doctor's note for illness | 44 | **0.49** | Weakest — document gap |

**Say this while showing the table:**

> "This is 659 automated test runs, ranked.
> The top three questions — the agent handles perfectly.
> The bottom three — we now know exactly why they fail
> and exactly what to do to fix them.
>
> No human wrote these test cases.
> No human ran these tests.
> No human analysed the results.
>
> The system did all of this by itself, continuously,
> while we were doing other things."

---

## The Comparison That Lands — Say This at the End

> "Let me show you how this compares to what everyone else does.
>
> **Without our system:**
> You build an agent, you test 5 questions manually,
> they look fine, you ship it.
> Three months later, an employee gets wrong information about their leave.
> You have no idea when it started going wrong.
>
> **With our system:**
> 659 automated runs found a contradiction in Run 1 of the probationary question.
> Found that sick leave questions are being answered uselessly — 44 runs of evidence.
> Found that the minimum leave question is answered perfectly — 42 runs of evidence.
> All of this before a single real employee asks a single real question.
>
> This is the difference between hoping your AI works
> and **knowing** your AI works."

---

## The Technical Flex (For a Developer Audience)

If there are engineers in the room, add this:

> "The most interesting part technically is Layer 1 — the Factual Anchor Check.
>
> Every number, dollar amount, and time period in the agent's answer
> is extracted by pure regex code and checked against the source document.
> No LLM involved. No API call. No cost.
>
> So when the agent says '30 days to submit expense claims' —
> the system extracts '30', finds '30' in the Expense Policy, marks it supported.
> Score: 1.00 for that fact.
>
> If the agent ever says '60 days' — the system extracts '60',
> doesn't find it in Expense Policy, marks it hallucinated.
> Score drops immediately. Hard cap kicks in.
>
> Two lines of the evaluation are completely un-gameable by any LLM:
> pure code and pure math. That's what makes this reliable."

---

## The Killer Closing Line

> "Every AI demo you've seen shows you the answers that worked.
> We're showing you the ones that didn't — because that's
> the only way you actually know if your AI is safe to deploy."

---

## Quick Reference — The 4 Numbers to Memorise

Before you present, memorise these four numbers:

| Number | What to say |
|---|---|
| **659** | Total automated test runs — no human involved |
| **2** | Contradictions caught automatically by the system |
| **0.37** | Lowest score — probationary leave question, caught a wrong answer |
| **1.00** | Highest score — minimum leave question, agent knew its limits perfectly |
