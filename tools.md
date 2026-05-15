# Tools

All tool calls go through `TOOL_REGISTRY` in `src/ledgersoul/agent/tool_registry.py`. The MVP exposes deterministic local tools plus explicit DOKU MCP tools for sandbox/provider access.

## check_payment_status

- **Purpose:** Read current payment state from the payment provider (mock).
- **Inputs:** `payment_id: str | None`
- **Outputs:** `{payment_id, status, source}`
- **Risk:** read
- **Verification:** result has a non-empty `status`.
- **Mock behavior:** returns `status="failed"`, `source="mock"`.
- **Live behavior (stretch):** calls real payment provider with `PAYMENT_API_KEY`.

## create_recovery_link

- **Purpose:** Generate a recovery link for the customer.
- **Inputs:** `payment_id`, `customer_id`, `amount`
- **Outputs:** `{payment_id, customer_id, amount, url, source}`
- **Risk:** write (mock-safe; would be dangerous live above threshold)
- **Verification:** `url` is non-empty and matches mock host in MVP.
- **Mock behavior:** returns `https://mock-payments.local/recover/<id>`.
- **Live behavior (stretch):** creates a real provider checkout/recovery session.

## get_transaction_by_invoice_number

- **Purpose:** Reconcile a customer/order transaction by invoice number.
- **Inputs:** `invoice_number: str | None`
- **Outputs:** `{invoice_number, transaction_status, amount, currency, payment_method, customer_name, source}`
- **Risk:** read
- **Verification:** invoice number and transaction status are present, and the result is audited.
- **Mock behavior:** returns a deterministic paid DOKU Sandbox Checkout record.
- **DOKU MCP behavior (explicit):** use remote `get_transaction_by_invoice_number` through `call_doku_mcp_tool` when live lookup is intentionally requested.

## draft_customer_message

- **Purpose:** Draft customer-facing recovery message.
- **Inputs:** `event`, `recovery_link`
- **Outputs:** `{channel, message, sent}`
- **Risk:** draft
- **Verification:** non-empty `message`, `sent=False` in MVP.
- **Mock behavior:** never sends; only drafts.
- **Live behavior (stretch):** sends via `MESSAGING_MODE=telegram` or similar.

## create_approval_request

- **Purpose:** Create a human approval ticket for a risky/unknown event.
- **Inputs:** `event`, `reason`
- **Outputs:** `{approval_id, event_id, reason, status}`
- **Risk:** write
- **Verification:** approval entry exists in `pending_approvals.jsonl`.
- **Mock behavior:** appends to `state/pending_approvals.jsonl`.
- **Live behavior (stretch):** posts to human review channel.

## write_audit_log

- **Purpose:** Append a structured audit entry for the run.
- **Inputs:** `memory`, `event`, `action`, `result`
- **Outputs:** `{written, entry}`
- **Risk:** write (audit-only)
- **Verification:** entry appears in `state/audit_log.jsonl`.
- **Mock behavior:** local JSONL append.
- **Live behavior (stretch):** mirror to remote audit sink.

## list_doku_mcp_tools

- **Purpose:** Initialize the DOKU MCP Server and list available remote payment tools.
- **Inputs:** `config: AgentConfig`
- **Outputs:** `{server, protocolVersion, tools}`
- **Risk:** read/network
- **Verification:** returns a `tools` list after DOKU MCP accepts the configured headers.
- **Sandbox behavior:** calls `https://api-sandbox.doku.com/doku-mcp-server/mcp` when explicitly requested.
- **Required env:** `DOKU_MCP_URL`, `DOKU_CLIENT_ID`, and either `DOKU_AUTHORIZATION` or `DOKU_API_KEY`.

## call_doku_mcp_tool

- **Purpose:** Explicitly call one remote DOKU MCP tool by name.
- **Inputs:** `config: AgentConfig`, `tool_name: str`, `tool_request: str`
- **Outputs:** DOKU MCP JSON-RPC response.
- **Risk:** tool-dependent; may create payment links, checkout links, QRIS, virtual accounts, customers, or other provider-side objects.
- **Verification:** response must contain a DOKU MCP `result` and should be audited before being shown to a customer.
- **Guardrail:** used by the deterministic runtime only for allowlisted DOKU workflows such as Judge Mode `doku_payment_methods`; live/provider calls must remain explicit and workflow-scoped.
- **Judge Mode use:** remote tool name is hardcoded to `get_merchant_payment_methods`; judge requests cannot pass arbitrary DOKU MCP tool names.

## Judge Mode Workflow Registry

Judge-facing workflow selection is defined separately from `TOOL_REGISTRY` in `src/ledgersoul/judge/workflows.py`. The workflow registry is intentionally tiny and maps button-level actions to fixed event shapes. Runtime execution still goes through the planner, executor, verifier, and explicit `TOOL_REGISTRY`.

MVP judge workflows:

- `transaction_lookup`: deterministic invoice reconciliation using `get_transaction_by_invoice_number` and `write_audit_log`.
- `doku_payment_methods`: read-only DOKU MCP sandbox workflow using `call_doku_mcp_tool` and `write_audit_log`.

## Adding a Tool

1. Implement the function under `src/ledgersoul/tools/`.
2. Register it in `TOOL_REGISTRY`.
3. Document it here with the same fields.
4. Add a verifier rule and a test.
