from mcp.server.fastmcp import FastMCP
import sqlite3
import pandas as pd
import os
import json
from datetime import datetime
import pytz
from typing import Dict, List, Any, Optional

KST = pytz.timezone('Asia/Seoul')

mcp = FastMCP(
            "LedgerService",  
            host="0.0.0.0",  
            port=8002,  
            )

STORAGE_TYPE = 'sqlite'

DB_PATH = 'data/gold_ledger.db'
CSV_PATH = 'data/gold_ledger.csv'

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

def init_storage():
    """
    db 초기화
    """
    if STORAGE_TYPE == 'sqlite':
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
                        CREATE TABLE IF NOT EXISTS transactions (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            date TEXT NOT NULL,
                            transaction_type TEXT NOT NULL,
                            amount REAL NOT NULL,
                            price REAL NOT NULL,
                            total_price REAL NOT NULL,
                            note TEXT,
                            timestamp TEXT NOT NULL
                        )
                        ''')
        conn.commit()
        conn.close()
    elif STORAGE_TYPE == 'csv':
        if not os.path.exists(CSV_PATH):
            df = pd.DataFrame(columns=[
                                    'id', 'date', 'transaction_type', 'amount', 
                                    'price', 'total_price', 'note', 'timestamp'
                                    ])
                                    df.to_csv(CSV_PATH, index=False)

init_storage()

@mcp.tool()
async def add_transaction(
                        date: str, # 거래 날짜 (YYYY-MM-DD)
                        transaction_type: str, # 거래 유형 ('buy'/'sell')
                        amount: float, # 거래량 (g)
                        price: float, # 단가 (원/g)
                        note: Optional[str] = None
                        ):
    """
    금 거래 내역 추가
    """
    try:
        now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
        
        total_price = amount * price
        
        if STORAGE_TYPE == 'sqlite':
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                            '''
                            INSERT INTO transactions 
                            (date, transaction_type, amount, price, total_price, note, timestamp) 
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            ''',
                            (date, transaction_type, amount, price, total_price, note, now)
                        )
            transaction_id = cursor.lastrowid
            conn.commit()
            conn.close()
        elif STORAGE_TYPE == 'csv':
            df = pd.read_csv(CSV_PATH)
            
            transaction_id = 1 if df.empty else df['id'].max() + 1
            
            new_row = pd.DataFrame([{
                                    'id': transaction_id,
                                    'date': date,
                                    'transaction_type': transaction_type,
                                    'amount': amount,
                                    'price': price,
                                    'total_price': total_price,
                                    'note': note if note else '',
                                    'timestamp': now
                                }])
            
            df = pd.concat([df, new_row], ignore_index=True)
            df.to_csv(CSV_PATH, index=False)
        
        return {
            "status": "success",
            "message": f"{transaction_type} 거래 추가 done",
            "transaction_id": transaction_id,
            "details": {
                        "date": date,
                        "transaction_type": transaction_type,
                        "amount": amount,
                        "price": price,
                        "total_price": total_price,
                        "note": note
                        }
                }
    except Exception as e:
        return {
                "status": "error",
                "message": f"Error add_transaction: {str(e)}"
                }

@mcp.tool()
async def get_transactions(
                            start_date: Optional[str] = None, # 시작 날짜 (YYYY-MM-DD)
                            end_date: Optional[str] = None, # 종료 날짜 (YYYY-MM-DD)
                            transaction_type: Optional[str] = None # 거래 유형 필터 ('buy' / 'sell')
                        ):
    """
    거래 내역 조회
    """
    try:
        if STORAGE_TYPE == 'sqlite':
            conn = sqlite3.connect(DB_PATH)
            
            query = "SELECT * FROM transactions WHERE 1=1"
            params = []
            
            if start_date:
                query += " AND date >= ?"
                params.append(start_date)
            
            if end_date:
                query += " AND date <= ?"
                params.append(end_date)
            
            if transaction_type:
                query += " AND transaction_type = ?"
                params.append(transaction_type)
            
            query += " ORDER BY date DESC"
            
            df = pd.read_sql_query(query, conn, params=params)
            conn.close()
        elif STORAGE_TYPE == 'csv':
            df = pd.read_csv(CSV_PATH)
            
            if start_date:
                df = df[df['date'] >= start_date]
            
            if end_date:
                df = df[df['date'] <= end_date]
            
            if transaction_type:
                df = df[df['transaction_type'] == transaction_type]
            
            df = df.sort_values(by='date', ascending=False)
        
        transactions = json.loads(df.to_json(orient='records'))
        
        return {
                "status": "success",
                "count": len(transactions),
                "transactions": transactions
                }
    except Exception as e:
        return {
                "status": "error",
                "message": f"Error get_transactions: {str(e)}"
                }

@mcp.tool()
async def update_transaction(
                            transaction_id: int, # 수정할 거래 ID
                            date: Optional[str] = None, # 거래 날짜 (YYYY-MM-DD)
                            transaction_type: Optional[str] = None, # 거래 유형 ('buy' / 'sell')
                            amount: Optional[float] = None, # 거래량 (g)
                            price: Optional[float] = None, # 단가 (원/g)
                            note: Optional[str] = None
                            ):
    """
    기존 거래 내역 수정
    """
    try:
        now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
        
        if STORAGE_TYPE == 'sqlite':
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM transactions WHERE id = ?", (transaction_id,))
            transaction = cursor.fetchone()
            
            if not transaction:
                return {"status": "error", "message": f"ID {transaction_id}에 해당하는 거래가 없습니다."}
            
            current_date = date if date is not None else transaction[1]
            current_type = transaction_type if transaction_type is not None else transaction[2]
            current_amount = amount if amount is not None else transaction[3]
            current_price = price if price is not None else transaction[4]
            current_note = note if note is not None else transaction[6]
            
            total_price = current_amount * current_price
            
            cursor.execute(
                            '''
                            UPDATE transactions 
                            SET date = ?, transaction_type = ?, amount = ?, 
                            price = ?, total_price = ?, note = ?, timestamp = ? 
                            WHERE id = ?
                            ''',
                            (current_date, current_type, current_amount, current_price, 
                            total_price, current_note, now, transaction_id)
                        )
            conn.commit()
            conn.close()
        elif STORAGE_TYPE == 'csv':
            df = pd.read_csv(CSV_PATH)
            
            if transaction_id not in df['id'].values:
                return {"status": "error", "message": f"ID {transaction_id}에 해당하는 거래가 없습니다."}
            
            idx = df[df['id'] == transaction_id].index[0]
            
            if date is not None: df.at[idx, 'date'] = date
            if transaction_type is not None: df.at[idx, 'transaction_type'] = transaction_type
            if amount is not None: df.at[idx, 'amount'] = amount
            if price is not None: df.at[idx, 'price'] = price
            if note is not None: df.at[idx, 'note'] = note
            
            df.at[idx, 'total_price'] = df.at[idx, 'amount'] * df.at[idx, 'price']
            df.at[idx, 'timestamp'] = now
            
            df.to_csv(CSV_PATH, index=False)
        
        return {
                "status": "success",
                "message": f"거래 ID {transaction_id}가 성공적으로 수정되었습니다."
                }
    except Exception as e:
        return {
                "status": "error",
                "message": f"Error update_transaction: {str(e)}"
                }

@mcp.tool()
async def delete_transaction(transaction_id):
    """
    거래 내역 삭제
    """
    try:
        if STORAGE_TYPE == 'sqlite':
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute("SELECT id FROM transactions WHERE id = ?", (transaction_id,))
            if not cursor.fetchone():
                return {"status": "error", "message": f"ID {transaction_id}에 해당하는 거래가 없습니다."}
            
            cursor.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
            conn.commit()
            conn.close()
        elif STORAGE_TYPE == 'csv':
            df = pd.read_csv(CSV_PATH)
            
            if transaction_id not in df['id'].values:
                return {"status": "error", "message": f"ID {transaction_id}에 해당하는 거래가 없습니다."}
            
            df = df[df['id'] != transaction_id]
            
            df.to_csv(CSV_PATH, index=False)
        
        return {
                "status": "success",
                "message": f"거래 ID {transaction_id}가 성공적으로 삭제되었습니다."
                }
    except Exception as e:
        return {
                "status": "error",
                "message": f"Error delete_transaction: {str(e)}"
                }

@mcp.tool()
async def export_transactions(forma = "json"):
    """
    거래 내역 JSON 형식으로 반환
    """
    try:
        if STORAGE_TYPE == 'sqlite':
            conn = sqlite3.connect(DB_PATH)
            df = pd.read_sql_query("SELECT * FROM transactions ORDER BY date DESC", conn)
            conn.close()
        elif STORAGE_TYPE == 'csv':
            df = pd.read_csv(CSV_PATH)
            df = df.sort_values(by='date', ascending=False)
        
        if format.lower() == "json":export_data = json.loads(df.to_json(orient='records'))
        else: export_data = df.to_csv(index=False)
        
        return {
                "status": "success",
                "format": format.lower(),
                "data": export_data
                }
    except Exception as e:
        return {
                "status": "error",
                "message": f"Error export_transactions: {str(e)}"
                }

if __name__ == "__main__":
    print("LedgerServer 시작 중...")
    # mcp.run(transport="sse") # remote 방식
    mcp.run(transport="stdio") # local 방식 
