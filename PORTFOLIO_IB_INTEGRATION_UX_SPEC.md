# Portfolio Interactive Brokers Integration - UX Specification

## Overview

This document describes the **Interactive Brokers (IB) integration** for automated portfolios. Portfolios can now execute real trades through Interactive Brokers instead of just simulating them. This feature is **optional** and extends the existing automation system.

---

## What Changed

Previously, automated portfolios **simulated** all trades with estimated prices and slippage. Now, automated portfolios can optionally connect to **Interactive Brokers** to execute **real market orders**.

### Key Differences

| Feature | Simulation Mode (Before) | IB Mode (New) |
|---------|-------------------------|---------------|
| Order Execution | Instant, simulated | Real orders to IB |
| Fill Prices | Estimated + slippage | Actual market fills |
| Commissions | Estimated | Actual IB commissions |
| Risk | No real money | **REAL MONEY** |
| Requirements | None | IB Gateway running |

---

## API Changes

### Portfolio Model - New Fields

Add **6 new fields** to the Portfolio model for IB configuration:

#### 1. `use_interactive_brokers` (boolean, default: `false`)
- **If `true`**: Trades executed via Interactive Brokers API
- **If `false`**: Trades simulated (original behavior)
- **IMPORTANT**: Only applies to automated portfolios (`is_automated=true`)

#### 2. `ib_host` (string, default: `"127.0.0.1"`, optional)
- IB Gateway/TWS host address
- Usually `"127.0.0.1"` (localhost)
- Can be remote IP if IB Gateway on another machine

#### 3. `ib_port` (integer, default: `4001`, optional)
- IB Gateway/TWS port number
- **Common values**:
  - `4001` - IB Gateway Live Trading
  - `4002` - IB Gateway Paper Trading (recommended)
  - `7497` - TWS Live Trading
  - `7496` - TWS Paper Trading

#### 4. `ib_client_id` (integer, default: `1`, optional)
- Unique client ID for this portfolio's IB connection
- **Range**: 1 to 999
- **IMPORTANT**: Each portfolio must have a different client_id
- If two portfolios use the same client_id, connections will conflict

#### 5. `ib_account` (string, optional, can be null/blank)
- Interactive Brokers account number
- Only needed if user has multiple IB accounts
- Leave blank/null for default account

#### 6. `ib_is_paper` (boolean, default: `true`)
- **If `true`**: Uses IB paper trading account (fake money)
- **If `false`**: Uses IB live trading account (**REAL MONEY**)
- **IMPORTANT**: Show prominent warning when `false`

---

## API Response Example

### Portfolio with IB Enabled

```json
{
  "id": 15,
  "name": "My IB Day Trading Portfolio",
  "description": "Live trading via Interactive Brokers",
  "user": 1,
  "exchange": 2,
  "is_active": true,
  "cash_balance": 5421.80,

  "is_automated": true,
  "dt_max_position_percent": "0.25",
  "dt_per_trade_risk_fraction": "0.020",
  "dt_max_recommendations": 50,
  "dt_allow_fractional_shares": false,

  "use_interactive_brokers": true,
  "ib_host": "127.0.0.1",
  "ib_port": 4002,
  "ib_client_id": 1,
  "ib_account": null,
  "ib_is_paper": true,

  "created_at": "2025-10-01T10:00:00Z",
  "updated_at": "2025-10-17T15:30:00Z"
}
```

### Portfolio with IB Disabled (Original Behavior)

```json
{
  "id": 16,
  "name": "My Simulated Portfolio",
  "description": "Simulated trading only",
  "user": 1,
  "exchange": 2,
  "is_active": true,
  "cash_balance": 10000.00,

  "is_automated": true,
  "dt_max_position_percent": "0.25",
  "dt_per_trade_risk_fraction": "0.020",
  "dt_max_recommendations": 50,
  "dt_allow_fractional_shares": false,

  "use_interactive_brokers": false,
  "ib_host": "127.0.0.1",
  "ib_port": 4001,
  "ib_client_id": 1,
  "ib_account": null,
  "ib_is_paper": true,

  "created_at": "2025-10-01T10:00:00Z",
  "updated_at": "2025-10-17T15:30:00Z"
}
```

---

## UX Requirements

### 1. Portfolio Creation/Edit Form - Add IB Section

Add a new collapsible section **AFTER** the "Day Trading Settings" section:

#### Section: "Interactive Brokers Integration" (visible only when `is_automated=true`)

This section should be **conditionally displayed** only when the portfolio is automated.

**Toggle:**
- **☐ Use Interactive Brokers for Live Trading**
  - Default: OFF (unchecked)
  - Label: "Connect to Interactive Brokers"
  - Help Text: "Execute real trades via IB Gateway/TWS. Requires IB Gateway running on your computer."

**Fields (visible only when toggle is ON):**

**Field 1: Connection Settings**
```
┌─────────────────────────────────────────┐
│ Connection Settings                     │
│                                         │
│ Host: [127.0.0.1    ]                   │
│ Help: IB Gateway/TWS host address       │
│                                         │
│ Port: [4002]                            │
│ Help: 4001=Gateway Live, 4002=Gateway   │
│       Paper, 7497=TWS Live, 7496=TWS    │
│       Paper                             │
│                                         │
│ Client ID: [1]                          │
│ Help: Unique ID (1-999). Each portfolio │
│       needs a different Client ID.      │
└─────────────────────────────────────────┘
```

**Field 2: Account Settings**
```
┌─────────────────────────────────────────┐
│ Account Settings                        │
│                                         │
│ IB Account Number (optional):           │
│ [                    ]                  │
│ Help: Leave blank for default account   │
└─────────────────────────────────────────┘
```

**Field 3: Trading Mode**
```
┌─────────────────────────────────────────┐
│ Trading Mode                            │
│                                         │
│ ○ Paper Trading (Recommended)           │
│   Trades with fake money on IB paper    │
│   account. Safe for testing.            │
│                                         │
│ ○ Live Trading ⚠️                        │
│   Trades with REAL MONEY. Use only      │
│   after testing with paper account.     │
└─────────────────────────────────────────┘
```

#### Field Mappings

| UI Field | API Field | Input Type | Default |
|----------|-----------|------------|---------|
| "Connect to Interactive Brokers" toggle | `use_interactive_brokers` | Checkbox/Toggle | `false` |
| "Host" | `ib_host` | Text Input | `"127.0.0.1"` |
| "Port" | `ib_port` | Number Input | `4002` |
| "Client ID" | `ib_client_id` | Number Input | `1` |
| "IB Account Number" | `ib_account` | Text Input (optional) | `null` |
| Trading Mode radio | `ib_is_paper` | Radio Buttons | `true` (Paper) |

#### Validation Rules

1. **IB fields only required when `use_interactive_brokers=true`**
2. **Host**: Cannot be empty if IB enabled
3. **Port**: Must be 1-65535
4. **Client ID**: Must be 1-999
5. **Client ID uniqueness**: Show warning if another portfolio uses same client_id (backend should validate)
6. **Account Number**: Optional, can be blank/null

---

### 2. Portfolio List View - Add IB Badge

Update the automation badge to show IB status:

**Current (Automation Only):**
```
My Day Trading Portfolio     🤖 Automated
```

**New (With IB Status):**
```
My Day Trading Portfolio     🤖 Automated • 🔌 IB Live
My Simulated Portfolio       🤖 Automated • 💻 Simulated
My Manual Portfolio          👤 Manual
```

**Badge Logic:**
- If `is_automated=false`: Show "👤 Manual"
- If `is_automated=true` AND `use_interactive_brokers=false`: Show "🤖 Automated • 💻 Simulated"
- If `is_automated=true` AND `use_interactive_brokers=true` AND `ib_is_paper=true`: Show "🤖 Automated • 🔌 IB Paper"
- If `is_automated=true` AND `use_interactive_brokers=true` AND `ib_is_paper=false`: Show "🤖 Automated • 🔌 IB Live" (with warning color)

---

### 3. Portfolio Detail View - Show IB Connection Status

Update the "Automation Status" section:

**When `use_interactive_brokers=false` (Simulated):**
```
┌─────────────────────────────────────────┐
│ Trading Mode: Automated 🤖              │
│ Execution: Simulated 💻                 │
│                                         │
│ Settings:                               │
│ • Max Position Size: 25%                │
│ • Risk Per Trade: 2%                    │
│ • Max Daily Positions: 50               │
│ • Fractional Shares: Disabled           │
│                                         │
│ All trades are simulated. No real       │
│ money involved.                         │
│                                         │
│ [Edit Settings] [Enable IB Trading]     │
└─────────────────────────────────────────┘
```

**When `use_interactive_brokers=true` AND `ib_is_paper=true` (IB Paper):**
```
┌─────────────────────────────────────────┐
│ Trading Mode: Automated 🤖              │
│ Execution: Interactive Brokers 🔌       │
│ Account: Paper Trading (Safe) ✓         │
│                                         │
│ IB Connection:                          │
│ • Host: 127.0.0.1                       │
│ • Port: 4002 (Gateway Paper)            │
│ • Client ID: 1                          │
│ • Status: Connected ✓                   │
│   (or "Disconnected - Check IB Gateway")│
│                                         │
│ Day Trading Settings:                   │
│ • Max Position Size: 25%                │
│ • Risk Per Trade: 2%                    │
│ • Max Daily Positions: 50               │
│ • Fractional Shares: Disabled           │
│                                         │
│ [Edit Settings] [Test Connection]       │
└─────────────────────────────────────────┘
```

**When `use_interactive_brokers=true` AND `ib_is_paper=false` (IB Live):**
```
┌─────────────────────────────────────────┐
│ Trading Mode: Automated 🤖              │
│ Execution: Interactive Brokers 🔌       │
│ Account: ⚠️ LIVE TRADING - REAL MONEY   │
│                                         │
│ IB Connection:                          │
│ • Host: 127.0.0.1                       │
│ • Port: 4001 (Gateway Live)             │
│ • Client ID: 1                          │
│ • Status: Connected ✓                   │
│                                         │
│ ⚠️ WARNING: This portfolio trades with  │
│ real money. All trades are executed on  │
│ your live IB account.                   │
│                                         │
│ Day Trading Settings:                   │
│ • Max Position Size: 25%                │
│ • Risk Per Trade: 2%                    │
│ • Max Daily Positions: 50               │
│ • Fractional Shares: Disabled           │
│                                         │
│ [Edit Settings] [Test Connection]       │
└─────────────────────────────────────────┘
```

---

### 4. Warnings and Confirmations

#### When Enabling IB for First Time:
```
⚠️ Enable Interactive Brokers Trading?

This portfolio will execute REAL orders through Interactive Brokers.

Before continuing:
✓ Ensure IB Gateway or TWS is running
✓ API connections are enabled in IB settings
✓ You have configured the correct port
✓ Start with PAPER TRADING to test

We recommend:
• Use paper trading first
• Test with small positions
• Monitor closely for first few days

[Cancel] [Continue to Settings]
```

#### When Switching Paper → Live:
```
⚠️ SWITCH TO LIVE TRADING?

You are about to enable LIVE trading with REAL MONEY.

This portfolio will:
• Execute real buy/sell orders
• Use your actual IB account balance
• Incur real commissions and fees
• Trade with real market risk

Are you absolutely sure?

Type "CONFIRM" to proceed: [_______]

[Cancel] [Enable Live Trading]
```

#### When Testing Connection:
Show a connection test dialog:
```
Testing IB Connection...

Host: 127.0.0.1
Port: 4002
Client ID: 1

[... checking ...]

✓ Connected successfully!
✓ Account type: Paper Trading
✓ Buying power: $100,000.00

[Close]
```

Or if failed:
```
❌ Connection Failed

Could not connect to IB Gateway at 127.0.0.1:4002

Common issues:
• IB Gateway is not running
• Incorrect port number
• API connections not enabled in IB settings
• Client ID already in use

[Try Again] [Cancel]
```

---

### 5. Settings Page / Dashboard Updates

If you have a settings or dashboard overview:

**Add IB Connection Status Widget:**
```
┌─────────────────────────────────────────┐
│ Interactive Brokers Status              │
│                                         │
│ Connected Portfolios:                   │
│ • Portfolio #1: ✓ Connected (Paper)     │
│ • Portfolio #2: ✓ Connected (Live) ⚠️   │
│ • Portfolio #3: ❌ Disconnected          │
│                                         │
│ [Test All Connections]                  │
└─────────────────────────────────────────┘
```

---

### 6. Position/Order Status Updates

When viewing positions or order history for IB-enabled portfolios:

**Show execution details:**
```
Order History (Today)

BUY 100 AAPL @ $175.50
Status: ✓ Filled
Type: Market Order
IB Order ID: 123456789
Fill Price: $175.52 (actual)
Commission: $0.35
Time: 9:30:15 AM

SELL 100 AAPL @ $176.80
Status: ⏳ Pending (submitted to IB)
Type: Market Order
IB Order ID: 123456790
Submitted: 3:29:45 PM
Expected fill: Within 30 seconds
```

For simulated portfolios, no IB order ID shown.

---

## Form Layout Recommendation

Suggested order of sections in Portfolio Edit form:

1. **Basic Info** (Name, Description, Exchange)
2. **Trading Mode** (Manual vs Automated toggle)
3. **Day Trading Settings** (if automated)
4. **Interactive Brokers Integration** (if automated) ← NEW
5. **Initial Cash Balance**
6. Save/Cancel buttons

---

## Validation & Error Handling

### Client-Side Validation

When `use_interactive_brokers=true`:
- ✓ `ib_host` is not empty
- ✓ `ib_port` is between 1-65535
- ✓ `ib_client_id` is between 1-999
- ✓ If `ib_is_paper=false`, require extra confirmation

### Backend Errors to Handle

Your API may return these errors:

| HTTP Code | Error | User Message |
|-----------|-------|--------------|
| 400 | Invalid port | "Port must be between 1 and 65535" |
| 400 | Invalid client_id | "Client ID must be between 1 and 999" |
| 409 | client_id in use | "Client ID 1 is already used by Portfolio #5. Each portfolio needs a unique Client ID." |
| 500 | IB connection failed | "Could not connect to IB Gateway. Please check your settings." |

---

## Behavioral Notes

### How IB Integration Works (Background Info)

1. **Morning (9:15 AM EST)**:
   - System generates recommendations
   - If `use_interactive_brokers=true`:
     - Submits BUY orders to IB
     - Orders show as "Pending"
     - Background task checks status every 30 seconds
   - If `use_interactive_brokers=false`:
     - Simulates fills immediately

2. **Order Fills**:
   - IB orders typically fill within seconds
   - Actual fill price may differ slightly from estimated
   - Position updates to "Open" after fill
   - Transaction created with actual fill price

3. **Position Closing**:
   - Similar async process
   - SELL orders submitted to IB
   - Position shows "Closing"
   - Updates to "Closed" after fill

### User-Visible Differences

Users will notice:
- **Slight delays** (30-60 seconds) between order submission and fill
- **Position status changes**: PENDING → OPEN → CLOSING → CLOSED
- **Actual prices** instead of estimates
- **Real commissions** from IB

---

## Mobile Considerations

For mobile/tablet views:

1. **Collapse IB section by default** with "Advanced: IB Integration" header
2. **Simplify connection test** - single "Test" button instead of detailed output
3. **Stack fields vertically** instead of side-by-side
4. **Use bottom sheets** for warnings/confirmations

---

## Accessibility

- Use `<fieldset>` and `<legend>` for IB settings group
- Label inputs clearly: "IB Gateway Host Address", not just "Host"
- Provide `aria-describedby` for help text
- Use color + icon + text for status (not just color)
- Ensure warnings are announced to screen readers

---

## Migration Notes

### For Existing Portfolios

All existing portfolios will have:
- `use_interactive_brokers = false` (disabled by default)
- IB fields populated with defaults
- No change in behavior until user explicitly enables IB

### For New Portfolios

Default values:
- `use_interactive_brokers = false`
- `ib_host = "127.0.0.1"`
- `ib_port = 4002` (paper trading)
- `ib_client_id = 1`
- `ib_account = null`
- `ib_is_paper = true`

---

## Testing Checklist

### UI Testing
- [ ] IB section hidden for manual portfolios
- [ ] IB section visible for automated portfolios
- [ ] Toggle shows/hides IB fields correctly
- [ ] All fields save correctly
- [ ] Validation works (port range, client_id range)
- [ ] Paper/Live radio buttons work
- [ ] Warnings display when enabling IB
- [ ] Extra confirmation when switching to live
- [ ] Portfolio list shows correct IB badges
- [ ] Portfolio detail shows IB connection status
- [ ] Test connection button works

### API Testing
- [ ] Can create portfolio with IB enabled
- [ ] Can update portfolio to enable IB
- [ ] Can update portfolio to disable IB
- [ ] Backend validates client_id uniqueness
- [ ] GET endpoints return new IB fields
- [ ] PATCH works for partial updates

---

## Visual Reference

### Recommended UI Layout

```
┌────────────────────────────────────────────────┐
│ Edit Portfolio: My Trading Portfolio          │
├────────────────────────────────────────────────┤
│                                                │
│ Basic Information                              │
│ Name: [My Trading Portfolio          ]        │
│ Description: [Trading account         ]        │
│ Exchange: [NASDAQ ▼]                           │
│                                                │
│ ──────────────────────────────────────────────│
│                                                │
│ Trading Mode                                   │
│ ○ Manual Portfolio                             │
│ ● Automated Day Trading                        │
│                                                │
│ ──────────────────────────────────────────────│
│                                                │
│ Day Trading Settings                           │
│ Max Position Size: [25] %                      │
│ Risk Per Trade: [2.0] %                        │
│ Max Daily Positions: [50]                      │
│ ☐ Allow Fractional Shares                      │
│                                                │
│ ──────────────────────────────────────────────│
│                                                │
│ Interactive Brokers Integration                │
│ ☑ Connect to Interactive Brokers               │
│                                                │
│   Connection Settings                          │
│   Host: [127.0.0.1         ]                   │
│   Port: [4002] ⓘ Paper trading                 │
│   Client ID: [1]                               │
│                                                │
│   Account (optional)                           │
│   IB Account: [              ]                 │
│                                                │
│   Trading Mode                                 │
│   ● Paper Trading (Recommended)                │
│   ○ Live Trading ⚠️                             │
│                                                │
│   [Test Connection]                            │
│                                                │
│ ──────────────────────────────────────────────│
│                                                │
│ [Cancel]                    [Save Portfolio]   │
└────────────────────────────────────────────────┘
```

---

## Questions for Backend Team

_(Frontend team: Feel free to add questions here)_

1. Is there a "test connection" endpoint, or should we just attempt to save and show errors?
2. Can we get real-time IB connection status, or is it only checked when saving?
3. Is client_id uniqueness validated at the API level?
4. Are there any additional IB status fields we should display (e.g., last connection time)?

---

## Summary for Frontend Team

### What You Need to Do

1. **Add 6 new fields** to Portfolio create/edit forms (conditionally shown)
2. **Update portfolio list** to show IB badges
3. **Update portfolio detail** to show IB connection info
4. **Add warnings/confirmations** for enabling IB and switching to live
5. **Handle new validation** rules
6. **Test** with automated portfolios only

### What NOT to Change

- Manual portfolios: No IB settings needed
- Existing automation fields: No changes
- Simulation mode: Still works as before

### Priority

- **P0 (Must Have)**: Basic IB form fields, toggle, save functionality
- **P1 (Important)**: Warnings, badges, connection status display
- **P2 (Nice to Have)**: Test connection button, detailed status

---

## Support

For technical questions about this integration:
- Backend docs: See `IB_INTEGRATION.md`
- API schema: See `/api/docs/`
- Test command: `python manage.py test_ib_connection <portfolio_id>`

For UX/design questions:
- Contact: Backend team or design lead
