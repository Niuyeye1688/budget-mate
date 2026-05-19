from storage import load_data, save_data


def set_monthly_budget(amount):
    data = load_data()
    data["monthly_budget"] = amount
    save_data(data)
    return amount


def get_monthly_budget():
    return load_data().get("monthly_budget", 0)


def set_category_limit(category, amount):
    data = load_data()
    data["category_limits"][category] = amount
    save_data(data)
    return amount


def get_category_limits():
    return load_data().get("category_limits", {})


def get_remaining_budget():
    from ledger import get_month_spent
    return get_monthly_budget() - get_month_spent()
