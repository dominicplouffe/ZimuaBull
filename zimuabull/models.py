from django.db import models


class DaySymbolChoice(models.TextChoices):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    STRONG_BUY = "STRONG_BUY"
    STRONG_SELL = "STRONG_SELL"
    NA = "NA"


class CloseBucketChoice(models.TextChoices):
    UP = "UP"
    DOWN = "DOWN"
    NA = "NA"


class DayPredictionChoice(models.TextChoices):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    NEUTRAL = "NEUTRAL"


# Create your models here.
class Exchange(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, null=True, blank=True)
    country = models.CharField(max_length=100)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "{} - {}".format(self.name, self.country)

    unique_together = ("name", "country")


class Symbol(models.Model):
    name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=10)
    exchange = models.ForeignKey(Exchange, on_delete=models.CASCADE)

    # Classification
    sector = models.CharField(max_length=100, blank=True, null=True)  # e.g., "Technology", "Healthcare"
    industry = models.CharField(max_length=100, blank=True, null=True)  # e.g., "Software", "Biotechnology"

    # Current metrics
    last_open = models.FloatField()
    last_close = models.FloatField()
    last_volume = models.IntegerField()
    obv_status = models.CharField(
        max_length=20, choices=DaySymbolChoice.choices, default=DaySymbolChoice.NA
    )
    thirty_close_trend = models.FloatField()
    close_bucket = models.CharField(
        max_length=20, choices=CloseBucketChoice.choices, default=CloseBucketChoice.NA
    )
    accuracy = models.FloatField(null=True, blank=True)

    # Real-time price tracking
    latest_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    price_updated_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "{} - {} = {}".format(self.name, self.symbol, self.exchange.name)

    unique_together = ("symbol", "exchange")

    def update_trading_signal(self):
        """
        Calculate and update the trading signal (obv_status) for this symbol
        based on latest prediction and technical indicators.

        Returns:
            str: The new trading signal
        """
        from .signals import calculate_trading_signal
        new_signal = calculate_trading_signal(self)
        self.obv_status = new_signal
        self.save(update_fields=['obv_status', 'updated_at'])
        return new_signal

    def get_signal_explanation(self):
        """
        Get detailed explanation of the current trading signal.

        Returns:
            dict: Signal details and explanation
        """
        from .signals import get_signal_explanation
        return get_signal_explanation(self)


class DaySymbol(models.Model):
    symbol = models.ForeignKey(Symbol, on_delete=models.CASCADE)
    date = models.DateField()
    open = models.FloatField()
    high = models.FloatField()
    low = models.FloatField()
    adj_close = models.FloatField()
    close = models.FloatField()
    volume = models.IntegerField()
    obv = models.BigIntegerField()
    obv_signal = models.IntegerField()
    obv_signal_sum = models.IntegerField()
    price_diff = models.FloatField()
    thirty_price_diff = models.FloatField()
    thirty_close_trend = models.FloatField()
    status = models.CharField(
        max_length=20, choices=DaySymbolChoice.choices, default=DaySymbolChoice.NA
    )

    # Technical indicators
    rsi = models.FloatField(null=True, blank=True)  # Relative Strength Index (0-100)
    macd = models.FloatField(null=True, blank=True)  # MACD line
    macd_signal = models.FloatField(null=True, blank=True)  # Signal line
    macd_histogram = models.FloatField(null=True, blank=True)  # MACD - Signal

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "{} - {}".format(self.symbol, self.date)

    unique_together = ("symbol", "date")

    @staticmethod
    def calculate_rsi(symbol, date, period=14):
        """
        Calculate Relative Strength Index (RSI) for a given symbol and date.

        RSI = 100 - (100 / (1 + RS))
        where RS = Average Gain / Average Loss over period

        Args:
            symbol: Symbol instance
            date: Date to calculate RSI for
            period: Lookback period (default 14)

        Returns:
            float: RSI value between 0-100, or None if insufficient data
        """
        # Get historical data including current date
        historical = DaySymbol.objects.filter(
            symbol=symbol,
            date__lte=date
        ).order_by('-date')[:(period + 1)]

        if len(historical) < period + 1:
            return None

        # Reverse to get oldest first
        historical = list(reversed(historical))

        # Calculate price changes
        gains = []
        losses = []

        for i in range(1, len(historical)):
            change = historical[i].close - historical[i-1].close
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))

        # Calculate average gain and loss
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return round(rsi, 2)

    @staticmethod
    def calculate_macd(symbol, date, fast=12, slow=26, signal=9):
        """
        Calculate MACD (Moving Average Convergence Divergence).

        MACD Line = EMA(fast) - EMA(slow)
        Signal Line = EMA(MACD, signal period)
        Histogram = MACD - Signal

        Args:
            symbol: Symbol instance
            date: Date to calculate MACD for
            fast: Fast EMA period (default 12)
            slow: Slow EMA period (default 26)
            signal: Signal line EMA period (default 9)

        Returns:
            tuple: (macd, signal_line, histogram) or (None, None, None) if insufficient data
        """
        # Need enough data for slow EMA plus signal EMA
        required_days = slow + signal

        historical = DaySymbol.objects.filter(
            symbol=symbol,
            date__lte=date
        ).order_by('-date')[:required_days]

        if len(historical) < required_days:
            return None, None, None

        # Reverse to get oldest first
        historical = list(reversed(historical))
        closes = [day.close for day in historical]

        # Calculate EMAs
        def calculate_ema(prices, period):
            """Calculate Exponential Moving Average"""
            multiplier = 2 / (period + 1)
            ema = sum(prices[:period]) / period  # Start with SMA

            for price in prices[period:]:
                ema = (price * multiplier) + (ema * (1 - multiplier))

            return ema

        # Calculate fast and slow EMAs
        fast_ema = calculate_ema(closes, fast)
        slow_ema = calculate_ema(closes, slow)

        # MACD line
        macd_line = fast_ema - slow_ema

        # For signal line, we need MACD values over signal period
        # This is simplified - in production you'd want to calculate signal from all MACD values
        # For now, using MACD line itself as approximation
        signal_line = macd_line  # Simplified - should be EMA of MACD values

        # Histogram
        histogram = macd_line - signal_line

        return round(macd_line, 4), round(signal_line, 4), round(histogram, 4)


class DayPrediction(models.Model):
    symbol = models.ForeignKey(Symbol, on_delete=models.CASCADE)
    date = models.DateField()
    buy_price = models.FloatField()
    sell_price = models.FloatField()
    diff = models.FloatField()
    prediction = models.CharField(
        max_length=20,
        choices=DayPredictionChoice.choices,
        default=DayPredictionChoice.NEUTRAL,
    )
    buy_date = models.DateField(null=True, blank=True)
    sell_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "{} - {}".format(self.symbol, self.date)

    unique_together = ("symbol", "date")


class Favorite(models.Model):
    symbol = models.ForeignKey(Symbol, on_delete=models.CASCADE)
    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "{} - {}".format(self.symbol, self.user)

    unique_together = ("symbol", "user")


class Portfolio(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    exchange = models.ForeignKey("Exchange", on_delete=models.PROTECT)  # All holdings must be from this exchange
    cash_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)  # Available cash
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "{} - {} ({})".format(self.name, self.user.username, self.exchange.code)

    class Meta:
        unique_together = ("name", "user")
        ordering = ["-created_at"]

    def total_invested(self):
        """Calculate total amount currently invested in holdings (market value of positions)"""
        from decimal import Decimal
        total = Decimal('0')
        for holding in self.holdings.filter(status='ACTIVE'):
            current_price = Decimal(str(holding.symbol.last_close))
            total += current_price * holding.quantity
        return float(total)

    def current_value(self):
        """Calculate current total portfolio value (cash + holdings)"""
        return float(self.cash_balance) + self.total_invested()

    def total_gain_loss(self):
        """Calculate total gain/loss based on transaction history"""
        from decimal import Decimal

        # Get all active holding symbol IDs (these are still open positions)
        active_symbol_ids = set(
            self.holdings.filter(status='ACTIVE').values_list('symbol_id', flat=True)
        )

        # Calculate realized gains from CLOSED positions only
        realized = Decimal('0')
        transactions = self.transactions.all()

        # Track buy cost and sell proceeds for each symbol
        symbol_tracker = {}

        for txn in transactions.order_by('transaction_date'):
            # Skip cash transactions (DEPOSIT/WITHDRAWAL)
            if txn.symbol is None:
                continue

            symbol_id = txn.symbol.id
            if symbol_id not in symbol_tracker:
                symbol_tracker[symbol_id] = {'cost': Decimal('0'), 'proceeds': Decimal('0')}

            if txn.transaction_type == 'BUY':
                symbol_tracker[symbol_id]['cost'] += txn.price * txn.quantity
            elif txn.transaction_type == 'SELL':
                symbol_tracker[symbol_id]['proceeds'] += txn.price * txn.quantity

        # Realized gains = sells - buys, but ONLY for fully closed positions
        for symbol_id, data in symbol_tracker.items():
            if symbol_id not in active_symbol_ids:
                # This position is fully closed, count the realized gain/loss
                realized += data['proceeds'] - data['cost']

        # Add unrealized gains from current holdings
        unrealized = Decimal('0')
        for holding in self.holdings.filter(status='ACTIVE'):
            current_price = Decimal(str(holding.symbol.last_close))
            current_value = current_price * holding.quantity
            cost_basis = holding.average_cost * holding.quantity
            unrealized += current_value - cost_basis

        return float(realized + unrealized)

    def total_gain_loss_percent(self):
        """Calculate total gain/loss (percentage) relative to total capital deployed"""
        from decimal import Decimal

        # Total capital = all BUY transactions
        total_buys = Decimal('0')
        for txn in self.transactions.filter(transaction_type='BUY'):
            total_buys += txn.price * txn.quantity

        if total_buys == 0:
            return 0

        gain_loss = Decimal(str(self.total_gain_loss()))
        return float((gain_loss / total_buys) * 100)


class TransactionType(models.TextChoices):
    BUY = "BUY"  # Buy shares
    SELL = "SELL"  # Sell shares
    DEPOSIT = "DEPOSIT"  # Add cash to portfolio
    WITHDRAWAL = "WITHDRAWAL"  # Remove cash from portfolio
    CALL = "CALL"  # Buy call option (future use)
    PUT = "PUT"  # Buy put option (future use)


class PortfolioTransaction(models.Model):
    """
    Track all portfolio transactions (buys, sells, deposits, withdrawals, options).
    Holdings are derived from BUY/SELL transactions.
    Cash is managed via DEPOSIT/WITHDRAWAL transactions.
    """
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name="transactions")
    symbol = models.ForeignKey(Symbol, on_delete=models.CASCADE, null=True, blank=True)  # Null for cash transactions
    transaction_type = models.CharField(max_length=15, choices=TransactionType.choices)
    quantity = models.DecimalField(max_digits=10, decimal_places=4, default=0)  # 0 for cash transactions
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # 0 for cash transactions
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)  # Direct amount for DEPOSIT/WITHDRAWAL
    transaction_date = models.DateField()
    notes = models.TextField(blank=True, null=True)

    # For options (future use)
    strike_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    expiration_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.transaction_type in ['DEPOSIT', 'WITHDRAWAL']:
            return f"{self.transaction_type} ${self.amount} on {self.transaction_date}"
        return f"{self.transaction_type} {self.quantity} {self.symbol.symbol if self.symbol else 'N/A'} @ {self.price} on {self.transaction_date}"

    class Meta:
        ordering = ["-transaction_date", "-created_at"]
        indexes = [
            models.Index(fields=['portfolio', '-transaction_date']),
            models.Index(fields=['symbol', '-transaction_date']),
        ]

    def total_amount(self):
        """Total transaction amount (quantity * price)"""
        return float(self.quantity * self.price)

    def save(self, *args, **kwargs):
        """Override save to update portfolio cash and holdings"""
        from decimal import Decimal

        is_new = self.pk is None

        # Save the transaction first
        super().save(*args, **kwargs)

        if is_new:
            if self.transaction_type == 'BUY':
                # Deduct cash for buy
                amount = self.quantity * self.price
                self.portfolio.cash_balance -= amount
                self.portfolio.save(update_fields=['cash_balance', 'updated_at'])
                # Update or create holding
                self._update_holding_for_buy()

            elif self.transaction_type == 'SELL':
                # Add cash for sell
                amount = self.quantity * self.price
                self.portfolio.cash_balance += amount
                self.portfolio.save(update_fields=['cash_balance', 'updated_at'])
                # Update holding
                self._update_holding_for_sell()

            elif self.transaction_type == 'DEPOSIT':
                # Add cash to portfolio
                self.portfolio.cash_balance += self.amount
                self.portfolio.save(update_fields=['cash_balance', 'updated_at'])

            elif self.transaction_type == 'WITHDRAWAL':
                # Remove cash from portfolio
                self.portfolio.cash_balance -= self.amount
                self.portfolio.save(update_fields=['cash_balance', 'updated_at'])

    def _update_holding_for_buy(self):
        """Update or create holding after a buy transaction"""
        from decimal import Decimal

        holding, created = PortfolioHolding.objects.get_or_create(
            portfolio=self.portfolio,
            symbol=self.symbol,
            status='ACTIVE',
            defaults={
                'quantity': self.quantity,
                'average_cost': self.price,
                'first_purchase_date': self.transaction_date
            }
        )

        if not created:
            # Update average cost and quantity
            total_cost = (holding.quantity * holding.average_cost) + (self.quantity * self.price)
            total_quantity = holding.quantity + self.quantity
            holding.average_cost = total_cost / total_quantity
            holding.quantity = total_quantity
            holding.save(update_fields=['quantity', 'average_cost', 'updated_at'])

    def _update_holding_for_sell(self):
        """Update holding after a sell transaction"""
        try:
            holding = PortfolioHolding.objects.get(
                portfolio=self.portfolio,
                symbol=self.symbol,
                status='ACTIVE'
            )

            holding.quantity -= self.quantity

            if holding.quantity <= 0:
                # Fully sold - remove holding
                holding.delete()
            else:
                # Partial sell - update quantity
                holding.save(update_fields=['quantity', 'updated_at'])

        except PortfolioHolding.DoesNotExist:
            # Can't sell what you don't have - this should be validated before save
            pass


class HoldingStatus(models.TextChoices):
    ACTIVE = "ACTIVE"  # Currently holding
    SOLD = "SOLD"  # Sold position (deprecated - now tracked via transactions)
    PARTIAL = "PARTIAL"  # Partially sold (deprecated - now tracked via transactions)


class PortfolioHolding(models.Model):
    """
    Represents current holdings in a portfolio.
    Now calculated/updated from PortfolioTransaction records.
    """
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name="holdings")
    symbol = models.ForeignKey(Symbol, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=10, decimal_places=4)  # Current quantity held
    average_cost = models.DecimalField(max_digits=10, decimal_places=2)  # Average cost basis
    first_purchase_date = models.DateField()  # Date of first purchase

    status = models.CharField(
        max_length=20,
        choices=HoldingStatus.choices,
        default=HoldingStatus.ACTIVE
    )

    # Optional: Risk management
    stop_loss_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    target_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "{} - {} shares of {}".format(
            self.portfolio.name,
            self.quantity,
            self.symbol.symbol
        )

    class Meta:
        ordering = ["-first_purchase_date"]
        unique_together = ('portfolio', 'symbol', 'status')

    def cost_basis(self):
        """Total amount paid for this holding"""
        return float(self.average_cost * self.quantity)

    def current_value(self):
        """Current market value of this holding"""
        from decimal import Decimal
        # Use latest_price if available and recent, otherwise fall back to last_close
        price = self.symbol.latest_price if self.symbol.latest_price else Decimal(str(self.symbol.last_close))
        return float(price * self.quantity)

    def gain_loss(self):
        """Absolute gain/loss on this holding"""
        return self.current_value() - self.cost_basis()

    def gain_loss_percent(self):
        """Percentage gain/loss on this holding"""
        cost = self.cost_basis()
        if cost == 0:
            return 0
        return (self.gain_loss() / cost) * 100

    def days_held(self):
        """Number of days this position has been held"""
        from datetime import date as dt_date
        end_date = self.sell_date if self.status == HoldingStatus.SOLD else dt_date.today()
        return (end_date - self.purchase_date).days


class PortfolioSnapshot(models.Model):
    """Daily snapshot of portfolio value for historical tracking"""
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name="snapshots")
    date = models.DateField()
    total_value = models.DecimalField(max_digits=15, decimal_places=2)
    total_invested = models.DecimalField(max_digits=15, decimal_places=2)
    gain_loss = models.DecimalField(max_digits=15, decimal_places=2)
    gain_loss_percent = models.DecimalField(max_digits=8, decimal_places=4)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return "{} - {} (${})".format(self.portfolio.name, self.date, self.total_value)

    class Meta:
        unique_together = ("portfolio", "date")
        ordering = ["-date"]


class Conversation(models.Model):
    """Store LLM conversation history for context and continuity"""
    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    title = models.CharField(max_length=200, blank=True)  # Auto-generated from first message
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.title or 'Untitled'} ({self.created_at.date()})"

    class Meta:
        ordering = ["-updated_at"]


class ConversationMessage(models.Model):
    """Individual messages in a conversation"""
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=20, choices=[
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System')
    ])
    content = models.TextField()
    context_data = models.JSONField(null=True, blank=True)  # Store context used for this message
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.conversation.id} - {self.role}: {self.content[:50]}"

    class Meta:
        ordering = ["created_at"]


class SignalHistory(models.Model):
    """
    Track when trading signals change for symbols.
    Allows LLMs to analyze signal trends and reliability over time.
    """
    symbol = models.ForeignKey(Symbol, on_delete=models.CASCADE, related_name="signal_history")
    date = models.DateField()

    # Previous and new signals
    previous_signal = models.CharField(
        max_length=20,
        choices=DaySymbolChoice.choices,
        null=True,
        blank=True
    )
    new_signal = models.CharField(
        max_length=20,
        choices=DaySymbolChoice.choices
    )

    # Context at time of signal change
    price = models.FloatField()
    volume = models.IntegerField(null=True, blank=True)
    prediction = models.CharField(
        max_length=20,
        choices=DayPredictionChoice.choices,
        null=True,
        blank=True
    )

    # Metadata
    reason = models.TextField(blank=True, null=True)  # Optional explanation
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.symbol.symbol} - {self.date}: {self.previous_signal} -> {self.new_signal}"

    class Meta:
        ordering = ["-date"]
        verbose_name_plural = "Signal histories"
        indexes = [
            models.Index(fields=['symbol', '-date']),
            models.Index(fields=['new_signal', '-date']),
        ]


class MarketIndex(models.Model):
    """
    Track major market indices for benchmark comparison.
    Examples: S&P 500, NASDAQ Composite, Dow Jones, TSX Composite
    """
    name = models.CharField(max_length=100)  # e.g., "S&P 500"
    symbol = models.CharField(max_length=20, unique=True)  # e.g., "^GSPC"
    description = models.TextField(blank=True, null=True)
    country = models.CharField(max_length=100)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.symbol})"

    class Meta:
        ordering = ["name"]


class MarketIndexData(models.Model):
    """
    Daily data for market indices.
    Similar structure to DaySymbol but for indices.
    """
    index = models.ForeignKey(MarketIndex, on_delete=models.CASCADE, related_name="daily_data")
    date = models.DateField()
    open = models.FloatField()
    high = models.FloatField()
    low = models.FloatField()
    close = models.FloatField()
    volume = models.BigIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.index.symbol} - {self.date}"

    class Meta:
        ordering = ["-date"]
        unique_together = ("index", "date")
        indexes = [
            models.Index(fields=['index', '-date']),
        ]


class DayTradingRecommendation(models.Model):
    """
    Track daily trading recommendations for intraday trading.
    Generated each morning, tracks performance by end of day.
    """
    symbol = models.ForeignKey(Symbol, on_delete=models.CASCADE, related_name="day_trade_recommendations")
    recommendation_date = models.DateField()

    # Recommendation details
    rank = models.IntegerField()  # 1-5, where 1 is top pick
    confidence_score = models.FloatField()  # 0-100, composite score
    recommended_allocation = models.DecimalField(max_digits=10, decimal_places=2)  # Dollar amount

    # Price data at recommendation time
    entry_price = models.FloatField()  # Expected entry (previous close or current open)
    target_price = models.FloatField(null=True, blank=True)  # Estimated target
    stop_loss_price = models.FloatField(null=True, blank=True)  # Risk management

    # Scoring breakdown
    signal_score = models.FloatField()  # Trading signal strength (0-20)
    momentum_score = models.FloatField()  # Price momentum (0-20)
    volume_score = models.FloatField()  # Volume analysis (0-20)
    prediction_score = models.FloatField()  # AI prediction alignment (0-20)
    technical_score = models.FloatField()  # RSI/MACD indicators (0-20)

    # Performance tracking (updated end of day)
    actual_high = models.FloatField(null=True, blank=True)
    actual_low = models.FloatField(null=True, blank=True)
    actual_close = models.FloatField(null=True, blank=True)
    actual_return = models.FloatField(null=True, blank=True)  # Percentage return
    hit_target = models.BooleanField(null=True, blank=True)  # Did it reach target?

    # Metadata
    recommendation_reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.recommendation_date} - Rank {self.rank}: {self.symbol.symbol} (Score: {self.confidence_score:.1f})"

    class Meta:
        ordering = ['recommendation_date', 'rank']
        unique_together = ('symbol', 'recommendation_date')
        indexes = [
            models.Index(fields=['-recommendation_date', 'rank']),
            models.Index(fields=['symbol', '-recommendation_date']),
        ]

    def calculate_actual_return(self):
        """Calculate actual return if we have end-of-day data"""
        if self.actual_close and self.entry_price:
            self.actual_return = ((self.actual_close - self.entry_price) / self.entry_price) * 100
            if self.target_price:
                self.hit_target = self.actual_high >= self.target_price
            self.save(update_fields=['actual_return', 'hit_target', 'updated_at'])
