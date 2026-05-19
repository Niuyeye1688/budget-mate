import json
import os

DATA_FILE = os.path.join(os.path.dirname(__file__), "budget_data.json")

# 先备份
data = json.load(open(DATA_FILE, "r", encoding="utf-8"))

# 模拟上月数据和记录
data["current_month"] = "2026-04"
data["records"] = [
    {"id": 1, "date": "2026-04-15 12:00:00", "amount": 25, "description": "午饭", "category": "餐饮", "approved": True},
    {"id": 2, "date": "2026-04-15 19:00:00", "amount": 35, "description": "晚饭", "category": "餐饮", "approved": True},
    {"id": 3, "date": "2026-04-20 08:00:00", "amount": 50, "description": "打车", "category": "交通", "approved": True},
]

with open(DATA_FILE, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("已模拟上月数据（2026-04），记录数:", len(data["records"]))

# 运行月度重置检查
from bills import check_monthly_reset
check_monthly_reset()

# 检查结果
data_after = json.load(open(DATA_FILE, "r", encoding="utf-8"))
print("\n重置后:")
print("  current_month:", data_after.get("current_month"))
print("  records 数量:", len(data_after.get("records", [])))

# 检查账单文件
bill_dir = os.path.join(os.path.dirname(DATA_FILE), "bills")
bill_file = os.path.join(bill_dir, "bill_month_2026-04.txt")
if os.path.exists(bill_file):
    print("  账单文件已生成:", bill_file)
    with open(bill_file, "r", encoding="utf-8") as f:
        print("\n--- 账单内容预览 ---")
        print(f.read()[:500])
else:
    print("  账单文件未找到!")
