CREATE DATABASE IF NOT EXISTS finsight
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE finsight;

-- 1. Users Table
CREATE TABLE IF NOT EXISTS users (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  name        VARCHAR(100)  NOT NULL,
  email       VARCHAR(100)  NOT NULL UNIQUE,
  password    VARCHAR(255)  NOT NULL,
  created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Income Table
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

-- 3. Expenses Table
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

-- 4. Budget Table
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

-- 5. Investments Table
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

-- 6. Goals Table
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

-- 7. Goal Parts Table
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

-- 8. Savings Goals Table (Detail logs)
CREATE TABLE IF NOT EXISTS savings_goals (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  goal_id         INT           NOT NULL,
  amount          DECIMAL(12,2) NOT NULL,
  saving_date     DATE          NOT NULL,
  note            VARCHAR(255),
  created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (goal_id) REFERENCES goals(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 9. User Profile Table
CREATE TABLE IF NOT EXISTS user_profile (
  id                          INT AUTO_INCREMENT PRIMARY KEY,
  user_id                     INT NOT NULL UNIQUE,
  phone                       VARCHAR(20),
  currency                    VARCHAR(10) DEFAULT '₹',
  monthly_saving_capacity     DECIMAL(12,2) DEFAULT 0.00,
  monthly_investment_capacity DECIMAL(12,2) DEFAULT 0.00,
  notes                       TEXT,
  profile_pic                 VARCHAR(255) DEFAULT NULL,
  created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 10. Alerts Table
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

-- Seed Demo Data
INSERT INTO users (id, name, email, password) VALUES
  (1, 'Demo User', 'demo@finsight.com', '$2b$12$KIXxLpf4q1cTaV3sYlQS9.GZtN5f.kFQzPqFdD8Xr1BkW2jH7eIBm')
  ON DUPLICATE KEY UPDATE id=1;
