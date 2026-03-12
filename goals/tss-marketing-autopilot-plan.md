# TSS Marketing Autopilot Plan

Last updated: 2026-03-12
Owner: Sys + Eric
Status: Phase 1 kickoff

## End Goal
Run a high-performance, mostly hands-off growth system that continuously analyzes performance, recommends improvements, and progressively automates content/creative operations with guardrails.

## Phases

### Phase 1 — Analysis + Alerts (implement now)
Objective: reliable decision engine before automating creative execution.

Deliverables:
1. Daily deep-dive report (strategic)
2. Intra-day monitoring checks (operational)
3. Threshold-based red alerts (exception handling)
4. Action queue with prioritized recommendations
5. QA + reliability checks so outputs are trustworthy

### Phase 2 — Creative ideation automation
Generate and rank hooks, script angles, and creative tests from recent performance trends.

### Phase 3 — Draft production automation
Create draft video variants/captions/CTAs in batches for approval workflows.

### Phase 4 — Hands-off loop
Auto-ship approved content patterns, monitor outcomes, and retune continuously.

---

## Phase 1 Detailed Operating Spec

### 1) Cadence
- Daily deep dive: 8:00 AM America/Los_Angeles
- Intra-day checks: every 3 hours
- Red alerts: immediate on threshold breaches

### 2) Data scope (v1)
- Meta Ads performance
- KPI/follower trajectory in existing dashboard pipeline
- Optional expansion later: organic content diagnostics + post-level metadata

### 3) Core metrics
- Spend, CPC, CPM, CTR, CPA/CPF
- ROAS proxy metrics (where available)
- Follower net growth + pace-to-goal
- Campaign/adset/ad-level trend deltas (DoD, 7D)
- Delivery health (learning-limited, under-delivery, volatility)

### 4) Alert thresholds (initial defaults)
- CPA or CPF worsens >20% DoD with meaningful spend
- Spend pace drops >30% versus expected daily pacing
- CTR drops >20% DoD on active campaigns
- Follower pace falls below required daily growth to target
- Any data freshness failure (stale pipeline or failed pull)

### 5) Output format
- Executive summary (5 bullets max)
- Operator actions (top 3 with impact/urgency)
- Red flags and confidence level
- Link/reference to dashboard context

### 6) QA / “done right first time” safeguards
- Freshness checks before analysis runs
- Minimum sample-size gates to reduce false alarms
- Compare latest run versus previous run to catch data anomalies
- Clear confidence tags: High / Medium / Low
- Failsafe message when data quality is insufficient

### 7) Ownership model
- Green: system can auto-publish updates/analysis messages
- Yellow: system drafts changes and requests one-tap approval
- Red: system blocks and requests explicit review

### 8) Success criteria for Phase 1
- 14-day run with >95% successful scheduled analyses
- <10% false-positive alerts
- Action recommendations accepted as useful in majority of daily reports
- No missed critical pacing/performance event

---

## Open Questions to lock before full rollout
1. Preferred deep-dive delivery channel (this Discord channel confirmed?)
2. Quiet hours for non-critical alerts
3. Final threshold tuning per KPI
4. Whether to include weekday/weekend pacing normalization in v1
5. Exact goal target and deadline for follower growth model

## Phase 1 Exit Criteria (gate to Phase 2)

Run for 3–5 consecutive days and move to Phase 2 only when all are true:

1. Reliability
- Scheduled jobs success rate >= 95%
- No critical pipeline break (data pull + KPI build + deploy path healthy)

2. Signal Quality
- False-positive alert rate <= 10%
- At least 1 true actionable alert captured (or explicit note that no thresholds were breached)
- Attribution confidence median at least Medium across daily runs

3. Data Integrity
- Daily spend source is unambiguous (today vs window spend clearly labeled)
- Freshness check passes on all daily deep dives
- No unresolved schema mismatch between dashboard JSON and UI fields

4. Operator Value
- Daily brief includes clear top 3 actions with expected impact
- Recommendations judged useful in majority of days (>=3 of last 5)

5. Safety/Control
- Guardrails stable (no unintended outbound actions)
- Manual override path tested and reversible

## Immediate Execution Checklist (now)
- [ ] Run today’s 6pm PT calibration review and tune thresholds
- [ ] Confirm tomorrow morning deep-dive output quality
- [ ] Capture one full day of clean auto-monitor events (every 3h)
- [ ] Lock threshold adjustments after day 3 if stable
- [ ] Start Phase 2 kickoff only after passing the criteria above

## Next Step
Operate Phase 1 under the exit criteria above; once the gate is met, begin Phase 2 (creative ideation automation).
