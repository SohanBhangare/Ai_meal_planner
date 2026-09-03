from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from datetime import date
import pandas as pd
import os
import meal_planner
from models import db, User, CalorieLog, DailyStats

app = Flask(__name__)
app.config["SECRET_KEY"] = "supersecretkey"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///pal.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
bcrypt = Bcrypt(app)

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---------------- CALORIE CALCULATION FUNCTION ----------------
def calculate_calorie_goal(user):
    """
    Calculates TDEE (Total Daily Energy Expenditure) and adjusts
    the calorie goal based on the user's profile data and weight goal.
    Assumes weight is in kg and height is in cm.
    """
    
    # Fallback if critical data is missing (should not happen after profile update)
    if not all([user.weight, user.height, user.age, user.gender]):
        return 2000

    # Mifflin-St Jeor Equation to calculate BMR (Basal Metabolic Rate)
    # The constants used here assume weight in kg and height in cm.
    if user.gender.lower() == 'male':
        # BMR = 10*weight (kg) + 6.25*height (cm) - 5*age (years) + 5
        bmr = (10 * user.weight) + (6.25 * user.height) - (5 * user.age) + 5
    else: # Assuming female
        # BMR = 10*weight (kg) + 6.25*height (cm) - 5*age (years) - 161
        bmr = (10 * user.weight) + (6.25 * user.height) - (5 * user.age) - 161

    # Activity Multiplier to calculate TDEE
    activity_multipliers = {
        "sedentary": 1.2,
        "lightly active": 1.375,
        "moderately active": 1.55,
        "very active": 1.725,
        "extra active": 1.9
    }
    tdee = bmr * activity_multipliers.get(user.activity_level.lower(), 1.2)
    
    # Adjust TDEE based on weight goal
    # Bug 2 Fix: form sends 'lose', not 'loss'
    goal_adjustment = 0
    if user.goal.lower() == 'lose':
        # Daily deficit for weight loss
        goal_adjustment = -500
    elif user.goal.lower() == 'gain':
        # Daily surplus for muscle/weight gain
        goal_adjustment = 300
    
    # Final goal, rounded to the nearest 50
    raw_goal = tdee + goal_adjustment
    final_goal = int(round(raw_goal / 50) * 50)
    
    # Ensure minimum safe calorie intake
    return max(final_goal, 1200)

# ---------------- CSV Loader ----------------
base_path = os.path.dirname(os.path.abspath(__file__))
data_path = os.path.join(base_path, "Dataset")
all_foods = pd.DataFrame()
for file in ["Breakfast.csv", "Lunch.csv", "Dinner.csv"]:
    path = os.path.join(data_path, file)
    if os.path.exists(path):
        df = pd.read_csv(path)
        df.columns = df.columns.str.strip().str.lower()
        if "food_name" not in df.columns:
            df.rename(columns={df.columns[0]: "food_name"}, inplace=True)
        expected_cols = ["calories", "protein", "carbs", "fat", "fiber", "calcium", "iron"]
        for col in expected_cols:
            if col not in df.columns:
                df[col] = 0
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        all_foods = pd.concat([all_foods, df], ignore_index=True)

# ---------------- ROUTES ----------------
@app.route("/")
def home():
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if User.query.filter_by(username=username).first():
            # Use a friendly message box/redirect instead of raw return in a real app
            return "User already exists!"

        hashed_pw = bcrypt.generate_password_hash(password).decode("utf-8")
        # Keep calorie_goal=2000 here, as it will be immediately updated 
        # when the user fills out the profile form next.
        new_user = User(username=username, password=hashed_pw,
                        preference="veg", goal="maintain", calorie_goal=2000)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for("profile", user_id=new_user.id))
    return render_template("register.html")


@app.route("/profile", methods=["GET", "POST"])
def profile():
    user_id = request.args.get("user_id")
    if not user_id:
        return redirect(url_for("register"))
    user = User.query.get(int(user_id))
    if not user:
        return redirect(url_for("register"))
        
    if request.method == "POST":
        user.height = float(request.form["height"])
        user.weight = float(request.form["weight"])
        user.age = int(request.form["age"])
        user.gender = request.form["gender"]
        user.activity_level = request.form["activity_level"]
        user.preference = request.form["preference"]
        user.goal = request.form["goal"]
        
        # 🌟 FIX: Calculate and set the initial personalized calorie goal
        user.calorie_goal = calculate_calorie_goal(user)
        
        db.session.commit()
        return redirect(url_for("login"))
    return render_template("profile.html", user=user)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("dashboard"))
        else:
            return "Invalid credentials!"
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
@login_required
def dashboard():
    logs = CalorieLog.query.filter_by(user_id=current_user.id, log_date=date.today()).all()

    total_calories = total_protein = total_carbs = total_fat = total_fiber = total_calcium = total_iron = 0.0
    log_data = []

    for log in logs:
        # Bug 3 Fix: Use values already stored in DB (already multiplied by serving_size at log time).
        # Do NOT re-fetch from CSV and re-multiply — that causes double-counting.
        log_calories_total = log.calories * log.serving_size  # calories stored per serving
        protein  = round(log.protein,  1)
        carbs    = round(log.carbs,    1)
        fat      = round(log.fat,      1)
        fiber    = round(log.fiber,    1)
        calcium  = round(log.calcium,  1)
        iron     = round(log.iron,     1)

        total_calories += log_calories_total
        total_protein  += protein
        total_carbs    += carbs
        total_fat      += fat
        total_fiber    += fiber
        total_calcium  += calcium
        total_iron     += iron

        log_data.append({
            "food_name": log.food_name,
            "meal_type": log.meal_type,
            "calories": round(log_calories_total, 1),
            "protein":  protein,
            "carbs":    carbs,
            "fat":      fat,
            "fiber":    fiber,
            "calcium":  calcium,
            "iron":     iron
        })

    stats = DailyStats.query.filter_by(user_id=current_user.id, date=date.today()).first()
    if not stats:
        stats = DailyStats(user_id=current_user.id, date=date.today(), water_intake=0, steps=0)
        db.session.add(stats)
        db.session.commit()

    # -------------------- Adaptive Next Day Goal --------------------
    # Bug 5 Fix: Save today's goal BEFORE overwriting it, so the template shows the correct today's goal.
    todays_calorie_goal = current_user.calorie_goal

    calorie_diff = total_calories - todays_calorie_goal
    adjustment_factor = 0.5  # adjust 50% of deviation

    next_day_goal = todays_calorie_goal
    if calorie_diff > 0:  # Overeaten
        next_day_goal = max(todays_calorie_goal - (calorie_diff * adjustment_factor), 1200)
    elif calorie_diff < 0:  # Undereaten
        next_day_goal = min(todays_calorie_goal + (abs(calorie_diff) * adjustment_factor), 3000)

    # Round to nearest 50 for consistency
    next_day_goal = int(round(next_day_goal / 50) * 50)

    # Persist next day's goal for tomorrow
    current_user.calorie_goal = next_day_goal
    db.session.commit()

    # Generate adaptive meal plan based on the updated next_day_goal
    meals = meal_planner.generate_daily_meal_plan(next_day_goal, current_user.preference)

    return render_template(
        "dashboard.html",
        user=current_user,
        today=date.today(),
        logs=log_data,
        total_calories=round(total_calories, 1),
        total_protein=round(total_protein, 1),
        total_carbs=round(total_carbs, 1),
        total_fat=round(total_fat, 1),
        total_fiber=round(total_fiber, 1),
        total_calcium=round(total_calcium, 1),
        total_iron=round(total_iron, 1),
        calorie_goal=todays_calorie_goal,   # Bug 5 Fix: today's actual goal
        next_day_goal=next_day_goal,         # Tomorrow's adaptive goal
        meals=meals,
        stats=stats
    )


@app.route("/log", methods=["POST"])
@login_required
def log_food():
    food_name = request.form["food_name"]
    meal_type = request.form["meal_type"]
    serving_size = float(request.form.get("serving_size", 1))

    match = all_foods[all_foods["food_name"].str.lower() == food_name.lower()]
    
    # Use food info from the loaded CSV for accurate calculation
    if not match.empty:
        food_info = match.iloc[0]
        # Base values (per single serving) from CSV
        base_calories = float(food_info.get("calories", 0))
        base_protein = float(food_info.get("protein", 0))
        base_carbs = float(food_info.get("carbs", 0))
        base_fat = float(food_info.get("fat", 0))
        base_fiber = float(food_info.get("fiber", 0))
        base_calcium = float(food_info.get("calcium", 0))
        base_iron = float(food_info.get("iron", 0))
    else:
        # If food not found, assume 0 or handle error
        base_calories = base_protein = base_carbs = base_fat = base_fiber = base_calcium = base_iron = 0
    
    # Store per-serving base values in the log (or just the total if model is simpler)
    # The models.py structure implies storing the total, or the per-serving values.
    # We will store the base (per 1 serving) calories, and the total values in the other fields
    
    calories_per_serving_to_store = base_calories

    new_log = CalorieLog(
        food_name=food_name,
        # Store calories per single serving (as done in the original code, but confirmed here)
        calories=calories_per_serving_to_store, 
        meal_type=meal_type,
        log_date=date.today(),
        user_id=current_user.id,
        serving_size=serving_size,
        # Note: The model stores total macros in the log fields, which is okay, 
        # but typically you store per-serving data and calculate the total in the dashboard.
        # Sticking to the original behavior of storing total macros based on serving_size for now.
        protein=base_protein * serving_size,
        carbs=base_carbs * serving_size,
        fat=base_fat * serving_size,
        fiber=base_fiber * serving_size,
        calcium=base_calcium * serving_size,
        iron=base_iron * serving_size
    )
    db.session.add(new_log)
    db.session.commit()
    return redirect(url_for("dashboard"))


@app.route("/update_stats", methods=["POST"])
@login_required
def update_stats():
    stats = DailyStats.query.filter_by(user_id=current_user.id, date=date.today()).first()
    if not stats:
        stats = DailyStats(user_id=current_user.id, date=date.today(), water_intake=0, steps=0)
        db.session.add(stats)
    stats.water_intake = int(request.form.get("water_intake", 0))
    stats.steps = int(request.form.get("steps", 0))
    db.session.commit()
    return redirect(url_for("dashboard"))


@app.route("/calendar_data")
@login_required
def calendar_data():
    stats = DailyStats.query.filter_by(user_id=current_user.id).all()
    events = []
    for s in stats:
        events.append({
            "title": f"Steps: {s.steps} | Water: {s.water_intake}ml",
            "start": s.date.isoformat(),
            "color": "#a855f7"
        })
    return jsonify(events)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
