# Game Design Dimensions

Use this as a routing and audit reference, not as a questionnaire. Inspect only the current layer, choose the highest-impact gap, and ask one question at a time.

## 1. Positioning and success

- What player or business problem does the feature solve?
- Who is the target player, and why would they participate now?
- Is it a one-off event, recurring activity, stackable layer, or long-term system?
- If one experience must survive, what is it?
- What existing behavior or resource should it amplify rather than replace?
- What observable outcome would show that the feature worked?

Do not proceed when the answer is only a mechanic with no player or business purpose.

## 2. Core player experience and loop

- What does the player prepare, trigger, do repeatedly, and feel at the climax?
- Where does agency live? What decision can change the outcome?
- What creates tension, relief, mastery, surprise, or comeback emotion?
- Does the loop produce dead time, solved states, hoarding, last-second play, or repetitive ramps?
- Can the feature be described as a short player-facing loop without system jargon?

Prefer existing game actions. Added controls, currencies, random choices, or manual selection need a clear experiential job.

## 3. Rules and state model

### Entry and start

- Unlock and eligibility
- Trigger versus formal start
- Matchmaking or grouping moment
- Preparation allowed before start
- Cost, confirmation, and cancellation

### Active state

- Valid scoring/progress actions
- Ownership of progress and timing
- Opponent/system behavior
- Caps, targets, checkpoints, and priority
- Leaving the main screen, backgrounding, disconnecting, and recovery

### Resolution

- Success and failure conditions
- Timeout and tie handling
- Overshoot, simultaneous completion, and duplicate submission
- Reward eligibility and claim timing
- Progress carried, reset, or converted

### Replay and end

- Cooldown, retry, rematch, and opponent refresh
- Daily/period limits
- Event ending during an active state
- Version update, rollback, and compensation boundaries when relevant

## 4. Values, pacing, and economy

- Translate the intended experience into time, actions, energy, currency, and reward exposure.
- Separate theoretical ceilings, high-intensity human ranges, typical behavior, and telemetry.
- Check pre-stocked resources, multipliers, buffs, segmentation, and paid acceleration.
- Ensure targets do not reward waiting, last-second dumping, or a single stored burst unless intended.
- State assumptions and leave exact values pending until the rule and data source are stable.

## 5. UI, interaction, and teaching

- What must remain visible during play?
- How does one action visibly cause progress in every affected system?
- What changes after the player catches up, leads, reaches a cap, or becomes unable to act?
- Can the first-use teaching be understood through cause-and-effect feedback rather than a paragraph?
- Cover normal, unavailable, no-resource, no-space, capped, interrupted, and ended states.
- Define trigger, target selection, skip, completion, and recovery for guides.

## 6. Configuration, analytics, and acceptance

### Configuration

- Distinguish total, current, added, historical, and per-stage values.
- Identify which rules are configurable and which are code invariants.
- Verify edit source, export chain, and runtime consumer.

### Analytics

- Start from product questions.
- Record before/add/after values, sources, results, and critical failure reasons.
- Separate exposure, participation, active behavior, spend, outcome, retry, and reward claim.

### Acceptance

- Cover the main flow, every state transition, boundaries, interruption recovery, segmentation, overlapping activities, and event end.
- Verify the actual build, asset, video, sheet, or runtime output rather than a preview or same-named generated file.

## Audit output

When the user asks for a completeness audit, report only:

1. Blocking gaps — cannot hand off safely
2. Material risks — can proceed only with explicit assumptions
3. Deferred items — intentionally left for a later layer
4. Confirmed-safe areas — brief, no praise padding

Do not reopen an accepted decision merely because another option exists.
