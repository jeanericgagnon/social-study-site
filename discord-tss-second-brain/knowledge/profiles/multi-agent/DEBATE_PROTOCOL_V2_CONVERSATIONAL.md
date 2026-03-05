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
6. **Local-corpus-first evidence policy**:
   - Citations must come from local persona corpora first.
   - Internet citations are fallback-only when local corpus lacks support.
7. **Single-response policy**:
   - Default user output is one unified arbiter synthesis.
   - Per-expert outputs are hidden unless `debug=true` is explicitly requested.

## Loop Budget
- Default: **3 loops** after framing (best quality/speed tradeoff)
  1) Initial takes
  2) Cross-examination
  3) Iteration + convergence
- Optional loop 4 only if major disagreements remain unresolved.
- Hard stop at loop 4 (avoid overthinking loops).

## Turn Protocol

### Round 0: Frame
Arbiter defines objective, constraints, timeline, success metrics.

### Round 1: Initial takes
Each expert provides:
- thesis
- 3 actions
- 1 key assumption
- 1 source-backed citation from local corpus (quote/snippet + local file path)

### Round 2: Cross-examination
Each expert must:
- challenge at least 2 claims from others,
- request evidence/mechanism,
- propose 1 stronger alternative,
- include 1 source-backed citation from local corpus.

### Round 3: Iteration
Each expert must submit:
- what they changed based on others,
- what they still disagree on,
- one experiment to settle the disagreement,
- 1 source-backed citation from local corpus,
- 1 metric-bound action.

### Round 4: Convergence (only if needed)
Arbiter outputs:
- agreed actions,
- unresolved disagreements,
- decision rule (choose now vs test-first).

## Output Format (strict)

### Default (`debug=false`)
Return **one unified final response** only:
1) Best approach (2-4 lines)
2) Top-5 merged actions (ranked, each with owner + deadline <=7d + metric)
3) Risks + mitigations (max 3)
4) Confidence + top unknowns
5) Evidence notes (local corpus file paths used)

### Debug mode (`debug=true` only)
Include internal details:
- Expert Conversation Summary
- Per-expert action sets
- Contrarian Matrix
- Revision notes by loop

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
Use loop budget: 3 loops by default, loop 4 only if major disagreements remain.
Enforce challenge + iteration rules. Require evidence/mechanism/assumption for claims.
Citations must be local-corpus-first (file paths); internet only as fallback.
Default output is one unified final synthesis (`debug=false`).
Only include per-expert internals and contrarian matrix when `debug=true`.
No passive agreement."
