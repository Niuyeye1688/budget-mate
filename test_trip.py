import urllib.request
import json
import time

BASE = "http://127.0.0.1:5000"

def api(path, method="GET", data=None):
    url = f"{BASE}{path}"
    if method == "GET":
        req = urllib.request.Request(url)
    else:
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method=method,
        )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

# 清空记录
print("=== 清空记录 ===")
api("/api/records", "DELETE")

# 设置预算
print("=== 设置预算 ===")
api("/api/budget", "POST", {"amount": 1500})
api("/api/limits", "POST", {"category": "餐饮", "amount": 1000})

# 测试1：午饭 15元
print("\n=== 测试1：午饭 15元 ===")
r1 = api("/api/approve", "POST", {"amount": 15, "description": "午饭"})
print(f"结果: {r1['approved']}")
print(f"理由: {r1['reason']}")
print(f"分类: {r1['category']}")

# 测试2：奶茶 15元（10秒内提交，应触发外出合并）
print("\n=== 测试2：奶茶 15元 ===")
time.sleep(1)
r2 = api("/api/approve", "POST", {"amount": 15, "description": "奶茶"})
print(f"结果: {r2['approved']}")
print(f"理由: {r2['reason']}")

# 测试3：小吃 10元（继续触发外出合并）
print("\n=== 测试3：小吃 10元 ===")
time.sleep(1)
r3 = api("/api/approve", "POST", {"amount": 10, "description": "小吃"})
print(f"结果: {r3['approved']}")
print(f"理由: {r3['reason']}")

# 检查记录
print("\n=== 当前记录 ===")
records = api("/api/records")
for rec in records["records"]:
    print(f"  {rec['date']} | {rec['description']} {rec['amount']}元 | {rec['category']} | {'通过' if rec['approved'] else '拒绝'}")

print("\n=== 测试完成 ===")
