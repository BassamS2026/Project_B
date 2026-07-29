from app.database import db, User, Category
from flask_bcrypt import Bcrypt

bcrypt = Bcrypt()

def create_user(email: str, password: str, name: str):
    """
    Hashes the password, creates a new user, and initializes default categories.
    Returns: (user, error_message)
    """
    # Check for duplicate email
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return None, "Email is already registered."

    # Hash password and save user
    password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    new_user = User(email=email, password_hash=password_hash, name=name)
    
    db.session.add(new_user)
    db.session.commit()

    # Seed default categories for expense tracking
    default_categories = ['Food & Dining', 'Transportation', 'Utilities', 'Entertainment', 'Shopping']
    for cat_name in default_categories:
        db.session.add(Category(user_id=new_user.id, name=cat_name, monthly_budget=500.0))
    db.session.commit()

    return new_user, None


def validate_user_credentials(email: str, password: str):
    """
    Validates user email and password against stored hash.
    Returns: (user, error_message)
    """
    user = User.query.filter_by(email=email).first()
    if not user or not bcrypt.check_password_hash(user.password_hash, password):
        return None, "Invalid email or password."

    return user, None