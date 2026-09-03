import pandas as pd
import os

# ----------------------------- CSV Paths -----------------------------
base_path = os.path.dirname(os.path.abspath(__file__))
data_path = os.path.join(base_path, "Dataset")

# ----------------------------- CSV Loader -----------------------------
def load_csv(file_name):
    """Load and clean CSV file safely with calories, macros, and micros"""
    path = os.path.join(data_path, file_name)
    if not os.path.exists(path):
        return pd.DataFrame(columns=[
            "food_name", "category", "calories", "protein", "carbs", "fat",
            "fiber", "calcium", "iron"
        ])

    df = pd.read_csv(path)
    df.columns = df.columns.str.strip().str.lower()

    # Ensure mandatory columns exist
    expected_cols = ["food_name", "category", "calories", "protein", "carbs", "fat", "fiber", "calcium", "iron"]
    for col in expected_cols:
        if col not in df.columns:
            df[col] = 0

    # Convert numeric columns safely
    for col in ["calories", "protein", "carbs", "fat", "fiber", "calcium", "iron"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["food_name"] = df["food_name"].astype(str).str.strip()
    df["category"] = df["category"].astype(str).str.strip()

    return df

# ----------------------------- Load Datasets -----------------------------
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
    """Generate a meal with calories, macros, and micros"""
    if df.empty:
        return []

    df = df.sample(frac=1).reset_index(drop=True)  # shuffle
    items = []
    total_cal = 0

    for i, row in df.iterrows():
        if total_cal >= target_calories:
            break

        remaining = target_calories - total_cal
        if row["calories"] == 0:
            factor = 1
        else:
            factor = min(1.5, remaining / row["calories"])  # scale servings

        scaled_item = {
            "food_name": row["food_name"],
            "calories": int(row["calories"] * factor),
            "protein": round(row["protein"] * factor, 1),
            "carbs": round(row["carbs"] * factor, 1),
            "fat": round(row["fat"] * factor, 1),
            "fiber": round(row["fiber"] * factor, 1),
            "calcium": round(row["calcium"] * factor, 1),
            "iron": round(row["iron"] * factor, 1),
        }

        items.append(scaled_item)
        total_cal += scaled_item["calories"]

    # If still under target, adjust first item's calories to match
    if items and total_cal < target_calories:
        diff = target_calories - total_cal
        # Bug 4 Fix: calculate scale factor BEFORE adding diff to calories
        # to avoid dividing by the already-inflated value
        original_cal = items[0]["calories"]
        items[0]["calories"] += diff
        if original_cal > 0:
            scale = 1 + diff / original_cal
            for key in ["protein", "carbs", "fat", "fiber", "calcium", "iron"]:
                items[0][key] = round(items[0][key] * scale, 1)

    return items

# ----------------------------- Daily Meal Plan Generator -----------------------------
def generate_daily_meal_plan(daily_calories=2000, preference="veg"):
    """Generate daily meal plan with calories, macros, and micros"""
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

# ----------------------------- Run Example -----------------------------
if __name__ == "__main__":
    plan = generate_daily_meal_plan(daily_calories=2000, preference="veg")
    import pprint
    pprint.pprint(plan)
