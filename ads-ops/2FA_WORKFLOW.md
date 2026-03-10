# Ads Write 2FA Workflow (v1)

## Status
- Approval gate: **ENABLED**
- OTP transport to iMessage: **READY** (validated 2026-03-10)
- OTP verification flow: **READY** (issue + return code validated 2026-03-10)
- Write mode: **ENFORCED-GATE** (approval + OTP required)

## Required before any write
1. Exact approval message from Eric:
   - `APPROVE ADS CHANGE: <exact action list>`
2. OTP challenge generated for that exact action text.
3. OTP delivered to Eric at `+16196339606` via iMessage.
4. Eric returns OTP within 5 minutes.
5. OTP verifies as:
   - 6 digits
   - single-use
   - not expired
   - bound to exact action text (byte-for-byte)

## High-risk actions (second confirm required)
- New campaign creation
- Budget increases >20%
- Bulk edits affecting >3 ad sets

Second confirm format:
- `CONFIRM HIGH-RISK ADS CHANGE: <exact same action list>`

## Rejection rules (fail-closed)
Reject write if any of:
- Approval line missing/malformed
- OTP missing/invalid/expired/reused
- Action text mismatch
- High-risk second confirm missing

## Action text canonical format (must match exactly)
Use one line per action, no extra prose:
- `A1: <entity> <field> <from> -> <to>`
- `A2: ...`

Example:
- `A1: adset_123 budget 25 -> 30`
- `A2: ad_445 status paused -> active`

Approval must reference these exact lines.

## Readiness test (non-destructive)
- Step 1: challenge build for sample action list
- Step 2: OTP send attempt to iMessage
- Step 3: OTP verify (valid)
- Step 4: OTP replay test (must fail)
- Step 5: expired OTP test (must fail)
- Step 6: action-text mismatch test (must fail)

Pass criteria: all six steps pass.

## Until transport is enabled
- Label all plans as:
  - `SAFE TO EXECUTE`: read-only analysis/reporting tasks
  - `NEEDS APPROVAL`: any potential ad-account write
