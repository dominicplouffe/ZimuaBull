# Day Trading Overhaul Plan

## 1. Data & Feature Engineering
- **Audit**: Validate historical coverage of `DaySymbol`, `DayPrediction`, `Symbol.latest_price`, and `MarketIndexData`. Identify missing dates, exchanges, and stale indicators.
- **New tables**:
  - `IntradaySnapshot`: capture open/high/low/close/volume at 5–15 minute intervals (extensible for live monitoring).
  - `FeatureSnapshot`: denormalized daily feature set per symbol, timestamped pre-market.
- **Feature set** (available before market open):
  - Price-based: prior-day return, 5/10/20-day momentum, overnight gap %, ATR(14), rolling volatility (std of returns), distance from 20/50-day SMA.
  - Volume/liquidity: average dollar volume (5/20-day), volume percentile, float turnover.
  - Market/sector context: index returns (`MarketIndexData`), sector ETF overnight gap, breadth indicators, VIX proxy.
  - Event flags: earnings (external source), news sentiment (future), corporate actions.
- **Pipelines**:
  - Nightly Celery task to build `FeatureSnapshot` for all tradable symbols.
  - Real-time task to update `IntradaySnapshot` at market open/close (and optionally intraday).

## 2. Labeling & Modeling
- **Label definition**: intraday target `return = (close_t - open_t) / open_t`, realized strictly same-day. Additional labels: max adverse excursion (from open to day low) and max favorable excursion (open to day high) for risk assessment.
- **Dataset**: join `FeatureSnapshot` with future open/close from `DaySymbol`. Exclude days with missing data or abnormal trading halts.
- **Modeling approach**:
  - Baseline classifiers: logistic regression, gradient boosting (XGBoost/LightGBM) predicting positive risk-adjusted returns.
  - Regression alternative: forecast expected intraday return, penalize high drawdowns.
  - Walk-forward cross-validation (monthly/quarterly folds). Metrics: precision @k, cumulative return, hit rate, max drawdown.
- **Model management**:
  - Store trained models (joblib) with metadata.
  - Track feature importance & drift; retrain weekly/monthly depending on performance.

## 3. Trading & Portfolio Automation
- **Workflow**:
  1. 09:15 EST: load portfolio (user #1), fetch cash, latest features, run model inference, select 1–5 symbols satisfying liquidity & risk filters.
  2. Position sizing: bankroll × risk budget / (ATR × dollar volatility). Cap 25–30% per symbol, enforce diversification by sector.
  3. Generate trades via `PortfolioTransaction`:
     - Submit market-on-open equivalent (simulate via latest pre-open price if true market orders unavailable).
  4. Monitor positions: intraday task checks price feed every N minutes. If price hits stop/target, execute sell/buy adjustments.
  5. 15:30 EST: flatten positions, update holdings, log performance metrics.
- **Scheduling**: Use Celery beat or APScheduler:
  - `generate_day_trades` (09:15 EST)
  - `monitor_trades` (09:30–15:30 every 5/10 min)
  - `close_positions` (15:30 EST)
- **Data sources**: integrate reliable intraday pricing API (Polygon, IEX Cloud). Design interface allowing fallback to Yahoo Finance for EOD.
- **Risk controls**:
  - Skip trading if market gap < -1% or volatility spike (e.g., VIX > threshold).
  - Hard stop-loss market orders; trailing stop optional.
  - Daily capital at risk cap (e.g., 10% of bankroll).

## 4. Backtesting & Evaluation
- **Simulator**:
  - Replay historical sessions using open/high/low/close data.
  - Apply slippage & fees assumptions.
  - Model intraday stop/target using high/low; assume worst-case fill to stay conservative.
- **Metrics**: CAGR, Sharpe, max drawdown, win rate, average gain/loss, exposure. Compare vs baseline strategies and index.
- **Reporting**:
  - Persist daily trade logs.
  - Dashboard/API endpoint summarizing performance.
  - Alerts for degrading metrics or model drift.

## 5. Implementation Phases
1. **Foundation**: create feature/label pipeline scripts, ensure data integrity.
2. **Modeling**: build training module, save baseline model, expose inference service.
3. **Backtester**: develop simulator & evaluation notebook/CLI command.
4. **Automation**: integrate with portfolios, schedule tasks, add monitoring endpoints.
5. **QA**: unit/integration tests, dry-run in paper trading mode, document operations.

## 6. Open Questions
- Preferred intraday data vendor & rate limits?
- Commission/slippage assumptions?
- Are partial-day holidays handled?
- Should automation pause on earnings or macro events?

