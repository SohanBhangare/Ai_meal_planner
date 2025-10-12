from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import date

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

    # personal info
    height = db.Column(db.Float, nullable=True)
    weight = db.Column(db.Float, nullable=True)
    age = db.Column(db.Integer, nullable=True)
    gender = db.Column(db.String(10), nullable=True)
    activity_level = db.Column(db.String(20), nullable=True)
    preference = db.Column(db.String(10), nullable=True, default="veg")
    goal = db.Column(db.String(20), nullable=True, default="maintain")

    # calorie goal
    calorie_goal = db.Column(db.Integer, nullable=True)


class CalorieLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    food_name = db.Column(db.String(100), nullable=False)
    calories = db.Column(db.Integer, nullable=False)
    meal_type = db.Column(db.String(20), nullable=False)
    log_date = db.Column(db.Date, nullable=False, default=date.today)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    
    # NEW: serving size
    serving_size = db.Column(db.Float, default=1.0)  # number of servings

    # optional: you can also store macros per serving if needed
    protein = db.Column(db.Float, default=0)
    carbs = db.Column(db.Float, default=0)
    fat = db.Column(db.Float, default=0)
    fiber = db.Column(db.Float, default=0)
    calcium = db.Column(db.Float, default=0)
    iron = db.Column(db.Float, default=0)


class DailyStats(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=date.today)
    water_intake = db.Column(db.Integer, default=0)  # in ml
    steps = db.Column(db.Integer, default=0)
    weight = db.Column(db.Float, nullable=True)  # 👈 Added to track daily weight
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
