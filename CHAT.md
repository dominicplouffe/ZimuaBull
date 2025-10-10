# ZimuaBull Chat / Agent Integration Guide

This guide equips UX and front-end engineers to integrate the new orchestrated chat experience (OpenAI + ZimuaBull analytics tools).

## High-Level Flow
1. **User enters a prompt** (e.g., “Backtest a 20-50 EMA crossover on TD.TO from 2020–2025”).
2. Frontend sends `POST /api/chat/` with the prompt and optional context **or opens an SSE stream** (see Streaming section below).
3. Backend orchestrator (OpenAI function-calling + tool layer) interprets the request, invokes the necessary tools, and aggregates results.
4. Response includes:
   - `reply`: conversational summary (Markdown-formatted)
   - `analysis`: structured payload (symbols, portfolios, scenarios, backtests, simulations)
   - `status_updates`: step-by-step log (“Executed tool run_strategy_backtest”)
   - `tool_results`: raw tool outputs for advanced UI elements or debugging
5. Conversation history is persisted via `/api/conversations/` endpoints for audit and memory.

> **Note:** The assistant now uses OpenAI (cloud hosted) and ZimuaBull data/tools only—no external brokerage integrations.

## Endpoints

### `POST /api/chat/`
- **Auth:** required (session or token)
- **Body:**
  ```jsonc
  {
    "message": "How did my tech portfolio perform this week versus the S&P 500?",
    "conversation_id": 42,          // optional: continue existing thread
    "context": {
      "portfolio_ids": [3],        // optional hints
      "include_history": true,
      "history_days": 60           // default 30
    }
  }
  ```
- **Response:**
  ```json
  {
    "conversation_id": 42,
    "reply": "Here is a summary...",
    "analysis": {
      "symbols": [ {...} ],
      "comparisons": [ {...} ],
      "portfolios": [ {...} ],
      "scenarios": [ {...} ],
      "backtests": [ {...} ],
      "simulations": [ {...} ],
      "warnings": ["Symbol SHOP exists on multiple exchanges; using TSE."]
    },
    "messages": [
      {"role": "user", "content": "How did my tech portfolio perform this week versus the S&P 500?"},
      {"role": "assistant", "content": "Here is a summary..."}
    ],
    "status_updates": ["Executed tool portfolio_overview", "Executed tool compare_symbols"],
    "tool_results": [
      {
        "tool": "run_strategy_backtest",
        "arguments": {"symbol": "TD", "exchange": "TSE", ...},
        "result": {"type": "backtest", "data": {...}}
      }
    ]
  }
  ```

### `GET /api/conversations/`
- Lists the user’s conversations (`[{"id": 42, "title": "Tech performance", ...}]`).
- `DELETE /api/conversations/` removes **all** conversations for the current user (`{"deleted": 5}`).

### `GET /api/conversations/<id>/`
- Returns the full transcript, timestamps, and stored context data.
- `DELETE /api/conversations/<id>/` deletes a single conversation (204 on success).

### `GET /api/llm-context/`
- Optional helper for quick-look symbol/portfolio data (same structure as pieces of `analysis`).

### `POST /api/chat-response/`
- Legacy endpoint for pushing custom assistant messages (rarely needed now).

### `GET /api/chat/stream/`
- **Auth:** required
- **Purpose:** Server-Sent Events (SSE) endpoint for live progress updates.
- **Query/body:** same parameters as `POST /api/chat/` (use query string or POST body)
- **Event schema:**
  - Initial: `data: {"status": "started"}`
  - Progress: `data: {"status": "Executed tool run_strategy_backtest"}` (one per step)
  - Final payload: `data: {"type": "final", "reply": "...", "analysis": {...}, "tool_results": [...]}`
  - Stream terminates with `event: end`.
- **Client integration:** use `EventSource` in the browser; update UI on each message and close once `event: end` is received. (Fallback to `POST /api/chat/` if SSE unavailable.)

## Tooling & Behaviour
- Powered by OpenAI (function calling) + internal tools:
  - `get_symbol_overview`
  - `compare_symbols`
  - `portfolio_overview`
  - `portfolio_scenario_analysis`
  - `run_strategy_backtest` (EMA crossover; extendable)
  - `simulate_rule_based_strategy`
- Tools return structured JSON snippets; the orchestrator aggregates them into the `analysis` block.
- `analysis.warnings` contains clarifications (e.g., ambiguous tickers).
- Status updates list each tool execution or failure for progressive UI feedback.

### Simulation Rules
- Triggered when the user specifies buy/sell thresholds, share quantity, and bankroll.
- Uses daily close-to-close deltas over the requested (or default 90-day) window.
- Buy rule: delta ≥ threshold → purchase `buy_shares` if cash permits.
- Sell rule: delta ≤ −threshold → liquidate current holdings.
- Output includes ending value, PnL, % return, remaining shares, and per-trade log.

## UX Implementation Tips
- Display `reply` as the assistant bubble.
- Render `analysis.symbols[]` and `analysis.comparisons[]` as metric cards + charts.
- Use `analysis.portfolios[]` and `analysis.scenarios[]` to power portfolio dashboards.
- `analysis.backtests[]` / `analysis.simulations[]` include results + trade logs for dedicated panels.
- Show `status_updates` as inline notifications (“Running backtest…done”).
- Optionally, use `tool_results` for drill-down tables or debugging output.
- For streaming UX, initiate an `EventSource` to `/api/chat/stream/` and show progress as each `status` message arrives; once the `final` payload is received, render the answer just like the non-streaming flow.

## Error Handling
- Missing `message` ⇒ `400 {"error": "Message is required"}`.
- Invalid `conversation_id` ⇒ `404 {"error": "Conversation not found"}`.
- Missing OpenAI API key ⇒ `503` with fallback reply.
- Tool failures appear in `analysis.warnings` and `status_updates`; assistant apologises automatically.

## Testing Checklist
- Single symbol queries (with/without exchange).
- Multi-symbol comparisons (“compare MSFT and AAPL”).
- Portfolio summary + scenario (“What if AAPL +10%, GOOG −2%?”).
- Strategy backtest (“Backtest a 20-50 EMA crossover on TD.TO from 2020–2025.”).
- Rule-based simulation (“If MSFT rises $1 buy 10 shares; if it falls $0.25 sell; bankroll $1000”).
- Conversation continuity (follow-up questions reuse context).
- Transcript retrieval (`GET /api/conversations/<id>/`).

With this contract, the UX team can present rich chat experiences: conversational bubbles, analysis cards, charts, and progressive status indicators without additional backend changes.
