"""
Serializers for Portfolio Transaction system.
"""

from rest_framework import serializers
from .models import Portfolio, PortfolioTransaction, PortfolioHolding, Symbol
from decimal import Decimal


class PortfolioTransactionSerializer(serializers.ModelSerializer):
    """Serializer for portfolio transactions"""
    symbol_ticker = serializers.SerializerMethodField()
    exchange_code = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()

    class Meta:
        model = PortfolioTransaction
        fields = [
            'id', 'portfolio', 'symbol', 'symbol_ticker', 'exchange_code',
            'transaction_type', 'quantity', 'price', 'amount', 'total_amount',
            'transaction_date', 'notes', 'strike_price', 'expiration_date',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_symbol_ticker(self, obj):
        return obj.symbol.symbol if obj.symbol else None

    def get_exchange_code(self, obj):
        return obj.symbol.exchange.code if obj.symbol else None

    def get_total_amount(self, obj):
        if obj.transaction_type in ['DEPOSIT', 'WITHDRAWAL']:
            return float(obj.amount)
        return float(obj.quantity * obj.price)


class PortfolioTransactionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating transactions with validation"""
    symbol_ticker = serializers.CharField(write_only=True, required=False, allow_blank=True)
    exchange_code = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = PortfolioTransaction
        fields = [
            'portfolio', 'symbol_ticker', 'exchange_code',
            'transaction_type', 'quantity', 'price', 'amount', 'transaction_date',
            'notes', 'strike_price', 'expiration_date'
        ]

    def validate(self, data):
        """Validate transaction"""
        portfolio = data['portfolio']
        transaction_type = data['transaction_type']

        # Handle DEPOSIT and WITHDRAWAL (cash-only transactions)
        if transaction_type in ['DEPOSIT', 'WITHDRAWAL']:
            if 'amount' not in data or not data['amount']:
                raise serializers.ValidationError({
                    'amount': ['Amount is required for DEPOSIT/WITHDRAWAL transactions']
                })

            # Validate withdrawal doesn't exceed cash balance
            if transaction_type == 'WITHDRAWAL':
                if data['amount'] > portfolio.cash_balance:
                    raise serializers.ValidationError({
                        'amount': [
                            f"Insufficient funds. Cannot withdraw ${data['amount']:.2f}, only have ${portfolio.cash_balance:.2f} in cash"
                        ]
                    })

            # Remove symbol fields for cash transactions
            data.pop('symbol_ticker', None)
            data.pop('exchange_code', None)
            data['symbol'] = None
            data['quantity'] = 0
            data['price'] = 0

            return data

        # Handle BUY/SELL (stock transactions - require symbol)
        if not data.get('symbol_ticker') or not data.get('exchange_code'):
            raise serializers.ValidationError({
                'symbol_ticker': ['Symbol and exchange are required for BUY/SELL transactions']
            })

        # Get symbol
        try:
            from .models import Exchange
            exchange = Exchange.objects.get(code=data['exchange_code'])
            symbol = Symbol.objects.get(symbol=data['symbol_ticker'], exchange=exchange)
            data['symbol'] = symbol
        except (Exchange.DoesNotExist, Symbol.DoesNotExist):
            raise serializers.ValidationError(
                f"Symbol {data['symbol_ticker']}:{data['exchange_code']} not found"
            )

        quantity = data['quantity']
        price = data['price']
        total_amount = quantity * price

        # Validate BUY transaction
        if transaction_type == 'BUY':
            if total_amount > portfolio.cash_balance:
                raise serializers.ValidationError({
                    'non_field_errors': [
                        f"Insufficient funds. Need ${total_amount:.2f} but only have ${portfolio.cash_balance:.2f} in cash"
                    ]
                })

        # Validate SELL transaction
        elif transaction_type == 'SELL':
            try:
                holding = PortfolioHolding.objects.get(
                    portfolio=portfolio,
                    symbol=symbol,
                    status='ACTIVE'
                )
                if quantity > holding.quantity:
                    raise serializers.ValidationError({
                        'quantity': [
                            f"Cannot sell {quantity} shares. You only own {holding.quantity} shares"
                        ]
                    })
            except PortfolioHolding.DoesNotExist:
                raise serializers.ValidationError({
                    'non_field_errors': [
                        f"You don't own any shares of {symbol.symbol} to sell"
                    ]
                })

        # Remove temporary fields
        del data['symbol_ticker']
        del data['exchange_code']

        return data


class PortfolioWithCashSerializer(serializers.ModelSerializer):
    """Portfolio serializer that includes cash balance and holdings"""
    initial_balance = serializers.DecimalField(
        max_digits=15, decimal_places=2, write_only=True, required=False, default=10000
    )
    cash_balance = serializers.SerializerMethodField()
    holdings_value = serializers.SerializerMethodField()
    total_value = serializers.SerializerMethodField()
    holdings_count = serializers.SerializerMethodField()

    class Meta:
        model = Portfolio
        fields = [
            'id', 'name', 'description', 'exchange',
            'initial_balance', 'cash_balance', 'holdings_value', 'total_value', 'holdings_count',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def create(self, validated_data):
        """Create portfolio with initial balance"""
        initial_balance = validated_data.pop('initial_balance', Decimal('10000'))
        portfolio = Portfolio.objects.create(
            cash_balance=0,  # Start at 0, DEPOSIT transaction will add the amount
            **validated_data
        )

        # Create initial DEPOSIT transaction to track the starting balance
        # The transaction's save() method will automatically add this amount to cash_balance
        PortfolioTransaction.objects.create(
            portfolio=portfolio,
            transaction_type='DEPOSIT',
            amount=initial_balance,
            transaction_date=portfolio.created_at.date(),
            notes=f"Initial deposit of ${initial_balance}"
        )

        return portfolio

    def get_cash_balance(self, obj):
        return float(obj.cash_balance)

    def get_holdings_value(self, obj):
        return obj.total_invested()

    def get_total_value(self, obj):
        return obj.current_value()

    def get_holdings_count(self, obj):
        return obj.holdings.filter(status='ACTIVE').count()
