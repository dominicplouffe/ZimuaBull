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
Celery Beat now orchestrates the end-to-end workflow:

| Schedule (UTC) | Task | Description |
| --- | --- | --- |
| 11:30 (Mon–Fri) | `generate_daily_feature_snapshots` | Refresh feature snapshots for the current trading session. |
| 13:15 & 14:15 (Mon–Fri) | `run_morning_trading_session` | Build recommendations and execute entries for user #1. |
| Every 10 min 13:00–20:59 (Mon–Fri) | `monitor_intraday_positions` | Track stops/targets and recycle freed capital into new picks. |
| 19:30 & 20:30 (Mon–Fri) | `close_intraday_positions` | Flatten any remaining positions before the market close. |
| 21:30 (Mon–Fri) | `complete_daily_feature_labels` | Populate labels/realized returns once official closes are in. |
| 21:45 (Mon–Fri) | `daily_trading_health_check` | Flag open positions, orphan recs, or missing labels. |
| 22:00 (Mon–Fri) | `daily_performance_report` | Summarize intraday PnL and win rate for the session. |
| 22:00 (Sun) | `weekly_model_refresh` | Retrain the model on the latest data and run an in-sample backtest. |

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
  from zimuabull.daytrading.trading_engine import get_portfolios_for_user, close_all_positions
  for portfolio in get_portfolios_for_user(1):
      close_all_positions(portfolio)
  PY
  ```
- To delete a portfolio and all related data:
  ```bash
  python manage.py delete_portfolio <portfolio_id> --user-id <owner_id>
  ```

## Validation
- Run `python3 -m compileall zimuabull/daytrading zimuabull/tasks/day_trading.py` to ensure syntax integrity.
- Execute backtests on rolling windows after each model retraining.
- Monitor `DayTradingRecommendation` and `DayTradePosition` tables for data anomalies.
