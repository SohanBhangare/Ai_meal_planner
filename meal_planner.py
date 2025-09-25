import pandas as pd
import os

# ----------------------------- CSV Paths -----------------------------
base_path = os.path.dirname(os.path.abspath(__file__))
data_path = os.path.join(base_path, "Dataset")

def load_csv(file_name):
    """Load and clean CSV file safely"""
    path = os.path.join(data_path, file_name)
    if not os.path.exists(path):
        return pd.DataFrame(columns=["food_name", "calories"])

    df = pd.read_csv(path)
    df.columns = df.columns.str.strip().str.lower()

    # Normalize columns
    if "food_name" not in df.columns:
        df.rename(columns={df.columns[0]: "food_name"}, inplace=True)
    if "calories" not in df.columns:
        df["calories"] = 0

    # Clean values
    df["calories"] = pd.to_numeric(df["calories"], errors="coerce").fillna(0).astype(int)
    df["food_name"] = df["food_name"].astype(str).str.strip()

    return df

# Load datasets
df_breakfast = load_csv("Breakfast.csv")
df_lunch = load_csv("Lunch.csv")
df_dinner = load_csv("Dinner.csv")

# ----------------------------- Veg/Non-Veg Filter -----------------------------
def filter_foods(df, preference):
    """Filter foods based on veg/non-veg preference"""
    if preference == "veg":
        nonveg_keywords = ["chicken", "egg", "fish", "meat", "mutton", "prawn"]
        return df[~df["food_name"].str.lower().str.contains("|".join(nonveg_keywords), na=False)]
    return df  # nonveg → allow all

# ----------------------------- Meal Builder -----------------------------
def build_meal(df, target_calories):
    """Generate a meal from dataset to match target calories"""
    if df.empty:
        return []

    df = df.sample(frac=1).reset_index(drop=True)  # shuffle
    items = []
    total = 0
    max_items = min(4, len(df))  # limit items
    count = 0

    while total < target_calories and count < max_items:
        row = df.iloc[count]
        remaining = target_calories - total
        cal = min(row["calories"] * 2, remaining)  # allow portion scaling
        items.append({"food_name": row["food_name"], "calories": int(cal)})
        total += cal
        count += 1

    # Balance out if still under target
    if total < target_calories and items:
        diff = target_calories - total
        items[0]["calories"] += int(diff)

    return items

# ----------------------------- Main Function -----------------------------
def generate_daily_meal_plan(daily_calories=2000, preference="veg"):
    """Generate breakfast, lunch, dinner plan"""
    allocation = {"breakfast": 0.25, "lunch": 0.40, "dinner": 0.35}
    recommended = {k: int(daily_calories * v) for k, v in allocation.items()}

    bf = filter_foods(df_breakfast, preference)
    ln = filter_foods(df_lunch, preference)
    dn = filter_foods(df_dinner, preference)

    breakfast = build_meal(bf, recommended["breakfast"])
    lunch = build_meal(ln, recommended["lunch"])
    dinner = build_meal(dn, recommended["dinner"])

    return {
        "breakfast": breakfast,
        "lunch": lunch,
        "dinner": dinner
    }
