from mcp.server.fastmcp import FastMCP
import sqlite3
import pandas as pd
import os
import requests
import json
from datetime import datetime
import pytz
from typing import Dict, List, Any, Optional, Tuple

KST = pytz.timezone('Asia/Seoul')

mcp = FastMCP(
            "ProfitCalcService",  
            host="0.0.0.0", 
            port=8003, 
            )

DB_PATH = 'data/gold_ledger.db'
CSV_PATH = 'data/gold_ledger.csv'

STORAGE_TYPE = 'sqlite'  # 'sqlite' / 'csv'

def get_transactions() -> pd.DataFrame:
    """
    거래 내역 dataframe 형식으로 로드
    """
    if STORAGE_TYPE == 'sqlite':
        if not os.path.exists(DB_PATH):
            return pd.DataFrame(columns=[
                                        'id', 'date', 'transaction_type', 'amount', 
                                        'price', 'total_price', 'note', 'timestamp'
                                        ])
            
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT * FROM transactions ORDER BY date", conn)
        conn.close()
    else:  
        if not os.path.exists(CSV_PATH):
            return pd.DataFrame(columns=[
                                        'id', 'date', 'transaction_type', 'amount', 
                                        'price', 'total_price', 'note', 'timestamp'
                                        ])
            
        df = pd.read_csv(CSV_PATH)
        df = df.sort_values(by='date')
    
    return df

def get_current_gold_price() -> Dict[str, Any]:
    """
    현재 금 시세 정보 조회
    """
    try:
        url = "http://koreagoldx.co.kr/"
        
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()  
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        content_text = soup.get_text()
        
        exchange_rate_pattern = r"환\s*율\s*:\s*([\d,.]+)원/\$"
        gold_international_pattern = r"金국제가\s*:\s*([\d,.]+)\$/T\.oz"
        gold_price_pattern = r"金기준가\s*:\s*([\d,.]+)원/g"
        gold_don_pattern = r"金한돈가\s*:\s*([\d,.]+)원"
        
        exchange_rate_match = re.search(exchange_rate_pattern, content_text)
        gold_international_match = re.search(gold_international_pattern, content_text)
        gold_price_match = re.search(gold_price_pattern, content_text)
        gold_don_match = re.search(gold_don_pattern, content_text)
        
        exchange_rate = float(exchange_rate_match.group(1).replace(',', '')) if exchange_rate_match else None
        gold_international = float(gold_international_match.group(1).replace(',', '')) if gold_international_match else None
        gold_price = float(gold_price_match.group(1).replace(',', '')) if gold_price_match else None
        gold_don = float(gold_don_match.group(1).replace(',', '')) if gold_don_match else None
        
        change_pattern = r"金기준가\s*:\s*[\d,.]+원/g\s*([▲▼])"
        change_match = re.search(change_pattern, content_text)
        
        change_symbol = change_match.group(1) if change_match else ''
        change_amount = 0  
        change_percent = 0  
        
        if change_symbol == '▲': change_direction = 'up'
        elif change_symbol == '▼': change_direction = 'down'
        else: change_direction = 'stable'
            
        now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
        
        return {
                "timestamp": now,
                "price_krw": gold_price,
                "price_don": gold_don,
                "price_international": gold_international,
                "exchange_rate": exchange_rate,
                "change_direction": change_direction,
                "change_amount": change_amount,
                "change_percent": change_percent,
                "unit": "원/g",
                "source": "한국금거래소",
                "status": "success"
                }
    except Exception as e:
        logging.error(f"get_current_gold_price Error : {str(e)}")
        
        return {
                "timestamp": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"),
                "status": "error",
                "message": str(e)
                }

def calculate_average_price(transactions: pd.DataFrame):
    """
    평균 매수 단가, 총 보유량 계산
    """
    if transactions.empty:
        return 0.0, 0.0
    
    buy_txs = transactions[transactions['transaction_type'] == 'buy']
    sell_txs = transactions[transactions['transaction_type'] == 'sell']
    
    total_buy_amount = buy_txs['amount'].sum()
    total_buy_price = buy_txs['total_price'].sum()
    
    total_sell_amount = sell_txs['amount'].sum()
    
    current_holding = total_buy_amount - total_sell_amount
    
    if current_holding <= 0:
        return 0.0, 0.0
    
    remaining_amount = current_holding
    remaining_cost = 0.0
    
    buy_txs_sorted = buy_txs.sort_values(by='date')
    
    for _, tx in buy_txs_sorted.iterrows():
        if remaining_amount <= 0:
            break
            
        amount = tx['amount']
        price = tx['price']
        
        remaining_from_tx = amount
        
        for _, sell_tx in sell_txs[sell_txs['date'] > tx['date']].iterrows():
            if remaining_from_tx <= 0:
                break
                
            sell_amount = sell_tx['amount']
            remaining_from_tx -= min(remaining_from_tx, sell_amount)
        
        amount_to_consider = min(remaining_amount, remaining_from_tx)
        if amount_to_consider > 0:
            remaining_cost += amount_to_consider * price
            remaining_amount -= amount_to_consider
    
    average_price = remaining_cost / current_holding if current_holding > 0 else 0.0
    
    return average_price, current_holding

def calculate_realized_profit(transactions: pd.DataFrame):
    """
    실현 손익 계산
    """
    if transactions.empty:
        return 0.0
    
    realized_profit = 0.0
    
    buy_queue = []
    
    transactions_sorted = transactions.sort_values(by='date')
    
    for _, tx in transactions_sorted.iterrows():
        if tx['transaction_type'] == 'buy':
            buy_queue.append({
                            'amount': tx['amount'],
                            'price': tx['price']
                            })
        else:  
            sell_amount = tx['amount']
            sell_price = tx['price']
            
            while sell_amount > 0 and buy_queue:
                buy_tx = buy_queue[0]
                
                amount_to_process = min(sell_amount, buy_tx['amount'])
                
                profit = amount_to_process * (sell_price - buy_tx['price'])
                realized_profit += profit
                
                sell_amount -= amount_to_process
                buy_tx['amount'] -= amount_to_process
                
                if buy_tx['amount'] <= 0:
                    buy_queue.pop(0)
    
    return realized_profit

@mcp.tool()
async def calculate_portfolio_summary():
    """
    요약
    """
    try:
        transactions = get_transactions()
        
        current_price = get_current_gold_price()
        
        avg_price, holding_amount = calculate_average_price(transactions)
        
        realized_profit = calculate_realized_profit(transactions)
        
        unrealized_profit = holding_amount * (current_price - avg_price) if holding_amount > 0 else 0.0
        
        total_profit = realized_profit + unrealized_profit
        
        profit_rate = (current_price / avg_price - 1) * 100 if avg_price > 0 else 0.0
        
        total_investment = holding_amount * avg_price if holding_amount > 0 else 0.0
        
        current_value = holding_amount * current_price if holding_amount > 0 else 0.0
        
        return {
                "timestamp": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"),
                "holding_amount": round(holding_amount, 2),  # 보유량 (g)
                "avg_price": round(avg_price, 2),  # 평균 매수 단가 (원/g)
                "current_price": current_price,  # 현재 시세 (원/g)
                "unrealized_profit": round(unrealized_profit, 2),  # 미실현 손익 (원)
                "realized_profit": round(realized_profit, 2),  # 실현 손익 (원)
                "total_profit": round(total_profit, 2),  # 총 손익 (원)
                "profit_rate": round(profit_rate, 2),  # 수익률 (%)
                "total_investment": round(total_investment, 2),  # 총 투자 금액 (원)
                "current_value": round(current_value, 2),  # 현재 시장 가치 (원)
                "status": "success"
                }
    except Exception as e:
        return {
                "timestamp": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"),
                "status": "error",
                "message": f"포트폴리오 계산 중 오류 발생: {str(e)}"
                }

@mcp.tool()
async def calculate_transaction_profit(transaction_id):
    """
    특정 거래 손익 계산
    """
    try:
        transactions = get_transactions()
        
        transaction = transactions[transactions['id'] == transaction_id]
        
        if transaction.empty:
            return {
                    "status": "error",
                    "message": f"ID {transaction_id}에 해당하는 거래를 찾을 수 없습니다."
                    }
        
        transaction = transaction.iloc[0]
        
        if transaction['transaction_type'] != 'sell':
            return {
                    "status": "success",
                    "message": "해당 거래는 매도 거래가 아니라 손익을 계산할 수 없습니다.",
                    "transaction": json.loads(transaction.to_json())
                    }
        
        previous_buy_txs = transactions[
                                        (transactions['transaction_type'] == 'buy') & 
                                        (transactions['date'] < transaction['date'])
                                        ]
        
        previous_sell_txs = transactions[
                                        (transactions['transaction_type'] == 'sell') & 
                                        (transactions['date'] < transaction['date'])
                                        ]
        
        total_previous_buy = previous_buy_txs['amount'].sum()
        
        total_previous_sell = previous_sell_txs['amount'].sum()
        
        previous_holding = total_previous_buy - total_previous_sell
        
        if transaction['amount'] > previous_holding:
            return {
                    "status": "error",
                    "message": "매도량이 이전 보유량보다 많습니다. 유효하지 않은 거래입니다."
                    }
        
        sell_amount = transaction['amount']
        
        sell_price = transaction['price']
        
        buy_queue = []
        for _, buy_tx in previous_buy_txs.sort_values(by='date').iterrows():
            processed_amount = 0
            for _, prev_sell in previous_sell_txs[previous_sell_txs['date'] > buy_tx['date']].iterrows():
                processed_amount += min(buy_tx['amount'] - processed_amount, prev_sell['amount'])
                if processed_amount >= buy_tx['amount']:
                    break
            
            remaining = buy_tx['amount'] - processed_amount
            if remaining > 0:
                buy_queue.append({
                                'amount': remaining,
                                'price': buy_tx['price'],
                                'date': buy_tx['date']
                                })
        
        profit = 0.0
        cost_basis = 0.0
        matched_buys = []
        
        remaining_sell = sell_amount
        
        for buy in buy_queue:
            if remaining_sell <= 0:
                break
                
            amount_from_this_buy = min(remaining_sell, buy['amount'])
            cost_from_this_buy = amount_from_this_buy * buy['price']
            revenue_from_this_buy = amount_from_this_buy * sell_price
            profit_from_this_buy = revenue_from_this_buy - cost_from_this_buy
            
            profit += profit_from_this_buy
            cost_basis += cost_from_this_buy
            
            matched_buys.append({
                                'date': buy['date'],
                                'amount': amount_from_this_buy,
                                'price': buy['price'],
                                'cost': cost_from_this_buy
                                })
            
            remaining_sell -= amount_from_this_buy
        
        avg_buy_price = cost_basis / sell_amount if sell_amount > 0 else 0
        profit_rate = ((sell_price / avg_buy_price) - 1) * 100 if avg_buy_price > 0 else 0
        
        return {
                "status": "success",
                "transaction_id": transaction_id,
                "sell_date": transaction['date'],
                "sell_amount": sell_amount,
                "sell_price": sell_price,
                "sell_total": sell_amount * sell_price,
                "cost_basis": round(cost_basis, 2),
                "profit": round(profit, 2),
                "profit_rate": round(profit_rate, 2),
                "matched_buys": matched_buys
                }
    except Exception as e:
        return {
                "status": "error",
                "message": f"Error calculate_transaction_profit: {str(e)}"
                }

if __name__ == "__main__":
    print("ProfitCalcServer 시작 중...")
    # mcp.run(transport="sse") # remote 방식
    mcp.run(transport="stdio") # local 방식 