from pathlib import Path

# Feature engineering configuration
FEATURE_VERSION = "v1"
MIN_HISTORY_DAYS = 40  # we need at least this many observations before a trade date
LOOKBACK_WINDOWS = [1, 3, 5, 10, 20]
VOLUME_WINDOWS = [5, 10, 20]
VOLATILITY_WINDOW = 10
ATR_WINDOW = 14

# Model artefact storage
MODEL_DIR = Path("artifacts") / "daytrading"
MODEL_FILENAME = "intraday_model.joblib"
MODEL_METADATA_FILENAME = "intraday_model_meta.json"

# Training parameters
TRAIN_START_DATE = None  # allows CLI callers to override
MIN_TRAINING_ROWS = 500
TARGET_COLUMN = "intraday_return"

# Backtest defaults
BACKTEST_TRANSACTION_COST_BPS = 5  # 0.05% cost per trade
BACKTEST_SLIPPAGE_BPS = 5
MAX_RECOMMENDATIONS = 5
DEFAULT_BANKROLL = 10000

# Autonomous trading configuration
AUTONOMOUS_USER_ID = 1
MAX_POSITION_PERCENT = 0.25
PER_TRADE_RISK_FRACTION = 0.02
MONITOR_INTERVAL_MINUTES = 10
