import os
from datetime import datetime
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, 
    url_for, flash, session, jsonify
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# --- Configuration ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_secret_key_here')

# PostgreSQL Database URI Configuration
# Replace 'username', 'password', 'localhost', '5432', and 'expense_db' with your PostgreSQL credentials in pgAdmin
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASS = os.environ.get('DB_PASS', 'postgres')
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_PORT = os.environ.get('DB_PORT', '5432')
DB_NAME = os.environ.get('DB_NAME', 'expense_db')

app.config['SQLALCHEMY_DATABASE_URI'] = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- Database Models ---[cite: 1]

class User(db.Model):
    """Users Table[cite: 1]"""
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    categories = db.relationship('Category', backref='user', lazy=True, cascade="all, delete-orphan")
    expenses = db.relationship('Expense', backref='user', lazy=True, cascade="all, delete-orphan")

class Category(db.Model):
    """Categories Table[cite: 1]"""
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    monthly_budget = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)

    # Relationships
    expenses = db.relationship('Expense', backref='category', lazy=True, cascade="all, delete-orphan")

class Expense(db.Model):
    """Expenses Table[cite: 1]"""
    __tablename__ = 'expenses'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    description = db.Column(db.Text, nullable=True)
    expense_date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# --- Helper Decorator ---

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Authentication Routes ---[cite: 1]

@app.route('/register', methods=['GET', 'POST'])
@app.route('/auth/register', methods=['POST'])
def register():
    """Handles User Registration[cite: 1]"""
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')

        if not name or not email or not password:
            flash("All fields are required.", "danger")
            return redirect(url_for('register'))

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Email address already registered.", "warning")
            return redirect(url_for('register'))

        # Hash password and create user[cite: 1]
        hashed_pw = generate_password_hash(password, method='scrypt')
        new_user = User(name=name, email=email, password_hash=hashed_pw)
        db.session.add(new_user)
        db.session.commit()

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
@app.route('/auth/login', methods=['POST'])
def login():
    """Handles User Login[cite: 1]"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['user_name'] = user.name
            flash("Logged in successfully!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid email or password.", "danger")
            return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logs out the current user"""
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

# --- Dashboard & Expense Routes ---[cite: 1]

@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard view displaying list of expenses and monthly budget summary[cite: 1]"""
    user_id = session['user_id']
    categories = Category.query.filter_by(user_id=user_id).all()
    expenses = Expense.query.filter_by(user_id=user_id).order_by(Expense.expense_date.desc()).all()

    # Calculate Budget Summaries[cite: 1]
    now = datetime.utcnow()
    budget_summaries = []
    
    for cat in categories:
        # Sum total expenses for this category in the current month[cite: 1]
        total_spent = db.session.query(db.func.coalesce(db.func.sum(Expense.amount), 0)).filter(
            Expense.category_id == cat.id,
            Expense.user_id == user_id,
            db.extract('year', Expense.expense_date) == now.year,
            db.extract('month', Expense.expense_date) == now.month
        ).scalar()

        budget = float(cat.monthly_budget)
        spent = float(total_spent)
        percentage = (spent / budget * 100) if budget > 0 else 0

        budget_summaries.append({
            'category': cat,
            'spent': spent,
            'budget': budget,
            'percentage': round(percentage, 1),
            'is_over_budget': spent > budget if budget > 0 else False
        })

    return render_template('dashboard.html', 
                           expenses=expenses, 
                           categories=categories, 
                           budget_summaries=budget_summaries)

# --- Category Routes ---[cite: 1]

@app.route('/categories', methods=['POST'])
@login_required
def add_category():
    """Creates a category with a monthly budget[cite: 1]"""
    user_id = session['user_id']
    name = request.form.get('name')
    monthly_budget = request.form.get('monthly_budget', 0.0)

    if not name:
        flash("Category name is required.", "danger")
        return redirect(url_for('dashboard'))

    category = Category(user_id=user_id, name=name, monthly_budget=monthly_budget)
    db.session.add(category)
    db.session.commit()

    flash("Category created successfully!", "success")
    return redirect(url_for('dashboard'))


@app.route('/categories/summary')
@login_required
def categories_summary():
    """GET /categories/summary - Returns total spent vs budget per category[cite: 1]"""
    user_id = session['user_id']
    now = datetime.utcnow()
    categories = Category.query.filter_by(user_id=user_id).all()

    summary_data = []
    for cat in categories:
        total_spent = db.session.query(db.func.coalesce(db.func.sum(Expense.amount), 0)).filter(
            Expense.category_id == cat.id,
            Expense.user_id == user_id,
            db.extract('year', Expense.expense_date) == now.year,
            db.extract('month', Expense.expense_date) == now.month
        ).scalar()

        summary_data.append({
            'id': cat.id,
            'name': cat.name,
            'monthly_budget': float(cat.monthly_budget),
            'total_spent': float(total_spent)
        })

    return jsonify(summary_data)

# --- Expense CRUD Routes ---[cite: 1]

@app.route('/expenses', methods=['POST'])
@app.route('/expenses/add', methods=['GET', 'POST'])
@login_required
def add_expense():
    """Creates a new expense record[cite: 1]"""
    user_id = session['user_id']

    if request.method == 'POST':
        category_id = request.form.get('category_id')
        amount = request.form.get('amount')
        description = request.form.get('description')
        expense_date_str = request.form.get('expense_date')

        if not category_id or not amount:
            flash("Category and amount are required.", "danger")
            return redirect(url_for('add_expense'))

        expense_date = datetime.strptime(expense_date_str, '%Y-%m-%d').date() if expense_date_str else datetime.utcnow().date()

        expense = Expense(
            user_id=user_id,
            category_id=category_id,
            amount=amount,
            description=description,
            expense_date=expense_date
        )
        db.session.add(expense)
        db.session.commit()

        flash("Expense added successfully!", "success")
        return redirect(url_for('dashboard'))

    categories = Category.query.filter_by(user_id=user_id).all()
    return render_template('expense_form.html', categories=categories, expense=None)


@app.route('/expenses/<int:expense_id>/edit', methods=['GET', 'POST', 'PATCH'])
@login_required
def edit_expense(expense_id):
    """Edits an existing expense (checks ownership)[cite: 1]"""
    user_id = session['user_id']
    expense = Expense.query.filter_by(id=expense_id, user_id=user_id).first_or_404()

    if request.method in ['POST', 'PATCH']:
        category_id = request.form.get('category_id') or request.json.get('category_id')
        amount = request.form.get('amount') or request.json.get('amount')
        description = request.form.get('description') or request.json.get('description')
        expense_date_str = request.form.get('expense_date') or request.json.get('expense_date')

        if category_id:
            expense.category_id = category_id
        if amount:
            expense.amount = amount
        if description is not None:
            expense.description = description
        if expense_date_str:
            expense.expense_date = datetime.strptime(expense_date_str, '%Y-%m-%d').date()

        db.session.commit()
        
        if request.headers.get('Content-Type') == 'application/json':
            return jsonify({'message': 'Expense updated successfully'})
            
        flash("Expense updated successfully!", "success")
        return redirect(url_for('dashboard'))

    categories = Category.query.filter_by(user_id=user_id).all()
    return render_template('expense_form.html', categories=categories, expense=expense)


@app.route('/expenses/<int:expense_id>/delete', methods=['POST', 'DELETE'])
@login_required
def delete_expense(expense_id):
    """Removes an expense record (checks ownership)[cite: 1]"""
    user_id = session['user_id']
    expense = Expense.query.filter_by(id=expense_id, user_id=user_id).first_or_404()

    db.session.delete(expense)
    db.session.commit()

    if request.headers.get('Content-Type') == 'application/json':
        return jsonify({'message': 'Expense deleted successfully'})

    flash("Expense removed successfully!", "info")
    return redirect(url_for('dashboard'))

# --- Search & Filter Routes ---[cite: 1]

@app.route('/expenses/search', methods=['GET'])
@login_required
def search_expenses():
    """Filters expenses dynamically based on parameters passed[cite: 1]"""
    user_id = session['user_id']
    query = Expense.query.filter_by(user_id=user_id)

    # Dynamic SQL WHERE filters[cite: 1]
    category_id = request.args.get('category')
    min_amount = request.args.get('min_amount')
    max_amount = request.args.get('max_amount')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if category_id:
        query = query.filter(Expense.category_id == category_id)
    if min_amount:
        query = query.filter(Expense.amount >= float(min_amount))
    if max_amount:
        query = query.filter(Expense.amount <= float(max_amount))
    if start_date:
        query = query.filter(Expense.expense_date >= datetime.strptime(start_date, '%Y-%m-%d').date())
    if end_date:
        query = query.filter(Expense.expense_date <= datetime.strptime(end_date, '%Y-%m-%d').date())

    filtered_expenses = query.order_by(Expense.expense_date.desc()).all()
    categories = Category.query.filter_by(user_id=user_id).all()

    # If requested via API/Fetch
    if request.headers.get('Accept') == 'application/json':
        return jsonify([{
            'id': e.id,
            'category_id': e.category_id,
            'category_name': e.category.name,
            'amount': float(e.amount),
            'description': e.description,
            'expense_date': e.expense_date.strftime('%Y-%m-%d')
        } for e in filtered_expenses])

    return render_template('dashboard.html', expenses=filtered_expenses, categories=categories, budget_summaries=[])

# --- Initialization ---

if __name__ == '__main__':
    with app.app_context():
        # Creates tables in pgAdmin4 database if they don't exist
        db.create_all()
    app.run(debug=True, port=5000)