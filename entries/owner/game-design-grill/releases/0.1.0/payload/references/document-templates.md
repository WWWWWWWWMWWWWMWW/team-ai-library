# Document Templates

Create these files lazily and only inside the user-approved project location. Preserve an existing project format when one already exists.

## `CONTEXT.md`

Use only for canonical terminology and stable relationships. Keep entries short and free of implementation details.

```markdown
# <Feature> Context

## <Canonical term>

<One precise definition. State how it differs from a commonly confused term when necessary.>

## Relationships

- `<Term A>` contains / starts / resolves `<Term B>`.
```

Do not include values, proposed alternatives, UI copy, implementation fields, meeting notes, or open questions.

## `RULES.md`

Use as the current rule source of truth.

```markdown
# <Feature> Rules

## Positioning

- <Confirmed purpose, audience, and activity type>

## Core loop

- <Short player-facing loop>

## Confirmed rules

### Entry and start

- <Rule>

### Active play

- <Rule>

### Resolution

- <Rule>

### Retry and end

- <Rule>

### Reward

- <Rule>

## Pending decisions

- <Question or missing rule; do not insert a preferred answer as fact>

## Deferred layers

- Values: <scope intentionally deferred>
- UI: <scope intentionally deferred>
- Implementation: <scope intentionally deferred>
```

Delete empty headings. Never keep contradictory active rules. Do not store rejected alternatives here.

## Major design-decision record

Store under `docs/decisions/` with a sequential prefix and a short decision-led name, for example `0001-use-target-score-with-time-cap.md`.

Create only after the user approves both the decision and the record.

```markdown
# <Decision title>

- Status: Accepted
- Date: YYYY-MM-DD

## Context

<The concrete design problem and why the decision matters.>

## Decision

<The chosen rule in unambiguous language.>

## Alternatives considered

- <Alternative>: <why it was not chosen>

## Reasons

- <Reason tied to player experience, product goal, fairness, economy, or delivery risk>

## Consequences

- Positive: <what this enables>
- Cost: <what becomes harder or less predictable>

## Revisit when

- <Evidence or condition that should reopen the decision>
```

For a replaced major decision, change its status to `Superseded`, link the replacement, and leave its original reasoning intact.

## Writing rules

- Use the user's language.
- Prefer one rule per bullet.
- State what happens, not the meeting history.
- Keep confirmed, pending, observed, and inferred information visibly separate.
- Cite source files, fields, videos, or external pages when a rule depends on them.
