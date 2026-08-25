import pymysql

pymysql.install_as_MySQLdb()

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify

import bcrypt

import re

from datetime import datetime, timedelta

from config import Config

from functools import wraps

app = Flask(__name__)

# --- Custom Jinja Filter for Indian Rupee Formatting ---

def inr_format(value):

    try:

        if value is None: return "0"

        is_negative = float(value) < 0

        val = abs(int(float(value)))

        s = str(val)

        if len(s) <= 3:

            res = s

        else:

            res = s[-3:]

            s = s[:-3]

            while len(s) > 2:

                res = s[-2:] + ',' + res

                s = s[:-2]

            if s:

                res = s + ',' + res

        return ("-" if is_negative else "") + res

    except:

        return str(value)

app.jinja_env.filters['inr_format'] = inr_format

app.config.from_object(Config)

# Starts database and tables

def init_db():
    ssl_config = {}
    host = app.config.get('MYSQL_HOST', '')
    if app.config.get('MYSQL_SSL') or 'tidbcloud.com' in host:
        ssl_config = {
            'ssl': {
                'check_hostname': True,
                'verify_identity': True
            }
        }

        

    try:

        conn = pymysql.connect(

            host=app.config['MYSQL_HOST'],

            port=int(app.config['MYSQL_PORT']),

            user=app.config['MYSQL_USER'],

            password=app.config['MYSQL_PASSWORD'],

            autocommit=True,

            **ssl_config

        )

        with conn.cursor() as cur:

            # Dynamically use MYSQL_DB

            db_name = app.config['MYSQL_DB']

            cur.execute(f"CREATE DATABASE IF NOT EXISTS {db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")

        conn.close()

        

        conn = pymysql.connect(

            host=app.config['MYSQL_HOST'],

            port=int(app.config['MYSQL_PORT']),

            user=app.config['MYSQL_USER'],

            password=app.config['MYSQL_PASSWORD'],

            database=app.config['MYSQL_DB'],

            autocommit=True,

            **ssl_config

        )

        with conn.cursor() as cur:

            cur.execute('''

                CREATE TABLE IF NOT EXISTS users (

                  id          INT AUTO_INCREMENT PRIMARY KEY,

                  name        VARCHAR(100)  NOT NULL,

                  email       VARCHAR(100)  NOT NULL UNIQUE,

                  password    VARCHAR(255)  NOT NULL,

                  created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP

                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

            ''')

            cur.execute('''

                CREATE TABLE IF NOT EXISTS income (

                  id          INT AUTO_INCREMENT PRIMARY KEY,

                  user_id     INT           NOT NULL,

                  source      VARCHAR(100)  NOT NULL,

                  amount      DECIMAL(10,2) NOT NULL,

                  income_date DATE          NOT NULL,

                  notes       VARCHAR(255),

                  created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE

                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

            ''')

            cur.execute('''

                CREATE TABLE IF NOT EXISTS expenses (

                  id           INT AUTO_INCREMENT PRIMARY KEY,

                  user_id      INT           NOT NULL,

                  category     VARCHAR(100)  NOT NULL,

                  amount       DECIMAL(10,2) NOT NULL,

                  expense_date DATE          NOT NULL,

                  notes        VARCHAR(255),

                  created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE

                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

            ''')

            cur.execute('''

                CREATE TABLE IF NOT EXISTS budget (

                  id           INT AUTO_INCREMENT PRIMARY KEY,

                  user_id      INT           NOT NULL,

                  category     VARCHAR(100)  NOT NULL,

                  limit_amount DECIMAL(10,2) NOT NULL,

                  month        INT           NOT NULL,

                  year         INT           NOT NULL,

                  goal_id      INT           NULL,

                  created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,

                  UNIQUE KEY unique_budget_per_month (user_id, category, month, year)

                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

            ''')

            cur.execute('''

                CREATE TABLE IF NOT EXISTS investments (

                  id            INT AUTO_INCREMENT PRIMARY KEY,

                  user_id       INT           NOT NULL,

                  source        VARCHAR(100)  NOT NULL,

                  amount        DECIMAL(10,2) NOT NULL,

                  invest_date   DATE          NOT NULL,

                  invest_type   VARCHAR(50)   DEFAULT 'General',

                  notes         VARCHAR(255),

                  created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE

                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

            ''')

            cur.execute('''

                CREATE TABLE IF NOT EXISTS goals (

                  id              INT AUTO_INCREMENT PRIMARY KEY,

                  user_id         INT           NOT NULL,

                  goal_name       VARCHAR(150)  NOT NULL,

                  goal_type       VARCHAR(100),

                  description     TEXT,

                  target_amount   DECIMAL(12,2) NOT NULL DEFAULT 0.00,

                  current_amount  DECIMAL(12,2) NOT NULL DEFAULT 0.00,

                  start_date      DATE,

                  target_date     DATE,

                  category        VARCHAR(50)   DEFAULT 'Personal',

                  priority        VARCHAR(20)   DEFAULT 'Medium',

                  status          VARCHAR(20)   NOT NULL DEFAULT 'Active',

                  notes           TEXT,

                  created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                  updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

                  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE

                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

            ''')

            cur.execute('''

                CREATE TABLE IF NOT EXISTS goal_parts (

                  id              INT AUTO_INCREMENT PRIMARY KEY,

                  goal_id         INT           NOT NULL,

                  part_name       VARCHAR(150)  NOT NULL,

                  target_amount   DECIMAL(12,2) NOT NULL DEFAULT 0.00,

                  saved_amount    DECIMAL(12,2) NOT NULL DEFAULT 0.00,

                  due_date        DATE,

                  status          VARCHAR(20)   NOT NULL DEFAULT 'Pending',

                  created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                  FOREIGN KEY (goal_id) REFERENCES goals(id) ON DELETE CASCADE

                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

            ''')

            cur.execute('''

                CREATE TABLE IF NOT EXISTS savings_goals (

                  id              INT AUTO_INCREMENT PRIMARY KEY,

                  goal_id         INT           NOT NULL,

                  amount          DECIMAL(12,2) NOT NULL,

                  saving_date     DATE          NOT NULL,

                  note            VARCHAR(255),

                  created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                  FOREIGN KEY (goal_id) REFERENCES goals(id) ON DELETE CASCADE

                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

            ''')

            cur.execute('''

                CREATE TABLE IF NOT EXISTS user_profile (

                  id                          INT AUTO_INCREMENT PRIMARY KEY,

                  user_id                     INT NOT NULL UNIQUE,

                  phone                       VARCHAR(20),

                  currency                    VARCHAR(10) DEFAULT '₹',

                  monthly_saving_capacity     DECIMAL(12,2) DEFAULT 0.00,

                  monthly_investment_capacity DECIMAL(12,2) DEFAULT 0.00,

                  notes                       TEXT,

                  created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                  updated_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

                  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE

                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

                        ''')

            # Add profile_pic column to user_profile if it doesn't exist
            try:
                cur.execute("ALTER TABLE user_profile ADD COLUMN profile_pic VARCHAR(255) DEFAULT NULL")
            except Exception:
                pass

        print("SUCCESS: Database 'finsight' and all tables verified!")

        # Migration: add goal_id to budget if missing

        try:

            with conn.cursor() as cur:

                cur.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME='budget' AND COLUMN_NAME='goal_id'", (app.config['MYSQL_DB'],))

                if not cur.fetchone():

                    cur.execute("ALTER TABLE budget ADD COLUMN goal_id INT NULL")

                    print("Migrated: budget.goal_id column added.")

        except Exception as me:

            print("Migration warning:", me)

        # Create alerts table

        try:

            with conn.cursor() as cur:

                cur.execute('''

                    CREATE TABLE IF NOT EXISTS alerts (

                      id           INT AUTO_INCREMENT PRIMARY KEY,

                      user_id      INT          NOT NULL,

                      alert_type   VARCHAR(60)  NOT NULL,

                      title        VARCHAR(200) NOT NULL,

                      message      TEXT,

                      is_read      TINYINT(1)   DEFAULT 0,

                      severity     VARCHAR(20)  DEFAULT 'info',

                      trigger_ref  VARCHAR(100),

                      created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE

                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

                ''')

        except Exception as ae:

            print("Alerts table warning:", ae)

    except Exception as e:

        print('ERROR: Database initialization error:', e)

init_db()

# Gets database connection

def get_db_connection():
    ssl_config = {}
    host = app.config.get('MYSQL_HOST', '')
    if app.config.get('MYSQL_SSL') or 'tidbcloud.com' in host:
        ssl_config = {
            'ssl': {
                'check_hostname': True,
                'verify_identity': True
            }
        }
    return pymysql.connect(
        host=app.config['MYSQL_HOST'],
        port=int(app.config['MYSQL_PORT']),
        user=app.config['MYSQL_USER'],
        password=app.config['MYSQL_PASSWORD'],
        database=app.config['MYSQL_DB'],
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        **ssl_config
    )


# Checks if user is logged in

def login_required(f):

    @wraps(f)

    def decorated(*args, **kwargs):

        if 'user_id' not in session:

            flash('Please log in to access this page.', 'warning')

            return redirect(url_for('login_page'))

        return f(*args, **kwargs)

    return decorated

# Checks if email is valid

def is_valid_email(email: str) -> bool:

    pattern = '^[\\w\\.\\+\\-]+@[\\w\\-]+\\.[a-zA-Z]{2,}$'

    return bool(re.match(pattern, email))

# Checks if password is strong

def is_strong_password(password: str) -> bool:

    if len(password) < 8:

        return False

    if not re.search('[A-Z]', password):

        return False

    if not re.search('[a-z]', password):

        return False

    if not re.search('\\d', password):

        return False

    if not re.search('[!@#$%^&*(),.?":{}|<>_\\-\\[\\]\\/\\\\]', password):

        return False

    return True

@app.route('/')

@app.route('/home')

# Shows home page

def home():

    if 'user_id' in session:

        return redirect(url_for('dashboard'))

    return render_template('home.html')

# Alias for home page

def index():

    return home()

@app.route('/login', methods=['GET', 'POST'])

# Handles user login

def login_page():

    if 'user_id' in session:

        return redirect(url_for('dashboard'))

    if request.method == 'POST':

        email = request.form.get('email', '').strip().lower()

        password = request.form.get('password', '').strip()

        remember = request.form.get('remember')

        if not email or not password:

            flash('All fields are required.', 'danger')

            return render_template('login.html')

        if not is_valid_email(email):

            flash('Please enter a valid email address.', 'danger')

            return render_template('login.html')

        try:

            conn = get_db_connection()

            with conn.cursor() as cur:

                cur.execute('SELECT id, name, email, password FROM users WHERE email = %s', (email,))

                user = cur.fetchone()

            conn.close()

        except Exception as e:

            print('DB Error during login:', e)

            flash(f'Database connection error: {e}', 'danger')

            return render_template('login.html')

        if user and bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):

            session['user_id'] = user['id']

            session['user_name'] = user['name']

            session['user_email'] = user['email']

            if remember:

                app.permanent_session_lifetime = timedelta(days=30)

                session.permanent = True

            flash(f"Welcome back, {user['name']}! 🎉", 'success')

            return redirect(url_for('dashboard'))

        else:

            flash('Invalid email or password. Please try again.', 'danger')

            return render_template('login.html')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])

# Handles user registration

def register():

    if 'user_id' in session:

        return redirect(url_for('dashboard'))

    if request.method == 'POST':

        name = request.form.get('name', '').strip()

        email = request.form.get('email', '').strip().lower()

        password = request.form.get('password', '').strip()

        confirm_password = request.form.get('confirm_password', '').strip()

        errors = []

        if not name:

            errors.append('Full name is required.')

        if not email:

            errors.append('Email address is required.')

        elif not is_valid_email(email):

            errors.append('Please enter a valid email address.')

        if not password:

            errors.append('Password is required.')

        elif not is_strong_password(password):

            errors.append('Password must be at least 8 characters with uppercase, lowercase, number, and special character.')

        if password != confirm_password:

            errors.append('Passwords do not match.')

        if errors:

            for err in errors:

                flash(err, 'danger')

            return render_template('register.html')

        try:

            conn = get_db_connection()

            with conn.cursor() as cur:

                cur.execute('SELECT id FROM users WHERE email = %s', (email,))

                existing = cur.fetchone()

                if existing:

                    conn.close()

                    flash('An account with this email already exists. Please log in.', 'warning')

                    return render_template('register.html')

                hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=12))

                cur.execute('INSERT INTO users (name, email, password) VALUES (%s, %s, %s)', (name, email, hashed_pw.decode('utf-8')))

            conn.close()

        except Exception as e:

            print('DB ERROR DURING REGISTRATION:', e)

            flash(f'Registration failed: {e}', 'danger')

            return render_template('register.html')

        flash('Account created successfully! Please log in.', 'success')

        return redirect(url_for('login_page'))

    return render_template('register.html')

@app.route('/dashboard')

@login_required

# Shows dashboard page

def dashboard():

    user_id = session.get('user_id')

    user_name = session.get('user_name', 'User')

    user_email = session.get('user_email', '')

    recent_goals = []

    try:

        conn = get_db_connection()

        with conn.cursor() as cur:

            cur.execute('SELECT * FROM goals WHERE user_id = %s ORDER BY updated_at DESC LIMIT 5', (user_id,))

            rows = cur.fetchall()

            recent_goals = [process_goal(row) for row in rows]

        conn.close()

    except Exception as e:

        print("Error fetching dashboard goals:", e)

    return render_template('dashboard.html', user_name=user_name, user_email=user_email, recent_goals=recent_goals)

@app.route('/logout')

@login_required

# Logs out the user

def logout():

    session.clear()

    flash('You have been logged out successfully.', 'info')

    return redirect(url_for('home'))

@app.route('/budget')

@login_required

# Alias for budget view

def budget():

    user_name = session.get('user_name', 'User')

    user_email = session.get('user_email', '')

    return render_template('dashboard.html', user_name=user_name, user_email=user_email)

@app.route('/forgot-password')

# Forgot password link

def forgot_password():

    flash('Password reset feature coming soon. Contact support for help.', 'info')

    return redirect(url_for('login_page'))

@app.route('/api/dashboard-summary')

@login_required

# API: gets dashboard stats

def api_dashboard_summary():

    user_id = session.get('user_id')

    try:

        conn = get_db_connection()

        with conn.cursor() as cur:

            cur.execute('SELECT COALESCE(SUM(amount), 0) AS total FROM income WHERE user_id = %s', (user_id,))

            total_income = float(cur.fetchone()['total'])

            cur.execute('SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE user_id = %s', (user_id,))

            total_expenses = float(cur.fetchone()['total'])

            cur.execute('SELECT COALESCE(SUM(amount), 0) AS total FROM investments WHERE user_id = %s', (user_id,))

            total_investments = float(cur.fetchone()['total'])

        conn.close()

        total_savings = min(total_income * 0.25, max(0, total_income - total_expenses - total_investments))

        remaining_balance = max(0, total_income - total_expenses - total_investments - total_savings)

        

        if total_income > 0:

            expenses_pct = round(total_expenses / total_income * 100)

            savings_pct = round(total_savings / total_income * 100)

            investments_pct = round(total_investments / total_income * 100)

            remaining_pct = max(0, 100 - expenses_pct - savings_pct - investments_pct)

        else:

            expenses_pct = savings_pct = investments_pct = remaining_pct = 0

            

        prev_month = datetime.now().replace(day=1) - timedelta(days=1)

        try:

            conn2 = get_db_connection()

            with conn2.cursor() as cur:

                cur.execute('SELECT COALESCE(SUM(amount),0) AS t FROM income WHERE user_id=%s AND MONTH(income_date)=MONTH(CURDATE()) AND YEAR(income_date)=YEAR(CURDATE())', (user_id,))

                cur_income = float(cur.fetchone()['t'])

                cur.execute('SELECT COALESCE(SUM(amount),0) AS t FROM income WHERE user_id=%s AND MONTH(income_date)=%s AND YEAR(income_date)=%s', (user_id, prev_month.month, prev_month.year))

                prev_income = float(cur.fetchone()['t'])

                cur.execute('SELECT COALESCE(SUM(amount),0) AS t FROM expenses WHERE user_id=%s AND MONTH(expense_date)=MONTH(CURDATE()) AND YEAR(expense_date)=YEAR(CURDATE())', (user_id,))

                cur_expenses = float(cur.fetchone()['t'])

                cur.execute('SELECT COALESCE(SUM(amount),0) AS t FROM expenses WHERE user_id=%s AND MONTH(expense_date)=%s AND YEAR(expense_date)=%s', (user_id, prev_month.month, prev_month.year))

                prev_expenses = float(cur.fetchone()['t'])

                cur.execute('SELECT COALESCE(SUM(amount),0) AS t FROM investments WHERE user_id=%s AND MONTH(invest_date)=MONTH(CURDATE()) AND YEAR(invest_date)=YEAR(CURDATE())', (user_id,))

                cur_invest = float(cur.fetchone()['t'])

                cur.execute('SELECT COALESCE(SUM(amount),0) AS t FROM investments WHERE user_id=%s AND MONTH(invest_date)=%s AND YEAR(invest_date)=%s', (user_id, prev_month.month, prev_month.year))

                prev_invest = float(cur.fetchone()['t'])

            conn2.close()

            def pct_change(cur_val, prev_val):

                if prev_val > 0:

                    return round((cur_val - prev_val) / prev_val * 100, 1)

                return 0

            income_change = pct_change(cur_income, prev_income)

            expenses_change = pct_change(cur_expenses, prev_expenses)

            invest_change = pct_change(cur_invest, prev_invest)

            cur_savings = min(cur_income * 0.25, max(0, cur_income - cur_expenses - cur_invest))

            prev_savings = min(prev_income * 0.25, max(0, prev_income - prev_expenses - prev_invest))

            savings_change = pct_change(cur_savings, prev_savings)

        except:

            income_change = expenses_change = savings_change = invest_change = 0

        return jsonify({

            'income':      {'total': total_income,      'change': income_change},

            'expenses':    {'total': total_expenses,    'change': expenses_change},

            'savings':     {'total': total_savings,     'change': savings_change},

            'investments': {'total': total_investments, 'change': invest_change},

            'remaining':   {'total': remaining_balance},

            'chart_segments': {

                'expenses': expenses_pct,

                'savings': savings_pct,

                'investments': investments_pct,

                'remaining': remaining_pct

            }

        })

    except Exception as e:

        return (jsonify({'error': str(e)}), 500)

@app.route('/api/user-profile')

@login_required

# API: gets user profile

def api_user_profile():

    return jsonify({'name': session.get('user_name', 'User'), 'email': session.get('user_email', ''), 'role': 'Premium User', 'member_since': 'Active', 'account_status': 'Verified', 'financial_health_score': 100})

@app.route('/api/recent-transactions')

@login_required

# API: gets recent transactions

def api_recent_transactions():

    user_id = session.get('user_id')

    try:

        conn = get_db_connection()

        with conn.cursor() as cur:

            cur.execute("SELECT id, source AS title, 'Income' AS category, amount, income_date AS date, 'income' AS type, created_at FROM income WHERE user_id = %s", (user_id,))

            incomes = cur.fetchall()

            cur.execute("SELECT id, category AS title, 'Expense' AS category, amount, expense_date AS date, 'expense' AS type, created_at FROM expenses WHERE user_id = %s", (user_id,))

            expenses = cur.fetchall()

            cur.execute("SELECT id, source AS title, invest_type AS category, amount, invest_date AS date, 'investment' AS type, created_at FROM investments WHERE user_id = %s", (user_id,))

            investments = cur.fetchall()

        conn.close()

        transactions = incomes + expenses + investments

        transactions.sort(key=lambda x: x['created_at'], reverse=True)

        recent = transactions[:8]

        result = []

        for t in recent:

            result.append({'title': t['title'], 'category': t['category'], 'amount': float(t['amount']), 'type': t['type'], 'date': str(t['date'])})

        return jsonify(result)

    except Exception as e:

        return (jsonify({'error': str(e)}), 500)

@app.route('/api/monthly-spending')

@login_required

# API: gets monthly spending data

def api_monthly_spending():

    user_id = session.get('user_id')

    try:

        conn = get_db_connection()

        with conn.cursor() as cur:

            cur.execute('''

                SELECT MONTHNAME(expense_date) AS month, SUM(amount) AS total 

                FROM expenses 

                WHERE user_id = %s AND expense_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)

                GROUP BY month 

                ORDER BY MIN(expense_date) ASC

            ''', (user_id,))

            rows = cur.fetchall()

        conn.close()

        labels = [r['month'][:3] for r in rows] if rows else ['No Data']

        values = [float(r['total']) for r in rows] if rows else [0]

        return jsonify({'labels': labels, 'values': values})

    except Exception as e:

        return (jsonify({'error': str(e)}), 500)

@app.route('/api/insights')

@login_required

# API: gets smart insights

def api_insights():

    user_id = session.get('user_id')

    try:

        conn = get_db_connection()

        with conn.cursor() as cur:

            cur.execute('SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE user_id = %s AND MONTH(expense_date) = MONTH(CURDATE()) AND YEAR(expense_date) = YEAR(CURDATE())', (user_id,))

            monthly_spent = float(cur.fetchone()['total'])

            cur.execute('SELECT COALESCE(SUM(limit_amount), 0) AS total_budget FROM budget WHERE user_id = %s AND month = MONTH(CURDATE()) AND year = YEAR(CURDATE())', (user_id,))

            total_budget = float(cur.fetchone()['total_budget'])

            cur.execute('SELECT COALESCE(SUM(amount), 0) AS total FROM income WHERE user_id = %s AND MONTH(income_date) = MONTH(CURDATE()) AND YEAR(income_date) = YEAR(CURDATE())', (user_id,))

            monthly_income = float(cur.fetchone()['total'])

        conn.close()

        if total_budget > 0:

            budget_pct = min(100, round(monthly_spent / total_budget * 100))

            if budget_pct > 100:

                budget_status = 'Over Budget'

                budget_desc = f'Spending is {budget_pct - 100}% over plan'

                budget_color = '#EF4444'

            else:

                budget_status = 'On Track'

                budget_desc = f'Spending is {100 - budget_pct}% below plan'

                budget_color = '#2563EB'

        else:

            budget_pct = 0

            budget_status = 'No Budget Set'

            budget_desc = 'Create a budget to track spending'

            budget_color = '#94A3B8'

        if monthly_income > 0:

            savings = max(0, monthly_income - monthly_spent)

            savings_rate = round(savings / monthly_income * 100)

            savings_status = f'{savings_rate}% Saved'

            savings_desc = 'Savings rate this month'

        else:

            savings_rate = 0

            savings_status = '0% Saved'

            savings_desc = 'No income recorded this month'

        return jsonify([{'title': 'Budget Status', 'status': budget_status, 'description': budget_desc, 'percentage': budget_pct, 'color': budget_color}, {'title': 'Savings Rate', 'status': savings_status, 'description': savings_desc, 'percentage': savings_rate, 'color': '#10B981'}, {'title': 'Investment Growth', 'status': '+0%', 'description': 'Tracking coming soon', 'percentage': 0, 'color': '#8B5CF6'}, {'title': 'Monthly Spending', 'status': f'₹{monthly_spent:,.0f}', 'description': 'Total spent this month', 'percentage': min(100, monthly_spent / max(1, monthly_income) * 100) if monthly_income > 0 else 0, 'color': '#3B82F6'}])

    except Exception as e:

        return (jsonify({'error': str(e)}), 500)

@app.route('/view-all')

@login_required

# Placeholder: view transactions

def view_all():

    return jsonify({'message': 'Recent transactions view is ready for the next step.'})

@app.route('/view-detailed-report')

@login_required

# Placeholder: view reports

def view_detailed_report():

    return jsonify({'message': 'The detailed report page is ready to be expanded.'})

@app.route('/quick-actions/expense')

@login_required

# Placeholder: add expense

def quick_action_expense():

    return jsonify({'message': 'Expense tracking action placeholder'})

@app.route('/quick-actions/budget')

@login_required

# Placeholder: add budget

def quick_action_budget():

    return jsonify({'message': 'Budget creation action placeholder'})

@app.route('/quick-actions/investment')

@login_required

# Placeholder: add investment

def quick_action_investment():

    return jsonify({'message': 'Investment entry action placeholder'})

@app.route('/quick-actions/report')

@login_required

# Placeholder: get reports

def quick_action_report():

    return jsonify({'message': 'Report generation action placeholder'})

@app.route('/api/income', methods=['GET'])

@login_required

# API: gets income list

def api_get_income():

    user_id = session.get('user_id')

    try:

        conn = get_db_connection()

        with conn.cursor() as cur:

            cur.execute('SELECT id, source, amount, income_date, notes, created_at FROM income WHERE user_id = %s ORDER BY created_at DESC', (user_id,))

            rows = cur.fetchall()

        conn.close()

        result = []

        for row in rows:

            result.append({'id': row['id'], 'source': row['source'], 'amount': float(row['amount']), 'income_date': str(row['income_date']), 'notes': row['notes'], 'created_at': str(row['created_at'])})

        return (jsonify(result), 200)

    except Exception as e:

        return (jsonify({'error': str(e)}), 500)

@app.route('/api/income', methods=['POST'])

@login_required

# API: adds new income

def api_create_income():

    data = request.get_json()

    required = ['source', 'amount', 'income_date']

    if not all((k in data for k in required)):

        return (jsonify({'error': f'Missing required fields: {required}'}), 400)

    user_id = session.get('user_id')

    try:

        conn = get_db_connection()

        with conn.cursor() as cur:

            cur.execute('INSERT INTO income (user_id, source, amount, income_date, notes) VALUES (%s, %s, %s, %s, %s)', (user_id, data['source'], data['amount'], data['income_date'], data.get('notes', '')))

            new_id = cur.lastrowid

        conn.close()

        return (jsonify({'id': new_id, 'message': 'Income record created successfully'}), 201)

    except Exception as e:

        return (jsonify({'error': str(e)}), 500)

@app.route('/api/expenses', methods=['GET'])

@login_required

# API: gets expense list

def api_get_expenses():

    user_id = session.get('user_id')

    try:

        conn = get_db_connection()

        with conn.cursor() as cur:

            cur.execute('SELECT id, category, amount, expense_date, notes, created_at FROM expenses WHERE user_id = %s ORDER BY created_at DESC', (user_id,))

            rows = cur.fetchall()

        conn.close()

        result = []

        for row in rows:

            result.append({'id': row['id'], 'category': row['category'], 'amount': float(row['amount']), 'expense_date': str(row['expense_date']), 'notes': row['notes'], 'created_at': str(row['created_at'])})

        return (jsonify(result), 200)

    except Exception as e:

        return (jsonify({'error': str(e)}), 500)

@app.route('/api/expenses', methods=['POST'])

@login_required

# API: adds new expense

def api_create_expense():

    data = request.get_json()

    required = ['category', 'amount', 'expense_date']

    if not all((k in data for k in required)):

        return (jsonify({'error': f'Missing required fields: {required}'}), 400)

    user_id = session.get('user_id')

    try:

        conn = get_db_connection()

        with conn.cursor() as cur:

            cur.execute('INSERT INTO expenses (user_id, category, amount, expense_date, notes) VALUES (%s, %s, %s, %s, %s)', (user_id, data['category'], data['amount'], data['expense_date'], data.get('notes', '')))

            new_id = cur.lastrowid

        conn.close()

        return (jsonify({'id': new_id, 'message': 'Expense record created successfully'}), 201)

    except Exception as e:

        return (jsonify({'error': str(e)}), 500)

@app.route('/api/budget', methods=['GET'])

@login_required

# API: gets budget list

def api_get_budget():

    user_id = session.get('user_id')

    try:

        conn = get_db_connection()

        with conn.cursor() as cur:

            cur.execute('SELECT id, category, limit_amount, month, year, created_at FROM budget WHERE user_id = %s ORDER BY year DESC, month DESC', (user_id,))

            rows = cur.fetchall()

        conn.close()

        result = []

        for row in rows:

            result.append({'id': row['id'], 'category': row['category'], 'limit_amount': float(row['limit_amount']), 'month': row['month'], 'year': row['year'], 'created_at': str(row['created_at'])})

        return (jsonify(result), 200)

    except Exception as e:

        return (jsonify({'error': str(e)}), 500)

@app.route('/api/budget', methods=['POST'])

@login_required

# API: adds new budget

def api_create_budget():

    data = request.get_json()

    required = ['category', 'limit_amount', 'month', 'year']

    if not all((k in data for k in required)):

        return (jsonify({'error': f'Missing required fields: {required}'}), 400)

    user_id = session.get('user_id')

    try:

        conn = get_db_connection()

        with conn.cursor() as cur:

            cur.execute('INSERT INTO budget (user_id, category, limit_amount, month, year) VALUES (%s, %s, %s, %s, %s)', (user_id, data['category'], data['limit_amount'], data['month'], data['year']))

            new_id = cur.lastrowid

        conn.close()

        return (jsonify({'id': new_id, 'message': 'Budget record created successfully'}), 201)

    except Exception as e:

        return (jsonify({'error': str(e)}), 400)

@app.route('/finances')
@login_required
def finances():
    tab = request.args.get('tab', 'income').strip().lower()
    if tab not in ['income', 'expense', 'budget']:
        tab = 'income'

    active_goals = []
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT id, goal_name, category FROM goals WHERE user_id=%s AND status='Active' ORDER BY goal_name ASC", (session.get('user_id'),))
            active_goals = cur.fetchall()
        conn.close()
    except Exception:
        pass

    return render_template('finances.html', tab=tab, user_name=session.get('user_name', 'User'), active_goals=active_goals)

@app.route('/add-income', methods=['GET', 'POST'])
@login_required
# Form page: adds income
def add_income():
    if request.method == 'GET':
        return redirect(url_for('finances', tab='income'))

    error = None
    if request.method == 'POST':
        source = request.form.get('source', '').strip()
        amount_str = request.form.get('amount', '').strip()
        income_date = request.form.get('income_date', '').strip()
        notes = request.form.get('notes', '').strip()

        if not source or not amount_str or not income_date:
            error = 'Source, Amount, and Date are required fields.'
        else:
            try:
                amount = float(amount_str)
                if amount <= 0:
                    error = 'Amount must be a positive number greater than zero.'
            except ValueError:
                error = 'Please enter a valid numeric amount.'

        if not error:
            try:
                conn = get_db_connection()
                with conn.cursor() as cur:
                    cur.execute('INSERT INTO income (user_id, source, amount, income_date, notes) VALUES (%s, %s, %s, %s, %s)', (session.get('user_id'), source, amount, income_date, notes))
                conn.close()
                flash('Income record added successfully!', 'success')
                return redirect(url_for('finances', tab='income'))
            except Exception as e:
                error = f'Database error: {str(e)}'

    active_goals = []
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT id, goal_name, category FROM goals WHERE user_id=%s AND status='Active' ORDER BY goal_name ASC", (session.get('user_id'),))
            active_goals = cur.fetchall()
        conn.close()
    except Exception:
        pass

    return render_template('finances.html', tab='income', error=error, user_name=session.get('user_name', 'User'), active_goals=active_goals)

@app.route('/add-expense', methods=['GET', 'POST'])
@login_required
# Form page: adds expense
def add_expense():
    if request.method == 'GET':
        return redirect(url_for('finances', tab='expense'))

    error = None
    if request.method == 'POST':
        category = request.form.get('category', '').strip()
        amount_str = request.form.get('amount', '').strip()
        expense_date = request.form.get('expense_date', '').strip()
        notes = request.form.get('notes', '').strip()

        if not category or not amount_str or not expense_date:
            error = 'Category, Amount, and Date are required fields.'
        else:
            try:
                amount = float(amount_str)
                if amount <= 0:
                    error = 'Amount must be a positive number greater than zero.'
            except ValueError:
                error = 'Please enter a valid numeric amount.'

        if not error:
            try:
                conn = get_db_connection()
                with conn.cursor() as cur:
                    cur.execute('INSERT INTO expenses (user_id, category, amount, expense_date, notes) VALUES (%s, %s, %s, %s, %s)', (session.get('user_id'), category, amount, expense_date, notes))
                conn.close()
                flash('Expense record added successfully!', 'success')
                return redirect(url_for('finances', tab='expense'))
            except Exception as e:
                error = f'Database error: {str(e)}'

    active_goals = []
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT id, goal_name, category FROM goals WHERE user_id=%s AND status='Active' ORDER BY goal_name ASC", (session.get('user_id'),))
            active_goals = cur.fetchall()
        conn.close()
    except Exception:
        pass

    return render_template('finances.html', tab='expense', error=error, user_name=session.get('user_name', 'User'), active_goals=active_goals)

@app.route('/add-budget', methods=['GET', 'POST'])
@login_required
# Form page: adds budget
def add_budget():
    if request.method == 'GET':
        return redirect(url_for('finances', tab='budget'))

    error = None
    if request.method == 'POST':
        category = request.form.get('category', '').strip()
        amount_str = request.form.get('limit_amount', '').strip()
        month_str = request.form.get('month', '').strip()
        year_str = request.form.get('year', '').strip()

        if not category or not amount_str or not month_str or not year_str:
            error = 'Category, Limit Amount, Month, and Year are all required.'
        else:
            try:
                limit_amount = float(amount_str)
                month = int(month_str)
                year = int(year_str)

                if limit_amount <= 0:
                    error = 'Limit amount must be greater than zero.'
                elif not 1 <= month <= 12:
                    error = 'Month must be a number between 1 and 12.'
            except ValueError:
                error = 'Please enter valid numeric values for amount, month, and year.'

        if not error:
            try:
                goal_id = request.form.get('goal_id') or None
                if goal_id:
                    goal_id = int(goal_id)
                conn = get_db_connection()
                with conn.cursor() as cur:
                    cur.execute('INSERT INTO budget (user_id, category, limit_amount, month, year, goal_id) VALUES (%s, %s, %s, %s, %s, %s)', (session.get('user_id'), category, limit_amount, month, year, goal_id))
                conn.close()
                flash('Budget record created successfully!', 'success')
                return redirect(url_for('finances', tab='budget'))
            except Exception as e:
                error = f'Could not create budget (it may already exist for this category/month): {str(e)}'

    # Fetch active goals for the link dropdown
    active_goals = []
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT id, goal_name, category FROM goals WHERE user_id=%s AND status='Active' ORDER BY goal_name ASC", (session.get('user_id'),))
            active_goals = cur.fetchall()
        conn.close()
    except Exception:
        pass

    return render_template('finances.html', tab='budget', error=error, user_name=session.get('user_name', 'User'), active_goals=active_goals)

@app.route('/add-investment', methods=['GET', 'POST'])

@login_required

# Form page: adds investment

def add_investment():
    error = None
    user_id = session.get('user_id')
    user_name = session.get('user_name', 'User')

    if request.method == 'POST':
        source = request.form.get('source', '').strip()
        amount_str = request.form.get('amount', '').strip()
        invest_date = request.form.get('invest_date', '').strip()
        invest_type = request.form.get('invest_type', 'General').strip()
        notes = request.form.get('notes', '').strip()

        if not source or not amount_str or not invest_date:
            error = 'Source, Amount, and Date are required fields.'
        else:
            try:
                amount = float(amount_str)
                if amount <= 0:
                    error = 'Amount must be a positive number greater than zero.'
            except ValueError:
                error = 'Please enter a valid numeric amount.'

        if not error:
            try:
                conn = get_db_connection()
                with conn.cursor() as cur:
                    cur.execute(
                        'INSERT INTO investments (user_id, source, amount, invest_date, invest_type, notes) VALUES (%s, %s, %s, %s, %s, %s)',
                        (user_id, source, amount, invest_date, invest_type, notes)
                    )
                conn.close()
                flash('Investment record added successfully! 📈', 'success')
                return redirect(url_for('add_investment'))
            except Exception as e:
                error = f'Database error: {str(e)}'

    # Fetch investments
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute('SELECT id, source, amount, invest_date, invest_type, notes FROM investments WHERE user_id = %s ORDER BY invest_date DESC', (user_id,))
            rows = cur.fetchall()
        conn.close()

        investments = []
        for r in rows:
            investments.append({
                'id': r['id'],
                'source': r['source'],
                'amount': float(r['amount']),
                'invest_date': str(r['invest_date']),
                'invest_type': r['invest_type'],
                'notes': r['notes']
            })
    except Exception as e:
        print("Error fetching investments:", e)
        investments = []

        return render_template('investment.html', error=error, user_name=user_name, investments=investments)

@app.route('/api/investment/<int:invest_id>/delete', methods=['POST'])
@login_required
def delete_investment(invest_id):
    user_id = session.get('user_id')
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM investments WHERE id = %s AND user_id = %s", (invest_id, user_id))
            inv = cur.fetchone()
            if not inv:
                flash("Investment record not found or access denied.", "danger")
            else:
                cur.execute("DELETE FROM investments WHERE id = %s", (invest_id,))
                flash("Investment record deleted successfully! 🗑️", "success")
        conn.close()
    except Exception as e:
        flash(f"Error deleting investment: {str(e)}", "danger")
    return redirect(url_for('add_investment'))

@app.route('/api/balance-summary')

@login_required

# API: gets total balance

def api_balance_summary():

    user_id = session.get('user_id')

    try:

        conn = get_db_connection()

        with conn.cursor() as cur:

            cur.execute('SELECT COALESCE(SUM(amount), 0) AS total FROM income WHERE user_id = %s', (user_id,))

            total_income = float(cur.fetchone()['total'])

            cur.execute('SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE user_id = %s', (user_id,))

            total_expenses = float(cur.fetchone()['total'])

        conn.close()

        balance = total_income - total_expenses

        return (jsonify({'total_income': total_income, 'total_expenses': total_expenses, 'balance': balance}), 200)

    except Exception as e:

        return (jsonify({'error': str(e)}), 500)

@app.route('/api/reset-data', methods=['POST'])

@login_required

# API: resets all data to 0

def api_reset_data():

    user_id = session.get('user_id')

    try:

        conn = get_db_connection()

        with conn.cursor() as cur:

            cur.execute('DELETE FROM income WHERE user_id = %s', (user_id,))

            cur.execute('DELETE FROM expenses WHERE user_id = %s', (user_id,))

            cur.execute('DELETE FROM budget WHERE user_id = %s', (user_id,))

            cur.execute('DELETE FROM investments WHERE user_id = %s', (user_id,))

        conn.close()

        return jsonify({'status': 'success', 'message': 'All your data has been reset to 0.'})

    except Exception as e:

        return jsonify({'error': str(e)}), 500

# ═══════════════════════════════════════════════════════════════════

# GOAL PLANNING & PROFILE HELPERS (from Milestone 2)

# ═══════════════════════════════════════════════════════════════════

GOAL_CATEGORIES = ['Education', 'Electronics', 'Travel', 'Emergency',

                   'Vehicle', 'Personal', 'Health', 'Other']

GOAL_PRIORITIES = ['High', 'Medium', 'Low']

GOAL_STATUSES   = ['Active', 'Completed', 'On Hold']

def _parse_date(s):

    if not s:

        return None

    for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y'):

        try:

            return datetime.strptime(s, fmt).date()

        except ValueError:

            continue

    return None

def process_goal(row):

    """Convert a goal DB row → dict with all computed financial fields."""

    g = dict(row)

    target_amount  = float(g.get('target_amount') or 0)

    current_amount = float(g.get('current_amount') or 0)

    start_date_str = g.get('start_date')

    target_date_str = g.get('target_date')

    today = datetime.now().date()

    start_date  = _parse_date(str(start_date_str)) if start_date_str else None

    target_date = _parse_date(str(target_date_str)) if target_date_str else None

    remaining    = max(target_amount - current_amount, 0)

    progress_pct = min(round((current_amount / target_amount * 100), 1), 100) if target_amount > 0 else 0

    days_left = (target_date - today).days if target_date else None

    if target_date and target_date > today:

        months_left = max((target_date - today).days / 30.44, 0)

    else:

        months_left = 0

    required_monthly = round(remaining / months_left, 2) if months_left > 0 else 0

    required_weekly  = round(required_monthly / 4.33, 2) if required_monthly > 0 else 0

    # Smart status

    if current_amount >= target_amount and target_amount > 0:

        smart_status = 'Completed'

    elif start_date and target_date:

        total_days   = (target_date - start_date).days

        elapsed_days = (today - start_date).days

        if total_days > 0:

            ratio    = max(min(elapsed_days / total_days, 1.0), 0.0)

            expected = target_amount * ratio

            if current_amount >= expected * 0.90:

                smart_status = 'On Track'

            elif current_amount >= expected * 0.70:

                smart_status = 'Needs Attention'

            else:

                smart_status = 'Behind Schedule'

        else:

            smart_status = 'Behind Schedule'

    else:

        smart_status = g.get('status', 'Active')

    smart_cls    = {'On Track': 'success', 'Completed': 'success',

                    'Needs Attention': 'warning', 'Behind Schedule': 'danger'}.get(smart_status, 'secondary')

    priority_cls = {'High': 'danger', 'Medium': 'warning', 'Low': 'success'}.get(g.get('priority', 'Medium'), 'secondary')

    status_cls   = {'Active': 'primary', 'Completed': 'success', 'On Hold': 'secondary'}.get(g.get('status', 'Active'), 'secondary')

    g.update({

        'remaining_amount':        remaining,

        'progress_percentage':     progress_pct,

        'required_monthly_saving': required_monthly,

        'required_weekly_saving':  required_weekly,

        'days_left':               days_left,

        'months_left':             round(months_left, 1),

        'smart_status':            smart_status,

        'smart_status_class':      smart_cls,

        'priority_class':          priority_cls,

        'status_class':            status_cls,

    })

    return g

def process_goal_part(row):

    p = dict(row)

    target = float(p.get('target_amount') or 0)

    saved  = float(p.get('saved_amount') or 0)

    p['remaining_amount']    = max(target - saved, 0)

    p['progress_percentage'] = min(round((saved / target * 100), 1), 100) if target > 0 else 0

    p['status_class'] = {'Completed': 'success', 'In Progress': 'primary',

                         'On Hold': 'warning', 'Pending': 'secondary'}.get(p.get('status', 'Pending'), 'secondary')

    return p

# ═══════════════════════════════════════════════════════════════════

# GOALS LIST

# ═══════════════════════════════════════════════════════════════════

@app.route('/goals')

@login_required

def goals_list():

    user_id = session.get('user_id')

    search   = request.args.get('search', '').strip()

    category = request.args.get('category', '')

    status   = request.args.get('status', '')

    priority = request.args.get('priority', '')

    sort     = request.args.get('sort', 'newest')

    try:

        conn = get_db_connection()

        with conn.cursor() as cur:

            sql = 'SELECT * FROM goals WHERE user_id = %s'

            params = [user_id]

            if search:

                sql += ' AND (goal_name LIKE %s OR description LIKE %s)'

                params += [f'%{search}%', f'%{search}%']

            if category:

                sql += ' AND category = %s'

                params.append(category)

            if status:

                sql += ' AND status = %s'

                params.append(status)

            if priority:

                sql += ' AND priority = %s'

                params.append(priority)

            sort_map = {

                'newest': 'created_at DESC',

                'oldest': 'created_at ASC',

                'deadline': 'target_date ASC',

                'amount_high': 'target_amount DESC',

                'amount_low': 'target_amount ASC',

                'progress': 'current_amount/GREATEST(target_amount,1) DESC',

            }

            sql += f' ORDER BY {sort_map.get(sort, "created_at DESC")}'

            cur.execute(sql, params)

            rows = cur.fetchall()

        conn.close()

        goals = [process_goal(r) for r in rows]

    except Exception as e:

        print('Goals list error:', e)

        goals = []

    return render_template('goals.html',

                           goals=goals, categories=GOAL_CATEGORIES,

                           statuses=GOAL_STATUSES, priorities=GOAL_PRIORITIES,

                           search=search, selected_category=category,

                           selected_status=status, selected_priority=priority,

                           selected_sort=sort,

                           user_name=session.get('user_name', 'User'))

# ═══════════════════════════════════════════════════════════════════

# GOAL PLANNING (CREATE / EDIT)

# ═══════════════════════════════════════════════════════════════════

@app.route('/goal-planning', methods=['GET', 'POST'])

@login_required

def goal_planning():

    user_id = session.get('user_id')

    if request.method == 'POST':

        goal_name     = request.form.get('goal_name', '').strip()

        goal_type     = request.form.get('goal_type', '').strip()

        description   = request.form.get('description', '').strip()

        category      = request.form.get('category', 'Personal')

        priority      = request.form.get('priority', 'Medium')

        status        = request.form.get('status', 'Active')

        notes         = request.form.get('notes', '').strip()

        start_date    = request.form.get('start_date', '')

        target_date   = request.form.get('target_date', '')

        try:

            target_amount  = float(request.form.get('target_amount', 0))

            current_amount = float(request.form.get('current_amount', 0))

        except (ValueError, TypeError):

            flash('Invalid amount values.', 'danger')

            return redirect(url_for('goal_planning'))

        errors = []

        if not goal_name:

            errors.append('Goal name is required.')

        if target_amount <= 0:

            errors.append('Target amount must be greater than zero.')

        if current_amount < 0:

            errors.append('Current amount cannot be negative.')

        if current_amount > target_amount:

            errors.append('Current amount cannot exceed target amount.')

        sd = _parse_date(start_date)

        td = _parse_date(target_date)

        if sd and td and td <= sd:

            errors.append('Target date must be after start date.')

        if errors:

            for e in errors:

                flash(e, 'danger')

            return render_template('goal_planning.html',

                                   categories=GOAL_CATEGORIES, priorities=GOAL_PRIORITIES,

                                   statuses=GOAL_STATUSES, form=request.form,

                                   today=datetime.now().strftime('%Y-%m-%d'),

                                   user_name=session.get('user_name', 'User'))

        if current_amount >= target_amount > 0:

            status = 'Completed'

        try:

            conn = get_db_connection()

            with conn.cursor() as cur:

                cur.execute('''INSERT INTO goals (user_id, goal_name, goal_type, description,

                    target_amount, current_amount, start_date, target_date, category,

                    priority, status, notes) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',

                    (user_id, goal_name, goal_type, description, target_amount,

                     current_amount, start_date or None, target_date or None,

                     category, priority, status, notes))

            conn.close()

            flash(f'Goal "{goal_name}" created successfully! 🎯', 'success')

            return redirect(url_for('goals_list'))

        except Exception as e:

            flash(f'Error creating goal: {e}', 'danger')

    return render_template('goal_planning.html',

                           categories=GOAL_CATEGORIES, priorities=GOAL_PRIORITIES,

                           statuses=GOAL_STATUSES, form=None,

                           today=datetime.now().strftime('%Y-%m-%d'),

                           user_name=session.get('user_name', 'User'),

                           edit=False, goal=None)

@app.route('/goals/<int:goal_id>/edit', methods=['GET', 'POST'])

@login_required

def edit_goal(goal_id):

    user_id = session.get('user_id')

    try:

        conn = get_db_connection()

        with conn.cursor() as cur:

            cur.execute('SELECT * FROM goals WHERE id = %s AND user_id = %s', (goal_id, user_id))

            row = cur.fetchone()

        conn.close()

    except Exception:

        row = None

    if not row:

        flash('Goal not found.', 'danger')

        return redirect(url_for('goals_list'))

    goal = process_goal(row)

    if request.method == 'POST':

        goal_name     = request.form.get('goal_name', '').strip()

        goal_type     = request.form.get('goal_type', '').strip()

        description   = request.form.get('description', '').strip()

        category      = request.form.get('category', 'Personal')

        priority      = request.form.get('priority', 'Medium')

        status        = request.form.get('status', 'Active')

        notes         = request.form.get('notes', '').strip()

        start_date    = request.form.get('start_date', '')

        target_date   = request.form.get('target_date', '')

        try:

            target_amount  = float(request.form.get('target_amount', 0))

            current_amount = float(request.form.get('current_amount', 0))

        except (ValueError, TypeError):

            flash('Invalid amount values.', 'danger')

            return redirect(url_for('edit_goal', goal_id=goal_id))

        errors = []

        if not goal_name:

            errors.append('Goal name is required.')

        if target_amount <= 0:

            errors.append('Target amount must be greater than zero.')

        if errors:

            for e in errors:

                flash(e, 'danger')

            return render_template('goal_planning.html',

                                   categories=GOAL_CATEGORIES, priorities=GOAL_PRIORITIES,

                                   statuses=GOAL_STATUSES, goal=goal, edit=True,

                                   today=datetime.now().strftime('%Y-%m-%d'),

                                   user_name=session.get('user_name', 'User'))

        if current_amount >= target_amount > 0:

            status = 'Completed'

        try:

            conn = get_db_connection()

            with conn.cursor() as cur:

                cur.execute('''UPDATE goals SET goal_name=%s, goal_type=%s, description=%s,

                    target_amount=%s, current_amount=%s, start_date=%s, target_date=%s,

                    category=%s, priority=%s, status=%s, notes=%s WHERE id=%s AND user_id=%s''',

                    (goal_name, goal_type, description, target_amount, current_amount,

                     start_date or None, target_date or None, category, priority, status,

                     notes, goal_id, user_id))

            conn.close()

            flash(f'Goal "{goal_name}" updated! ✅', 'success')

            return redirect(url_for('goal_detail', goal_id=goal_id))

        except Exception as e:

            flash(f'Error updating goal: {e}', 'danger')

    return render_template('goal_planning.html',

                           categories=GOAL_CATEGORIES, priorities=GOAL_PRIORITIES,

                           statuses=GOAL_STATUSES, goal=goal, edit=True,

                           today=datetime.now().strftime('%Y-%m-%d'),

                           user_name=session.get('user_name', 'User'))

# ═══════════════════════════════════════════════════════════════════

# GOAL DETAIL

# ═══════════════════════════════════════════════════════════════════

@app.route('/goals/<int:goal_id>')

@login_required

def goal_detail(goal_id):

    user_id = session.get('user_id')

    try:

        conn = get_db_connection()

        with conn.cursor() as cur:

            cur.execute('SELECT * FROM goals WHERE id = %s AND user_id = %s', (goal_id, user_id))

            row = cur.fetchone()

            if not row:

                flash('Goal not found.', 'danger')

                return redirect(url_for('goals_list'))

            goal = process_goal(row)

            cur.execute('SELECT * FROM goal_parts WHERE goal_id = %s ORDER BY created_at ASC', (goal_id,))

            parts_raw = cur.fetchall()

            parts = [process_goal_part(p) for p in parts_raw]

            cur.execute('SELECT * FROM savings_goals WHERE goal_id = %s ORDER BY saving_date DESC', (goal_id,))

            savings = [dict(s) for s in cur.fetchall()]

            for s in savings:

                s['amount'] = float(s['amount'])

        conn.close()

    except Exception as e:

        print('Goal detail error:', e)

        flash('Error loading goal details.', 'danger')

        return redirect(url_for('goals_list'))

    return render_template('goal_details.html', goal=goal, parts=parts, savings=savings,

                           today=datetime.now().strftime('%Y-%m-%d'),

                           user_name=session.get('user_name', 'User'))

# ═══════════════════════════════════════════════════════════════════

# GOAL DELETE, SAVINGS, MILESTONES

# ═══════════════════════════════════════════════════════════════════

@app.route('/goals/<int:goal_id>/delete', methods=['POST'])

@login_required

def goal_delete(goal_id):

    user_id = session.get('user_id')

    try:

        conn = get_db_connection()

        with conn.cursor() as cur:

            cur.execute('SELECT goal_name FROM goals WHERE id = %s AND user_id = %s', (goal_id, user_id))

            row = cur.fetchone()

            if not row:

                flash('Goal not found.', 'danger')

                return redirect(url_for('goals_list'))

            name = row['goal_name']

            cur.execute('DELETE FROM goals WHERE id = %s AND user_id = %s', (goal_id, user_id))

        conn.close()

        flash(f'Goal "{name}" deleted.', 'info')

    except Exception as e:

        flash(f'Error: {e}', 'danger')

    return redirect(url_for('goals_list'))

@app.route('/goals/<int:goal_id>/savings', methods=['POST'])

@login_required

def add_savings(goal_id):

    user_id = session.get('user_id')

    amount_str = request.form.get('amount', '0')

    saving_date = request.form.get('saving_date', datetime.now().strftime('%Y-%m-%d'))

    note = request.form.get('note', '').strip()

    try:

        amount = float(amount_str)

        if amount <= 0:

            flash('Amount must be greater than zero.', 'danger')

            return redirect(url_for('goal_detail', goal_id=goal_id))

    except ValueError:

        flash('Invalid amount.', 'danger')

        return redirect(url_for('goal_detail', goal_id=goal_id))

    try:

        conn = get_db_connection()

        with conn.cursor() as cur:

            cur.execute('SELECT id FROM goals WHERE id = %s AND user_id = %s', (goal_id, user_id))

            if not cur.fetchone():

                flash('Goal not found.', 'danger')

                conn.close()

                return redirect(url_for('goals_list'))

            cur.execute('INSERT INTO savings_goals (goal_id, amount, saving_date, note) VALUES (%s,%s,%s,%s)',

                        (goal_id, amount, saving_date, note))

            cur.execute('UPDATE goals SET current_amount = current_amount + %s WHERE id = %s', (amount, goal_id))

            # Check if goal is now completed

            cur.execute('SELECT target_amount, current_amount FROM goals WHERE id = %s', (goal_id,))

            g = cur.fetchone()

            if g and float(g['current_amount']) >= float(g['target_amount']):

                cur.execute("UPDATE goals SET status = 'Completed' WHERE id = %s", (goal_id,))

        conn.close()

        flash(f'₹{amount:,.0f} savings added! 🎉', 'success')

    except Exception as e:

        flash(f'Error: {e}', 'danger')

    return redirect(url_for('goal_detail', goal_id=goal_id))

@app.route('/goals/<int:goal_id>/milestones', methods=['POST'])

@login_required

def add_milestone(goal_id):

    user_id = session.get('user_id')

    part_name = request.form.get('part_name', '').strip()

    due_date  = request.form.get('due_date', '') or None

    part_status = request.form.get('part_status', 'Pending')

    try:

        target_amount = float(request.form.get('target_amount', 0))

        saved_amount  = float(request.form.get('saved_amount', 0))

    except (ValueError, TypeError):

        flash('Invalid amount.', 'danger')

        return redirect(url_for('goal_detail', goal_id=goal_id))

    if not part_name:

        flash('Milestone name is required.', 'danger')

        return redirect(url_for('goal_detail', goal_id=goal_id))

    try:

        conn = get_db_connection()

        with conn.cursor() as cur:

            cur.execute('SELECT id FROM goals WHERE id = %s AND user_id = %s', (goal_id, user_id))

            if not cur.fetchone():

                flash('Goal not found.', 'danger')

                conn.close()

                return redirect(url_for('goals_list'))

            cur.execute('''INSERT INTO goal_parts (goal_id, part_name, target_amount, saved_amount, due_date, status)

                           VALUES (%s,%s,%s,%s,%s,%s)''',

                        (goal_id, part_name, target_amount, saved_amount, due_date, part_status))

        conn.close()

        flash(f'Milestone "{part_name}" added! ✅', 'success')

    except Exception as e:

        flash(f'Error: {e}', 'danger')

    return redirect(url_for('goal_detail', goal_id=goal_id))

@app.route('/goals/<int:goal_id>/milestones/<int:part_id>/update', methods=['POST'])

@login_required

def update_milestone(goal_id, part_id):

    user_id = session.get('user_id')

    saved_amount = request.form.get('saved_amount', 0)

    part_status  = request.form.get('part_status', 'Pending')

    try:

        conn = get_db_connection()

        with conn.cursor() as cur:

            cur.execute('SELECT id FROM goals WHERE id = %s AND user_id = %s', (goal_id, user_id))

            if not cur.fetchone():

                flash('Goal not found.', 'danger')

                conn.close()

                return redirect(url_for('goals_list'))

            cur.execute('UPDATE goal_parts SET saved_amount = %s, status = %s WHERE id = %s AND goal_id = %s',

                        (saved_amount, part_status, part_id, goal_id))

        conn.close()

        flash('Milestone updated! ✅', 'success')

    except Exception as e:

        flash(f'Error: {e}', 'danger')

    return redirect(url_for('goal_detail', goal_id=goal_id))

# ═══════════════════════════════════════════════════════════════════

# PROFILE

# ═══════════════════════════════════════════════════════════════════

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile_page():
    user_id = session.get('user_id')
    import os

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        currency = request.form.get('currency', '₹').strip() or '₹'
        notes = request.form.get('notes', '').strip()

        try:
            saving_cap = float(request.form.get('monthly_saving_capacity', 0) or 0)
            invest_cap = float(request.form.get('monthly_investment_capacity', 0) or 0)
        except (ValueError, TypeError):
            saving_cap = 0
            invest_cap = 0

        # Handle Profile Picture Upload
        profile_pic_path = None
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and file.filename != '':
                try:
                    uploads_dir = os.path.join(app.root_path, 'static', 'uploads')
                    os.makedirs(uploads_dir, exist_ok=True)
                    ext = os.path.splitext(file.filename)[1]
                    filename = f"profile_{user_id}{ext}"
                    file_save_path = os.path.join(uploads_dir, filename)
                    file.save(file_save_path)
                    profile_pic_path = f"uploads/{filename}"
                except Exception as e:
                    print("Error saving profile pic:", e)

        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                # 1. Update Users Table (Name, Email)
                if name and email:
                    cur.execute('UPDATE users SET name=%s, email=%s WHERE id=%s', (name, email, user_id))
                    session['user_name'] = name
                    session['user_email'] = email

                # 2. Update User Profile Table
                cur.execute('SELECT id FROM user_profile WHERE user_id = %s', (user_id,))
                existing = cur.fetchone()

                if existing:
                    if profile_pic_path:
                        cur.execute('''UPDATE user_profile SET phone=%s, currency=%s,
                            monthly_saving_capacity=%s, monthly_investment_capacity=%s,
                            notes=%s, profile_pic=%s WHERE user_id=%s''',
                            (phone, currency, saving_cap, invest_cap, notes, profile_pic_path, user_id))
                    else:
                        cur.execute('''UPDATE user_profile SET phone=%s, currency=%s,
                            monthly_saving_capacity=%s, monthly_investment_capacity=%s,
                            notes=%s WHERE user_id=%s''',
                            (phone, currency, saving_cap, invest_cap, notes, user_id))
                else:
                    cur.execute('''INSERT INTO user_profile (user_id, phone, currency,
                        monthly_saving_capacity, monthly_investment_capacity, notes, profile_pic)
                        VALUES (%s,%s,%s,%s,%s,%s,%s)''',
                        (user_id, phone, currency, saving_cap, invest_cap, notes, profile_pic_path))

            conn.close()
            flash('Profile updated successfully! ✅', 'success')
            return redirect(url_for('profile_page'))
        except Exception as e:
            flash(f'Error updating profile: {e}', 'danger')

    # Get profile and fresh user details
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute('SELECT name, email FROM users WHERE id = %s', (user_id,))
            user_row = cur.fetchone()
            db_user_name = user_row['name'] if user_row else 'User'
            db_user_email = user_row['email'] if user_row else ''

            cur.execute('SELECT * FROM user_profile WHERE user_id = %s', (user_id,))
            prof = cur.fetchone()
            prof = dict(prof) if prof else {}
        conn.close()
    except Exception as e:
        print('Profile query error:', e)
        prof = {}
        db_user_name = session.get('user_name', 'User')
        db_user_email = session.get('user_email', '')

        return render_template('profile.html', prof=prof,
                           user_name=db_user_name,
                           user_email=db_user_email)

@app.route('/api/profile/change-password', methods=['POST'])
@login_required
def change_password():
    user_id = session.get('user_id')
    current_pw = request.form.get('current_password', '')
    new_pw = request.form.get('new_password', '')
    confirm_pw = request.form.get('confirm_password', '')

    if not current_pw or not new_pw or not confirm_pw:
        flash('All password fields are required.', 'danger')
        return redirect(url_for('profile_page'))

    if new_pw != confirm_pw:
        flash('New password and confirmation do not match.', 'danger')
        return redirect(url_for('profile_page'))

    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute('SELECT password_hash FROM users WHERE id = %s', (user_id,))
            user = cur.fetchone()
            if not user:
                flash('User not found.', 'danger')
                return redirect(url_for('profile_page'))
            
            hashed = user['password_hash'].encode('utf-8')
            if not bcrypt.checkpw(current_pw.encode('utf-8'), hashed):
                flash('Incorrect current password.', 'danger')
                return redirect(url_for('profile_page'))
            
            new_hash = bcrypt.hashpw(new_pw.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            cur.execute('UPDATE users SET password_hash = %s WHERE id = %s', (new_hash, user_id))
        conn.close()
        flash('Password updated successfully! 🔑', 'success')
    except Exception as e:
        flash(f'Error updating password: {e}', 'danger')
    
    return redirect(url_for('profile_page'))

@app.route('/api/profile/delete-account', methods=['POST'])
@login_required
def delete_account():
    user_id = session.get('user_id')
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute('DELETE FROM users WHERE id = %s', (user_id,))
        conn.close()
        session.clear()
        flash('Your account and all associated data have been permanently deleted.', 'info')
        return redirect(url_for('login'))
    except Exception as e:
        flash(f'Error deleting account: {e}', 'danger')
        return redirect(url_for('profile_page'))

@app.route('/api/dashboard-goals-data')

@login_required

def api_dashboard_goals_data():

    user_id = session.get('user_id')

    try:

        conn = get_db_connection()

        with conn.cursor() as cur:

            # Goal status distribution

            cur.execute("SELECT status, COUNT(*) as cnt FROM goals WHERE user_id = %s GROUP BY status", (user_id,))

            status_rows = cur.fetchall()

            status_counts = {'Active': 0, 'Completed': 0, 'On Hold': 0}

            for r in status_rows:

                s = r['status']

                if s in status_counts:

                    status_counts[s] = int(r['cnt'])

            # Category distribution

            cur.execute("SELECT category, COUNT(*) as cnt FROM goals WHERE user_id = %s GROUP BY category", (user_id,))

            cat_rows = cur.fetchall()

            cat_data = {r['category'] or 'Other': int(r['cnt']) for r in cat_rows}

            # Target vs Saved (top 6 goals by target)

            cur.execute("SELECT goal_name, target_amount, current_amount FROM goals WHERE user_id = %s ORDER BY target_amount DESC LIMIT 6", (user_id,))

            top_goals = cur.fetchall()

            target_vs_saved = {

                'labels': [g['goal_name'] for g in top_goals],

                'target': [float(g['target_amount']) for g in top_goals],

                'saved':  [float(g['current_amount']) for g in top_goals],

            }

            # Monthly savings trend (last 6 months)

            from datetime import timedelta, date

            from decimal import Decimal

            today = date.today()

            monthly_trend = []

            for i in range(5, -1, -1):

                # Calculate start and end date for each of the last 6 months

                # Subtracting approx months

                m_end = today - timedelta(days=i * 30)

                m_start = today - timedelta(days=(i + 1) * 30)

                # Query savings_goals for this range

                cur.execute(

                    "SELECT COALESCE(SUM(amount), 0) as total FROM savings_goals sg "

                    "JOIN goals g ON sg.goal_id = g.id "

                    "WHERE g.user_id = %s AND sg.saving_date >= %s AND sg.saving_date <= %s",

                    (user_id, m_start.strftime('%Y-%m-%d'), m_end.strftime('%Y-%m-%d'))

                )

                row = cur.fetchone()

                monthly_trend.append({'label': m_end.strftime('%b %Y'), 'amount': float(row['total'])})

            # Recent goals (top 5)

            cur.execute("SELECT * FROM goals WHERE user_id = %s ORDER BY updated_at DESC LIMIT 5", (user_id,))

            recent_rows = cur.fetchall()

            recent_goals = [process_goal(r) for r in recent_rows]

            recent_goals_clean = []

            for g_item in recent_goals:

                g_clean = {}

                for k, v in g_item.items():

                    if isinstance(v, (date, datetime)):

                        g_clean[k] = str(v)

                    elif isinstance(v, Decimal):

                        g_clean[k] = float(v)

                    else:

                        g_clean[k] = v

                recent_goals_clean.append(g_clean)

        conn.close()

        return jsonify({

            'status_distribution': status_counts,

            'category_distribution': cat_data,

            'target_vs_saved': target_vs_saved,

            'monthly_trend': monthly_trend,

            'recent_goals': recent_goals_clean

        })

    except Exception as e:

        return jsonify({'error': str(e)}), 500

# ═══════════════════════════════════════════════════════════════════

# ALERTS SYSTEM

# ═══════════════════════════════════════════════════════════════════

def generate_alerts_for_user(user_id, conn):
    """Generate smart financial alerts for the user (rule-based AI analysis)."""
    try:
        with conn.cursor() as cur:
            today = datetime.now().date()
            cur_month = today.month
            cur_year  = today.year

            # ── 1. Budget exceeded / warning / saving alerts ──────────────────
            cur.execute('''
                SELECT b.id, b.category, b.limit_amount, b.goal_id,
                       COALESCE(SUM(e.amount),0) AS spent
                FROM budget b
                LEFT JOIN expenses e
                  ON e.user_id = b.user_id
                  AND e.category = b.category
                  AND MONTH(e.expense_date) = b.month
                  AND YEAR(e.expense_date) = b.year
                WHERE b.user_id = %s AND b.month = %s AND b.year = %s
                GROUP BY b.id
            ''', (user_id, cur_month, cur_year))
            budgets = cur.fetchall()

            for bud in budgets:
                spent      = float(bud['spent'])
                limit_amt  = float(bud['limit_amount'])
                cat        = bud['category']
                ref        = f"budget:{bud['id']}"
                pct        = (spent / limit_amt * 100) if limit_amt > 0 else 0

                # A. Budget Exceeded (Red dot)
                if pct >= 100:
                    cur.execute(
                        "SELECT id FROM alerts WHERE user_id=%s AND trigger_ref=%s AND alert_type='budget_exceeded' AND MONTH(created_at)=%s AND YEAR(created_at)=%s",
                        (user_id, ref, cur_month, cur_year)
                    )
                    if not cur.fetchone():
                        cur.execute(
                            "INSERT INTO alerts (user_id, alert_type, title, message, severity, trigger_ref) VALUES (%s,%s,%s,%s,%s,%s)",
                            (user_id, 'budget_exceeded',
                             f'🔴 Budget Exceeded: {cat}',
                             f'{cat} budget exceeded by ₹{spent - limit_amt:,.0f}.',
                             'red', ref)
                        )
                # B. Budget Near Limit (Orange dot)
                elif pct >= 80:
                    cur.execute(
                        "SELECT id FROM alerts WHERE user_id=%s AND trigger_ref=%s AND alert_type='budget_warning' AND MONTH(created_at)=%s AND YEAR(created_at)=%s",
                        (user_id, ref, cur_month, cur_year)
                    )
                    if not cur.fetchone():
                        cur.execute(
                            "INSERT INTO alerts (user_id, alert_type, title, message, severity, trigger_ref) VALUES (%s,%s,%s,%s,%s,%s)",
                            (user_id, 'budget_warning',
                             f'🟠 Budget Near Limit: {cat}',
                             f'{cat} budget is {pct:.0f}% used. ₹{limit_amt-spent:,.0f} remaining.',
                             'orange', ref)
                        )
                # C. Budget Saving (Green dot)
                elif spent > 0 and spent < limit_amt:
                    cur.execute(
                        "SELECT id FROM alerts WHERE user_id=%s AND trigger_ref=%s AND alert_type='budget_saving' AND MONTH(created_at)=%s AND YEAR(created_at)=%s",
                        (user_id, ref, cur_month, cur_year)
                    )
                    if not cur.fetchone():
                        cur.execute(
                            "INSERT INTO alerts (user_id, alert_type, title, message, severity, trigger_ref) VALUES (%s,%s,%s,%s,%s,%s)",
                            (user_id, 'budget_saving',
                             f'🟢 Budget Saving: {cat}',
                             f'You have ₹{limit_amt-spent:,.0f} unused in your {cat} monthly budget.',
                             'green', ref)
                        )

            # ── 2. Goal deadline & Goal Contribution Due alerts ───────────────────────────────
            cur.execute(
                "SELECT id, goal_name, target_date, current_amount, target_amount FROM goals WHERE user_id=%s AND status='Active'",
                (user_id,)
            )
            goals = cur.fetchall()

            for g in goals:
                ref = f"goal:{g['id']}"
                remaining = float(g['target_amount']) - float(g['current_amount'])
                if remaining <= 0:
                    continue

                # A. Goal Deadline (Purple dot)
                if g['target_date']:
                    td = g['target_date'] if isinstance(g['target_date'], type(today)) else _parse_date(str(g['target_date']))
                    if td:
                        days_left = (td - today).days
                        if 0 <= days_left <= 30:
                            cur.execute(
                                "SELECT id FROM alerts WHERE user_id=%s AND trigger_ref=%s AND alert_type='goal_deadline' AND MONTH(created_at)=%s AND YEAR(created_at)=%s",
                                (user_id, ref, cur_month, cur_year)
                            )
                            if not cur.fetchone():
                                cur.execute(
                                    "INSERT INTO alerts (user_id, alert_type, title, message, severity, trigger_ref) VALUES (%s,%s,%s,%s,%s,%s)",
                                    (user_id, 'goal_deadline',
                                     f'🟣 Goal Deadline: {g["goal_name"]}',
                                     f'{g["goal_name"]} deadline is in {days_left} days. ₹{remaining:,.0f} remaining.',
                                     'purple', ref)
                                )

                # B. Goal Contribution Due (Blue dot)
                cur.execute(
                    "SELECT id, part_name, target_amount, saved_amount, due_date FROM goal_parts WHERE goal_id=%s AND status='Pending'",
                    (g['id'],)
                )
                parts = cur.fetchall()
                for p in parts:
                    part_ref = f"goal_part:{p['id']}"
                    p_due_date = p['due_date'] if isinstance(p['due_date'], type(today)) else _parse_date(str(p['due_date']))
                    if p_due_date:
                        days_to_due = (p_due_date - today).days
                        if 0 <= days_to_due <= 7:
                            due_amount = float(p['target_amount']) - float(p['saved_amount'])
                            if due_amount > 0:
                                cur.execute(
                                    "SELECT id FROM alerts WHERE user_id=%s AND trigger_ref=%s AND alert_type='goal_contribution_due'",
                                    (user_id, part_ref)
                                )
                                if not cur.fetchone():
                                    cur.execute(
                                        "INSERT INTO alerts (user_id, alert_type, title, message, severity, trigger_ref) VALUES (%s,%s,%s,%s,%s,%s)",
                                        (user_id, 'goal_contribution_due',
                                         f'🔵 Goal Contribution Due: {g["goal_name"]}',
                                         f'₹{due_amount:,.0f} contribution is due for {g["goal_name"]}.',
                                         'blue', part_ref)
                                    )

            # ── 3. High Spending (Yellow dot) ───────────────────────
            cur.execute("SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE user_id=%s AND MONTH(expense_date) = %s AND YEAR(expense_date) = %s", (user_id, cur_month, cur_year))
            this_month_total = float(cur.fetchone()['total'])

            lm_month = 12 if cur_month == 1 else cur_month - 1
            lm_year = cur_year - 1 if cur_month == 1 else cur_year

            cur.execute("SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE user_id=%s AND MONTH(expense_date) = %s AND YEAR(expense_date) = %s AND DAY(expense_date) <= %s", (user_id, lm_month, lm_year, today.day))
            last_month_same_period = float(cur.fetchone()['total'])

            if last_month_same_period > 0 and this_month_total > last_month_same_period * 1.1:
                increase_pct = round((this_month_total - last_month_same_period) / last_month_same_period * 100)
                cur.execute("SELECT id FROM alerts WHERE user_id=%s AND alert_type='high_spending' AND MONTH(created_at)=%s AND YEAR(created_at)=%s", (user_id, cur_month, cur_year))
                if not cur.fetchone():
                    cur.execute(
                        "INSERT INTO alerts (user_id, alert_type, title, message, severity, trigger_ref) VALUES (%s,%s,%s,%s,%s,%s)",
                        (user_id, 'high_spending',
                         '🟡 High Spending',
                         f'Your spending is {increase_pct}% higher than last month.',
                         'yellow', 'high_spending')
                    )

            # ── 4. Investment Reminder (Blue dot) ───────────────────────
            cur.execute("SELECT monthly_investment_capacity FROM user_profile WHERE user_id=%s", (user_id,))
            profile = cur.fetchone()
            if profile and profile['monthly_investment_capacity']:
                capacity = float(profile['monthly_investment_capacity'])
                if capacity > 0:
                    cur.execute("SELECT id FROM alerts WHERE user_id=%s AND alert_type='investment_reminder' AND MONTH(created_at)=%s AND YEAR(created_at)=%s", (user_id, cur_month, cur_year))
                    if not cur.fetchone():
                        cur.execute(
                            "INSERT INTO alerts (user_id, alert_type, title, message, severity, trigger_ref) VALUES (%s,%s,%s,%s,%s,%s)",
                            (user_id, 'investment_reminder',
                             '🔵 Investment Reminder',
                             f'Your SIP contribution of ₹{capacity:,.0f} is due tomorrow.',
                             'blue', 'investment_reminder')
                        )

    except Exception as e:
        print("Alert generation error:", e)

@app.route('/api/alerts/generate', methods=['POST'])

@login_required

def api_generate_alerts():

    """Trigger alert generation for current user."""

    user_id = session.get('user_id')

    try:

        conn = get_db_connection()

        generate_alerts_for_user(user_id, conn)

        conn.close()

        return jsonify({'status': 'ok'})

    except Exception as e:

        return jsonify({'error': str(e)}), 500

@app.route('/api/alerts')

@login_required

def api_get_alerts():

    """Get all alerts for current user (newest first)."""

    user_id = session.get('user_id')

    try:

        conn = get_db_connection()

        with conn.cursor() as cur:

            cur.execute(

                "SELECT id, alert_type, title, message, is_read, severity, trigger_ref, created_at FROM alerts WHERE user_id=%s ORDER BY created_at DESC LIMIT 30",

                (user_id,)

            )

            rows = cur.fetchall()

            unread_count_res = [r for r in rows if not r['is_read']]

        conn.close()

        result = []

        for r in rows:

            result.append({

                'id': r['id'],

                'alert_type': r['alert_type'],

                'title': r['title'],

                'message': r['message'],

                'is_read': bool(r['is_read']),

                'severity': r['severity'],

                'trigger_ref': r['trigger_ref'],

                'created_at': str(r['created_at'])

            })

        return jsonify({'alerts': result, 'unread_count': len(unread_count_res)})

    except Exception as e:

        return jsonify({'error': str(e)}), 500

@app.route('/api/alerts/mark-read', methods=['POST'])

@login_required

def api_mark_alerts_read():

    """Mark all alerts as read for the current user."""

    user_id = session.get('user_id')

    try:

        conn = get_db_connection()

        with conn.cursor() as cur:

            data = request.get_json() or {}

            alert_id = data.get('alert_id')

            if alert_id:

                cur.execute("UPDATE alerts SET is_read=1 WHERE id=%s AND user_id=%s", (alert_id, user_id))

            else:

                cur.execute("UPDATE alerts SET is_read=1 WHERE user_id=%s", (user_id,))

        conn.close()

        return jsonify({'status': 'ok'})

    except Exception as e:

        return jsonify({'error': str(e)}), 500

@app.route('/api/alerts/clear', methods=['POST'])

@login_required

def api_clear_alerts():

    """Delete all alerts for the current user."""

    user_id = session.get('user_id')

    try:

        conn = get_db_connection()

        with conn.cursor() as cur:

            cur.execute("DELETE FROM alerts WHERE user_id=%s", (user_id,))

        conn.close()

        return jsonify({'status': 'ok'})

    except Exception as e:

        return jsonify({'error': str(e)}), 500

@app.route('/health-score')
@login_required
def health_score_page():
    user_id = session.get('user_id')
    user_name = session.get('user_name', 'User')
    today = datetime.now().date()
    cur_month = today.month
    cur_year = today.year

    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # 1. Income this month
            cur.execute("SELECT COALESCE(SUM(amount), 0) AS total FROM income WHERE user_id = %s AND MONTH(income_date) = %s AND YEAR(income_date) = %s", (user_id, cur_month, cur_year))
            monthly_income = float(cur.fetchone()['total'])

            # 2. Expenses this month
            cur.execute("SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE user_id = %s AND MONTH(expense_date) = %s AND YEAR(expense_date) = %s", (user_id, cur_month, cur_year))
            monthly_expenses = float(cur.fetchone()['total'])

            # 3. Investments this month
            cur.execute("SELECT COALESCE(SUM(amount), 0) AS total FROM investments WHERE user_id = %s AND MONTH(invest_date) = %s AND YEAR(invest_date) = %s", (user_id, cur_month, cur_year))
            monthly_investments = float(cur.fetchone()['total'])

            # 4. User Profile
            cur.execute("SELECT monthly_saving_capacity, monthly_investment_capacity FROM user_profile WHERE user_id = %s", (user_id,))
            profile = cur.fetchone()
            saving_capacity = float(profile['monthly_saving_capacity']) if profile and profile['monthly_saving_capacity'] else 0.0
            investment_capacity = float(profile['monthly_investment_capacity']) if profile and profile['monthly_investment_capacity'] else 0.0

            # 5. Budgets this month
            cur.execute('''
                SELECT b.category, b.limit_amount, COALESCE(SUM(e.amount),0) AS spent
                FROM budget b
                LEFT JOIN expenses e
                  ON e.user_id = b.user_id
                  AND e.category = b.category
                  AND MONTH(e.expense_date) = b.month
                  AND YEAR(e.expense_date) = b.year
                WHERE b.user_id = %s AND b.month = %s AND b.year = %s
                GROUP BY b.id
            ''', (user_id, cur_month, cur_year))
            budgets = cur.fetchall()

            # 6. Active Goals
            cur.execute("SELECT id, goal_name, target_amount, current_amount, target_date, status FROM goals WHERE user_id = %s", (user_id,))
            goals = cur.fetchall()

            # 7. Expenses last month same period
            lm_month = 12 if cur_month == 1 else cur_month - 1
            lm_year = cur_year - 1 if cur_month == 1 else cur_year
            cur.execute("SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE user_id = %s AND MONTH(expense_date) = %s AND YEAR(expense_date) = %s AND DAY(expense_date) <= %s", (user_id, lm_month, lm_year, today.day))
            last_month_same_period = float(cur.fetchone()['total'])

        conn.close()

        # ── 1. Budget Management (30 points) ──
        if budgets:
            not_exceeded = 0
            for b in budgets:
                if float(b['spent']) <= float(b['limit_amount']):
                    not_exceeded += 1
            budget_score = round(30 * (not_exceeded / len(budgets)))
        else:
            if monthly_expenses <= monthly_income and monthly_income > 0:
                budget_score = 25
            else:
                budget_score = 15

        # ── 2. Savings Rate (25 points) ──
        savings = monthly_income - monthly_expenses
        savings_rate = (savings / monthly_income * 100) if monthly_income > 0 else 0
        if savings_rate >= 30:
            savings_score = 25
        elif savings_rate > 0:
            savings_score = round(25 * (savings_rate / 30))
        else:
            savings_score = 0

        # ── 3. Goal Progress (20 points) ──
        if goals:
            goal_points = 0
            for g in goals:
                g_target = float(g['target_amount'])
                g_saved = float(g['current_amount'])
                g_status = g['status']
                g_date = g['target_date']
                
                if g_status == 'Completed':
                    goal_points += 1.0
                else:
                    deadline_missed = False
                    if g_date:
                        td = g_date if isinstance(g_date, type(today)) else _parse_date(str(g_date))
                        if td and td < today:
                            deadline_missed = True
                    
                    if deadline_missed:
                        goal_points += max(0.0, (g_saved / g_target) * 0.5)
                    else:
                        goal_points += (g_saved / g_target) if g_target > 0 else 1.0
            goal_score = round(20 * (goal_points / len(goals)))
        else:
            goal_score = 10

        # ── 4. Spending Pattern (15 points) ──
        if last_month_same_period > 0:
            if monthly_expenses <= last_month_same_period:
                spending_score = 15
            else:
                increase_pct = ((monthly_expenses - last_month_same_period) / last_month_same_period) * 100
                if increase_pct <= 20:
                    spending_score = round(15 * (1 - (increase_pct / 100)))
                else:
                    spending_score = 5
        else:
            spending_score = 15 if monthly_expenses == 0 else 12

        # ── 5. Investment Habit (10 points) ──
        if investment_capacity > 0:
            investment_score = round(10 * min(1.0, monthly_investments / investment_capacity))
        else:
            investment_score = 10 if monthly_investments > 0 else 5

        # ── Total Score ──
        total_score = budget_score + savings_score + goal_score + spending_score + investment_score
        total_score = max(0, min(100, total_score))

        if total_score >= 90:
            status = "Excellent"
            status_color = "#10B981"
            description = "Incredible job! You are managing your finances masterfully. Keep it up!"
        elif total_score >= 75:
            status = "Good"
            status_color = "#10B981"
            description = "You are managing your finances well. Keep it up and try to increase your savings."
        elif total_score >= 50:
            status = "Fair"
            status_color = "#F59E0B"
            description = "Your financial health is stable, but there is room for improvement. Try to cut back on dining out or shopping."
        else:
            status = "Needs Action"
            status_color = "#EF4444"
            description = "Your financial health needs attention. You are spending more than you save or missing your goal deadlines. Let's fix this!"

        return render_template('health_score.html',
                               user_name=user_name,
                               total_score=total_score,
                               status=status,
                               status_color=status_color,
                               description=description,
                               breakdown={
                                   'budget': budget_score,
                                   'savings': savings_score,
                                   'goals': goal_score,
                                   'spending': spending_score,
                                   'investments': investment_score
                               })

    except Exception as e:
        return f"Error loading Financial Health Score: {str(e)}"

@app.route('/transactions')
@login_required
def transactions_page():
    user_id = session.get('user_id')
    user_name = session.get('user_name', 'User')

    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT id, source AS title, 'Income' AS category, amount, income_date AS date, 'income' AS type, created_at FROM income WHERE user_id = %s", (user_id,))
            incomes = cur.fetchall()

            cur.execute("SELECT id, category AS title, 'Expense' AS category, amount, expense_date AS date, 'expense' AS type, created_at FROM expenses WHERE user_id = %s", (user_id,))
            expenses = cur.fetchall()

            cur.execute("SELECT id, source AS title, invest_type AS category, amount, invest_date AS date, 'investment' AS type, created_at FROM investments WHERE user_id = %s", (user_id,))
            investments = cur.fetchall()
        conn.close()

        transactions = incomes + expenses + investments
        for t in transactions:
            t['amount'] = float(t['amount'])
            t['date'] = str(t['date'])

        # Sort by date descending
        transactions.sort(key=lambda x: x['date'], reverse=True)

        return render_template('transactions.html',
                               user_name=user_name,
                               transactions=transactions)
    except Exception as e:
        return f"Error loading transactions: {str(e)}"

# ═══════════════════════════════════════════════════════════════════

@app.route('/ai-insights')
@login_required
def ai_insights():
    user_id = session.get('user_id')
    user_name = session.get('user_name', 'User')

    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # 1. Income this month
            cur.execute("SELECT COALESCE(SUM(amount), 0) AS total FROM income WHERE user_id = %s AND MONTH(income_date) = MONTH(CURDATE()) AND YEAR(income_date) = YEAR(CURDATE())", (user_id,))
            monthly_income = float(cur.fetchone()['total'])

            # 2. Expenses this month
            cur.execute("SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE user_id = %s AND MONTH(expense_date) = MONTH(CURDATE()) AND YEAR(expense_date) = YEAR(CURDATE())", (user_id,))
            monthly_expenses = float(cur.fetchone()['total'])

            # 3. Investments this month
            cur.execute("SELECT COALESCE(SUM(amount), 0) AS total FROM investments WHERE user_id = %s AND MONTH(invest_date) = MONTH(CURDATE()) AND YEAR(invest_date) = YEAR(CURDATE())", (user_id,))
            monthly_investments = float(cur.fetchone()['total'])

            # 4. User Profile
            cur.execute("SELECT monthly_saving_capacity, monthly_investment_capacity FROM user_profile WHERE user_id = %s", (user_id,))
            profile = cur.fetchone()
            saving_capacity = float(profile['monthly_saving_capacity']) if profile and profile['monthly_saving_capacity'] else 0.0
            investment_capacity = float(profile['monthly_investment_capacity']) if profile and profile['monthly_investment_capacity'] else 0.0

            # 5. Top spending category
            cur.execute("SELECT category, SUM(amount) AS total FROM expenses WHERE user_id = %s AND MONTH(expense_date) = MONTH(CURDATE()) AND YEAR(expense_date) = YEAR(CURDATE()) GROUP BY category ORDER BY total DESC LIMIT 1", (user_id,))
            top_category_row = cur.fetchone()
            top_category = top_category_row['category'] if top_category_row else None
            top_category_amount = float(top_category_row['total']) if top_category_row else 0.0

            # 6. Active Goals
            cur.execute("SELECT id, goal_name, target_amount, current_amount, target_date, category FROM goals WHERE user_id = %s AND status = 'Active'", (user_id,))
            active_goals = cur.fetchall()

            # 7. Budgets
            cur.execute("SELECT category, limit_amount FROM budget WHERE user_id = %s AND month = MONTH(CURDATE()) AND year = YEAR(CURDATE())", (user_id,))
            budgets = cur.fetchall()

        conn.close()

        # Generate rule-based well-wishing insights
        savings = monthly_income - monthly_expenses
        savings_rate = round((savings / monthly_income * 100)) if monthly_income > 0 else 0

        # Card 1: Spending Pattern
        spending_pattern_title = "Spending Pattern"
        if top_category:
            spending_pattern_text = f"You spent ₹{top_category_amount:,.0f} on {top_category} this month. This accounts for {round(top_category_amount / monthly_expenses * 100) if monthly_expenses > 0 else 0}% of your total expenses."
        else:
            spending_pattern_text = "No spending recorded this month. Add some expenses to analyze your patterns!"

        # Card 2: Top Insight
        top_insight_title = "Top Insight"
        if savings > 0:
            top_insight_text = f"You have saved ₹{savings:,.0f} this month with a savings rate of {savings_rate}%. You are building a strong financial foundation!"
        else:
            top_insight_text = "Your expenses are equal to or higher than your income this month. Let's work on reducing non-essential spending."

        # Card 3: Saving Opportunity
        saving_opportunity_title = "Saving Opportunity"
        saving_opp = 0
        if top_category_amount > 0:
            saving_opp = top_category_amount * 0.15
            saving_opportunity_text = f"Reducing your {top_category} spending by 15% would save you around ₹{saving_opp:,.0f} this month. This could be redirected to your savings."
        else:
            saving_opportunity_text = "Establish a budget limit for categories like Food or Entertainment to identify saving opportunities."

        # Card 4: Recommendation
        recommendation_title = "Recommendation"
        if active_goals:
            first_goal = active_goals[0]
            goal_name = first_goal['goal_name']
            goal_target = float(first_goal['target_amount'])
            goal_saved = float(first_goal['current_amount'])
            goal_rem = max(0, goal_target - goal_saved)
            recommendation_text = f"Allocate ₹{saving_opp:,.0f} towards your '{goal_name}' goal. You need ₹{goal_rem:,.0f} more to reach it!"
        else:
            recommendation_text = "Create a savings goal (like an Emergency Fund or Laptop Goal) to give your savings a clear purpose."

        # Personal well-wisher note from Anya
        today = datetime.now().date()
        letter = f"Dear {user_name},\n\n"
        letter += "I have carefully analyzed your transactions for this month, and I'm here as your well-wisher to share some insights.\n\n"

        if monthly_income == 0:
            letter += "Currently, you haven't recorded any income for this month. Once you add your earnings under the 'Finances' tab, I can help you plan your budget and goals more effectively.\n\n"
        else:
            letter += f"This month, you earned ₹{monthly_income:,.0f} and spent ₹{monthly_expenses:,.0f}, leaving you with ₹{savings:,.0f} in savings ({savings_rate}% savings rate). "
            if savings_rate >= 30:
                letter += "This is an excellent savings rate! You are doing an amazing job managing your cash flow.\n\n"
            elif savings_rate >= 10:
                letter += "This is a good start, but try to aim for a 20% to 30% savings rate by checking if you can cut back on subscription services or dining out.\n\n"
            else:
                letter += "Your savings rate is low. To secure your future, let's try to increase it by setting strict budget limits.\n\n"

        if monthly_investments > 0:
            letter += f"I noticed you invested ₹{monthly_investments:,.0f} this month. This is wonderful! "
            if investment_capacity > 0:
                if monthly_investments >= investment_capacity:
                    letter += f"You have met your monthly investment target of ₹{investment_capacity:,.0f}. Keep up this consistency!\n\n"
                else:
                    diff = investment_capacity - monthly_investments
                    letter += f"You are ₹{diff:,.0f} short of your monthly investment target (₹{investment_capacity:,.0f}). Consider setting up a recurring SIP to automate this.\n\n"
            else:
                letter += "Investing regularly is the key to building wealth. Great job!\n\n"
        else:
            if investment_capacity > 0:
                letter += f"You have a planned investment capacity of ₹{investment_capacity:,.0f} but haven't recorded any investments yet this month. I highly recommend automating an investment of ₹{investment_capacity:,.0f} in low-cost index funds or mutual funds today.\n\n"
            else:
                letter += "I don't see any investments recorded this month. Investing even small amounts early can compound significantly over time. Consider allocating 10% of your income towards mutual funds or stocks.\n\n"

        if active_goals:
            letter += "Regarding your goals:\n"
            for g in active_goals:
                g_name = g['goal_name']
                g_target = float(g['target_amount'])
                g_saved = float(g['current_amount'])
                g_rem = max(0, g_target - g_saved)
                pct = round(g_saved / g_target * 100) if g_target > 0 else 0
                letter += f"• **{g_name}**: You have saved ₹{g_saved:,.0f} out of ₹{g_target:,.0f} ({pct}% complete). "
                if g['target_date']:
                    td = g['target_date'] if isinstance(g['target_date'], type(today)) else _parse_date(str(g['target_date']))
                    if td:
                        days_left = (td - today).days
                        if days_left > 0:
                            months_left = days_left / 30.44
                            monthly_needed = g_rem / max(0.1, months_left)
                            letter += f"With {days_left} days left, you should contribute ₹{monthly_needed:,.0f} monthly to meet your deadline.\n"
                        else:
                            letter += "The target date has passed. Consider editing the goal to adjust your timeline.\n"
                else:
                    letter += "\n"
        else:
            letter += "I highly suggest creating a Savings Goal in the 'Goals' tab. It gives your money direction and keeps you motivated!\n\n"

        letter += "\nRemember, consistency is the key to financial freedom. I will be here to monitor your progress and guide you every step of the way!\n\nWarm regards,\n**Anya, Your AI Well-Wisher**"

        insights_cards = [
            {'title': spending_pattern_title, 'text': spending_pattern_text, 'icon': 'bi-bar-chart-fill', 'color': '#8B5CF6'},
            {'title': top_insight_title, 'text': top_insight_text, 'icon': 'bi-lightning-charge-fill', 'color': '#F97316'},
            {'title': saving_opportunity_title, 'text': saving_opportunity_text, 'icon': 'bi-piggy-bank-fill', 'color': '#10B981'},
            {'title': recommendation_title, 'text': recommendation_text, 'icon': 'bi-award-fill', 'color': '#6366F1'}
        ]

        return render_template('ai_insights.html',
                               user_name=user_name,
                               insights=insights_cards,
                               letter=letter)

    except Exception as e:
        return f"Error loading AI Insights: {str(e)}"

# AI SPENDING ANALYSIS

# ═══════════════════════════════════════════════════════════════════

@app.route('/api/spending-analysis')

@login_required

def api_spending_analysis():

    """Rule-based AI spending pattern analysis."""

    user_id = session.get('user_id')

    try:

        conn = get_db_connection()

        with conn.cursor() as cur:

            # Top spending category this month

            cur.execute('''

                SELECT category, SUM(amount) AS total

                FROM expenses WHERE user_id=%s

                AND MONTH(expense_date)=MONTH(CURDATE()) AND YEAR(expense_date)=YEAR(CURDATE())

                GROUP BY category ORDER BY total DESC LIMIT 1

            ''', (user_id,))

            top_cat = cur.fetchone()

            # Month over month comparison (last 3 months)

            cur.execute('''

                SELECT MONTHNAME(expense_date) AS month_name,

                       MONTH(expense_date) AS m,

                       YEAR(expense_date) AS y,

                       SUM(amount) AS total

                FROM expenses WHERE user_id=%s

                AND expense_date >= DATE_SUB(CURDATE(), INTERVAL 3 MONTH)

                GROUP BY y, m, month_name ORDER BY y ASC, m ASC

            ''', (user_id,))

            monthly_exp = cur.fetchall()

            # Savings rate

            cur.execute("SELECT COALESCE(SUM(amount),0) AS t FROM income WHERE user_id=%s AND MONTH(income_date)=MONTH(CURDATE()) AND YEAR(income_date)=YEAR(CURDATE())", (user_id,))

            cur_income = float(cur.fetchone()['t'])

            cur.execute("SELECT COALESCE(SUM(amount),0) AS t FROM expenses WHERE user_id=%s AND MONTH(expense_date)=MONTH(CURDATE()) AND YEAR(expense_date)=YEAR(CURDATE())", (user_id,))

            cur_exp = float(cur.fetchone()['t'])

            # Over-budget categories

            cur.execute('''

                SELECT b.category, b.limit_amount, COALESCE(SUM(e.amount),0) AS spent

                FROM budget b

                LEFT JOIN expenses e ON e.user_id=b.user_id AND e.category=b.category

                  AND MONTH(e.expense_date)=b.month AND YEAR(e.expense_date)=b.year

                WHERE b.user_id=%s AND b.month=MONTH(CURDATE()) AND b.year=YEAR(CURDATE())

                GROUP BY b.id HAVING spent > b.limit_amount

            ''', (user_id,))

            over_budget = cur.fetchall()

            # Biggest single expense this month

            cur.execute('''

                SELECT category, amount, expense_date FROM expenses

                WHERE user_id=%s AND MONTH(expense_date)=MONTH(CURDATE()) AND YEAR(expense_date)=YEAR(CURDATE())

                ORDER BY amount DESC LIMIT 1

            ''', (user_id,))

            biggest = cur.fetchone()

        conn.close()

        insights = []

        # Savings rate insight

        savings_rate = round((cur_income - cur_exp) / cur_income * 100, 1) if cur_income > 0 else 0

        if savings_rate >= 30:

            insights.append({'icon': '💚', 'color': '#10B981', 'title': 'Excellent Savings Rate', 'text': f'You are saving {savings_rate}% of income this month. Great financial discipline!', 'badge': 'Excellent'})

        elif savings_rate >= 15:

            insights.append({'icon': '💛', 'color': '#F59E0B', 'title': 'Good Savings Rate', 'text': f'Savings rate is {savings_rate}%. Try to push above 30% for long-term wealth.', 'badge': 'Good'})

        elif cur_income > 0:

            insights.append({'icon': '🔴', 'color': '#EF4444', 'title': 'Low Savings Rate', 'text': f'Only saving {savings_rate}% this month. Review your expense categories.', 'badge': 'Needs Action'})

        # Top category insight

        if top_cat:

            insights.append({'icon': '📊', 'color': '#6366F1', 'title': f'Top Spend: {top_cat["category"]}', 'text': f'₹{float(top_cat["total"]):,.0f} spent on {top_cat["category"]} this month — your biggest category.', 'badge': 'Insight'})

        # Over-budget insight

        if over_budget:

            cats = ', '.join([r['category'] for r in over_budget])

            insights.append({'icon': '⚠️', 'color': '#EF4444', 'title': 'Over Budget Alert', 'text': f'Categories exceeding budget: {cats}. Cut back to stay on track.', 'badge': 'Action Needed'})

        # Spending trend

        if len(monthly_exp) >= 2:

            prev_total = float(monthly_exp[-2]['total'])

            cur_total  = float(monthly_exp[-1]['total'])

            if prev_total > 0:

                trend_pct = round((cur_total - prev_total) / prev_total * 100, 1)

                if trend_pct > 20:

                    insights.append({'icon': '📈', 'color': '#EF4444', 'title': 'Spending Rising Fast', 'text': f'Expenses up {trend_pct}% vs last month. Monitor your daily spending closely.', 'badge': 'Warning'})

                elif trend_pct < -10:

                    insights.append({'icon': '📉', 'color': '#10B981', 'title': 'Spending Trending Down', 'text': f'Expenses down {abs(trend_pct)}% vs last month. Excellent cost control!', 'badge': 'Great'})

        # Biggest expense

        if biggest:

            insights.append({'icon': '💰', 'color': '#8B5CF6', 'title': 'Largest Expense', 'text': f'Biggest spend: ₹{float(biggest["amount"]):,.0f} on {biggest["category"]} ({str(biggest["expense_date"])}).', 'badge': 'FYI'})

        if not insights:

            insights.append({'icon': '🚀', 'color': '#6366F1', 'title': 'Start Tracking', 'text': 'Add income and expenses to unlock AI spending analysis and insights.', 'badge': 'Get Started'})

        return jsonify({'insights': insights, 'savings_rate': savings_rate, 'monthly_data': [{'month': r['month_name'], 'total': float(r['total'])} for r in monthly_exp]})

    except Exception as e:

        return jsonify({'error': str(e)}), 500

# ═══════════════════════════════════════════════════════════════════

# BUDGET ↔ GOAL LINK API

# ═══════════════════════════════════════════════════════════════════

@app.route('/api/budget-with-goals')

@login_required

def api_budget_with_goals():

    """Return budgets with linked goal name and current spent amount."""

    user_id = session.get('user_id')

    try:

        conn = get_db_connection()

        with conn.cursor() as cur:

            cur.execute('''

                SELECT b.id, b.category, b.limit_amount, b.month, b.year, b.goal_id,

                       g.goal_name, g.current_amount AS goal_saved, g.target_amount AS goal_target,

                       COALESCE(SUM(e.amount),0) AS spent

                FROM budget b

                LEFT JOIN goals g ON b.goal_id = g.id

                LEFT JOIN expenses e ON e.user_id=b.user_id AND e.category=b.category

                  AND MONTH(e.expense_date)=b.month AND YEAR(e.expense_date)=b.year

                WHERE b.user_id=%s

                GROUP BY b.id

                ORDER BY b.year DESC, b.month DESC

            ''', (user_id,))

            rows = cur.fetchall()

        conn.close()

        result = []

        for r in rows:

            limit_amt = float(r['limit_amount'])

            spent     = float(r['spent'])

            pct       = round(spent / limit_amt * 100, 1) if limit_amt > 0 else 0

            result.append({

                'id':          r['id'],

                'category':    r['category'],

                'limit_amount': limit_amt,

                'month':       r['month'],

                'year':        r['year'],

                'goal_id':     r['goal_id'],

                'goal_name':   r['goal_name'],

                'goal_saved':  float(r['goal_saved']) if r['goal_saved'] else 0,

                'goal_target': float(r['goal_target']) if r['goal_target'] else 0,

                'spent':       spent,

                'percent_used': pct,

                'status':      'exceeded' if pct >= 100 else ('warning' if pct >= 80 else 'ok')

            })

        return jsonify(result)

    except Exception as e:

        return jsonify({'error': str(e)}), 500

@app.route('/api/budget/<int:budget_id>/link-goal', methods=['POST'])

@login_required

def api_link_budget_goal(budget_id):

    """Link a budget to a goal."""

    user_id = session.get('user_id')

    data    = request.get_json() or {}

    goal_id = data.get('goal_id')

    try:

        conn = get_db_connection()

        with conn.cursor() as cur:

            cur.execute("UPDATE budget SET goal_id=%s WHERE id=%s AND user_id=%s", (goal_id, budget_id, user_id))

        conn.close()

        return jsonify({'status': 'ok', 'message': 'Budget linked to goal.'})

    except Exception as e:

        return jsonify({'error': str(e)}), 500

# ═══════════════════════════════════════════════════════════════════

# MONTHLY INCOME vs EXPENSE vs BUDGET TREND

# ═══════════════════════════════════════════════════════════════════

@app.route('/api/monthly-trend')

@login_required

def api_monthly_trend():

    """Return last 6 months income, expenses and budget limit for trend chart."""

    user_id = session.get('user_id')

    try:

        from datetime import date as date_cls

        conn = get_db_connection()

        today = datetime.now().date()

        labels, income_vals, expense_vals, budget_vals = [], [], [], []

        with conn.cursor() as cur:

            for i in range(5, -1, -1):

                # Compute target month/year

                target = (today.replace(day=1) - timedelta(days=i * 30)).replace(day=1)

                m, y = target.month, target.year

                labels.append(target.strftime('%b %Y'))

                cur.execute("SELECT COALESCE(SUM(amount),0) AS t FROM income WHERE user_id=%s AND MONTH(income_date)=%s AND YEAR(income_date)=%s", (user_id, m, y))

                income_vals.append(float(cur.fetchone()['t']))

                cur.execute("SELECT COALESCE(SUM(amount),0) AS t FROM expenses WHERE user_id=%s AND MONTH(expense_date)=%s AND YEAR(expense_date)=%s", (user_id, m, y))

                expense_vals.append(float(cur.fetchone()['t']))

                cur.execute("SELECT COALESCE(SUM(limit_amount),0) AS t FROM budget WHERE user_id=%s AND month=%s AND year=%s", (user_id, m, y))

                budget_vals.append(float(cur.fetchone()['t']))

        conn.close()

        return jsonify({'labels': labels, 'income': income_vals, 'expenses': expense_vals, 'budget': budget_vals})

    except Exception as e:

        return jsonify({'error': str(e)}), 500

# ═══════════════════════════════════════════════════════════════════

# GOAL EXPENSE ACTIVITY FEED

# ═══════════════════════════════════════════════════════════════════

@app.route('/api/goal/<int:goal_id>/activity')

@login_required

def api_goal_activity(goal_id):

    """Return expense + savings activities for a goal (via linked budgets)."""

    user_id = session.get('user_id')

    try:

        conn = get_db_connection()

        with conn.cursor() as cur:

            # Verify goal belongs to user

            cur.execute("SELECT goal_name FROM goals WHERE id=%s AND user_id=%s", (goal_id, user_id))

            goal_row = cur.fetchone()

            if not goal_row:

                return jsonify({'error': 'Goal not found'}), 404

            # Savings activities

            cur.execute("""

                SELECT 'savings' AS type, amount, saving_date AS activity_date, note AS notes

                FROM savings_goals WHERE goal_id=%s ORDER BY saving_date DESC LIMIT 20

            """, (goal_id,))

            savings_acts = cur.fetchall()

            # Expenses from linked budget categories

            cur.execute("SELECT category FROM budget WHERE goal_id=%s AND user_id=%s", (goal_id, user_id))

            linked_cats = [r['category'] for r in cur.fetchall()]

            expense_acts = []

            if linked_cats:

                placeholders = ','.join(['%s'] * len(linked_cats))

                cur.execute(f"""

                    SELECT 'expense' AS type, amount, expense_date AS activity_date, category AS notes

                    FROM expenses WHERE user_id=%s AND category IN ({placeholders})

                    ORDER BY expense_date DESC LIMIT 20

                """, [user_id] + linked_cats)

                expense_acts = cur.fetchall()

        conn.close()

        activities = []

        for r in savings_acts:

            activities.append({'type': 'savings', 'amount': float(r['amount']), 'date': str(r['activity_date']), 'notes': r['notes'] or ''})

        for r in expense_acts:

            activities.append({'type': 'expense', 'amount': float(r['amount']), 'date': str(r['activity_date']), 'notes': r['notes'] or ''})

        activities.sort(key=lambda x: x['date'], reverse=True)

        return jsonify({'goal_name': goal_row['goal_name'], 'activities': activities[:30]})

    except Exception as e:

        return jsonify({'error': str(e)}), 500

# ═══════════════════════════════════════════════════════════════════

# UPDATED BUDGET CREATION — with goal_id support

# ═══════════════════════════════════════════════════════════════════

@app.route('/api/goals/active-list')

@login_required

def api_active_goals_list():

    """Return list of active goals for linking to budget."""

    user_id = session.get('user_id')

    try:

        conn = get_db_connection()

        with conn.cursor() as cur:

            cur.execute("SELECT id, goal_name, category FROM goals WHERE user_id=%s AND status='Active' ORDER BY goal_name ASC", (user_id,))

            rows = cur.fetchall()

        conn.close()

        return jsonify([{'id': r['id'], 'goal_name': r['goal_name'], 'category': r['category']} for r in rows])

    except Exception as e:

        return jsonify({'error': str(e)}), 500

@app.errorhandler(404)

# Handles 404 error

def not_found(e):

    return (render_template('login.html'), 404)

@app.errorhandler(500)

# Handles 500 error

def server_error(e):

    flash('An internal server error occurred.', 'danger')

    return (render_template('login.html'), 500)

if __name__ == '__main__':

    import os

    port = int(os.environ.get('PORT', 5000))

    app.run(debug=True, host='0.0.0.0', port=port)



# ========================================== 
# INLINE EMBEDDED TEMPLATES AND CSS RESOURCES
# ==========================================

import base64
from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader
from flask import Response

INLINE_TEMPLATES = {
    'dashboard.html': base64.b64decode('PCFkb2N0eXBlIGh0bWw+CjxodG1sIGxhbmc9ImVuIj4KPGhlYWQ+CiAgPG1ldGEgY2hhcnNldD0idXRmLTgiPgogIDxtZXRhIG5hbWU9InZpZXdwb3J0IiBjb250ZW50PSJ3aWR0aD1kZXZpY2Utd2lkdGgsIGluaXRpYWwtc2NhbGU9MSI+CiAgPHRpdGxlPkZpblNpZ2h0IC0gU21hcnQgRGFzaGJvYXJkPC90aXRsZT4KICA8bGluayByZWw9InByZWNvbm5lY3QiIGhyZWY9Imh0dHBzOi8vZm9udHMuZ29vZ2xlYXBpcy5jb20iPgogIDxsaW5rIHJlbD0icHJlY29ubmVjdCIgaHJlZj0iaHR0cHM6Ly9mb250cy5nc3RhdGljLmNvbSIgY3Jvc3NvcmlnaW4+CiAgPGxpbmsgaHJlZj0iaHR0cHM6Ly9mb250cy5nb29nbGVhcGlzLmNvbS9jc3MyP2ZhbWlseT1JbnRlcjp3Z2h0QDQwMDs1MDA7NjAwOzcwMDs4MDA7OTAwJmZhbWlseT1PdXRmaXQ6d2dodEA0MDA7NTAwOzYwMDs3MDA7ODAwJmRpc3BsYXk9c3dhcCIgcmVsPSJzdHlsZXNoZWV0Ij4KICA8bGluayBocmVmPSJodHRwczovL2Nkbi5qc2RlbGl2ci5uZXQvbnBtL2Jvb3RzdHJhcEA1LjMuMy9kaXN0L2Nzcy9ib290c3RyYXAubWluLmNzcyIgcmVsPSJzdHlsZXNoZWV0Ij4KICA8bGluayByZWw9InN0eWxlc2hlZXQiIGhyZWY9Imh0dHBzOi8vY2RuLmpzZGVsaXZyLm5ldC9ucG0vYm9vdHN0cmFwLWljb25zQDEuMTEuMy9mb250L2Jvb3RzdHJhcC1pY29ucy5jc3MiPgogIDxsaW5rIHJlbD0ic3R5bGVzaGVldCIgaHJlZj0ie3sgdXJsX2Zvcignc3RhdGljJywgZmlsZW5hbWU9J2Nzcy9kYXNoYm9hcmQuY3NzJykgfX0iPgogIDxsaW5rIHJlbD0ic3R5bGVzaGVldCIgaHJlZj0ie3sgdXJsX2Zvcignc3RhdGljJywgZmlsZW5hbWU9J2Nzcy9wYWdlcy5jc3MnKSB9fSI+CiAgPGxpbmsgcmVsPSJzdHlsZXNoZWV0IiBocmVmPSJ7eyB1cmxfZm9yKCdzdGF0aWMnLCBmaWxlbmFtZT0nY3NzL2N1cnNvci5jc3MnKSB9fSI+CiAgPGxpbmsgcmVsPSJzdHlsZXNoZWV0IiBocmVmPSJ7eyB1cmxfZm9yKCdzdGF0aWMnLCBmaWxlbmFtZT0nY3NzL3NtYXJ0X2Rhc2guY3NzJykgfX0iPgo8L2hlYWQ+Cjxib2R5IGNsYXNzPSJ0aGVtZS1kYXNoIj4KPGRpdiBpZD0iY3Vyc29yLWRvdCI+PC9kaXY+CjxkaXYgaWQ9ImN1cnNvci1yaW5nIj48L2Rpdj4KCjwhLS0gUHJvZmlsZSBDaGlwIC0tPgo8YSBocmVmPSJ7eyB1cmxfZm9yKCdwcm9maWxlX3BhZ2UnKSB9fSIgY2xhc3M9InByb2ZpbGUtY2hpcC1nbG9iYWwiIHRpdGxlPSJWaWV3IFByb2ZpbGUiPgogIDxkaXYgY2xhc3M9InByb2ZpbGUtY2hpcC1hdmF0YXIiPnt7IHVzZXJfbmFtZVswXXx1cHBlciBpZiB1c2VyX25hbWUgZWxzZSAnQScgfX08L2Rpdj4KICA8ZGl2IGNsYXNzPSJwcm9maWxlLWNoaXAtaW5mbyI+CiAgICA8c3BhbiBjbGFzcz0icHJvZmlsZS1jaGlwLW5hbWUiPnt7IHVzZXJfbmFtZSBpZiB1c2VyX25hbWUgZWxzZSAnQXJqdW4gTWVodGEnIH19PC9zcGFuPgogIDwvZGl2Pgo8L2E+CgoKPCEtLSBGbG9hdGluZyBIYW1idXJnZXIgLS0+CjxidXR0b24gY2xhc3M9ImZsb2F0aW5nLWhhbWJ1cmdlciIgaWQ9InNpZGViYXItdG9nZ2xlLWJ0biIgdHlwZT0iYnV0dG9uIiB0aXRsZT0iVG9nZ2xlIFNpZGViYXIgTWVudSI+CiAgPGkgY2xhc3M9ImJpIGJpLWxpc3QiPjwvaT4KPC9idXR0b24+Cgo8IS0tIE5vdGlmaWNhdGlvbiBCZWxsIC0tPgo8YnV0dG9uIGNsYXNzPSJub3RpZi1iZWxsLWJ0biIgaWQ9Im5vdGlmLWJlbGwtYnRuIiB0aXRsZT0iRmluYW5jaWFsIEFsZXJ0cyI+CiAgPGkgY2xhc3M9ImJpIGJpLWJlbGwtZmlsbCI+PC9pPgogIDxzcGFuIGNsYXNzPSJub3RpZi1iYWRnZSBoaWRkZW4iIGlkPSJub3RpZi1iYWRnZSI+MDwvc3Bhbj4KPC9idXR0b24+Cgo8IS0tIEFsZXJ0IFBhbmVsIE92ZXJsYXkgLS0+CjxkaXYgY2xhc3M9ImFsZXJ0LXBhbmVsLW92ZXJsYXkiIGlkPSJhbGVydC1wYW5lbC1vdmVybGF5Ij48L2Rpdj4KCjwhLS0gQWxlcnQgUGFuZWwgKFJpZ2h0IFNpZGUpIC0tPgo8ZGl2IGNsYXNzPSJhbGVydC1wYW5lbCIgaWQ9ImFsZXJ0LXBhbmVsIj4KICA8ZGl2IGNsYXNzPSJhbGVydC1wYW5lbC1oZWFkZXIiPgogICAgPGgzPjxpIGNsYXNzPSJiaSBiaS1zaGllbGQtZXhjbGFtYXRpb24iPjwvaT4gRmluYW5jaWFsIEFsZXJ0czwvaDM+CiAgICA8YnV0dG9uIGNsYXNzPSJhbGVydC1wYW5lbC1jbG9zZSIgaWQ9ImFsZXJ0LXBhbmVsLWNsb3NlIj48aSBjbGFzcz0iYmkgYmkteC1sZyI+PC9pPjwvYnV0dG9uPgogIDwvZGl2PgogIDxkaXYgY2xhc3M9ImFsZXJ0LXBhbmVsLWFjdGlvbnMiIHN0eWxlPSJkaXNwbGF5OiBmbGV4OyBnYXA6IDhweDsganVzdGlmeS1jb250ZW50OiBzcGFjZS1iZXR3ZWVuOyBhbGlnbi1pdGVtczogY2VudGVyOyI+CiAgICA8c3BhbiBjbGFzcz0iYWxlcnQtY291bnQtYmFkZ2UiIGlkPSJhbGVydC1jb3VudC10ZXh0Ij4wIFVucmVhZDwvc3Bhbj4KICAgIDxkaXYgc3R5bGU9ImRpc3BsYXk6IGZsZXg7IGdhcDogNnB4OyI+CiAgICAgIDxidXR0b24gY2xhc3M9Im1hcmstYWxsLXJlYWQtYnRuIiBpZD0ibWFyay1hbGwtcmVhZC1idG4iIHN0eWxlPSJ3aGl0ZS1zcGFjZTogbm93cmFwOyI+JiMxMDAwMzsgTWFyayBSZWFkPC9idXR0b24+CiAgICAgIDxidXR0b24gY2xhc3M9ImNsZWFyLWFsbC1idG4iIGlkPSJjbGVhci1hbGwtYnRuIiBzdHlsZT0iYmFja2dyb3VuZDpub25lO2JvcmRlcjoxcHggc29saWQgcmdiYSgyNTUsMjU1LDI1NSwwLjE4KTtjb2xvcjojRUY0NDQ0O2ZvbnQtc2l6ZTowLjczcmVtO3BhZGRpbmc6NHB4IDEwcHg7Ym9yZGVyLXJhZGl1czoxMDBweDtjdXJzb3I6cG9pbnRlcjt0cmFuc2l0aW9uOmFsbCAwLjJzO3doaXRlLXNwYWNlOiBub3dyYXA7Ij7wn5eRIENsZWFyIEFsbDwvYnV0dG9uPgogICAgPC9kaXY+CiAgPC9kaXY+CiAgPGRpdiBjbGFzcz0iYWxlcnQtbGlzdCIgaWQ9ImFsZXJ0LWxpc3QiPgogICAgPGRpdiBjbGFzcz0iYWxlcnQtZW1wdHkiPjxpIGNsYXNzPSJiaSBiaS1jaGVjazItY2lyY2xlIj48L2k+Tm8gYWxlcnRzIHlldC4gS2VlcCB0cmFja2luZyE8L2Rpdj4KICA8L2Rpdj4KPC9kaXY+Cgo8ZGl2IGNsYXNzPSJkLWZsZXgiPgoKICA8IS0tIExlZnQgU2lkZWJhciAtLT4KICA8YXNpZGUgY2xhc3M9InNpZGViYXIiIGlkPSJzaWRlYmFyIj4KICAgIDxkaXYgY2xhc3M9ImxvZ28tcm93Ij4KICAgICAgPGltZyBzcmM9Int7IHVybF9mb3IoJ3N0YXRpYycsIGZpbGVuYW1lPSdpbWFnZXMvbG9nby5qcGVnJykgfX0iIGFsdD0iRmluU2lnaHQgTG9nbyIgY2xhc3M9ImRhc2gtbmF2LWxvZ28taW1nIiBzdHlsZT0id2lkdGg6NDJweDtoZWlnaHQ6NDJweDsiPgogICAgICA8ZGl2IGNsYXNzPSJsb2dvLXRleHQiPgogICAgICAgIDxoMz5GaW5TaWdodDwvaDM+CiAgICAgICAgPHNtYWxsPlNtYXJ0LiBTZWN1cmUuIFNpbXBsZS48L3NtYWxsPgogICAgICA8L2Rpdj4KICAgIDwvZGl2PgogICAgPG5hdiBjbGFzcz0ibmF2LWxpc3QiPgogICAgICA8YSBocmVmPSJ7eyB1cmxfZm9yKCdkYXNoYm9hcmQnKSB9fSIgY2xhc3M9Im5hdi1pdGVtIGFjdGl2ZSI+PGkgY2xhc3M9ImJpIGJpLWdyaWQtMXgyLWZpbGwiPjwvaT48c3Bhbj5EYXNoYm9hcmQ8L3NwYW4+PC9hPgogICAgICA8YSBocmVmPSJ7eyB1cmxfZm9yKCdhZGRfaW5jb21lJykgfX0iIGNsYXNzPSJuYXYtaXRlbSI+PGkgY2xhc3M9ImJpIGJpLWNhc2gtY29pbiI+PC9pPjxzcGFuPkluY29tZTwvc3Bhbj48L2E+CiAgICAgIDxhIGhyZWY9Int7IHVybF9mb3IoJ2FkZF9leHBlbnNlJykgfX0iIGNsYXNzPSJuYXYtaXRlbSI+PGkgY2xhc3M9ImJpIGJpLXdhbGxldDIiPjwvaT48c3Bhbj5FeHBlbnNlczwvc3Bhbj48L2E+CiAgICAgIDxhIGhyZWY9Int7IHVybF9mb3IoJ2FkZF9idWRnZXQnKSB9fSIgY2xhc3M9Im5hdi1pdGVtIj48aSBjbGFzcz0iYmkgYmktcGllLWNoYXJ0LWZpbGwiPjwvaT48c3Bhbj5CdWRnZXQ8L3NwYW4+PC9hPgogICAgICA8YSBocmVmPSJ7eyB1cmxfZm9yKCdhZGRfaW52ZXN0bWVudCcpIH19IiBjbGFzcz0ibmF2LWl0ZW0iPjxpIGNsYXNzPSJiaSBiaS1ncmFwaC11cC1hcnJvdyI+PC9pPjxzcGFuPkludmVzdG1lbnRzPC9zcGFuPjwvYT4KICAgICAgPGEgaHJlZj0ie3sgdXJsX2ZvcignZ29hbHNfbGlzdCcpIH19IiBjbGFzcz0ibmF2LWl0ZW0iPjxpIGNsYXNzPSJiaSBiaS1mbGFnLWZpbGwiPjwvaT48c3Bhbj5Hb2Fsczwvc3Bhbj48L2E+CiAgICAgIDxhIGhyZWY9Int7IHVybF9mb3IoJ3Byb2ZpbGVfcGFnZScpIH19IiBjbGFzcz0ibmF2LWl0ZW0iPjxpIGNsYXNzPSJiaSBiaS1wZXJzb24tY2lyY2xlIj48L2k+PHNwYW4+UHJvZmlsZTwvc3Bhbj48L2E+CiAgICA8L25hdj4KICAgIDxidXR0b24gY2xhc3M9InNpZGViYXItcmVzZXQtYnRuIiBpZD0ic2lkZWJhci1yZXNldC1idG4iIHR5cGU9ImJ1dHRvbiIKICAgICAgb25jbGljaz0iaWYoY29uZmlybSgnUmVzZXQgYWxsIGRhdGEgdG8gMD8nKSl7ZmV0Y2goJy9hcGkvcmVzZXQtZGF0YScse21ldGhvZDonUE9TVCd9KS50aGVuKCgpPT53aW5kb3cubG9jYXRpb24uaHJlZj0nL2Rhc2hib2FyZCcpO30iCiAgICAgIHRpdGxlPSJSZXNldCBhbGwgZGF0YSI+CiAgICAgIDxpIGNsYXNzPSJiaSBiaS10cmFzaCI+PC9pPjxzcGFuPlJlc2V0IERhdGE8L3NwYW4+CiAgICA8L2J1dHRvbj4KICAgIDxhIGhyZWY9Int7IHVybF9mb3IoJ2xvZ291dCcpIH19IiBjbGFzcz0ic2lkZWJhci1sb2dvdXQtYnRuIiB0aXRsZT0iTG9nb3V0Ij4KICAgICAgPGkgY2xhc3M9ImJpIGJpLWJveC1hcnJvdy1yaWdodCI+PC9pPjxzcGFuPkxvZ291dDwvc3Bhbj4KICAgIDwvYT4KICA8L2FzaWRlPgoKICA8IS0tIE1haW4gUGFuZWwgLS0+CiAgPG1haW4gY2xhc3M9Im1haW4tcGFuZWwiPgogICAgPGRpdiBjbGFzcz0iY29udGVudC1zdGFjayI+CgogICAgICA8IS0tIEhlcm8gQmFubmVyIC0tPgogICAgICA8ZGl2IGNsYXNzPSJzbWFydC1kYXNoLWhlcm8iPgogICAgICAgIDxkaXYgY2xhc3M9Imhlcm8tZ3JlZXRpbmciPgogICAgICAgICAgPGgxIGlkPSJkYXNoYm9hcmQtZ3JlZXRpbmciIGRhdGEtdXNlcm5hbWU9Int7IHVzZXJfbmFtZSB9fSI+SGVsbG8sIHt7IHVzZXJfbmFtZSB9fSE8L2gxPgogICAgICAgICAgPHA+V2VsY29tZSBiYWNrIHRvIEZpblNpZ2h0ICZtZGFzaDsgeW91ciBjb21wbGV0ZSBmaW5hbmNpYWwgY29tbWFuZCBjZW50ZXIuPC9wPgogICAgICAgIDwvZGl2PgogICAgICAgIDxkaXYgY2xhc3M9Imhlcm8tZGF0ZS1iYWRnZSI+CiAgICAgICAgICA8c3Ryb25nIGlkPSJ0b3BiYXItZGF0ZSI+Jm1kYXNoOzwvc3Ryb25nPgogICAgICAgICAgPHNwYW4gaWQ9InRvcGJhci1kYXkiPiZtZGFzaDs8L3NwYW4+CiAgICAgICAgPC9kaXY+CiAgICAgIDwvZGl2PgoKICAgICAgPCEtLSBTbWFydCBLUEkgUm93IC0tPgogICAgICA8ZGl2IGNsYXNzPSJzbWFydC1rcGktcm93Ij4KICAgICAgICA8ZGl2IGNsYXNzPSJrcGktY2FyZCBrcGktYmx1ZSI+CiAgICAgICAgICA8ZGl2IGNsYXNzPSJrcGktbGFiZWwiPlRvdGFsIEluY29tZTwvZGl2PgogICAgICAgICAgPGRpdiBjbGFzcz0ia3BpLXZhbHVlIiBpZD0ia3BpLWluY29tZSI+JiM4Mzc3OzA8L2Rpdj4KICAgICAgICAgIDxkaXYgY2xhc3M9ImtwaS1zdWIiIGlkPSJrcGktaW5jb21lLXN1YiI+LS0gdnMgbGFzdCBtb250aDwvZGl2PgogICAgICAgICAgPGkgY2xhc3M9ImJpIGJpLWJyaWVmY2FzZS1maWxsIGtwaS1pY29uIj48L2k+CiAgICAgICAgPC9kaXY+CiAgICAgICAgPGRpdiBjbGFzcz0ia3BpLWNhcmQga3BpLW9yYW5nZSI+CiAgICAgICAgICA8ZGl2IGNsYXNzPSJrcGktbGFiZWwiPlRvdGFsIEV4cGVuc2VzPC9kaXY+CiAgICAgICAgICA8ZGl2IGNsYXNzPSJrcGktdmFsdWUiIGlkPSJrcGktZXhwZW5zZXMiPiYjODM3NzswPC9kaXY+CiAgICAgICAgICA8ZGl2IGNsYXNzPSJrcGktc3ViIiBpZD0ia3BpLWV4cGVuc2VzLXN1YiI+LS0gdnMgbGFzdCBtb250aDwvZGl2PgogICAgICAgICAgPGkgY2xhc3M9ImJpIGJpLWNhcnQzIGtwaS1pY29uIj48L2k+CiAgICAgICAgPC9kaXY+CiAgICAgICAgPGRpdiBjbGFzcz0ia3BpLWNhcmQga3BpLXB1cnBsZSI+CiAgICAgICAgICA8ZGl2IGNsYXNzPSJrcGktbGFiZWwiPkJ1ZGdldCBVc2VkPC9kaXY+CiAgICAgICAgICA8ZGl2IGNsYXNzPSJrcGktdmFsdWUiIGlkPSJrcGktYnVkZ2V0LXBjdCI+MCU8L2Rpdj4KICAgICAgICAgIDxkaXYgY2xhc3M9ImtwaS1zdWIiIGlkPSJrcGktYnVkZ2V0LXN1YiI+b2YgbW9udGhseSBsaW1pdDwvZGl2PgogICAgICAgICAgPGkgY2xhc3M9ImJpIGJpLXBpZS1jaGFydC1maWxsIGtwaS1pY29uIj48L2k+CiAgICAgICAgPC9kaXY+CiAgICAgICAgPGRpdiBjbGFzcz0ia3BpLWNhcmQga3BpLWdyZWVuIj4KICAgICAgICAgIDxkaXYgY2xhc3M9ImtwaS1sYWJlbCI+U2F2aW5ncyBSYXRlPC9kaXY+CiAgICAgICAgICA8ZGl2IGNsYXNzPSJrcGktdmFsdWUiIGlkPSJrcGktc2F2aW5ncy1yYXRlIj4wJTwvZGl2PgogICAgICAgICAgPGRpdiBjbGFzcz0ia3BpLXN1YiI+b2YgaW5jb21lIHNhdmVkPC9kaXY+CiAgICAgICAgICA8aSBjbGFzcz0iYmkgYmktcGlnZ3ktYmFuay1maWxsIGtwaS1pY29uIj48L2k+CiAgICAgICAgPC9kaXY+CiAgICAgICAgPGRpdiBjbGFzcz0ia3BpLWNhcmQga3BpLWluZGlnbyI+CiAgICAgICAgICA8ZGl2IGNsYXNzPSJrcGktbGFiZWwiPkFjdGl2ZSBHb2FsczwvZGl2PgogICAgICAgICAgPGRpdiBjbGFzcz0ia3BpLXZhbHVlIiBpZD0ia3BpLWdvYWxzIj4wPC9kaXY+CiAgICAgICAgICA8ZGl2IGNsYXNzPSJrcGktc3ViIiBpZD0ia3BpLWdvYWxzLXN1YiI+aW4gcHJvZ3Jlc3M8L2Rpdj4KICAgICAgICAgIDxpIGNsYXNzPSJiaSBiaS1mbGFnLWZpbGwga3BpLWljb24iPjwvaT4KICAgICAgICA8L2Rpdj4KICAgICAgPC9kaXY+CgogICAgICA8IS0tIFRocmVlIENvbHVtbjogRG91Z2hudXQgKyBUcmFuc2FjdGlvbnMgKyBJbnNpZ2h0cyAtLT4KICAgICAgPHNlY3Rpb24gY2xhc3M9InRocmVlLWNvbCIgc3R5bGU9Im1hcmdpbi1ib3R0b206MjRweDsiPgogICAgICAgIDxhcnRpY2xlIGNsYXNzPSJwYW5lbCBhbmFseXRpY3MtcGFuZWwiPgogICAgICAgICAgPGRpdiBjbGFzcz0icGFuZWwtdGl0bGUtcm93IiBzdHlsZT0iZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2FsaWduLWl0ZW1zOmZsZXgtc3RhcnQ7Ij4KICAgICAgICAgICAgPGRpdj4KICAgICAgICAgICAgICA8aDQgc3R5bGU9ImZvbnQtd2VpZ2h0OjgwMDtmb250LXNpemU6MS4wNXJlbTtjb2xvcjojMEYxNzJBO21hcmdpbjowOyI+SW5jb21lIEFsbG9jYXRpb248L2g0PgogICAgICAgICAgICAgIDxkaXYgaWQ9ImluY29tZS1hbGxvY2F0aW9uLXN1YnRpdGxlIiBzdHlsZT0iZm9udC1zaXplOjAuODJyZW07Y29sb3I6IzY0NzQ4QjttYXJnaW4tdG9wOjJweDsiPkhvdyB5b3VyIGluY29tZSBpcyBzcGxpdDwvZGl2PgogICAgICAgICAgICA8L2Rpdj4KICAgICAgICAgIDwvZGl2PgogICAgICAgICAgPGRpdiBjbGFzcz0iYW5hbHl0aWNzLWJvZHkiPgogICAgICAgICAgICA8ZGl2IGNsYXNzPSJjaGFydC13cmFwcGVyIj48Y2FudmFzIGlkPSJhbmFseXRpY3NDaGFydCIgd2lkdGg9IjIyMCIgaGVpZ2h0PSIyMjAiPjwvY2FudmFzPjwvZGl2PgogICAgICAgICAgICA8ZGl2IGNsYXNzPSJsZWdlbmQtbGlzdCI+PC9kaXY+CiAgICAgICAgICA8L2Rpdj4KICAgICAgICAgIDxkaXYgY2xhc3M9ImZvb3Rlci1zdHJpcCI+CiAgICAgICAgICAgIDxkaXYgY2xhc3M9InN1bW1hcnktcGlsbCI+PGkgY2xhc3M9ImJpIGJpLXdhbGxldDIiPjwvaT48c3BhbiBpZD0ic2F2aW5ncy1kaWZmLXRleHQiPkxpdmUgZmluYW5jaWFsIGJyZWFrZG93bjwvc3Bhbj48L2Rpdj4KICAgICAgICAgIDwvZGl2PgogICAgICAgIDwvYXJ0aWNsZT4KCiAgICAgICAgPGFydGljbGUgY2xhc3M9InBhbmVsIj4KICAgICAgICAgIDxkaXYgY2xhc3M9InBhbmVsLXRpdGxlLXJvdyI+CiAgICAgICAgICAgIDxoND5SZWNlbnQgVHJhbnNhY3Rpb25zPC9oND4KICAgICAgICAgICAgPGEgY2xhc3M9ImxpbmstYmx1ZSIgaHJlZj0ie3sgdXJsX2ZvcignYWRkX2V4cGVuc2UnKSB9fSI+VmlldyBBbGwgJiM4NTk0OzwvYT4KICAgICAgICAgIDwvZGl2PgogICAgICAgICAgPGRpdiBjbGFzcz0idHJhbnNhY3Rpb24tbGlzdCI+PC9kaXY+CiAgICAgICAgPC9hcnRpY2xlPgoKICAgICAgICA8YXJ0aWNsZSBjbGFzcz0icGFuZWwiPgogICAgICAgICAgPGRpdiBjbGFzcz0icGFuZWwtdGl0bGUtcm93Ij48aDQ+RGFzaGJvYXJkIEluc2lnaHRzPC9oND48L2Rpdj4KICAgICAgICAgIDxkaXYgY2xhc3M9Imluc2lnaHQtbGlzdCI+PC9kaXY+CiAgICAgICAgPC9hcnRpY2xlPgogICAgICA8L3NlY3Rpb24+CgogICAgICA8IS0tIE1vbnRobHkgVHJlbmQgQ2hhcnQgLS0+CiAgICAgIDxkaXYgY2xhc3M9InRyZW5kLXNlY3Rpb24iPgogICAgICAgIDxkaXYgY2xhc3M9InRyZW5kLWhlYWRlciI+CiAgICAgICAgICA8ZGl2IGNsYXNzPSJ0cmVuZC10aXRsZSI+TW9udGhseSBJbmNvbWUgdnMgRXhwZW5zZXMgdnMgQnVkZ2V0PC9kaXY+CiAgICAgICAgICA8ZGl2IGNsYXNzPSJ0cmVuZC1sZWdlbmQiPgogICAgICAgICAgICA8ZGl2IGNsYXNzPSJ0cmVuZC1sZWdlbmQtaXRlbSI+PGRpdiBjbGFzcz0idHJlbmQtbGVnZW5kLWRvdCIgc3R5bGU9ImJhY2tncm91bmQ6IzNCODJGNjsiPjwvZGl2PkluY29tZTwvZGl2PgogICAgICAgICAgICA8ZGl2IGNsYXNzPSJ0cmVuZC1sZWdlbmQtaXRlbSI+PGRpdiBjbGFzcz0idHJlbmQtbGVnZW5kLWRvdCIgc3R5bGU9ImJhY2tncm91bmQ6I0VGNDQ0NDsiPjwvZGl2PkV4cGVuc2VzPC9kaXY+CiAgICAgICAgICAgIDxkaXYgY2xhc3M9InRyZW5kLWxlZ2VuZC1pdGVtIj48ZGl2IGNsYXNzPSJ0cmVuZC1sZWdlbmQtZG90IiBzdHlsZT0iYmFja2dyb3VuZDojRjU5RTBCO3dpZHRoOjEycHg7aGVpZ2h0OjRweDtib3JkZXItcmFkaXVzOjJweDttYXJnaW4tdG9wOjNweDsiPjwvZGl2PkJ1ZGdldCBMaW1pdDwvZGl2PgogICAgICAgICAgPC9kaXY+CiAgICAgICAgPC9kaXY+CiAgICAgICAgPGRpdiBjbGFzcz0idHJlbmQtY2hhcnQtd3JhcCI+PGNhbnZhcyBpZD0ibW9udGhseVRyZW5kQ2hhcnQiPjwvY2FudmFzPjwvZGl2PgogICAgICA8L2Rpdj4KCiAgICAgIDwhLS0gQUkgU3BlbmRpbmcgSW5zaWdodHMgLS0+CiAgICAgIDxkaXYgY2xhc3M9ImFpLXNlY3Rpb24iPgogICAgICAgIDxkaXYgY2xhc3M9ImFpLWhlYWRlciI+CiAgICAgICAgICA8c3BhbiBjbGFzcz0iYWktYmFkZ2UiPkFJIEFOQUxZU0lTPC9zcGFuPgogICAgICAgICAgPHNwYW4gY2xhc3M9ImFpLXRpdGxlIj5TbWFydCBTcGVuZGluZyBJbnNpZ2h0czwvc3Bhbj4KICAgICAgICA8L2Rpdj4KICAgICAgICA8ZGl2IGNsYXNzPSJhaS1ncmlkIiBpZD0iYWktaW5zaWdodHMtZ3JpZCI+CiAgICAgICAgICA8ZGl2IGNsYXNzPSJhaS1jYXJkIj4KICAgICAgICAgICAgPGRpdiBjbGFzcz0iYWktY2FyZC10b3AiPjxzcGFuIGNsYXNzPSJhaS1jYXJkLWljb24iPiYjODk4Nzs8L3NwYW4+PC9kaXY+CiAgICAgICAgICAgIDxkaXYgY2xhc3M9ImFpLWNhcmQtdGl0bGUiPkxvYWRpbmcgSW5zaWdodHMuLi48L2Rpdj4KICAgICAgICAgICAgPGRpdiBjbGFzcz0iYWktY2FyZC10ZXh0Ij5BbmFseXppbmcgeW91ciBmaW5hbmNpYWwgcGF0dGVybnMuPC9kaXY+CiAgICAgICAgICA8L2Rpdj4KICAgICAgICA8L2Rpdj4KICAgICAgPC9kaXY+CgogICAgICA8IS0tIEJ1ZGdldCBUcmFja2VyIHdpdGggR29hbCBMaW5rcyAtLT4KICAgICAgPGRpdiBzdHlsZT0ibWFyZ2luLWJvdHRvbToyNHB4OyI+CiAgICAgICAgPGRpdiBjbGFzcz0ic2VjdGlvbi10aXRsZS1yb3ciPgogICAgICAgICAgPGRpdiBjbGFzcz0ic2VjdGlvbi10aXRsZS1iYXIiIHN0eWxlPSJiYWNrZ3JvdW5kOmxpbmVhci1ncmFkaWVudCgxODBkZWcsIzhCNUNGNiwjNjM2NkYxKTsiPjwvZGl2PgogICAgICAgICAgPGg0IGNsYXNzPSJzZWN0aW9uLXRpdGxlIj5CdWRnZXQgVHJhY2tlcjwvaDQ+CiAgICAgICAgICA8YSBocmVmPSJ7eyB1cmxfZm9yKCdhZGRfYnVkZ2V0JykgfX0iIGNsYXNzPSJzZWN0aW9uLWxpbmsiPisgQWRkIEJ1ZGdldCAmIzg1OTQ7PC9hPgogICAgICAgIDwvZGl2PgogICAgICAgIDxkaXYgY2xhc3M9ImJ1ZGdldC10cmFja2VyLWdyaWQiIGlkPSJidWRnZXQtdHJhY2tlci1ncmlkIj4KICAgICAgICAgIDxkaXYgc3R5bGU9ImNvbG9yOiM5NEEzQjg7Zm9udC1zaXplOjAuODVyZW07cGFkZGluZzoyMHB4IDA7Ij5Mb2FkaW5nIGJ1ZGdldHMuLi48L2Rpdj4KICAgICAgICA8L2Rpdj4KICAgICAgPC9kaXY+CgogICAgICA8IS0tIEdvYWxzIERhc2hib2FyZCBIZWFkZXIgLS0+CiAgICAgIDxkaXYgY2xhc3M9InBhZ2UtaGVybyBkYXNoLWhlcm8gbXQtMiIgc3R5bGU9ImJhY2tncm91bmQ6bGluZWFyLWdyYWRpZW50KDEzNWRlZywjMUUxQjRCIDAlLCMzMTJFODEgMTAwJSk7bWFyZ2luLXRvcDowIWltcG9ydGFudDsiPgogICAgICAgIDxkaXYgY2xhc3M9Imhlcm8tbGVmdCI+CiAgICAgICAgICA8ZGl2IGNsYXNzPSJoZXJvLWljb24td3JhcCBkYXNoLWljb24td3JhcCIgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgyNTUsMjU1LDI1NSwwLjE1KTsiPgogICAgICAgICAgICA8aSBjbGFzcz0iYmkgYmktYnVsbHNleWUgdGV4dC13aGl0ZSI+PC9pPgogICAgICAgICAgPC9kaXY+CiAgICAgICAgICA8ZGl2PgogICAgICAgICAgICA8aDEgY2xhc3M9Imhlcm8tdGl0bGUgdGV4dC13aGl0ZSIgc3R5bGU9ImZvbnQtc2l6ZToxLjRyZW07bWFyZ2luLWJvdHRvbToycHg7Ij5Hb2FscyAmYW1wOyBTYXZpbmdzIERhc2hib2FyZDwvaDE+CiAgICAgICAgICAgIDxwIGNsYXNzPSJoZXJvLXN1YnRpdGxlIHRleHQtd2hpdGUtNTAiPlRyYWNrIG1pbGVzdG9uZXMsIHNhdmluZ3MgcHJvZ3Jlc3MsIGFuZCB0YXJnZXQgdHJlbmRzLjwvcD4KICAgICAgICAgIDwvZGl2PgogICAgICAgIDwvZGl2PgogICAgICA8L2Rpdj4KCiAgICAgIDxzZWN0aW9uIGNsYXNzPSJ0aHJlZS1jb2wiIHN0eWxlPSJtYXJnaW4tdG9wOjIwcHg7Ij4KICAgICAgICA8YXJ0aWNsZSBjbGFzcz0icGFuZWwiPgogICAgICAgICAgPGRpdiBjbGFzcz0icGFuZWwtdGl0bGUtcm93Ij48aDQgc3R5bGU9ImZvbnQtd2VpZ2h0OjgwMDtmb250LXNpemU6MXJlbTtjb2xvcjojMEYxNzJBO21hcmdpbjowOyI+R29hbCBTdGF0dXM8L2g0PjwvZGl2PgogICAgICAgICAgPGRpdiBjbGFzcz0iYW5hbHl0aWNzLWJvZHkiPjxkaXYgY2xhc3M9ImNoYXJ0LXdyYXBwZXIiIHN0eWxlPSJoZWlnaHQ6MjAwcHg7Ij48Y2FudmFzIGlkPSJnb2FsU3RhdHVzQ2hhcnQiPjwvY2FudmFzPjwvZGl2PjwvZGl2PgogICAgICAgIDwvYXJ0aWNsZT4KICAgICAgICA8YXJ0aWNsZSBjbGFzcz0icGFuZWwiPgogICAgICAgICAgPGRpdiBjbGFzcz0icGFuZWwtdGl0bGUtcm93Ij48aDQgc3R5bGU9ImZvbnQtd2VpZ2h0OjgwMDtmb250LXNpemU6MXJlbTtjb2xvcjojMEYxNzJBO21hcmdpbjowOyI+Q2F0ZWdvcnkgRGlzdHJpYnV0aW9uPC9oND48L2Rpdj4KICAgICAgICAgIDxkaXYgY2xhc3M9ImFuYWx5dGljcy1ib2R5Ij48ZGl2IGNsYXNzPSJjaGFydC13cmFwcGVyIiBzdHlsZT0iaGVpZ2h0OjIwMHB4OyI+PGNhbnZhcyBpZD0iZ29hbENhdGVnb3J5Q2hhcnQiPjwvY2FudmFzPjwvZGl2PjwvZGl2PgogICAgICAgIDwvYXJ0aWNsZT4KICAgICAgICA8YXJ0aWNsZSBjbGFzcz0icGFuZWwiPgogICAgICAgICAgPGRpdiBjbGFzcz0icGFuZWwtdGl0bGUtcm93Ij4KICAgICAgICAgICAgPGg0IHN0eWxlPSJmb250LXdlaWdodDo4MDA7Zm9udC1zaXplOjFyZW07Y29sb3I6IzBGMTcyQTttYXJnaW46MDsiPlJlY2VudCBHb2FsczwvaDQ+CiAgICAgICAgICAgIDxhIGNsYXNzPSJsaW5rLWJsdWUiIGhyZWY9Int7IHVybF9mb3IoJ2dvYWxzX2xpc3QnKSB9fSI+VmlldyBBbGwgJiM4NTk0OzwvYT4KICAgICAgICAgIDwvZGl2PgogICAgICAgICAgPGRpdiBjbGFzcz0idHJhbnNhY3Rpb24tbGlzdCIgaWQ9InJlY2VudC1nb2Fscy1saXN0IiBzdHlsZT0ibWFyZ2luLXRvcDoxNXB4OyI+PC9kaXY+CiAgICAgICAgPC9hcnRpY2xlPgogICAgICA8L3NlY3Rpb24+CgogICAgICA8c2VjdGlvbiBjbGFzcz0idGhyZWUtY29sIiBzdHlsZT0iZ3JpZC10ZW1wbGF0ZS1jb2x1bW5zOnJlcGVhdCgyLDFmcik7bWFyZ2luLWJvdHRvbTo0MHB4OyI+CiAgICAgICAgPGFydGljbGUgY2xhc3M9InBhbmVsIj4KICAgICAgICAgIDxkaXYgY2xhc3M9InBhbmVsLXRpdGxlLXJvdyI+PGg0IHN0eWxlPSJmb250LXdlaWdodDo4MDA7Zm9udC1zaXplOjFyZW07Y29sb3I6IzBGMTcyQTttYXJnaW46MDsiPkdvYWwgVGFyZ2V0IHZzIFNhdmVkPC9oND48L2Rpdj4KICAgICAgICAgIDxkaXYgY2xhc3M9ImxpbmUtY2hhcnQtYm94IiBzdHlsZT0iaGVpZ2h0OjIyMHB4OyI+PGNhbnZhcyBpZD0iZ29hbFRhcmdldFZzU2F2ZWRDaGFydCI+PC9jYW52YXM+PC9kaXY+CiAgICAgICAgPC9hcnRpY2xlPgogICAgICAgIDxhcnRpY2xlIGNsYXNzPSJwYW5lbCI+CiAgICAgICAgICA8ZGl2IGNsYXNzPSJwYW5lbC10aXRsZS1yb3ciPjxoNCBzdHlsZT0iZm9udC13ZWlnaHQ6ODAwO2ZvbnQtc2l6ZToxcmVtO2NvbG9yOiMwRjE3MkE7bWFyZ2luOjA7Ij5Nb250aGx5IFNhdmluZ3MgVHJlbmQ8L2g0PjwvZGl2PgogICAgICAgICAgPGRpdiBjbGFzcz0ibGluZS1jaGFydC1ib3giIHN0eWxlPSJoZWlnaHQ6MjIwcHg7Ij48Y2FudmFzIGlkPSJnb2FsVHJlbmRDaGFydCI+PC9jYW52YXM+PC9kaXY+CiAgICAgICAgPC9hcnRpY2xlPgogICAgICA8L3NlY3Rpb24+CgogICAgPC9kaXY+CiAgPC9tYWluPgo8L2Rpdj4KCjxzY3JpcHQgc3JjPSJodHRwczovL2Nkbi5qc2RlbGl2ci5uZXQvbnBtL2Jvb3RzdHJhcEA1LjMuMy9kaXN0L2pzL2Jvb3RzdHJhcC5idW5kbGUubWluLmpzIj48L3NjcmlwdD4KPHNjcmlwdCBzcmM9Imh0dHBzOi8vY2RuLmpzZGVsaXZyLm5ldC9ucG0vY2hhcnQuanMiPjwvc2NyaXB0Pgo8c2NyaXB0IHNyYz0ie3sgdXJsX2Zvcignc3RhdGljJywgZmlsZW5hbWU9J2pzL2Rhc2hib2FyZC5qcycpIH19Ij48L3NjcmlwdD4KPHNjcmlwdCBzcmM9Int7IHVybF9mb3IoJ3N0YXRpYycsIGZpbGVuYW1lPSdqcy9hbGVydHMuanMnKSB9fSI+PC9zY3JpcHQ+CjxzY3JpcHQgc3JjPSJ7eyB1cmxfZm9yKCdzdGF0aWMnLCBmaWxlbmFtZT0nanMvY3Vyc29yLmpzJykgfX0iPjwvc2NyaXB0Pgo8c2NyaXB0PgogIChmdW5jdGlvbigpewogICAgdmFyIG5vdz1uZXcgRGF0ZSgpOwogICAgdmFyIGRheXM9WydTdW5kYXknLCdNb25kYXknLCdUdWVzZGF5JywnV2VkbmVzZGF5JywnVGh1cnNkYXknLCdGcmlkYXknLCdTYXR1cmRheSddOwogICAgdmFyIG1vbnRocz1bJ0phbnVhcnknLCdGZWJydWFyeScsJ01hcmNoJywnQXByaWwnLCdNYXknLCdKdW5lJywnSnVseScsJ0F1Z3VzdCcsJ1NlcHRlbWJlcicsJ09jdG9iZXInLCdOb3ZlbWJlcicsJ0RlY2VtYmVyJ107CiAgICB2YXIgZD1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgndG9wYmFyLWRhdGUnKTsKICAgIHZhciBkeT1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgndG9wYmFyLWRheScpOwogICAgaWYoZCkgZC50ZXh0Q29udGVudD1ub3cuZ2V0RGF0ZSgpKycgJyttb250aHNbbm93LmdldE1vbnRoKCldKycgJytub3cuZ2V0RnVsbFllYXIoKTsKICAgIGlmKGR5KSBkeS50ZXh0Q29udGVudD1kYXlzW25vdy5nZXREYXkoKV07CiAgICB2YXIgZWw9ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ2Rhc2hib2FyZC1ncmVldGluZycpOwogICAgaWYoZWwpewogICAgICB2YXIgdXNlcm5hbWU9ZWwuZ2V0QXR0cmlidXRlKCdkYXRhLXVzZXJuYW1lJyl8fCdVc2VyJzsKICAgICAgdmFyIGhvdXI9bm93LmdldEhvdXJzKCk7CiAgICAgIHZhciBncmVldD1ob3VyPDEyPydHb29kIG1vcm5pbmcnOmhvdXI8MTc/J0dvb2QgYWZ0ZXJub29uJzonR29vZCBldmVuaW5nJzsKICAgICAgdmFyIGVtb2ppPWhvdXI8MTI/J1x1MjYwMFx1ZmUwZic6aG91cjwxNz8nXHUyNmM1JzonXHVkODNjXHVkZjE5JzsKICAgICAgZWwudGV4dENvbnRlbnQ9Z3JlZXQrJywgJyt1c2VybmFtZSsnISAnK2Vtb2ppOwogICAgfQogIH0pKCk7Cjwvc2NyaXB0Pgo8L2JvZHk+CjwvaHRtbD4=').decode('utf-8'),
    'ai_insights.html': base64.b64decode('PCFkb2N0eXBlIGh0bWw+CjxodG1sIGxhbmc9ImVuIj4KPGhlYWQ+CiAgPG1ldGEgY2hhcnNldD0idXRmLTgiPgogIDxtZXRhIG5hbWU9InZpZXdwb3J0IiBjb250ZW50PSJ3aWR0aD1kZXZpY2Utd2lkdGgsIGluaXRpYWwtc2NhbGU9MSI+CiAgPHRpdGxlPkFJIEluc2lnaHRzIOKAkyBGaW5TaWdodDwvdGl0bGU+CiAgPGxpbmsgcmVsPSJwcmVjb25uZWN0IiBocmVmPSJodHRwczovL2ZvbnRzLmdvb2dsZWFwaXMuY29tIj4KICA8bGluayByZWw9InByZWNvbm5lY3QiIGhyZWY9Imh0dHBzOi8vZm9udHMuZ3N0YXRpYy5jb20iIGNyb3Nzb3JpZ2luPgogIDxsaW5rIGhyZWY9Imh0dHBzOi8vZm9udHMuZ29vZ2xlYXBpcy5jb20vY3NzMj9mYW1pbHk9SW50ZXI6d2dodEA0MDA7NTAwOzYwMDs3MDA7ODAwJmRpc3BsYXk9c3dhcCIgcmVsPSJzdHlsZXNoZWV0Ij4KICA8bGluayBocmVmPSJodHRwczovL2Nkbi5qc2RlbGl2ci5uZXQvbnBtL2Jvb3RzdHJhcEA1LjMuMy9kaXN0L2Nzcy9ib290c3RyYXAubWluLmNzcyIgcmVsPSJzdHlsZXNoZWV0Ij4KICA8bGluayByZWw9InN0eWxlc2hlZXQiIGhyZWY9Imh0dHBzOi8vY2RuLmpzZGVsaXZyLm5ldC9ucG0vYm9vdHN0cmFwLWljb25zQDEuMTEuMy9mb250L2Jvb3RzdHJhcC1pY29ucy5jc3MiPgogIDxsaW5rIHJlbD0ic3R5bGVzaGVldCIgaHJlZj0ie3sgdXJsX2Zvcignc3RhdGljJywgZmlsZW5hbWU9J2Nzcy9kYXNoYm9hcmQuY3NzJykgfX0iPgogIDxsaW5rIHJlbD0ic3R5bGVzaGVldCIgaHJlZj0ie3sgdXJsX2Zvcignc3RhdGljJywgZmlsZW5hbWU9J2Nzcy9wYWdlcy5jc3MnKSB9fSI+CiAgPGxpbmsgcmVsPSJzdHlsZXNoZWV0IiBocmVmPSJ7eyB1cmxfZm9yKCdzdGF0aWMnLCBmaWxlbmFtZT0nY3NzL2N1cnNvci5jc3MnKSB9fSI+CiAgPHN0eWxlPgogICAgLmluc2lnaHRzLWdyaWQgewogICAgICBkaXNwbGF5OiBncmlkOwogICAgICBncmlkLXRlbXBsYXRlLWNvbHVtbnM6IHJlcGVhdChhdXRvLWZpdCwgbWlubWF4KDI0MHB4LCAxZnIpKTsKICAgICAgZ2FwOiAyMHB4OwogICAgICBtYXJnaW4tdG9wOiAxNXB4OwogICAgfQogICAgLmluc2lnaHQtY2FyZCB7CiAgICAgIGJhY2tncm91bmQ6IHZhcigtLXdoaXRlKTsKICAgICAgYm9yZGVyLXJhZGl1czogdmFyKC0tYm9yZGVyLXJhZGl1cy1jYXJkKTsKICAgICAgYm9yZGVyOiAxcHggc29saWQgI0UyRThGMDsKICAgICAgcGFkZGluZzogMjBweDsKICAgICAgYm94LXNoYWRvdzogdmFyKC0tc2hhZG93KTsKICAgICAgZGlzcGxheTogZmxleDsKICAgICAgZ2FwOiAxNnB4OwogICAgICBhbGlnbi1pdGVtczogZmxleC1zdGFydDsKICAgICAgdHJhbnNpdGlvbjogdHJhbnNmb3JtIDAuMnMsIGJveC1zaGFkb3cgMC4yczsKICAgIH0KICAgIC5pbnNpZ2h0LWNhcmQ6aG92ZXIgewogICAgICB0cmFuc2Zvcm06IHRyYW5zbGF0ZVkoLTJweCk7CiAgICAgIGJveC1zaGFkb3c6IDAgOHB4IDE2cHggcmdiYSgwLDAsMCwwLjA1KTsKICAgIH0KICAgIC5pbnNpZ2h0LWljb24td3JhcCB7CiAgICAgIHdpZHRoOiA0NHB4OwogICAgICBoZWlnaHQ6IDQ0cHg7CiAgICAgIGJvcmRlci1yYWRpdXM6IDUwJTsKICAgICAgZGlzcGxheTogZ3JpZDsKICAgICAgcGxhY2UtaXRlbXM6IGNlbnRlcjsKICAgICAgZm9udC1zaXplOiAxLjI1cmVtOwogICAgICBmbGV4LXNocmluazogMDsKICAgIH0KICAgIC5pbnNpZ2h0LXRpdGxlIHsKICAgICAgZm9udC1zaXplOiAwLjk1cmVtOwogICAgICBmb250LXdlaWdodDogNzAwOwogICAgICBjb2xvcjogdmFyKC0tdGV4dC1kYXJrKTsKICAgICAgbWFyZ2luLWJvdHRvbTogNHB4OwogICAgfQogICAgLmluc2lnaHQtdGV4dCB7CiAgICAgIGZvbnQtc2l6ZTogMC44MnJlbTsKICAgICAgY29sb3I6IHZhcigtLXRleHQtbXV0ZWQpOwogICAgICBsaW5lLWhlaWdodDogMS40NTsKICAgIH0KICAgIC53aXNoZXItY2FyZCB7CiAgICAgIGJhY2tncm91bmQ6IHZhcigtLXdoaXRlKTsKICAgICAgYm9yZGVyLXJhZGl1czogdmFyKC0tYm9yZGVyLXJhZGl1cy1jYXJkKTsKICAgICAgYm9yZGVyOiAxcHggc29saWQgI0UyRThGMDsKICAgICAgcGFkZGluZzogMjhweDsKICAgICAgYm94LXNoYWRvdzogdmFyKC0tc2hhZG93KTsKICAgICAgaGVpZ2h0OiAxMDAlOwogICAgfQogICAgLndpc2hlci1oZWFkZXIgewogICAgICBkaXNwbGF5OiBmbGV4OwogICAgICBhbGlnbi1pdGVtczogY2VudGVyOwogICAgICBnYXA6IDE0cHg7CiAgICAgIG1hcmdpbi1ib3R0b206IDIwcHg7CiAgICAgIHBhZGRpbmctYm90dG9tOiAxNXB4OwogICAgICBib3JkZXItYm90dG9tOiAxcHggc29saWQgI0YxRjVGOTsKICAgIH0KICAgIC53aXNoZXItYXZhdGFyIHsKICAgICAgd2lkdGg6IDQ4cHg7CiAgICAgIGhlaWdodDogNDhweDsKICAgICAgYm9yZGVyLXJhZGl1czogNTAlOwogICAgICBiYWNrZ3JvdW5kOiBsaW5lYXItZ3JhZGllbnQoMTM1ZGVnLCAjNEY0NkU1LCAjOEI1Q0Y2KTsKICAgICAgZGlzcGxheTogZ3JpZDsKICAgICAgcGxhY2UtaXRlbXM6IGNlbnRlcjsKICAgICAgY29sb3I6IHdoaXRlOwogICAgICBmb250LXNpemU6IDEuNHJlbTsKICAgIH0KICAgIC53aXNoZXItbmFtZSB7CiAgICAgIGZvbnQtd2VpZ2h0OiA3MDA7CiAgICAgIGZvbnQtc2l6ZTogMS4wNXJlbTsKICAgICAgY29sb3I6IHZhcigtLXRleHQtZGFyayk7CiAgICAgIG1hcmdpbjogMDsKICAgIH0KICAgIC53aXNoZXItc3VidGl0bGUgewogICAgICBmb250LXNpemU6IDAuNzhyZW07CiAgICAgIGNvbG9yOiB2YXIoLS10ZXh0LW11dGVkKTsKICAgICAgbWFyZ2luOiAwOwogICAgfQogICAgLndpc2hlci1ib2R5IHsKICAgICAgZm9udC1zaXplOiAwLjg2cmVtOwogICAgICBjb2xvcjogIzMzNDE1NTsKICAgICAgbGluZS1oZWlnaHQ6IDEuNjsKICAgICAgbWF4LWhlaWdodDogNDgwcHg7CiAgICAgIG92ZXJmbG93LXk6IGF1dG87CiAgICAgIHBhZGRpbmctcmlnaHQ6IDhweDsKICAgIH0KICAgIC5haS1pbnNpZ2h0cy1oZXJvIHsKICAgICAgYmFja2dyb3VuZDogbGluZWFyLWdyYWRpZW50KDEzNWRlZywgIzFFMUI0QiAwJSwgIzMxMkU4MSAxMDAlKTsKICAgICAgYm94LXNoYWRvdzogMCAxMHB4IDIwcHggcmdiYSg0OSwgNDYsIDEyOSwgMC4xNSk7CiAgICB9CgogICAgLyogUm9ib3QgQW5pbWF0aW9ucyAqLwogICAgQGtleWZyYW1lcyByb2JvdEZsb2F0IHsKICAgICAgMCUsIDEwMCUgeyB0cmFuc2Zvcm06IHRyYW5zbGF0ZVkoMHB4KTsgfQogICAgICA1MCUgeyB0cmFuc2Zvcm06IHRyYW5zbGF0ZVkoLTEycHgpOyB9CiAgICB9CiAgICBAa2V5ZnJhbWVzIHJvYm90V2F2ZSB7CiAgICAgIDAlIHsgdHJhbnNmb3JtOiByb3RhdGUoMGRlZyk7IH0KICAgICAgMTAlIHsgdHJhbnNmb3JtOiByb3RhdGUoMTRkZWcpOyB9CiAgICAgIDIwJSB7IHRyYW5zZm9ybTogcm90YXRlKC04ZGVnKTsgfQogICAgICAzMCUgeyB0cmFuc2Zvcm06IHJvdGF0ZSgxNGRlZyk7IH0KICAgICAgNDAlIHsgdHJhbnNmb3JtOiByb3RhdGUoLTRkZWcpOyB9CiAgICAgIDUwJSB7IHRyYW5zZm9ybTogcm90YXRlKDEwZGVnKTsgfQogICAgICA2MCUgeyB0cmFuc2Zvcm06IHJvdGF0ZSgwZGVnKTsgfQogICAgICAxMDAlIHsgdHJhbnNmb3JtOiByb3RhdGUoMGRlZyk7IH0KICAgIH0KICAgIEBrZXlmcmFtZXMgZmFkZVNsaWRlVXAgewogICAgICBmcm9tIHsgb3BhY2l0eTogMDsgdHJhbnNmb3JtOiB0cmFuc2xhdGVZKDMwcHgpOyB9CiAgICAgIHRvIHsgb3BhY2l0eTogMTsgdHJhbnNmb3JtOiB0cmFuc2xhdGVZKDApOyB9CiAgICB9CiAgICBAa2V5ZnJhbWVzIHNwYXJrbGUgewogICAgICAwJSwgMTAwJSB7IG9wYWNpdHk6IDAuMzsgdHJhbnNmb3JtOiBzY2FsZSgwLjgpOyB9CiAgICAgIDUwJSB7IG9wYWNpdHk6IDE7IHRyYW5zZm9ybTogc2NhbGUoMS4yKTsgfQogICAgfQogICAgQGtleWZyYW1lcyBwdWxzZUdsb3cgewogICAgICAwJSwgMTAwJSB7IGJveC1zaGFkb3c6IDAgNHB4IDEwcHggcmdiYSg3OSwgNzAsIDIyOSwgMC4xKTsgfQogICAgICA1MCUgeyBib3gtc2hhZG93OiAwIDhweCAzMHB4IHJnYmEoNzksIDcwLCAyMjksIDAuMjUpOyB9CiAgICB9CiAgICAucm9ib3QtcGFuZWwgewogICAgICBhbmltYXRpb246IGZhZGVTbGlkZVVwIDAuNnMgZWFzZS1vdXQgZm9yd2FyZHMsIHB1bHNlR2xvdyAzcyBlYXNlLWluLW91dCBpbmZpbml0ZTsKICAgICAgcG9zaXRpb246IHJlbGF0aXZlOwogICAgICBvdmVyZmxvdzogaGlkZGVuOwogICAgfQogICAgLnJvYm90LXBhbmVsOjpiZWZvcmUgewogICAgICBjb250ZW50OiAn4pyoJzsKICAgICAgcG9zaXRpb246IGFic29sdXRlOwogICAgICB0b3A6IDEycHg7IGxlZnQ6IDE2cHg7CiAgICAgIGZvbnQtc2l6ZTogMS4ycmVtOwogICAgICBhbmltYXRpb246IHNwYXJrbGUgMnMgZWFzZS1pbi1vdXQgaW5maW5pdGU7CiAgICB9CiAgICAucm9ib3QtcGFuZWw6OmFmdGVyIHsKICAgICAgY29udGVudDogJ/CfkqEnOwogICAgICBwb3NpdGlvbjogYWJzb2x1dGU7CiAgICAgIGJvdHRvbTogMTRweDsgcmlnaHQ6IDE4cHg7CiAgICAgIGZvbnQtc2l6ZTogMS4xcmVtOwogICAgICBhbmltYXRpb246IHNwYXJrbGUgMi41cyBlYXNlLWluLW91dCBpbmZpbml0ZSAwLjVzOwogICAgfQogICAgLnJvYm90LWltZyB7CiAgICAgIGFuaW1hdGlvbjogcm9ib3RGbG9hdCAzcyBlYXNlLWluLW91dCBpbmZpbml0ZTsKICAgICAgY3Vyc29yOiBwb2ludGVyOwogICAgICB0cmFuc2l0aW9uOiB0cmFuc2Zvcm0gMC4zczsKICAgIH0KICAgIC5yb2JvdC1pbWc6aG92ZXIgewogICAgICBhbmltYXRpb246IHJvYm90V2F2ZSAxLjJzIGVhc2UtaW4tb3V0OwogICAgfQogICAgLnJvYm90LWdyZWV0aW5nIHsKICAgICAgcG9zaXRpb246IGFic29sdXRlOwogICAgICB0b3A6IDhweDsgcmlnaHQ6IDE0cHg7CiAgICAgIGJhY2tncm91bmQ6IGxpbmVhci1ncmFkaWVudCgxMzVkZWcsICM0RjQ2RTUsICM3QzNBRUQpOwogICAgICBjb2xvcjogd2hpdGU7CiAgICAgIHBhZGRpbmc6IDZweCAxNHB4OwogICAgICBib3JkZXItcmFkaXVzOiAxNnB4IDE2cHggMCAxNnB4OwogICAgICBmb250LXNpemU6IDAuNzVyZW07CiAgICAgIGZvbnQtd2VpZ2h0OiA3MDA7CiAgICAgIGFuaW1hdGlvbjogZmFkZVNsaWRlVXAgMC44cyBlYXNlLW91dCAwLjNzIGJvdGg7CiAgICAgIGJveC1zaGFkb3c6IDAgNHB4IDEycHggcmdiYSg3OSwgNzAsIDIyOSwgMC4zKTsKICAgICAgei1pbmRleDogMTA7CiAgICB9CiAgICAud2lzaGVyLWNhcmQtYW5pbSB7CiAgICAgIGFuaW1hdGlvbjogZmFkZVNsaWRlVXAgMC43cyBlYXNlLW91dCAwLjJzIGJvdGg7CiAgICB9CiAgICAuaW5zaWdodC1jYXJkLWFuaW0gewogICAgICBhbmltYXRpb246IGZhZGVTbGlkZVVwIDAuNXMgZWFzZS1vdXQgYm90aDsKICAgIH0KICA8L3N0eWxlPgo8L2hlYWQ+Cjxib2R5IGNsYXNzPSJ0aGVtZS1pbnZlc3QiPgo8ZGl2IGlkPSJjdXJzb3ItZG90Ij48L2Rpdj4KPGRpdiBpZD0iY3Vyc29yLXJpbmciPjwvZGl2PgoKPCEtLSBQcm9maWxlIENoaXAgLS0+CjxhIGhyZWY9Int7IHVybF9mb3IoJ3Byb2ZpbGVfcGFnZScpIH19IiBjbGFzcz0icHJvZmlsZS1jaGlwLWdsb2JhbCIgdGl0bGU9IlZpZXcgUHJvZmlsZSI+CiAgPGRpdiBjbGFzcz0icHJvZmlsZS1jaGlwLWF2YXRhciI+e3sgdXNlcl9uYW1lWzBdfHVwcGVyIGlmIHVzZXJfbmFtZSBlbHNlICdBJyB9fTwvZGl2PgogIDxkaXYgY2xhc3M9InByb2ZpbGUtY2hpcC1pbmZvIj4KICAgIDxzcGFuIGNsYXNzPSJwcm9maWxlLWNoaXAtbmFtZSI+e3sgdXNlcl9uYW1lIGlmIHVzZXJfbmFtZSBlbHNlICdBcmp1biBNZWh0YScgfX08L3NwYW4+CiAgPC9kaXY+CjwvYT4KCjxidXR0b24gY2xhc3M9ImZsb2F0aW5nLWhhbWJ1cmdlciIgaWQ9InNpZGViYXItdG9nZ2xlLWJ0biIgdHlwZT0iYnV0dG9uIiB0aXRsZT0iVG9nZ2xlIFNpZGViYXIgTWVudSI+CiAgPGkgY2xhc3M9ImJpIGJpLWxpc3QiPjwvaT4KPC9idXR0b24+Cgo8ZGl2IGNsYXNzPSJkLWZsZXgiPgoKICA8IS0tIExlZnQgU2lkZWJhciAtLT4KICA8YXNpZGUgY2xhc3M9InNpZGViYXIiIGlkPSJzaWRlYmFyIj4KICAgIDxkaXYgY2xhc3M9ImxvZ28tcm93Ij4KICAgICAgPGltZyBzcmM9Int7IHVybF9mb3IoJ3N0YXRpYycsIGZpbGVuYW1lPSdpbWFnZXMvbG9nby5qcGVnJykgfX0iIGFsdD0iRmluU2lnaHQgTG9nbyIgY2xhc3M9ImRhc2gtbmF2LWxvZ28taW1nIiBzdHlsZT0id2lkdGg6NDJweDtoZWlnaHQ6NDJweDsiPgogICAgICA8ZGl2IGNsYXNzPSJsb2dvLXRleHQiPgogICAgICAgIDxoMz5GaW5TaWdodDwvaDM+CiAgICAgICAgPHNtYWxsPlNtYXJ0LiBTZWN1cmUuIFNpbXBsZS48L3NtYWxsPgogICAgICA8L2Rpdj4KICAgIDwvZGl2PgogICAgPG5hdiBjbGFzcz0ibmF2LWxpc3QiPgogICAgICA8YSBocmVmPSJ7eyB1cmxfZm9yKCdkYXNoYm9hcmQnKSB9fSIgY2xhc3M9Im5hdi1pdGVtIj48aSBjbGFzcz0iYmkgYmktZ3JpZCI+PC9pPjxzcGFuPkRhc2hib2FyZDwvc3Bhbj48L2E+CiAgICAgIDxhIGhyZWY9Int7IHVybF9mb3IoJ2ZpbmFuY2VzJykgfX0iIGNsYXNzPSJuYXYtaXRlbSI+PGkgY2xhc3M9ImJpIGJpLXdhbGxldDIiPjwvaT48c3Bhbj5GaW5hbmNlczwvc3Bhbj48L2E+CiAgICAgIDxhIGhyZWY9Int7IHVybF9mb3IoJ2FkZF9pbnZlc3RtZW50JykgfX0iIGNsYXNzPSJuYXYtaXRlbSI+PGkgY2xhc3M9ImJpIGJpLWdyYXBoLXVwLWFycm93Ij48L2k+PHNwYW4+SW52ZXN0bWVudHM8L3NwYW4+PC9hPgogICAgICA8YSBocmVmPSJ7eyB1cmxfZm9yKCdnb2Fsc19saXN0JykgfX0iIGNsYXNzPSJuYXYtaXRlbSI+PGkgY2xhc3M9ImJpIGJpLWZsYWciPjwvaT48c3Bhbj5Hb2Fsczwvc3Bhbj48L2E+CiAgICAgIDxhIGhyZWY9Int7IHVybF9mb3IoJ2hlYWx0aF9zY29yZV9wYWdlJykgfX0iIGNsYXNzPSJuYXYtaXRlbSI+PGkgY2xhc3M9ImJpIGJpLWhlYXJ0LXB1bHNlIj48L2k+PHNwYW4+SGVhbHRoIFNjb3JlPC9zcGFuPjwvYT4KICAgICAgPGEgaHJlZj0ie3sgdXJsX2ZvcigndHJhbnNhY3Rpb25zX3BhZ2UnKSB9fSIgY2xhc3M9Im5hdi1pdGVtIj48aSBjbGFzcz0iYmkgYmktYXJyb3ctbGVmdC1yaWdodCI+PC9pPjxzcGFuPlRyYW5zYWN0aW9uczwvc3Bhbj48L2E+CiAgICAgIDxhIGhyZWY9Int7IHVybF9mb3IoJ2FpX2luc2lnaHRzJykgfX0iIGNsYXNzPSJuYXYtaXRlbSBhY3RpdmUiPjxpIGNsYXNzPSJiaSBiaS1yb2JvdCI+PC9pPjxzcGFuPkFJIEluc2lnaHRzPC9zcGFuPjwvYT4KICAgICAgPGEgaHJlZj0ie3sgdXJsX2ZvcigncHJvZmlsZV9wYWdlJykgfX0iIGNsYXNzPSJuYXYtaXRlbSI+PGkgY2xhc3M9ImJpIGJpLXBlcnNvbi1jaXJjbGUiPjwvaT48c3Bhbj5Qcm9maWxlPC9zcGFuPjwvYT4KICAgIDwvbmF2PgogICAgCiAgICA8YnV0dG9uIGNsYXNzPSJzaWRlYmFyLXJlc2V0LWJ0biIgaWQ9InNpZGViYXItcmVzZXQtYnRuIiB0eXBlPSJidXR0b24iIG9uY2xpY2s9ImlmKGNvbmZpcm0oJ0FyZSB5b3Ugc3VyZSB5b3Ugd2FudCB0byByZXNldCBhbGwgZGF0YSB0byAwPycpKSB7IGZldGNoKCcvYXBpL3Jlc2V0LWRhdGEnLCB7bWV0aG9kOiAnUE9TVCd9KS50aGVuKCgpID0+IHsgd2luZG93LmxvY2F0aW9uLmhyZWY9Jy9kYXNoYm9hcmQnOyB9KTsgfSIgdGl0bGU9IlJlc2V0IGFsbCBkYXRhIHRvIDAiPgogICAgICA8aSBjbGFzcz0iYmkgYmktdHJhc2giPjwvaT48c3Bhbj5SZXNldCBEYXRhPC9zcGFuPgogICAgPC9idXR0b24+CiAgICA8YSBocmVmPSJ7eyB1cmxfZm9yKCdsb2dvdXQnKSB9fSIgY2xhc3M9InNpZGViYXItbG9nb3V0LWJ0biIgdGl0bGU9IkxvZ291dCBmcm9tIHNlc3Npb24iPgogICAgICA8aSBjbGFzcz0iYmkgYmktYm94LWFycm93LXJpZ2h0Ij48L2k+PHNwYW4+TG9nb3V0PC9zcGFuPgogICAgPC9hPgogIDwvYXNpZGU+CgogIDwhLS0gTWFpbiBQYW5lbCAtLT4KICA8bWFpbiBjbGFzcz0ibWFpbi1wYW5lbCI+CiAgICA8ZGl2IGNsYXNzPSJjb250ZW50LXN0YWNrIj4KCiAgICAgIDwhLS0gUGFnZSBIZXJvIC0tPgogICAgICA8ZGl2IGNsYXNzPSJwYWdlLWhlcm8gYWktaW5zaWdodHMtaGVybyI+CiAgICAgICAgPGRpdiBjbGFzcz0iaGVyby1sZWZ0Ij4KICAgICAgICAgIDxkaXYgY2xhc3M9Imhlcm8taWNvbi13cmFwIGRhc2gtaWNvbi13cmFwIiBzdHlsZT0iYmFja2dyb3VuZDogcmdiYSgyNTUsMjU1LDI1NSwwLjE1KTsiPgogICAgICAgICAgICA8aSBjbGFzcz0iYmkgYmktcm9ib3QgdGV4dC13aGl0ZSI+PC9pPgogICAgICAgICAgPC9kaXY+CiAgICAgICAgICA8ZGl2PgogICAgICAgICAgICA8aDEgY2xhc3M9Imhlcm8tdGl0bGUgdGV4dC13aGl0ZSI+QUkgSW5zaWdodHM8L2gxPgogICAgICAgICAgICA8cCBjbGFzcz0iaGVyby1zdWJ0aXRsZSB0ZXh0LXdoaXRlLTUwIj5TcGVuZGluZyBwYXR0ZXJuIGFuYWx5c2lzIGFuZCBkeW5hbWljIGZpbmFuY2lhbCBndWlkYW5jZSBmcm9tIHlvdXIgd2VsbC13aXNoZXI8L3A+CiAgICAgICAgICA8L2Rpdj4KICAgICAgICA8L2Rpdj4KICAgICAgPC9kaXY+CgogICAgICA8IS0tIFRvcCBSb3c6IFJvYm90IEltYWdlIG9uIGxlZnQsIEFueWEgbGV0dGVyIG9uIHJpZ2h0IC0tPgogICAgICA8ZGl2IGNsYXNzPSJyb3cgZy00IG10LTIiPgogICAgICAgIDxkaXYgY2xhc3M9ImNvbC1sZy00IGNvbC1tZC01Ij4KICAgICAgICAgIDxkaXYgY2xhc3M9InBhbmVsIHRleHQtY2VudGVyIHJvYm90LXBhbmVsIiBzdHlsZT0iYmFja2dyb3VuZDogd2hpdGU7IHBhZGRpbmc6IDI0cHg7IGJvcmRlci1yYWRpdXM6IHZhcigtLWJvcmRlci1yYWRpdXMtY2FyZCk7IGJveC1zaGFkb3c6IHZhcigtLXNoYWRvdyk7IGJvcmRlci10b3A6IDRweCBzb2xpZCAjNEY0NkU1OyBkaXNwbGF5OiBmbGV4OyBhbGlnbi1pdGVtczogY2VudGVyOyBqdXN0aWZ5LWNvbnRlbnQ6IGNlbnRlcjsgaGVpZ2h0OiAxMDAlOyI+CiAgICAgICAgICAgIDxkaXYgY2xhc3M9InJvYm90LWdyZWV0aW5nIj7wn5GLIEhpIHt7IHVzZXJfbmFtZSB9fSE8L2Rpdj4KICAgICAgICAgICAgPGltZyBzcmM9Int7IHVybF9mb3IoJ3N0YXRpYycsIGZpbGVuYW1lPSdpbWFnZXMvYWlfY2hhcmFjdGVyLnBuZycpIH19IiBhbHQ9IkFueWEgQUkiIGNsYXNzPSJpbWctZmx1aWQgcm9ib3QtaW1nIiBzdHlsZT0iYm9yZGVyLXJhZGl1czogMTZweDsgd2lkdGg6IDEwMCU7IG1heC1oZWlnaHQ6IDI4MHB4OyBvYmplY3QtZml0OiBjb250YWluOyI+CiAgICAgICAgICA8L2Rpdj4KICAgICAgICA8L2Rpdj4KICAgICAgICA8ZGl2IGNsYXNzPSJjb2wtbGctOCBjb2wtbWQtNyI+CiAgICAgICAgICA8ZGl2IGNsYXNzPSJ3aXNoZXItY2FyZCB3aXNoZXItY2FyZC1hbmltIiBzdHlsZT0iaGVpZ2h0OiAxMDAlOyBib3JkZXItdG9wOiA0cHggc29saWQgIzRGNDZFNTsgZGlzcGxheTogZmxleDsgZmxleC1kaXJlY3Rpb246IGNvbHVtbjsiPgogICAgICAgICAgICA8ZGl2IGNsYXNzPSJ3aXNoZXItaGVhZGVyIiBzdHlsZT0ibWFyZ2luLWJvdHRvbTogMTJweDsgcGFkZGluZy1ib3R0b206IDhweDsiPgogICAgICAgICAgICAgIDxkaXYgY2xhc3M9Indpc2hlci1hdmF0YXIiPgogICAgICAgICAgICAgICAgPGkgY2xhc3M9ImJpIGJpLWNoYXQtaGVhcnQtZmlsbCI+PC9pPgogICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICAgIDxkaXY+CiAgICAgICAgICAgICAgICA8aDQgY2xhc3M9Indpc2hlci1uYW1lIj5BbnlhLCBZb3VyIEFJIFdlbGwtV2lzaGVyPC9oND4KICAgICAgICAgICAgICAgIDxwIGNsYXNzPSJ3aXNoZXItc3VidGl0bGUiPkR5bmFtaWMgZmluYW5jaWFsIGNvdW5zZWxvciAmYW1wOyBhZHZpc29yPC9wPgogICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICA8L2Rpdj4KICAgICAgICAgICAgPGRpdiBjbGFzcz0id2lzaGVyLWJvZHkiIHN0eWxlPSJtYXgtaGVpZ2h0OiAyMjBweDsgb3ZlcmZsb3cteTogYXV0bzsiPgogICAgICAgICAgICAgIHt7IGxldHRlciB8IHJlcGxhY2UoJ1xuJywgJzxicj4nKSB8IHNhZmUgfX0KICAgICAgICAgICAgPC9kaXY+CiAgICAgICAgICA8L2Rpdj4KICAgICAgICA8L2Rpdj4KICAgICAgPC9kaXY+CgogICAgICA8IS0tIEJvdHRvbSBSb3c6IFNwZW5kaW5nIFBhdHRlcm4gQW5hbHlzaXMgKDQgY2FyZHMgZnVsbCB3aWR0aCkgLS0+CiAgICAgIDxkaXYgY2xhc3M9InJvdyBnLTQgbXQtMSI+CiAgICAgICAgPGRpdiBjbGFzcz0iY29sLTEyIj4KICAgICAgICAgIDxkaXYgY2xhc3M9InBhbmVsIiBzdHlsZT0iYm9yZGVyLXRvcDogNHB4IHNvbGlkICM0RjQ2RTU7IGJhY2tncm91bmQ6IHdoaXRlOyBwYWRkaW5nOiAyNHB4OyBib3JkZXItcmFkaXVzOiB2YXIoLS1ib3JkZXItcmFkaXVzLWNhcmQpOyBib3gtc2hhZG93OiB2YXIoLS1zaGFkb3cpOyI+CiAgICAgICAgICAgIDxkaXYgY2xhc3M9ImQtZmxleCBqdXN0aWZ5LWNvbnRlbnQtYmV0d2VlbiBhbGlnbi1pdGVtcy1jZW50ZXIgbWItMyI+CiAgICAgICAgICAgICAgPGg0IHN0eWxlPSJmb250LXdlaWdodDogODAwOyBjb2xvcjogdmFyKC0tdGV4dC1kYXJrKTsgbWFyZ2luOiAwOyI+U3BlbmRpbmcgUGF0dGVybiBBbmFseXNpczwvaDQ+CiAgICAgICAgICAgICAgPHNlbGVjdCBjbGFzcz0iZm9ybS1zZWxlY3QgZm9ybS1zZWxlY3Qtc20iIHN0eWxlPSJ3aWR0aDogYXV0bzsgYm9yZGVyLXJhZGl1czogOHB4OyI+CiAgICAgICAgICAgICAgICA8b3B0aW9uIHNlbGVjdGVkPlRoaXMgTW9udGg8L29wdGlvbj4KICAgICAgICAgICAgICAgIDxvcHRpb24+TGFzdCBNb250aDwvb3B0aW9uPgogICAgICAgICAgICAgIDwvc2VsZWN0PgogICAgICAgICAgICA8L2Rpdj4KCiAgICAgICAgICAgIDxkaXYgY2xhc3M9Imluc2lnaHRzLWdyaWQiPgogICAgICAgICAgICAgIHslIGZvciBjYXJkIGluIGluc2lnaHRzICV9CiAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJpbnNpZ2h0LWNhcmQgaW5zaWdodC1jYXJkLWFuaW0iIHN0eWxlPSJhbmltYXRpb24tZGVsYXk6IHt7IGxvb3AuaW5kZXgwICogMC4xMiB9fXM7Ij4KICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0iaW5zaWdodC1pY29uLXdyYXAiIHN0eWxlPSJiYWNrZ3JvdW5kOiB7eyBjYXJkLmNvbG9yIH19MWE7IGNvbG9yOiB7eyBjYXJkLmNvbG9yIH19OyBib3JkZXItcmFkaXVzOiA1MCU7IGRpc3BsYXk6IGdyaWQ7IHBsYWNlLWl0ZW1zOiBjZW50ZXI7IHdpZHRoOiA0NHB4OyBoZWlnaHQ6IDQ0cHg7IGZsZXgtc2hyaW5rOiAwOyI+CiAgICAgICAgICAgICAgICAgICAgPGkgY2xhc3M9ImJpIHt7IGNhcmQuaWNvbiB9fSIgc3R5bGU9ImZvbnQtc2l6ZTogMS4yNXJlbTsiPjwvaT4KICAgICAgICAgICAgICAgICAgPC9kaXY+CiAgICAgICAgICAgICAgICAgIDxkaXY+CiAgICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0iaW5zaWdodC10aXRsZSIgc3R5bGU9ImZvbnQtd2VpZ2h0OiA4MDA7IGNvbG9yOiB2YXIoLS10ZXh0LWRhcmspOyBmb250LXNpemU6IDAuOTVyZW07IG1hcmdpbi1ib3R0b206IDRweDsiPnt7IGNhcmQudGl0bGUgfX08L2Rpdj4KICAgICAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJpbnNpZ2h0LXRleHQiIHN0eWxlPSJmb250LXNpemU6IDAuODJyZW07IGNvbG9yOiB2YXIoLS10ZXh0LW11dGVkKTsgbGluZS1oZWlnaHQ6IDEuNDU7Ij57eyBjYXJkLnRleHQgfX08L2Rpdj4KICAgICAgICAgICAgICAgICAgPC9kaXY+CiAgICAgICAgICAgICAgICA8L2Rpdj4KICAgICAgICAgICAgICB7JSBlbmRmb3IgJX0KICAgICAgICAgICAgPC9kaXY+CgogICAgICAgICAgICA8ZGl2IGNsYXNzPSJ0ZXh0LWNlbnRlciBtdC00Ij4KICAgICAgICAgICAgICA8YnV0dG9uIG9uY2xpY2s9IndpbmRvdy5sb2NhdGlvbi5yZWxvYWQoKTsiIGNsYXNzPSJidG4gYnRuLXByaW1hcnkgcHgtNCBweS0yIiBzdHlsZT0iYm9yZGVyLXJhZGl1czogMTBweDsgYmFja2dyb3VuZC1jb2xvcjogIzRGNDZFNTsgYm9yZGVyLWNvbG9yOiAjNEY0NkU1OyBmb250LXdlaWdodDogNjAwOyI+CiAgICAgICAgICAgICAgICA8aSBjbGFzcz0iYmkgYmktYXJyb3ctY2xvY2t3aXNlIG1lLTEiPjwvaT4gR2VuZXJhdGUgTmV3IEluc2lnaHRzCiAgICAgICAgICAgICAgPC9idXR0b24+CiAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgPC9kaXY+CiAgICAgICAgPC9kaXY+CiAgICAgIDwvZGl2PgoKICAgIDwvZGl2PgogIDwvbWFpbj4KPC9kaXY+Cgo8c2NyaXB0IHNyYz0iaHR0cHM6Ly9jZG4uanNkZWxpdnIubmV0L25wbS9ib290c3RyYXBANS4zLjMvZGlzdC9qcy9ib290c3RyYXAuYnVuZGxlLm1pbi5qcyI+PC9zY3JpcHQ+CjxzY3JpcHQgc3JjPSJ7eyB1cmxfZm9yKCdzdGF0aWMnLCBmaWxlbmFtZT0nanMvY3Vyc29yLmpzJykgfX0iPjwvc2NyaXB0Pgo8L2JvZHk+CjwvaHRtbD4K').decode('utf-8'),
    'goals.html': base64.b64decode('PCFkb2N0eXBlIGh0bWw+CjxodG1sIGxhbmc9ImVuIj4KPGhlYWQ+CiAgPG1ldGEgY2hhcnNldD0idXRmLTgiPgogIDxtZXRhIG5hbWU9InZpZXdwb3J0IiBjb250ZW50PSJ3aWR0aD1kZXZpY2Utd2lkdGgsIGluaXRpYWwtc2NhbGU9MSI+CiAgPHRpdGxlPkZpbmFuY2lhbCBHb2FscyDigJMgRmluU2lnaHQ8L3RpdGxlPgogIDxsaW5rIHJlbD0icHJlY29ubmVjdCIgaHJlZj0iaHR0cHM6Ly9mb250cy5nb29nbGVhcGlzLmNvbSI+CiAgPGxpbmsgcmVsPSJwcmVjb25uZWN0IiBocmVmPSJodHRwczovL2ZvbnRzLmdzdGF0aWMuY29tIiBjcm9zc29yaWdpbj4KICA8bGluayBocmVmPSJodHRwczovL2ZvbnRzLmdvb2dsZWFwaXMuY29tL2NzczI/ZmFtaWx5PUludGVyOndnaHRANDAwOzUwMDs2MDA7NzAwOzgwMCZkaXNwbGF5PXN3YXAiIHJlbD0ic3R5bGVzaGVldCI+CiAgPGxpbmsgaHJlZj0iaHR0cHM6Ly9jZG4uanNkZWxpdnIubmV0L25wbS9ib290c3RyYXBANS4zLjMvZGlzdC9jc3MvYm9vdHN0cmFwLm1pbi5jc3MiIHJlbD0ic3R5bGVzaGVldCI+CiAgPGxpbmsgcmVsPSJzdHlsZXNoZWV0IiBocmVmPSJodHRwczovL2Nkbi5qc2RlbGl2ci5uZXQvbnBtL2Jvb3RzdHJhcC1pY29uc0AxLjExLjMvZm9udC9ib290c3RyYXAtaWNvbnMuY3NzIj4KICA8bGluayByZWw9InN0eWxlc2hlZXQiIGhyZWY9Int7IHVybF9mb3IoJ3N0YXRpYycsIGZpbGVuYW1lPSdjc3MvZGFzaGJvYXJkLmNzcycpIH19Ij4KICA8bGluayByZWw9InN0eWxlc2hlZXQiIGhyZWY9Int7IHVybF9mb3IoJ3N0YXRpYycsIGZpbGVuYW1lPSdjc3MvcGFnZXMuY3NzJykgfX0iPgogIDxsaW5rIHJlbD0ic3R5bGVzaGVldCIgaHJlZj0ie3sgdXJsX2Zvcignc3RhdGljJywgZmlsZW5hbWU9J2Nzcy9jdXJzb3IuY3NzJykgfX0iPgogIDxzdHlsZT4KICAgIC5nb2FsLWdyaWQgewogICAgICBkaXNwbGF5OiBncmlkOwogICAgICBncmlkLXRlbXBsYXRlLWNvbHVtbnM6IHJlcGVhdChhdXRvLWZpbGwsIG1pbm1heCgzMjBweCwgMWZyKSk7CiAgICAgIGdhcDogMjBweDsKICAgICAgbWFyZ2luLXRvcDogMjBweDsKICAgIH0KICAgIC5nb2FsLWNhcmQgewogICAgICBiYWNrZ3JvdW5kOiB2YXIoLS13aGl0ZSk7CiAgICAgIGJvcmRlci1yYWRpdXM6IHZhcigtLWJvcmRlci1yYWRpdXMtY2FyZCk7CiAgICAgIGJvcmRlcjogMXB4IHNvbGlkICNFMkU4RjA7CiAgICAgIHBhZGRpbmc6IDI0cHg7CiAgICAgIGJveC1zaGFkb3c6IHZhcigtLXNoYWRvdyk7CiAgICAgIGRpc3BsYXk6IGZsZXg7CiAgICAgIGZsZXgtZGlyZWN0aW9uOiBjb2x1bW47CiAgICAgIGp1c3RpZnktY29udGVudDogc3BhY2UtYmV0d2VlbjsKICAgICAgdHJhbnNpdGlvbjogdHJhbnNmb3JtIDAuMnMsIGJveC1zaGFkb3cgMC4yczsKICAgIH0KICAgIC5nb2FsLWNhcmQ6aG92ZXIgewogICAgICB0cmFuc2Zvcm06IHRyYW5zbGF0ZVkoLTRweCk7CiAgICAgIGJveC1zaGFkb3c6IDAgMTBweCAyMHB4IHJnYmEoMCwwLDAsMC4wNSk7CiAgICB9CiAgICAuZ29hbC1jYXJkLWhlYWRlciB7CiAgICAgIGRpc3BsYXk6IGZsZXg7CiAgICAgIGp1c3RpZnktY29udGVudDogc3BhY2UtYmV0d2VlbjsKICAgICAgYWxpZ24taXRlbXM6IGZsZXgtc3RhcnQ7CiAgICAgIG1hcmdpbi1ib3R0b206IDE1cHg7CiAgICB9CiAgICAuZ29hbC10aXRsZSB7CiAgICAgIGZvbnQtc2l6ZTogMS4xNXJlbTsKICAgICAgZm9udC13ZWlnaHQ6IDcwMDsKICAgICAgY29sb3I6IHZhcigtLXRleHQtZGFyayk7CiAgICAgIG1hcmdpbjogMDsKICAgIH0KICAgIC5nb2FsLWNhdGVnb3J5IHsKICAgICAgZm9udC1zaXplOiAwLjhyZW07CiAgICAgIGNvbG9yOiB2YXIoLS10ZXh0LW11dGVkKTsKICAgICAgbWFyZ2luLXRvcDogMnB4OwogICAgICBkaXNwbGF5OiBmbGV4OwogICAgICBhbGlnbi1pdGVtczogY2VudGVyOwogICAgICBnYXA6IDVweDsKICAgIH0KICAgIC5nb2FsLWFtb3VudHMgewogICAgICBkaXNwbGF5OiBmbGV4OwogICAgICBqdXN0aWZ5LWNvbnRlbnQ6IHNwYWNlLWJldHdlZW47CiAgICAgIG1hcmdpbjogMTVweCAwOwogICAgICBwYWRkaW5nOiAxMnB4IDE0cHg7CiAgICAgIGJhY2tncm91bmQ6ICNGOEZBRkM7CiAgICAgIGJvcmRlci1yYWRpdXM6IDEycHg7CiAgICB9CiAgICAuYW1vdW50LWl0ZW0gewogICAgICBkaXNwbGF5OiBmbGV4OwogICAgICBmbGV4LWRpcmVjdGlvbjogY29sdW1uOwogICAgfQogICAgLmFtb3VudC1sYWJlbCB7CiAgICAgIGZvbnQtc2l6ZTogMC43MnJlbTsKICAgICAgdGV4dC10cmFuc2Zvcm06IHVwcGVyY2FzZTsKICAgICAgbGV0dGVyLXNwYWNpbmc6IDAuNXB4OwogICAgICBjb2xvcjogdmFyKC0tdGV4dC1tdXRlZCk7CiAgICAgIGZvbnQtd2VpZ2h0OiA2MDA7CiAgICB9CiAgICAuYW1vdW50LXZhbCB7CiAgICAgIGZvbnQtc2l6ZTogMC45NXJlbTsKICAgICAgZm9udC13ZWlnaHQ6IDcwMDsKICAgICAgY29sb3I6IHZhcigtLXRleHQtZGFyayk7CiAgICB9CiAgICAuYW1vdW50LXZhbC5zYXZlZCB7CiAgICAgIGNvbG9yOiB2YXIoLS1zdWNjZXNzKTsKICAgIH0KICAgIC5hbW91bnQtdmFsLnJlbWFpbmluZyB7CiAgICAgIGNvbG9yOiB2YXIoLS1vcmFuZ2UpOwogICAgfQogICAgLnByb2dyZXNzLXNlY3Rpb24gewogICAgICBtYXJnaW4tdG9wOiAxMHB4OwogICAgfQogICAgLnByb2dyZXNzLWhlYWRlciB7CiAgICAgIGRpc3BsYXk6IGZsZXg7CiAgICAgIGp1c3RpZnktY29udGVudDogc3BhY2UtYmV0d2VlbjsKICAgICAgZm9udC1zaXplOiAwLjhyZW07CiAgICAgIGZvbnQtd2VpZ2h0OiA2MDA7CiAgICAgIG1hcmdpbi1ib3R0b206IDZweDsKICAgIH0KICAgIC5nb2FsLWZvb3RlciB7CiAgICAgIGRpc3BsYXk6IGZsZXg7CiAgICAgIGp1c3RpZnktY29udGVudDogc3BhY2UtYmV0d2VlbjsKICAgICAgYWxpZ24taXRlbXM6IGNlbnRlcjsKICAgICAgbWFyZ2luLXRvcDogMjBweDsKICAgICAgcGFkZGluZy10b3A6IDE1cHg7CiAgICAgIGJvcmRlci10b3A6IDFweCBzb2xpZCAjRjFGNUY5OwogICAgfQogICAgLmdvYWwtZGF0ZSB7CiAgICAgIGZvbnQtc2l6ZTogMC43OHJlbTsKICAgICAgY29sb3I6IHZhcigtLXRleHQtbXV0ZWQpOwogICAgICBkaXNwbGF5OiBmbGV4OwogICAgICBhbGlnbi1pdGVtczogY2VudGVyOwogICAgICBnYXA6IDVweDsKICAgIH0KICAgIC5idG4tYWN0aW9uLWdyb3VwIHsKICAgICAgZGlzcGxheTogZmxleDsKICAgICAgZ2FwOiA2cHg7CiAgICB9CiAgICAuYnRuLWljb24gewogICAgICB3aWR0aDogMzJweDsKICAgICAgaGVpZ2h0OiAzMnB4OwogICAgICBib3JkZXItcmFkaXVzOiA4cHg7CiAgICAgIGJvcmRlcjogMXB4IHNvbGlkICNFMkU4RjA7CiAgICAgIGJhY2tncm91bmQ6IHZhcigtLXdoaXRlKTsKICAgICAgZGlzcGxheTogZ3JpZDsKICAgICAgcGxhY2UtaXRlbXM6IGNlbnRlcjsKICAgICAgY29sb3I6IHZhcigtLXRleHQtbXV0ZWQpOwogICAgICB0cmFuc2l0aW9uOiBhbGwgMC4yczsKICAgIH0KICAgIC5idG4taWNvbjpob3ZlciB7CiAgICAgIGJhY2tncm91bmQ6ICNGMUY1Rjk7CiAgICAgIGNvbG9yOiB2YXIoLS10ZXh0LWRhcmspOwogICAgfQogICAgLmJ0bi1pY29uLmRlbGV0ZTpob3ZlciB7CiAgICAgIGJhY2tncm91bmQ6ICNGRUUyRTI7CiAgICAgIGNvbG9yOiB2YXIoLS1kYW5nZXIpOwogICAgICBib3JkZXItY29sb3I6ICNGQ0E1QTU7CiAgICB9CiAgICAuZmlsdGVycy1yb3cgewogICAgICBib3JkZXItdG9wOiA0cHggc29saWQgIzFFMjkzQjsKICAgICAgYmFja2dyb3VuZDogdmFyKC0td2hpdGUpOwogICAgICBib3JkZXItcmFkaXVzOiB2YXIoLS1ib3JkZXItcmFkaXVzLWNhcmQpOwogICAgICBwYWRkaW5nOiAyMHB4OwogICAgICBib3gtc2hhZG93OiB2YXIoLS1zaGFkb3cpOwogICAgICBtYXJnaW4tYm90dG9tOiAyMHB4OwogICAgfQogICAgLmZvcm0tcGFuZWwgewogICAgICBib3JkZXItdG9wOiA0cHggc29saWQgIzFFMjkzQjsKICAgIH0KICAgIC5wcmV2aWV3LXBhbmVsIHsKICAgICAgYmFja2dyb3VuZDogdmFyKC0td2hpdGUpOwogICAgICBib3JkZXItcmFkaXVzOiB2YXIoLS1ib3JkZXItcmFkaXVzLWNhcmQpOwogICAgICBwYWRkaW5nOiAyNHB4OwogICAgICBib3gtc2hhZG93OiB2YXIoLS1zaGFkb3cpOwogICAgICBwb3NpdGlvbjogc3RpY2t5OwogICAgICB0b3A6IDIwcHg7CiAgICB9CiAgICAucHJldmlldy10aXRsZSB7CiAgICAgIGZvbnQtc2l6ZTogMS4xcmVtOwogICAgICBmb250LXdlaWdodDogNzAwOwogICAgICBjb2xvcjogdmFyKC0tdGV4dC1kYXJrKTsKICAgICAgbWFyZ2luLWJvdHRvbTogMThweDsKICAgICAgZGlzcGxheTogZmxleDsKICAgICAgYWxpZ24taXRlbXM6IGNlbnRlcjsKICAgICAgZ2FwOiA4cHg7CiAgICB9CiAgICAucHJldmlldy1yb3cgewogICAgICBkaXNwbGF5OiBmbGV4OwogICAgICBqdXN0aWZ5LWNvbnRlbnQ6IHNwYWNlLWJldHdlZW47CiAgICAgIHBhZGRpbmc6IDEwcHggMDsKICAgICAgYm9yZGVyLWJvdHRvbTogMXB4IHNvbGlkICNGMUY1Rjk7CiAgICAgIGZvbnQtc2l6ZTogMC45cmVtOwogICAgfQogICAgLnByZXZpZXctcm93Omxhc3QtY2hpbGQgewogICAgICBib3JkZXItYm90dG9tOiAwOwogICAgfQogICAgLnByZXZpZXctbGFiZWwgewogICAgICBjb2xvcjogdmFyKC0tdGV4dC1tdXRlZCk7CiAgICAgIGZvbnQtd2VpZ2h0OiA1MDA7CiAgICB9CiAgICAucHJldmlldy12YWx1ZSB7CiAgICAgIGZvbnQtd2VpZ2h0OiA3MDA7CiAgICAgIGNvbG9yOiB2YXIoLS10ZXh0LWRhcmspOwogICAgfQoKICAgIC5uYXYtcGlsbHMgLm5hdi1saW5rIHsKICAgICAgY29sb3I6ICM0NzU1Njk7CiAgICAgIGJhY2tncm91bmQ6ICNGMUY1Rjk7CiAgICAgIGJvcmRlcjogMXB4IHNvbGlkICNFMkU4RjA7CiAgICAgIHRyYW5zaXRpb246IGFsbCAwLjJzOwogICAgICBmb250LXdlaWdodDogNjAwOwogICAgICBib3JkZXItcmFkaXVzOiAxMHB4OwogICAgICBwYWRkaW5nOiAxMHB4IDIwcHg7CiAgICB9CiAgICAubmF2LXBpbGxzIC5uYXYtbGluazpob3ZlciB7CiAgICAgIGJhY2tncm91bmQ6ICNFMkU4RjA7CiAgICAgIGNvbG9yOiAjMEYxNzJBOwogICAgfQogICAgLm5hdi1waWxscyAubmF2LWxpbmsuYWN0aXZlIHsKICAgICAgYmFja2dyb3VuZDogIzFFMjkzQiAhaW1wb3J0YW50OwogICAgICBjb2xvcjogI2ZmZiAhaW1wb3J0YW50OwogICAgICBib3JkZXItY29sb3I6ICMxRTI5M0IgIWltcG9ydGFudDsKICAgICAgYm94LXNoYWRvdzogMCA0cHggMTJweCByZ2JhKDMwLCA0MSwgNTksIDAuMTUpOwogICAgfQogIDwvc3R5bGU+CjwvaGVhZD4KPGJvZHkgY2xhc3M9InRoZW1lLWRhc2giPgo8ZGl2IGlkPSJjdXJzb3ItZG90Ij48L2Rpdj4KPGRpdiBpZD0iY3Vyc29yLXJpbmciPjwvZGl2PgoKPCEtLSBQcm9maWxlIENoaXAgLS0+CjxhIGhyZWY9Int7IHVybF9mb3IoJ3Byb2ZpbGVfcGFnZScpIH19IiBjbGFzcz0icHJvZmlsZS1jaGlwLWdsb2JhbCIgdGl0bGU9IlZpZXcgUHJvZmlsZSI+CiAgPGRpdiBjbGFzcz0icHJvZmlsZS1jaGlwLWF2YXRhciI+e3sgdXNlcl9uYW1lWzBdfHVwcGVyIGlmIHVzZXJfbmFtZSBlbHNlICdBJyB9fTwvZGl2PgogIDxkaXYgY2xhc3M9InByb2ZpbGUtY2hpcC1pbmZvIj4KICAgIDxzcGFuIGNsYXNzPSJwcm9maWxlLWNoaXAtbmFtZSI+e3sgdXNlcl9uYW1lIGlmIHVzZXJfbmFtZSBlbHNlICdBcmp1biBNZWh0YScgfX08L3NwYW4+CiAgPC9kaXY+CjwvYT4KCiAgPGJ1dHRvbiBjbGFzcz0iZmxvYXRpbmctaGFtYnVyZ2VyIiBpZD0ic2lkZWJhci10b2dnbGUtYnRuIiB0eXBlPSJidXR0b24iIHRpdGxlPSJUb2dnbGUgU2lkZWJhciBNZW51Ij4KICAgIDxpIGNsYXNzPSJiaSBiaS1saXN0Ij48L2k+CiAgPC9idXR0b24+CgogIDxkaXYgY2xhc3M9ImQtZmxleCI+CgogICAgPGFzaWRlIGNsYXNzPSJzaWRlYmFyIiBpZD0ic2lkZWJhciI+CiAgICAgIDxkaXYgY2xhc3M9ImxvZ28tcm93Ij4KICAgICAgICA8aW1nIHNyYz0ie3sgdXJsX2Zvcignc3RhdGljJywgZmlsZW5hbWU9J2ltYWdlcy9sb2dvLmpwZWcnKSB9fSIgYWx0PSJGaW5TaWdodCBMb2dvIiBjbGFzcz0iZGFzaC1uYXYtbG9nby1pbWciIHN0eWxlPSJ3aWR0aDo0MnB4O2hlaWdodDo0MnB4OyI+CiAgICAgICAgPGRpdiBjbGFzcz0ibG9nby10ZXh0Ij4KICAgICAgICAgIDxoMz5GaW5TaWdodDwvaDM+CiAgICAgICAgICA8c21hbGw+U21hcnQuIFNlY3VyZS4gU2ltcGxlLjwvc21hbGw+CiAgICAgICAgPC9kaXY+CiAgICAgIDwvZGl2PgogICAgICA8bmF2IGNsYXNzPSJuYXYtbGlzdCI+CiAgICAgICAgPGEgaHJlZj0ie3sgdXJsX2ZvcignZGFzaGJvYXJkJykgfX0iIGNsYXNzPSJuYXYtaXRlbSI+PGkgY2xhc3M9ImJpIGJpLWdyaWQiPjwvaT48c3Bhbj5EYXNoYm9hcmQ8L3NwYW4+PC9hPgogICAgICAgIDxhIGhyZWY9Int7IHVybF9mb3IoJ2FkZF9pbmNvbWUnKSB9fSIgY2xhc3M9Im5hdi1pdGVtIj48aSBjbGFzcz0iYmkgYmktY2FzaC1jb2luIj48L2k+PHNwYW4+SW5jb21lIE1hbmFnZW1lbnQ8L3NwYW4+PC9hPgogICAgICAgIDxhIGhyZWY9Int7IHVybF9mb3IoJ2FkZF9leHBlbnNlJykgfX0iIGNsYXNzPSJuYXYtaXRlbSI+PGkgY2xhc3M9ImJpIGJpLXdhbGxldDIiPjwvaT48c3Bhbj5FeHBlbnNlIE1hbmFnZW1lbnQ8L3NwYW4+PC9hPgogICAgICAgIDxhIGhyZWY9Int7IHVybF9mb3IoJ2FkZF9idWRnZXQnKSB9fSIgY2xhc3M9Im5hdi1pdGVtIj48aSBjbGFzcz0iYmkgYmktcGllLWNoYXJ0Ij48L2k+PHNwYW4+QnVkZ2V0IE1hbmFnZW1lbnQ8L3NwYW4+PC9hPgogICAgICAgIDxhIGhyZWY9Int7IHVybF9mb3IoJ2FkZF9pbnZlc3RtZW50JykgfX0iIGNsYXNzPSJuYXYtaXRlbSI+PGkgY2xhc3M9ImJpIGJpLWdyYXBoLXVwLWFycm93Ij48L2k+PHNwYW4+SW52ZXN0bWVudCBUcmFja2luZzwvc3Bhbj48L2E+CiAgICAgICAgPGEgaHJlZj0ie3sgdXJsX2ZvcignZ29hbHNfbGlzdCcpIH19IiBjbGFzcz0ibmF2LWl0ZW0gYWN0aXZlIj48aSBjbGFzcz0iYmkgYmktZmxhZyI+PC9pPjxzcGFuPkdvYWxzPC9zcGFuPjwvYT4KICAgICAgICA8YSBocmVmPSJ7eyB1cmxfZm9yKCdwcm9maWxlX3BhZ2UnKSB9fSIgY2xhc3M9Im5hdi1pdGVtIj48aSBjbGFzcz0iYmkgYmktcGVyc29uLWNpcmNsZSI+PC9pPjxzcGFuPlByb2ZpbGU8L3NwYW4+PC9hPgogICAgICA8L25hdj4KICAgICAgCiAgICAgIDxidXR0b24gY2xhc3M9InNpZGViYXItcmVzZXQtYnRuIiBpZD0ic2lkZWJhci1yZXNldC1idG4iIHR5cGU9ImJ1dHRvbiIgb25jbGljaz0iaWYoY29uZmlybSgnQXJlIHlvdSBzdXJlIHlvdSB3YW50IHRvIHJlc2V0IGFsbCBkYXRhIHRvIDA/JykpIHsgZmV0Y2goJy9hcGkvcmVzZXQtZGF0YScsIHttZXRob2Q6ICdQT1NUJ30pLnRoZW4oKCkgPT4geyB3aW5kb3cubG9jYXRpb24uaHJlZj0nL2Rhc2hib2FyZCc7IH0pOyB9IiB0aXRsZT0iUmVzZXQgYWxsIGRhdGEgdG8gMCI+CiAgICAgICAgPGkgY2xhc3M9ImJpIGJpLXRyYXNoIj48L2k+PHNwYW4+UmVzZXQgRGF0YTwvc3Bhbj4KICAgICAgPC9idXR0b24+CiAgICAgIDxhIGhyZWY9Int7IHVybF9mb3IoJ2xvZ291dCcpIH19IiBjbGFzcz0ic2lkZWJhci1sb2dvdXQtYnRuIiB0aXRsZT0iTG9nb3V0IGZyb20gc2Vzc2lvbiI+CiAgICAgICAgPGkgY2xhc3M9ImJpIGJpLWJveC1hcnJvdy1yaWdodCI+PC9pPjxzcGFuPkxvZ291dDwvc3Bhbj4KICAgICAgPC9hPgogICAgPC9hc2lkZT4KCiAgICA8bWFpbiBjbGFzcz0ibWFpbi1wYW5lbCI+CiAgICAgIDxkaXYgY2xhc3M9ImNvbnRlbnQtc3RhY2siPgoKICAgICAgICA8IS0tIFBhZ2UgSGVybyAtLT4KICAgICAgICA8ZGl2IGNsYXNzPSJwYWdlLWhlcm8gZ29hbHMtaGVybyI+CiAgICAgICAgICA8ZGl2IGNsYXNzPSJoZXJvLWxlZnQiPgogICAgICAgICAgICA8ZGl2IGNsYXNzPSJoZXJvLWljb24td3JhcCBkYXNoLWljb24td3JhcCIgc3R5bGU9ImJhY2tncm91bmQ6IHJnYmEoMjU1LDI1NSwyNTUsMC4yNSk7Ij4KICAgICAgICAgICAgICA8aSBjbGFzcz0iYmkgYmktZmxhZyB0ZXh0LXdoaXRlIj48L2k+CiAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICA8ZGl2PgogICAgICAgICAgICAgIDxoMSBjbGFzcz0iaGVyby10aXRsZSI+RmluYW5jaWFsIEdvYWxzPC9oMT4KICAgICAgICAgICAgICA8cCBjbGFzcz0iaGVyby1zdWJ0aXRsZSI+TWFuYWdlIGFuZCB0cmFjayB5b3VyIHNhdmluZyBtaWxlc3RvbmVzIGFuZCBzbWFydCB0aW1lbGluZXM8L3A+CiAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgPC9kaXY+CiAgICAgICAgICA8ZGl2IGNsYXNzPSJoZXJvLXN0YXRzIj4KICAgICAgICAgICAgPGJ1dHRvbiBjbGFzcz0iYnRuIGJ0bi1wcmltYXJ5IiBzdHlsZT0iYm9yZGVyLXJhZGl1czogMTJweDsgZm9udC13ZWlnaHQ6IDYwMDsiIG9uY2xpY2s9InN3aXRjaEdvYWxUYWIoJ3BsYW5uaW5nJykiPgogICAgICAgICAgICAgIDxpIGNsYXNzPSJiaSBiaS1wbHVzLWxnIG1lLTEiPjwvaT4gQ3JlYXRlIEdvYWwKICAgICAgICAgICAgPC9idXR0b24+CiAgICAgICAgICA8L2Rpdj4KICAgICAgICA8L2Rpdj4KCiAgICAgICAgPCEtLSBGbGFzaCBNZXNzYWdlcyAtLT4KICAgICAgICB7JSB3aXRoIG1lc3NhZ2VzID0gZ2V0X2ZsYXNoZWRfbWVzc2FnZXMod2l0aF9jYXRlZ29yaWVzPXRydWUpICV9CiAgICAgICAgICB7JSBpZiBtZXNzYWdlcyAlfQogICAgICAgICAgICB7JSBmb3IgY2F0ZWdvcnksIG1lc3NhZ2UgaW4gbWVzc2FnZXMgJX0KICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJwYWdlLWFsZXJ0IGFsZXJ0LXt7IGNhdGVnb3J5IH19Ij4KICAgICAgICAgICAgICAgIDxpIGNsYXNzPSJiaSB7JSBpZiBjYXRlZ29yeSA9PSAnc3VjY2VzcycgJX1iaS1jaGVjay1jaXJjbGUtZmlsbHslIGVsaWYgY2F0ZWdvcnkgPT0gJ2RhbmdlcicgJX1iaS1leGNsYW1hdGlvbi1jaXJjbGUtZmlsbHslIGVsc2UgJX1iaS1pbmZvLWNpcmNsZS1maWxseyUgZW5kaWYgJX0iPjwvaT4KICAgICAgICAgICAgICAgIDxzcGFuPnt7IG1lc3NhZ2UgfX08L3NwYW4+CiAgICAgICAgICAgICAgICA8YnV0dG9uIHR5cGU9ImJ1dHRvbiIgY2xhc3M9ImFsZXJ0LWNsb3NlLWJ0biIgb25jbGljaz0idGhpcy5wYXJlbnRFbGVtZW50LnJlbW92ZSgpIj48aSBjbGFzcz0iYmkgYmkteC1sZyI+PC9pPjwvYnV0dG9uPgogICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICB7JSBlbmRmb3IgJX0KICAgICAgICAgIHslIGVuZGlmICV9CiAgICAgICAgeyUgZW5kd2l0aCAlfQoKICAgICAgICA8IS0tIFNldCBzaG93X3BsYW5uaW5nIHRhYiBzZWxlY3Rpb24gdmFyaWFibGUgLS0+CiAgICAgICAgeyUgc2V0IHNob3dfcGxhbm5pbmcgPSBlZGl0IG9yIChyZXF1ZXN0LmFyZ3MuZ2V0KCd0YWInKSA9PSAncGxhbm5pbmcnKSBvciAodGFiID09ICdwbGFubmluZycpICV9CgogICAgICAgIDwhLS0gVGFiIE5hdmlnYXRpb24gKEJvb3RzdHJhcCBQaWxscykgLS0+CiAgICAgICAgPHVsIGNsYXNzPSJuYXYgbmF2LXBpbGxzIGdhcC0yIG1iLTQiPgogICAgICAgICAgPGxpIGNsYXNzPSJuYXYtaXRlbSI+CiAgICAgICAgICAgIDxidXR0b24gY2xhc3M9Im5hdi1saW5rIHslIGlmIG5vdCBzaG93X3BsYW5uaW5nICV9YWN0aXZleyUgZW5kaWYgJX0iIGlkPSJ0YWItYnRuLWxpc3QiIG9uY2xpY2s9InN3aXRjaEdvYWxUYWIoJ2xpc3QnKSI+CiAgICAgICAgICAgICAgPGkgY2xhc3M9ImJpIGJpLWZsYWctZmlsbCBtZS0xIj48L2k+IE15IEdvYWxzCiAgICAgICAgICAgIDwvYnV0dG9uPgogICAgICAgICAgPC9saT4KICAgICAgICAgIDxsaSBjbGFzcz0ibmF2LWl0ZW0iPgogICAgICAgICAgICA8YnV0dG9uIGNsYXNzPSJuYXYtbGluayB7JSBpZiBzaG93X3BsYW5uaW5nICV9YWN0aXZleyUgZW5kaWYgJX0iIGlkPSJ0YWItYnRuLXBsYW5uaW5nIiBvbmNsaWNrPSJzd2l0Y2hHb2FsVGFiKCdwbGFubmluZycpIj4KICAgICAgICAgICAgICA8aSBjbGFzcz0iYmkgYmktY2FsY3VsYXRvci1maWxsIG1lLTEiPjwvaT4geyUgaWYgZWRpdCAlfUVkaXQgR29hbHslIGVsc2UgJX1Hb2FsIFBsYW5uaW5neyUgZW5kaWYgJX0KICAgICAgICAgICAgPC9idXR0b24+CiAgICAgICAgICA8L2xpPgogICAgICAgIDwvdWw+CgogICAgICAgIDwhLS0gRmlsdGVycyBCbG9jayAtLT4KICAgICAgICA8ZGl2IGNsYXNzPSJmaWx0ZXJzLXJvdyB7JSBpZiBzaG93X3BsYW5uaW5nICV9ZC1ub25leyUgZW5kaWYgJX0iPgogICAgICAgICAgPGZvcm0gbWV0aG9kPSJHRVQiIGlkPSJmaWx0ZXJGb3JtIiBjbGFzcz0icm93IGctMyBhbGlnbi1pdGVtcy1lbmQiPgogICAgICAgICAgICA8ZGl2IGNsYXNzPSJjb2wtbWQtMyI+CiAgICAgICAgICAgICAgPGxhYmVsIGNsYXNzPSJmb3JtLWxhYmVsIiBzdHlsZT0iZm9udC13ZWlnaHQ6IDYwMDsgZm9udC1zaXplOiAwLjg1cmVtOyBjb2xvcjogdmFyKC0tdGV4dC1kYXJrKTsiPlNlYXJjaCBHb2FsczwvbGFiZWw+CiAgICAgICAgICAgICAgPGRpdiBjbGFzcz0iaW5wdXQtZ3JvdXAiPgogICAgICAgICAgICAgICAgPHNwYW4gY2xhc3M9ImlucHV0LWdyb3VwLXRleHQgYmctbGlnaHQgYm9yZGVyLWVuZC0wIj48aSBjbGFzcz0iYmkgYmktc2VhcmNoIHRleHQtbXV0ZWQiPjwvaT48L3NwYW4+CiAgICAgICAgICAgICAgICA8aW5wdXQgdHlwZT0idGV4dCIgbmFtZT0ic2VhcmNoIiBjbGFzcz0iZm9ybS1jb250cm9sIGJvcmRlci1zdGFydC0wIGJnLWxpZ2h0IiBwbGFjZWhvbGRlcj0iZS5nLiBCdXkgYSBMYXB0b3AuLi4iIHZhbHVlPSJ7eyBzZWFyY2ggb3IgJycgfX0iPgogICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICA8L2Rpdj4KCiAgICAgICAgICAgIDxkaXYgY2xhc3M9ImNvbC1tZC0yIGNvbC02Ij4KICAgICAgICAgICAgICA8bGFiZWwgY2xhc3M9ImZvcm0tbGFiZWwiIHN0eWxlPSJmb250LXdlaWdodDogNjAwOyBmb250LXNpemU6IDAuODVyZW07IGNvbG9yOiB2YXIoLS10ZXh0LWRhcmspOyI+Q2F0ZWdvcnk8L2xhYmVsPgogICAgICAgICAgICAgIDxzZWxlY3QgbmFtZT0iY2F0ZWdvcnkiIGNsYXNzPSJmb3JtLXNlbGVjdCBiZy1saWdodCIgb25jaGFuZ2U9InRoaXMuZm9ybS5zdWJtaXQoKSI+CiAgICAgICAgICAgICAgICA8b3B0aW9uIHZhbHVlPSIiPkFsbCBDYXRlZ29yaWVzPC9vcHRpb24+CiAgICAgICAgICAgICAgICB7JSBmb3IgY2F0IGluIGNhdGVnb3JpZXMgJX0KICAgICAgICAgICAgICAgICAgPG9wdGlvbiB2YWx1ZT0ie3sgY2F0IH19IiB7JSBpZiBzZWxlY3RlZF9jYXRlZ29yeSA9PSBjYXQgJX1zZWxlY3RlZHslIGVuZGlmICV9Pnt7IGNhdCB9fTwvb3B0aW9uPgogICAgICAgICAgICAgICAgeyUgZW5kZm9yICV9CiAgICAgICAgICAgICAgPC9zZWxlY3Q+CiAgICAgICAgICAgIDwvZGl2PgoKICAgICAgICAgICAgPGRpdiBjbGFzcz0iY29sLW1kLTIgY29sLTYiPgogICAgICAgICAgICAgIDxsYWJlbCBjbGFzcz0iZm9ybS1sYWJlbCIgc3R5bGU9ImZvbnQtd2VpZ2h0OiA2MDA7IGZvbnQtc2l6ZTogMC44NXJlbTsgY29sb3I6IHZhcigtLXRleHQtZGFyayk7Ij5TdGF0dXM8L2xhYmVsPgogICAgICAgICAgICAgIDxzZWxlY3QgbmFtZT0ic3RhdHVzIiBjbGFzcz0iZm9ybS1zZWxlY3QgYmctbGlnaHQiIG9uY2hhbmdlPSJ0aGlzLmZvcm0uc3VibWl0KCkiPgogICAgICAgICAgICAgICAgPG9wdGlvbiB2YWx1ZT0iIj5BbGwgU3RhdHVzZXM8L29wdGlvbj4KICAgICAgICAgICAgICAgIHslIGZvciBzIGluIHN0YXR1c2VzICV9CiAgICAgICAgICAgICAgICAgIDxvcHRpb24gdmFsdWU9Int7IHMgfX0iIHslIGlmIHNlbGVjdGVkX3N0YXR1cyA9PSBzICV9c2VsZWN0ZWR7JSBlbmRpZiAlfT57eyBzIH19PC9vcHRpb24+CiAgICAgICAgICAgICAgICB7JSBlbmRmb3IgJX0KICAgICAgICAgICAgICA8L3NlbGVjdD4KICAgICAgICAgICAgPC9kaXY+CgogICAgICAgICAgICA8ZGl2IGNsYXNzPSJjb2wtbWQtMiBjb2wtNiI+CiAgICAgICAgICAgICAgPGxhYmVsIGNsYXNzPSJmb3JtLWxhYmVsIiBzdHlsZT0iZm9udC13ZWlnaHQ6IDYwMDsgZm9udC1zaXplOiAwLjg1cmVtOyBjb2xvcjogdmFyKC0tdGV4dC1kYXJrKTsiPlByaW9yaXR5PC9sYWJlbD4KICAgICAgICAgICAgICA8c2VsZWN0IG5hbWU9InByaW9yaXR5IiBjbGFzcz0iZm9ybS1zZWxlY3QgYmctbGlnaHQiIG9uY2hhbmdlPSJ0aGlzLmZvcm0uc3VibWl0KCkiPgogICAgICAgICAgICAgICAgPG9wdGlvbiB2YWx1ZT0iIj5BbGwgUHJpb3JpdGllczwvb3B0aW9uPgogICAgICAgICAgICAgICAgeyUgZm9yIHAgaW4gcHJpb3JpdGllcyAlfQogICAgICAgICAgICAgICAgICA8b3B0aW9uIHZhbHVlPSJ7eyBwIH19IiB7JSBpZiBzZWxlY3RlZF9wcmlvcml0eSA9PSBwICV9c2VsZWN0ZWR7JSBlbmRpZiAlfT57eyBwIH19PC9vcHRpb24+CiAgICAgICAgICAgICAgICB7JSBlbmRmb3IgJX0KICAgICAgICAgICAgICA8L3NlbGVjdD4KICAgICAgICAgICAgPC9kaXY+CgogICAgICAgICAgICA8ZGl2IGNsYXNzPSJjb2wtbWQtMiBjb2wtNiI+CiAgICAgICAgICAgICAgPGxhYmVsIGNsYXNzPSJmb3JtLWxhYmVsIiBzdHlsZT0iZm9udC13ZWlnaHQ6IDYwMDsgZm9udC1zaXplOiAwLjg1cmVtOyBjb2xvcjogdmFyKC0tdGV4dC1kYXJrKTsiPlNvcnQgQnk8L2xhYmVsPgogICAgICAgICAgICAgIDxzZWxlY3QgbmFtZT0ic29ydCIgY2xhc3M9ImZvcm0tc2VsZWN0IGJnLWxpZ2h0IiBvbmNoYW5nZT0idGhpcy5mb3JtLnN1Ym1pdCgpIj4KICAgICAgICAgICAgICAgIDxvcHRpb24gdmFsdWU9Im5ld2VzdCIgeyUgaWYgc2VsZWN0ZWRfc29ydCA9PSAnbmV3ZXN0JyAlfXNlbGVjdGVkeyUgZW5kaWYgJX0+TmV3ZXN0PC9vcHRpb24+CiAgICAgICAgICAgICAgICA8b3B0aW9uIHZhbHVlPSJvbGRlc3QiIHslIGlmIHNlbGVjdGVkX3NvcnQgPT0gJ29sZGVzdCcgJX1zZWxlY3RlZHslIGVuZGlmICV9Pk9sZGVzdDwvb3B0aW9uPgogICAgICAgICAgICAgICAgPG9wdGlvbiB2YWx1ZT0iZGVhZGxpbmUiIHslIGlmIHNlbGVjdGVkX3NvcnQgPT0gJ2RlYWRsaW5lJyAlfXNlbGVjdGVkeyUgZW5kaWYgJX0+RGVhZGxpbmU8L29wdGlvbj4KICAgICAgICAgICAgICAgIDxvcHRpb24gdmFsdWU9ImFtb3VudF9oaWdoIiB7JSBpZiBzZWxlY3RlZF9zb3J0ID09ICdhbW91bnRfaGlnaCcgJX1zZWxlY3RlZHslIGVuZGlmICV9PkFtb3VudCAoSGlnaCk8L29wdGlvbj4KICAgICAgICAgICAgICAgIDxvcHRpb24gdmFsdWU9ImFtb3VudF9sb3ciIHslIGlmIHNlbGVjdGVkX3NvcnQgPT0gJ2Ftb3VudF9sb3cnICV9c2VsZWN0ZWR7JSBlbmRpZiAlfT5BbW91bnQgKExvdyk8L29wdGlvbj4KICAgICAgICAgICAgICAgIDxvcHRpb24gdmFsdWU9InByb2dyZXNzIiB7JSBpZiBzZWxlY3RlZF9zb3J0ID09ICdwcm9ncmVzcycgJX1zZWxlY3RlZHslIGVuZGlmICV9PlByb2dyZXNzICU8L29wdGlvbj4KICAgICAgICAgICAgICA8L3NlbGVjdD4KICAgICAgICAgICAgPC9kaXY+CgogICAgICAgICAgICA8ZGl2IGNsYXNzPSJjb2wtbWQtMSBkLWdyaWQiPgogICAgICAgICAgICAgIDxhIGhyZWY9Int7IHVybF9mb3IoJ2dvYWxzX2xpc3QnKSB9fSIgY2xhc3M9ImJ0biBidG4tb3V0bGluZS1zZWNvbmRhcnkiIHN0eWxlPSJib3JkZXItcmFkaXVzOiA4cHg7Ij48aSBjbGFzcz0iYmkgYmkteC1sZyI+PC9pPjwvYT4KICAgICAgICAgICAgPC9kaXY+CiAgICAgICAgICA8L2Zvcm0+CiAgICAgICAgPC9kaXY+CgogICAgICAgIDwhLS0g4pSA4pSAIFRBQiAxOiBHb2FscyBHcmlkIOKUgOKUgCAtLT4KICAgICAgICA8ZGl2IGlkPSJnb2FsLXRhYi1saXN0IiBjbGFzcz0ieyUgaWYgc2hvd19wbGFubmluZyAlfWQtbm9uZXslIGVuZGlmICV9Ij4KICAgICAgICAgIHslIGlmIGdvYWxzICV9CiAgICAgICAgICAgIDxkaXYgY2xhc3M9ImdvYWwtZ3JpZCI+CiAgICAgICAgICAgICAgeyUgZm9yIGdvYWwgaW4gZ29hbHMgJX0KICAgICAgICAgICAgICAgIDxkaXYgY2xhc3M9ImdvYWwtY2FyZCI+CiAgICAgICAgICAgICAgICAgIDxkaXY+CiAgICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0iZ29hbC1jYXJkLWhlYWRlciI+CiAgICAgICAgICAgICAgICAgICAgICA8ZGl2PgogICAgICAgICAgICAgICAgICAgICAgICA8aDQgY2xhc3M9ImdvYWwtdGl0bGUiPnt7IGdvYWwuZ29hbF9uYW1lIH19PC9oND4KICAgICAgICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0iZ29hbC1jYXRlZ29yeSI+CiAgICAgICAgICAgICAgICAgICAgICAgICAgPGkgY2xhc3M9ImJpIHslIGlmIGdvYWwuY2F0ZWdvcnkgPT0gJ0VkdWNhdGlvbicgJX1iaS1tb3J0YXJib2FyZC1maWxseyUgZWxpZiBnb2FsLmNhdGVnb3J5ID09ICdFbGVjdHJvbmljcycgJX1iaS1sYXB0b3B7JSBlbGlmIGdvYWwuY2F0ZWdvcnkgPT0gJ1RyYXZlbCcgJX1iaS1haXJwbGFuZS1maWxseyUgZWxpZiBnb2FsLmNhdGVnb3J5ID09ICdWZWhpY2xlJyAlfWJpLWNhci1mcm9udC1maWxseyUgZWxpZiBnb2FsLmNhdGVnb3J5ID09ICdFbWVyZ2VuY3knICV9Ymktc2hpZWxkLWZpbGx7JSBlbGlmIGdvYWwuY2F0ZWdvcnkgPT0gJ0hlYWx0aCcgJX1iaS1oZWFydC1wdWxzZS1maWxseyUgZWxzZSAlfWJpLXN0YXItZmlsbHslIGVuZGlmICV9Ij48L2k+CiAgICAgICAgICAgICAgICAgICAgICAgICAge3sgZ29hbC5jYXRlZ29yeSB9fQogICAgICAgICAgICAgICAgICAgICAgICA8L2Rpdj4KICAgICAgICAgICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICAgICAgICAgICAgPHNwYW4gY2xhc3M9ImJhZGdlIGJnLXt7IGdvYWwuc3RhdHVzX2NsYXNzIH19Ij57eyBnb2FsLnN0YXR1cyB9fTwvc3Bhbj4KICAgICAgICAgICAgICAgICAgICA8L2Rpdj4KCiAgICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0iZ29hbC1hbW91bnRzIj4KICAgICAgICAgICAgICAgICAgICAgIDxkaXYgY2xhc3M9ImFtb3VudC1pdGVtIj4KICAgICAgICAgICAgICAgICAgICAgICAgPHNwYW4gY2xhc3M9ImFtb3VudC1sYWJlbCI+VGFyZ2V0PC9zcGFuPgogICAgICAgICAgICAgICAgICAgICAgICA8c3BhbiBjbGFzcz0iYW1vdW50LXZhbCI+4oK5e3sgZ29hbC50YXJnZXRfYW1vdW50fGlucl9mb3JtYXQgfX08L3NwYW4+CiAgICAgICAgICAgICAgICAgICAgICA8L2Rpdj4KICAgICAgICAgICAgICAgICAgICAgIDxkaXYgY2xhc3M9ImFtb3VudC1pdGVtIj4KICAgICAgICAgICAgICAgICAgICAgICAgPHNwYW4gY2xhc3M9ImFtb3VudC1sYWJlbCI+U2F2ZWQ8L3NwYW4+CiAgICAgICAgICAgICAgICAgICAgICAgIDxzcGFuIGNsYXNzPSJhbW91bnQtdmFsIHNhdmVkIj7igrl7eyBnb2FsLmN1cnJlbnRfYW1vdW50fGlucl9mb3JtYXQgfX08L3NwYW4+CiAgICAgICAgICAgICAgICAgICAgICA8L2Rpdj4KICAgICAgICAgICAgICAgICAgICAgIDxkaXYgY2xhc3M9ImFtb3VudC1pdGVtIj4KICAgICAgICAgICAgICAgICAgICAgICAgPHNwYW4gY2xhc3M9ImFtb3VudC1sYWJlbCI+UmVtYWluaW5nPC9zcGFuPgogICAgICAgICAgICAgICAgICAgICAgICA8c3BhbiBjbGFzcz0iYW1vdW50LXZhbCByZW1haW5pbmciPuKCuXt7IGdvYWwucmVtYWluaW5nX2Ftb3VudHxpbnJfZm9ybWF0IH19PC9zcGFuPgogICAgICAgICAgICAgICAgICAgICAgPC9kaXY+CiAgICAgICAgICAgICAgICAgICAgPC9kaXY+CgogICAgICAgICAgICAgICAgICAgIDxkaXYgY2xhc3M9InByb2dyZXNzLXNlY3Rpb24iPgogICAgICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0icHJvZ3Jlc3MtaGVhZGVyIj4KICAgICAgICAgICAgICAgICAgICAgICAgPHNwYW4gY2xhc3M9InByb2dyZXNzLXBjdCI+e3sgZ29hbC5wcm9ncmVzc19wZXJjZW50YWdlIH19JSBDb21wbGV0ZTwvc3Bhbj4KICAgICAgICAgICAgICAgICAgICAgICAgPHNwYW4gY2xhc3M9ImJhZGdlIHJvdW5kZWQtcGlsbCBiZy17eyBnb2FsLnNtYXJ0X3N0YXR1c19jbGFzcyB9fSI+e3sgZ29hbC5zbWFydF9zdGF0dXMgfX08L3NwYW4+CiAgICAgICAgICAgICAgICAgICAgICA8L2Rpdj4KICAgICAgICAgICAgICAgICAgICAgIDxkaXYgY2xhc3M9InByb2dyZXNzIiBzdHlsZT0iaGVpZ2h0OiA4cHg7IGJvcmRlci1yYWRpdXM6IDk5OXB4OyI+CiAgICAgICAgICAgICAgICAgICAgICAgIDxkaXYgY2xhc3M9InByb2dyZXNzLWJhciBiZy17eyBnb2FsLnNtYXJ0X3N0YXR1c19jbGFzcyB9fSIgcm9sZT0icHJvZ3Jlc3NiYXIiIHN0eWxlPSJ3aWR0aDoge3sgZ29hbC5wcm9ncmVzc19wZXJjZW50YWdlIH19JSI+PC9kaXY+CiAgICAgICAgICAgICAgICAgICAgICA8L2Rpdj4KICAgICAgICAgICAgICAgICAgICA8L2Rpdj4KICAgICAgICAgICAgICAgICAgPC9kaXY+CgogICAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJnb2FsLWZvb3RlciI+CiAgICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0iZ29hbC1kYXRlIj4KICAgICAgICAgICAgICAgICAgICAgIHslIGlmIGdvYWwudGFyZ2V0X2RhdGUgJX0KICAgICAgICAgICAgICAgICAgICAgICAgPGkgY2xhc3M9ImJpIGJpLWNhbGVuZGFyLWV2ZW50Ij48L2k+CiAgICAgICAgICAgICAgICAgICAgICAgIDxzcGFuPnt7IGdvYWwudGFyZ2V0X2RhdGUgfX08L3NwYW4+CiAgICAgICAgICAgICAgICAgICAgICAgIHslIGlmIGdvYWwuZGF5c19sZWZ0IGlzIG5vdCBub25lICV9CiAgICAgICAgICAgICAgICAgICAgICAgICAgPHNwYW4gY2xhc3M9InRleHQte3sgJ2RhbmdlcicgaWYgZ29hbC5kYXlzX2xlZnQgPCAzMCBlbHNlICdtdXRlZCcgfX0iPgogICAgICAgICAgICAgICAgICAgICAgICAgICAgKHt7IGdvYWwuZGF5c19sZWZ0IH19ZCBsZWZ0KQogICAgICAgICAgICAgICAgICAgICAgICAgIDwvc3Bhbj4KICAgICAgICAgICAgICAgICAgICAgICAgeyUgZW5kaWYgJX0KICAgICAgICAgICAgICAgICAgICAgIHslIGVsc2UgJX0KICAgICAgICAgICAgICAgICAgICAgICAgPHNwYW4+Tm8gZGVhZGxpbmU8L3NwYW4+CiAgICAgICAgICAgICAgICAgICAgICB7JSBlbmRpZiAlfQogICAgICAgICAgICAgICAgICAgIDwvZGl2PgoKICAgICAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJidG4tYWN0aW9uLWdyb3VwIj4KICAgICAgICAgICAgICAgICAgICAgIDxhIGhyZWY9Int7IHVybF9mb3IoJ2dvYWxfZGV0YWlsJywgZ29hbF9pZD1nb2FsLmlkKSB9fSIgY2xhc3M9ImJ0bi1pY29uIiB0aXRsZT0iVmlldyBEZXRhaWxzIj48aSBjbGFzcz0iYmkgYmktZXllIj48L2k+PC9hPgogICAgICAgICAgICAgICAgICAgICAgPGEgaHJlZj0ie3sgdXJsX2ZvcignZWRpdF9nb2FsJywgZ29hbF9pZD1nb2FsLmlkKSB9fSIgY2xhc3M9ImJ0bi1pY29uIiB0aXRsZT0iRWRpdCI+PGkgY2xhc3M9ImJpIGJpLXBlbmNpbCI+PC9pPjwvYT4KICAgICAgICAgICAgICAgICAgICAgIDxidXR0b24gY2xhc3M9ImJ0bi1pY29uIGRlbGV0ZSIgdGl0bGU9IkRlbGV0ZSIgb25jbGljaz0iY29uZmlybURlbGV0ZUdvYWwoe3sgZ29hbC5pZCB9fSwgJ3t7IGdvYWwuZ29hbF9uYW1lfHJlcGxhY2UoIiciLCJcJyIpIH19JykiPgogICAgICAgICAgICAgICAgICAgICAgICA8aSBjbGFzcz0iYmkgYmktdHJhc2giPjwvaT4KICAgICAgICAgICAgICAgICAgICAgIDwvYnV0dG9uPgogICAgICAgICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICAgICAgICA8L2Rpdj4KICAgICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICAgIHslIGVuZGZvciAlfQogICAgICAgICAgICA8L2Rpdj4KICAgICAgICAgIHslIGVsc2UgJX0KICAgICAgICAgICAgPGRpdiBjbGFzcz0icGFuZWwgdGV4dC1jZW50ZXIgcHktNSI+CiAgICAgICAgICAgICAgPGkgY2xhc3M9ImJpIGJpLWZsYWctZmlsbCIgc3R5bGU9ImZvbnQtc2l6ZTogM3JlbTsgY29sb3I6ICNDQkQ1RTE7Ij48L2k+CiAgICAgICAgICAgICAgPGgzIGNsYXNzPSJtdC0zIiBzdHlsZT0iZm9udC13ZWlnaHQ6IDcwMDsiPk5vIEdvYWxzIEZvdW5kPC9oMz4KICAgICAgICAgICAgICA8cCBjbGFzcz0idGV4dC1tdXRlZCI+Q3JlYXRlIGEgZ29hbCB0byBzdGFydCBwbGFubmluZyB5b3VyIHNhdmluZ3MgbWlsZXN0b25lcyE8L3A+CiAgICAgICAgICAgICAgPGJ1dHRvbiBjbGFzcz0iYnRuIGJ0bi1wcmltYXJ5IG10LTIiIG9uY2xpY2s9InN3aXRjaEdvYWxUYWIoJ3BsYW5uaW5nJykiPjxpIGNsYXNzPSJiaSBiaS1wbHVzLWxnIj48L2k+IENyZWF0ZSBGaXJzdCBHb2FsPC9idXR0b24+CiAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgeyUgZW5kaWYgJX0KICAgICAgICA8L2Rpdj4KCiAgICAgICAgPCEtLSDilIDilIAgVEFCIDI6IEdvYWwgUGxhbm5pbmcgRm9ybSAmIENhbGN1bGF0b3Ig4pSA4pSAIC0tPgogICAgICAgIDxkaXYgaWQ9ImdvYWwtdGFiLXBsYW5uaW5nIiBjbGFzcz0ieyUgaWYgbm90IHNob3dfcGxhbm5pbmcgJX1kLW5vbmV7JSBlbmRpZiAlfSI+CiAgICAgICAgICA8ZGl2IGNsYXNzPSJyb3cgZy00Ij4KICAgICAgICAgICAgPCEtLSBGb3JtIFBhbmVsIC0tPgogICAgICAgICAgICA8ZGl2IGNsYXNzPSJjb2wtbGctOCI+CiAgICAgICAgICAgICAgPGRpdiBjbGFzcz0icGFuZWwgZm9ybS1wYW5lbCI+CiAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJmb3JtLXBhbmVsLWhlYWRlciBkLWZsZXggYWxpZ24taXRlbXMtY2VudGVyIG1iLTQiPgogICAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJmb3JtLXBhbmVsLWljb24gYmctcHJpbWFyeS1zdWJ0bGUgdGV4dC1wcmltYXJ5IiBzdHlsZT0id2lkdGg6IDQ0cHg7IGhlaWdodDogNDRweDsgYm9yZGVyLXJhZGl1czogNTAlOyBkaXNwbGF5OiBncmlkOyBwbGFjZS1pdGVtczogY2VudGVyOyBmb250LXNpemU6IDEuMnJlbTsgbWFyZ2luLXJpZ2h0OiAxMnB4OyI+CiAgICAgICAgICAgICAgICAgICAgPGkgY2xhc3M9ImJpIGJpLXBsdXMtY2lyY2xlIj48L2k+CiAgICAgICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICAgICAgICA8ZGl2PgogICAgICAgICAgICAgICAgICAgIDxoNCBjbGFzcz0iZm9ybS1wYW5lbC10aXRsZSBtYi0wIiBzdHlsZT0iZm9udC13ZWlnaHQ6IDcwMDsgY29sb3I6IHZhcigtLXRleHQtZGFyayk7Ij5Hb2FsIENvbmZpZ3VyYXRpb248L2g0PgogICAgICAgICAgICAgICAgICAgIDxwIGNsYXNzPSJmb3JtLXBhbmVsLWRlc2MgbWItMCB0ZXh0LW11dGVkIiBzdHlsZT0iZm9udC1zaXplOiAwLjgycmVtOyI+UHJvdmlkZSB0YXJnZXRzLCBjdXJyZW50IHZhbHVlcyBhbmQgY2F0ZWdvcnkgbWFwcGluZzwvcD4KICAgICAgICAgICAgICAgICAgPC9kaXY+CiAgICAgICAgICAgICAgICA8L2Rpdj4KCiAgICAgICAgICAgICAgICA8Zm9ybSBtZXRob2Q9IlBPU1QiIGFjdGlvbj0ieyUgaWYgZWRpdCAlfXt7IHVybF9mb3IoJ2VkaXRfZ29hbCcsIGdvYWxfaWQ9Z29hbC5pZCkgfX17JSBlbHNlICV9e3sgdXJsX2ZvcignZ29hbF9wbGFubmluZycpIH19eyUgZW5kaWYgJX0iIGlkPSJnb2FsRm9ybSI+CiAgICAgICAgICAgICAgICAgIDxkaXYgY2xhc3M9InJvdyBnLTMiPgogICAgICAgICAgICAgICAgICAgIDxkaXYgY2xhc3M9ImNvbC1tZC02Ij4KICAgICAgICAgICAgICAgICAgICAgIDxsYWJlbCBjbGFzcz0iZm9ybS1sYWJlbCIgc3R5bGU9ImZvbnQtd2VpZ2h0OiA2MDA7Ij5Hb2FsIE5hbWUgKjwvbGFiZWw+CiAgICAgICAgICAgICAgICAgICAgICA8aW5wdXQgdHlwZT0idGV4dCIgaWQ9ImdvYWxfbmFtZSIgbmFtZT0iZ29hbF9uYW1lIiBjbGFzcz0iZm9ybS1jb250cm9sIiBwbGFjZWhvbGRlcj0iZS5nLiBEcmVhbSBWYWNhdGlvbiwgTGFwdG9wLi4uIiB2YWx1ZT0ie3sgZ29hbC5nb2FsX25hbWUgaWYgZWRpdCBlbHNlIChmb3JtLmdvYWxfbmFtZSBpZiBmb3JtIGVsc2UgJycpIH19IiByZXF1aXJlZD4KICAgICAgICAgICAgICAgICAgICA8L2Rpdj4KCiAgICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0iY29sLW1kLTYiPgogICAgICAgICAgICAgICAgICAgICAgPGxhYmVsIGNsYXNzPSJmb3JtLWxhYmVsIiBzdHlsZT0iZm9udC13ZWlnaHQ6IDYwMDsiPkdvYWwgVHlwZTwvbGFiZWw+CiAgICAgICAgICAgICAgICAgICAgICA8aW5wdXQgdHlwZT0idGV4dCIgaWQ9ImdvYWxfdHlwZSIgbmFtZT0iZ29hbF90eXBlIiBjbGFzcz0iZm9ybS1jb250cm9sIiBwbGFjZWhvbGRlcj0iZS5nLiBTaG9ydC10ZXJtLCBMb25nLXRlcm0uLi4iIHZhbHVlPSJ7eyBnb2FsLmdvYWxfdHlwZSBpZiBlZGl0IGVsc2UgKGZvcm0uZ29hbF90eXBlIGlmIGZvcm0gZWxzZSAnJykgfX0iPgogICAgICAgICAgICAgICAgICAgIDwvZGl2PgoKICAgICAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJjb2wtMTIiPgogICAgICAgICAgICAgICAgICAgICAgPGxhYmVsIGNsYXNzPSJmb3JtLWxhYmVsIiBzdHlsZT0iZm9udC13ZWlnaHQ6IDYwMDsiPkRlc2NyaXB0aW9uPC9sYWJlbD4KICAgICAgICAgICAgICAgICAgICAgIDx0ZXh0YXJlYSBpZD0iZGVzY3JpcHRpb24iIG5hbWU9ImRlc2NyaXB0aW9uIiBjbGFzcz0iZm9ybS1jb250cm9sIiBwbGFjZWhvbGRlcj0iV2hhdCBhcmUgZGV0YWlscyBvZiB0aGlzIGdvYWw/Ij57eyBnb2FsLmRlc2NyaXB0aW9uIGlmIGVkaXQgZWxzZSAoZm9ybS5kZXNjcmlwdGlvbiBpZiBmb3JtIGVsc2UgJycpIH19PC90ZXh0YXJlYT4KICAgICAgICAgICAgICAgICAgICA8L2Rpdj4KCiAgICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0iY29sLW1kLTQiPgogICAgICAgICAgICAgICAgICAgICAgPGxhYmVsIGNsYXNzPSJmb3JtLWxhYmVsIiBzdHlsZT0iZm9udC13ZWlnaHQ6IDYwMDsiPkNhdGVnb3J5PC9sYWJlbD4KICAgICAgICAgICAgICAgICAgICAgIDxzZWxlY3QgaWQ9ImNhdGVnb3J5IiBuYW1lPSJjYXRlZ29yeSIgY2xhc3M9ImZvcm0tc2VsZWN0Ij4KICAgICAgICAgICAgICAgICAgICAgICAgeyUgZm9yIGNhdCBpbiBjYXRlZ29yaWVzICV9CiAgICAgICAgICAgICAgICAgICAgICAgICAgPG9wdGlvbiB2YWx1ZT0ie3sgY2F0IH19IiB7JSBpZiBlZGl0IGFuZCBnb2FsLmNhdGVnb3J5ID09IGNhdCAlfXNlbGVjdGVkeyUgZWxpZiBmb3JtIGFuZCBmb3JtLmNhdGVnb3J5ID09IGNhdCAlfXNlbGVjdGVkeyUgZW5kaWYgJX0+e3sgY2F0IH19PC9vcHRpb24+CiAgICAgICAgICAgICAgICAgICAgICAgIHslIGVuZGZvciAlfQogICAgICAgICAgICAgICAgICAgICAgPC9zZWxlY3Q+CiAgICAgICAgICAgICAgICAgICAgPC9kaXY+CgogICAgICAgICAgICAgICAgICAgIDxkaXYgY2xhc3M9ImNvbC1tZC00Ij4KICAgICAgICAgICAgICAgICAgICAgIDxsYWJlbCBjbGFzcz0iZm9ybS1sYWJlbCIgc3R5bGU9ImZvbnQtd2VpZ2h0OiA2MDA7Ij5Qcmlvcml0eTwvbGFiZWw+CiAgICAgICAgICAgICAgICAgICAgICA8c2VsZWN0IGlkPSJwcmlvcml0eSIgbmFtZT0icHJpb3JpdHkiIGNsYXNzPSJmb3JtLXNlbGVjdCI+CiAgICAgICAgICAgICAgICAgICAgICAgIHslIGZvciBwIGluIHByaW9yaXRpZXMgJX0KICAgICAgICAgICAgICAgICAgICAgICAgICA8b3B0aW9uIHZhbHVlPSJ7eyBwIH19IiB7JSBpZiBlZGl0IGFuZCBnb2FsLnByaW9yaXR5ID09IHAgJX1zZWxlY3RlZHslIGVsaWYgZm9ybSBhbmQgZm9ybS5wcmlvcml0eSA9PSBwICV9c2VsZWN0ZWR7JSBlbmRpZiAlfT57eyBwIH19PC9vcHRpb24+CiAgICAgICAgICAgICAgICAgICAgICAgIHslIGVuZGZvciAlfQogICAgICAgICAgICAgICAgICAgICAgPC9zZWxlY3Q+CiAgICAgICAgICAgICAgICAgICAgPC9kaXY+CgogICAgICAgICAgICAgICAgICAgIDxkaXYgY2xhc3M9ImNvbC1tZC00Ij4KICAgICAgICAgICAgICAgICAgICAgIDxsYWJlbCBjbGFzcz0iZm9ybS1sYWJlbCIgc3R5bGU9ImZvbnQtd2VpZ2h0OiA2MDA7Ij5TdGF0dXM8L2xhYmVsPgogICAgICAgICAgICAgICAgICAgICAgPHNlbGVjdCBpZD0ic3RhdHVzIiBuYW1lPSJzdGF0dXMiIGNsYXNzPSJmb3JtLXNlbGVjdCI+CiAgICAgICAgICAgICAgICAgICAgICAgIHslIGZvciBzIGluIHN0YXR1c2VzICV9CiAgICAgICAgICAgICAgICAgICAgICAgICAgPG9wdGlvbiB2YWx1ZT0ie3sgcyB9fSIgeyUgaWYgZWRpdCBhbmQgZ29hbC5zdGF0dXMgPT0gcyAlfXNlbGVjdGVkeyUgZWxpZiBmb3JtIGFuZCBmb3JtLnN0YXR1cyA9PSBzICV9c2VsZWN0ZWR7JSBlbmRpZiAlfT57eyBzIH19PC9vcHRpb24+CiAgICAgICAgICAgICAgICAgICAgICAgIHslIGVuZGZvciAlfQogICAgICAgICAgICAgICAgICAgICAgPC9zZWxlY3Q+CiAgICAgICAgICAgICAgICAgICAgPC9kaXY+CgogICAgICAgICAgICAgICAgICAgIDxkaXYgY2xhc3M9ImNvbC1tZC02Ij4KICAgICAgICAgICAgICAgICAgICAgIDxsYWJlbCBjbGFzcz0iZm9ybS1sYWJlbCIgc3R5bGU9ImZvbnQtd2VpZ2h0OiA2MDA7Ij5UYXJnZXQgQW1vdW50IChJTlIpICo8L2xhYmVsPgogICAgICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0iaW5wdXQtZ3JvdXAiPgogICAgICAgICAgICAgICAgICAgICAgICA8c3BhbiBjbGFzcz0iaW5wdXQtZ3JvdXAtdGV4dCI+4oK5PC9zcGFuPgogICAgICAgICAgICAgICAgICAgICAgICA8aW5wdXQgdHlwZT0ibnVtYmVyIiBpZD0idGFyZ2V0X2Ftb3VudCIgbmFtZT0idGFyZ2V0X2Ftb3VudCIgY2xhc3M9ImZvcm0tY29udHJvbCIgcGxhY2Vob2xkZXI9IjAuMDAiIHN0ZXA9IjAuMDEiIG1pbj0iMC4wMSIgdmFsdWU9Int7IGdvYWwudGFyZ2V0X2Ftb3VudCBpZiBlZGl0IGVsc2UgKGZvcm0udGFyZ2V0X2Ftb3VudCBpZiBmb3JtIGVsc2UgJycpIH19IiByZXF1aXJlZD4KICAgICAgICAgICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICAgICAgICAgIDwvZGl2PgoKICAgICAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJjb2wtbWQtNiI+CiAgICAgICAgICAgICAgICAgICAgICA8bGFiZWwgY2xhc3M9ImZvcm0tbGFiZWwiIHN0eWxlPSJmb250LXdlaWdodDogNjAwOyI+Q3VycmVudCBTYXZpbmdzIChJTlIpPC9sYWJlbD4KICAgICAgICAgICAgICAgICAgICAgIDxkaXYgY2xhc3M9ImlucHV0LWdyb3VwIj4KICAgICAgICAgICAgICAgICAgICAgICAgPHNwYW4gY2xhc3M9ImlucHV0LWdyb3VwLXRleHQiPuKCuTwvc3Bhbj4KICAgICAgICAgICAgICAgICAgICAgICAgPGlucHV0IHR5cGU9Im51bWJlciIgaWQ9ImN1cnJlbnRfYW1vdW50IiBuYW1lPSJjdXJyZW50X2Ftb3VudCIgY2xhc3M9ImZvcm0tY29udHJvbCIgcGxhY2Vob2xkZXI9IjAiIHN0ZXA9IjAuMDEiIG1pbj0iMCIgdmFsdWU9Int7IGdvYWwuY3VycmVudF9hbW91bnQgaWYgZWRpdCBlbHNlIChmb3JtLmN1cnJlbnRfYW1vdW50IGlmIGZvcm0gZWxzZSAnJykgfX0iPgogICAgICAgICAgICAgICAgICAgICAgPC9kaXY+CiAgICAgICAgICAgICAgICAgICAgPC9kaXY+CgogICAgICAgICAgICAgICAgICAgIDxkaXYgY2xhc3M9ImNvbC1tZC02Ij4KICAgICAgICAgICAgICAgICAgICAgIDxsYWJlbCBjbGFzcz0iZm9ybS1sYWJlbCIgc3R5bGU9ImZvbnQtd2VpZ2h0OiA2MDA7Ij5TdGFydCBEYXRlPC9sYWJlbD4KICAgICAgICAgICAgICAgICAgICAgIDxpbnB1dCB0eXBlPSJkYXRlIiBpZD0ic3RhcnRfZGF0ZSIgbmFtZT0ic3RhcnRfZGF0ZSIgY2xhc3M9ImZvcm0tY29udHJvbCIgdmFsdWU9Int7IGdvYWwuc3RhcnRfZGF0ZSBpZiBlZGl0IGVsc2UgKGZvcm0uc3RhcnRfZGF0ZSBpZiBmb3JtIGVsc2UgdG9kYXkpIH19Ij4KICAgICAgICAgICAgICAgICAgICA8L2Rpdj4KCiAgICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0iY29sLW1kLTYiPgogICAgICAgICAgICAgICAgICAgICAgPGxhYmVsIGNsYXNzPSJmb3JtLWxhYmVsIiBzdHlsZT0iZm9udC13ZWlnaHQ6IDYwMDsiPlRhcmdldCBEYXRlPC9sYWJlbD4KICAgICAgICAgICAgICAgICAgICAgIDxpbnB1dCB0eXBlPSJkYXRlIiBpZD0idGFyZ2V0X2RhdGUiIG5hbWU9InRhcmdldF9kYXRlIiBjbGFzcz0iZm9ybS1jb250cm9sIiB2YWx1ZT0ie3sgZ29hbC50YXJnZXRfZGF0ZSBpZiBlZGl0IGVsc2UgKGZvcm0udGFyZ2V0X2RhdGUgaWYgZm9ybSBlbHNlICcnKSB9fSI+CiAgICAgICAgICAgICAgICAgICAgPC9kaXY+CgogICAgICAgICAgICAgICAgICAgIDxkaXYgY2xhc3M9ImNvbC0xMiI+CiAgICAgICAgICAgICAgICAgICAgICA8bGFiZWwgY2xhc3M9ImZvcm0tbGFiZWwiIHN0eWxlPSJmb250LXdlaWdodDogNjAwOyI+U3RyYXRlZ3kgTm90ZXMgLyBQcmlvcml0eSBJbmZvPC9sYWJlbD4KICAgICAgICAgICAgICAgICAgICAgIDx0ZXh0YXJlYSBpZD0ibm90ZXMiIG5hbWU9Im5vdGVzIiBjbGFzcz0iZm9ybS1jb250cm9sIiBwbGFjZWhvbGRlcj0iV3JpdGUgYW55IHNwZWNpZmljIHN0cmF0ZWd5IG9yIHByaW9yaXR5IGRldGFpbHMuLi4iPnt7IGdvYWwubm90ZXMgaWYgZWRpdCBlbHNlIChmb3JtLm5vdGVzIGlmIGZvcm0gZWxzZSAnJykgfX08L3RleHRhcmVhPgogICAgICAgICAgICAgICAgICAgIDwvZGl2PgoKICAgICAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJjb2wtMTIgbXQtNCI+CiAgICAgICAgICAgICAgICAgICAgICA8YnV0dG9uIHR5cGU9InN1Ym1pdCIgY2xhc3M9ImJ0biBidG4tcHJpbWFyeSBweC00IHB5LTIiIHN0eWxlPSJib3JkZXItcmFkaXVzOiAxMHB4OyI+CiAgICAgICAgICAgICAgICAgICAgICAgIDxpIGNsYXNzPSJiaSB7JSBpZiBlZGl0ICV9Ymktc2F2ZXslIGVsc2UgJX1iaS1wbHVzLWNpcmNsZXslIGVuZGlmICV9IG1lLTEiPjwvaT4KICAgICAgICAgICAgICAgICAgICAgICAgeyUgaWYgZWRpdCAlfVNhdmUgR29hbHslIGVsc2UgJX1DcmVhdGUgR29hbHslIGVuZGlmICV9CiAgICAgICAgICAgICAgICAgICAgICA8L2J1dHRvbj4KICAgICAgICAgICAgICAgICAgICA8L2Rpdj4KICAgICAgICAgICAgICAgICAgPC9kaXY+CiAgICAgICAgICAgICAgICA8L2Zvcm0+CiAgICAgICAgICAgICAgPC9kaXY+CiAgICAgICAgICAgIDwvZGl2PgoKICAgICAgICAgICAgPCEtLSBTYXZpbmdzIENhbGN1bGF0b3IgU2lkZWJhciAtLT4KICAgICAgICAgICAgPGRpdiBjbGFzcz0iY29sLWxnLTQiPgogICAgICAgICAgICAgIDxkaXYgY2xhc3M9InByZXZpZXctcGFuZWwiPgogICAgICAgICAgICAgICAgPGg0IGNsYXNzPSJwcmV2aWV3LXRpdGxlIj48aSBjbGFzcz0iYmkgYmktY2FsY3VsYXRvciB0ZXh0LXByaW1hcnkiPjwvaT4gU2F2aW5ncyBDYWxjdWxhdG9yPC9oND4KICAgICAgICAgICAgICAgIAogICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0icHJldmlldy1yb3ciPgogICAgICAgICAgICAgICAgICA8c3BhbiBjbGFzcz0icHJldmlldy1sYWJlbCI+VGFyZ2V0IEFtb3VudDwvc3Bhbj4KICAgICAgICAgICAgICAgICAgPHNwYW4gY2xhc3M9InByZXZpZXctdmFsdWUiIGlkPSJwcmV2LXRhcmdldCI+4oK5MC4wMDwvc3Bhbj4KICAgICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0icHJldmlldy1yb3ciPgogICAgICAgICAgICAgICAgICA8c3BhbiBjbGFzcz0icHJldmlldy1sYWJlbCI+Q3VycmVudCBTYXZpbmdzPC9zcGFuPgogICAgICAgICAgICAgICAgICA8c3BhbiBjbGFzcz0icHJldmlldy12YWx1ZSIgaWQ9InByZXYtY3VycmVudCI+4oK5MC4wMDwvc3Bhbj4KICAgICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0icHJldmlldy1yb3ciPgogICAgICAgICAgICAgICAgICA8c3BhbiBjbGFzcz0icHJldmlldy1sYWJlbCI+UmVtYWluaW5nPC9zcGFuPgogICAgICAgICAgICAgICAgICA8c3BhbiBjbGFzcz0icHJldmlldy12YWx1ZSB0ZXh0LWRhbmdlciIgaWQ9InByZXYtcmVtYWluaW5nIj7igrkwLjAwPC9zcGFuPgogICAgICAgICAgICAgICAgPC9kaXY+CiAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJwcmV2aWV3LXJvdyI+CiAgICAgICAgICAgICAgICAgIDxzcGFuIGNsYXNzPSJwcmV2aWV3LWxhYmVsIj5Qcm9ncmVzczwvc3Bhbj4KICAgICAgICAgICAgICAgICAgPHNwYW4gY2xhc3M9InByZXZpZXctdmFsdWUgdGV4dC1zdWNjZXNzIiBpZD0icHJldi1wcm9ncmVzcyI+MC4wJTwvc3Bhbj4KICAgICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0icHJldmlldy1yb3ciPgogICAgICAgICAgICAgICAgICA8c3BhbiBjbGFzcz0icHJldmlldy1sYWJlbCI+TW9udGhzIExlZnQ8L3NwYW4+CiAgICAgICAgICAgICAgICAgIDxzcGFuIGNsYXNzPSJwcmV2aWV3LXZhbHVlIiBpZD0icHJldi1tb250aHMiPk4vQTwvc3Bhbj4KICAgICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0icHJldmlldy1yb3ciPgogICAgICAgICAgICAgICAgICA8c3BhbiBjbGFzcz0icHJldmlldy1sYWJlbCI+TW9udGhseSBOZWVkZWQ8L3NwYW4+CiAgICAgICAgICAgICAgICAgIDxzcGFuIGNsYXNzPSJwcmV2aWV3LXZhbHVlIHRleHQtcHJpbWFyeSIgaWQ9InByZXYtbW9udGhseSI+4oK5MC4wMDwvc3Bhbj4KICAgICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0icHJldmlldy1yb3ciPgogICAgICAgICAgICAgICAgICA8c3BhbiBjbGFzcz0icHJldmlldy1sYWJlbCI+V2Vla2x5IE5lZWRlZDwvc3Bhbj4KICAgICAgICAgICAgICAgICAgPHNwYW4gY2xhc3M9InByZXZpZXctdmFsdWUgdGV4dC1wcmltYXJ5IiBpZD0icHJldi13ZWVrbHkiPuKCuTAuMDA8L3NwYW4+CiAgICAgICAgICAgICAgICA8L2Rpdj4KCiAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJtdC00Ij4KICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0icHJvZ3Jlc3MiIHN0eWxlPSJoZWlnaHQ6IDEwcHg7IGJvcmRlci1yYWRpdXM6IDk5OXB4OyBiYWNrZ3JvdW5kLWNvbG9yOiAjRTJFOEYwOyI+CiAgICAgICAgICAgICAgICAgICAgPGRpdiBpZD0icHJldi1wcm9ncmVzcy1iYXIiIGNsYXNzPSJwcm9ncmVzcy1iYXIgYmctc3VjY2VzcyIgcm9sZT0icHJvZ3Jlc3NiYXIiIHN0eWxlPSJ3aWR0aDogMCUiPjwvZGl2PgogICAgICAgICAgICAgICAgICA8L2Rpdj4KICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0idGV4dC1jZW50ZXIgbXQtMiI+CiAgICAgICAgICAgICAgICAgICAgPHNwYW4gaWQ9InByZXYtcHJvZ3Jlc3MtbGJsIiBzdHlsZT0iZm9udC1zaXplOiAwLjhyZW07IGZvbnQtd2VpZ2h0OiA2MDA7IGNvbG9yOiB2YXIoLS10ZXh0LW11dGVkKTsiPjAlIGNvbXBsZXRlPC9zcGFuPgogICAgICAgICAgICAgICAgICA8L2Rpdj4KICAgICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICA8L2Rpdj4KICAgICAgICAgIDwvZGl2PgogICAgICAgIDwvZGl2PgoKICAgICAgPC9kaXY+CiAgICA8L21haW4+CiAgPC9kaXY+CgogIDxzY3JpcHQgc3JjPSJodHRwczovL2Nkbi5qc2RlbGl2ci5uZXQvbnBtL2Jvb3RzdHJhcEA1LjMuMy9kaXN0L2pzL2Jvb3RzdHJhcC5idW5kbGUubWluLmpzIj48L3NjcmlwdD4KICA8c2NyaXB0IHNyYz0ie3sgdXJsX2Zvcignc3RhdGljJywgZmlsZW5hbWU9J2pzL2N1cnNvci5qcycpIH19Ij48L3NjcmlwdD4KICA8c2NyaXB0PgogICAgZnVuY3Rpb24gY29uZmlybURlbGV0ZUdvYWwoaWQsIG5hbWUpIHsKICAgICAgaWYoY29uZmlybSgnQXJlIHlvdSBzdXJlIHlvdSB3YW50IHRvIGRlbGV0ZSB0aGUgZ29hbCAiJyArIG5hbWUgKyAnIj8nKSkgewogICAgICAgIGNvbnN0IGZvcm0gPSBkb2N1bWVudC5jcmVhdGVFbGVtZW50KCdmb3JtJyk7CiAgICAgICAgZm9ybS5tZXRob2QgPSAnUE9TVCc7CiAgICAgICAgZm9ybS5hY3Rpb24gPSAnL2dvYWxzLycgKyBpZCArICcvZGVsZXRlJzsKICAgICAgICBkb2N1bWVudC5ib2R5LmFwcGVuZENoaWxkKGZvcm0pOwogICAgICAgIGZvcm0uc3VibWl0KCk7CiAgICAgIH0KICAgIH0KCiAgICBmdW5jdGlvbiBzd2l0Y2hHb2FsVGFiKHRhYikgewogICAgICBjb25zdCBsaXN0VGFiID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ2dvYWwtdGFiLWxpc3QnKTsKICAgICAgY29uc3QgcGxhbm5pbmdUYWIgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgnZ29hbC10YWItcGxhbm5pbmcnKTsKICAgICAgY29uc3QgbGlzdEJ0biA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCd0YWItYnRuLWxpc3QnKTsKICAgICAgY29uc3QgcGxhbm5pbmdCdG4gPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgndGFiLWJ0bi1wbGFubmluZycpOwogICAgICBjb25zdCBmaWx0ZXJzID0gZG9jdW1lbnQucXVlcnlTZWxlY3RvcignLmZpbHRlcnMtcm93Jyk7CgogICAgICBpZiAodGFiID09PSAnbGlzdCcpIHsKICAgICAgICBsaXN0VGFiLmNsYXNzTGlzdC5yZW1vdmUoJ2Qtbm9uZScpOwogICAgICAgIHBsYW5uaW5nVGFiLmNsYXNzTGlzdC5hZGQoJ2Qtbm9uZScpOwogICAgICAgIGxpc3RCdG4uY2xhc3NMaXN0LmFkZCgnYWN0aXZlJyk7CiAgICAgICAgcGxhbm5pbmdCdG4uY2xhc3NMaXN0LnJlbW92ZSgnYWN0aXZlJyk7CiAgICAgICAgaWYgKGZpbHRlcnMpIGZpbHRlcnMuY2xhc3NMaXN0LnJlbW92ZSgnZC1ub25lJyk7CiAgICAgICAgLy8gY2hhbmdlIHRpdGxlIGFuZCBlZGl0IGJ1dHRvbiB0ZXh0IGlmIGl0IHdhcyBlZGl0aW5nCiAgICAgICAgY29uc3QgdGl0bGVFbCA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCd0YWItYnRuLXBsYW5uaW5nJyk7CiAgICAgICAgaWYgKHRpdGxlRWwpIHRpdGxlRWwuaW5uZXJIVE1MID0gJzxpIGNsYXNzPSJiaSBiaS1jYWxjdWxhdG9yLWZpbGwgbWUtMSI+PC9pPiBHb2FsIFBsYW5uaW5nJzsKICAgICAgfSBlbHNlIHsKICAgICAgICBsaXN0VGFiLmNsYXNzTGlzdC5hZGQoJ2Qtbm9uZScpOwogICAgICAgIHBsYW5uaW5nVGFiLmNsYXNzTGlzdC5yZW1vdmUoJ2Qtbm9uZScpOwogICAgICAgIGxpc3RCdG4uY2xhc3NMaXN0LnJlbW92ZSgnYWN0aXZlJyk7CiAgICAgICAgcGxhbm5pbmdCdG4uY2xhc3NMaXN0LmFkZCgnYWN0aXZlJyk7CiAgICAgICAgaWYgKGZpbHRlcnMpIGZpbHRlcnMuY2xhc3NMaXN0LmFkZCgnZC1ub25lJyk7CiAgICAgIH0KICAgIH0KCiAgICBkb2N1bWVudC5hZGRFdmVudExpc3RlbmVyKCdET01Db250ZW50TG9hZGVkJywgKCkgPT4gewogICAgICBjb25zdCB0YXJnZXRJbnB1dCA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCd0YXJnZXRfYW1vdW50Jyk7CiAgICAgIGNvbnN0IGN1cnJlbnRJbnB1dCA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCdjdXJyZW50X2Ftb3VudCcpOwogICAgICBjb25zdCBzdGFydElucHV0ID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ3N0YXJ0X2RhdGUnKTsKICAgICAgY29uc3QgdGFyZ2V0RGF0ZUlucHV0ID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ3RhcmdldF9kYXRlJyk7CgogICAgICBpZiAodGFyZ2V0SW5wdXQgJiYgY3VycmVudElucHV0KSB7CiAgICAgICAgZnVuY3Rpb24gdXBkYXRlQ2FsY3VsYXRvcigpIHsKICAgICAgICAgIGNvbnN0IHRhcmdldCA9IHBhcnNlRmxvYXQodGFyZ2V0SW5wdXQudmFsdWUpIHx8IDA7CiAgICAgICAgICBjb25zdCBjdXJyZW50ID0gcGFyc2VGbG9hdChjdXJyZW50SW5wdXQudmFsdWUpIHx8IDA7CiAgICAgICAgICBjb25zdCByZW1haW5pbmcgPSBNYXRoLm1heCh0YXJnZXQgLSBjdXJyZW50LCAwKTsKICAgICAgICAgIGNvbnN0IHByb2dyZXNzID0gdGFyZ2V0ID4gMCA/IE1hdGgubWluKChjdXJyZW50IC8gdGFyZ2V0KSAqIDEwMCwgMTAwKSA6IDA7CgogICAgICAgICAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ3ByZXYtdGFyZ2V0JykudGV4dENvbnRlbnQgPSBg4oK5JHt0YXJnZXQudG9Mb2NhbGVTdHJpbmcoJ2VuLUlOJywge21pbmltdW1GcmFjdGlvbkRpZ2l0czogMiwgbWF4aW11bUZyYWN0aW9uRGlnaXRzOiAyfSl9YDsKICAgICAgICAgIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCdwcmV2LWN1cnJlbnQnKS50ZXh0Q29udGVudCA9IGDigrkke2N1cnJlbnQudG9Mb2NhbGVTdHJpbmcoJ2VuLUlOJywge21pbmltdW1GcmFjdGlvbkRpZ2l0czogMiwgbWF4aW11bUZyYWN0aW9uRGlnaXRzOiAyfSl9YDsKICAgICAgICAgIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCdwcmV2LXJlbWFpbmluZycpLnRleHRDb250ZW50ID0gYOKCuSR7cmVtYWluaW5nLnRvTG9jYWxlU3RyaW5nKCdlbi1JTicsIHttaW5pbXVtRnJhY3Rpb25EaWdpdHM6IDIsIG1heGltdW1GcmFjdGlvbkRpZ2l0czogMn0pfWA7CiAgICAgICAgICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgncHJldi1wcm9ncmVzcycpLnRleHRDb250ZW50ID0gYCR7cHJvZ3Jlc3MudG9GaXhlZCgxKX0lYDsKICAgICAgICAgIAogICAgICAgICAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ3ByZXYtcHJvZ3Jlc3MtYmFyJykuc3R5bGUud2lkdGggPSBgJHtwcm9ncmVzc30lYDsKICAgICAgICAgIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCdwcmV2LXByb2dyZXNzLWxibCcpLnRleHRDb250ZW50ID0gYCR7cHJvZ3Jlc3MudG9GaXhlZCgwKX0lIGNvbXBsZXRlYDsKCiAgICAgICAgICAvLyBDYWxjdWxhdGUgbW9udGhzIGxlZnQKICAgICAgICAgIGxldCBtb250aHMgPSAwOwogICAgICAgICAgaWYgKHRhcmdldERhdGVJbnB1dC52YWx1ZSkgewogICAgICAgICAgICBjb25zdCBzdGFydCA9IHN0YXJ0SW5wdXQudmFsdWUgPyBuZXcgRGF0ZShzdGFydElucHV0LnZhbHVlKSA6IG5ldyBEYXRlKCk7CiAgICAgICAgICAgIGNvbnN0IGVuZCA9IG5ldyBEYXRlKHRhcmdldERhdGVJbnB1dC52YWx1ZSk7CiAgICAgICAgICAgIGNvbnN0IHRpbWVEaWZmID0gZW5kIC0gc3RhcnQ7CiAgICAgICAgICAgIGNvbnN0IGRheXMgPSB0aW1lRGlmZiAvICgxMDAwICogNjAgKiA2MCAqIDI0KTsKICAgICAgICAgICAgbW9udGhzID0gTWF0aC5tYXgoZGF5cyAvIDMwLjQ0LCAwKTsKICAgICAgICAgIH0KCiAgICAgICAgICBpZiAobW9udGhzID4gMCkgewogICAgICAgICAgICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgncHJldi1tb250aHMnKS50ZXh0Q29udGVudCA9IGAke21vbnRocy50b0ZpeGVkKDEpfSBtb250aHNgOwogICAgICAgICAgICBjb25zdCBtb250aGx5ID0gcmVtYWluaW5nIC8gbW9udGhzOwogICAgICAgICAgICBjb25zdCB3ZWVrbHkgPSBtb250aGx5IC8gNC4zMzsKICAgICAgICAgICAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ3ByZXYtbW9udGhseScpLnRleHRDb250ZW50ID0gYOKCuSR7bW9udGhseS50b0xvY2FsZVN0cmluZygnZW4tSU4nLCB7bWluaW11bUZyYWN0aW9uRGlnaXRzOiAyLCBtYXhpbXVtRnJhY3Rpb25EaWdpdHM6IDJ9KX1gOwogICAgICAgICAgICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgncHJldi13ZWVrbHknKS50ZXh0Q29udGVudCA9IGDigrkke3dlZWtseS50b0xvY2FsZVN0cmluZygnZW4tSU4nLCB7bWluaW11bUZyYWN0aW9uRGlnaXRzOiAyLCBtYXhpbXVtRnJhY3Rpb25EaWdpdHM6IDJ9KX1gOwogICAgICAgICAgfSBlbHNlIHsKICAgICAgICAgICAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ3ByZXYtbW9udGhzJykudGV4dENvbnRlbnQgPSAnTi9BJzsKICAgICAgICAgICAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ3ByZXYtbW9udGhseScpLnRleHRDb250ZW50ID0gJ+KCuTAuMDAnOwogICAgICAgICAgICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgncHJldi13ZWVrbHknKS50ZXh0Q29udGVudCA9ICfigrkwLjAwJzsKICAgICAgICAgIH0KICAgICAgICB9CgogICAgICAgIHRhcmdldElucHV0LmFkZEV2ZW50TGlzdGVuZXIoJ2lucHV0JywgdXBkYXRlQ2FsY3VsYXRvcik7CiAgICAgICAgY3VycmVudElucHV0LmFkZEV2ZW50TGlzdGVuZXIoJ2lucHV0JywgdXBkYXRlQ2FsY3VsYXRvcik7CiAgICAgICAgc3RhcnRJbnB1dC5hZGRFdmVudExpc3RlbmVyKCdpbnB1dCcsIHVwZGF0ZUNhbGN1bGF0b3IpOwogICAgICAgIHRhcmdldERhdGVJbnB1dC5hZGRFdmVudExpc3RlbmVyKCdpbnB1dCcsIHVwZGF0ZUNhbGN1bGF0b3IpOwoKICAgICAgICB1cGRhdGVDYWxjdWxhdG9yKCk7CiAgICAgIH0KICAgIH0pOwogIDwvc2NyaXB0Pgo8L2JvZHk+CjwvaHRtbD4=').decode('utf-8'),
    'goal_details.html': base64.b64decode('PCFkb2N0eXBlIGh0bWw+CjxodG1sIGxhbmc9ImVuIj4KPGhlYWQ+CiAgPG1ldGEgY2hhcnNldD0idXRmLTgiPgogIDxtZXRhIG5hbWU9InZpZXdwb3J0IiBjb250ZW50PSJ3aWR0aD1kZXZpY2Utd2lkdGgsIGluaXRpYWwtc2NhbGU9MSI+CiAgPHRpdGxlPkdvYWwgRGV0YWlscyDigJMgRmluU2lnaHQ8L3RpdGxlPgogIDxsaW5rIHJlbD0icHJlY29ubmVjdCIgaHJlZj0iaHR0cHM6Ly9mb250cy5nb29nbGVhcGlzLmNvbSI+CiAgPGxpbmsgcmVsPSJwcmVjb25uZWN0IiBocmVmPSJodHRwczovL2ZvbnRzLmdzdGF0aWMuY29tIiBjcm9zc29yaWdpbj4KICA8bGluayBocmVmPSJodHRwczovL2ZvbnRzLmdvb2dsZWFwaXMuY29tL2NzczI/ZmFtaWx5PUludGVyOndnaHRANDAwOzUwMDs2MDA7NzAwOzgwMCZkaXNwbGF5PXN3YXAiIHJlbD0ic3R5bGVzaGVldCI+CiAgPGxpbmsgaHJlZj0iaHR0cHM6Ly9jZG4uanNkZWxpdnIubmV0L25wbS9ib290c3RyYXBANS4zLjMvZGlzdC9jc3MvYm9vdHN0cmFwLm1pbi5jc3MiIHJlbD0ic3R5bGVzaGVldCI+CiAgPGxpbmsgcmVsPSJzdHlsZXNoZWV0IiBocmVmPSJodHRwczovL2Nkbi5qc2RlbGl2ci5uZXQvbnBtL2Jvb3RzdHJhcC1pY29uc0AxLjExLjMvZm9udC9ib290c3RyYXAtaWNvbnMuY3NzIj4KICA8bGluayByZWw9InN0eWxlc2hlZXQiIGhyZWY9Int7IHVybF9mb3IoJ3N0YXRpYycsIGZpbGVuYW1lPSdjc3MvZGFzaGJvYXJkLmNzcycpIH19Ij4KICA8bGluayByZWw9InN0eWxlc2hlZXQiIGhyZWY9Int7IHVybF9mb3IoJ3N0YXRpYycsIGZpbGVuYW1lPSdjc3MvcGFnZXMuY3NzJykgfX0iPgogIDxsaW5rIHJlbD0ic3R5bGVzaGVldCIgaHJlZj0ie3sgdXJsX2Zvcignc3RhdGljJywgZmlsZW5hbWU9J2Nzcy9jdXJzb3IuY3NzJykgfX0iPgogIDxzdHlsZT4KICAgIC5kZXRhaWxzLWdyaWQgewogICAgICBkaXNwbGF5OiBncmlkOwogICAgICBncmlkLXRlbXBsYXRlLWNvbHVtbnM6IDFmciAzNDBweDsKICAgICAgZ2FwOiAyNHB4OwogICAgfQogICAgQG1lZGlhIChtYXgtd2lkdGg6IDk5MS45OHB4KSB7CiAgICAgIC5kZXRhaWxzLWdyaWQgewogICAgICAgIGdyaWQtdGVtcGxhdGUtY29sdW1uczogMWZyOwogICAgICB9CiAgICB9CiAgICAubWlsZXN0b25lLXJvdyB7CiAgICAgIGRpc3BsYXk6IGZsZXg7CiAgICAgIGFsaWduLWl0ZW1zOiBjZW50ZXI7CiAgICAgIGdhcDogMTVweDsKICAgICAgcGFkZGluZzogMTJweCAwOwogICAgICBib3JkZXItYm90dG9tOiAxcHggc29saWQgI0YxRjVGOTsKICAgIH0KICAgIC5taWxlc3RvbmUtcm93Omxhc3QtY2hpbGQgewogICAgICBib3JkZXItYm90dG9tOiAwOwogICAgfQogICAgLm1pbGVzdG9uZS1kb3QgewogICAgICB3aWR0aDogMTRweDsKICAgICAgaGVpZ2h0OiAxNHB4OwogICAgICBib3JkZXItcmFkaXVzOiA1MCU7CiAgICAgIGJhY2tncm91bmQ6ICNDQkQ1RTE7CiAgICAgIGJvcmRlcjogM3B4IHNvbGlkIHZhcigtLXdoaXRlKTsKICAgICAgYm94LXNoYWRvdzogMCAwIDAgMnB4ICNDQkQ1RTE7CiAgICB9CiAgICAubWlsZXN0b25lLWRvdC5jb21wbGV0ZWQgewogICAgICBiYWNrZ3JvdW5kOiB2YXIoLS1zdWNjZXNzKTsKICAgICAgYm94LXNoYWRvdzogMCAwIDAgMnB4IHZhcigtLXN1Y2Nlc3MpOwogICAgfQogICAgLm1pbGVzdG9uZS1kb3QuaW4tcHJvZ3Jlc3MgewogICAgICBiYWNrZ3JvdW5kOiB2YXIoLS1wcmltYXJ5LWJsdWUpOwogICAgICBib3gtc2hhZG93OiAwIDAgMCAycHggdmFyKC0tcHJpbWFyeS1ibHVlKTsKICAgIH0KICAgIC5taWxlc3RvbmUtZG90Lm9uLWhvbGQgewogICAgICBiYWNrZ3JvdW5kOiB2YXIoLS1vcmFuZ2UpOwogICAgICBib3gtc2hhZG93OiAwIDAgMCAycHggdmFyKC0tb3JhbmdlKTsKICAgIH0KICA8L3N0eWxlPgo8L2hlYWQ+Cjxib2R5IGNsYXNzPSJ0aGVtZS1kYXNoIj4KPGRpdiBpZD0iY3Vyc29yLWRvdCI+PC9kaXY+CjxkaXYgaWQ9ImN1cnNvci1yaW5nIj48L2Rpdj4KCiAgPGJ1dHRvbiBjbGFzcz0iZmxvYXRpbmctaGFtYnVyZ2VyIiBpZD0ic2lkZWJhci10b2dnbGUtYnRuIiB0eXBlPSJidXR0b24iIHRpdGxlPSJUb2dnbGUgU2lkZWJhciBNZW51Ij4KICAgIDxpIGNsYXNzPSJiaSBiaS1saXN0Ij48L2k+CiAgPC9idXR0b24+CgogIDxkaXYgY2xhc3M9ImQtZmxleCI+CgogICAgPGFzaWRlIGNsYXNzPSJzaWRlYmFyIiBpZD0ic2lkZWJhciI+CiAgICAgIDxkaXYgY2xhc3M9ImxvZ28tcm93Ij4KICAgICAgICA8aW1nIHNyYz0ie3sgdXJsX2Zvcignc3RhdGljJywgZmlsZW5hbWU9J2ltYWdlcy9sb2dvLmpwZWcnKSB9fSIgYWx0PSJGaW5TaWdodCBMb2dvIiBjbGFzcz0iZGFzaC1uYXYtbG9nby1pbWciIHN0eWxlPSJ3aWR0aDo0MnB4O2hlaWdodDo0MnB4OyI+CiAgICAgICAgPGRpdiBjbGFzcz0ibG9nby10ZXh0Ij4KICAgICAgICAgIDxoMz5GaW5TaWdodDwvaDM+CiAgICAgICAgICA8c21hbGw+U21hcnQuIFNlY3VyZS4gU2ltcGxlLjwvc21hbGw+CiAgICAgICAgPC9kaXY+CiAgICAgIDwvZGl2PgogICAgICA8bmF2IGNsYXNzPSJuYXYtbGlzdCI+CiAgICAgICAgPGEgaHJlZj0ie3sgdXJsX2ZvcignZGFzaGJvYXJkJykgfX0iIGNsYXNzPSJuYXYtaXRlbSI+PGkgY2xhc3M9ImJpIGJpLWdyaWQiPjwvaT48c3Bhbj5EYXNoYm9hcmQ8L3NwYW4+PC9hPgogICAgICAgIDxhIGhyZWY9Int7IHVybF9mb3IoJ2FkZF9pbmNvbWUnKSB9fSIgY2xhc3M9Im5hdi1pdGVtIj48aSBjbGFzcz0iYmkgYmktY2FzaC1jb2luIj48L2k+PHNwYW4+SW5jb21lIE1hbmFnZW1lbnQ8L3NwYW4+PC9hPgogICAgICAgIDxhIGhyZWY9Int7IHVybF9mb3IoJ2FkZF9leHBlbnNlJykgfX0iIGNsYXNzPSJuYXYtaXRlbSI+PGkgY2xhc3M9ImJpIGJpLXdhbGxldDIiPjwvaT48c3Bhbj5FeHBlbnNlIE1hbmFnZW1lbnQ8L3NwYW4+PC9hPgogICAgICAgIDxhIGhyZWY9Int7IHVybF9mb3IoJ2FkZF9idWRnZXQnKSB9fSIgY2xhc3M9Im5hdi1pdGVtIj48aSBjbGFzcz0iYmkgYmktcGllLWNoYXJ0Ij48L2k+PHNwYW4+QnVkZ2V0IE1hbmFnZW1lbnQ8L3NwYW4+PC9hPgogICAgICAgIDxhIGhyZWY9Int7IHVybF9mb3IoJ2FkZF9pbnZlc3RtZW50JykgfX0iIGNsYXNzPSJuYXYtaXRlbSI+PGkgY2xhc3M9ImJpIGJpLWdyYXBoLXVwLWFycm93Ij48L2k+PHNwYW4+SW52ZXN0bWVudCBUcmFja2luZzwvc3Bhbj48L2E+CiAgICAgICAgPGEgaHJlZj0ie3sgdXJsX2ZvcignZ29hbHNfbGlzdCcpIH19IiBjbGFzcz0ibmF2LWl0ZW0gYWN0aXZlIj48aSBjbGFzcz0iYmkgYmktZmxhZyI+PC9pPjxzcGFuPkdvYWxzPC9zcGFuPjwvYT4KICAgICAgICA8YSBocmVmPSJ7eyB1cmxfZm9yKCdwcm9maWxlX3BhZ2UnKSB9fSIgY2xhc3M9Im5hdi1pdGVtIj48aSBjbGFzcz0iYmkgYmktcGVyc29uLWNpcmNsZSI+PC9pPjxzcGFuPlByb2ZpbGU8L3NwYW4+PC9hPgogICAgICA8L25hdj4KICAgICAgCiAgICAgIDxidXR0b24gY2xhc3M9InNpZGViYXItcmVzZXQtYnRuIiBpZD0ic2lkZWJhci1yZXNldC1idG4iIHR5cGU9ImJ1dHRvbiIgb25jbGljaz0iaWYoY29uZmlybSgnQXJlIHlvdSBzdXJlIHlvdSB3YW50IHRvIHJlc2V0IGFsbCBkYXRhIHRvIDA/JykpIHsgZmV0Y2goJy9hcGkvcmVzZXQtZGF0YScsIHttZXRob2Q6ICdQT1NUJ30pLnRoZW4oKCkgPT4geyB3aW5kb3cubG9jYXRpb24uaHJlZj0nL2Rhc2hib2FyZCc7IH0pOyB9IiB0aXRsZT0iUmVzZXQgYWxsIGRhdGEgdG8gMCI+CiAgICAgICAgPGkgY2xhc3M9ImJpIGJpLXRyYXNoIj48L2k+PHNwYW4+UmVzZXQgRGF0YTwvc3Bhbj4KICAgICAgPC9idXR0b24+CiAgICAgIDxhIGhyZWY9Int7IHVybF9mb3IoJ2xvZ291dCcpIH19IiBjbGFzcz0ic2lkZWJhci1sb2dvdXQtYnRuIiB0aXRsZT0iTG9nb3V0IGZyb20gc2Vzc2lvbiI+CiAgICAgICAgPGkgY2xhc3M9ImJpIGJpLWJveC1hcnJvdy1yaWdodCI+PC9pPjxzcGFuPkxvZ291dDwvc3Bhbj4KICAgICAgPC9hPgogICAgPC9hc2lkZT4KCiAgICA8bWFpbiBjbGFzcz0ibWFpbi1wYW5lbCI+CiAgICAgIDxkaXYgY2xhc3M9ImNvbnRlbnQtc3RhY2siPgoKICAgICAgICA8IS0tIFBhZ2UgSGVybyAtLT4KICAgICAgICA8ZGl2IGNsYXNzPSJwYWdlLWhlcm8gZ29hbHMtaGVybyI+CiAgICAgICAgICA8ZGl2IGNsYXNzPSJoZXJvLWxlZnQiPgogICAgICAgICAgICA8ZGl2IGNsYXNzPSJoZXJvLWljb24td3JhcCBkYXNoLWljb24td3JhcCIgc3R5bGU9ImJhY2tncm91bmQ6IHJnYmEoMjU1LDI1NSwyNTUsMC4yNSk7Ij4KICAgICAgICAgICAgICA8aSBjbGFzcz0iYmkgYmktZmxhZyB0ZXh0LXdoaXRlIj48L2k+CiAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICA8ZGl2PgogICAgICAgICAgICAgIDxoMSBjbGFzcz0iaGVyby10aXRsZSI+e3sgZ29hbC5nb2FsX25hbWUgfX08L2gxPgogICAgICAgICAgICAgIDxwIGNsYXNzPSJoZXJvLXN1YnRpdGxlIj5TbWFydCBUcmFjazogPHNwYW4gY2xhc3M9ImJhZGdlIHJvdW5kZWQtcGlsbCBiZy17eyBnb2FsLnNtYXJ0X3N0YXR1c19jbGFzcyB9fSI+e3sgZ29hbC5zbWFydF9zdGF0dXMgfX08L3NwYW4+IHwgUHJpb3JpdHk6IDxzcGFuIGNsYXNzPSJiYWRnZSByb3VuZGVkLXBpbGwgYmcte3sgZ29hbC5wcmlvcml0eV9jbGFzcyB9fSI+e3sgZ29hbC5wcmlvcml0eSB9fTwvc3Bhbj48L3A+CiAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgPC9kaXY+CiAgICAgICAgICA8ZGl2IGNsYXNzPSJoZXJvLXN0YXRzIGQtZmxleCBnYXAtMiI+CiAgICAgICAgICAgIDxidXR0b24gY2xhc3M9ImJ0biBidG4tc3VjY2VzcyIgc3R5bGU9ImJvcmRlci1yYWRpdXM6IDEycHg7IGZvbnQtd2VpZ2h0OiA2MDA7IiBkYXRhLWJzLXRvZ2dsZT0ibW9kYWwiIGRhdGEtYnMtdGFyZ2V0PSIjYWRkU2F2aW5nc01vZGFsIj48aSBjbGFzcz0iYmkgYmktcGlnZ3ktYmFuayBtZS0xIj48L2k+IEFkZCBTYXZpbmdzPC9idXR0b24+CiAgICAgICAgICAgIDxidXR0b24gY2xhc3M9ImJ0biBidG4tcHJpbWFyeSIgc3R5bGU9ImJvcmRlci1yYWRpdXM6IDEycHg7IGZvbnQtd2VpZ2h0OiA2MDA7IiBkYXRhLWJzLXRvZ2dsZT0ibW9kYWwiIGRhdGEtYnMtdGFyZ2V0PSIjYWRkTWlsZXN0b25lTW9kYWwiPjxpIGNsYXNzPSJiaSBiaS1wbHVzLWxnIG1lLTEiPjwvaT4gQWRkIE1pbGVzdG9uZTwvYnV0dG9uPgogICAgICAgICAgICA8YSBocmVmPSJ7eyB1cmxfZm9yKCdlZGl0X2dvYWwnLCBnb2FsX2lkPWdvYWwuaWQpIH19IiBjbGFzcz0iYnRuIGJ0bi1vdXRsaW5lLXNlY29uZGFyeSIgc3R5bGU9ImJvcmRlci1yYWRpdXM6IDEycHg7IGZvbnQtd2VpZ2h0OiA2MDA7Ij48aSBjbGFzcz0iYmkgYmktcGVuY2lsIG1lLTEiPjwvaT4gRWRpdDwvYT4KICAgICAgICAgIDwvZGl2PgogICAgICAgIDwvZGl2PgoKICAgICAgICA8IS0tIEZsYXNoIE1lc3NhZ2VzIC0tPgogICAgICAgIHslIHdpdGggbWVzc2FnZXMgPSBnZXRfZmxhc2hlZF9tZXNzYWdlcyh3aXRoX2NhdGVnb3JpZXM9dHJ1ZSkgJX0KICAgICAgICAgIHslIGlmIG1lc3NhZ2VzICV9CiAgICAgICAgICAgIHslIGZvciBjYXRlZ29yeSwgbWVzc2FnZSBpbiBtZXNzYWdlcyAlfQogICAgICAgICAgICAgIDxkaXYgY2xhc3M9InBhZ2UtYWxlcnQgYWxlcnQte3sgY2F0ZWdvcnkgfX0iPgogICAgICAgICAgICAgICAgPGkgY2xhc3M9ImJpIHslIGlmIGNhdGVnb3J5ID09ICdzdWNjZXNzJyAlfWJpLWNoZWNrLWNpcmNsZS1maWxseyUgZWxpZiBjYXRlZ29yeSA9PSAnZGFuZ2VyJyAlfWJpLWV4Y2xhbWF0aW9uLWNpcmNsZS1maWxseyUgZWxzZSAlfWJpLWluZm8tY2lyY2xlLWZpbGx7JSBlbmRpZiAlfSI+PC9pPgogICAgICAgICAgICAgICAgPHNwYW4+e3sgbWVzc2FnZSB9fTwvc3Bhbj4KICAgICAgICAgICAgICAgIDxidXR0b24gdHlwZT0iYnV0dG9uIiBjbGFzcz0iYWxlcnQtY2xvc2UtYnRuIiBvbmNsaWNrPSJ0aGlzLnBhcmVudEVsZW1lbnQucmVtb3ZlKCkiPjxpIGNsYXNzPSJiaSBiaS14LWxnIj48L2k+PC9idXR0b24+CiAgICAgICAgICAgICAgPC9kaXY+CiAgICAgICAgICAgIHslIGVuZGZvciAlfQogICAgICAgICAgeyUgZW5kaWYgJX0KICAgICAgICB7JSBlbmR3aXRoICV9CgogICAgICAgIDxkaXYgY2xhc3M9ImRldGFpbHMtZ3JpZCI+CiAgICAgICAgICA8IS0tIE1haW4gQ29udGVudCBQYW5lIC0tPgogICAgICAgICAgPGRpdiBjbGFzcz0iZC1mbGV4IGZsZXgtZGlyZWN0aW9uLWNvbHVtbiBnYXAtNCI+CiAgICAgICAgICAgIDwhLS0gUHJvZ3Jlc3MgQm94IC0tPgogICAgICAgICAgICA8ZGl2IGNsYXNzPSJwYW5lbCI+CiAgICAgICAgICAgICAgPGg0IHN0eWxlPSJmb250LXdlaWdodDogODAwOyBjb2xvcjogdmFyKC0tdGV4dC1kYXJrKTsgbWFyZ2luLWJvdHRvbTogMjBweDsiPk92ZXJhbGwgR29hbCBQcm9ncmVzczwvaDQ+CiAgICAgICAgICAgICAgPGRpdiBjbGFzcz0icm93IGctMyB0ZXh0LWNlbnRlciBtYi00Ij4KICAgICAgICAgICAgICAgIDxkaXYgY2xhc3M9ImNvbC1tZC0zIGNvbC02Ij4KICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0icC0zIGJnLWxpZ2h0IGJvcmRlciIgc3R5bGU9ImJvcmRlci1yYWRpdXM6IDEycHg7Ij4KICAgICAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJ0ZXh0LW11dGVkIiBzdHlsZT0iZm9udC1zaXplOiAwLjc2cmVtOyBmb250LXdlaWdodDogNjAwOyB0ZXh0LXRyYW5zZm9ybTogdXBwZXJjYXNlOyI+VGFyZ2V0PC9kaXY+CiAgICAgICAgICAgICAgICAgICAgPGRpdiBzdHlsZT0iZm9udC1zaXplOiAxLjE1cmVtOyBmb250LXdlaWdodDogODAwOyBtYXJnaW4tdG9wOiA0cHg7Ij7igrl7eyBnb2FsLnRhcmdldF9hbW91bnR8aW5yX2Zvcm1hdCB9fTwvZGl2PgogICAgICAgICAgICAgICAgICA8L2Rpdj4KICAgICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0iY29sLW1kLTMgY29sLTYiPgogICAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJwLTMgYmctbGlnaHQgYm9yZGVyIiBzdHlsZT0iYm9yZGVyLXJhZGl1czogMTJweDsiPgogICAgICAgICAgICAgICAgICAgIDxkaXYgY2xhc3M9InRleHQtbXV0ZWQiIHN0eWxlPSJmb250LXNpemU6IDAuNzZyZW07IGZvbnQtd2VpZ2h0OiA2MDA7IHRleHQtdHJhbnNmb3JtOiB1cHBlcmNhc2U7Ij5TYXZlZDwvZGl2PgogICAgICAgICAgICAgICAgICAgIDxkaXYgY2xhc3M9InRleHQtc3VjY2VzcyIgc3R5bGU9ImZvbnQtc2l6ZTogMS4xNXJlbTsgZm9udC13ZWlnaHQ6IDgwMDsgbWFyZ2luLXRvcDogNHB4OyI+4oK5e3sgZ29hbC5jdXJyZW50X2Ftb3VudHxpbnJfZm9ybWF0IH19PC9kaXY+CiAgICAgICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICAgICAgPC9kaXY+CiAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJjb2wtbWQtMyBjb2wtNiI+CiAgICAgICAgICAgICAgICAgIDxkaXYgY2xhc3M9InAtMyBiZy1saWdodCBib3JkZXIiIHN0eWxlPSJib3JkZXItcmFkaXVzOiAxMnB4OyI+CiAgICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0idGV4dC1tdXRlZCIgc3R5bGU9ImZvbnQtc2l6ZTogMC43NnJlbTsgZm9udC13ZWlnaHQ6IDYwMDsgdGV4dC10cmFuc2Zvcm06IHVwcGVyY2FzZTsiPlJlbWFpbmluZzwvZGl2PgogICAgICAgICAgICAgICAgICAgIDxkaXYgY2xhc3M9InRleHQtZGFuZ2VyIiBzdHlsZT0iZm9udC1zaXplOiAxLjE1cmVtOyBmb250LXdlaWdodDogODAwOyBtYXJnaW4tdG9wOiA0cHg7Ij7igrl7eyBnb2FsLnJlbWFpbmluZ19hbW91bnR8aW5yX2Zvcm1hdCB9fTwvZGl2PgogICAgICAgICAgICAgICAgICA8L2Rpdj4KICAgICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0iY29sLW1kLTMgY29sLTYiPgogICAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJwLTMgYmctbGlnaHQgYm9yZGVyIiBzdHlsZT0iYm9yZGVyLXJhZGl1czogMTJweDsiPgogICAgICAgICAgICAgICAgICAgIDxkaXYgY2xhc3M9InRleHQtbXV0ZWQiIHN0eWxlPSJmb250LXNpemU6IDAuNzZyZW07IGZvbnQtd2VpZ2h0OiA2MDA7IHRleHQtdHJhbnNmb3JtOiB1cHBlcmNhc2U7Ij5Qcm9ncmVzczwvZGl2PgogICAgICAgICAgICAgICAgICAgIDxkaXYgY2xhc3M9InRleHQtcHJpbWFyeSIgc3R5bGU9ImZvbnQtc2l6ZTogMS4xNXJlbTsgZm9udC13ZWlnaHQ6IDgwMDsgbWFyZ2luLXRvcDogNHB4OyI+e3sgZ29hbC5wcm9ncmVzc19wZXJjZW50YWdlIH19JTwvZGl2PgogICAgICAgICAgICAgICAgICA8L2Rpdj4KICAgICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICAgIDwvZGl2PgoKICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJwcm9ncmVzcyIgc3R5bGU9ImhlaWdodDogMTJweDsgYm9yZGVyLXJhZGl1czogOTk5cHg7IG1hcmdpbi1ib3R0b206IDhweDsiPgogICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0icHJvZ3Jlc3MtYmFyIGJnLXt7IGdvYWwuc21hcnRfc3RhdHVzX2NsYXNzIH19IiByb2xlPSJwcm9ncmVzc2JhciIgc3R5bGU9IndpZHRoOiB7eyBnb2FsLnByb2dyZXNzX3BlcmNlbnRhZ2UgfX0lIj48L2Rpdj4KICAgICAgICAgICAgICA8L2Rpdj4KICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJkLWZsZXgganVzdGlmeS1jb250ZW50LWJldHdlZW4gdGV4dC1tdXRlZCIgc3R5bGU9ImZvbnQtc2l6ZTogMC44cmVtOyBmb250LXdlaWdodDogNjAwOyI+CiAgICAgICAgICAgICAgICA8c3Bhbj5TdGFydDoge3sgZ29hbC5zdGFydF9kYXRlIG9yICdOL0EnIH19PC9zcGFuPgogICAgICAgICAgICAgICAgPHNwYW4+RGVhZGxpbmU6IHt7IGdvYWwudGFyZ2V0X2RhdGUgb3IgJ05vIERlYWRsaW5lJyB9fTwvc3Bhbj4KICAgICAgICAgICAgICA8L2Rpdj4KICAgICAgICAgICAgPC9kaXY+CgogICAgICAgICAgICA8IS0tIE1pbGVzdG9uZXMgUGFuZWwgLS0+CiAgICAgICAgICAgIDxkaXYgY2xhc3M9InBhbmVsIj4KICAgICAgICAgICAgICA8aDQgc3R5bGU9ImZvbnQtd2VpZ2h0OiA4MDA7IGNvbG9yOiB2YXIoLS10ZXh0LWRhcmspOyBtYXJnaW4tYm90dG9tOiAyMHB4OyI+TWlsZXN0b25lczwvaDQ+CiAgICAgICAgICAgICAgeyUgaWYgcGFydHMgJX0KICAgICAgICAgICAgICAgIDxkaXYgY2xhc3M9Im1pbGVzdG9uZXMtbGlzdCI+CiAgICAgICAgICAgICAgICAgIHslIGZvciBwYXJ0IGluIHBhcnRzICV9CiAgICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0ibWlsZXN0b25lLXJvdyBkLWZsZXgganVzdGlmeS1jb250ZW50LWJldHdlZW4gYWxpZ24taXRlbXMtY2VudGVyIj4KICAgICAgICAgICAgICAgICAgICAgIDxkaXYgY2xhc3M9ImQtZmxleCBhbGlnbi1pdGVtcy1jZW50ZXIgZ2FwLTMiPgogICAgICAgICAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJtaWxlc3RvbmUtZG90IHt7IHBhcnQuc3RhdHVzX2NsYXNzIH19Ij48L2Rpdj4KICAgICAgICAgICAgICAgICAgICAgICAgPGRpdj4KICAgICAgICAgICAgICAgICAgICAgICAgICA8ZGl2IHN0eWxlPSJmb250LXdlaWdodDogNzAwOyBjb2xvcjogdmFyKC0tdGV4dC1kYXJrKTsgZm9udC1zaXplOiAwLjk1cmVtOyI+e3sgcGFydC5wYXJ0X25hbWUgfX08L2Rpdj4KICAgICAgICAgICAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJ0ZXh0LW11dGVkIiBzdHlsZT0iZm9udC1zaXplOiAwLjc4cmVtOyI+CiAgICAgICAgICAgICAgICAgICAgICAgICAgICBUYXJnZXQ6IOKCuXt7IHBhcnQudGFyZ2V0X2Ftb3VudHxpbnJfZm9ybWF0IH19IHwgU2F2ZWQ6IOKCuXt7IHBhcnQuc2F2ZWRfYW1vdW50fGlucl9mb3JtYXQgfX0KICAgICAgICAgICAgICAgICAgICAgICAgICAgIHslIGlmIHBhcnQuZHVlX2RhdGUgJX0gfCBEdWU6IHt7IHBhcnQuZHVlX2RhdGUgfX17JSBlbmRpZiAlfQogICAgICAgICAgICAgICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICAgICAgICAgICAgICA8L2Rpdj4KICAgICAgICAgICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0iZC1mbGV4IGFsaWduLWl0ZW1zLWNlbnRlciBnYXAtMiI+CiAgICAgICAgICAgICAgICAgICAgICAgIDxzcGFuIGNsYXNzPSJiYWRnZSBiZy17eyBwYXJ0LnN0YXR1c19jbGFzcyB9fSI+e3sgcGFydC5zdGF0dXMgfX08L3NwYW4+CiAgICAgICAgICAgICAgICAgICAgICAgIDxidXR0b24gY2xhc3M9ImJ0biBidG4tc20gYnRuLWxpZ2h0IiBzdHlsZT0iYm9yZGVyLXJhZGl1czogOHB4OyBib3JkZXI6IDFweCBzb2xpZCAjRTJFOEYwOyIgb25jbGljaz0ib3BlblVwZGF0ZU1pbGVzdG9uZSh7eyBwYXJ0LmlkIH19LCAne3sgcGFydC5wYXJ0X25hbWV8cmVwbGFjZSgiJyIsIlxcJyIpIH19Jywge3sgcGFydC50YXJnZXRfYW1vdW50IH19LCB7eyBwYXJ0LnNhdmVkX2Ftb3VudCB9fSwgJ3t7IHBhcnQuc3RhdHVzIH19JykiPjxpIGNsYXNzPSJiaSBiaS1wZW5jaWwiPjwvaT48L2J1dHRvbj4KICAgICAgICAgICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICAgICAgICB7JSBlbmRmb3IgJX0KICAgICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICAgIHslIGVsc2UgJX0KICAgICAgICAgICAgICAgIDxkaXYgY2xhc3M9InRleHQtY2VudGVyIHB5LTQgdGV4dC1tdXRlZCI+CiAgICAgICAgICAgICAgICAgIDxpIGNsYXNzPSJiaSBiaS1saXN0LWNoZWNrIiBzdHlsZT0iZm9udC1zaXplOiAyLjVyZW07IG9wYWNpdHk6IDAuMzsiPjwvaT4KICAgICAgICAgICAgICAgICAgPHAgY2xhc3M9Im1iLTAgbXQtMiI+Tm8gbWlsZXN0b25lcyBzZXQuIERlZmluZSBtaWxlc3RvbmVzIHRvIGJyZWFrIGRvd24geW91ciBnb2FsITwvcD4KICAgICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICAgIHslIGVuZGlmICV9CiAgICAgICAgICAgIDwvZGl2PgoKICAgICAgICAgICAgPCEtLSBTYXZpbmdzIEhpc3RvcnkgUGFuZWwgLS0+CiAgICAgICAgICAgIDxkaXYgY2xhc3M9InBhbmVsIj4KICAgICAgICAgICAgICA8aDQgc3R5bGU9ImZvbnQtd2VpZ2h0OiA4MDA7IGNvbG9yOiB2YXIoLS10ZXh0LWRhcmspOyBtYXJnaW4tYm90dG9tOiAyMHB4OyI+U2F2aW5ncyBIaXN0b3J5PC9oND4KICAgICAgICAgICAgICB7JSBpZiBzYXZpbmdzICV9CiAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJ0YWJsZS1yZXNwb25zaXZlIj4KICAgICAgICAgICAgICAgICAgPHRhYmxlIGNsYXNzPSJ0YWJsZSB0YWJsZS1ob3ZlciBhbGlnbi1taWRkbGUiPgogICAgICAgICAgICAgICAgICAgIDx0aGVhZCBjbGFzcz0idGFibGUtbGlnaHQiPgogICAgICAgICAgICAgICAgICAgICAgPHRyPgogICAgICAgICAgICAgICAgICAgICAgICA8dGg+RGF0ZTwvdGg+CiAgICAgICAgICAgICAgICAgICAgICAgIDx0aD5Ob3RlPC90aD4KICAgICAgICAgICAgICAgICAgICAgICAgPHRoIGNsYXNzPSJ0ZXh0LWVuZCI+QW1vdW50PC90aD4KICAgICAgICAgICAgICAgICAgICAgIDwvdHI+CiAgICAgICAgICAgICAgICAgICAgPC90aGVhZD4KICAgICAgICAgICAgICAgICAgICA8dGJvZHk+CiAgICAgICAgICAgICAgICAgICAgICB7JSBmb3IgcyBpbiBzYXZpbmdzICV9CiAgICAgICAgICAgICAgICAgICAgICAgIDx0cj4KICAgICAgICAgICAgICAgICAgICAgICAgICA8dGQ+e3sgcy5zYXZpbmdfZGF0ZSB9fTwvdGQ+CiAgICAgICAgICAgICAgICAgICAgICAgICAgPHRkIGNsYXNzPSJ0ZXh0LW11dGVkIj57eyBzLm5vdGUgb3IgJ1NhdmluZ3MgZW50cnknIH19PC90ZD4KICAgICAgICAgICAgICAgICAgICAgICAgICA8dGQgY2xhc3M9InRleHQtZW5kIHRleHQtc3VjY2VzcyBmb250LXdlaWdodC1ib2xkIj7igrl7eyBzLmFtb3VudHxpbnJfZm9ybWF0IH19PC90ZD4KICAgICAgICAgICAgICAgICAgICAgICAgPC90cj4KICAgICAgICAgICAgICAgICAgICAgIHslIGVuZGZvciAlfQogICAgICAgICAgICAgICAgICAgIDwvdGJvZHk+CiAgICAgICAgICAgICAgICAgIDwvdGFibGU+CiAgICAgICAgICAgICAgICA8L2Rpdj4KICAgICAgICAgICAgICB7JSBlbHNlICV9CiAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJ0ZXh0LWNlbnRlciBweS00IHRleHQtbXV0ZWQiPgogICAgICAgICAgICAgICAgICA8aSBjbGFzcz0iYmkgYmktcGlnZ3ktYmFuayIgc3R5bGU9ImZvbnQtc2l6ZTogMi41cmVtOyBvcGFjaXR5OiAwLjM7Ij48L2k+CiAgICAgICAgICAgICAgICAgIDxwIGNsYXNzPSJtYi0wIG10LTIiPk5vIHNhdmluZ3MgcmVjb3JkZWQgeWV0LjwvcD4KICAgICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICAgIHslIGVuZGlmICV9CiAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgPC9kaXY+CgogICAgICAgICAgPCEtLSBTaWRlYmFyIFBhbmUgLS0+CiAgICAgICAgICA8ZGl2PgogICAgICAgICAgICA8IS0tIFRhcmdldCBTdW1tYXJ5IFNpZGViYXIgQm94IC0tPgogICAgICAgICAgICA8ZGl2IGNsYXNzPSJwYW5lbCBtYi00IiBzdHlsZT0iYm9yZGVyLWxlZnQ6IDRweCBzb2xpZCB2YXIoLS1wcmltYXJ5LWJsdWUpOyI+CiAgICAgICAgICAgICAgPGg1IHN0eWxlPSJmb250LXdlaWdodDogNzAwOyBjb2xvcjogdmFyKC0tdGV4dC1kYXJrKTsgbWFyZ2luLWJvdHRvbTogMTZweDsiPjxpIGNsYXNzPSJiaSBiaS1pbmZvLWNpcmNsZSB0ZXh0LXByaW1hcnkgbWUtMiI+PC9pPiBHb2FsIFN1bW1hcnk8L2g1PgogICAgICAgICAgICAgIDxkaXYgY2xhc3M9ImQtZmxleCBmbGV4LWNvbHVtbiBnYXAtMyIgc3R5bGU9ImZvbnQtc2l6ZTogMC44OHJlbTsiPgogICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0iZC1mbGV4IGp1c3RpZnktY29udGVudC1iZXR3ZWVuIj4KICAgICAgICAgICAgICAgICAgPHNwYW4gY2xhc3M9InRleHQtbXV0ZWQiPkdvYWwgVHlwZTwvc3Bhbj4KICAgICAgICAgICAgICAgICAgPHNwYW4gc3R5bGU9ImZvbnQtd2VpZ2h0OiA2MDA7Ij57eyBnb2FsLmdvYWxfdHlwZSBvciAnR2VuZXJhbCcgfX08L3NwYW4+CiAgICAgICAgICAgICAgICA8L2Rpdj4KICAgICAgICAgICAgICAgIDxkaXYgY2xhc3M9ImQtZmxleCBqdXN0aWZ5LWNvbnRlbnQtYmV0d2VlbiI+CiAgICAgICAgICAgICAgICAgIDxzcGFuIGNsYXNzPSJ0ZXh0LW11dGVkIj5DYXRlZ29yeTwvc3Bhbj4KICAgICAgICAgICAgICAgICAgPHNwYW4gc3R5bGU9ImZvbnQtd2VpZ2h0OiA2MDA7Ij57eyBnb2FsLmNhdGVnb3J5IH19PC9zcGFuPgogICAgICAgICAgICAgICAgPC9kaXY+CiAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJkLWZsZXgganVzdGlmeS1jb250ZW50LWJldHdlZW4iPgogICAgICAgICAgICAgICAgICA8c3BhbiBjbGFzcz0idGV4dC1tdXRlZCI+U3RhdHVzPC9zcGFuPgogICAgICAgICAgICAgICAgICA8c3BhbiBzdHlsZT0iZm9udC13ZWlnaHQ6IDYwMDsiPnt7IGdvYWwuc3RhdHVzIH19PC9zcGFuPgogICAgICAgICAgICAgICAgPC9kaXY+CiAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJkLWZsZXgganVzdGlmeS1jb250ZW50LWJldHdlZW4iPgogICAgICAgICAgICAgICAgICA8c3BhbiBjbGFzcz0idGV4dC1tdXRlZCI+VGltZSBMZWZ0PC9zcGFuPgogICAgICAgICAgICAgICAgICA8c3BhbiBzdHlsZT0iZm9udC13ZWlnaHQ6IDYwMDsiPnt7IGdvYWwubW9udGhzX2xlZnQgfX0gbW9udGhzICh7eyBnb2FsLmRheXNfbGVmdCBvciAnTi9BJyB9fSBkYXlzKTwvc3Bhbj4KICAgICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0iZC1mbGV4IGp1c3RpZnktY29udGVudC1iZXR3ZWVuIGJvcmRlci10b3AgcHQtMiI+CiAgICAgICAgICAgICAgICAgIDxzcGFuIGNsYXNzPSJ0ZXh0LW11dGVkIj5Nb250aGx5IFNhdmluZzwvc3Bhbj4KICAgICAgICAgICAgICAgICAgPHNwYW4gY2xhc3M9InRleHQtcHJpbWFyeSIgc3R5bGU9ImZvbnQtd2VpZ2h0OiA3MDA7Ij7igrl7eyBnb2FsLnJlcXVpcmVkX21vbnRobHlfc2F2aW5nfGlucl9mb3JtYXQgfX08L3NwYW4+CiAgICAgICAgICAgICAgICA8L2Rpdj4KICAgICAgICAgICAgICAgIDxkaXYgY2xhc3M9ImQtZmxleCBqdXN0aWZ5LWNvbnRlbnQtYmV0d2VlbiI+CiAgICAgICAgICAgICAgICAgIDxzcGFuIGNsYXNzPSJ0ZXh0LW11dGVkIj5XZWVrbHkgU2F2aW5nPC9zcGFuPgogICAgICAgICAgICAgICAgICA8c3BhbiBjbGFzcz0idGV4dC1wcmltYXJ5IiBzdHlsZT0iZm9udC13ZWlnaHQ6IDcwMDsiPuKCuXt7IGdvYWwucmVxdWlyZWRfd2Vla2x5X3NhdmluZ3xpbnJfZm9ybWF0IH19PC9zcGFuPgogICAgICAgICAgICAgICAgPC9kaXY+CiAgICAgICAgICAgICAgPC9kaXY+CiAgICAgICAgICAgIDwvZGl2PgoKICAgICAgICAgICAgPCEtLSBOb3RlcyBQYW5lbCAtLT4KICAgICAgICAgICAgeyUgaWYgZ29hbC5ub3RlcyAlfQogICAgICAgICAgICAgIDxkaXYgY2xhc3M9InBhbmVsIj4KICAgICAgICAgICAgICAgIDxoNSBzdHlsZT0iZm9udC13ZWlnaHQ6IDcwMDsgY29sb3I6IHZhcigtLXRleHQtZGFyayk7IG1hcmdpbi1ib3R0b206IDEycHg7Ij48aSBjbGFzcz0iYmkgYmktc3RpY2t5IHRleHQtd2FybmluZyBtZS0yIj48L2k+IE5vdGVzPC9oNT4KICAgICAgICAgICAgICAgIDxwIGNsYXNzPSJ0ZXh0LW11dGVkIG1iLTAiIHN0eWxlPSJmb250LXNpemU6IDAuODhyZW07IHdoaXRlLXNwYWNlOiBwcmUtd3JhcDsiPnt7IGdvYWwubm90ZXMgfX08L3A+CiAgICAgICAgICAgICAgPC9kaXY+CiAgICAgICAgICAgIHslIGVuZGlmICV9CiAgICAgICAgICA8L2Rpdj4KICAgICAgICA8L2Rpdj4KCiAgICAgIDwvZGl2PgoKICAgICAgPCEtLSBCdWRnZXQtR29hbC1FeHBlbnNlIEFjdGl2aXR5IEZlZWQgLS0+CiAgICAgIDxkaXYgY2xhc3M9InBhbmVsIG10LTQiIHN0eWxlPSJtYXJnaW4tdG9wOjI0cHghaW1wb3J0YW50OyI+CiAgICAgICAgPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjttYXJnaW4tYm90dG9tOjE4cHg7Ij4KICAgICAgICAgIDxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7Z2FwOjEwcHg7Ij4KICAgICAgICAgICAgPGRpdiBzdHlsZT0id2lkdGg6NHB4O2hlaWdodDoyMnB4O2JvcmRlci1yYWRpdXM6MnB4O2JhY2tncm91bmQ6bGluZWFyLWdyYWRpZW50KDE4MGRlZywjNjM2NkYxLCM4QjVDRjYpOyI+PC9kaXY+CiAgICAgICAgICAgIDxoNSBzdHlsZT0iZm9udC13ZWlnaHQ6ODAwO2NvbG9yOiMwRjE3MkE7bWFyZ2luOjA7Zm9udC1zaXplOjFyZW07Ij5CdWRnZXQgJiM4NTk0OyBHb2FsICYjODU5NDsgQWN0aXZpdHkgRmVlZDwvaDU+CiAgICAgICAgICA8L2Rpdj4KICAgICAgICAgIDxzcGFuIHN0eWxlPSJmb250LXNpemU6MC43NXJlbTtjb2xvcjojOTRBM0I4OyI+U2F2aW5ncyAmYW1wOyBsaW5rZWQgZXhwZW5zZSBhY3Rpdml0aWVzPC9zcGFuPgogICAgICAgIDwvZGl2PgogICAgICAgIDxkaXYgaWQ9ImdvYWwtYWN0aXZpdHktZmVlZCIgc3R5bGU9Im1pbi1oZWlnaHQ6ODBweDsiPgogICAgICAgICAgPGRpdiBzdHlsZT0idGV4dC1hbGlnbjpjZW50ZXI7cGFkZGluZzozMHB4O2NvbG9yOiM5NEEzQjg7Zm9udC1zaXplOjAuODVyZW07Ij4KICAgICAgICAgICAgPGkgY2xhc3M9ImJpIGJpLWhvdXJnbGFzcy1zcGxpdCIgc3R5bGU9ImZvbnQtc2l6ZToxLjVyZW07ZGlzcGxheTpibG9jazttYXJnaW4tYm90dG9tOjhweDsiPjwvaT4KICAgICAgICAgICAgTG9hZGluZyBhY3Rpdml0eSBmZWVkLi4uCiAgICAgICAgICA8L2Rpdj4KICAgICAgICA8L2Rpdj4KICAgICAgPC9kaXY+CgogICAgPC9tYWluPgogIDwvZGl2PgoKICA8IS0tIEFkZCBTYXZpbmdzIE1vZGFsIC0tPgogIDxkaXYgY2xhc3M9Im1vZGFsIGZhZGUiIGlkPSJhZGRTYXZpbmdzTW9kYWwiIHRhYmluZGV4PSItMSIgYXJpYS1oaWRkZW49InRydWUiPgogICAgPGRpdiBjbGFzcz0ibW9kYWwtZGlhbG9nIG1vZGFsLWRpYWxvZy1jZW50ZXJlZCI+CiAgICAgIDxkaXYgY2xhc3M9Im1vZGFsLWNvbnRlbnQiIHN0eWxlPSJib3JkZXItcmFkaXVzOiAxNnB4OyI+CiAgICAgICAgPGRpdiBjbGFzcz0ibW9kYWwtaGVhZGVyIGJvcmRlci0wIHBiLTAiPgogICAgICAgICAgPGg1IGNsYXNzPSJtb2RhbC10aXRsZSBmb250LXdlaWdodC1ib2xkIiBzdHlsZT0iZm9udC13ZWlnaHQ6IDgwMDsgY29sb3I6IHZhcigtLXRleHQtZGFyayk7Ij48aSBjbGFzcz0iYmkgYmktcGlnZ3ktYmFuayB0ZXh0LXN1Y2Nlc3MgbWUtMiI+PC9pPiBBZGQgU2F2aW5nczwvaDU+CiAgICAgICAgICA8YnV0dG9uIHR5cGU9ImJ1dHRvbiIgY2xhc3M9ImJ0bi1jbG9zZSIgZGF0YS1icy1kaXNtaXNzPSJtb2RhbCIgYXJpYS1sYWJlbD0iQ2xvc2UiPjwvYnV0dG9uPgogICAgICAgIDwvZGl2PgogICAgICAgIDxmb3JtIG1ldGhvZD0iUE9TVCIgYWN0aW9uPSJ7eyB1cmxfZm9yKCdhZGRfc2F2aW5ncycsIGdvYWxfaWQ9Z29hbC5pZCkgfX0iPgogICAgICAgICAgPGRpdiBjbGFzcz0ibW9kYWwtYm9keSI+CiAgICAgICAgICAgIDxkaXYgY2xhc3M9Im1iLTMiPgogICAgICAgICAgICAgIDxsYWJlbCBjbGFzcz0iZm9ybS1sYWJlbCIgc3R5bGU9ImZvbnQtd2VpZ2h0OiA2MDA7Ij5TYXZpbmdzIEFtb3VudCAoSU5SKSAqPC9sYWJlbD4KICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJpbnB1dC1ncm91cCI+CiAgICAgICAgICAgICAgICA8c3BhbiBjbGFzcz0iaW5wdXQtZ3JvdXAtdGV4dCI+4oK5PC9zcGFuPgogICAgICAgICAgICAgICAgPGlucHV0IHR5cGU9Im51bWJlciIgbmFtZT0iYW1vdW50IiBjbGFzcz0iZm9ybS1jb250cm9sIiBwbGFjZWhvbGRlcj0iMC4wMCIgc3RlcD0iMC4wMSIgbWluPSIwLjAxIiByZXF1aXJlZD4KICAgICAgICAgICAgICA8L2Rpdj4KICAgICAgICAgICAgPC9kaXY+CiAgICAgICAgICAgIDxkaXYgY2xhc3M9Im1iLTMiPgogICAgICAgICAgICAgIDxsYWJlbCBjbGFzcz0iZm9ybS1sYWJlbCIgc3R5bGU9ImZvbnQtd2VpZ2h0OiA2MDA7Ij5TYXZpbmcgRGF0ZSAqPC9sYWJlbD4KICAgICAgICAgICAgICA8aW5wdXQgdHlwZT0iZGF0ZSIgbmFtZT0ic2F2aW5nX2RhdGUiIGNsYXNzPSJmb3JtLWNvbnRyb2wiIHZhbHVlPSJ7eyB0b2RheSB9fSIgcmVxdWlyZWQ+CiAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICA8ZGl2IGNsYXNzPSJtYi0zIj4KICAgICAgICAgICAgICA8bGFiZWwgY2xhc3M9ImZvcm0tbGFiZWwiIHN0eWxlPSJmb250LXdlaWdodDogNjAwOyI+Tm90ZTwvbGFiZWw+CiAgICAgICAgICAgICAgPGlucHV0IHR5cGU9InRleHQiIG5hbWU9Im5vdGUiIGNsYXNzPSJmb3JtLWNvbnRyb2wiIHBsYWNlaG9sZGVyPSJlLmcuIE1hcmNoIGJvbnVzIHNhdmluZy4uLiI+CiAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgPC9kaXY+CiAgICAgICAgICA8ZGl2IGNsYXNzPSJtb2RhbC1mb290ZXIgYm9yZGVyLTAganVzdGlmeS1jb250ZW50LWVuZCBwYi00Ij4KICAgICAgICAgICAgPGJ1dHRvbiB0eXBlPSJidXR0b24iIGNsYXNzPSJidG4gYnRuLW91dGxpbmUtc2Vjb25kYXJ5IHB4LTQgbWUtMiIgc3R5bGU9ImJvcmRlci1yYWRpdXM6IDEwcHg7IiBkYXRhLWJzLWRpc21pc3M9Im1vZGFsIj5DYW5jZWw8L2J1dHRvbj4KICAgICAgICAgICAgPGJ1dHRvbiB0eXBlPSJzdWJtaXQiIGNsYXNzPSJidG4gYnRuLXN1Y2Nlc3MgcHgtNCIgc3R5bGU9ImJvcmRlci1yYWRpdXM6IDEwcHg7Ij5BZGQgU2F2aW5nczwvYnV0dG9uPgogICAgICAgICAgPC9kaXY+CiAgICAgICAgPC9mb3JtPgogICAgICA8L2Rpdj4KICAgIDwvZGl2PgogIDwvZGl2PgoKICA8IS0tIEFkZCBNaWxlc3RvbmUgTW9kYWwgLS0+CiAgPGRpdiBjbGFzcz0ibW9kYWwgZmFkZSIgaWQ9ImFkZE1pbGVzdG9uZU1vZGFsIiB0YWJpbmRleD0iLTEiIGFyaWEtaGlkZGVuPSJ0cnVlIj4KICAgIDxkaXYgY2xhc3M9Im1vZGFsLWRpYWxvZyBtb2RhbC1kaWFsb2ctY2VudGVyZWQiPgogICAgICA8ZGl2IGNsYXNzPSJtb2RhbC1jb250ZW50IiBzdHlsZT0iYm9yZGVyLXJhZGl1czogMTZweDsiPgogICAgICAgIDxkaXYgY2xhc3M9Im1vZGFsLWhlYWRlciBib3JkZXItMCBwYi0wIj4KICAgICAgICAgIDxoNSBjbGFzcz0ibW9kYWwtdGl0bGUgZm9udC13ZWlnaHQtYm9sZCIgc3R5bGU9ImZvbnQtd2VpZ2h0OiA4MDA7IGNvbG9yOiB2YXIoLS10ZXh0LWRhcmspOyI+PGkgY2xhc3M9ImJpIGJpLWZsYWctZmlsbCB0ZXh0LXByaW1hcnkgbWUtMiI+PC9pPiBBZGQgTWlsZXN0b25lPC9oNT4KICAgICAgICAgIDxidXR0b24gdHlwZT0iYnV0dG9uIiBjbGFzcz0iYnRuLWNsb3NlIiBkYXRhLWJzLWRpc21pc3M9Im1vZGFsIiBhcmlhLWxhYmVsPSJDbG9zZSI+PC9idXR0b24+CiAgICAgICAgPC9kaXY+CiAgICAgICAgPGZvcm0gbWV0aG9kPSJQT1NUIiBhY3Rpb249Int7IHVybF9mb3IoJ2FkZF9taWxlc3RvbmUnLCBnb2FsX2lkPWdvYWwuaWQpIH19Ij4KICAgICAgICAgIDxkaXYgY2xhc3M9Im1vZGFsLWJvZHkiPgogICAgICAgICAgICA8ZGl2IGNsYXNzPSJtYi0zIj4KICAgICAgICAgICAgICA8bGFiZWwgY2xhc3M9ImZvcm0tbGFiZWwiIHN0eWxlPSJmb250LXdlaWdodDogNjAwOyI+TWlsZXN0b25lIE5hbWUgKjwvbGFiZWw+CiAgICAgICAgICAgICAgPGlucHV0IHR5cGU9InRleHQiIG5hbWU9InBhcnRfbmFtZSIgY2xhc3M9ImZvcm0tY29udHJvbCIgcGxhY2Vob2xkZXI9ImUuZy4gU2F2ZSBmaXJzdCDigrkyMCwwMDAuLi4iIHJlcXVpcmVkPgogICAgICAgICAgICA8L2Rpdj4KICAgICAgICAgICAgPGRpdiBjbGFzcz0icm93IGctMyBtYi0zIj4KICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJjb2wtbWQtNiI+CiAgICAgICAgICAgICAgICA8bGFiZWwgY2xhc3M9ImZvcm0tbGFiZWwiIHN0eWxlPSJmb250LXdlaWdodDogNjAwOyI+VGFyZ2V0IEFtb3VudCAoSU5SKSAqPC9sYWJlbD4KICAgICAgICAgICAgICAgIDxpbnB1dCB0eXBlPSJudW1iZXIiIG5hbWU9InRhcmdldF9hbW91bnQiIGNsYXNzPSJmb3JtLWNvbnRyb2wiIHBsYWNlaG9sZGVyPSIwLjAwIiBzdGVwPSIwLjAxIiBtaW49IjEiIHJlcXVpcmVkPgogICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICAgIDxkaXYgY2xhc3M9ImNvbC1tZC02Ij4KICAgICAgICAgICAgICAgIDxsYWJlbCBjbGFzcz0iZm9ybS1sYWJlbCIgc3R5bGU9ImZvbnQtd2VpZ2h0OiA2MDA7Ij5BbW91bnQgU2F2ZWQ8L2xhYmVsPgogICAgICAgICAgICAgICAgPGlucHV0IHR5cGU9Im51bWJlciIgbmFtZT0ic2F2ZWRfYW1vdW50IiBjbGFzcz0iZm9ybS1jb250cm9sIiBwbGFjZWhvbGRlcj0iMC4wMCIgc3RlcD0iMC4wMSIgbWluPSIwIiB2YWx1ZT0iMCI+CiAgICAgICAgICAgICAgPC9kaXY+CiAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICA8ZGl2IGNsYXNzPSJyb3cgZy0zIj4KICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJjb2wtbWQtNiI+CiAgICAgICAgICAgICAgICA8bGFiZWwgY2xhc3M9ImZvcm0tbGFiZWwiIHN0eWxlPSJmb250LXdlaWdodDogNjAwOyI+RHVlIERhdGU8L2xhYmVsPgogICAgICAgICAgICAgICAgPGlucHV0IHR5cGU9ImRhdGUiIG5hbWU9ImR1ZV9kYXRlIiBjbGFzcz0iZm9ybS1jb250cm9sIj4KICAgICAgICAgICAgICA8L2Rpdj4KICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJjb2wtbWQtNiI+CiAgICAgICAgICAgICAgICA8bGFiZWwgY2xhc3M9ImZvcm0tbGFiZWwiIHN0eWxlPSJmb250LXdlaWdodDogNjAwOyI+U3RhdHVzPC9sYWJlbD4KICAgICAgICAgICAgICAgIDxzZWxlY3QgbmFtZT0icGFydF9zdGF0dXMiIGNsYXNzPSJmb3JtLXNlbGVjdCI+CiAgICAgICAgICAgICAgICAgIDxvcHRpb24gdmFsdWU9IlBlbmRpbmciPlBlbmRpbmc8L29wdGlvbj4KICAgICAgICAgICAgICAgICAgPG9wdGlvbiB2YWx1ZT0iSW4gUHJvZ3Jlc3MiPkluIFByb2dyZXNzPC9vcHRpb24+CiAgICAgICAgICAgICAgICAgIDxvcHRpb24gdmFsdWU9Ik9uIEhvbGQiPk9uIEhvbGQ8L29wdGlvbj4KICAgICAgICAgICAgICAgICAgPG9wdGlvbiB2YWx1ZT0iQ29tcGxldGVkIj5Db21wbGV0ZWQ8L29wdGlvbj4KICAgICAgICAgICAgICAgIDwvc2VsZWN0PgogICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICA8L2Rpdj4KICAgICAgICAgIDwvZGl2PgogICAgICAgICAgPGRpdiBjbGFzcz0ibW9kYWwtZm9vdGVyIGJvcmRlci0wIGp1c3RpZnktY29udGVudC1lbmQgcGItNCI+CiAgICAgICAgICAgIDxidXR0b24gdHlwZT0iYnV0dG9uIiBjbGFzcz0iYnRuIGJ0bi1vdXRsaW5lLXNlY29uZGFyeSBweC00IG1lLTIiIHN0eWxlPSJib3JkZXItcmFkaXVzOiAxMHB4OyIgZGF0YS1icy1kaXNtaXNzPSJtb2RhbCI+Q2FuY2VsPC9idXR0b24+CiAgICAgICAgICAgIDxidXR0b24gdHlwZT0ic3VibWl0IiBjbGFzcz0iYnRuIGJ0bi1wcmltYXJ5IHB4LTQiIHN0eWxlPSJib3JkZXItcmFkaXVzOiAxMHB4OyI+QWRkIE1pbGVzdG9uZTwvYnV0dG9uPgogICAgICAgICAgPC9kaXY+CiAgICAgICAgPC9mb3JtPgogICAgICA8L2Rpdj4KICAgIDwvZGl2PgogIDwvZGl2PgoKICA8IS0tIFVwZGF0ZSBNaWxlc3RvbmUgTW9kYWwgLS0+CiAgPGRpdiBjbGFzcz0ibW9kYWwgZmFkZSIgaWQ9InVwZGF0ZU1pbGVzdG9uZU1vZGFsIiB0YWJpbmRleD0iLTEiIGFyaWEtaGlkZGVuPSJ0cnVlIj4KICAgIDxkaXYgY2xhc3M9Im1vZGFsLWRpYWxvZyBtb2RhbC1kaWFsb2ctY2VudGVyZWQiPgogICAgICA8ZGl2IGNsYXNzPSJtb2RhbC1jb250ZW50IiBzdHlsZT0iYm9yZGVyLXJhZGl1czogMTZweDsiPgogICAgICAgIDxkaXYgY2xhc3M9Im1vZGFsLWhlYWRlciBib3JkZXItMCBwYi0wIj4KICAgICAgICAgIDxoNSBjbGFzcz0ibW9kYWwtdGl0bGUgZm9udC13ZWlnaHQtYm9sZCIgaWQ9InVwZGF0ZU1pbGVzdG9uZVRpdGxlIiBzdHlsZT0iZm9udC13ZWlnaHQ6IDgwMDsgY29sb3I6IHZhcigtLXRleHQtZGFyayk7Ij5VcGRhdGUgTWlsZXN0b25lPC9oNT4KICAgICAgICAgIDxidXR0b24gdHlwZT0iYnV0dG9uIiBjbGFzcz0iYnRuLWNsb3NlIiBkYXRhLWJzLWRpc21pc3M9Im1vZGFsIiBhcmlhLWxhYmVsPSJDbG9zZSI+PC9idXR0b24+CiAgICAgICAgPC9kaXY+CiAgICAgICAgPGZvcm0gbWV0aG9kPSJQT1NUIiBpZD0idXBkYXRlTWlsZXN0b25lRm9ybSI+CiAgICAgICAgICA8ZGl2IGNsYXNzPSJtb2RhbC1ib2R5Ij4KICAgICAgICAgICAgPGRpdiBjbGFzcz0ibWItMyI+CiAgICAgICAgICAgICAgPGxhYmVsIGNsYXNzPSJmb3JtLWxhYmVsIiBzdHlsZT0iZm9udC13ZWlnaHQ6IDYwMDsiPkFtb3VudCBTYXZlZCAoSU5SKTwvbGFiZWw+CiAgICAgICAgICAgICAgPGlucHV0IHR5cGU9Im51bWJlciIgaWQ9InVtX3NhdmVkIiBuYW1lPSJzYXZlZF9hbW91bnQiIGNsYXNzPSJmb3JtLWNvbnRyb2wiIHBsYWNlaG9sZGVyPSIwLjAwIiBzdGVwPSIwLjAxIiBtaW49IjAiPgogICAgICAgICAgICAgIDxkaXYgY2xhc3M9ImZvcm0tdGV4dCIgaWQ9InVtX3RhcmdldF9oaW50Ij48L2Rpdj4KICAgICAgICAgICAgPC9kaXY+CiAgICAgICAgICAgIDxkaXYgY2xhc3M9Im1iLTMiPgogICAgICAgICAgICAgIDxsYWJlbCBjbGFzcz0iZm9ybS1sYWJlbCIgc3R5bGU9ImZvbnQtd2VpZ2h0OiA2MDA7Ij5TdGF0dXM8L2xhYmVsPgogICAgICAgICAgICAgIDxzZWxlY3QgaWQ9InVtX3N0YXR1cyIgbmFtZT0icGFydF9zdGF0dXMiIGNsYXNzPSJmb3JtLXNlbGVjdCI+CiAgICAgICAgICAgICAgICA8b3B0aW9uIHZhbHVlPSJQZW5kaW5nIj5QZW5kaW5nPC9vcHRpb24+CiAgICAgICAgICAgICAgICA8b3B0aW9uIHZhbHVlPSJJbiBQcm9ncmVzcyI+SW4gUHJvZ3Jlc3M8L29wdGlvbj4KICAgICAgICAgICAgICAgIDxvcHRpb24gdmFsdWU9Ik9uIEhvbGQiPk9uIEhvbGQ8L29wdGlvbj4KICAgICAgICAgICAgICAgIDxvcHRpb24gdmFsdWU9IkNvbXBsZXRlZCI+Q29tcGxldGVkPC9vcHRpb24+CiAgICAgICAgICAgICAgPC9zZWxlY3Q+CiAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgPC9kaXY+CiAgICAgICAgICA8ZGl2IGNsYXNzPSJtb2RhbC1mb290ZXIgYm9yZGVyLTAganVzdGlmeS1jb250ZW50LWVuZCBwYi00Ij4KICAgICAgICAgICAgPGJ1dHRvbiB0eXBlPSJidXR0b24iIGNsYXNzPSJidG4gYnRuLW91dGxpbmUtc2Vjb25kYXJ5IHB4LTQgbWUtMiIgc3R5bGU9ImJvcmRlci1yYWRpdXM6IDEwcHg7IiBkYXRhLWJzLWRpc21pc3M9Im1vZGFsIj5DYW5jZWw8L2J1dHRvbj4KICAgICAgICAgICAgPGJ1dHRvbiB0eXBlPSJzdWJtaXQiIGNsYXNzPSJidG4gYnRuLXByaW1hcnkgcHgtNCIgc3R5bGU9ImJvcmRlci1yYWRpdXM6IDEwcHg7Ij5TYXZlIENoYW5nZXM8L2J1dHRvbj4KICAgICAgICAgIDwvZGl2PgogICAgICAgIDwvZm9ybT4KICAgICAgPC9kaXY+CiAgICA8L2Rpdj4KICA8L2Rpdj4KCiAgPHNjcmlwdCBzcmM9Imh0dHBzOi8vY2RuLmpzZGVsaXZyLm5ldC9ucG0vYm9vdHN0cmFwQDUuMy4zL2Rpc3QvanMvYm9vdHN0cmFwLmJ1bmRsZS5taW4uanMiPjwvc2NyaXB0PgogIDxzY3JpcHQgc3JjPSJ7eyB1cmxfZm9yKCdzdGF0aWMnLCBmaWxlbmFtZT0nanMvc2NyaXB0LmpzJykgfX0iIGRlZmVyPjwvc2NyaXB0PgogIDxzY3JpcHQgc3JjPSJ7eyB1cmxfZm9yKCdzdGF0aWMnLCBmaWxlbmFtZT0nanMvY3Vyc29yLmpzJykgfX0iPjwvc2NyaXB0PgogIDxzY3JpcHQ+CiAgICBmdW5jdGlvbiBvcGVuVXBkYXRlTWlsZXN0b25lKHBhcnRJZCwgbmFtZSwgdGFyZ2V0LCBzYXZlZCwgc3RhdHVzKSB7CiAgICAgIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCd1cGRhdGVNaWxlc3RvbmVUaXRsZScpLnRleHRDb250ZW50ID0gYFVwZGF0ZTogJHtuYW1lfWA7CiAgICAgIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCd1cGRhdGVNaWxlc3RvbmVGb3JtJykuYWN0aW9uID0gYC9nb2Fscy97eyBnb2FsLmlkIH19L21pbGVzdG9uZXMvJHtwYXJ0SWR9L3VwZGF0ZWA7CiAgICAgIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCd1bV9zYXZlZCcpLnZhbHVlID0gc2F2ZWQ7CiAgICAgIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCd1bV90YXJnZXRfaGludCcpLnRleHRDb250ZW50ID0gYFRhcmdldDog4oK5JHt0YXJnZXQudG9Mb2NhbGVTdHJpbmcodW5kZWZpbmVkLCB7bWluaW11bUZyYWN0aW9uRGlnaXRzOiAyfSl9YDsKICAgICAgY29uc3Qgc2VsID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ3VtX3N0YXR1cycpOwogICAgICBmb3IgKGxldCBvcHQgb2Ygc2VsLm9wdGlvbnMpIHsKICAgICAgICBvcHQuc2VsZWN0ZWQgPSAob3B0LnZhbHVlID09PSBzdGF0dXMpOwogICAgICB9CiAgICAgIGNvbnN0IG1vZGFsID0gbmV3IGJvb3RzdHJhcC5Nb2RhbChkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgndXBkYXRlTWlsZXN0b25lTW9kYWwnKSk7CiAgICAgIG1vZGFsLnNob3coKTsKICAgIH0KCiAgICAvLyBMb2FkIEFjdGl2aXR5IEZlZWQKICAgIChmdW5jdGlvbigpIHsKICAgICAgdmFyIGdvYWxJZCA9IHt7IGdvYWwuaWQgfX07CiAgICAgIHZhciBmZWVkID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ2dvYWwtYWN0aXZpdHktZmVlZCcpOwogICAgICBpZiAoIWZlZWQpIHJldHVybjsKICAgICAgZmV0Y2goJy9hcGkvZ29hbC8nICsgZ29hbElkICsgJy9hY3Rpdml0eScpCiAgICAgICAgLnRoZW4oZnVuY3Rpb24ocil7IHJldHVybiByLm9rID8gci5qc29uKCkgOiB7YWN0aXZpdGllczpbXX07IH0pCiAgICAgICAgLnRoZW4oZnVuY3Rpb24oZGF0YSkgewogICAgICAgICAgdmFyIGFjdHMgPSBkYXRhLmFjdGl2aXRpZXMgfHwgW107CiAgICAgICAgICBpZiAoYWN0cy5sZW5ndGggPT09IDApIHsKICAgICAgICAgICAgZmVlZC5pbm5lckhUTUwgPSAnPGRpdiBzdHlsZT0idGV4dC1hbGlnbjpjZW50ZXI7cGFkZGluZzozMHB4O2NvbG9yOiM5NEEzQjg7Zm9udC1zaXplOjAuODVyZW07Ij48aSBjbGFzcz0iYmkgYmktY2xvY2staGlzdG9yeSIgc3R5bGU9ImZvbnQtc2l6ZToxLjVyZW07ZGlzcGxheTpibG9jazttYXJnaW4tYm90dG9tOjhweDsiPjwvaT5ObyBhY3Rpdml0aWVzIHlldC4gQWRkIHNhdmluZ3Mgb3IgbGluayBhIGJ1ZGdldCB0byB0aGlzIGdvYWwuPC9kaXY+JzsKICAgICAgICAgICAgcmV0dXJuOwogICAgICAgICAgfQogICAgICAgICAgdmFyIGh0bWwgPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2ZsZXgtZGlyZWN0aW9uOmNvbHVtbjtnYXA6MTJweDsiPic7CiAgICAgICAgICBhY3RzLmZvckVhY2goZnVuY3Rpb24oYSkgewogICAgICAgICAgICB2YXIgaXNTYXZpbmdzID0gYS50eXBlID09PSAnc2F2aW5ncyc7CiAgICAgICAgICAgIHZhciBjb2xvciA9IGlzU2F2aW5ncyA/ICcjMTBCOTgxJyA6ICcjRUY0NDQ0JzsKICAgICAgICAgICAgdmFyIGljb24gID0gaXNTYXZpbmdzID8gJ2JpLXBpZ2d5LWJhbmstZmlsbCcgOiAnYmktY2FydDMnOwogICAgICAgICAgICB2YXIgbGFiZWwgPSBpc1NhdmluZ3MgPyAnU2F2aW5ncyBBZGRlZCcgOiAnRXhwZW5zZTogJyArIGEubm90ZXM7CiAgICAgICAgICAgIHZhciBzaWduICA9IGlzU2F2aW5ncyA/ICcrJyA6ICctJzsKICAgICAgICAgICAgaHRtbCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtnYXA6MTRweDtwYWRkaW5nOjEycHggMTZweDtiYWNrZ3JvdW5kOiNGOEZBRkM7Ym9yZGVyLXJhZGl1czoxMnB4O2JvcmRlcjoxcHggc29saWQgI0YxRjVGOTsiPicgKwogICAgICAgICAgICAgICc8ZGl2IHN0eWxlPSJ3aWR0aDozNnB4O2hlaWdodDozNnB4O2JvcmRlci1yYWRpdXM6NTAlO2JhY2tncm91bmQ6JyArIGNvbG9yICsgJzFBO2Rpc3BsYXk6Z3JpZDtwbGFjZS1pdGVtczpjZW50ZXI7ZmxleC1zaHJpbms6MDsiPicgKwogICAgICAgICAgICAgICc8aSBjbGFzcz0iYmkgJyArIGljb24gKyAnIiBzdHlsZT0iY29sb3I6JyArIGNvbG9yICsgJztmb250LXNpemU6MXJlbTsiPjwvaT48L2Rpdj4nICsKICAgICAgICAgICAgICAnPGRpdiBzdHlsZT0iZmxleDoxOyI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjAuODNyZW07Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOiMwRjE3MkE7Ij4nICsgbGFiZWwgKyAnPC9kaXY+JyArCiAgICAgICAgICAgICAgJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZTowLjczcmVtO2NvbG9yOiM5NEEzQjg7bWFyZ2luLXRvcDoycHg7Ij4nICsgYS5kYXRlICsgJzwvZGl2PjwvZGl2PicgKwogICAgICAgICAgICAgICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MC45cmVtO2ZvbnQtd2VpZ2h0OjgwMDtjb2xvcjonICsgY29sb3IgKyAnOyI+JyArIHNpZ24gKyAnJiM4Mzc3OycgKyBwYXJzZUZsb2F0KGEuYW1vdW50KS50b0xvY2FsZVN0cmluZygnZW4tSU4nKSArICc8L2Rpdj48L2Rpdj4nOwogICAgICAgICAgfSk7CiAgICAgICAgICBodG1sICs9ICc8L2Rpdj4nOwogICAgICAgICAgZmVlZC5pbm5lckhUTUwgPSBodG1sOwogICAgICAgIH0pCiAgICAgICAgLmNhdGNoKGZ1bmN0aW9uKCkgewogICAgICAgICAgZmVlZC5pbm5lckhUTUwgPSAnPGRpdiBzdHlsZT0idGV4dC1hbGlnbjpjZW50ZXI7cGFkZGluZzoyMHB4O2NvbG9yOiM5NEEzQjg7Zm9udC1zaXplOjAuODJyZW07Ij5Db3VsZCBub3QgbG9hZCBhY3Rpdml0eSBmZWVkLjwvZGl2Pic7CiAgICAgICAgfSk7CiAgICB9KSgpOwogIDwvc2NyaXB0Pgo8L2JvZHk+CjwvaHRtbD4K').decode('utf-8'),
    'goal_planning.html': base64.b64decode('PCFkb2N0eXBlIGh0bWw+CjxodG1sIGxhbmc9ImVuIj4KPGhlYWQ+CiAgPG1ldGEgY2hhcnNldD0idXRmLTgiPgogIDxtZXRhIG5hbWU9InZpZXdwb3J0IiBjb250ZW50PSJ3aWR0aD1kZXZpY2Utd2lkdGgsIGluaXRpYWwtc2NhbGU9MSI+CiAgPHRpdGxlPnslIGlmIGVkaXQgJX1FZGl0IEdvYWx7JSBlbHNlICV9R29hbCBQbGFubmluZ3slIGVuZGlmICV9IOKAkyBGaW5TaWdodDwvdGl0bGU+CiAgPGxpbmsgcmVsPSJwcmVjb25uZWN0IiBocmVmPSJodHRwczovL2ZvbnRzLmdvb2dsZWFwaXMuY29tIj4KICA8bGluayByZWw9InByZWNvbm5lY3QiIGhyZWY9Imh0dHBzOi8vZm9udHMuZ3N0YXRpYy5jb20iIGNyb3Nzb3JpZ2luPgogIDxsaW5rIGhyZWY9Imh0dHBzOi8vZm9udHMuZ29vZ2xlYXBpcy5jb20vY3NzMj9mYW1pbHk9SW50ZXI6d2dodEA0MDA7NTAwOzYwMDs3MDA7ODAwJmRpc3BsYXk9c3dhcCIgcmVsPSJzdHlsZXNoZWV0Ij4KICA8bGluayBocmVmPSJodHRwczovL2Nkbi5qc2RlbGl2ci5uZXQvbnBtL2Jvb3RzdHJhcEA1LjMuMy9kaXN0L2Nzcy9ib290c3RyYXAubWluLmNzcyIgcmVsPSJzdHlsZXNoZWV0Ij4KICA8bGluayByZWw9InN0eWxlc2hlZXQiIGhyZWY9Imh0dHBzOi8vY2RuLmpzZGVsaXZyLm5ldC9ucG0vYm9vdHN0cmFwLWljb25zQDEuMTEuMy9mb250L2Jvb3RzdHJhcC1pY29ucy5jc3MiPgogIDxsaW5rIHJlbD0ic3R5bGVzaGVldCIgaHJlZj0ie3sgdXJsX2Zvcignc3RhdGljJywgZmlsZW5hbWU9J2Nzcy9kYXNoYm9hcmQuY3NzJykgfX0iPgogIDxsaW5rIHJlbD0ic3R5bGVzaGVldCIgaHJlZj0ie3sgdXJsX2Zvcignc3RhdGljJywgZmlsZW5hbWU9J2Nzcy9wYWdlcy5jc3MnKSB9fSI+CiAgPGxpbmsgcmVsPSJzdHlsZXNoZWV0IiBocmVmPSJ7eyB1cmxfZm9yKCdzdGF0aWMnLCBmaWxlbmFtZT0nY3NzL2N1cnNvci5jc3MnKSB9fSI+CiAgPHN0eWxlPgogICAgLmZvcm0tcGFuZWwgewogICAgICBib3JkZXItdG9wOiA0cHggc29saWQgIzFFMjkzQjsKICAgIH0KICAgIC5wcmV2aWV3LXBhbmVsIHsKICAgICAgYmFja2dyb3VuZDogdmFyKC0td2hpdGUpOwogICAgICBib3JkZXItcmFkaXVzOiB2YXIoLS1ib3JkZXItcmFkaXVzLWNhcmQpOwogICAgICBwYWRkaW5nOiAyNHB4OwogICAgICBib3gtc2hhZG93OiB2YXIoLS1zaGFkb3cpOwogICAgICBwb3NpdGlvbjogc3RpY2t5OwogICAgICB0b3A6IDIwcHg7CiAgICB9CiAgICAucHJldmlldy10aXRsZSB7CiAgICAgIGZvbnQtc2l6ZTogMS4xcmVtOwogICAgICBmb250LXdlaWdodDogNzAwOwogICAgICBjb2xvcjogdmFyKC0tdGV4dC1kYXJrKTsKICAgICAgbWFyZ2luLWJvdHRvbTogMThweDsKICAgICAgZGlzcGxheTogZmxleDsKICAgICAgYWxpZ24taXRlbXM6IGNlbnRlcjsKICAgICAgZ2FwOiA4cHg7CiAgICB9CiAgICAucHJldmlldy1yb3cgewogICAgICBkaXNwbGF5OiBmbGV4OwogICAgICBqdXN0aWZ5LWNvbnRlbnQ6IHNwYWNlLWJldHdlZW47CiAgICAgIHBhZGRpbmc6IDEwcHggMDsKICAgICAgYm9yZGVyLWJvdHRvbTogMXB4IHNvbGlkICNGMUY1Rjk7CiAgICAgIGZvbnQtc2l6ZTogMC45cmVtOwogICAgfQogICAgLnByZXZpZXctcm93Omxhc3QtY2hpbGQgewogICAgICBib3JkZXItYm90dG9tOiAwOwogICAgfQogICAgLnByZXZpZXctbGFiZWwgewogICAgICBjb2xvcjogdmFyKC0tdGV4dC1tdXRlZCk7CiAgICAgIGZvbnQtd2VpZ2h0OiA1MDA7CiAgICB9CiAgICAucHJldmlldy12YWx1ZSB7CiAgICAgIGZvbnQtd2VpZ2h0OiA3MDA7CiAgICAgIGNvbG9yOiB2YXIoLS10ZXh0LWRhcmspOwogICAgfQogIDwvc3R5bGU+CjwvaGVhZD4KPGJvZHkgY2xhc3M9InRoZW1lLWRhc2giPgo8ZGl2IGlkPSJjdXJzb3ItZG90Ij48L2Rpdj4KPGRpdiBpZD0iY3Vyc29yLXJpbmciPjwvZGl2PgoKPCEtLSBQcm9maWxlIENoaXAgLS0+CjxhIGhyZWY9Int7IHVybF9mb3IoJ3Byb2ZpbGVfcGFnZScpIH19IiBjbGFzcz0icHJvZmlsZS1jaGlwLWdsb2JhbCIgdGl0bGU9IlZpZXcgUHJvZmlsZSI+CiAgPGRpdiBjbGFzcz0icHJvZmlsZS1jaGlwLWF2YXRhciI+e3sgdXNlcl9uYW1lWzBdfHVwcGVyIGlmIHVzZXJfbmFtZSBlbHNlICdBJyB9fTwvZGl2PgogIDxkaXYgY2xhc3M9InByb2ZpbGUtY2hpcC1pbmZvIj4KICAgIDxzcGFuIGNsYXNzPSJwcm9maWxlLWNoaXAtbmFtZSI+e3sgdXNlcl9uYW1lIGlmIHVzZXJfbmFtZSBlbHNlICdBcmp1biBNZWh0YScgfX08L3NwYW4+CiAgPC9kaXY+CjwvYT4KCiAgPGJ1dHRvbiBjbGFzcz0iZmxvYXRpbmctaGFtYnVyZ2VyIiBpZD0ic2lkZWJhci10b2dnbGUtYnRuIiB0eXBlPSJidXR0b24iIHRpdGxlPSJUb2dnbGUgU2lkZWJhciBNZW51Ij4KICAgIDxpIGNsYXNzPSJiaSBiaS1saXN0Ij48L2k+CiAgPC9idXR0b24+CgogIDxkaXYgY2xhc3M9ImQtZmxleCI+CgogICAgPGFzaWRlIGNsYXNzPSJzaWRlYmFyIiBpZD0ic2lkZWJhciI+CiAgICAgIDxkaXYgY2xhc3M9ImxvZ28tcm93Ij4KICAgICAgICA8aW1nIHNyYz0ie3sgdXJsX2Zvcignc3RhdGljJywgZmlsZW5hbWU9J2ltYWdlcy9sb2dvLmpwZWcnKSB9fSIgYWx0PSJGaW5TaWdodCBMb2dvIiBjbGFzcz0iZGFzaC1uYXYtbG9nby1pbWciIHN0eWxlPSJ3aWR0aDo0MnB4O2hlaWdodDo0MnB4OyI+CiAgICAgICAgPGRpdiBjbGFzcz0ibG9nby10ZXh0Ij4KICAgICAgICAgIDxoMz5GaW5TaWdodDwvaDM+CiAgICAgICAgICA8c21hbGw+U21hcnQuIFNlY3VyZS4gU2ltcGxlLjwvc21hbGw+CiAgICAgICAgPC9kaXY+CiAgICAgIDwvZGl2PgogICAgICA8bmF2IGNsYXNzPSJuYXYtbGlzdCI+CiAgICAgICAgPGEgaHJlZj0ie3sgdXJsX2ZvcignZGFzaGJvYXJkJykgfX0iIGNsYXNzPSJuYXYtaXRlbSI+PGkgY2xhc3M9ImJpIGJpLWdyaWQiPjwvaT48c3Bhbj5EYXNoYm9hcmQ8L3NwYW4+PC9hPgogICAgICAgIDxhIGhyZWY9Int7IHVybF9mb3IoJ2FkZF9pbmNvbWUnKSB9fSIgY2xhc3M9Im5hdi1pdGVtIj48aSBjbGFzcz0iYmkgYmktY2FzaC1jb2luIj48L2k+PHNwYW4+SW5jb21lIE1hbmFnZW1lbnQ8L3NwYW4+PC9hPgogICAgICAgIDxhIGhyZWY9Int7IHVybF9mb3IoJ2FkZF9leHBlbnNlJykgfX0iIGNsYXNzPSJuYXYtaXRlbSI+PGkgY2xhc3M9ImJpIGJpLXdhbGxldDIiPjwvaT48c3Bhbj5FeHBlbnNlIE1hbmFnZW1lbnQ8L3NwYW4+PC9hPgogICAgICAgIDxhIGhyZWY9Int7IHVybF9mb3IoJ2FkZF9idWRnZXQnKSB9fSIgY2xhc3M9Im5hdi1pdGVtIj48aSBjbGFzcz0iYmkgYmktcGllLWNoYXJ0Ij48L2k+PHNwYW4+QnVkZ2V0IE1hbmFnZW1lbnQ8L3NwYW4+PC9hPgogICAgICAgIDxhIGhyZWY9Int7IHVybF9mb3IoJ2FkZF9pbnZlc3RtZW50JykgfX0iIGNsYXNzPSJuYXYtaXRlbSI+PGkgY2xhc3M9ImJpIGJpLWdyYXBoLXVwLWFycm93Ij48L2k+PHNwYW4+SW52ZXN0bWVudCBUcmFja2luZzwvc3Bhbj48L2E+CiAgICAgICAgPGEgaHJlZj0ie3sgdXJsX2ZvcignZ29hbHNfbGlzdCcpIH19IiBjbGFzcz0ibmF2LWl0ZW0iPjxpIGNsYXNzPSJiaSBiaS1mbGFnIj48L2k+PHNwYW4+R29hbHM8L3NwYW4+PC9hPgogICAgICAgIDxhIGhyZWY9Int7IHVybF9mb3IoJ3Byb2ZpbGVfcGFnZScpIH19IiBjbGFzcz0ibmF2LWl0ZW0iPjxpIGNsYXNzPSJiaSBiaS1wZXJzb24tY2lyY2xlIj48L2k+PHNwYW4+UHJvZmlsZTwvc3Bhbj48L2E+CiAgICAgIDwvbmF2PgogICAgICAKICAgICAgPGJ1dHRvbiBjbGFzcz0ic2lkZWJhci1yZXNldC1idG4iIGlkPSJzaWRlYmFyLXJlc2V0LWJ0biIgdHlwZT0iYnV0dG9uIiBvbmNsaWNrPSJpZihjb25maXJtKCdBcmUgeW91IHN1cmUgeW91IHdhbnQgdG8gcmVzZXQgYWxsIGRhdGEgdG8gMD8nKSkgeyBmZXRjaCgnL2FwaS9yZXNldC1kYXRhJywge21ldGhvZDogJ1BPU1QnfSkudGhlbigoKSA9PiB7IHdpbmRvdy5sb2NhdGlvbi5ocmVmPScvZGFzaGJvYXJkJzsgfSk7IH0iIHRpdGxlPSJSZXNldCBhbGwgZGF0YSB0byAwIj4KICAgICAgICA8aSBjbGFzcz0iYmkgYmktdHJhc2giPjwvaT48c3Bhbj5SZXNldCBEYXRhPC9zcGFuPgogICAgICA8L2J1dHRvbj4KICAgICAgPGEgaHJlZj0ie3sgdXJsX2ZvcignbG9nb3V0JykgfX0iIGNsYXNzPSJzaWRlYmFyLWxvZ291dC1idG4iIHRpdGxlPSJMb2dvdXQgZnJvbSBzZXNzaW9uIj4KICAgICAgICA8aSBjbGFzcz0iYmkgYmktYm94LWFycm93LXJpZ2h0Ij48L2k+PHNwYW4+TG9nb3V0PC9zcGFuPgogICAgICA8L2E+CiAgICA8L2FzaWRlPgoKICAgIDxtYWluIGNsYXNzPSJtYWluLXBhbmVsIj4KICAgICAgPGRpdiBjbGFzcz0iY29udGVudC1zdGFjayI+CgogICAgICAgIDwhLS0gUGFnZSBIZXJvIC0tPgogICAgICAgIDxkaXYgY2xhc3M9InBhZ2UtaGVybyBnb2Fscy1oZXJvIj4KICAgICAgICAgIDxkaXYgY2xhc3M9Imhlcm8tbGVmdCI+CiAgICAgICAgICAgIDxkaXYgY2xhc3M9Imhlcm8taWNvbi13cmFwIGRhc2gtaWNvbi13cmFwIiBzdHlsZT0iYmFja2dyb3VuZDogcmdiYSgyNTUsMjU1LDI1NSwwLjI1KTsiPgogICAgICAgICAgICAgIDxpIGNsYXNzPSJiaSBiaS1idWxsc2V5ZSB0ZXh0LXdoaXRlIj48L2k+CiAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICA8ZGl2PgogICAgICAgICAgICAgIDxoMSBjbGFzcz0iaGVyby10aXRsZSI+R29hbCBQbGFubmluZzwvaDE+CiAgICAgICAgICAgICAgPHAgY2xhc3M9Imhlcm8tc3VidGl0bGUiPkludGVyYWN0aXZlIGNhbGN1bGF0b3IgdG8gc3RydWN0dXJlIHlvdXIgc2F2aW5ncyB0YXJnZXQ8L3A+CiAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgPC9kaXY+CiAgICAgICAgICA8ZGl2IGNsYXNzPSJoZXJvLXN0YXRzIj4KICAgICAgICAgICAgPGEgaHJlZj0ie3sgdXJsX2ZvcignZ29hbHNfbGlzdCcpIH19IiBjbGFzcz0iYnRuIGJ0bi1wcmltYXJ5IiBzdHlsZT0iYm9yZGVyLXJhZGl1czogMTJweDsgZm9udC13ZWlnaHQ6IDYwMDsiPjxpIGNsYXNzPSJiaSBiaS1hcnJvdy1sZWZ0IG1lLTEiPjwvaT4gQmFjayB0byBHb2FsczwvYT4KICAgICAgICAgIDwvZGl2PgogICAgICAgIDwvZGl2PgoKICAgICAgICA8IS0tIEZsYXNoIE1lc3NhZ2VzIC0tPgogICAgICAgIHslIHdpdGggbWVzc2FnZXMgPSBnZXRfZmxhc2hlZF9tZXNzYWdlcyh3aXRoX2NhdGVnb3JpZXM9dHJ1ZSkgJX0KICAgICAgICAgIHslIGlmIG1lc3NhZ2VzICV9CiAgICAgICAgICAgIHslIGZvciBjYXRlZ29yeSwgbWVzc2FnZSBpbiBtZXNzYWdlcyAlfQogICAgICAgICAgICAgIDxkaXYgY2xhc3M9InBhZ2UtYWxlcnQgYWxlcnQte3sgY2F0ZWdvcnkgfX0iPgogICAgICAgICAgICAgICAgPGkgY2xhc3M9ImJpIHslIGlmIGNhdGVnb3J5ID09ICdzdWNjZXNzJyAlfWJpLWNoZWNrLWNpcmNsZS1maWxseyUgZWxpZiBjYXRlZ29yeSA9PSAnZGFuZ2VyJyAlfWJpLWV4Y2xhbWF0aW9uLWNpcmNsZS1maWxseyUgZWxzZSAlfWJpLWluZm8tY2lyY2xlLWZpbGx7JSBlbmRpZiAlfSI+PC9pPgogICAgICAgICAgICAgICAgPHNwYW4+e3sgbWVzc2FnZSB9fTwvc3Bhbj4KICAgICAgICAgICAgICAgIDxidXR0b24gdHlwZT0iYnV0dG9uIiBjbGFzcz0iYWxlcnQtY2xvc2UtYnRuIiBvbmNsaWNrPSJ0aGlzLnBhcmVudEVsZW1lbnQucmVtb3ZlKCkiPjxpIGNsYXNzPSJiaSBiaS14LWxnIj48L2k+PC9idXR0b24+CiAgICAgICAgICAgICAgPC9kaXY+CiAgICAgICAgICAgIHslIGVuZGZvciAlfQogICAgICAgICAgeyUgZW5kaWYgJX0KICAgICAgICB7JSBlbmR3aXRoICV9CgogICAgICAgIDxkaXYgY2xhc3M9InJvdyBnLTQiPgogICAgICAgICAgPCEtLSBGb3JtIFBhbmVsIC0tPgogICAgICAgICAgPGRpdiBjbGFzcz0iY29sLWxnLTgiPgogICAgICAgICAgICA8ZGl2IGNsYXNzPSJwYW5lbCBmb3JtLXBhbmVsIj4KICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJmb3JtLXBhbmVsLWhlYWRlciBkLWZsZXggYWxpZ24taXRlbXMtY2VudGVyIG1iLTQiPgogICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0iZm9ybS1wYW5lbC1pY29uIGJnLXByaW1hcnktc3VidGxlIHRleHQtcHJpbWFyeSIgc3R5bGU9IndpZHRoOiA0NHB4OyBoZWlnaHQ6IDQ0cHg7IGJvcmRlci1yYWRpdXM6IDUwJTsgZGlzcGxheTogZ3JpZDsgcGxhY2UtaXRlbXM6IGNlbnRlcjsgZm9udC1zaXplOiAxLjJyZW07IG1hcmdpbi1yaWdodDogMTJweDsiPgogICAgICAgICAgICAgICAgICA8aSBjbGFzcz0iYmkgYmktcGx1cy1jaXJjbGUiPjwvaT4KICAgICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICAgICAgPGRpdj4KICAgICAgICAgICAgICAgICAgPGg0IGNsYXNzPSJmb3JtLXBhbmVsLXRpdGxlIG1iLTAiIHN0eWxlPSJmb250LXdlaWdodDogNzAwOyBjb2xvcjogdmFyKC0tdGV4dC1kYXJrKTsiPkdvYWwgQ29uZmlndXJhdGlvbjwvaDQ+CiAgICAgICAgICAgICAgICAgIDxwIGNsYXNzPSJmb3JtLXBhbmVsLWRlc2MgbWItMCB0ZXh0LW11dGVkIiBzdHlsZT0iZm9udC1zaXplOiAwLjgycmVtOyI+UHJvdmlkZSB0YXJnZXRzLCBjdXJyZW50IHZhbHVlcyBhbmQgY2F0ZWdvcnkgbWFwcGluZzwvcD4KICAgICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICAgIDwvZGl2PgoKICAgICAgICAgICAgICA8Zm9ybSBtZXRob2Q9IlBPU1QiIGFjdGlvbj0ieyUgaWYgZWRpdCAlfXt7IHVybF9mb3IoJ2VkaXRfZ29hbCcsIGdvYWxfaWQ9Z29hbC5pZCkgfX17JSBlbHNlICV9e3sgdXJsX2ZvcignZ29hbF9wbGFubmluZycpIH19eyUgZW5kaWYgJX0iIGlkPSJnb2FsRm9ybSI+CiAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJyb3cgZy0zIj4KICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0iY29sLW1kLTYiPgogICAgICAgICAgICAgICAgICAgIDxsYWJlbCBjbGFzcz0iZm9ybS1sYWJlbCIgc3R5bGU9ImZvbnQtd2VpZ2h0OiA2MDA7Ij5Hb2FsIE5hbWUgKjwvbGFiZWw+CiAgICAgICAgICAgICAgICAgICAgPGlucHV0IHR5cGU9InRleHQiIGlkPSJnb2FsX25hbWUiIG5hbWU9ImdvYWxfbmFtZSIgY2xhc3M9ImZvcm0tY29udHJvbCIgcGxhY2Vob2xkZXI9ImUuZy4gRHJlYW0gVmFjYXRpb24sIExhcHRvcC4uLiIgdmFsdWU9Int7IGdvYWwuZ29hbF9uYW1lIGlmIGVkaXQgZWxzZSAoZm9ybS5nb2FsX25hbWUgaWYgZm9ybSBlbHNlICcnKSB9fSIgcmVxdWlyZWQ+CiAgICAgICAgICAgICAgICAgIDwvZGl2PgoKICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0iY29sLW1kLTYiPgogICAgICAgICAgICAgICAgICAgIDxsYWJlbCBjbGFzcz0iZm9ybS1sYWJlbCIgc3R5bGU9ImZvbnQtd2VpZ2h0OiA2MDA7Ij5Hb2FsIFR5cGU8L2xhYmVsPgogICAgICAgICAgICAgICAgICAgIDxpbnB1dCB0eXBlPSJ0ZXh0IiBpZD0iZ29hbF90eXBlIiBuYW1lPSJnb2FsX3R5cGUiIGNsYXNzPSJmb3JtLWNvbnRyb2wiIHBsYWNlaG9sZGVyPSJlLmcuIFNob3J0LXRlcm0sIExvbmctdGVybS4uLiIgdmFsdWU9Int7IGdvYWwuZ29hbF90eXBlIGlmIGVkaXQgZWxzZSAoZm9ybS5nb2FsX3R5cGUgaWYgZm9ybSBlbHNlICcnKSB9fSI+CiAgICAgICAgICAgICAgICAgIDwvZGl2PgoKICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0iY29sLTEyIj4KICAgICAgICAgICAgICAgICAgICA8bGFiZWwgY2xhc3M9ImZvcm0tbGFiZWwiIHN0eWxlPSJmb250LXdlaWdodDogNjAwOyI+RGVzY3JpcHRpb248L2xhYmVsPgogICAgICAgICAgICAgICAgICAgIDx0ZXh0YXJlYSBpZD0iZGVzY3JpcHRpb24iIG5hbWU9ImRlc2NyaXB0aW9uIiBjbGFzcz0iZm9ybS1jb250cm9sIiBwbGFjZWhvbGRlcj0iV2hhdCBhcmUgZGV0YWlscyBvZiB0aGlzIGdvYWw/Ij57eyBnb2FsLmRlc2NyaXB0aW9uIGlmIGVkaXQgZWxzZSAoZm9ybS5kZXNjcmlwdGlvbiBpZiBmb3JtIGVsc2UgJycpIH19PC90ZXh0YXJlYT4KICAgICAgICAgICAgICAgICAgPC9kaXY+CgogICAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJjb2wtbWQtNCI+CiAgICAgICAgICAgICAgICAgICAgPGxhYmVsIGNsYXNzPSJmb3JtLWxhYmVsIiBzdHlsZT0iZm9udC13ZWlnaHQ6IDYwMDsiPkNhdGVnb3J5PC9sYWJlbD4KICAgICAgICAgICAgICAgICAgICA8c2VsZWN0IGlkPSJjYXRlZ29yeSIgbmFtZT0iY2F0ZWdvcnkiIGNsYXNzPSJmb3JtLXNlbGVjdCI+CiAgICAgICAgICAgICAgICAgICAgICB7JSBmb3IgY2F0IGluIGNhdGVnb3JpZXMgJX0KICAgICAgICAgICAgICAgICAgICAgICAgPG9wdGlvbiB2YWx1ZT0ie3sgY2F0IH19IiB7JSBpZiBlZGl0IGFuZCBnb2FsLmNhdGVnb3J5ID09IGNhdCAlfXNlbGVjdGVkeyUgZWxpZiBmb3JtIGFuZCBmb3JtLmNhdGVnb3J5ID09IGNhdCAlfXNlbGVjdGVkeyUgZW5kaWYgJX0+e3sgY2F0IH19PC9vcHRpb24+CiAgICAgICAgICAgICAgICAgICAgICB7JSBlbmRmb3IgJX0KICAgICAgICAgICAgICAgICAgICA8L3NlbGVjdD4KICAgICAgICAgICAgICAgICAgPC9kaXY+CgogICAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJjb2wtbWQtNCI+CiAgICAgICAgICAgICAgICAgICAgPGxhYmVsIGNsYXNzPSJmb3JtLWxhYmVsIiBzdHlsZT0iZm9udC13ZWlnaHQ6IDYwMDsiPlByaW9yaXR5PC9sYWJlbD4KICAgICAgICAgICAgICAgICAgICA8c2VsZWN0IGlkPSJwcmlvcml0eSIgbmFtZT0icHJpb3JpdHkiIGNsYXNzPSJmb3JtLXNlbGVjdCI+CiAgICAgICAgICAgICAgICAgICAgICB7JSBmb3IgcCBpbiBwcmlvcml0aWVzICV9CiAgICAgICAgICAgICAgICAgICAgICAgIDxvcHRpb24gdmFsdWU9Int7IHAgfX0iIHslIGlmIGVkaXQgYW5kIGdvYWwucHJpb3JpdHkgPT0gcCAlfXNlbGVjdGVkeyUgZWxpZiBmb3JtIGFuZCBmb3JtLnByaW9yaXR5ID09IHAgJX1zZWxlY3RlZHslIGVuZGlmICV9Pnt7IHAgfX08L29wdGlvbj4KICAgICAgICAgICAgICAgICAgICAgIHslIGVuZGZvciAlfQogICAgICAgICAgICAgICAgICAgIDwvc2VsZWN0PgogICAgICAgICAgICAgICAgICA8L2Rpdj4KCiAgICAgICAgICAgICAgICAgIDxkaXYgY2xhc3M9ImNvbC1tZC00Ij4KICAgICAgICAgICAgICAgICAgICA8bGFiZWwgY2xhc3M9ImZvcm0tbGFiZWwiIHN0eWxlPSJmb250LXdlaWdodDogNjAwOyI+U3RhdHVzPC9sYWJlbD4KICAgICAgICAgICAgICAgICAgICA8c2VsZWN0IGlkPSJzdGF0dXMiIG5hbWU9InN0YXR1cyIgY2xhc3M9ImZvcm0tc2VsZWN0Ij4KICAgICAgICAgICAgICAgICAgICAgIHslIGZvciBzIGluIHN0YXR1c2VzICV9CiAgICAgICAgICAgICAgICAgICAgICAgIDxvcHRpb24gdmFsdWU9Int7IHMgfX0iIHslIGlmIGVkaXQgYW5kIGdvYWwuc3RhdHVzID09IHMgJX1zZWxlY3RlZHslIGVsaWYgZm9ybSBhbmQgZm9ybS5zdGF0dXMgPT0gcyAlfXNlbGVjdGVkeyUgZW5kaWYgJX0+e3sgcyB9fTwvb3B0aW9uPgogICAgICAgICAgICAgICAgICAgICAgeyUgZW5kZm9yICV9CiAgICAgICAgICAgICAgICAgICAgPC9zZWxlY3Q+CiAgICAgICAgICAgICAgICAgIDwvZGl2PgoKICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0iY29sLW1kLTYiPgogICAgICAgICAgICAgICAgICAgIDxsYWJlbCBjbGFzcz0iZm9ybS1sYWJlbCIgc3R5bGU9ImZvbnQtd2VpZ2h0OiA2MDA7Ij5UYXJnZXQgQW1vdW50IChJTlIpICo8L2xhYmVsPgogICAgICAgICAgICAgICAgICAgIDxkaXYgY2xhc3M9ImlucHV0LWdyb3VwIj4KICAgICAgICAgICAgICAgICAgICAgIDxzcGFuIGNsYXNzPSJpbnB1dC1ncm91cC10ZXh0Ij7igrk8L3NwYW4+CiAgICAgICAgICAgICAgICAgICAgICA8aW5wdXQgdHlwZT0ibnVtYmVyIiBpZD0idGFyZ2V0X2Ftb3VudCIgbmFtZT0idGFyZ2V0X2Ftb3VudCIgY2xhc3M9ImZvcm0tY29udHJvbCIgcGxhY2Vob2xkZXI9IjAuMDAiIHN0ZXA9IjAuMDEiIG1pbj0iMC4wMSIgdmFsdWU9Int7IGdvYWwudGFyZ2V0X2Ftb3VudCBpZiBlZGl0IGVsc2UgKGZvcm0udGFyZ2V0X2Ftb3VudCBpZiBmb3JtIGVsc2UgJycpIH19IiByZXF1aXJlZD4KICAgICAgICAgICAgICAgICAgICA8L2Rpdj4KICAgICAgICAgICAgICAgICAgPC9kaXY+CgogICAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJjb2wtbWQtNiI+CiAgICAgICAgICAgICAgICAgICAgPGxhYmVsIGNsYXNzPSJmb3JtLWxhYmVsIiBzdHlsZT0iZm9udC13ZWlnaHQ6IDYwMDsiPkN1cnJlbnQgU2F2aW5ncyAoSU5SKTwvbGFiZWw+CiAgICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0iaW5wdXQtZ3JvdXAiPgogICAgICAgICAgICAgICAgICAgICAgPHNwYW4gY2xhc3M9ImlucHV0LWdyb3VwLXRleHQiPuKCuTwvc3Bhbj4KICAgICAgICAgICAgICAgICAgICAgIDxpbnB1dCB0eXBlPSJudW1iZXIiIGlkPSJjdXJyZW50X2Ftb3VudCIgbmFtZT0iY3VycmVudF9hbW91bnQiIGNsYXNzPSJmb3JtLWNvbnRyb2wiIHBsYWNlaG9sZGVyPSIwIiBzdGVwPSIwLjAxIiBtaW49IjAiIHZhbHVlPSJ7eyBnb2FsLmN1cnJlbnRfYW1vdW50IGlmIGVkaXQgZWxzZSAoZm9ybS5jdXJyZW50X2Ftb3VudCBpZiBmb3JtIGVsc2UgJycpIH19Ij4KICAgICAgICAgICAgICAgICAgICA8L2Rpdj4KICAgICAgICAgICAgICAgICAgPC9kaXY+CgogICAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJjb2wtbWQtNiI+CiAgICAgICAgICAgICAgICAgICAgPGxhYmVsIGNsYXNzPSJmb3JtLWxhYmVsIiBzdHlsZT0iZm9udC13ZWlnaHQ6IDYwMDsiPlN0YXJ0IERhdGU8L2xhYmVsPgogICAgICAgICAgICAgICAgICAgIDxpbnB1dCB0eXBlPSJkYXRlIiBpZD0ic3RhcnRfZGF0ZSIgbmFtZT0ic3RhcnRfZGF0ZSIgY2xhc3M9ImZvcm0tY29udHJvbCIgdmFsdWU9Int7IGdvYWwuc3RhcnRfZGF0ZSBpZiBlZGl0IGVsc2UgKGZvcm0uc3RhcnRfZGF0ZSBpZiBmb3JtIGVsc2UgdG9kYXkpIH19Ij4KICAgICAgICAgICAgICAgICAgPC9kaXY+CgogICAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJjb2wtbWQtNiI+CiAgICAgICAgICAgICAgICAgICAgPGxhYmVsIGNsYXNzPSJmb3JtLWxhYmVsIiBzdHlsZT0iZm9udC13ZWlnaHQ6IDYwMDsiPlRhcmdldCBEYXRlPC9sYWJlbD4KICAgICAgICAgICAgICAgICAgICA8aW5wdXQgdHlwZT0iZGF0ZSIgaWQ9InRhcmdldF9kYXRlIiBuYW1lPSJ0YXJnZXRfZGF0ZSIgY2xhc3M9ImZvcm0tY29udHJvbCIgdmFsdWU9Int7IGdvYWwudGFyZ2V0X2RhdGUgaWYgZWRpdCBlbHNlIChmb3JtLnRhcmdldF9kYXRlIGlmIGZvcm0gZWxzZSAnJykgfX0iPgogICAgICAgICAgICAgICAgICA8L2Rpdj4KCiAgICAgICAgICAgICAgICAgIDxkaXYgY2xhc3M9ImNvbC0xMiI+CiAgICAgICAgICAgICAgICAgICAgPGxhYmVsIGNsYXNzPSJmb3JtLWxhYmVsIiBzdHlsZT0iZm9udC13ZWlnaHQ6IDYwMDsiPlN0cmF0ZWd5IE5vdGVzIC8gUHJpb3JpdHkgSW5mbzwvbGFiZWw+CiAgICAgICAgICAgICAgICAgICAgPHRleHRhcmVhIGlkPSJub3RlcyIgbmFtZT0ibm90ZXMiIGNsYXNzPSJmb3JtLWNvbnRyb2wiIHBsYWNlaG9sZGVyPSJXcml0ZSBhbnkgc3BlY2lmaWMgc3RyYXRlZ3kgb3IgcHJpb3JpdHkgZGV0YWlscy4uLiI+e3sgZ29hbC5ub3RlcyBpZiBlZGl0IGVsc2UgKGZvcm0ubm90ZXMgaWYgZm9ybSBlbHNlICcnKSB9fTwvdGV4dGFyZWE+CiAgICAgICAgICAgICAgICAgIDwvZGl2PgoKICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0iY29sLTEyIG10LTQiPgogICAgICAgICAgICAgICAgICAgIDxidXR0b24gdHlwZT0ic3VibWl0IiBjbGFzcz0iYnRuIGJ0bi1wcmltYXJ5IHB4LTQgcHktMiIgc3R5bGU9ImJvcmRlci1yYWRpdXM6IDEwcHg7Ij4KICAgICAgICAgICAgICAgICAgICAgIDxpIGNsYXNzPSJiaSB7JSBpZiBlZGl0ICV9Ymktc2F2ZXslIGVsc2UgJX1iaS1wbHVzLWNpcmNsZXslIGVuZGlmICV9IG1lLTEiPjwvaT4KICAgICAgICAgICAgICAgICAgICAgIHslIGlmIGVkaXQgJX1TYXZlIEdvYWx7JSBlbHNlICV9Q3JlYXRlIEdvYWx7JSBlbmRpZiAlfQogICAgICAgICAgICAgICAgICAgIDwvYnV0dG9uPgogICAgICAgICAgICAgICAgICA8L2Rpdj4KICAgICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICAgIDwvZm9ybT4KICAgICAgICAgICAgPC9kaXY+CiAgICAgICAgICA8L2Rpdj4KCiAgICAgICAgICA8IS0tIFNhdmluZ3MgQ2FsY3VsYXRvciBTaWRlYmFyIC0tPgogICAgICAgICAgPGRpdiBjbGFzcz0iY29sLWxnLTQiPgogICAgICAgICAgICA8ZGl2IGNsYXNzPSJwcmV2aWV3LXBhbmVsIj4KICAgICAgICAgICAgICA8aDQgY2xhc3M9InByZXZpZXctdGl0bGUiPjxpIGNsYXNzPSJiaSBiaS1jYWxjdWxhdG9yIHRleHQtcHJpbWFyeSI+PC9pPiBTYXZpbmdzIENhbGN1bGF0b3I8L2g0PgogICAgICAgICAgICAgIAogICAgICAgICAgICAgIDxkaXYgY2xhc3M9InByZXZpZXctcm93Ij4KICAgICAgICAgICAgICAgIDxzcGFuIGNsYXNzPSJwcmV2aWV3LWxhYmVsIj5UYXJnZXQgQW1vdW50PC9zcGFuPgogICAgICAgICAgICAgICAgPHNwYW4gY2xhc3M9InByZXZpZXctdmFsdWUiIGlkPSJwcmV2LXRhcmdldCI+4oK5MC4wMDwvc3Bhbj4KICAgICAgICAgICAgICA8L2Rpdj4KICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJwcmV2aWV3LXJvdyI+CiAgICAgICAgICAgICAgICA8c3BhbiBjbGFzcz0icHJldmlldy1sYWJlbCI+Q3VycmVudCBTYXZpbmdzPC9zcGFuPgogICAgICAgICAgICAgICAgPHNwYW4gY2xhc3M9InByZXZpZXctdmFsdWUiIGlkPSJwcmV2LWN1cnJlbnQiPuKCuTAuMDA8L3NwYW4+CiAgICAgICAgICAgICAgPC9kaXY+CiAgICAgICAgICAgICAgPGRpdiBjbGFzcz0icHJldmlldy1yb3ciPgogICAgICAgICAgICAgICAgPHNwYW4gY2xhc3M9InByZXZpZXctbGFiZWwiPlJlbWFpbmluZzwvc3Bhbj4KICAgICAgICAgICAgICAgIDxzcGFuIGNsYXNzPSJwcmV2aWV3LXZhbHVlIHRleHQtZGFuZ2VyIiBpZD0icHJldi1yZW1haW5pbmciPuKCuTAuMDA8L3NwYW4+CiAgICAgICAgICAgICAgPC9kaXY+CiAgICAgICAgICAgICAgPGRpdiBjbGFzcz0icHJldmlldy1yb3ciPgogICAgICAgICAgICAgICAgPHNwYW4gY2xhc3M9InByZXZpZXctbGFiZWwiPlByb2dyZXNzPC9zcGFuPgogICAgICAgICAgICAgICAgPHNwYW4gY2xhc3M9InByZXZpZXctdmFsdWUgdGV4dC1zdWNjZXNzIiBpZD0icHJldi1wcm9ncmVzcyI+MC4wJTwvc3Bhbj4KICAgICAgICAgICAgICA8L2Rpdj4KICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJwcmV2aWV3LXJvdyI+CiAgICAgICAgICAgICAgICA8c3BhbiBjbGFzcz0icHJldmlldy1sYWJlbCI+TW9udGhzIExlZnQ8L3NwYW4+CiAgICAgICAgICAgICAgICA8c3BhbiBjbGFzcz0icHJldmlldy12YWx1ZSIgaWQ9InByZXYtbW9udGhzIj5OL0E8L3NwYW4+CiAgICAgICAgICAgICAgPC9kaXY+CiAgICAgICAgICAgICAgPGRpdiBjbGFzcz0icHJldmlldy1yb3ciPgogICAgICAgICAgICAgICAgPHNwYW4gY2xhc3M9InByZXZpZXctbGFiZWwiPk1vbnRobHkgTmVlZGVkPC9zcGFuPgogICAgICAgICAgICAgICAgPHNwYW4gY2xhc3M9InByZXZpZXctdmFsdWUgdGV4dC1wcmltYXJ5IiBpZD0icHJldi1tb250aGx5Ij7igrkwLjAwPC9zcGFuPgogICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICAgIDxkaXYgY2xhc3M9InByZXZpZXctcm93Ij4KICAgICAgICAgICAgICAgIDxzcGFuIGNsYXNzPSJwcmV2aWV3LWxhYmVsIj5XZWVrbHkgTmVlZGVkPC9zcGFuPgogICAgICAgICAgICAgICAgPHNwYW4gY2xhc3M9InByZXZpZXctdmFsdWUgdGV4dC1wcmltYXJ5IiBpZD0icHJldi13ZWVrbHkiPuKCuTAuMDA8L3NwYW4+CiAgICAgICAgICAgICAgPC9kaXY+CgogICAgICAgICAgICAgIDxkaXYgY2xhc3M9Im10LTQiPgogICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0icHJvZ3Jlc3MiIHN0eWxlPSJoZWlnaHQ6IDEwcHg7IGJvcmRlci1yYWRpdXM6IDk5OXB4OyBiYWNrZ3JvdW5kLWNvbG9yOiAjRTJFOEYwOyI+CiAgICAgICAgICAgICAgICAgIDxkaXYgaWQ9InByZXYtcHJvZ3Jlc3MtYmFyIiBjbGFzcz0icHJvZ3Jlc3MtYmFyIGJnLXN1Y2Nlc3MiIHJvbGU9InByb2dyZXNzYmFyIiBzdHlsZT0id2lkdGg6IDAlIj48L2Rpdj4KICAgICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0idGV4dC1jZW50ZXIgbXQtMiI+CiAgICAgICAgICAgICAgICAgIDxzcGFuIGlkPSJwcmV2LXByb2dyZXNzLWxibCIgc3R5bGU9ImZvbnQtc2l6ZTogMC44cmVtOyBmb250LXdlaWdodDogNjAwOyBjb2xvcjogdmFyKC0tdGV4dC1tdXRlZCk7Ij4wJSBjb21wbGV0ZTwvc3Bhbj4KICAgICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICA8L2Rpdj4KICAgICAgICAgIDwvZGl2PgogICAgICAgIDwvZGl2PgoKICAgICAgPC9kaXY+CiAgICA8L21haW4+CiAgPC9kaXY+CgogIDxzY3JpcHQgc3JjPSJodHRwczovL2Nkbi5qc2RlbGl2ci5uZXQvbnBtL2Jvb3RzdHJhcEA1LjMuMy9kaXN0L2pzL2Jvb3RzdHJhcC5idW5kbGUubWluLmpzIj48L3NjcmlwdD4KICA8c2NyaXB0IHNyYz0iaHR0cHM6Ly9jZG4uanNkZWxpdnIubmV0L25wbS9jaGFydC5qcyI+PC9zY3JpcHQ+CiAgPHNjcmlwdCBzcmM9Int7IHVybF9mb3IoJ3N0YXRpYycsIGZpbGVuYW1lPSdqcy9jdXJzb3IuanMnKSB9fSI+PC9zY3JpcHQ+CiAgPHNjcmlwdD4KICAgIGRvY3VtZW50LmFkZEV2ZW50TGlzdGVuZXIoJ0RPTUNvbnRlbnRMb2FkZWQnLCAoKSA9PiB7CiAgICAgIGNvbnN0IHRhcmdldElucHV0ID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ3RhcmdldF9hbW91bnQnKTsKICAgICAgY29uc3QgY3VycmVudElucHV0ID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ2N1cnJlbnRfYW1vdW50Jyk7CiAgICAgIGNvbnN0IHN0YXJ0SW5wdXQgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgnc3RhcnRfZGF0ZScpOwogICAgICBjb25zdCB0YXJnZXREYXRlSW5wdXQgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgndGFyZ2V0X2RhdGUnKTsKCiAgICAgIGZ1bmN0aW9uIHVwZGF0ZUNhbGN1bGF0b3IoKSB7CiAgICAgICAgY29uc3QgdGFyZ2V0ID0gcGFyc2VGbG9hdCh0YXJnZXRJbnB1dC52YWx1ZSkgfHwgMDsKICAgICAgICBjb25zdCBjdXJyZW50ID0gcGFyc2VGbG9hdChjdXJyZW50SW5wdXQudmFsdWUpIHx8IDA7CiAgICAgICAgY29uc3QgcmVtYWluaW5nID0gTWF0aC5tYXgodGFyZ2V0IC0gY3VycmVudCwgMCk7CiAgICAgICAgY29uc3QgcHJvZ3Jlc3MgPSB0YXJnZXQgPiAwID8gTWF0aC5taW4oKGN1cnJlbnQgLyB0YXJnZXQpICogMTAwLCAxMDApIDogMDsKCiAgICAgICAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ3ByZXYtdGFyZ2V0JykudGV4dENvbnRlbnQgPSBg4oK5JHt0YXJnZXQudG9Mb2NhbGVTdHJpbmcoJ2VuLUlOJywge21pbmltdW1GcmFjdGlvbkRpZ2l0czogMiwgbWF4aW11bUZyYWN0aW9uRGlnaXRzOiAyfSl9YDsKICAgICAgICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgncHJldi1jdXJyZW50JykudGV4dENvbnRlbnQgPSBg4oK5JHtjdXJyZW50LnRvTG9jYWxlU3RyaW5nKCdlbi1JTicsIHttaW5pbXVtRnJhY3Rpb25EaWdpdHM6IDIsIG1heGltdW1GcmFjdGlvbkRpZ2l0czogMn0pfWA7CiAgICAgICAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ3ByZXYtcmVtYWluaW5nJykudGV4dENvbnRlbnQgPSBg4oK5JHtyZW1haW5pbmcudG9Mb2NhbGVTdHJpbmcoJ2VuLUlOJywge21pbmltdW1GcmFjdGlvbkRpZ2l0czogMiwgbWF4aW11bUZyYWN0aW9uRGlnaXRzOiAyfSl9YDsKICAgICAgICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgncHJldi1wcm9ncmVzcycpLnRleHRDb250ZW50ID0gYCR7cHJvZ3Jlc3MudG9GaXhlZCgxKX0lYDsKICAgICAgICAKICAgICAgICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgncHJldi1wcm9ncmVzcy1iYXInKS5zdHlsZS53aWR0aCA9IGAke3Byb2dyZXNzfSVgOwogICAgICAgIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCdwcmV2LXByb2dyZXNzLWxibCcpLnRleHRDb250ZW50ID0gYCR7cHJvZ3Jlc3MudG9GaXhlZCgwKX0lIGNvbXBsZXRlYDsKCiAgICAgICAgLy8gQ2FsY3VsYXRlIG1vbnRocyBsZWZ0CiAgICAgICAgbGV0IG1vbnRocyA9IDA7CiAgICAgICAgaWYgKHRhcmdldERhdGVJbnB1dC52YWx1ZSkgewogICAgICAgICAgY29uc3Qgc3RhcnQgPSBzdGFydElucHV0LnZhbHVlID8gbmV3IERhdGUoc3RhcnRJbnB1dC52YWx1ZSkgOiBuZXcgRGF0ZSgpOwogICAgICAgICAgY29uc3QgZW5kID0gbmV3IERhdGUodGFyZ2V0RGF0ZUlucHV0LnZhbHVlKTsKICAgICAgICAgIGNvbnN0IHRpbWVEaWZmID0gZW5kIC0gc3RhcnQ7CiAgICAgICAgICBjb25zdCBkYXlzID0gdGltZURpZmYgLyAoMTAwMCAqIDYwICogNjAgKiAyNCk7CiAgICAgICAgICBtb250aHMgPSBNYXRoLm1heChkYXlzIC8gMzAuNDQsIDApOwogICAgICAgIH0KCiAgICAgICAgaWYgKG1vbnRocyA+IDApIHsKICAgICAgICAgIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCdwcmV2LW1vbnRocycpLnRleHRDb250ZW50ID0gYCR7bW9udGhzLnRvRml4ZWQoMSl9IG1vbnRoc2A7CiAgICAgICAgICBjb25zdCBtb250aGx5ID0gcmVtYWluaW5nIC8gbW9udGhzOwogICAgICAgICAgY29uc3Qgd2Vla2x5ID0gbW9udGhseSAvIDQuMzM7CiAgICAgICAgICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgncHJldi1tb250aGx5JykudGV4dENvbnRlbnQgPSBg4oK5JHttb250aGx5LnRvTG9jYWxlU3RyaW5nKCdlbi1JTicsIHttaW5pbXVtRnJhY3Rpb25EaWdpdHM6IDIsIG1heGltdW1GcmFjdGlvbkRpZ2l0czogMn0pfWA7CiAgICAgICAgICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgncHJldi13ZWVrbHknKS50ZXh0Q29udGVudCA9IGDigrkke3dlZWtseS50b0xvY2FsZVN0cmluZygnZW4tSU4nLCB7bWluaW11bUZyYWN0aW9uRGlnaXRzOiAyLCBtYXhpbXVtRnJhY3Rpb25EaWdpdHM6IDJ9KX1gOwogICAgICAgIH0gZWxzZSB7CiAgICAgICAgICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgncHJldi1tb250aHMnKS50ZXh0Q29udGVudCA9ICdOL0EnOwogICAgICAgICAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ3ByZXYtbW9udGhseScpLnRleHRDb250ZW50ID0gJ+KCuTAuMDAnOwogICAgICAgICAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ3ByZXYtd2Vla2x5JykudGV4dENvbnRlbnQgPSAn4oK5MC4wMCc7CiAgICAgICAgfQogICAgICB9CgogICAgICB0YXJnZXRJbnB1dC5hZGRFdmVudExpc3RlbmVyKCdpbnB1dCcsIHVwZGF0ZUNhbGN1bGF0b3IpOwogICAgICBjdXJyZW50SW5wdXQuYWRkRXZlbnRMaXN0ZW5lcignaW5wdXQnLCB1cGRhdGVDYWxjdWxhdG9yKTsKICAgICAgc3RhcnRJbnB1dC5hZGRFdmVudExpc3RlbmVyKCdpbnB1dCcsIHVwZGF0ZUNhbGN1bGF0b3IpOwogICAgICB0YXJnZXREYXRlSW5wdXQuYWRkRXZlbnRMaXN0ZW5lcignaW5wdXQnLCB1cGRhdGVDYWxjdWxhdG9yKTsKCiAgICAgIHVwZGF0ZUNhbGN1bGF0b3IoKTsKICAgIH0pOwogIDwvc2NyaXB0Pgo8L2JvZHk+CjwvaHRtbD4K').decode('utf-8'),
    'investment.html': base64.b64decode('PCFkb2N0eXBlIGh0bWw+CjxodG1sIGxhbmc9ImVuIj4KPGhlYWQ+CiAgPG1ldGEgY2hhcnNldD0idXRmLTgiPgogIDxtZXRhIG5hbWU9InZpZXdwb3J0IiBjb250ZW50PSJ3aWR0aD1kZXZpY2Utd2lkdGgsIGluaXRpYWwtc2NhbGU9MSI+CiAgPHRpdGxlPkludmVzdG1lbnQgVHJhY2tpbmcg4oCTIEZpblNpZ2h0PC90aXRsZT4KICA8bGluayByZWw9InByZWNvbm5lY3QiIGhyZWY9Imh0dHBzOi8vZm9udHMuZ29vZ2xlYXBpcy5jb20iPgogIDxsaW5rIHJlbD0icHJlY29ubmVjdCIgaHJlZj0iaHR0cHM6Ly9mb250cy5nc3RhdGljLmNvbSIgY3Jvc3NvcmlnaW4+CiAgPGxpbmsgaHJlZj0iaHR0cHM6Ly9mb250cy5nb29nbGVhcGlzLmNvbS9jc3MyP2ZhbWlseT1JbnRlcjp3Z2h0QDQwMDs1MDA7NjAwOzcwMDs4MDAmZGlzcGxheT1zd2FwIiByZWw9InN0eWxlc2hlZXQiPgogIDxsaW5rIGhyZWY9Imh0dHBzOi8vY2RuLmpzZGVsaXZyLm5ldC9ucG0vYm9vdHN0cmFwQDUuMy4zL2Rpc3QvY3NzL2Jvb3RzdHJhcC5taW4uY3NzIiByZWw9InN0eWxlc2hlZXQiPgogIDxsaW5rIHJlbD0ic3R5bGVzaGVldCIgaHJlZj0iaHR0cHM6Ly9jZG4uanNkZWxpdnIubmV0L25wbS9ib290c3RyYXAtaWNvbnNAMS4xMS4zL2ZvbnQvYm9vdHN0cmFwLWljb25zLmNzcyI+CiAgPGxpbmsgcmVsPSJzdHlsZXNoZWV0IiBocmVmPSJ7eyB1cmxfZm9yKCdzdGF0aWMnLCBmaWxlbmFtZT0nY3NzL2Rhc2hib2FyZC5jc3MnKSB9fSI+CiAgPGxpbmsgcmVsPSJzdHlsZXNoZWV0IiBocmVmPSJ7eyB1cmxfZm9yKCdzdGF0aWMnLCBmaWxlbmFtZT0nY3NzL3BhZ2VzLmNzcycpIH19Ij4KICA8bGluayByZWw9InN0eWxlc2hlZXQiIGhyZWY9Int7IHVybF9mb3IoJ3N0YXRpYycsIGZpbGVuYW1lPSdjc3MvY3Vyc29yLmNzcycpIH19Ij4KICA8c3R5bGU+CiAgICAuZm9ybS1wYW5lbCB7CiAgICAgIGJvcmRlci10b3A6IDRweCBzb2xpZCAjMUUyOTNCOwogICAgfQogICAgLnByZXZpZXctcGFuZWwgewogICAgICBiYWNrZ3JvdW5kOiB2YXIoLS13aGl0ZSk7CiAgICAgIGJvcmRlci1yYWRpdXM6IHZhcigtLWJvcmRlci1yYWRpdXMtY2FyZCk7CiAgICAgIHBhZGRpbmc6IDI0cHg7CiAgICAgIGJveC1zaGFkb3c6IHZhcigtLXNoYWRvdyk7CiAgICAgIHBvc2l0aW9uOiBzdGlja3k7CiAgICAgIHRvcDogMjBweDsKICAgIH0KICAgIC5wcmV2aWV3LXRpdGxlIHsKICAgICAgZm9udC1zaXplOiAxLjFyZW07CiAgICAgIGZvbnQtd2VpZ2h0OiA3MDA7CiAgICAgIGNvbG9yOiB2YXIoLS10ZXh0LWRhcmspOwogICAgICBtYXJnaW4tYm90dG9tOiAxOHB4OwogICAgICBkaXNwbGF5OiBmbGV4OwogICAgICBhbGlnbi1pdGVtczogY2VudGVyOwogICAgICBnYXA6IDhweDsKICAgIH0KICAgIC5wcmV2aWV3LXJvdyB7CiAgICAgIGRpc3BsYXk6IGZsZXg7CiAgICAgIGp1c3RpZnktY29udGVudDogc3BhY2UtYmV0d2VlbjsKICAgICAgcGFkZGluZzogMTBweCAwOwogICAgICBib3JkZXItYm90dG9tOiAxcHggc29saWQgI0YxRjVGOTsKICAgICAgZm9udC1zaXplOiAwLjlyZW07CiAgICB9CiAgICAucHJldmlldy1yb3c6bGFzdC1jaGlsZCB7CiAgICAgIGJvcmRlci1ib3R0b206IDA7CiAgICB9CiAgICAucHJldmlldy1sYWJlbCB7CiAgICAgIGNvbG9yOiB2YXIoLS10ZXh0LW11dGVkKTsKICAgICAgZm9udC13ZWlnaHQ6IDUwMDsKICAgIH0KICAgIC5wcmV2aWV3LXZhbHVlIHsKICAgICAgZm9udC13ZWlnaHQ6IDcwMDsKICAgICAgY29sb3I6IHZhcigtLXRleHQtZGFyayk7CiAgICB9CiAgPC9zdHlsZT4KPC9oZWFkPgo8Ym9keSBjbGFzcz0idGhlbWUtaW52ZXN0Ij4KPGRpdiBpZD0iY3Vyc29yLWRvdCI+PC9kaXY+CjxkaXYgaWQ9ImN1cnNvci1yaW5nIj48L2Rpdj4KCjwhLS0gUHJvZmlsZSBDaGlwIC0tPgo8YSBocmVmPSJ7eyB1cmxfZm9yKCdwcm9maWxlX3BhZ2UnKSB9fSIgY2xhc3M9InByb2ZpbGUtY2hpcC1nbG9iYWwiIHRpdGxlPSJWaWV3IFByb2ZpbGUiPgogIDxkaXYgY2xhc3M9InByb2ZpbGUtY2hpcC1hdmF0YXIiPnt7IHVzZXJfbmFtZVswXXx1cHBlciBpZiB1c2VyX25hbWUgZWxzZSAnQScgfX08L2Rpdj4KICA8ZGl2IGNsYXNzPSJwcm9maWxlLWNoaXAtaW5mbyI+CiAgICA8c3BhbiBjbGFzcz0icHJvZmlsZS1jaGlwLW5hbWUiPnt7IHVzZXJfbmFtZSBpZiB1c2VyX25hbWUgZWxzZSAnQXJqdW4gTWVodGEnIH19PC9zcGFuPgogIDwvZGl2Pgo8L2E+CgogIDxidXR0b24gY2xhc3M9ImZsb2F0aW5nLWhhbWJ1cmdlciIgaWQ9InNpZGViYXItdG9nZ2xlLWJ0biIgdHlwZT0iYnV0dG9uIiB0aXRsZT0iVG9nZ2xlIFNpZGViYXIgTWVudSI+CiAgICA8aSBjbGFzcz0iYmkgYmktbGlzdCI+PC9pPgogIDwvYnV0dG9uPgoKICA8ZGl2IGNsYXNzPSJkLWZsZXgiPgoKICA8YXNpZGUgY2xhc3M9InNpZGViYXIiIGlkPSJzaWRlYmFyIj4KICAgIDxkaXYgY2xhc3M9ImxvZ28tcm93Ij4KICAgICAgPGltZyBzcmM9Int7IHVybF9mb3IoJ3N0YXRpYycsIGZpbGVuYW1lPSdpbWFnZXMvbG9nby5qcGVnJykgfX0iIGFsdD0iRmluU2lnaHQgTG9nbyIgY2xhc3M9ImRhc2gtbmF2LWxvZ28taW1nIiBzdHlsZT0id2lkdGg6NDJweDtoZWlnaHQ6NDJweDsiPgogICAgICA8ZGl2IGNsYXNzPSJsb2dvLXRleHQiPgogICAgICAgIDxoMz5GaW5TaWdodDwvaDM+CiAgICAgICAgPHNtYWxsPlNtYXJ0LiBTZWN1cmUuIFNpbXBsZS48L3NtYWxsPgogICAgICA8L2Rpdj4KICAgIDwvZGl2PgogICAgPG5hdiBjbGFzcz0ibmF2LWxpc3QiPgogICAgICA8YSBocmVmPSJ7eyB1cmxfZm9yKCdkYXNoYm9hcmQnKSB9fSIgY2xhc3M9Im5hdi1pdGVtIj48aSBjbGFzcz0iYmkgYmktZ3JpZCI+PC9pPjxzcGFuPkRhc2hib2FyZDwvc3Bhbj48L2E+CiAgICAgIDxhIGhyZWY9Int7IHVybF9mb3IoJ2FkZF9pbmNvbWUnKSB9fSIgY2xhc3M9Im5hdi1pdGVtIj48aSBjbGFzcz0iYmkgYmktY2FzaC1jb2luIj48L2k+PHNwYW4+SW5jb21lIE1hbmFnZW1lbnQ8L3NwYW4+PC9hPgogICAgICA8YSBocmVmPSJ7eyB1cmxfZm9yKCdhZGRfZXhwZW5zZScpIH19IiBjbGFzcz0ibmF2LWl0ZW0iPjxpIGNsYXNzPSJiaSBiaS13YWxsZXQyIj48L2k+PHNwYW4+RXhwZW5zZSBNYW5hZ2VtZW50PC9zcGFuPjwvYT4KICAgICAgPGEgaHJlZj0ie3sgdXJsX2ZvcignYWRkX2J1ZGdldCcpIH19IiBjbGFzcz0ibmF2LWl0ZW0iPjxpIGNsYXNzPSJiaSBiaS1waWUtY2hhcnQiPjwvaT48c3Bhbj5CdWRnZXQgTWFuYWdlbWVudDwvc3Bhbj48L2E+CiAgICAgIDxhIGhyZWY9Int7IHVybF9mb3IoJ2FkZF9pbnZlc3RtZW50JykgfX0iIGNsYXNzPSJuYXYtaXRlbSBhY3RpdmUiPjxpIGNsYXNzPSJiaSBiaS1ncmFwaC11cC1hcnJvdyI+PC9pPjxzcGFuPkludmVzdG1lbnQgVHJhY2tpbmc8L3NwYW4+PC9hPgogICAgICA8YSBocmVmPSJ7eyB1cmxfZm9yKCdnb2Fsc19saXN0JykgfX0iIGNsYXNzPSJuYXYtaXRlbSI+PGkgY2xhc3M9ImJpIGJpLWZsYWciPjwvaT48c3Bhbj5Hb2Fsczwvc3Bhbj48L2E+CiAgICAgIDxhIGhyZWY9Int7IHVybF9mb3IoJ3Byb2ZpbGVfcGFnZScpIH19IiBjbGFzcz0ibmF2LWl0ZW0iPjxpIGNsYXNzPSJiaSBiaS1wZXJzb24tY2lyY2xlIj48L2k+PHNwYW4+UHJvZmlsZTwvc3Bhbj48L2E+CiAgICA8L25hdj4KICAgIAogICAgPGJ1dHRvbiBjbGFzcz0ic2lkZWJhci1yZXNldC1idG4iIGlkPSJzaWRlYmFyLXJlc2V0LWJ0biIgdHlwZT0iYnV0dG9uIiBvbmNsaWNrPSJpZihjb25maXJtKCdBcmUgeW91IHN1cmUgeW91IHdhbnQgdG8gcmVzZXQgYWxsIGRhdGEgdG8gMD8nKSkgeyBmZXRjaCgnL2FwaS9yZXNldC1kYXRhJywge21ldGhvZDogJ1BPU1QnfSkudGhlbigoKSA9PiB7IHdpbmRvdy5sb2NhdGlvbi5ocmVmPScvZGFzaGJvYXJkJzsgfSk7IH0iIHRpdGxlPSJSZXNldCBhbGwgZGF0YSB0byAwIj4KICAgICAgPGkgY2xhc3M9ImJpIGJpLXRyYXNoIj48L2k+PHNwYW4+UmVzZXQgRGF0YTwvc3Bhbj4KICAgIDwvYnV0dG9uPgogICAgPGEgaHJlZj0ie3sgdXJsX2ZvcignbG9nb3V0JykgfX0iIGNsYXNzPSJzaWRlYmFyLWxvZ291dC1idG4iIHRpdGxlPSJMb2dvdXQgZnJvbSBzZXNzaW9uIj4KICAgICAgPGkgY2xhc3M9ImJpIGJpLWJveC1hcnJvdy1yaWdodCI+PC9pPjxzcGFuPkxvZ291dDwvc3Bhbj4KICAgIDwvYT4KICA8L2FzaWRlPgoKICA8bWFpbiBjbGFzcz0ibWFpbi1wYW5lbCI+CiAgICA8ZGl2IGNsYXNzPSJjb250ZW50LXN0YWNrIj4KCiAgICAgIDxkaXYgY2xhc3M9InBhZ2UtaGVybyBpbnZlc3QtaGVybyI+CiAgICAgICAgPGRpdiBjbGFzcz0iaGVyby1sZWZ0Ij4KICAgICAgICAgIDxkaXYgY2xhc3M9Imhlcm8taWNvbi13cmFwIGludmVzdC1pY29uLXdyYXAiIHN0eWxlPSJiYWNrZ3JvdW5kOiByZ2JhKDI1NSwyNTUsMjU1LDAuMjUpOyI+CiAgICAgICAgICAgIDxpIGNsYXNzPSJiaSBiaS1ncmFwaC11cC1hcnJvdyB0ZXh0LXdoaXRlIj48L2k+CiAgICAgICAgICA8L2Rpdj4KICAgICAgICAgIDxkaXY+CiAgICAgICAgICAgIDxoMSBjbGFzcz0iaGVyby10aXRsZSI+SW52ZXN0bWVudCBUcmFja2luZzwvaDE+CiAgICAgICAgICAgIDxwIGNsYXNzPSJoZXJvLXN1YnRpdGxlIj5SZWNvcmQgaW52ZXN0bWVudHMgYW5kIGdyb3cgeW91ciBmaW5hbmNpYWwgcG9ydGZvbGlvPC9wPgogICAgICAgICAgPC9kaXY+CiAgICAgICAgPC9kaXY+CiAgICAgIDwvZGl2PgoKICAgICAgeyUgd2l0aCBtZXNzYWdlcyA9IGdldF9mbGFzaGVkX21lc3NhZ2VzKHdpdGhfY2F0ZWdvcmllcz10cnVlKSAlfQogICAgICAgIHslIGlmIG1lc3NhZ2VzICV9CiAgICAgICAgICB7JSBmb3IgY2F0ZWdvcnksIG1lc3NhZ2UgaW4gbWVzc2FnZXMgJX0KICAgICAgICAgICAgPGRpdiBjbGFzcz0icGFnZS1hbGVydCBhbGVydC17eyBjYXRlZ29yeSB9fSI+CiAgICAgICAgICAgICAgPGkgY2xhc3M9ImJpIHslIGlmIGNhdGVnb3J5ID09ICdzdWNjZXNzJyAlfWJpLWNoZWNrLWNpcmNsZS1maWxseyUgZWxpZiBjYXRlZ29yeSA9PSAnZGFuZ2VyJyAlfWJpLWV4Y2xhbWF0aW9uLWNpcmNsZS1maWxseyUgZWxzZSAlfWJpLWluZm8tY2lyY2xlLWZpbGx7JSBlbmRpZiAlfSI+PC9pPgogICAgICAgICAgICAgIDxzcGFuPnt7IG1lc3NhZ2UgfX08L3NwYW4+CiAgICAgICAgICAgICAgPGJ1dHRvbiB0eXBlPSJidXR0b24iIGNsYXNzPSJhbGVydC1jbG9zZS1idG4iIG9uY2xpY2s9InRoaXMucGFyZW50RWxlbWVudC5yZW1vdmUoKSI+PGkgY2xhc3M9ImJpIGJpLXgtbGciPjwvaT48L2J1dHRvbj4KICAgICAgICAgICAgPC9kaXY+CiAgICAgICAgICB7JSBlbmRmb3IgJX0KICAgICAgICB7JSBlbmRpZiAlfQogICAgICB7JSBlbmR3aXRoICV9CgogICAgICB7JSBpZiBlcnJvciAlfQogICAgICAgIDxkaXYgY2xhc3M9InBhZ2UtYWxlcnQgYWxlcnQtZGFuZ2VyIj4KICAgICAgICAgIDxpIGNsYXNzPSJiaSBiaS1leGNsYW1hdGlvbi1jaXJjbGUtZmlsbCI+PC9pPgogICAgICAgICAgPHNwYW4+e3sgZXJyb3IgfX08L3NwYW4+CiAgICAgICAgPC9kaXY+CiAgICAgIHslIGVuZGlmICV9CgogICAgICA8ZGl2IGNsYXNzPSJyb3cgZy00Ij4KICAgICAgICA8IS0tIEZvcm0gUGFuZWwgLS0+CiAgICAgICAgPGRpdiBjbGFzcz0iY29sLWxnLTgiPgogICAgICAgICAgPGRpdiBjbGFzcz0icGFuZWwgZm9ybS1wYW5lbCI+CiAgICAgICAgICAgIDxkaXYgY2xhc3M9ImZvcm0tcGFuZWwtaGVhZGVyIGQtZmxleCBhbGlnbi1pdGVtcy1jZW50ZXIgbWItNCI+CiAgICAgICAgICAgICAgPGRpdiBjbGFzcz0iZm9ybS1wYW5lbC1pY29uIGJnLXByaW1hcnktc3VidGxlIHRleHQtcHJpbWFyeSIgc3R5bGU9IndpZHRoOiA0NHB4OyBoZWlnaHQ6IDQ0cHg7IGJvcmRlci1yYWRpdXM6IDUwJTsgZGlzcGxheTogZ3JpZDsgcGxhY2UtaXRlbXM6IGNlbnRlcjsgZm9udC1zaXplOiAxLjJyZW07IG1hcmdpbi1yaWdodDogMTJweDsiPgogICAgICAgICAgICAgICAgPGkgY2xhc3M9ImJpIGJpLXBsdXMtY2lyY2xlIj48L2k+CiAgICAgICAgICAgICAgPC9kaXY+CiAgICAgICAgICAgICAgPGRpdj4KICAgICAgICAgICAgICAgIDxoNCBjbGFzcz0iZm9ybS1wYW5lbC10aXRsZSBtYi0wIiBzdHlsZT0iZm9udC13ZWlnaHQ6IDcwMDsgY29sb3I6IHZhcigtLXRleHQtZGFyayk7Ij5OZXcgSW52ZXN0bWVudCBFbnRyeTwvaDQ+CiAgICAgICAgICAgICAgICA8cCBjbGFzcz0iZm9ybS1wYW5lbC1kZXNjIG1iLTAgdGV4dC1tdXRlZCIgc3R5bGU9ImZvbnQtc2l6ZTogMC44MnJlbTsiPlJlY29yZCB5b3VyIGludmVzdG1lbnQgdG8gdHJhY2sgcG9ydGZvbGlvIGdyb3d0aDwvcD4KICAgICAgICAgICAgICA8L2Rpdj4KICAgICAgICAgICAgPC9kaXY+CgogICAgICAgICAgICA8Zm9ybSBpZD0iaW52ZXN0bWVudC1mb3JtIiBhY3Rpb249Int7IHVybF9mb3IoJ2FkZF9pbnZlc3RtZW50JykgfX0iIG1ldGhvZD0iUE9TVCIgbm92YWxpZGF0ZT4KICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJyb3cgZy0zIj4KICAgICAgICAgICAgICAgIDxkaXYgY2xhc3M9ImNvbC1tZC02Ij4KICAgICAgICAgICAgICAgICAgPGxhYmVsIGZvcj0iaW52ZXN0LXNvdXJjZSIgY2xhc3M9ImZvcm0tbGFiZWwiIHN0eWxlPSJmb250LXdlaWdodDogNjAwOyI+SW52ZXN0bWVudCBTb3VyY2U8L2xhYmVsPgogICAgICAgICAgICAgICAgICA8aW5wdXQgdHlwZT0idGV4dCIgaWQ9ImludmVzdC1zb3VyY2UiIG5hbWU9InNvdXJjZSIgY2xhc3M9ImZvcm0tY29udHJvbCIgcGxhY2Vob2xkZXI9ImUuZy4gWmVyb2RoYSwgR3Jvd3csIEhERkMgTUYiIHJlcXVpcmVkPgogICAgICAgICAgICAgICAgPC9kaXY+CgogICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0iY29sLW1kLTYiPgogICAgICAgICAgICAgICAgICA8bGFiZWwgZm9yPSJpbnZlc3QtdHlwZSIgY2xhc3M9ImZvcm0tbGFiZWwiIHN0eWxlPSJmb250LXdlaWdodDogNjAwOyI+SW52ZXN0bWVudCBUeXBlPC9sYWJlbD4KICAgICAgICAgICAgICAgICAgPHNlbGVjdCBpZD0iaW52ZXN0LXR5cGUiIG5hbWU9ImludmVzdF90eXBlIiBjbGFzcz0iZm9ybS1zZWxlY3QiPgogICAgICAgICAgICAgICAgICAgIDxvcHRpb24gdmFsdWU9IlNJUCI+U0lQIChTeXN0ZW1hdGljIEludmVzdG1lbnQgUGxhbik8L29wdGlvbj4KICAgICAgICAgICAgICAgICAgICA8b3B0aW9uIHZhbHVlPSJTdG9ja3MiPlN0b2NrcyAvIEVxdWl0eTwvb3B0aW9uPgogICAgICAgICAgICAgICAgICAgIDxvcHRpb24gdmFsdWU9Ik11dHVhbCBGdW5kIj5NdXR1YWwgRnVuZDwvb3B0aW9uPgogICAgICAgICAgICAgICAgICAgIDxvcHRpb24gdmFsdWU9IkZEIj5GaXhlZCBEZXBvc2l0IChGRCk8L29wdGlvbj4KICAgICAgICAgICAgICAgICAgICA8b3B0aW9uIHZhbHVlPSJSRCI+UmVjdXJyaW5nIERlcG9zaXQgKFJEKTwvb3B0aW9uPgogICAgICAgICAgICAgICAgICAgIDxvcHRpb24gdmFsdWU9IkNyeXB0byI+Q3J5cHRvPC9vcHRpb24+CiAgICAgICAgICAgICAgICAgICAgPG9wdGlvbiB2YWx1ZT0iR29sZCI+R29sZCAvIFNpbHZlcjwvb3B0aW9uPgogICAgICAgICAgICAgICAgICAgIDxvcHRpb24gdmFsdWU9IlJlYWwgRXN0YXRlIj5SZWFsIEVzdGF0ZTwvb3B0aW9uPgogICAgICAgICAgICAgICAgICAgIDxvcHRpb24gdmFsdWU9IkdlbmVyYWwiIHNlbGVjdGVkPkdlbmVyYWw8L29wdGlvbj4KICAgICAgICAgICAgICAgICAgPC9zZWxlY3Q+CiAgICAgICAgICAgICAgICA8L2Rpdj4KCiAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJjb2wtbWQtNiI+CiAgICAgICAgICAgICAgICAgIDxsYWJlbCBmb3I9ImludmVzdC1hbW91bnQiIGNsYXNzPSJmb3JtLWxhYmVsIiBzdHlsZT0iZm9udC13ZWlnaHQ6IDYwMDsiPkFtb3VudCBJbnZlc3RlZCAo4oK5KTwvbGFiZWw+CiAgICAgICAgICAgICAgICAgIDxkaXYgY2xhc3M9ImlucHV0LWdyb3VwIj4KICAgICAgICAgICAgICAgICAgICA8c3BhbiBjbGFzcz0iaW5wdXQtZ3JvdXAtdGV4dCI+4oK5PC9zcGFuPgogICAgICAgICAgICAgICAgICAgIDxpbnB1dCB0eXBlPSJudW1iZXIiIGlkPSJpbnZlc3QtYW1vdW50IiBuYW1lPSJhbW91bnQiIGNsYXNzPSJmb3JtLWNvbnRyb2wiIHBsYWNlaG9sZGVyPSIwLjAwIiBzdGVwPSIwLjAxIiBtaW49IjAuMDEiIHJlcXVpcmVkPgogICAgICAgICAgICAgICAgICA8L2Rpdj4KICAgICAgICAgICAgICAgIDwvZGl2PgoKICAgICAgICAgICAgICAgIDxkaXYgY2xhc3M9ImNvbC1tZC02Ij4KICAgICAgICAgICAgICAgICAgPGxhYmVsIGZvcj0iaW52ZXN0LWRhdGUiIGNsYXNzPSJmb3JtLWxhYmVsIiBzdHlsZT0iZm9udC13ZWlnaHQ6IDYwMDsiPkRhdGUgb2YgSW52ZXN0bWVudDwvbGFiZWw+CiAgICAgICAgICAgICAgICAgIDxpbnB1dCB0eXBlPSJkYXRlIiBpZD0iaW52ZXN0LWRhdGUiIG5hbWU9ImludmVzdF9kYXRlIiBjbGFzcz0iZm9ybS1jb250cm9sIiByZXF1aXJlZD4KICAgICAgICAgICAgICAgIDwvZGl2PgoKICAgICAgICAgICAgICAgIDxkaXYgY2xhc3M9ImNvbC0xMiI+CiAgICAgICAgICAgICAgICAgIDxsYWJlbCBmb3I9ImludmVzdC1ub3RlcyIgY2xhc3M9ImZvcm0tbGFiZWwiIHN0eWxlPSJmb250LXdlaWdodDogNjAwOyI+Tm90ZXMgKG9wdGlvbmFsKTwvbGFiZWw+CiAgICAgICAgICAgICAgICAgIDx0ZXh0YXJlYSBpZD0iaW52ZXN0LW5vdGVzIiBuYW1lPSJub3RlcyIgY2xhc3M9ImZvcm0tY29udHJvbCIgcGxhY2Vob2xkZXI9ImUuZy4gTW9udGhseSBTSVAgZm9yIE5JRlRZIDUwIGluZGV4IGZ1bmQuLi4iIHJvd3M9IjMiPjwvdGV4dGFyZWE+CiAgICAgICAgICAgICAgICA8L2Rpdj4KCiAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJjb2wtMTIgbXQtNCI+CiAgICAgICAgICAgICAgICAgIDxidXR0b24gdHlwZT0ic3VibWl0IiBpZD0ic2F2ZS1pbnZlc3QtYnRuIiBjbGFzcz0iYnRuIGJ0bi1wcmltYXJ5IHB4LTQgcHktMiIgc3R5bGU9ImJvcmRlci1yYWRpdXM6IDEwcHg7Ij4KICAgICAgICAgICAgICAgICAgICA8aSBjbGFzcz0iYmkgYmktcGx1cy1jaXJjbGUtZmlsbCBtZS0xIj48L2k+IFNhdmUgSW52ZXN0bWVudAogICAgICAgICAgICAgICAgICA8L2J1dHRvbj4KICAgICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICA8L2Zvcm0+CiAgICAgICAgICA8L2Rpdj4KICAgICAgICA8L2Rpdj4KCiAgICAgICAgPCEtLSBIaXN0b3J5IFNpZGViYXIgLS0+CiAgICAgICAgPGRpdiBjbGFzcz0iY29sLWxnLTQiPgogICAgICAgICAgPGRpdiBjbGFzcz0icHJldmlldy1wYW5lbCI+CiAgICAgICAgICAgIDxoNCBjbGFzcz0icHJldmlldy10aXRsZSI+PGkgY2xhc3M9ImJpIGJpLWNsb2NrLWhpc3RvcnkgdGV4dC1wcmltYXJ5Ij48L2k+IFJlY2VudCBJbnZlc3RtZW50czwvaDQ+CiAgICAgICAgICAgIDxkaXYgaWQ9InJlY2VudC1pbnZlc3RtZW50LWxpc3QiIHN0eWxlPSJkaXNwbGF5OiBmbGV4OyBmbGV4LWRpcmVjdGlvbjogY29sdW1uOyBnYXA6IDEycHg7IG1hcmdpbi10b3A6IDE1cHg7Ij4KICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJ0ZXh0LWNlbnRlciB0ZXh0LW11dGVkIHB5LTQiPkxvYWRpbmcgZW50cmllcy4uLjwvZGl2PgogICAgICAgICAgICA8L2Rpdj4KICAgICAgICAgIDwvZGl2PgogICAgICAgIDwvZGl2PgogICAgICA8L2Rpdj4KICAgIDwvZGl2PgogIDwvbWFpbj4KPC9kaXY+Cgo8c2NyaXB0IHNyYz0iaHR0cHM6Ly9jZG4uanNkZWxpdnIubmV0L25wbS9ib290c3RyYXBANS4zLjMvZGlzdC9qcy9ib290c3RyYXAuYnVuZGxlLm1pbi5qcyI+PC9zY3JpcHQ+CjxzY3JpcHQgc3JjPSJ7eyB1cmxfZm9yKCdzdGF0aWMnLCBmaWxlbmFtZT0nanMvY3Vyc29yLmpzJykgfX0iPjwvc2NyaXB0Pgo8c2NyaXB0PgogIGRvY3VtZW50LmFkZEV2ZW50TGlzdGVuZXIoJ0RPTUNvbnRlbnRMb2FkZWQnLCAoKSA9PiB7CiAgICBmZXRjaCgnL2FwaS9yZWNlbnQtdHJhbnNhY3Rpb25zJykKICAgICAgLnRoZW4ociA9PiByLmpzb24oKSkKICAgICAgLnRoZW4oZGF0YSA9PiB7CiAgICAgICAgY29uc3QgbGlzdCA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCdyZWNlbnQtaW52ZXN0bWVudC1saXN0Jyk7CiAgICAgICAgbGlzdC5pbm5lckhUTUwgPSAnJzsKICAgICAgICBjb25zdCBpbnZlc3RtZW50cyA9IGRhdGEuZmlsdGVyKHQgPT4gdC50eXBlID09PSAnaW52ZXN0bWVudCcpOwogICAgICAgIGlmIChpbnZlc3RtZW50cy5sZW5ndGggPT09IDApIHsKICAgICAgICAgIGxpc3QuaW5uZXJIVE1MID0gJzxkaXYgY2xhc3M9InRleHQtY2VudGVyIHRleHQtbXV0ZWQgcHktMyI+Tm8gcmVjZW50IGludmVzdG1lbnRzIGZvdW5kLjwvZGl2Pic7CiAgICAgICAgICByZXR1cm47CiAgICAgICAgfQogICAgICAgIGludmVzdG1lbnRzLnNsaWNlKDAsIDUpLmZvckVhY2goaW52ID0+IHsKICAgICAgICAgIGNvbnN0IGl0ZW0gPSBkb2N1bWVudC5jcmVhdGVFbGVtZW50KCdkaXYnKTsKICAgICAgICAgIGl0ZW0uY2xhc3NOYW1lID0gJ3ByZXZpZXctcm93JzsKICAgICAgICAgIGl0ZW0uaW5uZXJIVE1MID0gYAogICAgICAgICAgICA8ZGl2IHN0eWxlPSJkaXNwbGF5OiBmbGV4OyBmbGV4LWRpcmVjdGlvbjogY29sdW1uOyI+CiAgICAgICAgICAgICAgPHNwYW4gY2xhc3M9InByZXZpZXctbGFiZWwiIHN0eWxlPSJjb2xvcjogdmFyKC0tdGV4dC1kYXJrKTsgZm9udC13ZWlnaHQ6IDYwMDsiPiR7aW52LnRpdGxlIHx8IGludi5jYXRlZ29yeX08L3NwYW4+CiAgICAgICAgICAgICAgPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZTogMC43NXJlbTsgY29sb3I6IHZhcigtLXRleHQtbXV0ZWQpOyI+JHtpbnYuZGF0ZX08L3NwYW4+CiAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICA8c3BhbiBjbGFzcz0icHJldmlldy12YWx1ZSB0ZXh0LXByaW1hcnkiPuKCuSR7KGludi5hbW91bnQgfHwgMCkudG9Mb2NhbGVTdHJpbmcoJ2VuLUlOJyl9PC9zcGFuPgogICAgICAgICAgYDsKICAgICAgICAgIGxpc3QuYXBwZW5kQ2hpbGQoaXRlbSk7CiAgICAgICAgfSk7CiAgICAgIH0pCiAgICAgIC5jYXRjaCgoKSA9PiB7CiAgICAgICAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ3JlY2VudC1pbnZlc3RtZW50LWxpc3QnKS5pbm5lckhUTUwgPSAnPGRpdiBjbGFzcz0idGV4dC1jZW50ZXIgdGV4dC1tdXRlZCBweS0zIj5GYWlsZWQgdG8gbG9hZCBlbnRyaWVzLjwvZGl2Pic7CiAgICAgIH0pOwogIH0pOwo8L3NjcmlwdD4KPC9ib2R5Pgo8L2h0bWw+').decode('utf-8'),
    'transactions.html': base64.b64decode('PCFkb2N0eXBlIGh0bWw+CjxodG1sIGxhbmc9ImVuIj4KPGhlYWQ+CiAgPG1ldGEgY2hhcnNldD0idXRmLTgiPgogIDxtZXRhIG5hbWU9InZpZXdwb3J0IiBjb250ZW50PSJ3aWR0aD1kZXZpY2Utd2lkdGgsIGluaXRpYWwtc2NhbGU9MSI+CiAgPHRpdGxlPlRyYW5zYWN0aW9ucyDigJMgRmluU2lnaHQ8L3RpdGxlPgogIDxsaW5rIHJlbD0icHJlY29ubmVjdCIgaHJlZj0iaHR0cHM6Ly9mb250cy5nb29nbGVhcGlzLmNvbSI+CiAgPGxpbmsgcmVsPSJwcmVjb25uZWN0IiBocmVmPSJodHRwczovL2ZvbnRzLmdzdGF0aWMuY29tIiBjcm9zc29yaWdpbj4KICA8bGluayBocmVmPSJodHRwczovL2ZvbnRzLmdvb2dsZWFwaXMuY29tL2NzczI/ZmFtaWx5PUludGVyOndnaHRANDAwOzUwMDs2MDA7NzAwOzgwMCZkaXNwbGF5PXN3YXAiIHJlbD0ic3R5bGVzaGVldCI+CiAgPGxpbmsgaHJlZj0iaHR0cHM6Ly9jZG4uanNkZWxpdnIubmV0L25wbS9ib290c3RyYXBANS4zLjMvZGlzdC9jc3MvYm9vdHN0cmFwLm1pbi5jc3MiIHJlbD0ic3R5bGVzaGVldCI+CiAgPGxpbmsgcmVsPSJzdHlsZXNoZWV0IiBocmVmPSJodHRwczovL2Nkbi5qc2RlbGl2ci5uZXQvbnBtL2Jvb3RzdHJhcC1pY29uc0AxLjExLjMvZm9udC9ib290c3RyYXAtaWNvbnMuY3NzIj4KICA8bGluayByZWw9InN0eWxlc2hlZXQiIGhyZWY9Int7IHVybF9mb3IoJ3N0YXRpYycsIGZpbGVuYW1lPSdjc3MvZGFzaGJvYXJkLmNzcycpIH19Ij4KICA8bGluayByZWw9InN0eWxlc2hlZXQiIGhyZWY9Int7IHVybF9mb3IoJ3N0YXRpYycsIGZpbGVuYW1lPSdjc3MvcGFnZXMuY3NzJykgfX0iPgogIDxsaW5rIHJlbD0ic3R5bGVzaGVldCIgaHJlZj0ie3sgdXJsX2Zvcignc3RhdGljJywgZmlsZW5hbWU9J2Nzcy9jdXJzb3IuY3NzJykgfX0iPgogIDxzdHlsZT4KICAgIC5zZWFyY2gtZmlsdGVyLXJvdyB7CiAgICAgIGRpc3BsYXk6IGZsZXg7CiAgICAgIGp1c3RpZnktY29udGVudDogc3BhY2UtYmV0d2VlbjsKICAgICAgYWxpZ24taXRlbXM6IGNlbnRlcjsKICAgICAgZ2FwOiAxNnB4OwogICAgICBtYXJnaW4tYm90dG9tOiAyMHB4OwogICAgICBmbGV4LXdyYXA6IHdyYXA7CiAgICB9CiAgICAuc2VhcmNoLWlucHV0LWdyb3VwIHsKICAgICAgcG9zaXRpb246IHJlbGF0aXZlOwogICAgICBmbGV4OiAxOwogICAgICBtYXgtd2lkdGg6IDQwMHB4OwogICAgICBtaW4td2lkdGg6IDI1MHB4OwogICAgfQogICAgLnNlYXJjaC1pbnB1dC1ncm91cCBpIHsKICAgICAgcG9zaXRpb246IGFic29sdXRlOwogICAgICBsZWZ0OiAxNHB4OwogICAgICB0b3A6IDUwJTsKICAgICAgdHJhbnNmb3JtOiB0cmFuc2xhdGVZKC01MCUpOwogICAgICBjb2xvcjogIzk0QTNCODsKICAgICAgZm9udC1zaXplOiAxLjFyZW07CiAgICB9CiAgICAuc2VhcmNoLWlucHV0LWdyb3VwIGlucHV0IHsKICAgICAgcGFkZGluZy1sZWZ0OiA0MnB4OwogICAgICBib3JkZXItcmFkaXVzOiAxMHB4OwogICAgICBib3JkZXI6IDFweCBzb2xpZCAjQ0JENUUxOwogICAgICBoZWlnaHQ6IDQycHg7CiAgICAgIGZvbnQtc2l6ZTogMC44OHJlbTsKICAgIH0KICAgIC5zZWFyY2gtaW5wdXQtZ3JvdXAgaW5wdXQ6Zm9jdXMgewogICAgICBib3JkZXItY29sb3I6ICM2MzY2RjE7CiAgICAgIGJveC1zaGFkb3c6IDAgMCAwIDNweCByZ2JhKDk5LCAxMDIsIDI0MSwgMC4xNSk7CiAgICB9CiAgICAuZmlsdGVyLWJ0bi1ncm91cCB7CiAgICAgIGRpc3BsYXk6IGZsZXg7CiAgICAgIGdhcDogOHB4OwogICAgfQogICAgLmZpbHRlci1idG4gewogICAgICBwYWRkaW5nOiA4cHggMTZweDsKICAgICAgYm9yZGVyLXJhZGl1czogOHB4OwogICAgICBmb250LXNpemU6IDAuODVyZW07CiAgICAgIGZvbnQtd2VpZ2h0OiA2MDA7CiAgICAgIGJvcmRlcjogMXB4IHNvbGlkICNFMkU4RjA7CiAgICAgIGJhY2tncm91bmQ6IHZhcigtLXdoaXRlKTsKICAgICAgY29sb3I6IHZhcigtLXRleHQtbXV0ZWQpOwogICAgICBjdXJzb3I6IHBvaW50ZXI7CiAgICAgIHRyYW5zaXRpb246IGFsbCAwLjJzOwogICAgfQogICAgLmZpbHRlci1idG46aG92ZXIgewogICAgICBiYWNrZ3JvdW5kOiAjRjhGQUZDOwogICAgICBjb2xvcjogdmFyKC0tdGV4dC1kYXJrKTsKICAgIH0KICAgIC5maWx0ZXItYnRuLmFjdGl2ZSB7CiAgICAgIGJhY2tncm91bmQ6ICM2MzY2RjE7CiAgICAgIGJvcmRlci1jb2xvcjogIzYzNjZGMTsKICAgICAgY29sb3I6IHdoaXRlOwogICAgfQogICAgLnR4bi10YWJsZS1jYXJkIHsKICAgICAgYmFja2dyb3VuZDogdmFyKC0td2hpdGUpOwogICAgICBib3JkZXItcmFkaXVzOiB2YXIoLS1ib3JkZXItcmFkaXVzLWNhcmQpOwogICAgICBib3JkZXI6IDFweCBzb2xpZCAjRTJFOEYwOwogICAgICBib3gtc2hhZG93OiB2YXIoLS1zaGFkb3cpOwogICAgICBwYWRkaW5nOiAwOwogICAgICBvdmVyZmxvdzogaGlkZGVuOwogICAgfQogICAgLnR4bi10YWJsZSB7CiAgICAgIHdpZHRoOiAxMDAlOwogICAgICBtYXJnaW46IDA7CiAgICB9CiAgICAudHhuLXRhYmxlIHRoIHsKICAgICAgYmFja2dyb3VuZDogI0Y4RkFGQzsKICAgICAgZm9udC1zaXplOiAwLjc4cmVtOwogICAgICBmb250LXdlaWdodDogNzAwOwogICAgICB0ZXh0LXRyYW5zZm9ybTogdXBwZXJjYXNlOwogICAgICBsZXR0ZXItc3BhY2luZzogMC4wNWVtOwogICAgICBjb2xvcjogIzQ3NTU2OTsKICAgICAgcGFkZGluZzogMTRweCAyMHB4OwogICAgICBib3JkZXItYm90dG9tOiAxcHggc29saWQgI0UyRThGMDsKICAgIH0KICAgIC50eG4tdGFibGUgdGQgewogICAgICBwYWRkaW5nOiAxNnB4IDIwcHg7CiAgICAgIHZlcnRpY2FsLWFsaWduOiBtaWRkbGU7CiAgICAgIGJvcmRlci1ib3R0b206IDFweCBzb2xpZCAjRjFGNUY5OwogICAgICBmb250LXNpemU6IDAuODhyZW07CiAgICB9CiAgICAudHlwZS1iYWRnZSB7CiAgICAgIGRpc3BsYXk6IGlubGluZS1mbGV4OwogICAgICBhbGlnbi1pdGVtczogY2VudGVyOwogICAgICBnYXA6IDZweDsKICAgICAgcGFkZGluZzogNHB4IDEwcHg7CiAgICAgIGJvcmRlci1yYWRpdXM6IDk5cHg7CiAgICAgIGZvbnQtc2l6ZTogMC43OHJlbTsKICAgICAgZm9udC13ZWlnaHQ6IDYwMDsKICAgIH0KICAgIC5iYWRnZS1pbmNvbWUgewogICAgICBiYWNrZ3JvdW5kOiByZ2JhKDE2LCAxODUsIDEyOSwgMC4xKTsKICAgICAgY29sb3I6ICMxMEI5ODE7CiAgICB9CiAgICAuYmFkZ2UtZXhwZW5zZSB7CiAgICAgIGJhY2tncm91bmQ6IHJnYmEoMjQ5LCAxMTUsIDIyLCAwLjEpOwogICAgICBjb2xvcjogI0Y5NzMxNjsKICAgIH0KICAgIC5iYWRnZS1pbnZlc3RtZW50IHsKICAgICAgYmFja2dyb3VuZDogcmdiYSgxMzksIDkyLCAyNDYsIDAuMSk7CiAgICAgIGNvbG9yOiAjOEI1Q0Y2OwogICAgfQogICAgLnR4bi1hbW91bnQgewogICAgICBmb250LXdlaWdodDogNzAwOwogICAgICBmb250LXNpemU6IDAuOTVyZW07CiAgICB9CiAgICAuYW1vdW50LXBvc2l0aXZlIHsKICAgICAgY29sb3I6ICMxMEI5ODE7CiAgICB9CiAgICAuYW1vdW50LW5lZ2F0aXZlIHsKICAgICAgY29sb3I6ICNFRjQ0NDQ7CiAgICB9CiAgICAuZW1wdHktc3RhdGUgewogICAgICB0ZXh0LWFsaWduOiBjZW50ZXI7CiAgICAgIHBhZGRpbmc6IDYwcHggMjBweDsKICAgICAgY29sb3I6ICM2NDc0OEI7CiAgICB9CiAgICAuZW1wdHktc3RhdGUgaSB7CiAgICAgIGZvbnQtc2l6ZTogM3JlbTsKICAgICAgY29sb3I6ICNDQkQ1RTE7CiAgICAgIG1hcmdpbi1ib3R0b206IDE2cHg7CiAgICAgIGRpc3BsYXk6IGJsb2NrOwogICAgfQogIDwvc3R5bGU+CjwvaGVhZD4KPGJvZHkgY2xhc3M9InRoZW1lLWRhc2giPgo8ZGl2IGlkPSJjdXJzb3ItZG90Ij48L2Rpdj4KPGRpdiBpZD0iY3Vyc29yLXJpbmciPjwvZGl2PgoKPCEtLSBQcm9maWxlIENoaXAgLS0+CjxhIGhyZWY9Int7IHVybF9mb3IoJ3Byb2ZpbGVfcGFnZScpIH19IiBjbGFzcz0icHJvZmlsZS1jaGlwLWdsb2JhbCIgdGl0bGU9IlZpZXcgUHJvZmlsZSI+CiAgPGRpdiBjbGFzcz0icHJvZmlsZS1jaGlwLWF2YXRhciI+e3sgdXNlcl9uYW1lWzBdfHVwcGVyIGlmIHVzZXJfbmFtZSBlbHNlICdBJyB9fTwvZGl2PgogIDxkaXYgY2xhc3M9InByb2ZpbGUtY2hpcC1pbmZvIj4KICAgIDxzcGFuIGNsYXNzPSJwcm9maWxlLWNoaXAtbmFtZSI+e3sgdXNlcl9uYW1lIGlmIHVzZXJfbmFtZSBlbHNlICdBcmp1biBNZWh0YScgfX08L3NwYW4+CiAgPC9kaXY+CjwvYT4KCjxidXR0b24gY2xhc3M9ImZsb2F0aW5nLWhhbWJ1cmdlciIgaWQ9InNpZGViYXItdG9nZ2xlLWJ0biIgdHlwZT0iYnV0dG9uIiB0aXRsZT0iVG9nZ2xlIFNpZGViYXIgTWVudSI+CiAgPGkgY2xhc3M9ImJpIGJpLWxpc3QiPjwvaT4KPC9idXR0b24+Cgo8ZGl2IGNsYXNzPSJkLWZsZXgiPgoKICA8IS0tIExlZnQgU2lkZWJhciAtLT4KICA8YXNpZGUgY2xhc3M9InNpZGViYXIiIGlkPSJzaWRlYmFyIj4KICAgIDxkaXYgY2xhc3M9ImxvZ28tcm93Ij4KICAgICAgPGltZyBzcmM9Int7IHVybF9mb3IoJ3N0YXRpYycsIGZpbGVuYW1lPSdpbWFnZXMvbG9nby5qcGVnJykgfX0iIGFsdD0iRmluU2lnaHQgTG9nbyIgY2xhc3M9ImRhc2gtbmF2LWxvZ28taW1nIiBzdHlsZT0id2lkdGg6NDJweDtoZWlnaHQ6NDJweDsiPgogICAgICA8ZGl2IGNsYXNzPSJsb2dvLXRleHQiPgogICAgICAgIDxoMz5GaW5TaWdodDwvaDM+CiAgICAgICAgPHNtYWxsPlNtYXJ0LiBTZWN1cmUuIFNpbXBsZS48L3NtYWxsPgogICAgICA8L2Rpdj4KICAgIDwvZGl2PgogICAgPG5hdiBjbGFzcz0ibmF2LWxpc3QiPgogICAgICA8YSBocmVmPSJ7eyB1cmxfZm9yKCdkYXNoYm9hcmQnKSB9fSIgY2xhc3M9Im5hdi1pdGVtIj48aSBjbGFzcz0iYmkgYmktZ3JpZCI+PC9pPjxzcGFuPkRhc2hib2FyZDwvc3Bhbj48L2E+CiAgICAgIDxhIGhyZWY9Int7IHVybF9mb3IoJ2ZpbmFuY2VzJykgfX0iIGNsYXNzPSJuYXYtaXRlbSI+PGkgY2xhc3M9ImJpIGJpLXdhbGxldDIiPjwvaT48c3Bhbj5GaW5hbmNlczwvc3Bhbj48L2E+CiAgICAgIDxhIGhyZWY9Int7IHVybF9mb3IoJ2FkZF9pbnZlc3RtZW50JykgfX0iIGNsYXNzPSJuYXYtaXRlbSI+PGkgY2xhc3M9ImJpIGJpLWdyYXBoLXVwLWFycm93Ij48L2k+PHNwYW4+SW52ZXN0bWVudHM8L3NwYW4+PC9hPgogICAgICA8YSBocmVmPSJ7eyB1cmxfZm9yKCdnb2Fsc19saXN0JykgfX0iIGNsYXNzPSJuYXYtaXRlbSI+PGkgY2xhc3M9ImJpIGJpLWZsYWciPjwvaT48c3Bhbj5Hb2Fsczwvc3Bhbj48L2E+CiAgICAgICAgICAgIDxhIGhyZWY9Int7IHVybF9mb3IoJ2hlYWx0aF9zY29yZV9wYWdlJykgfX0iIGNsYXNzPSJuYXYtaXRlbSI+PGkgY2xhc3M9ImJpIGJpLWhlYXJ0LXB1bHNlIj48L2k+PHNwYW4+SGVhbHRoIFNjb3JlPC9zcGFuPjwvYT4KICAgICAgPGEgaHJlZj0ie3sgdXJsX2ZvcigndHJhbnNhY3Rpb25zX3BhZ2UnKSB9fSIgY2xhc3M9Im5hdi1pdGVtIGFjdGl2ZSI+PGkgY2xhc3M9ImJpIGJpLWFycm93LWxlZnQtcmlnaHQiPjwvaT48c3Bhbj5UcmFuc2FjdGlvbnM8L3NwYW4+PC9hPgogICAgICA8YSBocmVmPSJ7eyB1cmxfZm9yKCdhaV9pbnNpZ2h0cycpIH19IiBjbGFzcz0ibmF2LWl0ZW0iPjxpIGNsYXNzPSJiaSBiaS1yb2JvdCI+PC9pPjxzcGFuPkFJIEluc2lnaHRzPC9zcGFuPjwvYT4KICAgICAgPGEgaHJlZj0ie3sgdXJsX2ZvcigncHJvZmlsZV9wYWdlJykgfX0iIGNsYXNzPSJuYXYtaXRlbSI+PGkgY2xhc3M9ImJpIGJpLXBlcnNvbi1jaXJjbGUiPjwvaT48c3Bhbj5Qcm9maWxlPC9zcGFuPjwvYT4KICAgIDwvbmF2PgogICAgCiAgICA8YnV0dG9uIGNsYXNzPSJzaWRlYmFyLXJlc2V0LWJ0biIgaWQ9InNpZGViYXItcmVzZXQtYnRuIiB0eXBlPSJidXR0b24iIG9uY2xpY2s9ImlmKGNvbmZpcm0oJ0FyZSB5b3Ugc3VyZSB5b3Ugd2FudCB0byByZXNldCBhbGwgZGF0YSB0byAwPycpKSB7IGZldGNoKCcvYXBpL3Jlc2V0LWRhdGEnLCB7bWV0aG9kOiAnUE9TVCd9KS50aGVuKCgpID0+IHsgd2luZG93LmxvY2F0aW9uLmhyZWY9Jy9kYXNoYm9hcmQnOyB9KTsgfSIgdGl0bGU9IlJlc2V0IGFsbCBkYXRhIHRvIDAiPgogICAgICA8aSBjbGFzcz0iYmkgYmktdHJhc2giPjwvaT48c3Bhbj5SZXNldCBEYXRhPC9zcGFuPgogICAgPC9idXR0b24+CiAgICA8YSBocmVmPSJ7eyB1cmxfZm9yKCdsb2dvdXQnKSB9fSIgY2xhc3M9InNpZGViYXItbG9nb3V0LWJ0biIgdGl0bGU9IkxvZ291dCBmcm9tIHNlc3Npb24iPgogICAgICA8aSBjbGFzcz0iYmkgYmktYm94LWFycm93LXJpZ2h0Ij48L2k+PHNwYW4+TG9nb3V0PC9zcGFuPgogICAgPC9hPgogIDwvYXNpZGU+CgogIDwhLS0gTWFpbiBQYW5lbCAtLT4KICA8bWFpbiBjbGFzcz0ibWFpbi1wYW5lbCI+CiAgICA8ZGl2IGNsYXNzPSJjb250ZW50LXN0YWNrIj4KCiAgICAgIDwhLS0gUGFnZSBIZXJvIC0tPgogICAgICA8ZGl2IGNsYXNzPSJwYWdlLWhlcm8gaW52ZXN0LWhlcm8iPgogICAgICAgIDxkaXYgY2xhc3M9Imhlcm8tbGVmdCI+CiAgICAgICAgICA8ZGl2IGNsYXNzPSJoZXJvLWljb24td3JhcCBmaW5hbmNlcy1pY29uLXdyYXAiIHN0eWxlPSJiYWNrZ3JvdW5kOiByZ2JhKDI1NSwyNTUsMjU1LDAuMjUpOyI+CiAgICAgICAgICAgIDxpIGNsYXNzPSJiaSBiaS1hcnJvdy1sZWZ0LXJpZ2h0IHRleHQtd2hpdGUiPjwvaT4KICAgICAgICAgIDwvZGl2PgogICAgICAgICAgPGRpdj4KICAgICAgICAgICAgPGgxIGNsYXNzPSJoZXJvLXRpdGxlIj5UcmFuc2FjdGlvbnM8L2gxPgogICAgICAgICAgICA8cCBjbGFzcz0iaGVyby1zdWJ0aXRsZSI+Q29tcGxldGUgdGltZWxpbmUgb2YgeW91ciBpbmNvbWUsIGV4cGVuc2UsIGFuZCBpbnZlc3RtZW50IGVudHJpZXM8L3A+CiAgICAgICAgICA8L2Rpdj4KICAgICAgICA8L2Rpdj4KICAgICAgPC9kaXY+CgogICAgICA8ZGl2IGNsYXNzPSJzZWFyY2gtZmlsdGVyLXJvdyBtdC00Ij4KICAgICAgICA8IS0tIFNlYXJjaCBJbnB1dCAtLT4KICAgICAgICA8ZGl2IGNsYXNzPSJzZWFyY2gtaW5wdXQtZ3JvdXAiPgogICAgICAgICAgPGkgY2xhc3M9ImJpIGJpLXNlYXJjaCI+PC9pPgogICAgICAgICAgPGlucHV0IHR5cGU9InRleHQiIGNsYXNzPSJmb3JtLWNvbnRyb2wiIGlkPSJ0eG4tc2VhcmNoIiBwbGFjZWhvbGRlcj0iU2VhcmNoIGJ5IGRlc2NyaXB0aW9uIG9yIGNhdGVnb3J5Li4uIiBvbmlucHV0PSJmaWx0ZXJUcmFuc2FjdGlvbnMoKSI+CiAgICAgICAgPC9kaXY+CgogICAgICAgIDwhLS0gRmlsdGVyIEJ1dHRvbnMgLS0+CiAgICAgICAgPGRpdiBjbGFzcz0iZmlsdGVyLWJ0bi1ncm91cCI+CiAgICAgICAgICA8YnV0dG9uIGNsYXNzPSJmaWx0ZXItYnRuIGFjdGl2ZSIgaWQ9ImZpbHRlci1hbGwiIG9uY2xpY2s9InNldEZpbHRlcignYWxsJykiPkFsbDwvYnV0dG9uPgogICAgICAgICAgPGJ1dHRvbiBjbGFzcz0iZmlsdGVyLWJ0biIgaWQ9ImZpbHRlci1pbmNvbWUiIG9uY2xpY2s9InNldEZpbHRlcignaW5jb21lJykiPkluY29tZTwvYnV0dG9uPgogICAgICAgICAgPGJ1dHRvbiBjbGFzcz0iZmlsdGVyLWJ0biIgaWQ9ImZpbHRlci1leHBlbnNlIiBvbmNsaWNrPSJzZXRGaWx0ZXIoJ2V4cGVuc2UnKSI+RXhwZW5zZXM8L2J1dHRvbj4KICAgICAgICAgIDxidXR0b24gY2xhc3M9ImZpbHRlci1idG4iIGlkPSJmaWx0ZXItaW52ZXN0bWVudCIgb25jbGljaz0ic2V0RmlsdGVyKCdpbnZlc3RtZW50JykiPkludmVzdG1lbnRzPC9idXR0b24+CiAgICAgICAgPC9kaXY+CiAgICAgIDwvZGl2PgoKICAgICAgPCEtLSBUcmFuc2FjdGlvbnMgVGFibGUgLS0+CiAgICAgIDxkaXYgY2xhc3M9InR4bi10YWJsZS1jYXJkIj4KICAgICAgICA8ZGl2IGNsYXNzPSJ0YWJsZS1yZXNwb25zaXZlIj4KICAgICAgICAgIDx0YWJsZSBjbGFzcz0idGFibGUgdHhuLXRhYmxlIHRhYmxlLWhvdmVyIGFsaWduLW1pZGRsZSI+CiAgICAgICAgICAgIDx0aGVhZD4KICAgICAgICAgICAgICA8dHI+CiAgICAgICAgICAgICAgICA8dGg+RGF0ZTwvdGg+CiAgICAgICAgICAgICAgICA8dGg+VHlwZTwvdGg+CiAgICAgICAgICAgICAgICA8dGg+RGVzY3JpcHRpb248L3RoPgogICAgICAgICAgICAgICAgPHRoPkNhdGVnb3J5IC8gU291cmNlPC90aD4KICAgICAgICAgICAgICAgIDx0aCBjbGFzcz0idGV4dC1lbmQiPkFtb3VudDwvdGg+CiAgICAgICAgICAgICAgPC90cj4KICAgICAgICAgICAgPC90aGVhZD4KICAgICAgICAgICAgPHRib2R5IGlkPSJ0eG4tdGJvZHkiPgogICAgICAgICAgICAgIHslIGlmIHRyYW5zYWN0aW9ucyAlfQogICAgICAgICAgICAgICAgeyUgZm9yIHQgaW4gdHJhbnNhY3Rpb25zICV9CiAgICAgICAgICAgICAgICAgIDx0ciBjbGFzcz0idHhuLXJvdyIgZGF0YS10eXBlPSJ7eyB0LnR5cGUgfX0iIGRhdGEtdGl0bGU9Int7IHQudGl0bGV8bG93ZXIgfX0iIGRhdGEtY2F0PSJ7eyB0LmNhdGVnb3J5fGxvd2VyIH19Ij4KICAgICAgICAgICAgICAgICAgICA8dGQgY2xhc3M9InRleHQtbXV0ZWQiIHN0eWxlPSJmb250LXdlaWdodDogNTAwOyI+e3sgdC5kYXRlIH19PC90ZD4KICAgICAgICAgICAgICAgICAgICA8dGQ+CiAgICAgICAgICAgICAgICAgICAgICB7JSBpZiB0LnR5cGUgPT0gJ2luY29tZScgJX0KICAgICAgICAgICAgICAgICAgICAgICAgPHNwYW4gY2xhc3M9InR5cGUtYmFkZ2UgYmFkZ2UtaW5jb21lIj48aSBjbGFzcz0iYmkgYmktYXJyb3ctZG93bi1sZWZ0LWNpcmNsZS1maWxsIj48L2k+IEluY29tZTwvc3Bhbj4KICAgICAgICAgICAgICAgICAgICAgIHslIGVsaWYgdC50eXBlID09ICdleHBlbnNlJyAlfQogICAgICAgICAgICAgICAgICAgICAgICA8c3BhbiBjbGFzcz0idHlwZS1iYWRnZSBiYWRnZS1leHBlbnNlIj48aSBjbGFzcz0iYmkgYmktYXJyb3ctdXAtcmlnaHQtY2lyY2xlLWZpbGwiPjwvaT4gRXhwZW5zZTwvc3Bhbj4KICAgICAgICAgICAgICAgICAgICAgIHslIGVsc2UgJX0KICAgICAgICAgICAgICAgICAgICAgICAgPHNwYW4gY2xhc3M9InR5cGUtYmFkZ2UgYmFkZ2UtaW52ZXN0bWVudCI+PGkgY2xhc3M9ImJpIGJpLWdyYXBoLXVwIj48L2k+IEludmVzdG1lbnQ8L3NwYW4+CiAgICAgICAgICAgICAgICAgICAgICB7JSBlbmRpZiAlfQogICAgICAgICAgICAgICAgICAgIDwvdGQ+CiAgICAgICAgICAgICAgICAgICAgPHRkIHN0eWxlPSJmb250LXdlaWdodDogNjAwOyBjb2xvcjogdmFyKC0tdGV4dC1kYXJrKTsiPnt7IHQudGl0bGUgfX08L3RkPgogICAgICAgICAgICAgICAgICAgIDx0ZCBjbGFzcz0idGV4dC1tdXRlZCI+e3sgdC5jYXRlZ29yeSB9fTwvdGQ+CiAgICAgICAgICAgICAgICAgICAgPHRkIGNsYXNzPSJ0ZXh0LWVuZCB0eG4tYW1vdW50IHt7ICdhbW91bnQtcG9zaXRpdmUnIGlmIHQudHlwZSA9PSAnaW5jb21lJyBlbHNlICdhbW91bnQtbmVnYXRpdmUnIH19Ij4KICAgICAgICAgICAgICAgICAgICAgIHt7ICcrJyBpZiB0LnR5cGUgPT0gJ2luY29tZScgZWxzZSAnLScgfX3igrl7eyAiezosLjJmfSIuZm9ybWF0KHQuYW1vdW50KSB9fQogICAgICAgICAgICAgICAgICAgIDwvdGQ+CiAgICAgICAgICAgICAgICAgIDwvdHI+CiAgICAgICAgICAgICAgICB7JSBlbmRmb3IgJX0KICAgICAgICAgICAgICB7JSBlbHNlICV9CiAgICAgICAgICAgICAgICA8dHIgaWQ9Im5vLXR4bi1yb3ciPgogICAgICAgICAgICAgICAgICA8dGQgY29sc3Bhbj0iNSIgY2xhc3M9InAtMCI+CiAgICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzcz0iZW1wdHktc3RhdGUiPgogICAgICAgICAgICAgICAgICAgICAgPGkgY2xhc3M9ImJpIGJpLXdhbGxldDIiPjwvaT4KICAgICAgICAgICAgICAgICAgICAgIDxoNT5ObyB0cmFuc2FjdGlvbnMgZm91bmQ8L2g1PgogICAgICAgICAgICAgICAgICAgICAgPHAgY2xhc3M9InRleHQtbXV0ZWQiPlN0YXJ0IGJ5IGFkZGluZyB5b3VyIGluY29tZSwgZXhwZW5zZXMgb3IgaW52ZXN0bWVudHMuPC9wPgogICAgICAgICAgICAgICAgICAgIDwvZGl2PgogICAgICAgICAgICAgICAgICA8L3RkPgogICAgICAgICAgICAgICAgPC90cj4KICAgICAgICAgICAgICB7JSBlbmRpZiAlfQogICAgICAgICAgICAgIDwhLS0gRmFsbGJhY2sgcm93IGZvciBkeW5hbWljIGZpbHRlcmluZyAtLT4KICAgICAgICAgICAgICA8dHIgaWQ9ImR5bmFtaWMtZW1wdHktcm93IiBzdHlsZT0iZGlzcGxheTogbm9uZTsiPgogICAgICAgICAgICAgICAgPHRkIGNvbHNwYW49IjUiIGNsYXNzPSJwLTAiPgogICAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzPSJlbXB0eS1zdGF0ZSI+CiAgICAgICAgICAgICAgICAgICAgPGkgY2xhc3M9ImJpIGJpLXNlYXJjaCI+PC9pPgogICAgICAgICAgICAgICAgICAgIDxoNT5ObyBtYXRjaGluZyB0cmFuc2FjdGlvbnMgZm91bmQ8L2g1PgogICAgICAgICAgICAgICAgICAgIDxwIGNsYXNzPSJ0ZXh0LW11dGVkIj5UcnkgYWRqdXN0aW5nIHlvdXIgc2VhcmNoIHF1ZXJ5IG9yIGZpbHRlciBvcHRpb25zLjwvcD4KICAgICAgICAgICAgICAgICAgPC9kaXY+CiAgICAgICAgICAgICAgICA8L3RkPgogICAgICAgICAgICAgIDwvdHI+CiAgICAgICAgICAgIDwvdGJvZHk+CiAgICAgICAgICA8L3RhYmxlPgogICAgICAgIDwvZGl2PgogICAgICA8L2Rpdj4KCiAgICA8L2Rpdj4KICA8L21haW4+CjwvZGl2PgoKPHNjcmlwdCBzcmM9Imh0dHBzOi8vY2RuLmpzZGVsaXZyLm5ldC9ucG0vYm9vdHN0cmFwQDUuMy4zL2Rpc3QvanMvYm9vdHN0cmFwLmJ1bmRsZS5taW4uanMiPjwvc2NyaXB0Pgo8c2NyaXB0IHNyYz0ie3sgdXJsX2Zvcignc3RhdGljJywgZmlsZW5hbWU9J2pzL2N1cnNvci5qcycpIH19Ij48L3NjcmlwdD4KPHNjcmlwdD4KICBsZXQgYWN0aXZlRmlsdGVyID0gJ2FsbCc7CgogIGZ1bmN0aW9uIHNldEZpbHRlcihmaWx0ZXIpIHsKICAgIGFjdGl2ZUZpbHRlciA9IGZpbHRlcjsKICAgIAogICAgLy8gVXBkYXRlIGJ1dHRvbiBhY3RpdmUgc3RhdGUKICAgIGNvbnN0IGJ1dHRvbnMgPSBbJ2FsbCcsICdpbmNvbWUnLCAnZXhwZW5zZScsICdpbnZlc3RtZW50J107CiAgICBidXR0b25zLmZvckVhY2goYiA9PiB7CiAgICAgIGNvbnN0IGJ0biA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKGBmaWx0ZXItJHtifWApOwogICAgICBpZiAoYiA9PT0gZmlsdGVyKSB7CiAgICAgICAgYnRuLmNsYXNzTGlzdC5hZGQoJ2FjdGl2ZScpOwogICAgICB9IGVsc2UgewogICAgICAgIGJ0bi5jbGFzc0xpc3QucmVtb3ZlKCdhY3RpdmUnKTsKICAgICAgfQogICAgfSk7CgogICAgZmlsdGVyVHJhbnNhY3Rpb25zKCk7CiAgfQoKICBmdW5jdGlvbiBmaWx0ZXJUcmFuc2FjdGlvbnMoKSB7CiAgICBjb25zdCBzZWFyY2hWYWwgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgndHhuLXNlYXJjaCcpLnZhbHVlLnRvTG93ZXJDYXNlKCkudHJpbSgpOwogICAgY29uc3Qgcm93cyA9IGRvY3VtZW50LnF1ZXJ5U2VsZWN0b3JBbGwoJy50eG4tcm93Jyk7CiAgICBjb25zdCBlbXB0eVJvdyA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCdkeW5hbWljLWVtcHR5LXJvdycpOwogICAgbGV0IHZpc2libGVDb3VudCA9IDA7CgogICAgcm93cy5mb3JFYWNoKHJvdyA9PiB7CiAgICAgIGNvbnN0IHR5cGUgPSByb3cuZ2V0QXR0cmlidXRlKCdkYXRhLXR5cGUnKTsKICAgICAgY29uc3QgdGl0bGUgPSByb3cuZ2V0QXR0cmlidXRlKCdkYXRhLXRpdGxlJyk7CiAgICAgIGNvbnN0IGNhdCA9IHJvdy5nZXRBdHRyaWJ1dGUoJ2RhdGEtY2F0Jyk7CgogICAgICBjb25zdCBtYXRjaGVzRmlsdGVyID0gKGFjdGl2ZUZpbHRlciA9PT0gJ2FsbCcgfHwgdHlwZSA9PT0gYWN0aXZlRmlsdGVyKTsKICAgICAgY29uc3QgbWF0Y2hlc1NlYXJjaCA9ICh0aXRsZS5pbmNsdWRlcyhzZWFyY2hWYWwpIHx8IGNhdC5pbmNsdWRlcyhzZWFyY2hWYWwpKTsKCiAgICAgIGlmIChtYXRjaGVzRmlsdGVyICYmIG1hdGNoZXNTZWFyY2gpIHsKICAgICAgICByb3cuc3R5bGUuZGlzcGxheSA9ICcnOwogICAgICAgIHZpc2libGVDb3VudCsrOwogICAgICB9IGVsc2UgewogICAgICAgIHJvdy5zdHlsZS5kaXNwbGF5ID0gJ25vbmUnOwogICAgICB9CiAgICB9KTsKCiAgICBpZiAoZW1wdHlSb3cpIHsKICAgICAgaWYgKHZpc2libGVDb3VudCA9PT0gMCAmJiByb3dzLmxlbmd0aCA+IDApIHsKICAgICAgICBlbXB0eVJvdy5zdHlsZS5kaXNwbGF5ID0gJyc7CiAgICAgIH0gZWxzZSB7CiAgICAgICAgZW1wdHlSb3cuc3R5bGUuZGlzcGxheSA9ICdub25lJzsKICAgICAgfQogICAgfQogIH0KPC9zY3JpcHQ+CjwvYm9keT4KPC9odG1sPgo=').decode('utf-8'),
}

app.jinja_loader = ChoiceLoader([
    DictLoader(INLINE_TEMPLATES),
    FileSystemLoader(app.template_folder)
])

STYLE_CSS_B64 = 'LyogPT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09CiAgIEZpblNpZ2h0IOKAkyBzdHlsZS5jc3MKICAgRGFyayBTbGF0ZSBUaGVtZSDigJMgTWF0Y2hpbmcgRGFzaGJvYXJkIENvbG9yIFBhbGV0dGUKICAgPT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09ICovCgpAaW1wb3J0IHVybCgnaHR0cHM6Ly9mb250cy5nb29nbGVhcGlzLmNvbS9jc3MyP2ZhbWlseT1PdXRmaXQ6d2dodEAzMDA7NDAwOzUwMDs2MDA7NzAwOzgwMDs5MDAmZmFtaWx5PUludGVyOndnaHRAMzAwOzQwMDs1MDA7NjAwOzcwMCZkaXNwbGF5PXN3YXAnKTsKCi8qIOKUgOKUgCBEZXNpZ24gVG9rZW5zIChTeW5jZWQgd2l0aCBEYXNoYm9hcmQpIOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgCAqLwo6cm9vdCB7CiAgLS1wcmltYXJ5OiAgICAgICAgIzYzNjZGMTsKICAtLXByaW1hcnktZGFyazogICAjNEY0NkU1OwogIC0tcHJpbWFyeS1saWdodDogIHJnYmEoOTksIDEwMiwgMjQxLCAwLjEyKTsKICAtLWFjY2VudDogICAgICAgICAjMjJEM0VFOwogIC0tYWNjZW50LWdsb3c6ICAgIHJnYmEoMzQsIDIxMSwgMjM4LCAwLjE1KTsKICAtLWRhbmdlcjogICAgICAgICAjRUY0NDQ0OwogIC0tc3VjY2VzczogICAgICAgICMxMEI5ODE7CiAgLS13YXJuaW5nOiAgICAgICAgI0Y1OUUwQjsKICAtLWluZm86ICAgICAgICAgICAjM0I4MkY2OwoKICAtLWJnLWRhcms6ICAgICAgICAjMEYxNzJBOwogIC0tYmctY2FyZDogICAgICAgICMxRTI5M0I7CiAgLS1iZy1pbnB1dDogICAgICAgIzBGMTcyQTsKICAtLWJnLWVsZXZhdGVkOiAgICAjMzM0MTU1OwoKICAtLXRleHQtcHJpbWFyeTogICAjRjFGNUY5OwogIC0tdGV4dC1zZWNvbmRhcnk6ICM5NEEzQjg7CiAgLS10ZXh0LW11dGVkOiAgICAgIzY0NzQ4QjsKCiAgLS1ib3JkZXI6ICAgICAgICAgcmdiYSgxNDgsIDE2MywgMTg0LCAwLjE1KTsKICAtLWJvcmRlci1mb2N1czogICByZ2JhKDk5LCAxMDIsIDI0MSwgMC41KTsKCiAgLS1yYWRpdXMtc206ICAgOHB4OwogIC0tcmFkaXVzLW1kOiAgIDE0cHg7CiAgLS1yYWRpdXMtbGc6ICAgMjBweDsKICAtLXJhZGl1cy14bDogICAyOHB4OwogIC0tcmFkaXVzLWZ1bGw6IDk5OTlweDsKCiAgLS1mb250LXByaW1hcnk6ICdPdXRmaXQnLCBzYW5zLXNlcmlmOwogIC0tZm9udC1ib2R5OiAgICAnSW50ZXInLCBzYW5zLXNlcmlmOwoKICAtLXNoYWRvdy1zbTogIDAgMXB4IDJweCByZ2JhKDAsMCwwLDAuMyk7CiAgLS1zaGFkb3ctbWQ6ICAwIDRweCAxMnB4IHJnYmEoMCwwLDAsMC4yNSk7CiAgLS1zaGFkb3ctbGc6ICAwIDEwcHggNDBweCByZ2JhKDAsMCwwLDAuMzUpOwogIC0tc2hhZG93LWdsb3c6IDAgMCAzMHB4IHJnYmEoOTksIDEwMiwgMjQxLCAwLjE1KTsKCiAgLS10cmFuc2l0aW9uOiBhbGwgMC4yNXMgZWFzZTsKfQoKLyog4pSA4pSAIFJlc2V0IOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgCAqLwoqLCAqOjpiZWZvcmUsICo6OmFmdGVyIHsgYm94LXNpemluZzogYm9yZGVyLWJveDsgbWFyZ2luOiAwOyBwYWRkaW5nOiAwOyB9Cmh0bWwgeyBzY3JvbGwtYmVoYXZpb3I6IHNtb290aDsgfQpib2R5IHsKICBmb250LWZhbWlseTogdmFyKC0tZm9udC1wcmltYXJ5KTsKICBiYWNrZ3JvdW5kLWNvbG9yOiB2YXIoLS1iZy1kYXJrKTsKICBjb2xvcjogdmFyKC0tdGV4dC1wcmltYXJ5KTsKICBtaW4taGVpZ2h0OiAxMDB2aDsKICBvdmVyZmxvdy14OiBoaWRkZW47CiAgY3Vyc29yOiBub25lOwp9CgovKiDilIDilIAgQ3VzdG9tIEN1cnNvciDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIAgKi8KI2N1cnNvci1yaW5nIHsKICBwb3NpdGlvbjogZml4ZWQ7IHdpZHRoOiAzMnB4OyBoZWlnaHQ6IDMycHg7CiAgYm9yZGVyOiAycHggc29saWQgcmdiYSg5OSwgMTAyLCAyNDEsIDAuNzUpOwogIGJvcmRlci1yYWRpdXM6IDUwJTsgcG9pbnRlci1ldmVudHM6IG5vbmU7IHotaW5kZXg6IDk5OTk5OwogIHRyYW5zZm9ybTogdHJhbnNsYXRlKC01MCUsIC01MCUpOwogIHRyYW5zaXRpb246IHdpZHRoIDAuMThzIGVhc2UsIGhlaWdodCAwLjE4cyBlYXNlLCBib3JkZXItY29sb3IgMC4xOHMgZWFzZTsKfQojY3Vyc29yLXJpbmc6OmFmdGVyIHsKICBjb250ZW50OiAnJzsgcG9zaXRpb246IGFic29sdXRlOyB0b3A6IDUwJTsgbGVmdDogNTAlOwogIHRyYW5zZm9ybTogdHJhbnNsYXRlKC01MCUsIC01MCUpOyB3aWR0aDogNnB4OyBoZWlnaHQ6IDZweDsKICBiYWNrZ3JvdW5kOiByZ2JhKDk5LCAxMDIsIDI0MSwgMC44NSk7IGJvcmRlci1yYWRpdXM6IDUwJTsKICB0cmFuc2l0aW9uOiB3aWR0aCAwLjE4cyBlYXNlLCBoZWlnaHQgMC4xOHMgZWFzZTsKfQojY3Vyc29yLXJpbmcucmluZy1ob3ZlciB7IHdpZHRoOiA0NHB4OyBoZWlnaHQ6IDQ0cHg7IGJvcmRlci1jb2xvcjogcmdiYSg5OSwgMTAyLCAyNDEsIDEpOyB9CiNjdXJzb3ItcmluZy5yaW5nLWhvdmVyOjphZnRlciB7IHdpZHRoOiA3cHg7IGhlaWdodDogN3B4OyB9CiNjdXJzb3ItcmluZy5yaW5nLWNsaWNrIHsgd2lkdGg6IDYwcHg7IGhlaWdodDogNjBweDsgYm9yZGVyLWNvbG9yOiByZ2JhKDk5LCAxMDIsIDI0MSwgMSk7IH0KI2N1cnNvci1yaW5nLnJpbmctY2xpY2s6OmFmdGVyIHsgd2lkdGg6IDhweDsgaGVpZ2h0OiA4cHg7IH0KQG1lZGlhIChtYXgtd2lkdGg6IDc2OHB4KSB7ICNjdXJzb3ItcmluZyB7IGRpc3BsYXk6IG5vbmU7IH0gYm9keSB7IGN1cnNvcjogYXV0bzsgfSB9CgovKiDilIDilIAgU2Nyb2xsYmFyIOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgCAqLwo6Oi13ZWJraXQtc2Nyb2xsYmFyIHsgd2lkdGg6IDZweDsgfQo6Oi13ZWJraXQtc2Nyb2xsYmFyLXRyYWNrIHsgYmFja2dyb3VuZDogdmFyKC0tYmctZGFyayk7IH0KOjotd2Via2l0LXNjcm9sbGJhci10aHVtYiB7IGJhY2tncm91bmQ6IHJnYmEoOTksIDEwMiwgMjQxLCAwLjMwKTsgYm9yZGVyLXJhZGl1czogdmFyKC0tcmFkaXVzLWZ1bGwpOyB9Cjo6LXdlYmtpdC1zY3JvbGxiYXItdGh1bWI6aG92ZXIgeyBiYWNrZ3JvdW5kOiByZ2JhKDk5LCAxMDIsIDI0MSwgMC41NSk7IH0KOjpzZWxlY3Rpb24geyBiYWNrZ3JvdW5kOiByZ2JhKDk5LCAxMDIsIDI0MSwgMC4yNSk7IGNvbG9yOiAjZmZmOyB9CgovKiDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZAKICAgSE9NRSAvIExBTkRJTkcgUEFHRQogICDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZDilZAgKi8KLmhvbWUtbmF2YmFyIHsKICBiYWNrZ3JvdW5kOiByZ2JhKDE1LCAyMywgNDIsIDAuODUpOwogIGJhY2tkcm9wLWZpbHRlcjogYmx1cigxNnB4KTsgLXdlYmtpdC1iYWNrZHJvcC1maWx0ZXI6IGJsdXIoMTZweCk7CiAgYm9yZGVyLWJvdHRvbTogMXB4IHNvbGlkIHZhcigtLWJvcmRlcik7CiAgcGFkZGluZzogMDsgcG9zaXRpb246IHN0aWNreTsgdG9wOiAwOyB6LWluZGV4OiAxMDA7Cn0KLmhvbWUtbmF2LWlubmVyIHsKICBtYXgtd2lkdGg6IDEyMDBweDsgbWFyZ2luOiAwIGF1dG87IHBhZGRpbmc6IDAuOXJlbSAxLjVyZW07CiAgZGlzcGxheTogZmxleDsgYWxpZ24taXRlbXM6IGNlbnRlcjsganVzdGlmeS1jb250ZW50OiBzcGFjZS1iZXR3ZWVuOwp9Ci5ob21lLW5hdi1icmFuZCB7IGRpc3BsYXk6IGZsZXg7IGFsaWduLWl0ZW1zOiBjZW50ZXI7IGdhcDogMC41NXJlbTsgdGV4dC1kZWNvcmF0aW9uOiBub25lOyB9Ci5ob21lLW5hdi1sb2dvLWltZyB7IHdpZHRoOiAzOHB4OyBoZWlnaHQ6IDM4cHg7IGJvcmRlci1yYWRpdXM6IDEwcHg7IG9iamVjdC1maXQ6IGNvdmVyOyBmbGV4LXNocmluazogMDsgfQouaG9tZS1uYXYtbmFtZSB7IGZvbnQtc2l6ZTogMS4yNXJlbTsgZm9udC13ZWlnaHQ6IDgwMDsgY29sb3I6IHZhcigtLXRleHQtcHJpbWFyeSk7IGZvbnQtZmFtaWx5OiB2YXIoLS1mb250LXByaW1hcnkpOyB9Ci5ob21lLW5hdi1saW5rcyB7IGRpc3BsYXk6IGZsZXg7IGFsaWduLWl0ZW1zOiBjZW50ZXI7IGdhcDogMC41cmVtOyBsaXN0LXN0eWxlOiBub25lOyB9Ci5ob21lLW5hdi1saW5rIHsKICBjb2xvcjogdmFyKC0tdGV4dC1zZWNvbmRhcnkpOyB0ZXh0LWRlY29yYXRpb246IG5vbmU7IGZvbnQtZmFtaWx5OiB2YXIoLS1mb250LWJvZHkpOwogIGZvbnQtc2l6ZTogMC45MnJlbTsgZm9udC13ZWlnaHQ6IDUwMDsgcGFkZGluZzogMC41cmVtIDEuMnJlbTsKICBib3JkZXItcmFkaXVzOiB2YXIoLS1yYWRpdXMtZnVsbCk7IGJvcmRlcjogMXB4IHNvbGlkIHRyYW5zcGFyZW50OyB0cmFuc2l0aW9uOiB2YXIoLS10cmFuc2l0aW9uKTsKfQouaG9tZS1uYXYtbGluazpob3ZlciwgLmhvbWUtbmF2LWxpbmsuYWN0aXZlIHsKICBjb2xvcjogdmFyKC0tcHJpbWFyeSk7IGJhY2tncm91bmQ6IHZhcigtLXByaW1hcnktbGlnaHQpOyBib3JkZXItY29sb3I6IHJnYmEoOTksMTAyLDI0MSwwLjIpOwp9Ci5ob21lLW5hdi1jdGEgewogIGJhY2tncm91bmQ6IHZhcigtLXByaW1hcnkpOyBjb2xvcjogI2ZmZjsgdGV4dC1kZWNvcmF0aW9uOiBub25lOyBmb250LWZhbWlseTogdmFyKC0tZm9udC1wcmltYXJ5KTsKICBmb250LXNpemU6IDAuOXJlbTsgZm9udC13ZWlnaHQ6IDcwMDsgcGFkZGluZzogMC40OHJlbSAxLjJyZW07CiAgYm9yZGVyLXJhZGl1czogdmFyKC0tcmFkaXVzLWZ1bGwpOyB0cmFuc2l0aW9uOiB2YXIoLS10cmFuc2l0aW9uKTsKfQouaG9tZS1uYXYtY3RhOmhvdmVyIHsgYmFja2dyb3VuZDogdmFyKC0tcHJpbWFyeS1kYXJrKTsgY29sb3I6ICNmZmY7IH0KLmhvbWUtbmF2LXRvZ2dsZXIgewogIGRpc3BsYXk6IG5vbmU7IGZsZXgtZGlyZWN0aW9uOiBjb2x1bW47IGdhcDogNXB4OyBiYWNrZ3JvdW5kOiBub25lOyBib3JkZXI6IG5vbmU7IGN1cnNvcjogcG9pbnRlcjsgcGFkZGluZzogMC40cmVtOwp9Ci5ob21lLW5hdi10b2dnbGVyIHNwYW4geyBkaXNwbGF5OiBibG9jazsgd2lkdGg6IDIycHg7IGhlaWdodDogMnB4OyBiYWNrZ3JvdW5kOiB2YXIoLS10ZXh0LXNlY29uZGFyeSk7IGJvcmRlci1yYWRpdXM6IDJweDsgfQouaG9tZS1uYXYtbW9iaWxlIHsKICBkaXNwbGF5OiBub25lOyBmbGV4LWRpcmVjdGlvbjogY29sdW1uOyBnYXA6IDAuMnJlbTsgcGFkZGluZzogMC43NXJlbSAxLjVyZW0gMXJlbTsKICBib3JkZXItdG9wOiAxcHggc29saWQgdmFyKC0tYm9yZGVyKTsgYmFja2dyb3VuZDogdmFyKC0tYmctZGFyayk7Cn0KLmhvbWUtbmF2LW1vYmlsZS5vcGVuIHsgZGlzcGxheTogZmxleDsgfQouaG9tZS1uYXYtbW9iaWxlLWxpbmsgewogIGNvbG9yOiB2YXIoLS10ZXh0LXNlY29uZGFyeSk7IHRleHQtZGVjb3JhdGlvbjogbm9uZTsgZm9udC1mYW1pbHk6IHZhcigtLWZvbnQtYm9keSk7CiAgZm9udC1zaXplOiAwLjk1cmVtOyBwYWRkaW5nOiAwLjU1cmVtIDA7IGJvcmRlci1ib3R0b206IDFweCBzb2xpZCB2YXIoLS1ib3JkZXIpOyB0cmFuc2l0aW9uOiB2YXIoLS10cmFuc2l0aW9uKTsKfQouaG9tZS1uYXYtbW9iaWxlLWxpbms6aG92ZXIsIC5ob21lLW5hdi1tb2JpbGUtbGluay5jdGEgeyBjb2xvcjogdmFyKC0tcHJpbWFyeSk7IH0KQG1lZGlhIChtYXgtd2lkdGg6IDc2OHB4KSB7IC5ob21lLW5hdi1saW5rcyB7IGRpc3BsYXk6IG5vbmU7IH0gLmhvbWUtbmF2LXRvZ2dsZXIgeyBkaXNwbGF5OiBmbGV4OyB9IH0KCi8qIOKUgOKUgCBIZXJvIOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgCAqLwouaG9tZS1jb250YWluZXIgeyB3aWR0aDogMTAwJTsgbWF4LXdpZHRoOiAxMTAwcHg7IG1hcmdpbjogMCBhdXRvOyBwYWRkaW5nOiAwIDEuNXJlbTsgfQouaG9tZS1oZXJvIHsKICB0ZXh0LWFsaWduOiBjZW50ZXI7IHBhZGRpbmc6IDdyZW0gMCA1cmVtOyBwb3NpdGlvbjogcmVsYXRpdmU7CiAgYmFja2dyb3VuZDogcmFkaWFsLWdyYWRpZW50KGVsbGlwc2UgYXQgdG9wLCByZ2JhKDk5LDEwMiwyNDEsMC4wOCkgMCUsIHRyYW5zcGFyZW50IDYwJSk7Cn0KLmhvbWUtaGVybzo6YmVmb3JlIHsKICBjb250ZW50OiAnJzsgcG9zaXRpb246IGFic29sdXRlOyB0b3A6IDA7IGxlZnQ6IDA7IHJpZ2h0OiAwOyBib3R0b206IDA7IHBvaW50ZXItZXZlbnRzOiBub25lOwogIGJhY2tncm91bmQ6IHJhZGlhbC1ncmFkaWVudChjaXJjbGUgYXQgMjAlIDMwJSwgcmdiYSg5OSwxMDIsMjQxLDAuMDYpIDAlLCB0cmFuc3BhcmVudCA1MCUpLAogICAgICAgICAgICAgIHJhZGlhbC1ncmFkaWVudChjaXJjbGUgYXQgODAlIDcwJSwgcmdiYSgzNCwyMTEsMjM4LDAuMDQpIDAlLCB0cmFuc3BhcmVudCA1MCUpOwp9Ci5oZXJvLXRpdGxlIHsKICBmb250LXNpemU6IGNsYW1wKDIuMnJlbSwgNXZ3LCAzLjVyZW0pOyBmb250LXdlaWdodDogOTAwOyBjb2xvcjogdmFyKC0tdGV4dC1wcmltYXJ5KTsKICBsaW5lLWhlaWdodDogMS4xMjsgbGV0dGVyLXNwYWNpbmc6IC0xcHg7IG1hcmdpbi1ib3R0b206IDEuMnJlbTsgcG9zaXRpb246IHJlbGF0aXZlOwp9Ci5oZXJvLXRpdGxlIHNwYW4gewogIGJhY2tncm91bmQ6IGxpbmVhci1ncmFkaWVudCgxMzVkZWcsIHZhcigtLXByaW1hcnkpLCB2YXIoLS1hY2NlbnQpKTsKICAtd2Via2l0LWJhY2tncm91bmQtY2xpcDogdGV4dDsgLXdlYmtpdC10ZXh0LWZpbGwtY29sb3I6IHRyYW5zcGFyZW50OyBiYWNrZ3JvdW5kLWNsaXA6IHRleHQ7Cn0KLmhlcm8tc3VidGl0bGUgewogIGZvbnQtc2l6ZTogMS4xNXJlbTsgZm9udC1mYW1pbHk6IHZhcigtLWZvbnQtYm9keSk7IGNvbG9yOiB2YXIoLS10ZXh0LXNlY29uZGFyeSk7CiAgbGluZS1oZWlnaHQ6IDEuNzU7IG1hcmdpbi1ib3R0b206IDIuNXJlbTsgbWF4LXdpZHRoOiA1NTBweDsgbWFyZ2luLWxlZnQ6IGF1dG87IG1hcmdpbi1yaWdodDogYXV0bzsgcG9zaXRpb246IHJlbGF0aXZlOwp9Ci5oZXJvLWFjdGlvbnMgeyBkaXNwbGF5OiBmbGV4OyBhbGlnbi1pdGVtczogY2VudGVyOyBqdXN0aWZ5LWNvbnRlbnQ6IGNlbnRlcjsgZ2FwOiAxcmVtOyBmbGV4LXdyYXA6IHdyYXA7IHBvc2l0aW9uOiByZWxhdGl2ZTsgfQouaGVyby1idG4tcHJpbWFyeSB7CiAgZGlzcGxheTogaW5saW5lLWZsZXg7IGFsaWduLWl0ZW1zOiBjZW50ZXI7CiAgYmFja2dyb3VuZDogbGluZWFyLWdyYWRpZW50KDEzNWRlZywgdmFyKC0tcHJpbWFyeSksIHZhcigtLXByaW1hcnktZGFyaykpOyBjb2xvcjogI2ZmZjsKICB0ZXh0LWRlY29yYXRpb246IG5vbmU7IGZvbnQtZmFtaWx5OiB2YXIoLS1mb250LXByaW1hcnkpOyBmb250LXNpemU6IDFyZW07IGZvbnQtd2VpZ2h0OiA3MDA7CiAgcGFkZGluZzogMC44NXJlbSAyLjJyZW07IGJvcmRlci1yYWRpdXM6IHZhcigtLXJhZGl1cy1tZCk7CiAgdHJhbnNpdGlvbjogdmFyKC0tdHJhbnNpdGlvbik7IGJveC1zaGFkb3c6IDAgNHB4IDE0cHggcmdiYSg5OSwxMDIsMjQxLDAuMyk7Cn0KLmhlcm8tYnRuLXByaW1hcnk6aG92ZXIgewogIGJhY2tncm91bmQ6IGxpbmVhci1ncmFkaWVudCgxMzVkZWcsIHZhcigtLXByaW1hcnktZGFyayksICMzNzMwQTMpOyBjb2xvcjogI2ZmZjsKICBib3gtc2hhZG93OiAwIDZweCAyMHB4IHJnYmEoOTksMTAyLDI0MSwwLjQpOyB0cmFuc2Zvcm06IHRyYW5zbGF0ZVkoLTJweCk7Cn0KLmhlcm8tYnRuLW91dGxpbmUgewogIGRpc3BsYXk6IGlubGluZS1mbGV4OyBhbGlnbi1pdGVtczogY2VudGVyOyBiYWNrZ3JvdW5kOiB0cmFuc3BhcmVudDsgY29sb3I6IHZhcigtLXRleHQtcHJpbWFyeSk7CiAgdGV4dC1kZWNvcmF0aW9uOiBub25lOyBmb250LWZhbWlseTogdmFyKC0tZm9udC1wcmltYXJ5KTsgZm9udC1zaXplOiAxcmVtOyBmb250LXdlaWdodDogNjAwOwogIHBhZGRpbmc6IDAuODJyZW0gMnJlbTsgYm9yZGVyLXJhZGl1czogdmFyKC0tcmFkaXVzLW1kKTsgYm9yZGVyOiAxLjVweCBzb2xpZCB2YXIoLS1iZy1lbGV2YXRlZCk7CiAgdHJhbnNpdGlvbjogdmFyKC0tdHJhbnNpdGlvbik7Cn0KLmhlcm8tYnRuLW91dGxpbmU6aG92ZXIgeyBib3JkZXItY29sb3I6IHZhcigtLXByaW1hcnkpOyBjb2xvcjogdmFyKC0tcHJpbWFyeSk7IGJhY2tncm91bmQ6IHZhcigtLXByaW1hcnktbGlnaHQpOyB9CgovKiDilIDilIAgRmVhdHVyZXMg4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSAICovCi5ob21lLWZlYXR1cmVzIHsgcGFkZGluZzogNHJlbSAwIDUuNXJlbTsgcG9zaXRpb246IHJlbGF0aXZlOyB9Ci5ob21lLXNlY3Rpb24tdGl0bGUgewogIGZvbnQtc2l6ZTogMS45cmVtOyBmb250LXdlaWdodDogODAwOyBjb2xvcjogdmFyKC0tdGV4dC1wcmltYXJ5KTsKICB0ZXh0LWFsaWduOiBjZW50ZXI7IG1hcmdpbi1ib3R0b206IDNyZW07IGxldHRlci1zcGFjaW5nOiAtMC4zcHg7Cn0KLmhvbWUtZmVhdHVyZXMtZ3JpZCB7IGRpc3BsYXk6IGdyaWQ7IGdyaWQtdGVtcGxhdGUtY29sdW1uczogcmVwZWF0KGF1dG8tZml0LCBtaW5tYXgoMjgwcHgsIDFmcikpOyBnYXA6IDEuNXJlbTsgfQouaG9tZS1mZWF0dXJlLWNhcmQgewogIGJhY2tncm91bmQ6IHZhcigtLWJnLWNhcmQpOyBib3JkZXItcmFkaXVzOiB2YXIoLS1yYWRpdXMtbGcpOyBwYWRkaW5nOiAycmVtIDEuNXJlbTsKICB0ZXh0LWFsaWduOiBjZW50ZXI7IHRyYW5zaXRpb246IHRyYW5zZm9ybSAwLjNzIGVhc2UsIGJveC1zaGFkb3cgMC4zcyBlYXNlOwogIGJvcmRlcjogMXB4IHNvbGlkIHZhcigtLWJvcmRlcik7IHBvc2l0aW9uOiByZWxhdGl2ZTsgb3ZlcmZsb3c6IGhpZGRlbjsKfQouaG9tZS1mZWF0dXJlLWNhcmQ6OmJlZm9yZSB7CiAgY29udGVudDogJyc7IHBvc2l0aW9uOiBhYnNvbHV0ZTsgdG9wOiAwOyBsZWZ0OiAwOyByaWdodDogMDsgaGVpZ2h0OiAzcHg7CiAgYmFja2dyb3VuZDogbGluZWFyLWdyYWRpZW50KDkwZGVnLCB2YXIoLS1wcmltYXJ5KSwgdmFyKC0tYWNjZW50KSk7IG9wYWNpdHk6IDA7IHRyYW5zaXRpb246IG9wYWNpdHkgMC4zcyBlYXNlOwp9Ci5ob21lLWZlYXR1cmUtY2FyZDpob3ZlciB7IHRyYW5zZm9ybTogdHJhbnNsYXRlWSgtNnB4KTsgYm94LXNoYWRvdzogdmFyKC0tc2hhZG93LWxnKTsgYm9yZGVyLWNvbG9yOiByZ2JhKDk5LDEwMiwyNDEsMC4yKTsgfQouaG9tZS1mZWF0dXJlLWNhcmQ6aG92ZXI6OmJlZm9yZSB7IG9wYWNpdHk6IDE7IH0KLmhvbWUtZmVhdHVyZS1pY29uIHsKICBmb250LXNpemU6IDIuMnJlbTsgbWFyZ2luLWJvdHRvbTogMXJlbTsgZGlzcGxheTogaW5saW5lLWZsZXg7IGFsaWduLWl0ZW1zOiBjZW50ZXI7IGp1c3RpZnktY29udGVudDogY2VudGVyOwogIHdpZHRoOiA2MHB4OyBoZWlnaHQ6IDYwcHg7IGJvcmRlci1yYWRpdXM6IDE2cHg7IGJhY2tncm91bmQ6IHZhcigtLXByaW1hcnktbGlnaHQpOyBjb2xvcjogdmFyKC0tcHJpbWFyeSk7Cn0KLmhvbWUtZmVhdHVyZS10aXRsZSB7IGZvbnQtc2l6ZTogMS4wOHJlbTsgZm9udC13ZWlnaHQ6IDcwMDsgY29sb3I6IHZhcigtLXRleHQtcHJpbWFyeSk7IG1hcmdpbi1ib3R0b206IDAuNjVyZW07IGZvbnQtZmFtaWx5OiB2YXIoLS1mb250LXByaW1hcnkpOyB9Ci5ob21lLWZlYXR1cmUtZGVzYyB7IGZvbnQtc2l6ZTogMC44OHJlbTsgZm9udC1mYW1pbHk6IHZhcigtLWZvbnQtYm9keSk7IGNvbG9yOiB2YXIoLS10ZXh0LXNlY29uZGFyeSk7IGxpbmUtaGVpZ2h0OiAxLjY1OyBtYXJnaW46IDA7IH0KCi8qIOKUgOKUgCBGb290ZXIg4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSAICovCi5ob21lLWZvb3RlciB7IGJvcmRlci10b3A6IDFweCBzb2xpZCB2YXIoLS1ib3JkZXIpOyBwYWRkaW5nOiAxLjc1cmVtIDA7IHRleHQtYWxpZ246IGNlbnRlcjsgfQouaG9tZS1mb290ZXItdGV4dCB7IGZvbnQtc2l6ZTogMC44NXJlbTsgZm9udC1mYW1pbHk6IHZhcigtLWZvbnQtYm9keSk7IGNvbG9yOiB2YXIoLS10ZXh0LW11dGVkKTsgbWFyZ2luOiAwOyB9Ci5ob21lLWZvb3Rlci1saW5rIHsgY29sb3I6IHZhcigtLXByaW1hcnkpOyB0ZXh0LWRlY29yYXRpb246IG5vbmU7IGZvbnQtd2VpZ2h0OiA2MDA7IHRyYW5zaXRpb246IHZhcigtLXRyYW5zaXRpb24pOyB9Ci5ob21lLWZvb3Rlci1saW5rOmhvdmVyIHsgY29sb3I6ICNmZmY7IH0KQG1lZGlhIChtYXgtd2lkdGg6IDc2OHB4KSB7CiAgLmhvbWUtaGVybyB7IHBhZGRpbmc6IDRyZW0gMCAzcmVtOyB9CiAgLmhvbWUtZmVhdHVyZXMtZ3JpZCB7IGdyaWQtdGVtcGxhdGUtY29sdW1uczogMWZyOyB9CiAgLmhlcm8tYWN0aW9ucyB7IGZsZXgtZGlyZWN0aW9uOiBjb2x1bW47IGFsaWduLWl0ZW1zOiBzdHJldGNoOyB9CiAgLmhlcm8tYnRuLXByaW1hcnksIC5oZXJvLWJ0bi1vdXRsaW5lIHsganVzdGlmeS1jb250ZW50OiBjZW50ZXI7IH0KfQoKLyog4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQCiAgIEFVVEggUEFHRVMgKExvZ2luICYgUmVnaXN0ZXIpCiAgIOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkOKVkCAqLwoucGFnZS13cmFwcGVyIHsKICBwb3NpdGlvbjogcmVsYXRpdmU7IHotaW5kZXg6IDE7IG1pbi1oZWlnaHQ6IDEwMHZoOwogIGRpc3BsYXk6IGZsZXg7IGFsaWduLWl0ZW1zOiBjZW50ZXI7IGp1c3RpZnktY29udGVudDogY2VudGVyOyBwYWRkaW5nOiAyLjVyZW0gMXJlbTsKICBiYWNrZ3JvdW5kOiByYWRpYWwtZ3JhZGllbnQoZWxsaXBzZSBhdCA1MCUgMCUsIHJnYmEoOTksMTAyLDI0MSwwLjA2KSAwJSwgdHJhbnNwYXJlbnQgNjAlKTsKfQouYXV0aC1jb250YWluZXIgeyB3aWR0aDogMTAwJTsgbWF4LXdpZHRoOiA3MDBweDsgfQoKLmdsYXNzLWNhcmQgewogIGJhY2tncm91bmQ6IHZhcigtLWJnLWNhcmQpOyBib3JkZXI6IDFweCBzb2xpZCB2YXIoLS1ib3JkZXIpOyBib3JkZXItcmFkaXVzOiB2YXIoLS1yYWRpdXMteGwpOwogIHBhZGRpbmc6IDIuNXJlbSAyLjhyZW07IGJveC1zaGFkb3c6IHZhcigtLXNoYWRvdy1sZyk7IHBvc2l0aW9uOiByZWxhdGl2ZTsgb3ZlcmZsb3c6IGhpZGRlbjsKfQouZ2xhc3MtY2FyZDo6YmVmb3JlIHsKICBjb250ZW50OiAnJzsgcG9zaXRpb246IGFic29sdXRlOyB0b3A6IDA7IGxlZnQ6IDA7IHJpZ2h0OiAwOyBoZWlnaHQ6IDRweDsKICBiYWNrZ3JvdW5kOiBsaW5lYXItZ3JhZGllbnQoOTBkZWcsIHZhcigtLXByaW1hcnkpLCB2YXIoLS1hY2NlbnQpKTsKfQoKLnJlZy1mb3JtLXJvdyB7IGRpc3BsYXk6IGdyaWQ7IGdyaWQtdGVtcGxhdGUtY29sdW1uczogMWZyIDFmcjsgZ2FwOiAwIDEuMjVyZW07IH0KQG1lZGlhIChtYXgtd2lkdGg6IDYwMHB4KSB7IC5yZWctZm9ybS1yb3cgeyBncmlkLXRlbXBsYXRlLWNvbHVtbnM6IDFmcjsgfSB9CgovKiDilIDilIAgQnJhbmQgTG9nbyDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIAgKi8KLmJyYW5kLWxvZ28geyBkaXNwbGF5OiBmbGV4OyBhbGlnbi1pdGVtczogY2VudGVyOyBqdXN0aWZ5LWNvbnRlbnQ6IGNlbnRlcjsgZ2FwOiAwLjc1cmVtOyBtYXJnaW4tYm90dG9tOiAxLjc1cmVtOyB9Ci5icmFuZC1sb2dvLWltZyB7IHdpZHRoOiA1MnB4OyBoZWlnaHQ6IDUycHg7IGJvcmRlci1yYWRpdXM6IDE0cHg7IG9iamVjdC1maXQ6IGNvdmVyOyBmbGV4LXNocmluazogMDsgYm94LXNoYWRvdzogMCA0cHggMTJweCByZ2JhKDAsMCwwLDAuMyk7IH0KLmJyYW5kLXRleHQgeyBkaXNwbGF5OiBmbGV4OyBmbGV4LWRpcmVjdGlvbjogY29sdW1uOyB9Ci5icmFuZC1uYW1lIHsgZm9udC1zaXplOiAxLjY1cmVtOyBmb250LXdlaWdodDogODAwOyBjb2xvcjogdmFyKC0tdGV4dC1wcmltYXJ5KTsgbGluZS1oZWlnaHQ6IDEuMTsgbGV0dGVyLXNwYWNpbmc6IC0wLjNweDsgfQouYnJhbmQtdGFnbGluZSB7IGZvbnQtc2l6ZTogMC43MnJlbTsgZm9udC1mYW1pbHk6IHZhcigtLWZvbnQtYm9keSk7IGNvbG9yOiB2YXIoLS10ZXh0LW11dGVkKTsgbGV0dGVyLXNwYWNpbmc6IDAuOHB4OyB0ZXh0LXRyYW5zZm9ybTogdXBwZXJjYXNlOyBmb250LXdlaWdodDogNTAwOyB9CgovKiDilIDilIAgQXV0aCBUaXRsZSDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIAgKi8KLmF1dGgtdGl0bGUgeyBmb250LXNpemU6IDEuNTVyZW07IGZvbnQtd2VpZ2h0OiA3MDA7IGNvbG9yOiB2YXIoLS10ZXh0LXByaW1hcnkpOyBtYXJnaW4tYm90dG9tOiAwLjNyZW07IHRleHQtYWxpZ246IGNlbnRlcjsgfQouYXV0aC1zdWJ0aXRsZSB7IGZvbnQtc2l6ZTogMC44OHJlbTsgY29sb3I6IHZhcigtLXRleHQtc2Vjb25kYXJ5KTsgZm9udC1mYW1pbHk6IHZhcigtLWZvbnQtYm9keSk7IHRleHQtYWxpZ246IGNlbnRlcjsgbWFyZ2luLWJvdHRvbTogMS43NXJlbTsgfQoKLyog4pSA4pSAIERpdmlkZXIg4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSAICovCi5hdXRoLWRpdmlkZXIgeyBoZWlnaHQ6IDFweDsgYmFja2dyb3VuZDogdmFyKC0tYm9yZGVyKTsgbWFyZ2luOiAxLjI1cmVtIDA7IH0KCi8qIOKUgOKUgCBGb3JtIOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgCAqLwouZm9ybS1ncm91cCB7IG1hcmdpbi1ib3R0b206IDEuMXJlbTsgfQouZm9ybS1sYWJlbCB7CiAgZGlzcGxheTogYmxvY2s7IGZvbnQtc2l6ZTogMC44cmVtOyBmb250LXdlaWdodDogNjAwOyBjb2xvcjogdmFyKC0tdGV4dC1zZWNvbmRhcnkpOwogIG1hcmdpbi1ib3R0b206IDAuNDVyZW07IHRleHQtdHJhbnNmb3JtOiB1cHBlcmNhc2U7IGxldHRlci1zcGFjaW5nOiAwLjZweDsgZm9udC1mYW1pbHk6IHZhcigtLWZvbnQtYm9keSk7Cn0KLmlucHV0LXdyYXBwZXIgeyBwb3NpdGlvbjogcmVsYXRpdmU7IGRpc3BsYXk6IGZsZXg7IGFsaWduLWl0ZW1zOiBjZW50ZXI7IH0KLmlucHV0LWljb24geyBwb3NpdGlvbjogYWJzb2x1dGU7IGxlZnQ6IDAuOXJlbTsgY29sb3I6IHZhcigtLXRleHQtbXV0ZWQpOyBmb250LXNpemU6IDAuOTVyZW07IHBvaW50ZXItZXZlbnRzOiBub25lOyB6LWluZGV4OiAyOyB9Ci5mb3JtLWNvbnRyb2wtY3VzdG9tIHsKICB3aWR0aDogMTAwJTsgYmFja2dyb3VuZDogdmFyKC0tYmctaW5wdXQpOyBib3JkZXI6IDEuNXB4IHNvbGlkIHZhcigtLWJvcmRlcik7IGJvcmRlci1yYWRpdXM6IHZhcigtLXJhZGl1cy1tZCk7CiAgcGFkZGluZzogMC44cmVtIDFyZW0gMC44cmVtIDIuN3JlbTsgY29sb3I6IHZhcigtLXRleHQtcHJpbWFyeSk7IGZvbnQtZmFtaWx5OiB2YXIoLS1mb250LWJvZHkpOwogIGZvbnQtc2l6ZTogMC45MnJlbTsgdHJhbnNpdGlvbjogYm9yZGVyLWNvbG9yIDAuMnMgZWFzZSwgYm94LXNoYWRvdyAwLjJzIGVhc2U7IG91dGxpbmU6IG5vbmU7Cn0KLmZvcm0tY29udHJvbC1jdXN0b206OnBsYWNlaG9sZGVyIHsgY29sb3I6IHZhcigtLXRleHQtbXV0ZWQpOyB9Ci5mb3JtLWNvbnRyb2wtY3VzdG9tOmZvY3VzIHsgYm9yZGVyLWNvbG9yOiB2YXIoLS1wcmltYXJ5KTsgYm94LXNoYWRvdzogMCAwIDAgM3B4IHJnYmEoOTksMTAyLDI0MSwwLjEyKTsgYmFja2dyb3VuZDogcmdiYSgxNSwyMyw0MiwwLjgpOyB9Ci5mb3JtLWNvbnRyb2wtY3VzdG9tLmlzLXZhbGlkIHsgYm9yZGVyLWNvbG9yOiB2YXIoLS1zdWNjZXNzKTsgfQouZm9ybS1jb250cm9sLWN1c3RvbS5pcy1pbnZhbGlkIHsgYm9yZGVyLWNvbG9yOiB2YXIoLS1kYW5nZXIpOyB9Ci5oYXMtcmlnaHQtaWNvbiAuZm9ybS1jb250cm9sLWN1c3RvbSB7IHBhZGRpbmctcmlnaHQ6IDNyZW07IH0KCi5wYXNzd29yZC10b2dnbGUgewogIHBvc2l0aW9uOiBhYnNvbHV0ZTsgcmlnaHQ6IDAuOXJlbTsgYmFja2dyb3VuZDogbm9uZTsgYm9yZGVyOiBub25lOyBjb2xvcjogdmFyKC0tdGV4dC1tdXRlZCk7CiAgY3Vyc29yOiBwb2ludGVyOyBmb250LXNpemU6IDAuOTVyZW07IHotaW5kZXg6IDI7IHBhZGRpbmc6IDAuMnJlbTsgdHJhbnNpdGlvbjogY29sb3IgMC4ycyBlYXNlOwp9Ci5wYXNzd29yZC10b2dnbGU6aG92ZXIgeyBjb2xvcjogdmFyKC0tcHJpbWFyeSk7IH0KCi52YWxpZGF0aW9uLW1zZyB7IGZvbnQtc2l6ZTogMC43NnJlbTsgZm9udC1mYW1pbHk6IHZhcigtLWZvbnQtYm9keSk7IG1hcmdpbi10b3A6IDAuMzVyZW07IH0KLnZhbGlkYXRpb24tbXNnLnZhbGlkIHsgY29sb3I6IHZhcigtLXN1Y2Nlc3MpOyB9Ci52YWxpZGF0aW9uLW1zZy5pbnZhbGlkIHsgY29sb3I6IHZhcigtLWRhbmdlcik7IH0KCi8qIOKUgOKUgCBQYXNzd29yZCBTdHJlbmd0aCDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIAgKi8KLnN0cmVuZ3RoLW1ldGVyIHsgbWFyZ2luLXRvcDogMC42cmVtOyB9Ci5zdHJlbmd0aC1iYXJzIHsgZGlzcGxheTogZmxleDsgZ2FwOiA1cHg7IG1hcmdpbi1ib3R0b206IDAuMzVyZW07IH0KLnN0cmVuZ3RoLWJhciB7IGZsZXg6IDE7IGhlaWdodDogNHB4OyBib3JkZXItcmFkaXVzOiB2YXIoLS1yYWRpdXMtZnVsbCk7IGJhY2tncm91bmQ6IHJnYmEoMjU1LDI1NSwyNTUsMC4wNik7IHRyYW5zaXRpb246IGJhY2tncm91bmQgMC4zcyBlYXNlOyB9Ci5zdHJlbmd0aC1iYXIuYWN0aXZlLXdlYWsgeyBiYWNrZ3JvdW5kOiB2YXIoLS1kYW5nZXIpOyB9Ci5zdHJlbmd0aC1iYXIuYWN0aXZlLWZhaXIgeyBiYWNrZ3JvdW5kOiB2YXIoLS13YXJuaW5nKTsgfQouc3RyZW5ndGgtYmFyLmFjdGl2ZS1nb29kIHsgYmFja2dyb3VuZDogdmFyKC0taW5mbyk7IH0KLnN0cmVuZ3RoLWJhci5hY3RpdmUtc3Ryb25nIHsgYmFja2dyb3VuZDogdmFyKC0tc3VjY2Vzcyk7IH0KLnN0cmVuZ3RoLWxhYmVsIHsgZm9udC1zaXplOiAwLjc0cmVtOyBmb250LWZhbWlseTogdmFyKC0tZm9udC1ib2R5KTsgY29sb3I6IHZhcigtLXRleHQtbXV0ZWQpOyB9CgoucGFzc3dvcmQtcnVsZXMgewogIGRpc3BsYXk6IGZsZXg7IGZsZXgtd3JhcDogd3JhcDsgYWxpZ24taXRlbXM6IGNlbnRlcjsgZ2FwOiAwLjQ1cmVtIDFyZW07CiAgYmFja2dyb3VuZDogcmdiYSgyNTUsMjU1LDI1NSwwLjAzKTsgYm9yZGVyOiAxcHggc29saWQgdmFyKC0tYm9yZGVyKTsgYm9yZGVyLXJhZGl1czogdmFyKC0tcmFkaXVzLW1kKTsKICBwYWRkaW5nOiAwLjc1cmVtIDFyZW07IG1hcmdpbi10b3A6IDAuNjVyZW07Cn0KLnJ1bGUtaXRlbSB7CiAgZGlzcGxheTogZmxleDsgYWxpZ24taXRlbXM6IGNlbnRlcjsgZ2FwOiAwLjNyZW07IGZvbnQtc2l6ZTogMC43NHJlbTsKICBmb250LWZhbWlseTogdmFyKC0tZm9udC1ib2R5KTsgY29sb3I6IHZhcigtLXRleHQtbXV0ZWQpOyB0cmFuc2l0aW9uOiBjb2xvciAwLjJzIGVhc2U7IHdoaXRlLXNwYWNlOiBub3dyYXA7Cn0KLnJ1bGUtaXRlbS5tZXQgeyBjb2xvcjogdmFyKC0tc3VjY2Vzcyk7IH0KCi8qIOKUgOKUgCBDaGVja2JveCDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIAgKi8KLmN1c3RvbS1jaGVjayB7IGRpc3BsYXk6IGZsZXg7IGFsaWduLWl0ZW1zOiBjZW50ZXI7IGdhcDogMC41cmVtOyBjdXJzb3I6IHBvaW50ZXI7IHVzZXItc2VsZWN0OiBub25lOyB9Ci5jdXN0b20tY2hlY2sgaW5wdXRbdHlwZT0iY2hlY2tib3giXSB7IHdpZHRoOiAxNnB4OyBoZWlnaHQ6IDE2cHg7IGFjY2VudC1jb2xvcjogdmFyKC0tcHJpbWFyeSk7IGN1cnNvcjogcG9pbnRlcjsgfQouY3VzdG9tLWNoZWNrIHNwYW4geyBmb250LXNpemU6IDAuODNyZW07IGZvbnQtZmFtaWx5OiB2YXIoLS1mb250LWJvZHkpOyBjb2xvcjogdmFyKC0tdGV4dC1zZWNvbmRhcnkpOyB9CgouZm9yZ290LWxpbmsgeyBmb250LXNpemU6IDAuODJyZW07IGZvbnQtZmFtaWx5OiB2YXIoLS1mb250LWJvZHkpOyBjb2xvcjogdmFyKC0tdGV4dC1tdXRlZCk7IHRleHQtZGVjb3JhdGlvbjogbm9uZTsgdHJhbnNpdGlvbjogY29sb3IgMC4ycyBlYXNlOyB9Ci5mb3Jnb3QtbGluazpob3ZlciB7IGNvbG9yOiB2YXIoLS1wcmltYXJ5KTsgfQoKLyog4pSA4pSAIEJ1dHRvbnMg4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSAICovCi5idG4tcHJpbWFyeS1jdXN0b20gewogIHdpZHRoOiAxMDAlOyBiYWNrZ3JvdW5kOiBsaW5lYXItZ3JhZGllbnQoMTM1ZGVnLCB2YXIoLS1wcmltYXJ5KSwgdmFyKC0tcHJpbWFyeS1kYXJrKSk7IGJvcmRlcjogbm9uZTsKICBib3JkZXItcmFkaXVzOiB2YXIoLS1yYWRpdXMtbWQpOyBwYWRkaW5nOiAwLjg1cmVtIDEuNXJlbTsgY29sb3I6ICNmZmY7CiAgZm9udC1mYW1pbHk6IHZhcigtLWZvbnQtcHJpbWFyeSk7IGZvbnQtc2l6ZTogMXJlbTsgZm9udC13ZWlnaHQ6IDcwMDsgY3Vyc29yOiBwb2ludGVyOwogIHRyYW5zaXRpb246IGFsbCAwLjJzIGVhc2U7IGRpc3BsYXk6IGZsZXg7IGFsaWduLWl0ZW1zOiBjZW50ZXI7IGp1c3RpZnktY29udGVudDogY2VudGVyOyBnYXA6IDAuNHJlbTsKICBib3gtc2hhZG93OiAwIDRweCAxNHB4IHJnYmEoOTksMTAyLDI0MSwwLjMpOwp9Ci5idG4tcHJpbWFyeS1jdXN0b206aG92ZXIgeyBiYWNrZ3JvdW5kOiBsaW5lYXItZ3JhZGllbnQoMTM1ZGVnLCB2YXIoLS1wcmltYXJ5LWRhcmspLCAjMzczMEEzKTsgY29sb3I6ICNmZmY7IGJveC1zaGFkb3c6IDAgNnB4IDIwcHggcmdiYSg5OSwxMDIsMjQxLDAuNCk7IHRyYW5zZm9ybTogdHJhbnNsYXRlWSgtMXB4KTsgfQouYnRuLXByaW1hcnktY3VzdG9tOmFjdGl2ZSB7IHRyYW5zZm9ybTogdHJhbnNsYXRlWSgwKTsgfQoKLmJ0bi1vdXRsaW5lLWN1c3RvbSB7CiAgd2lkdGg6IDEwMCU7IGJhY2tncm91bmQ6IHRyYW5zcGFyZW50OyBib3JkZXI6IDEuNXB4IHNvbGlkIHZhcigtLWJvcmRlcik7IGJvcmRlci1yYWRpdXM6IHZhcigtLXJhZGl1cy1tZCk7CiAgcGFkZGluZzogMC44MnJlbSAxLjVyZW07IGNvbG9yOiB2YXIoLS10ZXh0LXNlY29uZGFyeSk7IGZvbnQtZmFtaWx5OiB2YXIoLS1mb250LXByaW1hcnkpOwogIGZvbnQtc2l6ZTogMC45NXJlbTsgZm9udC13ZWlnaHQ6IDYwMDsgY3Vyc29yOiBwb2ludGVyOyB0cmFuc2l0aW9uOiB2YXIoLS10cmFuc2l0aW9uKTsKICB0ZXh0LWFsaWduOiBjZW50ZXI7IGRpc3BsYXk6IGJsb2NrOyB0ZXh0LWRlY29yYXRpb246IG5vbmU7Cn0KLmJ0bi1vdXRsaW5lLWN1c3RvbTpob3ZlciB7IGJvcmRlci1jb2xvcjogdmFyKC0tcHJpbWFyeSk7IGNvbG9yOiB2YXIoLS1wcmltYXJ5KTsgYmFja2dyb3VuZDogdmFyKC0tcHJpbWFyeS1saWdodCk7IH0KCi8qIOKUgOKUgCBGbGFzaCBBbGVydHMg4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSAICovCi5hbGVydC1jdXN0b20gewogIGJvcmRlci1yYWRpdXM6IHZhcigtLXJhZGl1cy1tZCk7IHBhZGRpbmc6IDAuOHJlbSAxcmVtOyBmb250LWZhbWlseTogdmFyKC0tZm9udC1ib2R5KTsKICBmb250LXNpemU6IDAuODdyZW07IGJvcmRlcjogMXB4IHNvbGlkIHRyYW5zcGFyZW50OyBkaXNwbGF5OiBmbGV4OyBhbGlnbi1pdGVtczogY2VudGVyOwogIGdhcDogMC42cmVtOyBtYXJnaW4tYm90dG9tOiAxLjFyZW07Cn0KLmFsZXJ0LXN1Y2Nlc3MgeyBiYWNrZ3JvdW5kOiByZ2JhKDE2LDE4NSwxMjksMC4xMCk7IGJvcmRlci1jb2xvcjogcmdiYSgxNiwxODUsMTI5LDAuMzApOyBjb2xvcjogIzM0RDM5OTsgfQouYWxlcnQtZGFuZ2VyIHsgYmFja2dyb3VuZDogcmdiYSgyMzksNjgsNjgsMC4xMCk7IGJvcmRlci1jb2xvcjogcmdiYSgyMzksNjgsNjgsMC4zMCk7IGNvbG9yOiAjRjg3MTcxOyB9Ci5hbGVydC13YXJuaW5nIHsgYmFja2dyb3VuZDogcmdiYSgyNDUsMTU4LDExLDAuMTApOyBib3JkZXItY29sb3I6IHJnYmEoMjQ1LDE1OCwxMSwwLjMwKTsgY29sb3I6ICNGQkJGMjQ7IH0KLmFsZXJ0LWluZm8geyBiYWNrZ3JvdW5kOiByZ2JhKDU5LDEzMCwyNDYsMC4xMCk7IGJvcmRlci1jb2xvcjogcmdiYSg1OSwxMzAsMjQ2LDAuMjUpOyBjb2xvcjogIzkzQzVGRDsgfQoKLyog4pSA4pSAIEF1dGggRm9vdGVyIOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgCAqLwouYXV0aC1mb290ZXIgeyB0ZXh0LWFsaWduOiBjZW50ZXI7IG1hcmdpbi10b3A6IDEuMjVyZW07IGZvbnQtc2l6ZTogMC44MnJlbTsgZm9udC1mYW1pbHk6IHZhcigtLWZvbnQtYm9keSk7IGNvbG9yOiB2YXIoLS10ZXh0LW11dGVkKTsgfQouYXV0aC1mb290ZXIgYSB7IGNvbG9yOiB2YXIoLS1wcmltYXJ5KTsgdGV4dC1kZWNvcmF0aW9uOiBub25lOyBmb250LXdlaWdodDogNjAwOyB9Ci5hdXRoLWZvb3RlciBhOmhvdmVyIHsgY29sb3I6ICNmZmY7IH0KCkBtZWRpYSAobWF4LXdpZHRoOiA3NjhweCkgeyAuZ2xhc3MtY2FyZCB7IHBhZGRpbmc6IDJyZW0gMS40cmVtOyB9IC5hdXRoLXRpdGxlIHsgZm9udC1zaXplOiAxLjNyZW07IH0gLnBhc3N3b3JkLXJ1bGVzIHsgZ3JpZC10ZW1wbGF0ZS1jb2x1bW5zOiAxZnI7IH0gfQoKLyog4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQCiAgIERBU0hCT0FSRCBTVFlMRVMKICAg4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQ4pWQICovCi5kYXNoLW5hdmJhciB7IHBvc2l0aW9uOiBzdGlja3k7IHRvcDogMDsgei1pbmRleDogMTAwOyBiYWNrZ3JvdW5kOiB2YXIoLS1iZy1kYXJrKTsgYm9yZGVyLWJvdHRvbTogMXB4IHNvbGlkIHZhcigtLWJvcmRlcik7IHBhZGRpbmc6IDAuODVyZW0gMDsgfQoubmF2YmFyLWJyYW5kLWN1c3RvbSB7IGZvbnQtc2l6ZTogMS40cmVtOyBmb250LXdlaWdodDogODAwOyBjb2xvcjogdmFyKC0tdGV4dC1wcmltYXJ5KTsgdGV4dC1kZWNvcmF0aW9uOiBub25lOyB9Ci5kYXNoLW5hdi1sb2dvLWltZyB7IHdpZHRoOiAzNHB4OyBoZWlnaHQ6IDM0cHg7IGJvcmRlci1yYWRpdXM6IDlweDsgb2JqZWN0LWZpdDogY292ZXI7IGZsZXgtc2hyaW5rOiAwOyB9Ci51c2VyLWF2YXRhciB7IHdpZHRoOiAzOHB4OyBoZWlnaHQ6IDM4cHg7IGJhY2tncm91bmQ6IHZhcigtLXByaW1hcnkpOyBib3JkZXItcmFkaXVzOiA1MCU7IGRpc3BsYXk6IGZsZXg7IGFsaWduLWl0ZW1zOiBjZW50ZXI7IGp1c3RpZnktY29udGVudDogY2VudGVyOyBmb250LXdlaWdodDogNzAwOyBmb250LXNpemU6IDAuOTVyZW07IGNvbG9yOiAjZmZmOyBmbGV4LXNocmluazogMDsgfQouZGFzaC13ZWxjb21lLXRleHQgeyBmb250LXNpemU6IDAuNzhyZW07IGNvbG9yOiB2YXIoLS10ZXh0LW11dGVkKTsgZm9udC1mYW1pbHk6IHZhcigtLWZvbnQtYm9keSk7IH0KLmRhc2gtdXNlci1uYW1lIHsgZm9udC1zaXplOiAwLjkzcmVtOyBmb250LXdlaWdodDogNjAwOyBjb2xvcjogdmFyKC0tdGV4dC1wcmltYXJ5KTsgfQouYnRuLWxvZ291dCB7CiAgYmFja2dyb3VuZDogcmdiYSgyMzksNjgsNjgsMC4xMCk7IGJvcmRlcjogMXB4IHNvbGlkIHJnYmEoMjM5LDY4LDY4LDAuMjUpOyBjb2xvcjogI0Y4NzE3MTsKICBib3JkZXItcmFkaXVzOiB2YXIoLS1yYWRpdXMtbWQpOyBwYWRkaW5nOiAwLjQ4cmVtIDFyZW07IGZvbnQtZmFtaWx5OiB2YXIoLS1mb250LXByaW1hcnkpOwogIGZvbnQtc2l6ZTogMC44OHJlbTsgZm9udC13ZWlnaHQ6IDYwMDsgY3Vyc29yOiBwb2ludGVyOyB0cmFuc2l0aW9uOiB2YXIoLS10cmFuc2l0aW9uKTsKICB0ZXh0LWRlY29yYXRpb246IG5vbmU7IGRpc3BsYXk6IGlubGluZS1mbGV4OyBhbGlnbi1pdGVtczogY2VudGVyOyBnYXA6IDAuNHJlbTsKfQouYnRuLWxvZ291dDpob3ZlciB7IGJhY2tncm91bmQ6IHJnYmEoMjM5LDY4LDY4LDAuMjApOyBib3JkZXItY29sb3I6IHJnYmEoMjM5LDY4LDY4LDAuNSk7IGNvbG9yOiAjRUY0NDQ0OyB9CgovKiDilIDilIAgRGFzaGJvYXJkIEhlcm8g4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSAICovCi5kYXNoLWhlcm8geyBiYWNrZ3JvdW5kOiB2YXIoLS1iZy1jYXJkKTsgYm9yZGVyOiAxcHggc29saWQgdmFyKC0tYm9yZGVyKTsgYm9yZGVyLXJhZGl1czogdmFyKC0tcmFkaXVzLXhsKTsgcGFkZGluZzogMnJlbSAyLjVyZW07IHBvc2l0aW9uOiByZWxhdGl2ZTsgb3ZlcmZsb3c6IGhpZGRlbjsgbWFyZ2luLWJvdHRvbTogMS43NXJlbTsgfQouZGFzaC1oZXJvLWdyZWV0aW5nIHsgZm9udC1zaXplOiAwLjg4cmVtOyBjb2xvcjogdmFyKC0tcHJpbWFyeSk7IGZvbnQtd2VpZ2h0OiA2MDA7IGxldHRlci1zcGFjaW5nOiAwLjNweDsgbWFyZ2luLWJvdHRvbTogMC4zNXJlbTsgZm9udC1mYW1pbHk6IHZhcigtLWZvbnQtYm9keSk7IH0KLmRhc2gtaGVyby10aXRsZSB7IGZvbnQtc2l6ZTogMS44cmVtOyBmb250LXdlaWdodDogODAwOyBjb2xvcjogdmFyKC0tdGV4dC1wcmltYXJ5KTsgbWFyZ2luLWJvdHRvbTogMC40cmVtOyB9Ci5kYXNoLWhlcm8tdGl0bGUgc3BhbiB7IGNvbG9yOiB2YXIoLS1wcmltYXJ5KTsgfQouZGFzaC1oZXJvLXN1YiB7IGZvbnQtc2l6ZTogMC44OHJlbTsgZm9udC1mYW1pbHk6IHZhcigtLWZvbnQtYm9keSk7IGNvbG9yOiB2YXIoLS10ZXh0LXNlY29uZGFyeSk7IH0KCi8qIOKUgOKUgCBTdGF0IENhcmRzIOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgCAqLwouc3RhdC1jYXJkIHsgYmFja2dyb3VuZDogdmFyKC0tYmctY2FyZCk7IGJvcmRlcjogMXB4IHNvbGlkIHZhcigtLWJvcmRlcik7IGJvcmRlci1yYWRpdXM6IHZhcigtLXJhZGl1cy1sZyk7IHBhZGRpbmc6IDEuNHJlbTsgdHJhbnNpdGlvbjogdHJhbnNmb3JtIDAuM3MgZWFzZSwgYm9yZGVyLWNvbG9yIDAuM3MgZWFzZSwgYm94LXNoYWRvdyAwLjNzIGVhc2U7IGN1cnNvcjogZGVmYXVsdDsgfQouc3RhdC1jYXJkOmhvdmVyIHsgdHJhbnNmb3JtOiB0cmFuc2xhdGVZKC00cHgpOyBib3JkZXItY29sb3I6IHJnYmEoOTksMTAyLDI0MSwwLjI1KTsgYm94LXNoYWRvdzogdmFyKC0tc2hhZG93LW1kKTsgfQouc3RhdC1jYXJkLWljb24geyB3aWR0aDogNDhweDsgaGVpZ2h0OiA0OHB4OyBib3JkZXItcmFkaXVzOiB2YXIoLS1yYWRpdXMtbWQpOyBkaXNwbGF5OiBmbGV4OyBhbGlnbi1pdGVtczogY2VudGVyOyBqdXN0aWZ5LWNvbnRlbnQ6IGNlbnRlcjsgZm9udC1zaXplOiAxLjNyZW07IG1hcmdpbi1ib3R0b206IDFyZW07IGJhY2tncm91bmQ6IHZhcigtLXByaW1hcnktbGlnaHQpOyB9Ci5zdGF0LWxhYmVsIHsgZm9udC1zaXplOiAwLjc2cmVtOyBmb250LWZhbWlseTogdmFyKC0tZm9udC1ib2R5KTsgY29sb3I6IHZhcigtLXRleHQtbXV0ZWQpOyB0ZXh0LXRyYW5zZm9ybTogdXBwZXJjYXNlOyBsZXR0ZXItc3BhY2luZzogMC43cHg7IGZvbnQtd2VpZ2h0OiA2MDA7IG1hcmdpbi1ib3R0b206IDAuMzVyZW07IH0KLnN0YXQtdmFsdWUgeyBmb250LXNpemU6IDEuNjVyZW07IGZvbnQtd2VpZ2h0OiA4MDA7IGNvbG9yOiB2YXIoLS10ZXh0LXByaW1hcnkpOyBsaW5lLWhlaWdodDogMTsgbWFyZ2luLWJvdHRvbTogMC40NXJlbTsgfQouc3RhdC1jaGFuZ2UgeyBmb250LXNpemU6IDAuNzZyZW07IGZvbnQtZmFtaWx5OiB2YXIoLS1mb250LWJvZHkpOyBkaXNwbGF5OiBmbGV4OyBhbGlnbi1pdGVtczogY2VudGVyOyBnYXA6IDAuMnJlbTsgfQouc3RhdC1jaGFuZ2UudXAgeyBjb2xvcjogdmFyKC0tc3VjY2Vzcyk7IH0KLnN0YXQtY2hhbmdlLmRvd24geyBjb2xvcjogdmFyKC0tZGFuZ2VyKTsgfQoKLyog4pSA4pSAIERhc2hib2FyZCBUYWJsZSDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIAgKi8KLmRhc2gtc2VjdGlvbi10aXRsZSB7IGZvbnQtc2l6ZTogMS4wNXJlbTsgZm9udC13ZWlnaHQ6IDcwMDsgY29sb3I6IHZhcigtLXRleHQtcHJpbWFyeSk7IG1hcmdpbi1ib3R0b206IDEuMXJlbTsgZGlzcGxheTogZmxleDsgYWxpZ24taXRlbXM6IGNlbnRlcjsgZ2FwOiAwLjVyZW07IH0KLmRhc2gtc2VjdGlvbi10aXRsZTo6YWZ0ZXIgeyBjb250ZW50OiAnJzsgZmxleDogMTsgaGVpZ2h0OiAxcHg7IGJhY2tncm91bmQ6IHZhcigtLWJvcmRlcik7IH0KLmRhc2gtdGFibGUtd3JhcHBlciB7IGJhY2tncm91bmQ6IHZhcigtLWJnLWNhcmQpOyBib3JkZXI6IDFweCBzb2xpZCB2YXIoLS1ib3JkZXIpOyBib3JkZXItcmFkaXVzOiB2YXIoLS1yYWRpdXMtbGcpOyBvdmVyZmxvdzogaGlkZGVuOyB9Ci5kYXNoLXRhYmxlIHsgd2lkdGg6IDEwMCU7IGJvcmRlci1jb2xsYXBzZTogY29sbGFwc2U7IGZvbnQtZmFtaWx5OiB2YXIoLS1mb250LWJvZHkpOyB9Ci5kYXNoLXRhYmxlIHRoZWFkIHRoIHsgcGFkZGluZzogMC45cmVtIDEuMXJlbTsgZm9udC1zaXplOiAwLjc0cmVtOyBmb250LXdlaWdodDogNzAwOyBjb2xvcjogdmFyKC0tdGV4dC1tdXRlZCk7IHRleHQtdHJhbnNmb3JtOiB1cHBlcmNhc2U7IGxldHRlci1zcGFjaW5nOiAwLjdweDsgYm9yZGVyLWJvdHRvbTogMXB4IHNvbGlkIHZhcigtLWJvcmRlcik7IGJhY2tncm91bmQ6IHJnYmEoMjU1LDI1NSwyNTUsMC4wMik7IH0KLmRhc2gtdGFibGUgdGJvZHkgdGQgeyBwYWRkaW5nOiAwLjg1cmVtIDEuMXJlbTsgZm9udC1zaXplOiAwLjg3cmVtOyBjb2xvcjogdmFyKC0tdGV4dC1zZWNvbmRhcnkpOyBib3JkZXItYm90dG9tOiAxcHggc29saWQgcmdiYSgyNTUsMjU1LDI1NSwwLjA0KTsgfQouZGFzaC10YWJsZSB0Ym9keSB0cjpsYXN0LWNoaWxkIHRkIHsgYm9yZGVyLWJvdHRvbTogbm9uZTsgfQouZGFzaC10YWJsZSB0Ym9keSB0cjpob3ZlciB0ZCB7IGJhY2tncm91bmQ6IHJnYmEoMjU1LDI1NSwyNTUsMC4wMik7IH0KCi50eG4tdHlwZS1iYWRnZSB7IGRpc3BsYXk6IGlubGluZS1mbGV4OyBhbGlnbi1pdGVtczogY2VudGVyOyBnYXA6IDAuM3JlbTsgcGFkZGluZzogMC4yMnJlbSAwLjdyZW07IGJvcmRlci1yYWRpdXM6IHZhcigtLXJhZGl1cy1mdWxsKTsgZm9udC1zaXplOiAwLjc0cmVtOyBmb250LXdlaWdodDogNjAwOyB9Ci5iYWRnZS1pbmNvbWUgeyBiYWNrZ3JvdW5kOiByZ2JhKDE2LDE4NSwxMjksMC4xMik7IGNvbG9yOiB2YXIoLS1zdWNjZXNzKTsgfQouYmFkZ2UtZXhwZW5zZSB7IGJhY2tncm91bmQ6IHJnYmEoMjM5LDY4LDY4LDAuMTIpOyBjb2xvcjogdmFyKC0tZGFuZ2VyKTsgfQouYmFkZ2UtaW52ZXN0IHsgYmFja2dyb3VuZDogcmdiYSg5OSwxMDIsMjQxLDAuMTIpOyBjb2xvcjogdmFyKC0tcHJpbWFyeSk7IH0KCi8qIOKUgOKUgCBUeXBpbmcgY3Vyc29yIChkYXNoYm9hcmQpIOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgCAqLwoudHlwaW5nLWN1cnNvciB7IGRpc3BsYXk6IGlubGluZS1ibG9jazsgd2lkdGg6IDJweDsgYmFja2dyb3VuZDogdmFyKC0tcHJpbWFyeSk7IGFuaW1hdGlvbjogYmxpbmsgMC44cyBzdGVwLWVuZCBpbmZpbml0ZTsgbWFyZ2luLWxlZnQ6IDJweDsgdmVydGljYWwtYWxpZ246IG1pZGRsZTsgfQpAa2V5ZnJhbWVzIGJsaW5rIHsgNTAlIHsgb3BhY2l0eTogMDsgfSB9CgovKiDilIDilIAgVXRpbGl0eSDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIAgKi8KLnRleHQtZ3JhZGllbnQgeyBiYWNrZ3JvdW5kOiBsaW5lYXItZ3JhZGllbnQoMTM1ZGVnLCB2YXIoLS1wcmltYXJ5KSwgdmFyKC0tYWNjZW50KSk7IC13ZWJraXQtYmFja2dyb3VuZC1jbGlwOiB0ZXh0OyAtd2Via2l0LXRleHQtZmlsbC1jb2xvcjogdHJhbnNwYXJlbnQ7IGJhY2tncm91bmQtY2xpcDogdGV4dDsgfQouc3Itb25seSB7IHBvc2l0aW9uOiBhYnNvbHV0ZTsgd2lkdGg6IDFweDsgaGVpZ2h0OiAxcHg7IHBhZGRpbmc6IDA7IG1hcmdpbjogLTFweDsgb3ZlcmZsb3c6IGhpZGRlbjsgY2xpcDogcmVjdCgwLDAsMCwwKTsgd2hpdGUtc3BhY2U6IG5vd3JhcDsgYm9yZGVyOiAwOyB9Cg=='
DASHBOARD_CSS_B64 = 'OnJvb3QgewogIC0tcGFnZS1iZzogI0Y4RkFGQzsKICAtLXNpZGViYXItYmc6ICMwOTBEMUE7CiAgLS1zaWRlYmFyLW11dGVkOiAjOTRBM0I4OwogIC0tc2lkZXJiYXItaG92ZXI6IHJnYmEoMjU1LCAyNTUsIDI1NSwgMC4wNik7CiAgLS1wcmltYXJ5LWJsdWU6ICMzQjgyRjY7CiAgLS1wcmltYXJ5LWJsdWUtMjogIzYwQTVGQTsKICAtLW9yYW5nZTogI0Y5NzMxNjsKICAtLW9yYW5nZS0yOiAjRkI5MjNDOwogIC0tdGVhbDogIzEwQjk4MTsKICAtLXRlYWwtMjogIzM0RDM5OTsKICAtLXB1cnBsZTogIzhCNUNGNjsKICAtLXB1cnBsZS0yOiAjQTc4QkZBOwogIC0tdGV4dC1kYXJrOiAjMEYxNzJBOwogIC0tdGV4dC1tdXRlZDogIzY0NzQ4QjsKICAtLXN1Y2Nlc3M6ICMxMEI5ODE7CiAgLS1kYW5nZXI6ICNFRjQ0NDQ7CiAgLS13aGl0ZTogI0ZGRkZGRjsKICAtLWJvcmRlci1yYWRpdXMtY2FyZDogMTZweDsKICAtLWJvcmRlci1yYWRpdXMtcGlsbDogMTBweDsKICAtLXNoYWRvdzogMCAxMHB4IDI1cHggLTVweCByZ2JhKDE1LCAyMywgNDIsIDAuMDQpLCAwIDhweCAxMHB4IC02cHggcmdiYSgxNSwgMjMsIDQyLCAwLjA0KTsKfQoKKiB7IGJveC1zaXppbmc6IGJvcmRlci1ib3g7IH0KCmJvZHkgewogIG1hcmdpbjogMDsKICBmb250LWZhbWlseTogJ091dGZpdCcsICdJbnRlcicsIHN5c3RlbS11aSwgLWFwcGxlLXN5c3RlbSwgQmxpbmtNYWNTeXN0ZW1Gb250LCAnU2Vnb2UgVUknLCBzYW5zLXNlcmlmOwogIGJhY2tncm91bmQ6IHZhcigtLXBhZ2UtYmcpOwogIGNvbG9yOiB2YXIoLS10ZXh0LWRhcmspOwogIG92ZXJmbG93LXg6IGhpZGRlbjsKfQoKaW1nIHsgbWF4LXdpZHRoOiAxMDAlOyB9CmEgeyBjb2xvcjogaW5oZXJpdDsgdGV4dC1kZWNvcmF0aW9uOiBub25lOyB9Cgouc2lkZWJhciB7CiAgd2lkdGg6IDI2MHB4OwogIG1pbi1oZWlnaHQ6IDEwMHZoOwogIGJhY2tncm91bmQ6IGxpbmVhci1ncmFkaWVudCgxODVkZWcsICMwOTBEMUEgMCUsICMxRTFCNEIgMTAwJSk7CiAgY29sb3I6IHZhcigtLXdoaXRlKTsKICBwYWRkaW5nOiAyNHB4IDE4cHggMjBweDsKICBwb3NpdGlvbjogZml4ZWQ7CiAgdG9wOiAwOwogIGxlZnQ6IC0yNjBweDsKICBib3R0b206IDA7CiAgei1pbmRleDogMTAwMDsKICBkaXNwbGF5OiBmbGV4OwogIGZsZXgtZGlyZWN0aW9uOiBjb2x1bW47CiAgdHJhbnNpdGlvbjogbGVmdCAwLjNzIGN1YmljLWJlemllcigwLjI1LCAwLjgsIDAuMjUsIDEpOwogIGJveC1zaGFkb3c6IDRweCAwIDI0cHggcmdiYSgxNSwgMjMsIDQyLCAwLjE1KTsKfQouc2lkZWJhci5vcGVuIHsKICBsZWZ0OiAwOwp9CgouZmxvYXRpbmctaGFtYnVyZ2VyIHsKICBwb3NpdGlvbjogZml4ZWQ7CiAgdG9wOiAyMHB4OwogIGxlZnQ6IDIwcHg7CiAgei1pbmRleDogOTk5OwogIHdpZHRoOiA0NnB4OwogIGhlaWdodDogNDZweDsKICBib3JkZXItcmFkaXVzOiAxMnB4OwogIGJhY2tncm91bmQ6ICNGRkZGRkY7CiAgYm9yZGVyOiAxLjVweCBzb2xpZCAjRTJFOEYwOwogIGNvbG9yOiAjMUUyOTNCOwogIGRpc3BsYXk6IGdyaWQ7CiAgcGxhY2UtaXRlbXM6IGNlbnRlcjsKICBmb250LXNpemU6IDEuNDVyZW07CiAgY3Vyc29yOiBwb2ludGVyOwogIGJveC1zaGFkb3c6IDAgNHB4IDEycHggcmdiYSgxNSwgMjMsIDQyLCAwLjA4KTsKICB0cmFuc2l0aW9uOiB0cmFuc2Zvcm0gMC4zcyBjdWJpYy1iZXppZXIoMC4yNSwgMC44LCAwLjI1LCAxKSwgYmFja2dyb3VuZC1jb2xvciAwLjJzLCBib3JkZXItY29sb3IgMC4yczsKfQouZmxvYXRpbmctaGFtYnVyZ2VyOmhvdmVyIHsKICBiYWNrZ3JvdW5kLWNvbG9yOiAjRjhGQUZDOwogIGJvcmRlci1jb2xvcjogI0NCRDVFMTsKfQoKYm9keS5zaWRlYmFyLW9wZW4gLmZsb2F0aW5nLWhhbWJ1cmdlciB7CiAgdHJhbnNmb3JtOiB0cmFuc2xhdGVYKDI2MHB4KTsKfQoKCgoubG9nby1yb3cgeyBkaXNwbGF5OiBmbGV4OyBhbGlnbi1pdGVtczogY2VudGVyOyBnYXA6IDEycHg7IG1hcmdpbi1ib3R0b206IDI4cHg7IH0KLmxvZ28taWNvbiB7CiAgd2lkdGg6IDQ2cHg7IGhlaWdodDogNDZweDsKICBib3JkZXItcmFkaXVzOiAxNHB4OwogIGJhY2tncm91bmQ6IGxpbmVhci1ncmFkaWVudCgxMzVkZWcsIHZhcigtLXByaW1hcnktYmx1ZS0yKSwgdmFyKC0tcHVycGxlKSk7CiAgdHJhbnNmb3JtOiByb3RhdGUoNDVkZWcpOwogIGRpc3BsYXk6IGdyaWQ7IHBsYWNlLWl0ZW1zOiBjZW50ZXI7CiAgYm94LXNoYWRvdzogaW5zZXQgMCAycHggNHB4IHJnYmEoMjU1LDI1NSwyNTUsMC4xNSk7Cn0KLmxvZ28taWNvbiBpIHsgdHJhbnNmb3JtOiByb3RhdGUoLTQ1ZGVnKTsgZm9udC1zaXplOiAyMHB4OyB9Ci5sb2dvLXRleHQgaDMgeyBtYXJnaW46IDA7IGZvbnQtc2l6ZTogMS4xMjVyZW07IGZvbnQtd2VpZ2h0OiA3MDA7IGxldHRlci1zcGFjaW5nOiAtMC4wMmVtOyB9Ci5sb2dvLXRleHQgc21hbGwgeyBjb2xvcjogdmFyKC0tc2lkZWJhci1tdXRlZCk7IGRpc3BsYXk6IGJsb2NrOyBtYXJnaW4tdG9wOiAycHg7IH0KCi5uYXYtbGlzdCB7IGRpc3BsYXk6IGZsZXg7IGZsZXgtZGlyZWN0aW9uOiBjb2x1bW47IGdhcDogOHB4OyB9Ci5uYXYtaXRlbSB7CiAgZGlzcGxheTogZmxleDsgYWxpZ24taXRlbXM6IGNlbnRlcjsgZ2FwOiAxMnB4OwogIHBhZGRpbmc6IDEycHggMTJweDsgYm9yZGVyLXJhZGl1czogMTBweDsKICBjb2xvcjogdmFyKC0tc2lkZWJhci1tdXRlZCk7IGZvbnQtc2l6ZTogMC45MjVyZW07CiAgdHJhbnNpdGlvbjogYWxsIDAuMnMgZWFzZTsgY3Vyc29yOiBwb2ludGVyOwp9Ci5uYXYtaXRlbTpob3ZlciB7IGJhY2tncm91bmQ6IHZhcigtLXNpZGVyYmFyLWhvdmVyKTsgY29sb3I6IHZhcigtLXdoaXRlKTsgfQoubmF2LWl0ZW0uYWN0aXZlIHsgYmFja2dyb3VuZDogbGluZWFyLWdyYWRpZW50KDEzNWRlZywgIzNCODJGNiwgIzI1NjNFQik7IGNvbG9yOiB2YXIoLS13aGl0ZSk7IGJveC1zaGFkb3c6IDAgNHB4IDEycHggcmdiYSgzNywgOTksIDIzNSwgMC4zNSk7IH0KCi5zaWRlYmFyLXByb21vIHsKICBtYXJnaW4tdG9wOiBhdXRvOwogIGJhY2tncm91bmQ6IHJnYmEoMjU1LDI1NSwyNTUsMC4wNSk7CiAgYm9yZGVyOiAxcHggc29saWQgcmdiYSgyNTUsMjU1LDI1NSwwLjA4KTsKICBib3JkZXItcmFkaXVzOiAxNnB4OyBwYWRkaW5nOiAxNnB4Owp9Ci5zaWRlYmFyLXByb21vIGg2IHsgbWFyZ2luOiAwIDAgOHB4OyBmb250LXNpemU6IDAuOTVyZW07IGZvbnQtd2VpZ2h0OiA3MDA7IH0KLnNpZGViYXItcHJvbW8gcCB7IG1hcmdpbjogMCAwIDE0cHg7IGNvbG9yOiB2YXIoLS1zaWRlYmFyLW11dGVkKTsgZm9udC1zaXplOiAwLjgycmVtOyBsaW5lLWhlaWdodDogMS41OyB9Ci5zaWRlYmFyLXByb21vIC5idG4geyB3aWR0aDogMTAwJTsgYm9yZGVyLXJhZGl1czogMTBweDsgYmFja2dyb3VuZDogdmFyKC0tcHJpbWFyeS1ibHVlKTsgYm9yZGVyOiAwOyB9Cgouc2lkZWJhci1yZWZyZXNoLWJ0biB7CiAgZGlzcGxheTogZmxleDsgYWxpZ24taXRlbXM6IGNlbnRlcjsgZ2FwOiAxMHB4OwogIHdpZHRoOiAxMDAlOyBtYXJnaW46IDEwcHggMCA4cHg7CiAgcGFkZGluZzogMTBweCAxMnB4OyBib3JkZXItcmFkaXVzOiAxMHB4OwogIGJhY2tncm91bmQ6IHJnYmEoNTksMTMwLDI0NiwwLjEyKTsKICBib3JkZXI6IDFweCBzb2xpZCByZ2JhKDU5LDEzMCwyNDYsMC4yMik7CiAgY29sb3I6ICM5M0M1RkQ7IGZvbnQtc2l6ZTogMC45cmVtOyBmb250LXdlaWdodDogNjAwOwogIGN1cnNvcjogcG9pbnRlcjsgdGV4dC1hbGlnbjogbGVmdDsKICB0cmFuc2l0aW9uOiBiYWNrZ3JvdW5kIDAuMnMsIGNvbG9yIDAuMnMsIGJvcmRlci1jb2xvciAwLjJzOwp9Ci5zaWRlYmFyLXJlZnJlc2gtYnRuOmhvdmVyIHsgYmFja2dyb3VuZDogcmdiYSg1OSwxMzAsMjQ2LDAuMik7IGNvbG9yOiAjQkZEQkZFOyBib3JkZXItY29sb3I6IHJnYmEoNTksMTMwLDI0NiwwLjQpOyB9Ci5zaWRlYmFyLXJlZnJlc2gtYnRuLnJlZnJlc2hpbmcgeyBvcGFjaXR5OiAwLjc7IHBvaW50ZXItZXZlbnRzOiBub25lOyB9Ci5zaWRlYmFyLXJlZnJlc2gtYnRuLnJlZnJlc2hpbmcgaSB7IGFuaW1hdGlvbjogc3BpbiAwLjhzIGxpbmVhciBpbmZpbml0ZTsgfQouc2lkZWJhci1yZWZyZXNoLWJ0biBpIHsgZm9udC1zaXplOiAxcmVtOyB9CkBrZXlmcmFtZXMgc3BpbiB7IHRvIHsgdHJhbnNmb3JtOiByb3RhdGUoMzYwZGVnKTsgfSB9Cgouc2lkZWJhci1yZXNldC1idG4gewogIGRpc3BsYXk6IGZsZXg7IGFsaWduLWl0ZW1zOiBjZW50ZXI7IGdhcDogMTBweDsKICB3aWR0aDogMTAwJTsgbWFyZ2luOiA0cHggMCA4cHg7CiAgcGFkZGluZzogMTBweCAxMnB4OyBib3JkZXItcmFkaXVzOiAxMHB4OwogIGJhY2tncm91bmQ6IHJnYmEoMjM5LDY4LDY4LDAuMTIpOwogIGJvcmRlcjogMXB4IHNvbGlkIHJnYmEoMjM5LDY4LDY4LDAuMjIpOwogIGNvbG9yOiAjRkNBNUE1OyBmb250LXNpemU6IDAuOXJlbTsgZm9udC13ZWlnaHQ6IDYwMDsKICBjdXJzb3I6IHBvaW50ZXI7IHRleHQtYWxpZ246IGxlZnQ7CiAgdHJhbnNpdGlvbjogYmFja2dyb3VuZCAwLjJzLCBjb2xvciAwLjJzLCBib3JkZXItY29sb3IgMC4yczsKfQouc2lkZWJhci1yZXNldC1idG46aG92ZXIgeyBiYWNrZ3JvdW5kOiByZ2JhKDIzOSw2OCw2OCwwLjIpOyBjb2xvcjogI0ZFRTJFMjsgYm9yZGVyLWNvbG9yOiByZ2JhKDIzOSw2OCw2OCwwLjQpOyB9Ci5zaWRlYmFyLXJlc2V0LWJ0biBpIHsgZm9udC1zaXplOiAxcmVtOyB9Cgouc2lkZWJhci1sb2dvdXQtYnRuIHsKICBkaXNwbGF5OiBmbGV4OyBhbGlnbi1pdGVtczogY2VudGVyOyBnYXA6IDEwcHg7CiAgd2lkdGg6IDEwMCU7IG1hcmdpbjogNHB4IDAgOHB4OwogIHBhZGRpbmc6IDEwcHggMTJweDsgYm9yZGVyLXJhZGl1czogMTBweDsKICBiYWNrZ3JvdW5kOiByZ2JhKDU5LDEzMCwyNDYsMC4xMik7CiAgYm9yZGVyOiAxcHggc29saWQgcmdiYSg1OSwxMzAsMjQ2LDAuMjIpOwogIGNvbG9yOiAjOTNDNUZEOyBmb250LXNpemU6IDAuOXJlbTsgZm9udC13ZWlnaHQ6IDYwMDsKICBjdXJzb3I6IHBvaW50ZXI7IHRleHQtYWxpZ246IGxlZnQ7CiAgdHJhbnNpdGlvbjogYmFja2dyb3VuZCAwLjJzLCBjb2xvciAwLjJzLCBib3JkZXItY29sb3IgMC4yczsKICB0ZXh0LWRlY29yYXRpb246IG5vbmU7Cn0KLnNpZGViYXItbG9nb3V0LWJ0bjpob3ZlciB7IGJhY2tncm91bmQ6IHJnYmEoNTksMTMwLDI0NiwwLjIpOyBjb2xvcjogI0JGREJGRTsgYm9yZGVyLWNvbG9yOiByZ2JhKDU5LDEzMCwyNDYsMC40KTsgfQouc2lkZWJhci1sb2dvdXQtYnRuIGkgeyBmb250LXNpemU6IDFyZW07IH0KCgoKLm1haW4tcGFuZWwgewogIGZsZXg6IDE7CiAgcGFkZGluZzogODZweCAyNHB4IDMwcHg7CiAgbWFyZ2luLWxlZnQ6IDA7CiAgdHJhbnNpdGlvbjogdHJhbnNmb3JtIDAuM3MgY3ViaWMtYmV6aWVyKDAuMjUsIDAuOCwgMC4yNSwgMSksIHdpZHRoIDAuM3MgY3ViaWMtYmV6aWVyKDAuMjUsIDAuOCwgMC4yNSwgMSk7CiAgd2lkdGg6IDEwMCU7Cn0KCmJvZHkuc2lkZWJhci1vcGVuIC5tYWluLXBhbmVsIHsKICB0cmFuc2Zvcm06IHRyYW5zbGF0ZVgoMjYwcHgpOwogIHdpZHRoOiBjYWxjKDEwMCUgLSAyNjBweCk7Cn0KCgoudG9wYmFyIHsKICBiYWNrZ3JvdW5kOiB2YXIoLS13aGl0ZSk7IGJvcmRlci1yYWRpdXM6IDE2cHg7CiAgcGFkZGluZzogMCAyNHB4OyBoZWlnaHQ6IDY0cHg7CiAgZGlzcGxheTogZmxleDsgYWxpZ24taXRlbXM6IGNlbnRlcjsganVzdGlmeS1jb250ZW50OiBzcGFjZS1iZXR3ZWVuOwogIGJveC1zaGFkb3c6IHZhcigtLXNoYWRvdyk7CiAgYm9yZGVyOiAxcHggc29saWQgcmdiYSgyMjYsIDIzMiwgMjQwLCAwLjgpOwp9Ci50b3BiYXItbGVmdCB7IGRpc3BsYXk6IGZsZXg7IGFsaWduLWl0ZW1zOiBjZW50ZXI7IGdhcDogMTJweDsgZmxleDogMTsgfQouaGFtYnVyZ2VyIHsKICB3aWR0aDogNDBweDsgaGVpZ2h0OiA0MHB4OyBib3JkZXItcmFkaXVzOiA1MCU7CiAgYm9yZGVyOiAxcHggc29saWQgI0UyRThGMDsgZGlzcGxheTogZ3JpZDsgcGxhY2UtaXRlbXM6IGNlbnRlcjsKICBjb2xvcjogdmFyKC0tdGV4dC1kYXJrKTsgZm9udC1zaXplOiAxcmVtOwp9Ci5zZWFyY2gtYm94IHsKICBkaXNwbGF5OiBmbGV4OyBhbGlnbi1pdGVtczogY2VudGVyOyBnYXA6IDEwcHg7CiAgYmFja2dyb3VuZDogI0YxRjVGOTsgYm9yZGVyLXJhZGl1czogOTk5cHg7CiAgcGFkZGluZzogMCAxNnB4OyBoZWlnaHQ6IDQ0cHg7IGZsZXg6IDE7IG1heC13aWR0aDogNDYwcHg7Cn0KLnNlYXJjaC1ib3ggaSB7IGNvbG9yOiB2YXIoLS10ZXh0LW11dGVkKTsgfQouc2VhcmNoLWJveCBpbnB1dCB7IGJvcmRlcjogMDsgb3V0bGluZTogMDsgYmFja2dyb3VuZDogdHJhbnNwYXJlbnQ7IHdpZHRoOiAxMDAlOyBmb250LXNpemU6IDAuOTVyZW07IGNvbG9yOiB2YXIoLS10ZXh0LWRhcmspOyB9Ci5zZWFyY2gtYm94IC5zaG9ydGN1dCB7IGNvbG9yOiB2YXIoLS10ZXh0LW11dGVkKTsgZm9udC1zaXplOiAwLjhyZW07IGJhY2tncm91bmQ6IHJnYmEoMjU1LDI1NSwyNTUsMC44KTsgcGFkZGluZzogNHB4IDhweDsgYm9yZGVyLXJhZGl1czogOTk5cHg7IH0KCi50b3BiYXItcmlnaHQgeyBkaXNwbGF5OiBmbGV4OyBhbGlnbi1pdGVtczogY2VudGVyOyBnYXA6IDE0cHg7IH0KLnRvcGJhci1waWxsIHsgYm9yZGVyLXJhZGl1czogOTk5cHg7IHBhZGRpbmc6IDZweCAxMHB4OyBiYWNrZ3JvdW5kOiAjRjhGQUZDOyBjb2xvcjogdmFyKC0tdGV4dC1tdXRlZCk7IGZvbnQtc2l6ZTogMC43OHJlbTsgZGlzcGxheTogZmxleDsgYWxpZ24taXRlbXM6IGNlbnRlcjsgZ2FwOiA2cHg7IH0KLmljb24tYmFkZ2UgeyB3aWR0aDogNDBweDsgaGVpZ2h0OiA0MHB4OyBib3JkZXItcmFkaXVzOiA1MCU7IGJhY2tncm91bmQ6ICNGOEZBRkM7IGRpc3BsYXk6IGdyaWQ7IHBsYWNlLWl0ZW1zOiBjZW50ZXI7IGNvbG9yOiB2YXIoLS10ZXh0LWRhcmspOyBwb3NpdGlvbjogcmVsYXRpdmU7IH0KLmJhZGdlLWRvdCB7IHBvc2l0aW9uOiBhYnNvbHV0ZTsgdG9wOiA3cHg7IHJpZ2h0OiA4cHg7IHdpZHRoOiA4cHg7IGhlaWdodDogOHB4OyBib3JkZXItcmFkaXVzOiA1MCU7IGJvcmRlcjogMnB4IHNvbGlkIHZhcigtLXdoaXRlKTsgfQouYmFkZ2UtZG90LnJlZCB7IGJhY2tncm91bmQ6ICNFRjQ0NDQ7IH0KLmJhZGdlLWRvdC5wdXJwbGUgeyBiYWNrZ3JvdW5kOiAjOEI1Q0Y2OyB9Ci5jYWxlbmRhci1iYWRnZSB7IGRpc3BsYXk6IGZsZXg7IGFsaWduLWl0ZW1zOiBjZW50ZXI7IGdhcDogOHB4OyBiYWNrZ3JvdW5kOiAjRjhGQUZDOyBib3JkZXItcmFkaXVzOiA5OTlweDsgcGFkZGluZzogOHB4IDEwcHg7IH0KLmNhbGVuZGFyLWJhZGdlIC5kYXRlLWJsb2NrIHsgZGlzcGxheTogZmxleDsgZmxleC1kaXJlY3Rpb246IGNvbHVtbjsgbGluZS1oZWlnaHQ6IDEuMTsgfQouY2FsZW5kYXItYmFkZ2UgLmRhdGUtYmxvY2sgc3Ryb25nIHsgZm9udC1zaXplOiAwLjc1cmVtOyBjb2xvcjogdmFyKC0tdGV4dC1kYXJrKTsgfQouY2FsZW5kYXItYmFkZ2UgLmRhdGUtYmxvY2sgc3BhbiB7IGZvbnQtc2l6ZTogMC43cmVtOyBjb2xvcjogdmFyKC0tdGV4dC1tdXRlZCk7IH0KCi5wcm9maWxlLWNoaXAgeyBkaXNwbGF5OiBmbGV4OyBhbGlnbi1pdGVtczogY2VudGVyOyBnYXA6IDhweDsgfQouYXZhdGFyIHsgd2lkdGg6IDQwcHg7IGhlaWdodDogNDBweDsgYm9yZGVyLXJhZGl1czogNTAlOyBiYWNrZ3JvdW5kOiBsaW5lYXItZ3JhZGllbnQoMTM1ZGVnLCAjMEIxMjIwLCAjMTcyMjNBKTsgY29sb3I6IHZhcigtLXdoaXRlKTsgZGlzcGxheTogZ3JpZDsgcGxhY2UtaXRlbXM6IGNlbnRlcjsgZm9udC13ZWlnaHQ6IDcwMDsgfQoucHJvZmlsZS1uYW1lIHsgZGlzcGxheTogZmxleDsgZmxleC1kaXJlY3Rpb246IGNvbHVtbjsgbGluZS1oZWlnaHQ6IDEuMTU7IH0KLnByb2ZpbGUtbmFtZSBzdHJvbmcgeyBmb250LXNpemU6IDAuOXJlbTsgfQoucHJvZmlsZS1uYW1lIHNwYW4geyBmb250LXNpemU6IDAuNzVyZW07IGNvbG9yOiB2YXIoLS10ZXh0LW11dGVkKTsgfQoKLyogTG9nb3V0IGJ1dHRvbiBpbiB0b3BiYXIgKi8KLnRvcGJhci1sb2dvdXQgewogIGRpc3BsYXk6IGlubGluZS1mbGV4OyBhbGlnbi1pdGVtczogY2VudGVyOyBnYXA6IDZweDsKICBwYWRkaW5nOiA4cHggMTRweDsgYm9yZGVyLXJhZGl1czogOTk5cHg7CiAgYmFja2dyb3VuZDogcmdiYSgyMjAsIDM4LCAzOCwgMC4xKTsgY29sb3I6ICNEQzI2MjY7CiAgZm9udC1zaXplOiAwLjgycmVtOyBmb250LXdlaWdodDogNjAwOwogIHRyYW5zaXRpb246IGJhY2tncm91bmQgMC4yczsKfQoudG9wYmFyLWxvZ291dDpob3ZlciB7IGJhY2tncm91bmQ6IHJnYmEoMjIwLCAzOCwgMzgsIDAuMTgpOyB9CgouY29udGVudC1zdGFjayB7IGRpc3BsYXk6IGZsZXg7IGZsZXgtZGlyZWN0aW9uOiBjb2x1bW47IGdhcDogMjBweDsgbWFyZ2luLXRvcDogMjBweDsgfQoKLnN0YXQtcm93IHsgZGlzcGxheTogZ3JpZDsgZ3JpZC10ZW1wbGF0ZS1jb2x1bW5zOiByZXBlYXQoNCwgbWlubWF4KDAsIDFmcikpOyBnYXA6IDIwcHg7IH0KLnN0YXQtY2FyZCB7CiAgYm9yZGVyLXJhZGl1czogdmFyKC0tYm9yZGVyLXJhZGl1cy1jYXJkKTsgcGFkZGluZzogMjRweDsgY29sb3I6IHZhcigtLXdoaXRlKTsKICBtaW4taGVpZ2h0OiAxNDJweDsgZGlzcGxheTogZmxleDsganVzdGlmeS1jb250ZW50OiBzcGFjZS1iZXR3ZWVuOwogIHBvc2l0aW9uOiByZWxhdGl2ZTsgb3ZlcmZsb3c6IGhpZGRlbjsKfQouc3RhdC1jYXJkLmJsdWUgeyBiYWNrZ3JvdW5kOiBsaW5lYXItZ3JhZGllbnQoMTM1ZGVnLCAjM0I4MkY2LCAjMUQ0RUQ4KTsgYm94LXNoYWRvdzogMCAxMHB4IDIwcHggcmdiYSgzNywgOTksIDIzNSwgMC4xMik7IH0KLnN0YXQtY2FyZC5vcmFuZ2UgeyBiYWNrZ3JvdW5kOiBsaW5lYXItZ3JhZGllbnQoMTM1ZGVnLCAjRjk3MzE2LCAjRUE1ODBDKTsgYm94LXNoYWRvdzogMCAxMHB4IDIwcHggcmdiYSgyNDksIDExNSwgMjIsIDAuMTIpOyB9Ci5zdGF0LWNhcmQudGVhbCB7IGJhY2tncm91bmQ6IGxpbmVhci1ncmFkaWVudCgxMzVkZWcsICMxMEI5ODEsICMwNTk2NjkpOyBib3gtc2hhZG93OiAwIDEwcHggMjBweCByZ2JhKDE2LCAxODUsIDEyOSwgMC4xMik7IH0KLnN0YXQtY2FyZC5wdXJwbGUgeyBiYWNrZ3JvdW5kOiBsaW5lYXItZ3JhZGllbnQoMTM1ZGVnLCAjOEI1Q0Y2LCAjNkQyOEQ5KTsgYm94LXNoYWRvdzogMCAxMHB4IDIwcHggcmdiYSgxMzksIDkyLCAyNDYsIDAuMTIpOyB9Ci5zdGF0LWNhcmQgLmxhYmVsIHsgZm9udC1zaXplOiAwLjg2cmVtOyBvcGFjaXR5OiAwLjk7IH0KLnN0YXQtY2FyZCAuYW1vdW50IHsgZm9udC1zaXplOiAxLjc1cmVtOyBmb250LXdlaWdodDogNzAwOyBtYXJnaW4tdG9wOiA2cHg7IH0KLnN0YXQtY2FyZCAuY2hhbmdlIHsgZm9udC1zaXplOiAwLjg0cmVtOyBkaXNwbGF5OiBmbGV4OyBhbGlnbi1pdGVtczogY2VudGVyOyBnYXA6IDZweDsgbWFyZ2luLXRvcDogMTJweDsgb3BhY2l0eTogMC45NTsgfQouc3RhdC1pY29uIHsgd2lkdGg6IDQ0cHg7IGhlaWdodDogNDRweDsgYm9yZGVyLXJhZGl1czogNTAlOyBiYWNrZ3JvdW5kOiByZ2JhKDI1NSwyNTUsMjU1LDAuMjUpOyBkaXNwbGF5OiBncmlkOyBwbGFjZS1pdGVtczogY2VudGVyOyBmb250LXNpemU6IDEuMnJlbTsgfQoKLyogU3RhdCBjYXJkIGVudHJhbmNlIGFuaW1hdGlvbiAqLwpAa2V5ZnJhbWVzIGNhcmRFbnRlciB7CiAgZnJvbSB7IG9wYWNpdHk6IDA7IHRyYW5zZm9ybTogdHJhbnNsYXRlWSgyMnB4KSBzY2FsZSgwLjk3KTsgfQogIHRvICAgeyBvcGFjaXR5OiAxOyB0cmFuc2Zvcm06IHRyYW5zbGF0ZVkoMCkgc2NhbGUoMSk7IH0KfQouc3RhdC1jYXJkLmNhcmQtZW50ZXIgeyBhbmltYXRpb246IGNhcmRFbnRlciAwLjQ1cyBjdWJpYy1iZXppZXIoMC4yMiwxLDAuMzYsMSkgYm90aDsgfQoKLyogUmVmcmVzaCBmbGFzaCBmZWVkYmFjayAqLwpAa2V5ZnJhbWVzIHJlZnJlc2hGbGFzaCB7CiAgMCUgICB7IGJveC1zaGFkb3c6IDAgMCAwIDAgcmdiYSgyNTUsMjU1LDI1NSwwLjApOyB9CiAgNDAlICB7IGJveC1zaGFkb3c6IDAgMCAwIDZweCByZ2JhKDI1NSwyNTUsMjU1LDAuMjUpOyB9CiAgMTAwJSB7IGJveC1zaGFkb3c6IDAgMCAwIDAgcmdiYSgyNTUsMjU1LDI1NSwwLjApOyB9Cn0KLnN0YXQtY2FyZC5yZWZyZXNoLWZsYXNoIHsgYW5pbWF0aW9uOiByZWZyZXNoRmxhc2ggMC44cyBlYXNlOyB9CgovKiBQYW5lbCBlbnRyYW5jZSBhbmltYXRpb24gKi8KQGtleWZyYW1lcyBwYW5lbEVudGVyIHsKICBmcm9tIHsgb3BhY2l0eTogMDsgdHJhbnNmb3JtOiB0cmFuc2xhdGVZKDE2cHgpOyB9CiAgdG8gICB7IG9wYWNpdHk6IDE7IHRyYW5zZm9ybTogdHJhbnNsYXRlWSgwKTsgfQp9Ci5wYW5lbCB7IGFuaW1hdGlvbjogcGFuZWxFbnRlciAwLjRzIGVhc2UgYm90aDsgfQoKCi5kYXNoYm9hcmQtZ3JpZCB7IGRpc3BsYXk6IGdyaWQ7IGdyaWQtdGVtcGxhdGUtY29sdW1uczogMWZyOyBnYXA6IDIwcHg7IH0KLnBhbmVsIHsgYmFja2dyb3VuZDogdmFyKC0td2hpdGUpOyBib3JkZXItcmFkaXVzOiB2YXIoLS1ib3JkZXItcmFkaXVzLWNhcmQpOyBwYWRkaW5nOiAyNHB4OyBib3gtc2hhZG93OiB2YXIoLS1zaGFkb3cpOyB9CgouYW5hbHl0aWNzLWJvZHkgeyBkaXNwbGF5OiBmbGV4OyBmbGV4LWRpcmVjdGlvbjogY29sdW1uOyBnYXA6IDMwcHg7IGFsaWduLWl0ZW1zOiBjZW50ZXI7IHBhZGRpbmc6IDE1cHggMDsgfQouY2hhcnQtd3JhcHBlciB7IHBvc2l0aW9uOiByZWxhdGl2ZTsgZGlzcGxheTogZmxleDsganVzdGlmeS1jb250ZW50OiBjZW50ZXI7IGFsaWduLWl0ZW1zOiBjZW50ZXI7IHdpZHRoOiAxMDAlOyB9Ci5jaGFydC13cmFwcGVyIGNhbnZhcyB7IG1heC13aWR0aDogMjUwcHggIWltcG9ydGFudDsgbWF4LWhlaWdodDogMjUwcHggIWltcG9ydGFudDsgfQoubGVnZW5kLWxpc3QgeyBkaXNwbGF5OiBncmlkOyBncmlkLXRlbXBsYXRlLWNvbHVtbnM6IHJlcGVhdChhdXRvLWZpdCwgbWlubWF4KDkwcHgsIDFmcikpOyBnYXA6IDEwcHg7IHdpZHRoOiAxMDAlOyB9Ci5sZWdlbmQtcm93IHsgZGlzcGxheTogZmxleDsgZmxleC1kaXJlY3Rpb246IGNvbHVtbjsgYWxpZ24taXRlbXM6IGNlbnRlcjsganVzdGlmeS1jb250ZW50OiBjZW50ZXI7IGdhcDogNnB4OyBwYWRkaW5nOiAxMHB4IDhweDsgYmFja2dyb3VuZDogI0Y4RkFGQzsgYm9yZGVyLXJhZGl1czogMTJweDsgYm9yZGVyOiAxLjVweCBzb2xpZCAjRjFGNUY5OyBib3gtc2hhZG93OiAwIDFweCAzcHggcmdiYSgwLDAsMCwwLjAyKTsgdHJhbnNpdGlvbjogdHJhbnNmb3JtIDAuMnMsIGJveC1zaGFkb3cgMC4yczsgfQoubGVnZW5kLXJvdzpob3ZlciB7IHRyYW5zZm9ybTogdHJhbnNsYXRlWSgtMnB4KTsgYm94LXNoYWRvdzogMCA0cHggMTJweCByZ2JhKDAsMCwwLDAuMDUpOyB9Ci5sZWdlbmQtbGFiZWwgeyBkaXNwbGF5OiBmbGV4OyBhbGlnbi1pdGVtczogY2VudGVyOyBnYXA6IDdweDsgZm9udC1zaXplOiAwLjk1cmVtOyBmb250LXdlaWdodDogNzAwOyB9Ci5sZWdlbmQtbGFiZWwgaSB7IGZvbnQtc2l6ZTogMS4ycmVtOyB9Ci5sZWdlbmQtbWV0YSB7IHRleHQtYWxpZ246IGNlbnRlcjsgfQoubGVnZW5kLW1ldGEgc3Ryb25nIHsgZGlzcGxheTogYmxvY2s7IGZvbnQtc2l6ZTogMS4xNXJlbTsgY29sb3I6ICMwRjE3MkE7IGZvbnQtd2VpZ2h0OiA4MDA7IG1hcmdpbi1ib3R0b206IDJweDsgfQoubGVnZW5kLW1ldGEgc3BhbiB7IGRpc3BsYXk6IGJsb2NrOyBjb2xvcjogdmFyKC0tdGV4dC1tdXRlZCk7IGZvbnQtc2l6ZTogMC44cmVtOyBmb250LXdlaWdodDogNTAwOyB9CgouZm9vdGVyLXN0cmlwIHsgZGlzcGxheTogZmxleDsganVzdGlmeS1jb250ZW50OiBzcGFjZS1iZXR3ZWVuOyBhbGlnbi1pdGVtczogY2VudGVyOyBtYXJnaW4tdG9wOiAxOHB4OyBwYWRkaW5nLXRvcDogMTZweDsgYm9yZGVyLXRvcDogMXB4IHNvbGlkICNFMkU4RjA7IGNvbG9yOiB2YXIoLS10ZXh0LW11dGVkKTsgZm9udC1zaXplOiAwLjlyZW07IH0KLmZvb3Rlci1zdHJpcCAubGluay1ibHVlIHsgY29sb3I6IHZhcigtLXByaW1hcnktYmx1ZSk7IGZvbnQtd2VpZ2h0OiA2MDA7IH0KLnN1bW1hcnktcGlsbCB7IGRpc3BsYXk6IGlubGluZS1mbGV4OyBhbGlnbi1pdGVtczogY2VudGVyOyBnYXA6IDhweDsgcGFkZGluZzogOHB4IDEycHg7IGJhY2tncm91bmQ6ICNGOEZBRkM7IGJvcmRlci1yYWRpdXM6IDk5OXB4OyB9CgoudGhyZWUtY29sIHsgZGlzcGxheTogZ3JpZDsgZ3JpZC10ZW1wbGF0ZS1jb2x1bW5zOiByZXBlYXQoMywgbWlubWF4KDAsIDFmcikpOyBnYXA6IDIwcHg7IH0KLmNoYXJ0LWNhcmQgeyBwb3NpdGlvbjogcmVsYXRpdmU7IH0KLmxpbmUtY2hhcnQtYm94IHsgaGVpZ2h0OiAyNjBweDsgcG9zaXRpb246IHJlbGF0aXZlOyB3aWR0aDogMTAwJTsgcGFkZGluZy10b3A6IDEwcHg7IH0KLmxpbmUtY2hhcnQtYm94IGNhbnZhcyB7IHdpZHRoOiAxMDAlICFpbXBvcnRhbnQ7IGhlaWdodDogMTAwJSAhaW1wb3J0YW50OyBkaXNwbGF5OiBibG9jazsgfQoubGluZS1jaGFydC10b29sdGlwIHsgcG9zaXRpb246IGFic29sdXRlOyB0b3A6IDE4cHg7IHJpZ2h0OiA4cHg7IGJhY2tncm91bmQ6IHJnYmEoMjU1LDI1NSwyNTUsMC45Nik7IGJvcmRlci1yYWRpdXM6IDEycHg7IHBhZGRpbmc6IDhweCAxMHB4OyBib3gtc2hhZG93OiB2YXIoLS1zaGFkb3cpOyBmb250LXNpemU6IDAuNzhyZW07IGNvbG9yOiB2YXIoLS10ZXh0LWRhcmspOyBib3JkZXI6IDFweCBzb2xpZCAjRTJFOEYwOyB9CgoudHJhbnNhY3Rpb24tbGlzdCB7IGRpc3BsYXk6IGZsZXg7IGZsZXgtZGlyZWN0aW9uOiBjb2x1bW47IGdhcDogMTJweDsgfQoudHJhbnNhY3Rpb24tcm93IHsgZGlzcGxheTogZmxleDsgYWxpZ24taXRlbXM6IGNlbnRlcjsganVzdGlmeS1jb250ZW50OiBzcGFjZS1iZXR3ZWVuOyBnYXA6IDEycHg7IHBhZGRpbmc6IDEwcHggMDsgYm9yZGVyLWJvdHRvbTogMXB4IHNvbGlkICNGMUY1Rjk7IH0KLnRyYW5zYWN0aW9uLXJvdzpsYXN0LWNoaWxkIHsgYm9yZGVyLWJvdHRvbTogMDsgfQoudHJhbnNhY3Rpb24tbGVmdCB7IGRpc3BsYXk6IGZsZXg7IGFsaWduLWl0ZW1zOiBjZW50ZXI7IGdhcDogMTBweDsgfQoudHJhbnNhY3Rpb24taWNvbiB7IHdpZHRoOiA0MHB4OyBoZWlnaHQ6IDQwcHg7IGJvcmRlci1yYWRpdXM6IDUwJTsgZGlzcGxheTogZ3JpZDsgcGxhY2UtaXRlbXM6IGNlbnRlcjsgZm9udC1zaXplOiAxcmVtOyB9Ci50cmFuc2FjdGlvbi1pY29uLmdyZWVuIHsgYmFja2dyb3VuZDogcmdiYSgxNiwgMTg1LCAxMjksIDAuMTQpOyBjb2xvcjogdmFyKC0tc3VjY2Vzcyk7IH0KLnRyYW5zYWN0aW9uLWljb24ub3JhbmdlIHsgYmFja2dyb3VuZDogcmdiYSgyNDksIDExNSwgMjIsIDAuMTYpOyBjb2xvcjogdmFyKC0tb3JhbmdlKTsgfQoudHJhbnNhY3Rpb24taWNvbi5wdXJwbGUgeyBiYWNrZ3JvdW5kOiByZ2JhKDEzOSwgOTIsIDI0NiwgMC4xNik7IGNvbG9yOiB2YXIoLS1wdXJwbGUpOyB9Ci50cmFuc2FjdGlvbi1pY29uLmJsdWUgeyBiYWNrZ3JvdW5kOiByZ2JhKDM3LCA5OSwgMjM1LCAwLjE0KTsgY29sb3I6IHZhcigtLXByaW1hcnktYmx1ZSk7IH0KLnRyYW5zYWN0aW9uLXRpdGxlIHsgZm9udC13ZWlnaHQ6IDYwMDsgZm9udC1zaXplOiAwLjkycmVtOyB9Ci50cmFuc2FjdGlvbi1zdWJ0aXRsZSB7IGNvbG9yOiB2YXIoLS10ZXh0LW11dGVkKTsgZm9udC1zaXplOiAwLjc3cmVtOyB9Ci50cmFuc2FjdGlvbi1yaWdodCB7IHRleHQtYWxpZ246IHJpZ2h0OyB9Ci50cmFuc2FjdGlvbi1yaWdodCAuYW1vdW50IHsgZm9udC13ZWlnaHQ6IDcwMDsgZm9udC1zaXplOiAwLjk1cmVtOyB9Ci50cmFuc2FjdGlvbi1yaWdodCAuYW1vdW50LnBvc2l0aXZlIHsgY29sb3I6IHZhcigtLXN1Y2Nlc3MpOyB9Ci50cmFuc2FjdGlvbi1yaWdodCAuYW1vdW50Lm5lZ2F0aXZlIHsgY29sb3I6IHZhcigtLWRhbmdlcik7IH0KLnRyYW5zYWN0aW9uLXJpZ2h0IC5kYXRlIHsgY29sb3I6IHZhcigtLXRleHQtbXV0ZWQpOyBmb250LXNpemU6IDAuNzZyZW07IH0KCi5pbnNpZ2h0LWxpc3QgeyBkaXNwbGF5OiBmbGV4OyBmbGV4LWRpcmVjdGlvbjogY29sdW1uOyBnYXA6IDE0cHg7IH0KLmluc2lnaHQtaXRlbSB7IGJvcmRlcjogMXB4IHNvbGlkICNGMUY1Rjk7IGJvcmRlci1yYWRpdXM6IDE0cHg7IHBhZGRpbmc6IDE0cHggMTRweCAxMnB4OyB9Ci5pbnNpZ2h0LXJvdyB7IGRpc3BsYXk6IGZsZXg7IGFsaWduLWl0ZW1zOiBjZW50ZXI7IGp1c3RpZnktY29udGVudDogc3BhY2UtYmV0d2VlbjsgZ2FwOiAxMHB4OyB9Ci5pbnNpZ2h0LWxlZnQgeyBkaXNwbGF5OiBmbGV4OyBhbGlnbi1pdGVtczogY2VudGVyOyBnYXA6IDEwcHg7IH0KLmluc2lnaHQtaWNvbiB7IHdpZHRoOiAzOHB4OyBoZWlnaHQ6IDM4cHg7IGJvcmRlci1yYWRpdXM6IDUwJTsgZGlzcGxheTogZ3JpZDsgcGxhY2UtaXRlbXM6IGNlbnRlcjsgZm9udC1zaXplOiAwLjk1cmVtOyB9Ci5pbnNpZ2h0LXRpdGxlIHsgZm9udC1zaXplOiAwLjkycmVtOyBmb250LXdlaWdodDogNzAwOyB9Ci5pbnNpZ2h0LWRlc2MgeyBjb2xvcjogdmFyKC0tdGV4dC1tdXRlZCk7IGZvbnQtc2l6ZTogMC43NnJlbTsgbWFyZ2luLXRvcDogMnB4OyB9Ci5pbnNpZ2h0LWJhZGdlIHsgYm9yZGVyLXJhZGl1czogOTk5cHg7IHBhZGRpbmc6IDVweCA4cHg7IGZvbnQtc2l6ZTogMC43NHJlbTsgZm9udC13ZWlnaHQ6IDYwMDsgfQouYmFkZ2Utb24tdHJhY2sgeyBiYWNrZ3JvdW5kOiByZ2JhKDIyLCAxNjMsIDc0LCAwLjEyKTsgY29sb3I6IHZhcigtLXN1Y2Nlc3MpOyB9Ci5iYWRnZS1wb3NpdGl2ZSB7IGJhY2tncm91bmQ6IHJnYmEoMTYsIDE4NSwgMTI5LCAwLjEyKTsgY29sb3I6IHZhcigtLXN1Y2Nlc3MpOyB9Ci5iYWRnZS1wdXJwbGUgeyBiYWNrZ3JvdW5kOiByZ2JhKDEzOSwgOTIsIDI0NiwgMC4xNCk7IGNvbG9yOiB2YXIoLS1wdXJwbGUpOyB9CgoucHJvZ3Jlc3MtYmFyIHsgaGVpZ2h0OiA4cHg7IGJvcmRlci1yYWRpdXM6IDk5OXB4OyBiYWNrZ3JvdW5kOiAjRTJFOEYwOyBtYXJnaW4tdG9wOiAxMHB4OyBvdmVyZmxvdzogaGlkZGVuOyB9Ci5wcm9ncmVzcy1iYXIgPiBzcGFuIHsgZGlzcGxheTogYmxvY2s7IGhlaWdodDogMTAwJTsgYm9yZGVyLXJhZGl1czogaW5oZXJpdDsgfQoKLyog4pSA4pSAIEFuYWx5dGljcyBSaWJib24g4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSAICovCi5hbmFseXRpY3MtcmliYm9uIHsKICBkaXNwbGF5OiBmbGV4OwogIGFsaWduLWl0ZW1zOiBjZW50ZXI7CiAganVzdGlmeS1jb250ZW50OiBzcGFjZS1iZXR3ZWVuOwogIGdhcDogMTZweDsKICBiYWNrZ3JvdW5kOiBsaW5lYXItZ3JhZGllbnQoMTM1ZGVnLCAjMEIxMjIwIDAlLCAjMTcyMjNBIDYwJSwgIzFFMkQ0QSAxMDAlKTsKICBib3JkZXItcmFkaXVzOiAxNnB4OwogIHBhZGRpbmc6IDE0cHggMjBweDsKICBib3gtc2hhZG93OiAwIDRweCAyMHB4IHJnYmEoMTEsIDE4LCAzMiwgMC4yMiksIDAgMXB4IDRweCByZ2JhKDM3LDk5LDIzNSwwLjA4KTsKICBwb3NpdGlvbjogcmVsYXRpdmU7CiAgb3ZlcmZsb3c6IGhpZGRlbjsKfQouYW5hbHl0aWNzLXJpYmJvbjo6YmVmb3JlIHsKICBjb250ZW50OiAnJzsKICBwb3NpdGlvbjogYWJzb2x1dGU7CiAgaW5zZXQ6IDA7CiAgYmFja2dyb3VuZDogbGluZWFyLWdyYWRpZW50KDkwZGVnLCByZ2JhKDM3LDk5LDIzNSwwLjE4KSAwJSwgdHJhbnNwYXJlbnQgNTUlKTsKICBwb2ludGVyLWV2ZW50czogbm9uZTsKfQouYW5hbHl0aWNzLXJpYmJvbjo6YWZ0ZXIgewogIGNvbnRlbnQ6ICcnOwogIHBvc2l0aW9uOiBhYnNvbHV0ZTsKICByaWdodDogLTMwcHg7IHRvcDogLTMwcHg7CiAgd2lkdGg6IDE2MHB4OyBoZWlnaHQ6IDE2MHB4OwogIGJvcmRlci1yYWRpdXM6IDUwJTsKICBiYWNrZ3JvdW5kOiByYWRpYWwtZ3JhZGllbnQoY2lyY2xlLCByZ2JhKDEzOSw5MiwyNDYsMC4xOCkgMCUsIHRyYW5zcGFyZW50IDcwJSk7CiAgcG9pbnRlci1ldmVudHM6IG5vbmU7Cn0KCi5yaWJib24tbGVmdCB7IGZsZXg6IDE7IG1pbi13aWR0aDogMDsgcG9zaXRpb246IHJlbGF0aXZlOyB6LWluZGV4OiAxOyB9Ci5yaWJib24tc2VhcmNoLXdyYXAgewogIGRpc3BsYXk6IGZsZXg7IGFsaWduLWl0ZW1zOiBjZW50ZXI7IGdhcDogMTBweDsKICBiYWNrZ3JvdW5kOiByZ2JhKDI1NSwyNTUsMjU1LDAuMDcpOwogIGJvcmRlcjogMXB4IHNvbGlkIHJnYmEoMjU1LDI1NSwyNTUsMC4xMik7CiAgYm9yZGVyLXJhZGl1czogOTk5cHg7CiAgcGFkZGluZzogMCAxOHB4OyBoZWlnaHQ6IDQycHg7CiAgbWF4LXdpZHRoOiA1MjBweDsKICB0cmFuc2l0aW9uOiBib3JkZXItY29sb3IgMC4ycywgYmFja2dyb3VuZCAwLjJzOwogIGJhY2tkcm9wLWZpbHRlcjogYmx1cig0cHgpOwp9Ci5yaWJib24tc2VhcmNoLXdyYXA6Zm9jdXMtd2l0aGluIHsKICBiYWNrZ3JvdW5kOiByZ2JhKDI1NSwyNTUsMjU1LDAuMTEpOwogIGJvcmRlci1jb2xvcjogcmdiYSg1OSwgMTMwLCAyNDYsIDAuNTUpOwogIGJveC1zaGFkb3c6IDAgMCAwIDNweCByZ2JhKDU5LCAxMzAsIDI0NiwgMC4xNSk7Cn0KLnJpYmJvbi1zZWFyY2gtd3JhcCBpIHsgY29sb3I6IHJnYmEoMjU1LDI1NSwyNTUsMC40NSk7IGZvbnQtc2l6ZTogMC45MnJlbTsgZmxleC1zaHJpbms6IDA7IH0KLnJpYmJvbi1zZWFyY2gtd3JhcCBpbnB1dCB7CiAgYm9yZGVyOiAwOyBvdXRsaW5lOiAwOyBiYWNrZ3JvdW5kOiB0cmFuc3BhcmVudDsKICB3aWR0aDogMTAwJTsgZm9udC1zaXplOiAwLjlyZW07CiAgY29sb3I6ICNmZmY7IGZvbnQtZmFtaWx5OiBpbmhlcml0Owp9Ci5yaWJib24tc2VhcmNoLXdyYXAgaW5wdXQ6OnBsYWNlaG9sZGVyIHsgY29sb3I6IHJnYmEoMjU1LDI1NSwyNTUsMC4zOCk7IH0KLnJpYmJvbi1zaG9ydGN1dCB7CiAgZmxleC1zaHJpbms6IDA7CiAgYmFja2dyb3VuZDogcmdiYSgyNTUsMjU1LDI1NSwwLjEpOwogIGJvcmRlcjogMXB4IHNvbGlkIHJnYmEoMjU1LDI1NSwyNTUsMC4xNSk7CiAgYm9yZGVyLXJhZGl1czogNnB4OyBwYWRkaW5nOiAycHggOHB4OwogIGZvbnQtc2l6ZTogMC43MnJlbTsgY29sb3I6IHJnYmEoMjU1LDI1NSwyNTUsMC41KTsKICBmb250LWZhbWlseTogJ0ludGVyJywgbW9ub3NwYWNlOyBsZXR0ZXItc3BhY2luZzogMC4wNGVtOwp9CgoucmliYm9uLXJpZ2h0IHsKICBkaXNwbGF5OiBmbGV4OyBhbGlnbi1pdGVtczogY2VudGVyOyBnYXA6IDE0cHg7CiAgZmxleC1zaHJpbms6IDA7IHBvc2l0aW9uOiByZWxhdGl2ZTsgei1pbmRleDogMTsKfQoucmliYm9uLWJhZGdlIHsKICB3aWR0aDogMzZweDsgaGVpZ2h0OiAzNnB4OyBib3JkZXItcmFkaXVzOiA1MCU7CiAgYmFja2dyb3VuZDogcmdiYSgyNTUsMjU1LDI1NSwwLjA4KTsKICBkaXNwbGF5OiBncmlkOyBwbGFjZS1pdGVtczogY2VudGVyOwogIGNvbG9yOiByZ2JhKDI1NSwyNTUsMjU1LDAuNik7IGZvbnQtc2l6ZTogMXJlbTsKICBwb3NpdGlvbjogcmVsYXRpdmU7IGN1cnNvcjogcG9pbnRlcjsKICB0cmFuc2l0aW9uOiBiYWNrZ3JvdW5kIDAuMnM7Cn0KLnJpYmJvbi1iYWRnZTpob3ZlciB7IGJhY2tncm91bmQ6IHJnYmEoMjU1LDI1NSwyNTUsMC4xNCk7IH0KLnJpYmJvbi1kb3QgewogIHBvc2l0aW9uOiBhYnNvbHV0ZTsgdG9wOiA3cHg7IHJpZ2h0OiA3cHg7CiAgd2lkdGg6IDhweDsgaGVpZ2h0OiA4cHg7IGJvcmRlci1yYWRpdXM6IDUwJTsKICBiYWNrZ3JvdW5kOiAjRUY0NDQ0OyBib3JkZXI6IDJweCBzb2xpZCAjMTcyMjNBOwp9Ci5yaWJib24tZGl2aWRlciB7IHdpZHRoOiAxcHg7IGhlaWdodDogMjhweDsgYmFja2dyb3VuZDogcmdiYSgyNTUsMjU1LDI1NSwwLjEyKTsgfQoucmliYm9uLXVzZXIgewogIGRpc3BsYXk6IGZsZXg7IGFsaWduLWl0ZW1zOiBjZW50ZXI7IGdhcDogMTBweDsKICBjdXJzb3I6IHBvaW50ZXI7IHBhZGRpbmc6IDRweCAxMHB4OyBib3JkZXItcmFkaXVzOiA5OTlweDsKICB0cmFuc2l0aW9uOiBiYWNrZ3JvdW5kIDAuMnM7Cn0KLnJpYmJvbi11c2VyOmhvdmVyIHsgYmFja2dyb3VuZDogcmdiYSgyNTUsMjU1LDI1NSwwLjA3KTsgfQoucmliYm9uLWF2YXRhciB7CiAgd2lkdGg6IDM2cHg7IGhlaWdodDogMzZweDsgYm9yZGVyLXJhZGl1czogNTAlOwogIGJhY2tncm91bmQ6IGxpbmVhci1ncmFkaWVudCgxMzVkZWcsICMyNTYzRUIsICM4QjVDRjYpOwogIGNvbG9yOiAjZmZmOyBkaXNwbGF5OiBncmlkOyBwbGFjZS1pdGVtczogY2VudGVyOwogIGZvbnQtd2VpZ2h0OiA3MDA7IGZvbnQtc2l6ZTogMC45cmVtOwogIGJveC1zaGFkb3c6IDAgMCAwIDJweCByZ2JhKDI1NSwyNTUsMjU1LDAuMTUpOwp9Ci5yaWJib24tdXNlci1pbmZvIHsgZGlzcGxheTogZmxleDsgZmxleC1kaXJlY3Rpb246IGNvbHVtbjsgbGluZS1oZWlnaHQ6IDEuMjsgfQoucmliYm9uLXVzZXItaW5mbyBzdHJvbmcgeyBmb250LXNpemU6IDAuODhyZW07IGNvbG9yOiAjZmZmOyBmb250LXdlaWdodDogNjAwOyB9Ci5yaWJib24tdXNlci1pbmZvIHNwYW4geyBmb250LXNpemU6IDAuNzJyZW07IGNvbG9yOiByZ2JhKDI1NSwyNTUsMjU1LDAuNDUpOyB9Ci5yaWJib24tc3RhdHVzLXBpbGwgewogIGRpc3BsYXk6IGZsZXg7IGFsaWduLWl0ZW1zOiBjZW50ZXI7IGdhcDogNnB4OwogIHBhZGRpbmc6IDVweCAxMnB4OyBib3JkZXItcmFkaXVzOiA5OTlweDsKICBiYWNrZ3JvdW5kOiByZ2JhKDE2LDE4NSwxMjksMC4xNSk7CiAgYm9yZGVyOiAxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LDAuMyk7CiAgY29sb3I6ICMzNEQzOTk7IGZvbnQtc2l6ZTogMC43OHJlbTsgZm9udC13ZWlnaHQ6IDYwMDsKfQoucmliYm9uLXN0YXR1cy1kb3QgewogIHdpZHRoOiA3cHg7IGhlaWdodDogN3B4OyBib3JkZXItcmFkaXVzOiA1MCU7CiAgYmFja2dyb3VuZDogIzEwQjk4MTsKICBhbmltYXRpb246IHB1bHNlLWRvdCAycyBlYXNlLWluLW91dCBpbmZpbml0ZTsKfQpAa2V5ZnJhbWVzIHB1bHNlLWRvdCB7CiAgMCUsIDEwMCUgeyBvcGFjaXR5OiAxOyB0cmFuc2Zvcm06IHNjYWxlKDEpOyB9CiAgNTAlIHsgb3BhY2l0eTogMC42OyB0cmFuc2Zvcm06IHNjYWxlKDAuOCk7IH0KfQoKLyog4pSA4pSAIFF1aWNrIEFjdGlvbnMg4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSAICovCi5xdWljay1hY3Rpb25zLXJvdyB7IG1hcmdpbi10b3A6IDIwcHg7IH0KCi5xdWljay1hY3Rpb25zLWdyaWQgeyBkaXNwbGF5OiBncmlkOyBncmlkLXRlbXBsYXRlLWNvbHVtbnM6IHJlcGVhdCg0LCBtaW5tYXgoMCwgMWZyKSk7IGdhcDogMjBweDsgbWFyZ2luLXRvcDogMTJweDsgfQoucXVpY2stYWN0aW9uLWNhcmQgeyBwYWRkaW5nOiAyMHB4OyBib3JkZXItcmFkaXVzOiAxNnB4OyBkaXNwbGF5OiBmbGV4OyBqdXN0aWZ5LWNvbnRlbnQ6IHNwYWNlLWJldHdlZW47IGFsaWduLWl0ZW1zOiBjZW50ZXI7IGdhcDogMTJweDsgbWluLWhlaWdodDogMTA0cHg7IGJveC1zaGFkb3c6IHZhcigtLXNoYWRvdyk7IH0KLnF1aWNrLWFjdGlvbi1jYXJkLmJsdWUgeyBiYWNrZ3JvdW5kOiByZ2JhKDM3LCA5OSwgMjM1LCAwLjA4KTsgfQoucXVpY2stYWN0aW9uLWNhcmQub3JhbmdlIHsgYmFja2dyb3VuZDogcmdiYSgyNDksIDExNSwgMjIsIDAuMDkpOyB9Ci5xdWljay1hY3Rpb24tY2FyZC5ncmVlbiB7IGJhY2tncm91bmQ6IHJnYmEoMTYsIDE4NSwgMTI5LCAwLjEpOyB9Ci5xdWljay1hY3Rpb24tY2FyZC5wdXJwbGUgeyBiYWNrZ3JvdW5kOiByZ2JhKDEzOSwgOTIsIDI0NiwgMC4xKTsgfQoucXVpY2stYWN0aW9uLWljb24geyB3aWR0aDogNDRweDsgaGVpZ2h0OiA0NHB4OyBib3JkZXItcmFkaXVzOiA1MCU7IGRpc3BsYXk6IGdyaWQ7IHBsYWNlLWl0ZW1zOiBjZW50ZXI7IGZvbnQtc2l6ZTogMS4wNXJlbTsgfQoucXVpY2stYWN0aW9uLWNhcmQuYmx1ZSAucXVpY2stYWN0aW9uLWljb24geyBiYWNrZ3JvdW5kOiByZ2JhKDM3LCA5OSwgMjM1LCAwLjE2KTsgY29sb3I6IHZhcigtLXByaW1hcnktYmx1ZSk7IH0KLnF1aWNrLWFjdGlvbi1jYXJkLm9yYW5nZSAucXVpY2stYWN0aW9uLWljb24geyBiYWNrZ3JvdW5kOiByZ2JhKDI0OSwgMTE1LCAyMiwgMC4xNik7IGNvbG9yOiB2YXIoLS1vcmFuZ2UpOyB9Ci5xdWljay1hY3Rpb24tY2FyZC5ncmVlbiAucXVpY2stYWN0aW9uLWljb24geyBiYWNrZ3JvdW5kOiByZ2JhKDE2LCAxODUsIDEyOSwgMC4xNik7IGNvbG9yOiB2YXIoLS10ZWFsKTsgfQoucXVpY2stYWN0aW9uLWNhcmQucHVycGxlIC5xdWljay1hY3Rpb24taWNvbiB7IGJhY2tncm91bmQ6IHJnYmEoMTM5LCA5MiwgMjQ2LCAwLjE2KTsgY29sb3I6IHZhcigtLXB1cnBsZSk7IH0KLnF1aWNrLWFjdGlvbi10aXRsZSB7IGZvbnQtd2VpZ2h0OiA3MDA7IGZvbnQtc2l6ZTogMC45NXJlbTsgfQoucXVpY2stYWN0aW9uLXN1YnRpdGxlIHsgY29sb3I6IHZhcigtLXRleHQtbXV0ZWQpOyBmb250LXNpemU6IDAuNzhyZW07IG1hcmdpbi10b3A6IDJweDsgfQoucXVpY2stYWN0aW9uLWFycm93IHsgY29sb3I6IHZhcigtLXRleHQtbXV0ZWQpOyB9CgpAbWVkaWEgKG1heC13aWR0aDogMTIwMHB4KSB7CiAgLmRhc2hib2FyZC1ncmlkIHsgZ3JpZC10ZW1wbGF0ZS1jb2x1bW5zOiAxZnI7IH0KICAudGhyZWUtY29sIHsgZ3JpZC10ZW1wbGF0ZS1jb2x1bW5zOiAxZnI7IH0KfQpAbWVkaWEgKG1heC13aWR0aDogOTkycHgpIHsKICAuc2lkZWJhciB7IHBvc2l0aW9uOiBmaXhlZDsgbGVmdDogLTI2MHB4OyB6LWluZGV4OiAxMDA7IHRyYW5zaXRpb246IGxlZnQgMC4ycyBlYXNlOyB9CiAgLnNpZGViYXIub3BlbiB7IGxlZnQ6IDA7IH0KICAubWFpbi1wYW5lbCB7IHBhZGRpbmc6IDE2cHg7IH0KICAuc3RhdC1yb3cgeyBncmlkLXRlbXBsYXRlLWNvbHVtbnM6IHJlcGVhdCgyLCBtaW5tYXgoMCwgMWZyKSk7IH0KICAucXVpY2stYWN0aW9ucy1ncmlkIHsgZ3JpZC10ZW1wbGF0ZS1jb2x1bW5zOiByZXBlYXQoMiwgbWlubWF4KDAsIDFmcikpOyB9Cn0KQG1lZGlhIChtYXgtd2lkdGg6IDc2OHB4KSB7CiAgLnRvcGJhciB7IGZsZXgtd3JhcDogd3JhcDsgaGVpZ2h0OiBhdXRvOyBwYWRkaW5nOiAxNHB4IDE2cHg7IGdhcDogMTJweDsgfQogIC50b3BiYXItbGVmdCB7IHdpZHRoOiAxMDAlOyB9CiAgLnRvcGJhci1yaWdodCB7IHdpZHRoOiAxMDAlOyBqdXN0aWZ5LWNvbnRlbnQ6IHNwYWNlLWJldHdlZW47IGZsZXgtd3JhcDogd3JhcDsgfQogIC5zdGF0LXJvdyB7IGdyaWQtdGVtcGxhdGUtY29sdW1uczogMWZyOyB9CiAgLnF1aWNrLWFjdGlvbnMtZ3JpZCB7IGdyaWQtdGVtcGxhdGUtY29sdW1uczogMWZyOyB9CiAgLmFuYWx5dGljcy1ib2R5LCAuaW5mby1ncmlkIHsgZ3JpZC10ZW1wbGF0ZS1jb2x1bW5zOiAxZnI7IH0KICAuZm9vdGVyLXN0cmlwIHsgZmxleC1kaXJlY3Rpb246IGNvbHVtbjsgYWxpZ24taXRlbXM6IGZsZXgtc3RhcnQ7IGdhcDogOHB4OyB9CiAgLmFuYWx5dGljcy1yaWJib24geyBmbGV4LWRpcmVjdGlvbjogY29sdW1uOyBhbGlnbi1pdGVtczogc3RyZXRjaDsgZ2FwOiAxMnB4OyBwYWRkaW5nOiAxNHB4IDE2cHg7IH0KICAucmliYm9uLXJpZ2h0IHsganVzdGlmeS1jb250ZW50OiBzcGFjZS1iZXR3ZWVuOyB9CiAgLnJpYmJvbi1zZWFyY2gtd3JhcCB7IG1heC13aWR0aDogMTAwJTsgfQp9CgovKiBQcm9maWxlIENoaXAgKi8KLnByb2ZpbGUtY2hpcC1nbG9iYWwgewogIHBvc2l0aW9uOiBmaXhlZDsKICB0b3A6IDE4cHg7CiAgcmlnaHQ6IDIycHg7CiAgei1pbmRleDogMTUwMDsKICBkaXNwbGF5OiBmbGV4OwogIGFsaWduLWl0ZW1zOiBjZW50ZXI7CiAgZ2FwOiAxMHB4OwogIGJhY2tncm91bmQ6IHdoaXRlOwogIHBhZGRpbmc6IDZweCAxNnB4IDZweCA2cHg7CiAgYm9yZGVyLXJhZGl1czogNTBweDsKICBib3gtc2hhZG93OiAwIDRweCAxNHB4IHJnYmEoMCwwLDAsMC4wOCk7CiAgdGV4dC1kZWNvcmF0aW9uOiBub25lOwogIGNvbG9yOiAjMUUyOTNCOwogIHRyYW5zaXRpb246IGFsbCAwLjJzOwogIGN1cnNvcjogcG9pbnRlcjsKICBib3JkZXI6IDFweCBzb2xpZCAjRTJFOEYwOwp9Ci5wcm9maWxlLWNoaXAtZ2xvYmFsOmhvdmVyIHsKICB0cmFuc2Zvcm06IHRyYW5zbGF0ZVkoLTJweCk7CiAgYm94LXNoYWRvdzogMCA2cHggMjBweCByZ2JhKDAsMCwwLDAuMTIpOwogIGNvbG9yOiAjMUUyOTNCOwp9Ci5wcm9maWxlLWNoaXAtYXZhdGFyIHsKICB3aWR0aDogMzZweDsKICBoZWlnaHQ6IDM2cHg7CiAgYm9yZGVyLXJhZGl1czogNTAlOwogIGJhY2tncm91bmQ6IGxpbmVhci1ncmFkaWVudCgxMzVkZWcsICMxRTI5M0IsICM0NzU1NjkpOwogIGNvbG9yOiB3aGl0ZTsKICBkaXNwbGF5OiBncmlkOwogIHBsYWNlLWl0ZW1zOiBjZW50ZXI7CiAgZm9udC13ZWlnaHQ6IDcwMDsKICBmb250LXNpemU6IDFyZW07Cn0KLnByb2ZpbGUtY2hpcC1uYW1lIHsKICBmb250LXNpemU6IDAuOXJlbTsKICBmb250LXdlaWdodDogNjAwOwp9Cg=='
SMART_DASH_CSS_B64 = 'LyogPT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0KICAgc21hcnRfZGFzaC5jc3MgLSBQcmVtaXVtIERhcmsgVGhlbWUgZm9yIEZpblNpZ2h0IFNtYXJ0IERhc2hib2FyZAogICBVbmlxdWUgcGFsZXR0ZTogRGVlcCBJbmRpZ28gKyBWaW9sZXQgKyBFbWVyYWxkICsgQW1iZXIKICAgPT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0gKi8KCi8qIEFsZXJ0IFBhbmVsIChSaWdodCBTaWRlIEJhcikgKi8KLmFsZXJ0LXBhbmVsLW92ZXJsYXkgewogIGRpc3BsYXk6bm9uZTtwb3NpdGlvbjpmaXhlZDtpbnNldDowOwogIGJhY2tncm91bmQ6cmdiYSgwLDAsMCwwLjUpO3otaW5kZXg6MjAwMDtiYWNrZHJvcC1maWx0ZXI6Ymx1cig0cHgpOwp9Ci5hbGVydC1wYW5lbC1vdmVybGF5Lm9wZW57ZGlzcGxheTpibG9jazt9Ci5hbGVydC1wYW5lbHsKICBwb3NpdGlvbjpmaXhlZDt0b3A6MDtyaWdodDotNDQwcHg7d2lkdGg6NDAwcHg7aGVpZ2h0OjEwMHZoOwogIGJhY2tncm91bmQ6bGluZWFyLWdyYWRpZW50KDE4MGRlZywjMEYxNzJBIDAlLCMxRTI5M0IgMTAwJSk7CiAgei1pbmRleDoyMDAxO3RyYW5zaXRpb246cmlnaHQgMC4zOHMgY3ViaWMtYmV6aWVyKDAuMjUsMC44LDAuMjUsMSk7CiAgZGlzcGxheTpmbGV4O2ZsZXgtZGlyZWN0aW9uOmNvbHVtbjsKICBib3gtc2hhZG93Oi04cHggMCA1MHB4IHJnYmEoMCwwLDAsMC41KTsKICBib3JkZXItbGVmdDoxcHggc29saWQgcmdiYSgyNTUsMjU1LDI1NSwwLjA3KTsKfQouYWxlcnQtcGFuZWwub3BlbntyaWdodDowO30KLmFsZXJ0LXBhbmVsLWhlYWRlcnsKICBwYWRkaW5nOjIycHggMjJweCAxOHB4OwogIGJhY2tncm91bmQ6bGluZWFyLWdyYWRpZW50KDEzNWRlZywjNkQyOEQ5LCM0RjQ2RTUpOwogIGRpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47CiAgZmxleC1zaHJpbms6MDtwb3NpdGlvbjpyZWxhdGl2ZTtvdmVyZmxvdzpoaWRkZW47Cn0KLmFsZXJ0LXBhbmVsLWhlYWRlcjo6YmVmb3JlewogIGNvbnRlbnQ6Jyc7cG9zaXRpb246YWJzb2x1dGU7d2lkdGg6MjAwcHg7aGVpZ2h0OjIwMHB4O2JvcmRlci1yYWRpdXM6NTAlOwogIGJhY2tncm91bmQ6cmdiYSgyNTUsMjU1LDI1NSwwLjA2KTt0b3A6LTgwcHg7cmlnaHQ6LTYwcHg7cG9pbnRlci1ldmVudHM6bm9uZTsKfQouYWxlcnQtcGFuZWwtaGVhZGVyIGgze2NvbG9yOiNmZmY7Zm9udC1zaXplOjEuMDVyZW07Zm9udC13ZWlnaHQ6NzAwO21hcmdpbjowO2Rpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7Z2FwOjEwcHg7fQouYWxlcnQtcGFuZWwtY2xvc2V7CiAgYmFja2dyb3VuZDpyZ2JhKDI1NSwyNTUsMjU1LDAuMTUpO2JvcmRlcjpub25lO2NvbG9yOiNmZmY7CiAgd2lkdGg6MzRweDtoZWlnaHQ6MzRweDtib3JkZXItcmFkaXVzOjUwJTtkaXNwbGF5OmdyaWQ7cGxhY2UtaXRlbXM6Y2VudGVyOwogIGN1cnNvcjpwb2ludGVyO2ZvbnQtc2l6ZToxcmVtO3RyYW5zaXRpb246YmFja2dyb3VuZCAwLjJzOwp9Ci5hbGVydC1wYW5lbC1jbG9zZTpob3ZlcntiYWNrZ3JvdW5kOnJnYmEoMjU1LDI1NSwyNTUsMC4yOCk7fQouYWxlcnQtcGFuZWwtYWN0aW9uc3sKICBwYWRkaW5nOjE0cHggMjJweCAxMHB4O2Rpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpjZW50ZXI7CiAgYm9yZGVyLWJvdHRvbToxcHggc29saWQgcmdiYSgyNTUsMjU1LDI1NSwwLjA4KTtmbGV4LXNocmluazowOwp9Ci5hbGVydC1jb3VudC1iYWRnZXsKICBiYWNrZ3JvdW5kOmxpbmVhci1ncmFkaWVudCgxMzVkZWcsI0VGNDQ0NCwjREMyNjI2KTtjb2xvcjojZmZmOwogIGZvbnQtc2l6ZTowLjczcmVtO2ZvbnQtd2VpZ2h0OjcwMDtwYWRkaW5nOjNweCAxMHB4O2JvcmRlci1yYWRpdXM6MTAwcHg7Cn0KLm1hcmstYWxsLXJlYWQtYnRuewogIGJhY2tncm91bmQ6bm9uZTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMjU1LDI1NSwyNTUsMC4xOCk7Y29sb3I6Izk0QTNCODsKICBmb250LXNpemU6MC43M3JlbTtwYWRkaW5nOjRweCAxMnB4O2JvcmRlci1yYWRpdXM6MTAwcHg7Y3Vyc29yOnBvaW50ZXI7dHJhbnNpdGlvbjphbGwgMC4yczsKfQoubWFyay1hbGwtcmVhZC1idG46aG92ZXJ7YmFja2dyb3VuZDpyZ2JhKDI1NSwyNTUsMjU1LDAuMDgpO2NvbG9yOiNmZmY7fQouYWxlcnQtbGlzdHtmbGV4OjE7b3ZlcmZsb3cteTphdXRvO3BhZGRpbmc6MTJweCAxNHB4O3Njcm9sbGJhci13aWR0aDp0aGluO3Njcm9sbGJhci1jb2xvcjojMzM0MTU1IHRyYW5zcGFyZW50O30KLmFsZXJ0LWl0ZW17CiAgcGFkZGluZzoxNHB4IDE2cHg7Ym9yZGVyLXJhZGl1czoxMnB4O21hcmdpbi1ib3R0b206MTBweDtjdXJzb3I6cG9pbnRlcjsKICBib3JkZXI6MXB4IHNvbGlkIHJnYmEoMjU1LDI1NSwyNTUsMC4wNik7dHJhbnNpdGlvbjpiYWNrZ3JvdW5kIDAuMnMsdHJhbnNmb3JtIDAuMTVzO3Bvc2l0aW9uOnJlbGF0aXZlOwogIGFuaW1hdGlvbjpzbGlkZUluQWxlcnQgMC4zcyBlYXNlIGZvcndhcmRzOwp9CkBrZXlmcmFtZXMgc2xpZGVJbkFsZXJ0e2Zyb217b3BhY2l0eTowO3RyYW5zZm9ybTp0cmFuc2xhdGVYKDE2cHgpfXRve29wYWNpdHk6MTt0cmFuc2Zvcm06dHJhbnNsYXRlWCgwKX19Ci5hbGVydC1pdGVtOmhvdmVye2JhY2tncm91bmQ6cmdiYSgyNTUsMjU1LDI1NSwwLjA1KTt0cmFuc2Zvcm06dHJhbnNsYXRlWCgtMnB4KTt9Ci5hbGVydC1pdGVtLnVucmVhZHtiYWNrZ3JvdW5kOnJnYmEoOTksMTAyLDI0MSwwLjEzKTtib3JkZXItY29sb3I6cmdiYSg5OSwxMDIsMjQxLDAuMjgpO30KLmFsZXJ0LWl0ZW0uc2V2ZXJpdHktZGFuZ2Vye2JvcmRlci1sZWZ0OjNweCBzb2xpZCAjRUY0NDQ0O30KLmFsZXJ0LWl0ZW0uc2V2ZXJpdHktd2FybmluZ3tib3JkZXItbGVmdDozcHggc29saWQgI0Y1OUUwQjt9Ci5hbGVydC1pdGVtLnNldmVyaXR5LWluZm97Ym9yZGVyLWxlZnQ6M3B4IHNvbGlkICMzQjgyRjY7fQouYWxlcnQtaXRlbS10aXRsZXtmb250LXNpemU6MC44NnJlbTtmb250LXdlaWdodDo3MDA7Y29sb3I6I0YxRjVGOTttYXJnaW4tYm90dG9tOjVweDtsaW5lLWhlaWdodDoxLjM7fQouYWxlcnQtaXRlbS1tc2d7Zm9udC1zaXplOjAuNzdyZW07Y29sb3I6Izk0QTNCODtsaW5lLWhlaWdodDoxLjU7fQouYWxlcnQtaXRlbS10aW1le2ZvbnQtc2l6ZTowLjY5cmVtO2NvbG9yOiM0NzU1Njk7bWFyZ2luLXRvcDo3cHg7fQouYWxlcnQtdW5yZWFkLWRvdHtwb3NpdGlvbjphYnNvbHV0ZTt0b3A6MTJweDtyaWdodDoxMnB4O3dpZHRoOjhweDtoZWlnaHQ6OHB4O2JvcmRlci1yYWRpdXM6NTAlO2JhY2tncm91bmQ6IzYzNjZGMTt9Ci5hbGVydC1lbXB0eXt0ZXh0LWFsaWduOmNlbnRlcjtwYWRkaW5nOjYwcHggMjBweDtjb2xvcjojNDc1NTY5O2ZvbnQtc2l6ZTowLjlyZW07fQouYWxlcnQtZW1wdHkgaXtmb250LXNpemU6Mi41cmVtO2Rpc3BsYXk6YmxvY2s7bWFyZ2luLWJvdHRvbToxMnB4O2NvbG9yOiMzMzQxNTU7fQoKLyogTm90aWZpY2F0aW9uIEJlbGwgKi8KLm5vdGlmLWJlbGwtYnRuewogIHBvc2l0aW9uOmZpeGVkO3RvcDoxOHB4O3JpZ2h0OiAyMjBweDt6LWluZGV4OjE1MDA7CiAgd2lkdGg6NDhweDtoZWlnaHQ6NDhweDtib3JkZXItcmFkaXVzOjE0cHg7CiAgYmFja2dyb3VuZDpsaW5lYXItZ3JhZGllbnQoMTM1ZGVnLCM0RjQ2RTUsIzdDM0FFRCk7Ym9yZGVyOm5vbmU7CiAgY29sb3I6I2ZmZjtkaXNwbGF5OmdyaWQ7cGxhY2UtaXRlbXM6Y2VudGVyO2ZvbnQtc2l6ZToxLjI1cmVtOwogIGN1cnNvcjpwb2ludGVyO2JveC1zaGFkb3c6MCA0cHggMjBweCByZ2JhKDc5LDcwLDIyOSwwLjUpOwogIHRyYW5zaXRpb246dHJhbnNmb3JtIDAuMnMsYm94LXNoYWRvdyAwLjJzOwp9Ci5ub3RpZi1iZWxsLWJ0bjpob3Zlcnt0cmFuc2Zvcm06c2NhbGUoMS4wOCkgcm90YXRlKC01ZGVnKTtib3gtc2hhZG93OjAgNnB4IDI2cHggcmdiYSg3OSw3MCwyMjksMC42NSk7fQoubm90aWYtYmVsbC1idG46YWN0aXZle3RyYW5zZm9ybTpzY2FsZSgwLjk2KTt9Ci5ub3RpZi1iYWRnZXsKICBwb3NpdGlvbjphYnNvbHV0ZTt0b3A6LTVweDtyaWdodDotNXB4OwogIGJhY2tncm91bmQ6bGluZWFyLWdyYWRpZW50KDEzNWRlZywjRUY0NDQ0LCNEQzI2MjYpO2NvbG9yOiNmZmY7CiAgZm9udC1zaXplOjAuNnJlbTtmb250LXdlaWdodDo4MDA7bWluLXdpZHRoOjE4cHg7aGVpZ2h0OjE4cHg7CiAgYm9yZGVyLXJhZGl1czoxMDBweDtkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpjZW50ZXI7CiAgcGFkZGluZzowIDRweDtib3JkZXI6MnB4IHNvbGlkICNmZmY7YW5pbWF0aW9uOnB1bHNlQmFkZ2UgMS44cyBlYXNlLWluLW91dCBpbmZpbml0ZTsKfQoubm90aWYtYmFkZ2UuaGlkZGVue2Rpc3BsYXk6bm9uZTt9CkBrZXlmcmFtZXMgcHVsc2VCYWRnZXsKICAwJSwxMDAle3RyYW5zZm9ybTpzY2FsZSgxKTtib3gtc2hhZG93OjAgMCAwIDAgcmdiYSgyMzksNjgsNjgsMC40KTt9CiAgNTAle3RyYW5zZm9ybTpzY2FsZSgxLjE1KTtib3gtc2hhZG93OjAgMCAwIDVweCByZ2JhKDIzOSw2OCw2OCwwKTt9Cn0KCi8qIFNtYXJ0IERhc2hib2FyZCBIZXJvICovCi5zbWFydC1kYXNoLWhlcm97CiAgYmFja2dyb3VuZDpsaW5lYXItZ3JhZGllbnQoMTM1ZGVnLCMwRjE3MkEgMCUsIzFFMUI0QiA1NSUsIzMxMkU4MSAxMDAlKTsKICBib3JkZXItcmFkaXVzOjIwcHg7cGFkZGluZzozMHB4IDM0cHg7CiAgZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjsKICBtYXJnaW4tYm90dG9tOjI0cHg7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDI1NSwyNTUsMjU1LDAuMDcpOwogIHBvc2l0aW9uOnJlbGF0aXZlO292ZXJmbG93OmhpZGRlbjsKfQouc21hcnQtZGFzaC1oZXJvOjpiZWZvcmV7CiAgY29udGVudDonJztwb3NpdGlvbjphYnNvbHV0ZTt3aWR0aDo0MDBweDtoZWlnaHQ6NDAwcHg7Ym9yZGVyLXJhZGl1czo1MCU7CiAgYmFja2dyb3VuZDpyYWRpYWwtZ3JhZGllbnQoY2lyY2xlLHJnYmEoOTksMTAyLDI0MSwwLjE4KSAwJSx0cmFuc3BhcmVudCA3MCUpOwogIHRvcDotMTUwcHg7cmlnaHQ6LTgwcHg7cG9pbnRlci1ldmVudHM6bm9uZTsKfQouaGVyby1ncmVldGluZ3tjb2xvcjojZmZmO30KLmhlcm8tZ3JlZXRpbmcgaDF7CiAgZm9udC1zaXplOjEuODVyZW07Zm9udC13ZWlnaHQ6OTAwO21hcmdpbjowIDAgNnB4O2xldHRlci1zcGFjaW5nOi0wLjA0ZW07CiAgYmFja2dyb3VuZDpsaW5lYXItZ3JhZGllbnQoMTM1ZGVnLCNmZmYgMCUsI0E1QjRGQyAxMDAlKTsKICAtd2Via2l0LWJhY2tncm91bmQtY2xpcDp0ZXh0Oy13ZWJraXQtdGV4dC1maWxsLWNvbG9yOnRyYW5zcGFyZW50O2JhY2tncm91bmQtY2xpcDp0ZXh0Owp9Ci5oZXJvLWdyZWV0aW5nIHB7Y29sb3I6Izk0QTNCODtmb250LXNpemU6MC45cmVtO21hcmdpbjowO30KLmhlcm8tZGF0ZS1iYWRnZXsKICBiYWNrZ3JvdW5kOnJnYmEoMjU1LDI1NSwyNTUsMC4wNyk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDI1NSwyNTUsMjU1LDAuMTIpOwogIGJvcmRlci1yYWRpdXM6MTRweDtwYWRkaW5nOjEycHggMjBweDtjb2xvcjojOTRBM0I4O2ZvbnQtc2l6ZTowLjgycmVtO3RleHQtYWxpZ246cmlnaHQ7Cn0KLmhlcm8tZGF0ZS1iYWRnZSBzdHJvbmd7ZGlzcGxheTpibG9jaztjb2xvcjojRTJFOEYwO2ZvbnQtc2l6ZToxLjA1cmVtO2ZvbnQtd2VpZ2h0OjcwMDttYXJnaW4tYm90dG9tOjJweDt9CgovKiBTbWFydCBLUEkgUm93ICovCi5zbWFydC1rcGktcm93e2Rpc3BsYXk6Z3JpZDtncmlkLXRlbXBsYXRlLWNvbHVtbnM6cmVwZWF0KDUsMWZyKTtnYXA6MTZweDttYXJnaW4tYm90dG9tOjI0cHg7fQpAbWVkaWEobWF4LXdpZHRoOjEzMDBweCl7LnNtYXJ0LWtwaS1yb3d7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOnJlcGVhdCgzLDFmcik7fX0KQG1lZGlhKG1heC13aWR0aDo5MDBweCl7LnNtYXJ0LWtwaS1yb3d7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOnJlcGVhdCgyLDFmcik7fX0KQG1lZGlhKG1heC13aWR0aDo2MDBweCl7LnNtYXJ0LWtwaS1yb3d7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOjFmcjt9fQoua3BpLWNhcmR7CiAgYmFja2dyb3VuZDojZmZmO2JvcmRlci1yYWRpdXM6MThweDtwYWRkaW5nOjIwcHggMjJweDsKICBib3gtc2hhZG93OjAgMnB4IDIwcHggcmdiYSgxNSwyMyw0MiwwLjA3KTtib3JkZXI6MXB4IHNvbGlkICNGMUY1Rjk7CiAgcG9zaXRpb246cmVsYXRpdmU7b3ZlcmZsb3c6aGlkZGVuOwogIHRyYW5zaXRpb246dHJhbnNmb3JtIDAuMjVzLGJveC1zaGFkb3cgMC4yNXM7CiAgYW5pbWF0aW9uOmtwaUVudHJhbmNlIDAuNXMgZWFzZSBmb3J3YXJkcztvcGFjaXR5OjA7Cn0KLmtwaS1jYXJkOm50aC1jaGlsZCgxKXthbmltYXRpb24tZGVsYXk6MC4wNXN9Ci5rcGktY2FyZDpudGgtY2hpbGQoMil7YW5pbWF0aW9uLWRlbGF5OjAuMTBzfQoua3BpLWNhcmQ6bnRoLWNoaWxkKDMpe2FuaW1hdGlvbi1kZWxheTowLjE1c30KLmtwaS1jYXJkOm50aC1jaGlsZCg0KXthbmltYXRpb24tZGVsYXk6MC4yMHN9Ci5rcGktY2FyZDpudGgtY2hpbGQoNSl7YW5pbWF0aW9uLWRlbGF5OjAuMjVzfQpAa2V5ZnJhbWVzIGtwaUVudHJhbmNle2Zyb217b3BhY2l0eTowO3RyYW5zZm9ybTp0cmFuc2xhdGVZKDE0cHgpfXRve29wYWNpdHk6MTt0cmFuc2Zvcm06dHJhbnNsYXRlWSgwKX19Ci5rcGktY2FyZDpob3Zlcnt0cmFuc2Zvcm06dHJhbnNsYXRlWSgtNHB4KTtib3gtc2hhZG93OjAgMTJweCAzMnB4IHJnYmEoMTUsMjMsNDIsMC4xMyk7fQoua3BpLWNhcmQ6OmJlZm9yZXtjb250ZW50OicnO3Bvc2l0aW9uOmFic29sdXRlO3RvcDowO2xlZnQ6MDtyaWdodDowO2hlaWdodDozcHg7Ym9yZGVyLXJhZGl1czoxOHB4IDE4cHggMCAwO30KLmtwaS1jYXJkLmtwaS1ibHVlOjpiZWZvcmV7YmFja2dyb3VuZDpsaW5lYXItZ3JhZGllbnQoOTBkZWcsIzI1NjNFQiwjNjBBNUZBKTt9Ci5rcGktY2FyZC5rcGktZ3JlZW46OmJlZm9yZXtiYWNrZ3JvdW5kOmxpbmVhci1ncmFkaWVudCg5MGRlZywjMDU5NjY5LCMzNEQzOTkpO30KLmtwaS1jYXJkLmtwaS1vcmFuZ2U6OmJlZm9yZXtiYWNrZ3JvdW5kOmxpbmVhci1ncmFkaWVudCg5MGRlZywjRUE1ODBDLCNGQjkyM0MpO30KLmtwaS1jYXJkLmtwaS1wdXJwbGU6OmJlZm9yZXtiYWNrZ3JvdW5kOmxpbmVhci1ncmFkaWVudCg5MGRlZywjN0MzQUVELCNBNzhCRkEpO30KLmtwaS1jYXJkLmtwaS1pbmRpZ286OmJlZm9yZXtiYWNrZ3JvdW5kOmxpbmVhci1ncmFkaWVudCg5MGRlZywjNEY0NkU1LCM4MThDRjgpO30KLmtwaS1sYWJlbHtmb250LXNpemU6MC43cmVtO2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjojOTRBM0I4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTtsZXR0ZXItc3BhY2luZzowLjA3ZW07bWFyZ2luLWJvdHRvbTo2cHg7fQoua3BpLXZhbHVle2ZvbnQtc2l6ZToxLjVyZW07Zm9udC13ZWlnaHQ6OTAwO2NvbG9yOiMwRjE3MkE7bGV0dGVyLXNwYWNpbmc6LTAuMDRlbTt9Ci5rcGktc3Vie2ZvbnQtc2l6ZTowLjcycmVtO2NvbG9yOiM2NDc0OEI7bWFyZ2luLXRvcDo1cHg7Zm9udC13ZWlnaHQ6NTAwO30KLmtwaS1pY29ue3Bvc2l0aW9uOmFic29sdXRlO3RvcDoxOHB4O3JpZ2h0OjE4cHg7Zm9udC1zaXplOjEuOHJlbTtvcGFjaXR5OjAuMDk7fQoKLyogVHJlbmQgQ2hhcnQgKi8KLnRyZW5kLXNlY3Rpb257CiAgYmFja2dyb3VuZDojZmZmO2JvcmRlci1yYWRpdXM6MjBweDtwYWRkaW5nOjI2cHggMjhweDsKICBib3gtc2hhZG93OjAgMnB4IDE4cHggcmdiYSgxNSwyMyw0MiwwLjA3KTtib3JkZXI6MXB4IHNvbGlkICNGMUY1Rjk7bWFyZ2luLWJvdHRvbToyNHB4Owp9Ci50cmVuZC1oZWFkZXJ7ZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2FsaWduLWl0ZW1zOmNlbnRlcjttYXJnaW4tYm90dG9tOjIycHg7ZmxleC13cmFwOndyYXA7Z2FwOjEycHg7fQoudHJlbmQtdGl0bGV7Zm9udC1zaXplOjEuMXJlbTtmb250LXdlaWdodDo4MDA7Y29sb3I6IzBGMTcyQTt9Ci50cmVuZC1sZWdlbmR7ZGlzcGxheTpmbGV4O2dhcDoyMHB4O2ZsZXgtd3JhcDp3cmFwO30KLnRyZW5kLWxlZ2VuZC1pdGVte2Rpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7Z2FwOjdweDtmb250LXNpemU6MC43N3JlbTtmb250LXdlaWdodDo2MDA7Y29sb3I6IzY0NzQ4Qjt9Ci50cmVuZC1sZWdlbmQtZG90e3dpZHRoOjEwcHg7aGVpZ2h0OjEwcHg7Ym9yZGVyLXJhZGl1czo1MCU7fQoudHJlbmQtY2hhcnQtd3JhcHtoZWlnaHQ6MjcwcHg7cG9zaXRpb246cmVsYXRpdmU7fQoKLyogQUkgSW5zaWdodHMgKi8KLmFpLXNlY3Rpb257CiAgYmFja2dyb3VuZDpsaW5lYXItZ3JhZGllbnQoMTM1ZGVnLCMwRjE3MkEgMCUsIzFFMjkzQiAxMDAlKTsKICBib3JkZXItcmFkaXVzOjIwcHg7cGFkZGluZzoyNnB4IDI4cHg7bWFyZ2luLWJvdHRvbToyNHB4OwogIGJvcmRlcjoxcHggc29saWQgcmdiYSgyNTUsMjU1LDI1NSwwLjA3KTtwb3NpdGlvbjpyZWxhdGl2ZTtvdmVyZmxvdzpoaWRkZW47Cn0KLmFpLXNlY3Rpb246OmJlZm9yZXsKICBjb250ZW50OicnO3Bvc2l0aW9uOmFic29sdXRlO3dpZHRoOjMwMHB4O2hlaWdodDozMDBweDtib3JkZXItcmFkaXVzOjUwJTsKICBiYWNrZ3JvdW5kOnJhZGlhbC1ncmFkaWVudChjaXJjbGUscmdiYSg5OSwxMDIsMjQxLDAuMTUpIDAlLHRyYW5zcGFyZW50IDcwJSk7CiAgdG9wOi0xMDBweDtyaWdodDotNjBweDtwb2ludGVyLWV2ZW50czpub25lOwp9Ci5haS1oZWFkZXJ7ZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtnYXA6MTRweDttYXJnaW4tYm90dG9tOjIwcHg7fQouYWktYmFkZ2V7CiAgYmFja2dyb3VuZDpsaW5lYXItZ3JhZGllbnQoMTM1ZGVnLCM0RjQ2RTUsIzdDM0FFRCk7Y29sb3I6I2ZmZjsKICBmb250LXNpemU6MC42NXJlbTtmb250LXdlaWdodDo4MDA7cGFkZGluZzo0cHggMTJweDtib3JkZXItcmFkaXVzOjEwMHB4O2xldHRlci1zcGFjaW5nOjAuMWVtOwp9Ci5haS10aXRsZXtmb250LXNpemU6MS4wOHJlbTtmb250LXdlaWdodDo4MDA7Y29sb3I6I0YxRjVGOTt9Ci5haS1ncmlke2Rpc3BsYXk6Z3JpZDtncmlkLXRlbXBsYXRlLWNvbHVtbnM6cmVwZWF0KGF1dG8tZmlsbCxtaW5tYXgoMjIwcHgsMWZyKSk7Z2FwOjE0cHg7fQouYWktY2FyZHsKICBiYWNrZ3JvdW5kOnJnYmEoMjU1LDI1NSwyNTUsMC4wNik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDI1NSwyNTUsMjU1LDAuMSk7CiAgYm9yZGVyLXJhZGl1czoxNHB4O3BhZGRpbmc6MTdweDt0cmFuc2l0aW9uOmJhY2tncm91bmQgMC4ycyx0cmFuc2Zvcm0gMC4xOHM7CiAgYW5pbWF0aW9uOmFpQ2FyZEluIDAuNHMgZWFzZSBmb3J3YXJkcztvcGFjaXR5OjA7Cn0KLmFpLWNhcmQ6bnRoLWNoaWxkKDEpe2FuaW1hdGlvbi1kZWxheTowLjFzfS5haS1jYXJkOm50aC1jaGlsZCgyKXthbmltYXRpb24tZGVsYXk6MC4xOHN9Ci5haS1jYXJkOm50aC1jaGlsZCgzKXthbmltYXRpb24tZGVsYXk6MC4yNnN9LmFpLWNhcmQ6bnRoLWNoaWxkKDQpe2FuaW1hdGlvbi1kZWxheTowLjM0c30KQGtleWZyYW1lcyBhaUNhcmRJbntmcm9te29wYWNpdHk6MDt0cmFuc2Zvcm06dHJhbnNsYXRlWSgxMHB4KX10b3tvcGFjaXR5OjE7dHJhbnNmb3JtOnRyYW5zbGF0ZVkoMCl9fQouYWktY2FyZDpob3ZlcntiYWNrZ3JvdW5kOnJnYmEoMjU1LDI1NSwyNTUsMC4xKTt0cmFuc2Zvcm06dHJhbnNsYXRlWSgtMnB4KTt9Ci5haS1jYXJkLXRvcHtkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO21hcmdpbi1ib3R0b206OXB4O30KLmFpLWNhcmQtaWNvbntmb250LXNpemU6MS41cmVtO30KLmFpLWNhcmQtYmFkZ2V7Zm9udC1zaXplOjAuNjJyZW07Zm9udC13ZWlnaHQ6NzAwO3BhZGRpbmc6MnB4IDhweDtib3JkZXItcmFkaXVzOjEwMHB4O2JhY2tncm91bmQ6cmdiYSgyNTUsMjU1LDI1NSwwLjEyKTtjb2xvcjojOTRBM0I4O30KLmFpLWNhcmQtdGl0bGV7Zm9udC1zaXplOjAuODNyZW07Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOiNFMkU4RjA7bWFyZ2luLWJvdHRvbTo1cHg7fQouYWktY2FyZC10ZXh0e2ZvbnQtc2l6ZTowLjc1cmVtO2NvbG9yOiM2NDc0OEI7bGluZS1oZWlnaHQ6MS41NTt9CgovKiBCdWRnZXQgVHJhY2tlciAqLwouc2VjdGlvbi10aXRsZS1yb3d7ZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtnYXA6MTJweDttYXJnaW4tYm90dG9tOjE4cHg7fQouc2VjdGlvbi10aXRsZS1iYXJ7d2lkdGg6NHB4O2hlaWdodDoyMnB4O2JvcmRlci1yYWRpdXM6MnB4O2ZsZXgtc2hyaW5rOjA7fQouc2VjdGlvbi10aXRsZXtmb250LXNpemU6MS4xcmVtO2ZvbnQtd2VpZ2h0OjgwMDtjb2xvcjojMEYxNzJBO21hcmdpbjowO30KLnNlY3Rpb24tbGlua3tmb250LXNpemU6MC44cmVtO2ZvbnQtd2VpZ2h0OjYwMDtjb2xvcjojNjM2NkYxO21hcmdpbi1sZWZ0OmF1dG87dGV4dC1kZWNvcmF0aW9uOm5vbmU7dHJhbnNpdGlvbjpjb2xvciAwLjJzO30KLnNlY3Rpb24tbGluazpob3Zlcntjb2xvcjojNEY0NkU1O30KLmJ1ZGdldC10cmFja2VyLWdyaWR7ZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczpyZXBlYXQoYXV0by1maWxsLG1pbm1heCgyODBweCwxZnIpKTtnYXA6MTZweDt9Ci5idWRnZXQtdHJhY2tlci1jYXJkewogIGJhY2tncm91bmQ6I2ZmZjtib3JkZXItcmFkaXVzOjE2cHg7cGFkZGluZzoxOHB4IDIwcHg7CiAgYm9yZGVyOjFweCBzb2xpZCAjRjFGNUY5O2JveC1zaGFkb3c6MCAycHggMTRweCByZ2JhKDE1LDIzLDQyLDAuMDYpOwogIHRyYW5zaXRpb246dHJhbnNmb3JtIDAuMjJzLGJveC1zaGFkb3cgMC4yMnM7CiAgYW5pbWF0aW9uOmJ0Y0luIDAuNHMgZWFzZSBmb3J3YXJkcztvcGFjaXR5OjA7Cn0KQGtleWZyYW1lcyBidGNJbntmcm9te29wYWNpdHk6MDt0cmFuc2Zvcm06c2NhbGUoMC45Nyl9dG97b3BhY2l0eToxO3RyYW5zZm9ybTpzY2FsZSgxKX19Ci5idWRnZXQtdHJhY2tlci1jYXJkOmhvdmVye3RyYW5zZm9ybTp0cmFuc2xhdGVZKC0zcHgpO2JveC1zaGFkb3c6MCAxMHB4IDI4cHggcmdiYSgxNSwyMyw0MiwwLjEpO30KLmJ0Yy10b3B7ZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2FsaWduLWl0ZW1zOmZsZXgtc3RhcnQ7bWFyZ2luLWJvdHRvbToxMHB4O30KLmJ0Yy1jYXR7Zm9udC1zaXplOjAuODhyZW07Zm9udC13ZWlnaHQ6ODAwO2NvbG9yOiMwRjE3MkE7fQouYnRjLWdvYWwtbGlua3tmb250LXNpemU6MC43MXJlbTtjb2xvcjojNjM2NkYxO2ZvbnQtd2VpZ2h0OjYwMDtiYWNrZ3JvdW5kOnJnYmEoOTksMTAyLDI0MSwwLjEpO3BhZGRpbmc6MnB4IDhweDtib3JkZXItcmFkaXVzOjEwMHB4O30KLmJ0Yy1uby1nb2Fse2ZvbnQtc2l6ZTowLjdyZW07Y29sb3I6I0NCRDVFMTt9Ci5idGMtYW1vdW50c3tkaXNwbGF5OmZsZXg7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47Zm9udC1zaXplOjAuNzdyZW07Y29sb3I6IzY0NzQ4QjttYXJnaW4tYm90dG9tOjhweDt9Ci5idGMtYW1vdW50cyBzdHJvbmd7Y29sb3I6IzBGMTcyQTtmb250LXdlaWdodDo3MDA7fQouYnRjLWJhci13cmFwe2hlaWdodDo3cHg7YmFja2dyb3VuZDojRjFGNUY5O2JvcmRlci1yYWRpdXM6MTAwcHg7b3ZlcmZsb3c6aGlkZGVuO30KLmJ0Yy1iYXJ7aGVpZ2h0OjEwMCU7Ym9yZGVyLXJhZGl1czoxMDBweDt0cmFuc2l0aW9uOndpZHRoIDAuOHMgY3ViaWMtYmV6aWVyKDAuMjUsMC44LDAuMjUsMSk7fQouYnRjLWJhci5va3tiYWNrZ3JvdW5kOmxpbmVhci1ncmFkaWVudCg5MGRlZywjMTBCOTgxLCMzNEQzOTkpO30KLmJ0Yy1iYXIud2FybmluZ3tiYWNrZ3JvdW5kOmxpbmVhci1ncmFkaWVudCg5MGRlZywjRjU5RTBCLCNGQ0QzNEQpO30KLmJ0Yy1iYXIuZXhjZWVkZWR7YmFja2dyb3VuZDpsaW5lYXItZ3JhZGllbnQoOTBkZWcsI0VGNDQ0NCwjRjg3MTcxKTt9Ci5idGMtZm9vdGVye2Rpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpjZW50ZXI7bWFyZ2luLXRvcDo4cHg7fQouYnRjLXBjdHtmb250LXNpemU6MC43cmVtO2ZvbnQtd2VpZ2h0OjcwMDt9Ci5idGMtcGN0Lm9re2NvbG9yOiMxMEI5ODE7fS5idGMtcGN0Lndhcm5pbmd7Y29sb3I6I0Y1OUUwQjt9LmJ0Yy1wY3QuZXhjZWVkZWR7Y29sb3I6I0VGNDQ0NDt9Ci5idGMtbW9udGh7Zm9udC1zaXplOjAuNjhyZW07Y29sb3I6Izk0QTNCODt9CgovKiDilIDilIAgUGFuZWwgVGl0bGUgUm93ICh1c2VkIGFjcm9zcyBhbGwgZGFzaGJvYXJkIHBhbmVscykg4pSA4pSA4pSA4pSA4pSA4pSA4pSAICovCi5wYW5lbC10aXRsZS1yb3cgewogIGRpc3BsYXk6IGZsZXg7CiAgYWxpZ24taXRlbXM6IGNlbnRlcjsKICBqdXN0aWZ5LWNvbnRlbnQ6IHNwYWNlLWJldHdlZW47CiAgbWFyZ2luLWJvdHRvbTogMThweDsKICBnYXA6IDEwcHg7Cn0KLnBhbmVsLXRpdGxlLXJvdyBoNCB7CiAgZm9udC1zaXplOiAxcmVtOwogIGZvbnQtd2VpZ2h0OiA4MDA7CiAgY29sb3I6ICMwRjE3MkE7CiAgbWFyZ2luOiAwOwp9Ci5wYW5lbC10aXRsZS1yb3cgLmxpbmstYmx1ZSB7CiAgZm9udC1zaXplOiAwLjhyZW07CiAgZm9udC13ZWlnaHQ6IDYwMDsKICBjb2xvcjogIzYzNjZGMTsKICB0ZXh0LWRlY29yYXRpb246IG5vbmU7CiAgdHJhbnNpdGlvbjogY29sb3IgMC4yczsKfQoucGFuZWwtdGl0bGUtcm93IC5saW5rLWJsdWU6aG92ZXIgeyBjb2xvcjogIzRGNDZFNTsgfQoKLyog4pSA4pSAIE5vdGlmaWNhdGlvbiBCZWxsIOKAlCBmaXhlZCB0b3AtcmlnaHQsIGJlbG93IGhhbWJ1cmdlciBhcmVhIOKUgOKUgCAqLwovKiBPdmVycmlkZTogbW92ZSBiZWxsIGJ1dHRvbiBzbyBpdCBkb2Vzbid0IG92ZXJsYXAgaGFtYnVyZ2VyICh0b3AtbGVmdCkgKi8KLm5vdGlmLWJlbGwtYnRuIHsKICBwb3NpdGlvbjogZml4ZWQ7CiAgdG9wOiAxOHB4OwogIHJpZ2h0OiAgMjIwcHg7CiAgei1pbmRleDogMTUwMDsKfQoKLyog4pSA4pSAIFJlZnJlc2ggZmxhc2ggZm9yIEtQSSBjYXJkcyDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIAgKi8KQGtleWZyYW1lcyBrcGlSZWZyZXNoRmxhc2ggewogIDAlICAgeyBib3gtc2hhZG93OiAwIDAgMCAwIHJnYmEoOTksMTAyLDI0MSwwLjApOyB9CiAgNDAlICB7IGJveC1zaGFkb3c6IDAgMCAwIDhweCByZ2JhKDk5LDEwMiwyNDEsMC4yMik7IH0KICAxMDAlIHsgYm94LXNoYWRvdzogMCAwIDAgMCByZ2JhKDk5LDEwMiwyNDEsMC4wKTsgfQp9Ci5rcGktY2FyZC5yZWZyZXNoLWZsYXNoIHsgYW5pbWF0aW9uOiBrcGlSZWZyZXNoRmxhc2ggMC44cyBlYXNlOyB9CgovKiDilIDilIAgZGFzaC1uYXYtbG9nby1pbWcgZmFsbGJhY2sg4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSAICovCi5kYXNoLW5hdi1sb2dvLWltZyB7CiAgYm9yZGVyLXJhZGl1czogMTJweDsKICBvYmplY3QtZml0OiBjb3ZlcjsKfQoKLyogUHJvZmlsZSBDaGlwICovCi5wcm9maWxlLWNoaXAtZ2xvYmFsIHsKICBwb3NpdGlvbjogZml4ZWQ7CiAgdG9wOiAxOHB4OwogIHJpZ2h0OiAyMnB4OwogIHotaW5kZXg6IDE1MDA7CiAgZGlzcGxheTogZmxleDsKICBhbGlnbi1pdGVtczogY2VudGVyOwogIGdhcDogMTBweDsKICBiYWNrZ3JvdW5kOiB3aGl0ZTsKICBwYWRkaW5nOiA2cHggMTZweCA2cHggNnB4OwogIGJvcmRlci1yYWRpdXM6IDUwcHg7CiAgYm94LXNoYWRvdzogMCA0cHggMTRweCByZ2JhKDAsMCwwLDAuMDgpOwogIHRleHQtZGVjb3JhdGlvbjogbm9uZTsKICBjb2xvcjogIzFFMjkzQjsKICB0cmFuc2l0aW9uOiBhbGwgMC4yczsKICBjdXJzb3I6IHBvaW50ZXI7CiAgYm9yZGVyOiAxcHggc29saWQgI0UyRThGMDsKfQoucHJvZmlsZS1jaGlwLWdsb2JhbDpob3ZlciB7CiAgdHJhbnNmb3JtOiB0cmFuc2xhdGVZKC0ycHgpOwogIGJveC1zaGFkb3c6IDAgNnB4IDIwcHggcmdiYSgwLDAsMCwwLjEyKTsKICBjb2xvcjogIzFFMjkzQjsKfQoucHJvZmlsZS1jaGlwLWF2YXRhciB7CiAgd2lkdGg6IDM2cHg7CiAgaGVpZ2h0OiAzNnB4OwogIGJvcmRlci1yYWRpdXM6IDUwJTsKICBiYWNrZ3JvdW5kOiBsaW5lYXItZ3JhZGllbnQoMTM1ZGVnLCAjMUUyOTNCLCAjNDc1NTY5KTsKICBjb2xvcjogd2hpdGU7CiAgZGlzcGxheTogZ3JpZDsKICBwbGFjZS1pdGVtczogY2VudGVyOwogIGZvbnQtd2VpZ2h0OiA3MDA7CiAgZm9udC1zaXplOiAxcmVtOwp9Ci5wcm9maWxlLWNoaXAtbmFtZSB7CiAgZm9udC1zaXplOiAwLjlyZW07CiAgZm9udC13ZWlnaHQ6IDYwMDsKfQo='

# Custom routes to serve inline CSS
@app.route('/static/css/style.css')
def serve_style_css():
    content = base64.b64decode(STYLE_CSS_B64).decode('utf-8')
    return Response(content, mimetype='text/css')

@app.route('/static/css/dashboard.css')
def serve_dashboard_css():
    content = base64.b64decode(DASHBOARD_CSS_B64).decode('utf-8')
    return Response(content, mimetype='text/css')

@app.route('/static/css/smart_dash.css')
def serve_smart_dash_css():
    content = base64.b64decode(SMART_DASH_CSS_B64).decode('utf-8')
    return Response(content, mimetype='text/css')
