from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

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

    # add this column
    calorie_goal = db.Column(db.Integer, nullable=True)

class CalorieLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    food_name = db.Column(db.String(100), nullable=False)
    calories = db.Column(db.Integer, nullable=False)
    meal_type = db.Column(db.String(20), nullable=False)
    log_date = db.Column(db.Date, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
