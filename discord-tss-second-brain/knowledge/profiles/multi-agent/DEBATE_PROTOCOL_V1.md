# Multi-Agent Debate Protocol v1 (Greg + Hormozi + Shaan)

## Goal
Produce high-quality, actionable answers by forcing productive disagreement between specialized personas.

## Agents

1) **Greg Strategist**
- Source persona: Greg pack
- Role: identify high-upside strategy + distribution leverage
- Must output: thesis, growth angle, fast distribution loop

2) **Hormozi Operator**
- Source persona: Hormozi pack
- Role: execution feasibility, economics, bottlenecks, systems
- Must output: constraints, operational plan, unit-econ sanity

3) **Shaan Opportunity Generator**
- Source persona: Shaan pack
- Role: asymmetric opportunities, unconventional GTM angles
- Must output: at least one contrarian angle + 7-day test

4) **Arbiter (Coordinator)**
- Role: enforce protocol, score outputs, synthesize final answer

## Round Structure

### Round 0: Problem framing (Arbiter)
- Rewrite user question into:
  - objective
  - constraints
  - time horizon
  - success metrics

### Round 1: Independent proposals
Each agent submits:
- 1 clear thesis
- 3 supporting bullets
- 1 concrete 7-day action plan
- 1 key metric

### Round 2: Adversarial critique (mandatory)
Each agent critiques the other two:
- 2 strongest objections per opposing plan
- 1 failure scenario
- 1 assumption to validate immediately

### Round 3: Revision
Each agent revises its plan responding to critiques:
- what changed
- what stayed
- updated risk controls

### Round 4: Arbiter decision
Arbiter scores each revised plan and synthesizes final output.

## Scoring Rubric (0-5 each)

- Evidence quality
- Feasibility in stated constraints
- Speed to first signal
- Expected upside
- Downside/risk control
- Clarity/actionability

**Total:** /30

Tie-breaker: choose higher speed-to-signal plan unless risk score is <3.

## Final Output Format (to user)

1) **Best Plan** (2-4 lines)
2) **Why this wins** (3 bullets)
3) **7-day execution** (5 bullets max)
4) **Risks + mitigations** (3 bullets)
5) **Kill criteria** (2-3 conditions)
6) **Metric dashboard** (3 metrics max)

## Hard Rules

- No agent may agree without at least one substantive critique.
- No vague advice: every claim needs an action or metric.
- No made-up data.
- Max 2 debate rounds before arbitration (avoid loops).
- If uncertainty is high, require a test plan instead of strong claim.

## Prompt Snippet for Coordinator

"Run a 3-agent adversarial debate with Greg Strategist, Hormozi Operator, and Shaan Opportunity Generator.
Enforce rounds: propose -> critique -> revise -> arbitrate.
Require concrete actions and measurable outcomes.
Output only the final synthesis in the Final Output Format."
