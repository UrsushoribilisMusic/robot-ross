import requests
import json
import time

# Config
BASE_URL = "https://api.robotross.art"
VIRTUALS_API_KEY = "acp-af80c0d53bd965c43a35"

def test_bidding():
    print("🚀 Testing Slot Bidding (Buying Slot A1 for $5)...")
    headers = { 
        "X-API-KEY": VIRTUALS_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "order_id": "bid_test_" + str(int(time.time())),
        "offering_id": "write_calligraphy",
        "parameters": {
            "content": "Property of Gemini",
            "slot": "A1"
        },
        "funds_transferred": 5.0,
        "buyer_id": "Gemini_Bot"
    }
    resp = requests.post(BASE_URL + "/acp/orders", headers=headers, json=payload)
    print("Status: " + str(resp.status_code))
    print(json.dumps(resp.json(), indent=2))

    if resp.status_code == 201:
        print("")
        print("📈 Testing Overwrite (Trying to buy A1 for $5.50 - SHOULD FAIL)...")
        payload["funds_transferred"] = 5.50
        resp = requests.post(BASE_URL + "/acp/orders", headers=headers, json=payload)
        print("Status: " + str(resp.status_code) + " (Expected 409)")
        
        print("")
        print("💰 Testing Overwrite (Trying to buy A1 for $10 - SHOULD SUCCEED)...")
        payload["funds_transferred"] = 10.0
        payload["order_id"] = "bid_test_win_" + str(int(time.time()))
        resp = requests.post(BASE_URL + "/acp/orders", headers=headers, json=payload)
        print("Status: " + str(resp.status_code) + " (Expected 201)")

if __name__ == "__main__":
    test_bidding()
