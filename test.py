#!/usr/bin/env python3
import os
import json

# Clean test data
DATA_FILE = os.path.join(os.path.dirname(__file__), "budget_data.json")
if os.path.exists(DATA_FILE):
    os.remove(DATA_FILE)

from budget import set_monthly_budget, set_category_limit, get_monthly_budget, get_remaining_budget
from approver import judge_expense
from ledger import add_record, get_all_records, get_today_records, get_week_records, get_month_spent
from bills import generate_daily_bill, generate_weekly_bill

print("=" * 50)
print("Running tests...")
print("=" * 50)

# Test 1: Budget
set_monthly_budget(5000)
set_category_limit("餐饮", 1500)
set_category_limit("交通", 800)
set_category_limit("购物", 1000)
assert get_monthly_budget() == 5000
assert get_remaining_budget() == 5000
print("[PASS] Budget setup")

# Test 2: Approval
r1 = judge_expense(200, "请朋友吃饭")
assert r1["approved"] == True
assert r1["category"] == "餐饮"
print(f"[PASS] Approve 200 for 请朋友吃饭: {r1}")

r2 = judge_expense(50, "地铁通勤")
assert r2["approved"] == True
assert r2["category"] == "交通"
print(f"[PASS] Approve 50 for 地铁通勤: {r2}")

r3 = judge_expense(1200, "买新手机")
assert r3["approved"] == False
assert r3["category"] == "购物"
print(f"[PASS] Reject 1200 for 买新手机: {r3}")

# Test 3: Ledger
add_record(200, "请朋友吃饭", "餐饮", True)
add_record(50, "地铁通勤", "交通", True)
add_record(1200, "买新手机", "购物", False)
add_record(30, "买咖啡", "餐饮", True)

records = get_all_records()
assert len(records) == 4
print("[PASS] Records stored")

assert get_month_spent() == 280  # 200 + 50 + 30
print(f"[PASS] Month spent = {get_month_spent()}")

# Test 4: Bills
daily = generate_daily_bill()
assert "每日账单" in daily
assert "请朋友吃饭" in daily
print("[PASS] Daily bill generated")

weekly = generate_weekly_bill()
assert "每周账单" in weekly
assert "餐饮" in weekly
print("[PASS] Weekly bill generated")

# Test 5: Data persistence
data = json.load(open(DATA_FILE, "r", encoding="utf-8"))
assert data["monthly_budget"] == 5000
assert len(data["records"]) == 4
print("[PASS] Data persisted correctly")

print("=" * 50)
print("All tests passed!")
print("=" * 50)

# Show sample output
print("\n--- Daily Bill ---")
print(daily)
print("\n--- Weekly Bill ---")
print(weekly)
