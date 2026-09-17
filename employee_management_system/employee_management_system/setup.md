# Complete Setup Guide: Employee Management System (EMS)

This guide provides instructions for setting up the **Employee Management System (EMS)** from scratch on any system (Ubuntu, Debian, macOS, or Windows WSL2).

The system consists of:
- **Backend**: Frappe Framework v15+ (Python 3.10/3.11, MariaDB 10.6+, Redis)
- **Frontend**: React 19 SPA (Vite 8, Tailwind CSS, Lucide Icons, shadcn/ui)
- **Attendance & Shifts**: Master Shift Types, Weekly Offs, Shift Assignments, GPS Geofencing, Company Holiday Calendar, Status-Aware Single-Action Clock IN/OUT Controls, 30-Minute Late Entry Grace Period Standard, and Strict Status Priority Auto-Attendance.
- **Leave & Payroll Workflows**: Real-time Balance Checking, Immediate Attendance Synchronization, Leave Cancellation Reversion, Today's Active Leave & Workforce Headcount Synchronization, Loss of Pay (LOP) Automation, Idempotent Batch Payroll, PDF Paystubs, and Email Tracking.
- **AI & Intelligent Services**: AST SQL Guard (sqlglot), Intent Router, Qdrant Vector Engine in Docker (384-dim semantic embeddings with offline NumPy fallback), and Persistent Chat Session Management.

---

## 📑 Table of Contents

1. [System Requirements & Architecture](#1-system-requirements--architecture)
2. [Operating System Prerequisites & Docker](#2-operating-system-prerequisites--docker)
3. [MariaDB Server Configuration](#3-mariadb-server-configuration)
4. [Frappe Bench Installation & Setup](#4-frappe-bench-installation--setup)
5. [App Installation & Python Dependencies](#5-app-installation--python-dependencies)
6. [Database Schema & Automated Data Seeding](#6-database-schema--automated-data-seeding)
7. [Scheduler & Background Jobs Setup](#7-scheduler--background-jobs-setup)
8. [React Frontend Installation & Build](#8-react-frontend-installation--build)
9. [Running the Application](#9-running-the-application)
10. [Automated Test Suite Verification](#10-automated-test-suite-verification)
11. [Production Deployment Architecture](#11-production-deployment-architecture)
12. [Troubleshooting & FAQs](#12-troubleshooting--faqs)

---

## 1. System Requirements & Architecture

### Recommended Specifications:
- **Operating System**: Ubuntu 22.04 / 24.04 LTS, Debian 12, macOS Sonoma / Sequoia, or Windows 11 with WSL2 (Ubuntu)
- **CPU**: 2+ Cores (4+ Cores recommended)
- **RAM**: 4 GB minimum (8 GB recommended)
- **Disk Space**: 10 GB free space
- **Docker**: Docker Engine 20.10+ & Docker Compose v2+ for Qdrant vector database

### Architecture Overview:
```
                      ┌────────────────────────────────────────┐
                      │          React 19 Frontend SPA         │
                      │          http://localhost:5173         │
                      │  • Shifts CRUD & Company Holidays UI   │
                      │  • Real-time Leave Balance & Cancel    │
                      │  • Today's Leave & Active Staff Sync   │
                      │  • Status-Aware Attendance Controls    │
                      │  • Batch Payroll Runs & PDF/Email      │
                      │  • In-App Notification Bell & Badge    │
                      │  • Persistent AI Chat Session History  │
                      └───────────────────┬────────────────────┘
                                          │
                                          │ /api HTTP Proxy
                                          ▼
                      ┌────────────────────────────────────────┐
                      │         Frappe Backend Server          │
                      │          http://localhost:8001         │
                      ├────────────────────────────────────────┤
                      │ • Session Auth & RBAC                  │
                      │ • Shift Attendance Priority Engine     │
                      │ • Leave-to-Attendance Sync & Revert    │
                      │ • Automated LOP & Batch Payroll Run    │
                      │ • AST SQL Guard & Chat Orchestrator    │
                      │ • Qdrant Vector Knowledge Engine       │
                      └───────┬──────────────┬──────────────┬──┘
                              │              │              │
                              ▼              ▼              ▼
                    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
                    │ MariaDB 10.6 │ │ Redis Server │ │Qdrant(Docker)│
                    │Relational DB │ │Queue & Cache │ │Vector DB:6333│
                    └──────────────┘ └──────────────┘ └──────────────┘
```

---

## 2. Operating System Prerequisites

### A. Ubuntu 22.04 / 24.04 LTS or Debian 12

Run the following commands in your terminal:

```bash
# 1. Update system packages
sudo apt update && sudo apt upgrade -y

# 2. Install essential build tools, Git, curl
sudo apt install -y git curl wget build-essential software-properties-common

# 3. Install Python 3.11, pip, and development headers
sudo apt install -y python3 python3-dev python3-pip python3-venv

# 4. Install MariaDB and client libraries
sudo apt install -y mariadb-server mariadb-client libmysqlclient-dev

# 5. Install Redis
sudo apt install -y redis-server
sudo systemctl enable redis-server && sudo systemctl start redis-server

# 6. Install Node.js 20 LTS and npm via NodeSource
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Verify versions
python3 --version   # Python 3.10+ or 3.11+
node -v             # v18+ or v20+
npm -v              # 9+ or 10+
mariadb --version   # 10.6+
```

### B. macOS (Homebrew)
```bash
brew install python@3.11 node@20 mariadb redis git curl
brew services start mariadb
brew services start redis
```

---

## 3. MariaDB Server Configuration

Frappe requires specific configuration settings in `my.cnf` (or `/etc/mysql/mariadb.conf.d/50-server.cnf`):

```ini
[mysqld]
character-set-client-handshake = FALSE
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci

[mysql]
default-character-set = utf8mb4
```

Restart MariaDB after updating:
```bash
sudo systemctl restart mariadb
```

---

## 4. Frappe Bench Installation & Setup

```bash
# 1. Install frappe-bench CLI
pip install frappe-bench

# 2. Initialize new bench with Frappe v15
bench init --frappe-branch version-15 frappe-bench
cd frappe-bench

# 3. Create your site (e.g. hospital.localhost)
bench new-site hospital.localhost \
  --mariadb-root-password your_mariadb_root_password \
  --admin-password EmsAdmin2026!
```

---

## 5. App Installation & Python Dependencies

### Step 5.1: Clone or Copy `employee_management_system`
Place the `employee_management_system` app inside `frappe-bench/apps/`:
```bash
cd frappe-bench/apps
# Copy or clone repo
```

### Step 5.2: Install App on Site
```bash
cd frappe-bench
bench --site hospital.localhost install-app employee_management_system
```

### Step 5.3: Install Python Dependencies
```bash
./env/bin/pip install sqlglot numpy reportlab
```

---

## 6. Database Schema & Automated Data Seeding

We provide an automated setup script [`setup_init_data.py`](file:///home/tui013/frappe-benchv/apps/employee_management_system/employee_management_system/employee_management_system/setup_init_data.py) that reloads all 16 DocTypes and seeds enterprise baseline data.

### Step 6.1: Run the Automated Setup Script

```bash
./env/bin/python apps/employee_management_system/employee_management_system/employee_management_system/setup_init_data.py
```

### What this automated script performs:
1. **Reloads 16 DocTypes Schema into MariaDB**:
   - `Department`, `Employee`, `Leave Type`, `Leave Application`, `Salary Slip`, `Salary Slip Allowance`, `Salary Slip Deduction`, `Payroll`, `Holiday`, `Office Location`, `Shift Type`, `Shift Assignment`, `Employee Checkin`, `Attendance`, `Chat Message`, `Chat Session`
2. **Configures Roles**:
   - `Administrator`, `HR`, `HR Manager`, `Employee`, `System Manager`
3. **Creates 3 Demo Accounts**:
   - 🛡️ **Administrator**: `admin@ems.com` (Password: `SarahJenkins`, or `Administrator` / `admin`)
   - 📋 **HR Manager**: `hr@ems.com` (Password: `AlexRivera`)
   - 👤 **Employee**: `employee@ems.com` (Password: `DavidChen`)
4. **Seeds Standard Departments, Shift Types & Company Holidays**:
   - Day Shift, Night Shift with configured `weekly_off_days`
   - Company Holiday Calendar (`tabHoliday`)
5. **Seeds Standard Leave Policies**:
   - Sick Leave (12 days), Casual Leave (14 days), Annual Leave (20 days, carry-forward enabled), Leave Without Pay (0 days quota / LOP).

---

## 7. Scheduler & Background Jobs Setup

### Step 7.1: Enable Scheduler on Site
```bash
bench --site hospital.localhost enable-scheduler
```

### Step 7.2: Scheduled Tasks in `hooks.py`
- **Periodic (`all`) & Hourly**: `process_shift_completion_job` (evaluates active check-in sessions against scheduled shift end times and automatically clocks out completed sessions at exact shift end timestamps with reason `'Shift Completed'`)
- **Hourly**: `process_auto_attendance_job` (evaluates shift assignments for yesterday and today, reconciling overnight night shifts and enforcing strict status priorities)
- **Daily**: `process_auto_attendance_daily` (performs 3-day retroactive reconciliation)

---

## 8. React Frontend Installation & Build

The modern React 19 SPA is located in:
`apps/employee_management_system/employee_management_system/employee_management_system/frontend/`

### Step 8.1: Install Node Dependencies
```bash
cd apps/employee_management_system/employee_management_system/employee_management_system/frontend
npm install
```

### Step 8.2: Build Production Bundle
```bash
npm run build
```
*(Produces optimized static assets in `dist/` cleanly).*

---

## 9. Running the Application

### Terminal 1: Frappe Backend Server
```bash
cd frappe-bench
bench --site hospital.localhost serve --port 8001
```

### Terminal 2: React Frontend Dev Server
```bash
cd frappe-bench/apps/employee_management_system/employee_management_system/employee_management_system/frontend
npm run dev
```

Navigate to: **`http://localhost:5173`**

---

## 10. Automated Test Suite Verification

Every core subsystem has an automated test suite. Run all 164 tests from your `frappe-bench/sites` directory:

```bash
cd /home/tui013/frappe-benchv/sites

# 1. Automatic Clock-Out System Suite (14 Tests)
../env/bin/python ../apps/employee_management_system/employee_management_system/test_auto_clock_out.py

# 2. GPS Attendance Security & Validation Suite (19 Tests)
../env/bin/python ../apps/employee_management_system/employee_management_system/test_gps_attendance.py

# 3. Shift-Based Automatic Attendance Engine (14 Tests)
../env/bin/python ../apps/employee_management_system/employee_management_system/test_shift_attendance.py

# 4. Shift Attendance Enhancements: Holidays & Weekly Offs Suite (5 Tests)
../env/bin/python ../apps/employee_management_system/employee_management_system/test_shift_attendance_enhancements.py

# 5. Leave Workflow Enhancements: Balances, Sync & Cancellation (6 Tests)
../env/bin/python ../apps/employee_management_system/employee_management_system/test_leave_workflow_enhancements.py

# 6. Payroll & LOP Enhancements: Derivation, Batch Runs & Dispatch (4 Tests)
../env/bin/python ../apps/employee_management_system/employee_management_system/test_payroll_enhancements.py

# 7. SQL Guard AST Security & RBAC Suite (34 Tests)
../env/bin/python ../apps/employee_management_system/employee_management_system/test_sql_guard.py

# 8. Intent Router & Classification Suite (30 Tests)
../env/bin/python ../apps/employee_management_system/employee_management_system/test_intent_router.py

# 9. Chat Orchestrator & Multi-Turn Pipeline (18 Tests)
../env/bin/python ../apps/employee_management_system/employee_management_system/test_orchestrator.py

# 10. Natural Language Result Formatter Suite (14 Tests)
../env/bin/python ../apps/employee_management_system/employee_management_system/test_result_formatter.py

# 11. Qdrant Vector Database & Resilient Knowledge Engine (10 Tests)
../env/bin/python ../apps/employee_management_system/employee_management_system/test_qdrant_knowledge.py
```

*Expected output: All 11 test suites report `OK` with zero failures (168/168 passing).*

---

## 11. Production Deployment Architecture

```bash
cd frappe-bench
bench --site hospital.localhost set-config developer_mode 0

cd apps/employee_management_system/employee_management_system/employee_management_system/frontend
npm run build
cd ../../../..

sudo bench setup production <your_linux_username>
sudo supervisorctl restart all
sudo systemctl reload nginx
```

---

## 12. Troubleshooting & FAQs

### Q1: `Lost connection to MySQL server` or connection drops during batch runs
**Resolution**: Ensure `max_allowed_packet = 64M` and `wait_timeout = 600` are set in MariaDB configuration (`/etc/mysql/my.cnf`).

### Q2: Salary Slip PDF Download returns 403 or blank
**Resolution**: Verify that authenticated user has `Administrator` or `HR` role, or is downloading their own personal slip. The endpoint dynamically renders HTML and converts using `frappe.utils.pdf.get_pdf`.

### Q3: Batch Payroll skips slips
**Resolution**: Batch payroll is strictly idempotent. If a salary slip already exists for that employee and month, it is safely skipped unless the `Regenerate Existing Slips` checkbox is selected.

### Q4: Automatic clock-out not triggering when scheduled shift ends
**Resolution**: Ensure Frappe Scheduler is enabled on the site (`bench --site hospital.localhost enable-scheduler`). The system now includes multi-level fallback shift resolution (`Day Shift` 09:00 - 17:00) so unassigned staff are never stranded in "Working" state, and page refresh/pulse calls evaluate shift completion in real-time.
