# Ads Ops System

This folder is the training loop for Sys ad recommendations.

## Daily flow (phone-friendly)
1. Sys sends 6:00am action plan.
2. Eric replies with action decisions using `ACTIONS` format.
3. After 24-72h, Eric sends outcomes using `OUTCOME` format.
4. Sys updates playbook/rules based on outcomes.

## Quick commands

### ACTIONS
Use one line per action:

`ACTIONS: <action_id> APPROVE|REJECT|MODIFY <optional note>`

Example:
- `ACTIONS: A1 APPROVE`
- `ACTIONS: A2 MODIFY cap increase at +10% not +20%`
- `ACTIONS: A3 REJECT`

### OUTCOME
Use one line per executed action:

`OUTCOME: <action_id> spend=<amt> cpa_delta=<%> roas_delta=<%> result=KEEP|UNDO note=<short>`

Example:
- `OUTCOME: A1 spend=42 cpa_delta=-18% roas_delta=+22% result=KEEP note=creative hook #3`

## Guardrails (always enforced)
- Total ad spend cap: **$100/day**.
- No ad write changes without explicit approval + valid iMessage OTP.
- OTP valid 5 min, single-use, bound to exact action text.
- See `2FA_WORKFLOW.md` for verification rules + fail-closed checks.
