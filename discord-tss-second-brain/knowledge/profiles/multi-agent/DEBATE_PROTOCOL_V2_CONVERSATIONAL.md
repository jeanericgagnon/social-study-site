# Multi-Agent Debate Protocol v2 (Conversational + Contrarian)

## Objective
Run true expert-to-expert conversation where each expert:
1) iterates on others' ideas,
2) disagrees when needed,
3) backs claims with evidence/logic,
4) converges on best plan.

## Experts
- Greg Strategist (distribution + growth)
- Hormozi Operator (execution + economics)
- Shaan Opportunity (asymmetric ideas + tests)
- Arbiter (moderator + scorer)

## Conversation Rules (mandatory)
1. **No passive agreement**: every turn must include at least one of:
   - challenge,
   - improvement,
   - risk callout,
   - evidence request.
2. **Claim discipline**:
   - Every strong claim must include either evidence, mechanism, or explicit assumption.
3. **Contrarian duty**:
   - Each expert must present at least 1 contrarian objection per round.
4. **Iterative updates**:
   - Every expert must revise at least 1 prior idea from another expert (not just their own).
5. **Disagreement log**:
   - Arbiter keeps unresolved disagreements and closes them with a decision or test.

## Turn Protocol

### Round 0: Frame
Arbiter defines objective, constraints, timeline, success metrics.

### Round 1: Initial takes
Each expert provides:
- thesis
- 3 actions
- 1 key assumption

### Round 2: Cross-examination
Each expert must:
- challenge at least 2 claims from others,
- request evidence/mechanism,
- propose 1 stronger alternative.

### Round 3: Iteration
Each expert must submit:
- what they changed based on others,
- what they still disagree on,
- one experiment to settle the disagreement.

### Round 4: Convergence
Arbiter outputs:
- agreed actions,
- unresolved disagreements,
- decision rule (choose now vs test-first).

## Output Format (strict)

### A) Expert Conversation Summary
For each expert:
- original stance
- what they challenged
- what they changed
- what they still dispute

### B) Action Plan (final)
- Greg: 3 actions (owner, deadline <=7d, metric)
- Hormozi: 3 actions (owner, deadline <=7d, metric)
- Shaan: 3 actions (owner, deadline <=7d, metric)
- No duplicates across experts

### C) Contrarian Matrix
- Claim
- Challenger
- Defense
- Resolution (accept/reject/test)

### D) Top-5 merged actions (ranked)
Each includes owner + deadline + metric.

### E) Confidence
- Confidence: High/Medium/Low
- Top 3 assumptions that could break plan

## Arbiter Scoring
Score each expert on (0-5):
- originality
- practicality
- quality of critique
- quality of iteration
- evidence quality

Prefer plans where critique changed behavior (not static positions).

## Coordinator Prompt Snippet
"Run a conversational contrarian debate with Greg, Hormozi, and Shaan.
Enforce challenge + iteration rules. Require evidence/mechanism/assumption for claims.
Output Expert Conversation Summary, Contrarian Matrix, and final ranked top-5 actions.
No passive agreement."
