# 📊 FinSight – Personal Finance & Investment Intelligence Platform

<div align="center">

![FinSight Banner](https://img.shields.io/badge/FinSight-Finance%20Intelligence-6c63ff?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZmlsbD0id2hpdGUiIGQ9Ik0xMiAyQzYuNDggMiAyIDYuNDggMiAxMnM0LjQ4IDEwIDEwIDEwIDEwLTQuNDggMTAtMTBTMTcuNTIgMiAxMiAyem0xIDE1aC0ydi02aDJ2NnptMC04aC0yVjdoMnYyeiIvPjwvc3ZnPg==)
![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=for-the-badge&logo=flask&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?style=for-the-badge&logo=mysql&logoColor=white)
![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3-7952B3?style=for-the-badge&logo=bootstrap&logoColor=white)

**A premium, dark-themed, glassmorphism-inspired personal finance & investment intelligence platform built as a B.Tech Major Project.**

[🚀 Features](#-features) • [🛠️ Tech Stack](#%EF%B8%8F-tech-stack) • [📦 Installation](#-installation) • [🗄️ Database Setup](#%EF%B8%8F-database-setup) • [▶️ How to Run](#%EF%B8%8F-how-to-run) • [📁 Folder Structure](#-folder-structure)

</div>

---

## 🌟 Overview

FinSight is a **full-stack web application** that provides users with a secure, elegant platform to manage their personal finances and investments. Designed with a **startup-grade UI**, FinSight features:

- 🔐 **Secure Authentication** — bcrypt-encrypted passwords, Flask Sessions
- 🎨 **Premium UI** — Dark glassmorphism, animated particles, cursor glow
- 📊 **Financial Dashboard** — Stats cards, transactions, savings goals, budget tracker
- 📱 **Fully Responsive** — Works on mobile, tablet, laptop, and desktop

---

## ✨ Features

### 🔐 Authentication Module
| Feature | Details |
|---|---|
| Login Page | Email + password with remember me, show/hide toggle |
| Registration | Live validation, password strength meter, rules checklist |
| Password Security | bcrypt hashing (12 rounds), never plain text |
| Session Auth | Flask sessions protect all dashboard routes |
| Error Handling | Beautiful Bootstrap alerts (success / danger / warning) |
| Forgot Password | Placeholder ready for future email integration |

### 🎨 UI/UX
| Feature | Details |
|---|---|
| Design Theme | Dark glassmorphism, gradient glows |
| Custom Cursor | Glowing cursor + smooth ring |
| Mouse Trail | 8-dot trailing animation |
| Particle Canvas | 60 interconnected animated particles |
| Floating Icons | Finance emoji icons drifting in background |
| Animations | Fade, slide, zoom, ripple, counter, typing effect |
| Typography | Outfit + Inter (Google Fonts) |

### 📊 Dashboard
| Widget | Details |
|---|---|
| Stats Cards | Expenses, Income, Savings, Investments with animated counters |
| Transactions | Recent transaction table with badges |
| Quick Actions | Expense / Income / Invest / Reports buttons |
| Savings Goals | 3 goals with animated progress bars |
| Budget Overview | Category-wise spending bars |
| Expense Trend | 7-day mini bar chart |
| Net Worth | Animated counter with growth indicator |

---

## 🛠️ Tech Stack

```
Frontend      →  HTML5, CSS3 (Vanilla), Bootstrap 5.3, JavaScript (ES6+)
Backend       →  Python 3.8+, Flask 3.0
Database      →  MySQL 8.0
Auth          →  Flask Sessions + bcrypt
Icons         →  Bootstrap Icons 1.11
Fonts         →  Google Fonts (Outfit, Inter)
```

---

## 📋 Requirements

```
Flask==3.0.3
Flask-MySQLdb==2.0.0
bcrypt==4.1.3
mysqlclient==2.2.4
Werkzeug==3.0.3
```

> **System Requirements:** Python 3.8+, MySQL 8.0+, pip

---

## 📦 Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/yourusername/finsight.git
cd finsight
```

### Step 2: Create a Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

> ⚠️ **Windows users:** If `mysqlclient` fails, install via:
> ```bash
> pip install mysqlclient --only-binary :all:
> ```
> Or download the wheel from [Gohlke's page](https://www.lfd.uci.edu/~gohlke/pythonlibs/).

---

## 🗄️ Database Setup

### Step 1: Start MySQL
Make sure your MySQL server is running (via XAMPP, WAMP, or system MySQL).

### Step 2: Import the SQL File

**Option A — phpMyAdmin:**
1. Open `http://localhost/phpmyadmin`
2. Click **Import**
3. Select `database.sql`
4. Click **Go**

**Option B — MySQL CLI:**
```bash
mysql -u root -p < database.sql
```

### Step 3: Configure Database Credentials

Open `config.py` and update:

```python
MYSQL_USER     = 'root'          # your MySQL username
MYSQL_PASSWORD = 'yourpassword'  # your MySQL password
MYSQL_DB       = 'finsight'
```

---

## ▶️ How to Run

```bash
# Make sure virtual environment is active
# Make sure MySQL is running with finsight database

python app.py
```

Open your browser: **http://localhost:5000**

You'll land on the **Login Page** by default.

### Test Credentials
```
Email    : demo@finsight.com
Password : Test@1234
```
*(Only works if the sample INSERT in database.sql is imported with this exact bcrypt hash)*

---

## 📁 Folder Structure

```
FinSight/
│
├── app.py              ← Flask application (routes, auth logic)
├── config.py           ← App & database configuration
├── requirements.txt    ← Python dependencies
├── database.sql        ← MySQL schema + sample data
├── README.md           ← This file
├── .gitignore          ← Git ignore rules
│
├── static/
│   ├── css/
│   │   └── style.css   ← Complete design system (1000+ lines)
│   ├── js/
│   │   └── script.js   ← All UI interactions & animations
│   └── images/         ← (reserved for future assets)
│
└── templates/
    ├── layout.html     ← Base Jinja2 template (shared assets)
    ├── login.html      ← Login page
    ├── register.html   ← Registration page
    └── dashboard.html  ← Protected dashboard
```

---

## 🔗 Routes

| Route | Method | Description | Auth Required |
|---|---|---|---|
| `/` | GET | Redirect to login or dashboard | No |
| `/login` | GET, POST | Login form + authentication | No |
| `/register` | GET, POST | Registration form + account creation | No |
| `/dashboard` | GET | Protected financial dashboard | ✅ Yes |
| `/logout` | GET | Destroy session + redirect to login | ✅ Yes |
| `/forgot-password` | GET | Placeholder (future email reset) | No |

---

## 🔒 Security Features

- ✅ **bcrypt** password hashing (12 rounds of salting)
- ✅ **Flask Sessions** — server-side session management
- ✅ **HTTPOnly cookies** — prevents XSS attacks
- ✅ **Backend validation** on all form inputs
- ✅ **Duplicate email** detection
- ✅ **Route protection** via `@login_required` decorator
- ✅ **Direct URL guarding** — `/dashboard` redirects to login if not authenticated

---

## 📸 Screenshots

> _Add screenshots here after running the project._

| Page | Screenshot |
|---|---|
| Login | `screenshots/login.png` |
| Register | `screenshots/register.png` |
| Dashboard | `screenshots/dashboard.png` |

---

## 🚀 Future Enhancements

- [ ] Email-based password reset
- [ ] Google OAuth 2.0 login
- [ ] Real expense tracking with CRUD
- [ ] Investment portfolio tracker (live stock prices)
- [ ] AI-powered spending insights
- [ ] PDF / CSV financial report export
- [ ] Budget alerts & notifications
- [ ] Two-factor authentication (2FA)
- [ ] Multi-currency support
- [ ] Mobile app (React Native)

---