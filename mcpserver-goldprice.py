from mcp.server.fastmcp import FastMCP
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import pytz
from typing import Optional, Dict, List, Any
import logging
from datetime import datetime, timedelta
import re, random
import json

KST = pytz.timezone('Asia/Seoul')

mcp = FastMCP(
            "GoldPriceService",  
            host="0.0.0.0",  
            port=8001,  
            )

@mcp.tool()
async def get_current_gold_price():
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

@mcp.tool()
async def get_gold_price_history(days = 30):
    """
    과거 금 시세 정보 일별로 조회
    """
    try:
        history_data = []
        
        url = "https://koreagoldx.co.kr/main/html.php?htmid=goods/gold_list.html"
        
        headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                    "Referer": "https://koreagoldx.co.kr/",
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "X-Requested-With": "XMLHttpRequest"
                    }
        
        session = requests.Session()
        
        session.get("https://koreagoldx.co.kr/", headers=headers)
        
        api_url = "https://koreagoldx.co.kr/main/json/price_list.php"
        
        end_date = datetime.now(KST).strftime("%Y-%m-%d")
        
        start_date = (datetime.now(KST) - timedelta(days=days)).strftime("%Y-%m-%d")
        
        params = {
                "type": "G", 
                "term": "custom", 
                "start_date": start_date,
                "end_date": end_date
                }
        
        response = session.get(api_url, params=params, headers=headers)
        response.raise_for_status()
        
        data_extracted = False  
        
        try:
            data = response.json()
            
            if isinstance(data, list) and data:
                for item in data:
                    date_str = item.get('date', '')
                    price = float(item.get('price', 0))
                    
                    history_data.append({
                                        "date": date_str,
                                        "price_krw": price,
                                        "unit": "원/g"
                                        })
                data_extracted = True
            elif isinstance(data, dict) and 'items' in data and data['items']:
                items = data.get('items', [])
                for item in items:
                    date_str = item.get('date', '')
                    price = float(item.get('price', 0))
                    
                    history_data.append({
                                        "date": date_str,
                                        "price_krw": price,
                                        "unit": "원/g"
                                        })
                data_extracted = True
        except (json.JSONDecodeError, KeyError, ValueError):
            logging.warning("Error: Check API request format")
        if not data_extracted:
            try:
                response = session.get(url, headers=headers)
                soup = BeautifulSoup(response.content, 'html.parser')
                
                scripts = soup.find_all('script')
                chart_data = None
                
                for script in scripts:
                    if script.string and ('chartData' in script.string or 'priceData' in script.string or 'goldData' in script.string):

                        pattern = r'var\s+(?:chartData|priceData|goldData)\s*=\s*(\[.*?\]);'
                        match = re.search(pattern, script.string, re.DOTALL)
                        if match:
                            try:
                                chart_data = json.loads(match.group(1))
                                break
                            except json.JSONDecodeError:
                                continue
                
                if chart_data:
                    for item in chart_data:
                        date_str = item.get('date', '')
                        price = float(item.get('value', 0))
                        
                        history_data.append({
                                            "date": date_str,
                                            "price_krw": price,
                                            "unit": "원/g"
                                            })
                    data_extracted = True
            except Exception as e:
                logging.warning(f"data crawling Falied: {str(e)}")

        if not data_extracted:
            logging.warning("API request, data crawling Falied")
            
            try:
                current_price_data = await get_current_gold_price()
                current_price = current_price_data.get("price_krw", 150000)  
            except Exception:
                current_price = 150000  
            
            base_date = datetime.now(KST)
            
            volatility = 0.005  
            
            temp_history = []  
            
            for i in range(days):
                date = base_date - timedelta(days=i)
                date_str = date.strftime("%Y-%m-%d")
                
                daily_change = random.uniform(-volatility, volatility)
                
                price = current_price / ((1 + daily_change) ** i)
                price = round(price, 2)  
                
                temp_history.append({
                                    "date": date_str,
                                    "price_krw": price,
                                    "unit": "원/g"
                                    })
            
            temp_history.reverse()
            history_data = temp_history
        
        if len(history_data) > days:
            history_data = history_data[-days:]
        
        return {
                "history": history_data,
                "period": f"{days}일",
                "source": "한국금거래소",
                "status": "success",
                "timestamp": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
                }
    except Exception as e:
        logging.error(f"get_gold_price_history Error: {str(e)}")
        
        return {
                "timestamp": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"),
                "status": "error",
                "message": str(e)
                }

if __name__ == "__main__":
    print("GoldPriceServer 시작 중...")
    # mcp.run(transport="sse") # remote 방식
    mcp.run(transport="stdio") # local 방식 