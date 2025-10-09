# Day Trading Automation Runbook

## Prerequisites
- Python environment with requirements from `requirements.txt` (`pip install -r requirements.txt`).
- Database populated with `Symbol` and `DaySymbol` history via existing scanners.
- Yahoo Finance (via `yfinance`) network access for live pricing.

## Daily Data Preparation
1. **Feature snapshots** (nightly or ad-hoc):
   ```bash
   python manage.py generate_daytrading_features --start-date 2023-01-01 --end-date 2023-12-31
   ```
   - Use `--date YYYY-MM-DD` for a single trading session.
   - Add `--overwrite` to refresh existing records.

2. **Check snapshot counts**:
   ```sql
   SELECT COUNT(*) FROM zimuabull_featuresnapshot;
   ```

## Model Lifecycle
1. **Training**:
   ```bash
   python manage.py train_daytrading_model --start-date 2023-01-01 --end-date 2024-06-30
   ```
   - Produces artifacts in `artifacts/daytrading/` (`intraday_model.joblib` + metadata).

2. **Backtesting**:
   ```bash
   python manage.py backtest_daytrading --start-date 2023-07-01 --end-date 2024-06-30 --bankroll 20000 --max-positions 5
   ```
   - Review equity curve and metrics from CLI output.

## Autonomous Trading Flow
Celery Beat now orchestrates three key tasks:

| Schedule (UTC) | Task | Description |
| --- | --- | --- |
| 13:15 & 14:15 | `run_morning_trading_session` | Build daily recommendations, execute buys for user #1 portfolio. |
| Every 10 min 13:00–20:59 | `monitor_intraday_positions` | Check stop/target levels, recycle capital into new picks when available. |
| 19:30 & 20:30 | `close_intraday_positions` | Flatten remaining positions ahead of market close. |

### Portfolio Requirements
- Active portfolio for `user_id = 1` with sufficient `cash_balance`.
- Transactions and holdings update automatically through the existing `PortfolioTransaction.save` hooks.

### Operational Checks
- Inspect open intraday positions:
  ```python
  from zimuabull.models import DayTradePosition, DayTradePositionStatus
  DayTradePosition.objects.filter(status=DayTradePositionStatus.OPEN)
  ```
- Review execution logs in Celery worker output.

## Manual Overrides
- Pause automation by disabling Celery beat entries in `core/settings.py`.
- To close positions immediately:
  ```bash
  python manage.py shell <<'PY'
  from zimuabull.daytrading.trading_engine import get_portfolio_for_user, close_all_positions
  portfolio = get_portfolio_for_user(1)
  close_all_positions(portfolio)
  PY
  ```

## Validation
- Run `python3 -m compileall zimuabull/daytrading zimuabull/tasks/day_trading.py` to ensure syntax integrity.
- Execute backtests on rolling windows after each model retraining.
- Monitor `DayTradingRecommendation` and `DayTradePosition` tables for data anomalies.
