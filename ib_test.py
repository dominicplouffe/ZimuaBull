import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()


from zimuabull.tasks import ib_order_monitor
from zimuabull.tasks import day_trading

if __name__ == "__main__":
    ib_order_monitor.monitor_ib_orders()
    # day_trading.run_morning_trading_session()
    # day_trading.close_intraday_positions()

# from ib_insync import *

# # Connect to IB Gateway (adjust port/clientId if needed)
# ib = IB()
# ib.connect('192.168.0.85', 4002, clientId=1)

# contract = Stock('INTC', 'SMART', 'USD', primaryExchange='NASDAQ')

# order = MarketOrder('BUY', 1.00)

# trade = ib.placeOrder(contract, order)

# # Wait until the order is filled or cancelled
# ib.sleep(2)
# print(f"Order Status: {trade.orderStatus.status}")
# print(f"Filled Quantity: {trade.orderStatus.filled}")

# # Disconnect when done
# ib.disconnect()

# from ib_insync import *

# # Connect to the IB Gateway or TWS
# ib = IB()
# ib.connect('192.168.0.85', 4002, clientId=3)  # 4002 = Gateway, 7497 = TWS

# # Define the contract for Intel stock on NASDAQ
# contract = Stock('INTC', 'SMART', 'USD', primaryExchange='NASDAQ')

# # Request live market data
# ticker = ib.reqMktData(contract)

# # Wait briefly for data to arrive
# ib.sleep(2)

# # Access the market data fields
# print(f"Ask Price: {ticker.ask}")
# print(f"Bid Price: {ticker.bid}")
# print(f"Last Traded Price: {ticker.last}")

# # Disconnect
# ib.disconnect()