#!/usr/bin/env python3
import json
import threading
import time
import requests

# Start Flask app in background thread
from app import app

def run_app():
    app.run(port=5001, debug=False, use_reloader=False)

thread = threading.Thread(target=run_app, daemon=True)
thread.start()
time.sleep(1)

BASE = "http://127.0.0.1:5001"

print("Testing Flask web app APIs...")

# Test 1: Set budget
r = requests.post(f"{BASE}/api/budget", json={"amount": 1500})
assert r.json()["success"]
print("[PASS] POST /api/budget")

# Test 2: Set limits
r = requests.post(f"{BASE}/api/limits", json={"category": "餐饮", "amount": 500})
assert r.json()["success"]
print("[PASS] POST /api/limits")

r = requests.post(f"{BASE}/api/limits", json={"category": "交通", "amount": 200})
assert r.json()["success"]
print("[PASS] POST /api/limits (交通)")

# Test 3: Get budget
r = requests.get(f"{BASE}/api/budget")
data = r.json()
assert data["monthly_budget"] == 1500
print(f"[PASS] GET /api/budget: {data}")

# Test 4: Approve
r = requests.post(f"{BASE}/api/approve", json={"amount": 50, "description": "地铁通勤"})
data = r.json()
assert data["approved"] == True
assert data["category"] == "交通"
print(f"[PASS] POST /api/approve (approved): {data}")

r = requests.post(f"{BASE}/api/approve", json={"amount": 1200, "description": "买新手机"})
data = r.json()
assert data["approved"] == False
print(f"[PASS] POST /api/approve (rejected): {data}")

# Test 5: Records
r = requests.get(f"{BASE}/api/records")
data = r.json()
assert len(data["records"]) >= 2
print(f"[PASS] GET /api/records: {len(data['records'])} records")

# Test 6: Bills
r = requests.get(f"{BASE}/api/bill/daily")
assert "每日账单" in r.json()["bill"]
print("[PASS] GET /api/bill/daily")

r = requests.get(f"{BASE}/api/bill/weekly")
assert "每周账单" in r.json()["bill"]
print("[PASS] GET /api/bill/weekly")

# Test 7: Index page
r = requests.get(f"{BASE}/")
assert r.status_code == 200
assert "经费审批与记账助手" in r.text
print("[PASS] GET / (index page)")

print("\nAll tests passed!")
