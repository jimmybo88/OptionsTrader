from ib_insync import *
from ib_insync import util
from datetime import datetime
import time

def connect_to_ib():
    print("Connecting to IB...")
    start_time = time.time()
    try:
        ib = IB()
        ib.connect('127.0.0.1', 7497, clientId=1)  # replace with your own IP and port
        ib.reqMarketDataType(3)  # delayed data??
        print(f"Connected to IB in {time.time() - start_time} seconds")
        return ib
    except Exception as e:
        print(f"Error connecting to IB: {e}")
        return None

def find_contract_closest_to_dte(ib, symbols, right, target_dte, days_min, days_max):
    overall_closest_contract = None
    overall_closest_dte_diff = float('inf')

    for symbol in symbols:
        print(f"Finding contract closest to DTE for {symbol}...")
        start_time = time.time()
        try:
            contracts = ib.reqContractDetails(Option(symbol, exchange='SMART', right=right))

            closest_contract = None
            closest_dte_diff = float('inf')

            for contract in contracts:
                dte = (contract.contract.lastTradeDateOrContractMonth - datetime.now().date()).days

                if days_min <= dte <= days_max:
                    dte_diff = abs(dte - target_dte)

                    if dte_diff < closest_dte_diff:
                        closest_contract = contract.contract
                        closest_dte_diff = dte_diff
                        print(f"New closest contract: {contract.contract} with DTE: {dte} and DTE diff: {dte_diff}")

            print(f"Found closest contract for {symbol} in {time.time() - start_time} seconds")

            if closest_dte_diff < overall_closest_dte_diff:
                overall_closest_contract = closest_contract
                overall_closest_dte_diff = closest_dte_diff
        except Exception as e:
            if 'connection' in str(e).lower():
                print("Connection error occurred while finding closest contract.")
            else:
                print(f"Error finding closest contract: {e}")

    return overall_closest_contract

def find_strike(ib, contract, target_delta):
    print("Finding strike...")
    start_time = time.time()
    chains = ib.reqSecDefOptParams(underlyingSymbol=contract.symbol,
                                   futFopExchange='',
                                   underlyingSecType=contract.secType,
                                   underlyingConId=contract.conId)

    chain = next(c for c in chains if c.tradingClass == contract.symbol and c.exchange == contract.exchange)

    # Get the option chain for the contract
    options = [Option(contract.symbol, contract.lastTradeDateOrContractMonth, strike, 'P', 'SMART')
               for strike in chain.strikes]

    ib.qualifyContracts(*options)

    tickers = ib.reqTickers(*options)

    # Wait for the delta to be available
    ib.sleep(1)

    # Find the option with the delta closest to the target
    closest_option = None
    closest_delta_diff = float('inf')

    for ticker in tickers:
        if ticker.modelGreeks:
            delta = ticker.modelGreeks.delta
            delta_diff = abs(delta - target_delta)

            if delta_diff < closest_delta_diff:
                closest_option = ticker.contract
                closest_delta_diff = delta_diff

    print(f"Found strike in {time.time() - start_time} seconds")
    return closest_option

def place_order(ib, contract):
    # Request market data for the contract
    print("Requesting market data...")
    start_time = time.time()
    ticker = ib.reqMktData(contract)

    # Wait for the ask price to be available
    ib.sleep(1)

    # Get the last ask price
    limit_price = ticker.ask
    print(f"Last ask price for {contract}: {limit_price}")
    print(f"Time taken to get market data: {time.time() - start_time} seconds")

    # Define the bracket order
    print("Placing order...")
    start_time = time.time()
    bracket = ib.bracketOrder(
        'SELL',  # action
        -1,  # quantity
        limit_price,  # limit price
        limit_price * 0.40,  # take-profit price
        limit_price * 3  # stop-loss price
    )

    for o in bracket:
        trade = ib.placeOrder(contract, o)
        ib.sleep(1)
        print(f"Placed order: {trade.order}")
        print(f"Contract details: Symbol: {contract.symbol}, Strike: {contract.strike}, Expiry: {contract.lastTradeDateOrContractMonth}")
        print(f"Order details: Action: {trade.order.action}, Quantity: {trade.order.totalQuantity}, Limit price: {trade.order.lmtPrice}")
    print(f"Time taken to place order: {time.time() - start_time} seconds")

def main():
    print("Starting main function...")
    start_time = time.time()

    ib = connect_to_ib()

    if ib is None:
        print("Failed to connect to IB")
        return


    symbols = ['SPY', 'SPYW']
    
    # Find the contract closest to 90 days to expiry between 75 and 105 days to expiry
    contract = find_contract_closest_to_dte(ib, symbols, 'P', 90, 75, 105)

    # Find a strike price
    strike = find_strike(ib, contract, -0.15)

    # Update the contract with the found strike price
    contract.strike = strike

    # Place the order
    place_order(ib, contract)

    # Disconnect from IB
    ib.disconnect()

    print(f"Time taken for main function: {time.time() - start_time} seconds")

if __name__ == '__main__':
    main()
