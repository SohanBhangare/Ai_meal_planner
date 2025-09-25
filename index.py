from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from datetime import date
import pandas as pd
import os
import meal_planner


from models import db, User, CalorieLog

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

# ----------------------------- Load CSVs for calorie lookup -----------------------------
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
        if "calories" not in df.columns:
            df["calories"] = 0
        df["calories"] = pd.to_numeric(df["calories"], errors="coerce").fillna(0).astype(int)
        all_foods = pd.concat([all_foods, df], ignore_index=True)

# ----------------------------- Routes -----------------------------
@app.route("/")
def home():
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        preference = request.form.get("preference", "veg")
        goal = request.form.get("goal", "maintain")

        if User.query.filter_by(username=username).first():
            return "User already exists!"

        # set calorie goal by user goal
        if goal == "loss":
            calorie_goal = 1800
        elif goal == "gain":
            calorie_goal = 2500
        else:
            calorie_goal = 2000

        hashed_pw = bcrypt.generate_password_hash(password).decode("utf-8")
        new_user = User(username=username, password=hashed_pw,
                        preference=preference, goal=goal,
                        calorie_goal=calorie_goal)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for("login"))

    return render_template("register.html")


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

@app.route("/dashboard")
@login_required
def dashboard():
    logs = CalorieLog.query.filter_by(user_id=current_user.id, log_date=date.today()).all()
    total_calories = sum(log.calories for log in logs)

    # Check if user has completed profile
    if not all([current_user.height, current_user.weight, current_user.age, current_user.activity_level, current_user.preference, current_user.goal]):
        return redirect(url_for("profile"))

    # For now, we'll just use a default daily_calories value or calculate from your logic
    daily_calories = 2000  # you can adjust based on user.goal if you want
    meals = meal_planner.generate_daily_meal_plan(daily_calories, current_user.preference)

    return render_template("dashboard.html", user=current_user, today=date.today(), logs=logs, total_calories=total_calories, meals=meals)


@app.route("/log", methods=["POST"])
@login_required
def log_food():
    food_name = request.form["food_name"]
    meal_type = request.form["meal_type"]

    match = all_foods[all_foods["food_name"].str.lower() == food_name.lower()]
    calories = int(match.iloc[0]["calories"]) if not match.empty else 0

    new_log = CalorieLog(
        food_name=food_name,
        calories=calories,
        meal_type=meal_type,
        log_date=date.today(),
        user_id=current_user.id
    )
    db.session.add(new_log)
    db.session.commit()
    return redirect(url_for("dashboard"))

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        current_user.height = float(request.form["height"])
        current_user.weight = float(request.form["weight"])
        current_user.age = int(request.form["age"])
        current_user.gender = request.form["gender"]
        current_user.activity_level = request.form["activity_level"]
        current_user.preference = request.form["preference"]
        current_user.goal = request.form["goal"]

        db.session.commit()
        return redirect(url_for("dashboard"))

    return render_template("profile.html", user=current_user)


# ----------------------------- Run -----------------------------
if __name__ == "__main__":
    with app.app_context():
        # Drop all existing tables (WARNING: deletes all data!)
        db.drop_all()
        # Recreate tables according to your models
        db.create_all()
    app.run(debug=True)

