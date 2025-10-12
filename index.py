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
            return "User already exists!"

        hashed_pw = bcrypt.generate_password_hash(password).decode("utf-8")
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
        match = all_foods[all_foods["food_name"].str.lower() == log.food_name.lower()]
        if not match.empty:
            food_info = match.iloc[0]
            protein = float(food_info.get("protein", 0)) * log.serving_size
            carbs = float(food_info.get("carbs", 0)) * log.serving_size
            fat = float(food_info.get("fat", 0)) * log.serving_size
            fiber = float(food_info.get("fiber", 0)) * log.serving_size
            calcium = float(food_info.get("calcium", 0)) * log.serving_size
            iron = float(food_info.get("iron", 0)) * log.serving_size
        else:
            protein = carbs = fat = fiber = calcium = iron = 0

        total_calories += log.calories * log.serving_size
        total_protein += protein
        total_carbs += carbs
        total_fat += fat
        total_fiber += fiber
        total_calcium += calcium
        total_iron += iron

        log_data.append({
            "food_name": log.food_name,
            "meal_type": log.meal_type,
            "calories": log.calories * log.serving_size,
            "protein": protein,
            "carbs": carbs,
            "fat": fat,
            "fiber": fiber,
            "calcium": calcium,
            "iron": iron
        })

    stats = DailyStats.query.filter_by(user_id=current_user.id, date=date.today()).first()
    if not stats:
        stats = DailyStats(user_id=current_user.id, date=date.today(), water_intake=0, steps=0)
        db.session.add(stats)
        db.session.commit()

    # -------------------- Adaptive Next Day Goal --------------------
    calorie_diff = total_calories - current_user.calorie_goal
    adjustment_factor = 0.5  # adjust 50% of deviation

    if calorie_diff > 0:  # Overeaten
        next_day_goal = max(current_user.calorie_goal - (calorie_diff * adjustment_factor), 1200)
    elif calorie_diff < 0:  # Undereaten
        next_day_goal = min(current_user.calorie_goal + (abs(calorie_diff) * adjustment_factor), 3000)
    else:
        next_day_goal = current_user.calorie_goal

    next_day_goal = int(round(next_day_goal / 50) * 50)

    # Update user's calorie goal for next day
    current_user.calorie_goal = next_day_goal
    db.session.commit()

    # Generate adaptive meal plan
    meals = meal_planner.generate_daily_meal_plan(next_day_goal, current_user.preference)

    return render_template(
        "dashboard.html",
        user=current_user,
        today=date.today(),
        logs=log_data,
        total_calories=total_calories,
        total_protein=total_protein,
        total_carbs=total_carbs,
        total_fat=total_fat,
        total_fiber=total_fiber,
        total_calcium=total_calcium,
        total_iron=total_iron,
        calorie_goal=current_user.calorie_goal,
        next_day_goal=next_day_goal,
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
    if not match.empty:
        food_info = match.iloc[0]
        calories = float(food_info.get("calories", 0)) * serving_size
        protein = float(food_info.get("protein", 0)) * serving_size
        carbs = float(food_info.get("carbs", 0)) * serving_size
        fat = float(food_info.get("fat", 0)) * serving_size
        fiber = float(food_info.get("fiber", 0)) * serving_size
        calcium = float(food_info.get("calcium", 0)) * serving_size
        iron = float(food_info.get("iron", 0)) * serving_size
    else:
        calories = protein = carbs = fat = fiber = calcium = iron = 0

    new_log = CalorieLog(
        food_name=food_name,
        calories=calories,
        meal_type=meal_type,
        log_date=date.today(),
        user_id=current_user.id,
        serving_size=serving_size,
        protein=protein,
        carbs=carbs,
        fat=fat,
        fiber=fiber,
        calcium=calcium,
        iron=iron
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
