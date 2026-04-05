import requests

class DhanEquityBroker:
    def __init__(self, client_id: str, access_token: str):
        self.client_id = client_id
        self.access_token = access_token
        self.headers = {
            "access-token": access_token,
            "client-id": client_id,
            "Content-Type": "application/json"
        }
        self.base_url = "https://api.dhan.co/v2"

    def get_quote(self, security_id: int):
        try:
            url = f"{self.base_url}/marketfeed/quote"
            body = {"NSE_EQ": [security_id]}
            res = requests.post(url, headers=self.headers, json=body, timeout=10)
            data = res.json()
            return data.get("data", {}).get("NSE_EQ", {}).get(str(security_id), {})
        except:
            return {}

    def place_order(self, security_id: int, qty: int, side: str = "BUY", price=0):
        body = {
            "dhanClientId": self.client_id,
            "transactionType": side,
            "exchangeSegment": "NSE_EQ",
            "productType": "INTRADAY",
            "orderType": "MARKET" if price == 0 else "LIMIT",
            "validity": "DAY",
            "securityId": str(security_id),
            "quantity": qty,
            "price": round(price, 2) if price > 0 else 0,
        }
        try:
            res = requests.post(f"{self.base_url}/orders", headers=self.headers, json=body)
            return res.json()
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_funds(self):
        try:
            res = requests.get(f"{self.base_url}/fundlimit", headers=self.headers)
            data = res.json().get("data", {})
            return {"available": float(data.get("availabelBalance", 0))}
        except:
            return {"available": 0}
