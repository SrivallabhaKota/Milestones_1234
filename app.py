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
