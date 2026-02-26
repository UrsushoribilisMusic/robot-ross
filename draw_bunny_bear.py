import requests
import json
import time

# Config
BASE_URL = "https://api.robotross.art"
VIRTUALS_API_KEY = "acp-af80c0d53bd965c43a35"

def send_bunny_bear():
    print("🚀 Sending Bunny & Bear Sketch Order to Salesman...")
    headers = { 
        "X-API-KEY": VIRTUALS_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "order_id": "demo_bunny_bear_" + str(int(time.time())),
        "offering_id": "sketch_drawing",
        "parameters": {
            "content": "A cute bunny and a friendly bear sitting together under a tree"
        },
        "buyer_id": "RobotRoss_Demo"
    }
    try:
        resp = requests.post(f"{BASE_URL}/acp/orders", headers=headers, json=payload)
        if resp.status_code == 201:
            print("✅ Order Created Successfully!")
            print("Order ID: " + str(resp.json().get('id')))
            print("\nNext Steps:")
            print("1. Ensure your Robot is Calibrated.")
            print("2. Run the poller on the Mac mini:")
            print("   /usr/bin/python3 ~/.openclaw/workspace/skills/robot-ross/artist_poller.py")
        else:
            print("❌ Failed: " + str(resp.status_code))
            print(resp.text)
    except Exception as e:
        print("❌ Error: " + str(e))

if __name__ == "__main__":
    send_bunny_bear()
