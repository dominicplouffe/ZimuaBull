# Portfolio Automation - UX Specification

## Overview

This document describes the new portfolio automation feature that allows users to enable autonomous day trading on their portfolios. Each portfolio can now be configured as either **Automated** (runs day trading algorithm) or **Manual** (user-managed tracking only).

## Feature Summary

- **Portfolio Type Toggle**: Users can mark a portfolio as "Automated" or "Manual"
- **Automated Portfolios**: System executes autonomous day trading based on ML predictions
- **Manual Portfolios**: User manages holdings manually, system only tracks performance
- **Per-Portfolio Settings**: Each automated portfolio has configurable day trading parameters

---

## API Changes

### Portfolio Model - New Fields

The Portfolio model now includes the following new fields accessible via the API:

#### Core Flag
- **`is_automated`** (boolean, default: `false`)
  - If `true`: Portfolio runs autonomous day trading algorithm
  - If `false`: Portfolio is manual, user manages trades

#### Day Trading Settings (only apply when `is_automated=true`)

1. **`dt_max_position_percent`** (decimal, default: `0.25`)
   - Maximum percentage of portfolio to allocate per position
   - Range: `0.05` to `0.50` (5% to 50%)
   - Example: `0.25` = allow up to 25% of portfolio in a single stock

2. **`dt_per_trade_risk_fraction`** (decimal, default: `0.020`)
   - Risk fraction per trade for position sizing based on stop-loss
   - Range: `0.005` to `0.050` (0.5% to 5%)
   - Example: `0.02` = risk maximum 2% of portfolio per trade

3. **`dt_max_recommendations`** (integer, default: `50`)
   - Maximum number of positions to open in morning trading session
   - Range: `1` to `100`
   - Example: `50` = open up to 50 different positions per day

4. **`dt_allow_fractional_shares`** (boolean, default: `false`)
   - If `true`: Buy/sell fractional shares (e.g., 12.5734 shares)
   - If `false`: Round to whole shares only (e.g., 12 shares)

### API Endpoints

All portfolio endpoints now include these fields:

```
GET    /api/portfolios/           - List portfolios (includes automation fields)
GET    /api/portfolios/{id}/      - Get portfolio details (includes automation fields)
POST   /api/portfolios/           - Create portfolio (can set automation)
PUT    /api/portfolios/{id}/      - Update portfolio (can modify automation)
PATCH  /api/portfolios/{id}/      - Partial update (can toggle automation)
```

### Example API Responses

#### Portfolio List/Detail Response
```json
{
  "id": 15,
  "name": "My Day Trading Portfolio",
  "description": "Automated intraday trading",
  "user": 1,
  "exchange": 2,
  "is_active": true,
  "cash_balance": 5421.80,
  "is_automated": true,
  "dt_max_position_percent": "0.25",
  "dt_per_trade_risk_fraction": "0.020",
  "dt_max_recommendations": 50,
  "dt_allow_fractional_shares": false,
  "created_at": "2025-10-01T10:00:00Z",
  "updated_at": "2025-10-13T15:30:00Z",
  "total_invested": 0.00,
  "current_value": 5421.80,
  "total_gain_loss": 421.80,
  "total_gain_loss_percent": 8.44,
  "holdings_count": 0,
  "active_holdings_count": 0
}
```

---

## UX Requirements

### 1. Portfolio Creation/Edit Form

When creating or editing a portfolio, add a new section for automation settings:

#### Section: "Trading Mode"

**Toggle/Radio Button Group:**
- **○ Manual Portfolio** (default)
  - User manages all trades manually
  - System tracks performance only

- **○ Automated Day Trading**
  - System executes autonomous intraday trades
  - Configurable risk parameters below

#### Section: "Day Trading Settings" (visible only when Automated is selected)

This section should be **conditionally displayed** only when `is_automated=true`.

**Field 1: Maximum Position Size**
- Label: "Max Position Size (%)"
- Input: Slider or Number Input
- Range: 5% to 50%
- Default: 25%
- Help Text: "Maximum percentage of portfolio to allocate to a single position"

**Field 2: Risk Per Trade**
- Label: "Risk Per Trade (%)"
- Input: Slider or Number Input
- Range: 0.5% to 5%
- Default: 2%
- Help Text: "Maximum portfolio risk per trade based on stop-loss distance"

**Field 3: Max Daily Positions**
- Label: "Max Daily Positions"
- Input: Number Input
- Range: 1 to 100
- Default: 50
- Help Text: "Maximum number of positions to open in morning session"

**Field 4: Fractional Shares**
- Label: "Allow Fractional Shares"
- Input: Checkbox or Toggle
- Default: Off (false)
- Help Text: "Enable fractional share trading (e.g., 12.5734 shares) instead of whole shares only"

#### Validation Rules

- All fields are required when `is_automated=true`
- Validate ranges:
  - `dt_max_position_percent`: 0.05 to 0.50
  - `dt_per_trade_risk_fraction`: 0.005 to 0.050
  - `dt_max_recommendations`: 1 to 100
- When switching from Automated to Manual, preserve settings but don't enforce them
- Show warning if user has open positions when trying to disable automation

---

### 2. Portfolio List View

Add a visual indicator to distinguish automated vs manual portfolios:

**Badge/Chip/Icon:**
- Automated portfolios: Show "🤖 Automated" badge or robot icon
- Manual portfolios: Show "👤 Manual" badge or user icon

**Example:**
```
┌─────────────────────────────────────────────────┐
│ My Day Trading Portfolio     🤖 Automated       │
│ Cash: $5,421.80  |  P&L: +$421.80 (+8.44%)     │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ Long Term Holdings          👤 Manual           │
│ Cash: $2,500.00  |  P&L: +$1,200.00 (+15.00%)  │
└─────────────────────────────────────────────────┘
```

---

### 3. Portfolio Detail View

Add an "Automation" or "Trading Settings" section to portfolio detail page:

**Section: Automation Status**

When `is_automated=false`:
```
┌─────────────────────────────────────┐
│ Trading Mode: Manual                │
│ You manage all trades manually      │
│ [Enable Automation] button          │
└─────────────────────────────────────┘
```

When `is_automated=true`:
```
┌─────────────────────────────────────┐
│ Trading Mode: Automated 🤖          │
│                                     │
│ Settings:                           │
│ • Max Position Size: 25%            │
│ • Risk Per Trade: 2%                │
│ • Max Daily Positions: 50           │
│ • Fractional Shares: Disabled       │
│                                     │
│ [Edit Settings] [Disable]           │
└─────────────────────────────────────┘
```

**Trading Activity Section (Automated Portfolios Only):**

Show recent automated trading activity:
```
┌─────────────────────────────────────┐
│ Today's Trading Activity            │
│                                     │
│ Morning Session (9:30 AM):          │
│ • 23 positions opened               │
│ • $4,850.00 deployed                │
│                                     │
│ Afternoon Close (3:30 PM):          │
│ • 23 positions closed               │
│ • P&L: +$127.50                     │
└─────────────────────────────────────┘
```

---

### 4. Settings Presets (Optional Enhancement)

Consider offering preset configurations for different risk profiles:

**Conservative:**
- Max Position: 10%
- Risk Per Trade: 1%
- Max Positions: 20
- Fractional Shares: On

**Balanced:** (default)
- Max Position: 25%
- Risk Per Trade: 2%
- Max Positions: 50
- Fractional Shares: Off

**Aggressive:**
- Max Position: 40%
- Risk Per Trade: 3%
- Max Positions: 100
- Fractional Shares: On

---

### 5. Warnings and Confirmations

#### When Enabling Automation:
```
⚠️ Enable Automated Day Trading?

This portfolio will execute autonomous intraday trades based on ML predictions.
The system will:
• Open positions at 9:30 AM EST daily
• Monitor positions every 10 minutes
• Close all positions at 3:30 PM EST
• Only trade on weekdays

You can disable automation at any time.

[Cancel] [Enable Automation]
```

#### When Disabling Automation (with open positions):
```
⚠️ Cannot Disable - Open Positions

This portfolio has 15 open day trading positions.
Please wait until market close (3:30 PM EST) when all positions will be automatically closed.

Current open positions will be closed today at 3:30 PM EST.

[OK]
```

#### When Disabling Automation (no open positions):
```
⚠️ Disable Automated Day Trading?

This portfolio will stop executing autonomous trades.
You'll need to manage all trades manually.

Your settings will be preserved if you re-enable automation later.

[Cancel] [Disable Automation]
```

---

### 6. Dashboard/Overview Updates

If you have a dashboard showing all portfolios:

**Add filters:**
- Show All
- Show Automated Only
- Show Manual Only

**Summary statistics:**
```
┌─────────────────────────────────┐
│ Portfolio Summary               │
│                                 │
│ Total Portfolios: 5             │
│ • Automated: 2 🤖               │
│ • Manual: 3 👤                  │
│                                 │
│ Total Value: $45,234.50         │
│ Today's Automated P&L: +$342.10 │
└─────────────────────────────────┘
```

---

## Behavioral Notes

### Automated Portfolio Behavior

1. **Morning Session (9:15 AM EST):**
   - System generates recommendations based on ML model
   - Opens positions automatically (up to `dt_max_recommendations`)
   - Uses portfolio-specific settings for position sizing

2. **During Trading Hours (9:30 AM - 3:30 PM EST):**
   - System monitors positions every 10 minutes
   - Automatically closes positions if:
     - Stop-loss hit
     - Target price reached
     - Significant adverse movement

3. **End of Day (3:30 PM EST):**
   - System closes ALL remaining open positions
   - Portfolio returns to 100% cash
   - Performance metrics updated

4. **Daily Snapshot:**
   - Portfolio snapshot created automatically each trading day
   - Tracks daily performance and cumulative returns

### Manual Portfolio Behavior

1. **User Controls Everything:**
   - User creates all transactions via API/UI
   - No autonomous trading

2. **Daily Snapshot:**
   - Portfolio snapshot created automatically each trading day
   - Tracks portfolio value and performance
   - No autonomous position management

---

## Migration Notes for Existing Users

If you have existing users with portfolios:

1. **All existing portfolios default to Manual** (`is_automated=false`)
2. **No automatic conversion** - users must explicitly opt-in
3. **Settings are pre-populated with defaults** when enabling automation
4. **No data loss** - all historical transactions and holdings preserved

---

## Testing Checklist

### UI Testing
- [ ] Can create new portfolio as Automated
- [ ] Can create new portfolio as Manual
- [ ] Can toggle existing portfolio from Manual to Automated
- [ ] Can toggle existing portfolio from Automated to Manual
- [ ] Day trading settings only visible when Automated is selected
- [ ] All settings validate correctly (min/max ranges)
- [ ] Settings persist after save
- [ ] Portfolio list shows correct automation badges
- [ ] Portfolio detail shows correct automation status
- [ ] Warnings display when enabling/disabling automation

### API Testing
- [ ] POST /api/portfolios/ with `is_automated=true` works
- [ ] PATCH /api/portfolios/{id}/ can toggle `is_automated`
- [ ] PATCH /api/portfolios/{id}/ can update day trading settings
- [ ] GET /api/portfolios/ returns new fields
- [ ] Settings validation enforced at API level

### Integration Testing
- [ ] Automated portfolio executes morning trades
- [ ] Manual portfolio does not execute autonomous trades
- [ ] Daily snapshots created for both types
- [ ] Settings changes take effect next trading day
- [ ] Can disable automation and continue manual trading

---

## Example User Flows

### Flow 1: Create Automated Portfolio

1. User clicks "Create Portfolio"
2. Fills in name, description, exchange
3. Selects "Automated Day Trading" mode
4. Adjusts settings:
   - Max Position: 20%
   - Risk Per Trade: 1.5%
   - Max Positions: 30
   - Fractional Shares: On
5. Clicks "Create"
6. System creates portfolio with settings
7. Next trading day at 9:15 AM, system starts trading

### Flow 2: Convert Manual to Automated

1. User views existing manual portfolio
2. Clicks "Enable Automation"
3. Sees confirmation dialog
4. Adjusts default settings or accepts defaults
5. Clicks "Enable Automation"
6. Portfolio shows "🤖 Automated" badge
7. Settings displayed in portfolio detail
8. Next trading day at 9:15 AM, system starts trading

### Flow 3: Convert Automated to Manual

1. User views automated portfolio
2. Clicks "Disable Automation"
3. If no open positions: sees confirmation, confirms, automation disabled
4. If open positions: sees warning to wait until 3:30 PM
5. After positions close: user can disable automation
6. Portfolio shows "👤 Manual" badge
7. User manages trades manually going forward

---

## Design Considerations

### Visual Hierarchy

**Priority 1 (Most Important):**
- Is portfolio Automated or Manual? (badge/icon)
- Current cash balance
- Total P&L

**Priority 2 (Important):**
- Automation settings (when automated)
- Recent trading activity (when automated)

**Priority 3 (Nice to Have):**
- Settings presets
- Historical automation performance
- Detailed trade log

### Mobile Responsiveness

- Use collapsible sections for day trading settings
- Show abbreviated settings in portfolio cards
- Full settings accessible via "Details" or "Edit"

### Accessibility

- Use semantic HTML for form fields
- Provide clear labels and help text
- Ensure toggle switches have proper ARIA labels
- Use color + icon + text for status (not just color)

---

## Questions for UX Team

1. **Preset buttons or custom sliders?** Do you prefer preset risk profiles (Conservative/Balanced/Aggressive) or fully custom sliders?

2. **Settings visibility**: Should day trading settings be visible (read-only) for manual portfolios, or completely hidden?

3. **Automation toggle location**: Should the automation toggle be:
   - In portfolio list view (quick toggle)?
   - Only in edit form?
   - Both places?

4. **Performance visualization**: How should we display automated trading performance?
   - Daily P&L chart?
   - Win rate percentage?
   - Trade history table?

5. **Notification preferences**: Should users receive notifications for:
   - Morning session execution?
   - Stop-loss hits?
   - Daily performance summary?

---

## Technical Notes for Frontend Developers

### State Management

- Portfolio automation state should be managed in your portfolio store/reducer
- Settings changes should trigger immediate API update
- Consider caching settings to avoid repeated API calls

### Real-time Updates

- Morning trading session: 9:15 AM EST
- Position monitoring: Every 10 minutes during market hours
- End of day close: 3:30 PM EST
- Consider websocket/polling for live position updates during trading hours

### Error Handling

Handle these API error cases:
- Invalid setting ranges (400 Bad Request)
- Cannot disable with open positions (409 Conflict)
- Portfolio not found (404 Not Found)
- Insufficient permissions (403 Forbidden)

### Performance

- Day trading settings rarely change - safe to cache
- Portfolio automation status should refresh on page load
- Consider lazy-loading trade history for automated portfolios

---

## Support Resources

- **Backend API Documentation**: See `/api/docs/` for OpenAPI spec
- **Sample API Calls**: See `PORTFOLIO_AUTOMATION_API_EXAMPLES.md` (if needed)
- **Database Schema**: Migration `0026_portfolio_dt_allow_fractional_shares_and_more.py`

For questions or clarification, contact the backend development team.
