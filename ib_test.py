from ib_insync import *

# Connect to IB Gateway (adjust port/clientId if needed)
ib = IB()
ib.connect('192.168.0.85', 4001, clientId=1)

contract = Stock('INTC', 'SMART', 'USD', primaryExchange='NASDAQ')

order = MarketOrder('BUY', 1.25)

trade = ib.placeOrder(contract, order)

# Wait until the order is filled or cancelled
ib.sleep(2)
print(f"Order Status: {trade.orderStatus.status}")
print(f"Filled Quantity: {trade.orderStatus.filled}")

# Disconnect when done
ib.disconnect()