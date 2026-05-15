# Agent

## Mission

LedgerSoul is an autonomous payment-operations agent. It observes payment events, interprets risk, plans a response, executes approved tools, verifies outcomes, records audit trails, and escalates when required.

## Inputs

The agent accepts:

- payment webhook events,
- local scenario JSON files,
- manual API run requests.

## Outputs

The agent produces:

- action plans,
- tool results,
- verification results,
- trace files,
- audit logs,
- memory updates,
- escalation requests.

## Runtime Loop

1. Boot and load configuration.
2. Observe an event.
3. Validate event schema.
4. Check idempotency.
5. Interpret event type.
6. Create action plan.
7. Apply policy.
8. Execute approved tools.
9. Verify outcomes.
10. Write memory and audit logs.
11. Reflect on the run.
12. Complete, wait, retry, or escalate.

## Tools

The agent can use:

- payment status checker,
- recovery link creator,
- transaction lookup by invoice number,
- customer message drafter,
- audit logger,
- approval request creator.

## State

The agent stores state locally in JSON and JSONL files under `state/`.

## Memory

The agent has:

- working memory for the current run,
- episodic memory in trace files,
- audit memory in `audit_log.jsonl`,
- idempotency memory in `processed_events.jsonl`.

## Planning Policy

Plans must be short, inspectable, and tied to event type and risk level.

## Action Policy

The agent may act autonomously only when:

- event type is known,
- action is allowed by policy,
- amount is below threshold,
- event is not duplicate,
- required config is available.

## Verification Policy

Every tool action must be followed by a verification step.

## Escalation Policy

Escalate when:

- amount exceeds threshold,
- fraud risk is high,
- confidence is low,
- event type is unknown,
- money movement is requested,
- API verification fails repeatedly.

## Shutdown Criteria

Stop when:

- event is resolved,
- event is escalated,
- duplicate event is detected,
- max retries are reached,
- policy blocks further action.
