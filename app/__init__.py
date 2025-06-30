from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
import os

# Initialize Flask app and load configurations
load_dotenv()
app = Flask(__name__, template_folder="../templates", static_folder="../static")
app.config.from_object('app.config.Config')

# Initialize database
db = SQLAlchemy(app)

# Create database tables if they don't exist
with app.app_context():
    db.create_all()

# Import routes to register them with the app
from app import routes
