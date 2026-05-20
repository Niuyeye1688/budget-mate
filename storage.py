import json
import os
import sys
from datetime import datetime

if getattr(sys, 'frozen', False):
    base_dir = os.path.join(
        os.environ.get('LOCALAPPDATA', os.path.expanduser('~')),
        'budget-mate'
    )
    os.makedirs(base_dir, exist_ok=True)
else:
    base_dir = os.path.dirname(__file__)

DATA_FILE = os.path.join(base_dir, "budget_data.json")

DEFAULT_DATA = {
    "monthly_budget": 0,
    "category_limits": {
        "餐饮": 0,
        "交通": 0,
        "购物": 0,
        "娱乐": 0,
        "其他": 0,
    },
    "records": [],
    "api_config": {
        "enabled": False,
        "api_key": "",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-v4-pro",
    },
    "current_month": "",
}


def load_data():
    if not os.path.exists(DATA_FILE):
        return DEFAULT_DATA.copy()
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_current_month():
    return datetime.now().strftime("%Y-%m")
