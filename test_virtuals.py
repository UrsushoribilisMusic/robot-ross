import requests
import json
import time

# Config - Robot Ross Salesman API
BASE_URL = "https://api.robotross.art"
VIRTUALS_API_KEY = "acp-af80c0d53bd965c43a35"

def test_offerings():
    print("--- 1. Testing GET /acp/offerings ---")
    headers = { "X-API-KEY": VIRTUALS_API_KEY }
    try:
        resp = requests.get(f"{BASE_URL}/acp/offerings", headers=headers)
        print(f"Status: {resp.status_code}")
        print(json.dumps(resp.json(), indent=2))
    except Exception as e:
        print(f"Error: {e}")

def test_create_order():
    print("--- 2. Testing POST /acp/orders (Virtuals Format) ---")
    headers = { 
        "X-API-KEY": VIRTUALS_API_KEY,
        "Content-Type": "application/json"
    }
    order_id = "test_" + str(int(time.time()))
    payload = {
        "order_id": order_id,
        "offering_id": "robot_ross_write",
        "parameters": {
            "content": "Hello Virtuals! Integration Test"
        },
        "buyer_id": "tester_gemini"
    }
    try:
        resp = requests.post(f"{BASE_URL}/acp/orders", headers=headers, json=payload)
        print(f"Status: {resp.status_code}")
        data = resp.json()
        print(json.dumps(data, indent=2))
        return data.get("id")
    except Exception as e:
        print(f"Error: {e}")
        return None

def test_order_status(order_id):
    if not order_id: return
    print("--- 3. Testing GET /acp/orders/" + str(order_id) + " ---")
    headers = { "X-API-KEY": VIRTUALS_API_KEY }
    try:
        resp = requests.get(f"{BASE_URL}/acp/orders/{order_id}", headers=headers)
        print(f"Status: {resp.status_code}")
        print(json.dumps(resp.json(), indent=2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_offerings()
    new_id = test_create_order()
    if new_id:
        time.sleep(1)
        test_order_status(new_id)
