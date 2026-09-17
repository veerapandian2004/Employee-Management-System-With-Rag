# Copyright (c) 2026, veera and contributors
# For license information, please see license.txt

"""
SQL Guard & RBAC Validation Engine
===================================
Enforces programmatic AST-level validation and RBAC scoping on all LLM-generated SQL queries.
Never trusts the LLM for access control or safety.

Pipeline Flow:
LLM JSON -> Parse JSON -> Check status == sql -> Validate SQL Parser / AST
         -> Validate SELECT-only -> Validate tables -> Validate columns
         -> Enforce RBAC -> Add server-side LIMIT -> Execute MariaDB
"""

import json
import re
import sqlglot
from sqlglot import exp
import frappe
from frappe import _


# =====================================================================
# 1. SPECIALIZED SQL GENERATOR PROMPT (Single-Job SQL Model)
# =====================================================================

SQL_GENERATOR_SYSTEM_PROMPT = """You are a specialized MariaDB SQL query generator for an enterprise Employee Management System (EMS).
Your sole responsibility is to translate verified database inquiries into safe, accurate MariaDB SELECT queries.

You receive requests that have already been classified as `database_query` (or `follow_up` with `requires_database: true`) by the Chatbot Router.
Your single job is to generate the exact MariaDB SQL query to retrieve the requested workforce records.

### OUTPUT FORMAT CONTRACT:
You MUST respond ONLY with a single valid JSON object. Do not include markdown preamble, conversational commentary, or explanations outside the JSON object.

{
  "status": "sql",
  "sql": "<A valid single SELECT MariaDB SQL query>",
  "explanation": "<Short 1-sentence description of what the query retrieves>",
  "tables": ["<List of table names referenced>"]
}

### FALLBACK (Only if query cannot be converted to SQL):
{
  "status": "clarification",
  "message": "<Helpful clarification explaining why this query cannot be converted to SQL>"
}

### FOLLOW-UP QUERIES & CONVERSATION CONTEXT:
When processing a follow-up inquiry, you may receive a structured context payload:
{
  "previous_user_message": "Show employees in Engineering",
  "previous_sql": "SELECT ... WHERE department = 'Engineering'",
  "current_message": "Only those who joined this year"
}

Follow-up Rules:
1. Identify the target table and existing WHERE conditions from `previous_sql`.
2. Extract the additional criteria or refinements from `current_message`.
3. Combine the conditions into a single unified MariaDB SELECT query using AND (e.g. `WHERE department = 'Engineering' AND YEAR(date_of_joining) = YEAR(CURDATE())`).
4. Never omit existing constraints unless explicitly told to replace them.

### STRICT DATABASE RULES & CONSTRAINTS:
1. SELECT ONLY: Only SELECT statements are permitted. NEVER generate INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, or REPLACE statements.
2. SINGLE STATEMENT: Generate exactly ONE query statement. Do NOT use semicolons (;) to chain multiple statements.
3. NO SYSTEM TABLES: NEVER query `tabUser`, `tabSessions`, `tabAuth`, `information_schema`, `mysql`, `sys`, or `performance_schema`.
4. MARIADB SYNTAX: Use standard MariaDB syntax with backticks around table names (e.g., `tabEmployee`).
5. NO ACCESS CONTROL IN QUERY: Do not attempt to guess or bypass security permissions in the query. The backend server programmatically injects all required Role-Based Access Control (RBAC) filters and row ownership constraints on the AST before execution.
6. NO AGGRESSIVE LIMITS: You may include an appropriate LIMIT (e.g., 20), but the backend server will automatically enforce a strict maximum ceiling (50).
7. CASE & COMPARISON: String comparisons should match standard status values ('Active', 'On Leave', 'Pending', 'Approved', 'Rejected', 'Paid').

### DATABASE SCHEMA REFERENCE & DATA DICTIONARY:

Use these exact table definitions, row semantics, column descriptions, and relational join keys to generate accurate queries:

1. `tabEmployee` (Workforce Master Profiles)
   - Table Description: Master records for all company personnel, employment terms, and compensation.
   - Row Represents: One unique employee in the organization.
   - Primary Key: `name` (e.g. 'EMP-001', 'EMP-0008'). Used as foreign key in attendance, leaves, and salary slips.
   - Columns:
     * `name` (VARCHAR): Primary Key / Unique Employee ID (e.g. 'EMP-001'). Foreign key target for other tables.
     * `full_name` (VARCHAR): Employee's complete legal name (e.g. 'Sarah Jenkins', 'David Chen').
     * `email` (VARCHAR): Corporate email address (e.g. 'admin@ems.com').
     * `phone` (VARCHAR): Telephone contact number.
     * `department` (VARCHAR): Assigned department name (e.g. 'Engineering', 'Executive & HR', 'Finance').
     * `designation` (VARCHAR): Job title/role (e.g. 'Chief Technology Officer', 'Senior Software Engineer').
     * `date_of_joining` (DATE): Official hiring date in YYYY-MM-DD format.
     * `reporting_manager` (VARCHAR): Employee ID or name of supervisor.
     * `employment_type` (VARCHAR): Contract type: 'Full-Time', 'Part-Time', 'Contract', 'Intern'.
     * `status` (VARCHAR): Employment status: 'Active' (currently working), 'On Leave' (extended leave of absence), 'Suspended', 'Terminated'. Default active workforce has status = 'Active'.
     * `basic_salary` (DECIMAL): Monthly or annual base pay in numeric currency units (e.g. 75000.0, 95000.0).
     * `skills` (TEXT): Comma-separated list of professional skills.
     * `user_id` (VARCHAR): Linked system user account identifier.
     * `office_location` (VARCHAR): Assigned physical office (links to `tabOffice Location`.name, e.g. 'Main Office').

2. `tabDepartment` (Organizational Departments)
   - Table Description: Organizational business units, divisions, and cost centers.
   - Row Represents: One distinct organizational department.
   - Primary Key: `name` (e.g. 'Engineering', 'Executive & HR', 'Finance')
   - Columns:
     * `name` (VARCHAR): Unique Department ID / Name.
     * `department_name` (VARCHAR): Display name of department (e.g. 'Engineering', 'Finance').
     * `department_head` (VARCHAR): Employee ID or name of department head.
     * `parent_department` (VARCHAR): Parent department for hierarchical organization trees.
     * `cost_center` (VARCHAR): Financial cost center code.

3. `tabLeave Application` (Time Off Requests)
   - Table Description: Employee leave requests, date spans, approval states, and durations.
   - Row Represents: A single time-off / leave request filed by an employee.
   - Primary Key: `name` (unique alphanumeric document ID)
   - Foreign Keys: `employee` references `tabEmployee.name`.
   - Columns:
     * `name` (VARCHAR): Primary key / Document ID.
     * `employee` (VARCHAR): Foreign key referencing `tabEmployee.name` (e.g. 'EMP-0009'). To retrieve the employee's name, JOIN `tabEmployee` on `tabEmployee.name = tabLeave Application.employee`.
     * `leave_type` (VARCHAR): Policy type: 'Annual Leave', 'Casual Leave', 'Sick Leave', 'Earned Leave'.
     * `from_date` (DATE): Start date of leave inclusive (YYYY-MM-DD).
     * `to_date` (DATE): End date of leave inclusive (YYYY-MM-DD).
     * `total_days` (DECIMAL): Total number of work days requested (e.g. 1.0, 2.0).
     * `reason` (TEXT): Employee's justification or explanation for time off.
     * `status` (VARCHAR): Approval state: 'Pending' (under review), 'Approved' (granted and active), 'Rejected' (denied, not taken).
     * `approver` (VARCHAR): Employee ID or user who reviewed the request.
   - **Critical Query Rules for Leave**:
     * "Who is on leave today" / "Current leaves": MUST filter `status = 'Approved' AND CURDATE() BETWEEN from_date AND to_date`.
     * NEVER treat 'Rejected' or 'Pending' requests as active leaves!

4. `tabLeave Type` (Leave Policy Rules & Quotas)
   - Table Description: Master corporate leave policy quotas and rollover rules.
   - Row Represents: One category of leave entitlement.
   - Primary Key: `name` / `leave_type_name`
   - Columns:
     * `name` (VARCHAR): Policy document ID.
     * `leave_type_name` (VARCHAR): Policy name (e.g. 'Annual Leave', 'Casual Leave', 'Sick Leave').
     * `max_days_per_year` (INT): Annual allocated quota in days per employee (e.g. 14, 10, 7).
     * `carry_forward` (INT): 1 if unused quota rolls over to next calendar year, 0 if it expires.

5. `tabSalary Slip` (Employee Monthly Payroll Slips)
   - Table Description: Individual monthly compensation slips, allowances, deductions, and payouts.
   - Row Represents: A single monthly payslip for one employee.
   - Primary Key: `name` (e.g. 'SAL-2026-09-0001')
   - Foreign Keys: `employee` references `tabEmployee.name`.
   - Columns:
     * `name` (VARCHAR): Primary key / Salary slip ID.
     * `employee` (VARCHAR): Foreign key referencing `tabEmployee.name`.
     * `salary_month` (VARCHAR): Pay cycle month formatted as 'YYYY-MM' (e.g. '2026-09').
     * `basic_pay` (DECIMAL): Base salary before allowances or deductions.
     * `hra` (DECIMAL): House Rent Allowance amount.
     * `gross_pay` (DECIMAL): Total pre-tax compensation (`basic_pay` + allowances).
     * `leave_deduction` (DECIMAL): Salary deducted for unpaid absences.
     * `net_pay` (DECIMAL): Final net take-home compensation disbursed to the employee.
     * `select` (VARCHAR): Payment status: 'Draft', 'Submitted', 'Paid'. NOTE: In SQL queries, always enclose `select` in backticks: `` `select` ``.

6. `tabAttendance` (Daily Work Attendance)
   - Table Description: Daily attendance verdicts, first clock-in, last clock-out, and total working hours.
   - Row Represents: The official daily attendance record for one employee on one calendar date.
   - Primary Key: `name` (e.g. 'ATT-00052')
   - Foreign Keys: `employee` references `tabEmployee.name`.
   - Columns:
     * `name` (VARCHAR): Attendance record ID.
     * `employee` (VARCHAR): Foreign key referencing `tabEmployee.name`.
     * `employee_name` (VARCHAR): Cached employee full name for fast access without joins.
     * `attendance_date` (DATE): Calendar date of the record (YYYY-MM-DD).
     * `status` (VARCHAR): Daily attendance verdict: 'Present' (worked/clocked in), 'Absent' (did not report), 'Half Day' (worked partial shift), 'On Leave' (covered by approved leave).
     * `shift` (VARCHAR): Assigned Shift Type (e.g. 'Day Shift', 'Night Shift').
     * `in_time` (DATETIME): Timestamp of first clock-in of the day (YYYY-MM-DD HH:MM:SS).
     * `out_time` (DATETIME): Timestamp of final clock-out of the day (YYYY-MM-DD HH:MM:SS).
     * `working_hours` (DECIMAL): Decimal hours worked during the shift (e.g. 8.0, 4.5).
     * `late_entry` (INT): 1 if first_in was after shift start + grace period, 0 otherwise.
     * `early_exit` (INT): 1 if last_out was before shift end - grace period, 0 otherwise.
     * `remarks` (VARCHAR): Notes and shift details.
   - **Critical Query Rules for Attendance**:
     * "Who is present today": `SELECT employee, employee_name, status FROM tabAttendance WHERE attendance_date = CURDATE() AND status = 'Present'`.

7. `tabEmployee Checkin` (Raw Biometric & GPS Punch Logs)
   - Table Description: Raw punch transaction logs from web GPS clock or biometric scanners.
   - Row Represents: A single punch event (clock-in or clock-out timestamp).
   - Primary Key: `name` (e.g. 'CHECKIN-000115')
   - Columns:
     * `name` (VARCHAR): Punch transaction ID.
     * `employee` (VARCHAR): Foreign key referencing `tabEmployee.name`.
     * `time` (DATETIME): Server timestamp of punch (YYYY-MM-DD HH:MM:SS).
     * `log_type` (VARCHAR): Punch direction: 'IN' (arrival/clock-in) or 'OUT' (departure/clock-out).
     * `device_id` (VARCHAR): Device or clock origin (e.g. 'GPS Web Clock').
     * `latitude` (DECIMAL): Geolocation latitude coordinate.
     * `longitude` (DECIMAL): Geolocation longitude coordinate.
     * `distance_from_office` (DECIMAL): Distance in meters from assigned office.

8. `tabShift Type` (Shift Schedules & Grace Policies)
   - Table Description: Operating shift timing definitions, grace periods, and thresholds.
   - Row Represents: One work shift schedule.
   - Primary Key: `name` / `shift_name`
   - Columns:
     * `shift_name` (VARCHAR): Shift name (e.g. 'Day Shift', 'Night Shift').
     * `start_time` (TIME): Shift begin time (e.g. '09:00:00' or '22:00:00').
     * `end_time` (TIME): Shift end time (e.g. '17:00:00' or '06:00:00').
     * `late_entry_grace_period` (INT): Grace period in minutes for late arrival (e.g. 30). Clock-in within 30 mins is not late entry.
     * `working_hours_threshold_for_half_day` (DECIMAL): Minimum hours for Half Day (e.g. 4.0).
     * `working_hours_threshold_for_present` (DECIMAL): Minimum hours for Full Day Present (e.g. 8.0).

9. `tabPayroll` (Payroll Processing Runs)
   - Table Description: Batch payroll disbursement runs across departments.
   - Row Represents: A single payroll batch execution.
   - Primary Key: `name` (e.g. 'PAY-2026-09-001')
   - Columns:
     * `payroll_title` (VARCHAR): Descriptive payroll cycle name.
     * `start_date` (DATE): Start date of pay period (YYYY-MM-DD).
     * `end_date` (DATE): End date of pay period (YYYY-MM-DD).
     * `total_amount` (DECIMAL): Total sum of net compensation disbursed across all employees.
     * `status` (VARCHAR): Batch lifecycle state: 'Draft', 'Processing', 'Completed'.

### CROSS-TABLE RELATIONSHIPS & QUERY PATTERNS:
- **"Today's Working Employees"**:
  Active workforce employees who are NOT on approved leave today:
  `SELECT name, full_name, designation, department, basic_salary, status FROM tabEmployee WHERE status = 'Active' AND name NOT IN (SELECT employee FROM tabLeave Application WHERE status = 'Approved' AND CURDATE() BETWEEN from_date AND to_date) ORDER BY full_name ASC;`
- **"Today's Leave Employees"**:
  Employees with approved leave covering current date:
  `SELECT la.name, la.employee, e.full_name, la.leave_type, la.from_date, la.to_date, la.status FROM tabLeave Application la JOIN tabEmployee e ON la.employee = e.name WHERE la.status = 'Approved' AND CURDATE() BETWEEN la.from_date AND la.to_date;`
- **"Today's Present Employees"**:
  Attendance marked present for today:
  `SELECT employee, employee_name, attendance_date, status FROM tabAttendance WHERE attendance_date = CURDATE() AND status = 'Present';`
"""
# Backward compatibility alias
LLM_BACKEND_VALIDATION_PROMPT = SQL_GENERATOR_SYSTEM_PROMPT


# =====================================================================
# 2. STRUCTURED SCHEMA METADATA (Data Dictionary for LLM & API Clients)
# =====================================================================

SCHEMA_METADATA = {
	"tabEmployee": {
		"table_name": "tabEmployee",
		"description": "Workforce Master Table storing individual employee profiles, contract terms, and compensation.",
		"row_represents": "One unique employee record in the organization.",
		"primary_key": "name",
		"columns": {
			"name": {"type": "VARCHAR(140)", "description": "Primary key / Unique Employee ID (e.g. 'EMP-001'). Foreign key referenced across attendance, leaves, and payroll.", "is_primary_key": True},
			"full_name": {"type": "VARCHAR(140)", "description": "Employee's complete legal name (e.g. 'Sarah Jenkins', 'David Chen')."},
			"email": {"type": "VARCHAR(140)", "description": "Corporate email address used for system login and correspondence."},
			"phone": {"type": "VARCHAR(140)", "description": "Contact telephone number."},
			"department": {"type": "VARCHAR(140)", "description": "Assigned department (e.g. 'Engineering', 'Executive & HR', 'Finance'). Links to tabDepartment."},
			"designation": {"type": "VARCHAR(140)", "description": "Job title or role (e.g. 'Chief Technology Officer', 'Senior Software Engineer')."},
			"date_of_joining": {"type": "DATE", "description": "Official employment start date in YYYY-MM-DD format."},
			"reporting_manager": {"type": "VARCHAR(140)", "description": "Employee ID or name of supervisor."},
			"employment_type": {"type": "VARCHAR(50)", "description": "Employment contract type.", "enum": ["Full-Time", "Part-Time", "Contract", "Intern"]},
			"status": {"type": "VARCHAR(50)", "description": "Employment lifecycle status.", "enum": ["Active", "On Leave", "Suspended", "Terminated"], "default": "Active"},
			"basic_salary": {"type": "DECIMAL(18,2)", "description": "Base salary amount in currency units (e.g. 75000.00)."},
			"skills": {"type": "TEXT", "description": "Comma-separated list of technical and professional skills."},
			"user_id": {"type": "VARCHAR(140)", "description": "Linked system user account email/username."},
			"office_location": {"type": "VARCHAR(140)", "description": "Assigned office location name (links to tabOffice Location)."},
		},
	},
	"tabDepartment": {
		"table_name": "tabDepartment",
		"description": "Organizational department master definitions and hierarchy.",
		"row_represents": "One organizational department or business division.",
		"primary_key": "name",
		"columns": {
			"name": {"type": "VARCHAR(140)", "description": "Department ID / Name (e.g. 'Engineering', 'Finance').", "is_primary_key": True},
			"department_name": {"type": "VARCHAR(140)", "description": "Display name of the department."},
			"department_head": {"type": "VARCHAR(140)", "description": "Employee ID or name of the department head."},
			"parent_department": {"type": "VARCHAR(140)", "description": "Parent department for organizational tree hierarchy."},
			"cost_center": {"type": "VARCHAR(140)", "description": "Financial cost center accounting code."},
		},
	},
	"tabLeave Application": {
		"table_name": "tabLeave Application",
		"description": "Employee time off requests, dates, reasons, and approval workflow states.",
		"row_represents": "A single leave request filed by an employee.",
		"primary_key": "name",
		"foreign_keys": {"employee": "tabEmployee.name"},
		"columns": {
			"name": {"type": "VARCHAR(140)", "description": "Unique document identifier.", "is_primary_key": True},
			"employee": {"type": "VARCHAR(140)", "description": "Foreign key linking to tabEmployee.name (e.g. 'EMP-0009'). Join with tabEmployee to get full_name.", "references": "tabEmployee.name"},
			"leave_type": {"type": "VARCHAR(140)", "description": "Requested leave policy category.", "enum": ["Annual Leave", "Casual Leave", "Sick Leave", "Earned Leave"]},
			"from_date": {"type": "DATE", "description": "Start date of leave inclusive in YYYY-MM-DD format."},
			"to_date": {"type": "DATE", "description": "End date of leave inclusive in YYYY-MM-DD format."},
			"total_days": {"type": "DECIMAL(5,1)", "description": "Number of working days requested (e.g. 1.0, 2.0)."},
			"reason": {"type": "TEXT", "description": "Employee's stated reason for time off."},
			"status": {"type": "VARCHAR(50)", "description": "Approval workflow status. An employee is only on leave if status is Approved.", "enum": ["Pending", "Approved", "Rejected"]},
			"approver": {"type": "VARCHAR(140)", "description": "Employee ID or user who approved or rejected the request."},
		},
	},
	"tabLeave Type": {
		"table_name": "tabLeave Type",
		"description": "Master leave policy rules, annual quota allocations, and rollover rules.",
		"row_represents": "One category of leave policy entitlement.",
		"primary_key": "name",
		"columns": {
			"name": {"type": "VARCHAR(140)", "description": "Leave policy unique ID.", "is_primary_key": True},
			"leave_type_name": {"type": "VARCHAR(140)", "description": "Display name of leave type (e.g. 'Annual Leave', 'Casual Leave', 'Sick Leave')."},
			"max_days_per_year": {"type": "INT", "description": "Allocated quota of days per employee per year (e.g. 14, 10, 7)."},
			"carry_forward": {"type": "INT", "description": "1 if unused days roll over into next calendar year, 0 if they lapse.", "enum": [0, 1]},
		},
	},
	"tabSalary Slip": {
		"table_name": "tabSalary Slip",
		"description": "Monthly employee payroll statements, gross pay, deductions, and take-home disbursement.",
		"row_represents": "A single monthly salary slip for one employee.",
		"primary_key": "name",
		"foreign_keys": {"employee": "tabEmployee.name"},
		"columns": {
			"name": {"type": "VARCHAR(140)", "description": "Salary slip document ID (e.g. 'SAL-2026-09-0001').", "is_primary_key": True},
			"employee": {"type": "VARCHAR(140)", "description": "Foreign key referencing tabEmployee.name.", "references": "tabEmployee.name"},
			"salary_month": {"type": "VARCHAR(20)", "description": "Pay period month formatted as 'YYYY-MM' (e.g. '2026-09')."},
			"basic_pay": {"type": "DECIMAL(18,2)", "description": "Base salary before allowances and deductions."},
			"hra": {"type": "DECIMAL(18,2)", "description": "House Rent Allowance component."},
			"gross_pay": {"type": "DECIMAL(18,2)", "description": "Total gross compensation (basic_pay + allowances)."},
			"leave_deduction": {"type": "DECIMAL(18,2)", "description": "Amount docked for unpaid leave or absence."},
			"net_pay": {"type": "DECIMAL(18,2)", "description": "Final take-home pay disbursed to employee."},
			"select": {"type": "VARCHAR(50)", "description": "Payment status. Always escape as `select` in SQL.", "enum": ["Draft", "Submitted", "Paid"]},
		},
	},
	"tabAttendance": {
		"table_name": "tabAttendance",
		"description": "Daily employee attendance tracking, shift timings, in/out timestamps, and working hours.",
		"row_represents": "The official daily attendance record for one employee on a specific date.",
		"primary_key": "name",
		"foreign_keys": {"employee": "tabEmployee.name"},
		"columns": {
			"name": {"type": "VARCHAR(140)", "description": "Attendance record unique ID (e.g. 'ATT-00052').", "is_primary_key": True},
			"employee": {"type": "VARCHAR(140)", "description": "Foreign key referencing tabEmployee.name (e.g. 'EMP-001').", "references": "tabEmployee.name"},
			"employee_name": {"type": "VARCHAR(140)", "description": "Cached employee full name for fast access without joins."},
			"attendance_date": {"type": "DATE", "description": "Date of attendance in YYYY-MM-DD format."},
			"status": {"type": "VARCHAR(50)", "description": "Official daily attendance verdict.", "enum": ["Present", "Absent", "Half Day", "On Leave"]},
			"shift": {"type": "VARCHAR(140)", "description": "Assigned shift type name (e.g. 'Day Shift', 'Night Shift')."},
			"in_time": {"type": "DATETIME", "description": "Timestamp of first clock-in of the day (YYYY-MM-DD HH:MM:SS)."},
			"out_time": {"type": "DATETIME", "description": "Timestamp of final clock-out of the day (YYYY-MM-DD HH:MM:SS)."},
			"working_hours": {"type": "DECIMAL(6,2)", "description": "Decimal hours worked during shift (e.g. 8.0, 4.5)."},
			"late_entry": {"type": "INT", "description": "1 if first_in exceeded shift grace period, 0 otherwise.", "enum": [0, 1]},
			"early_exit": {"type": "INT", "description": "1 if last_out was before shift departure cutoff, 0 otherwise.", "enum": [0, 1]},
			"remarks": {"type": "VARCHAR(255)", "description": "Shift calculation notes and audit trail."},
		},
	},
	"tabEmployee Checkin": {
		"table_name": "tabEmployee Checkin",
		"description": "Raw biometric and geofenced GPS punch transactions for clock-in and clock-out.",
		"row_represents": "An individual biometric or GPS punch event (IN or OUT).",
		"primary_key": "name",
		"foreign_keys": {"employee": "tabEmployee.name"},
		"columns": {
			"name": {"type": "VARCHAR(140)", "description": "Punch transaction ID (e.g. 'CHECKIN-000115').", "is_primary_key": True},
			"employee": {"type": "VARCHAR(140)", "description": "Foreign key referencing tabEmployee.name.", "references": "tabEmployee.name"},
			"time": {"type": "DATETIME", "description": "Timestamp of punch event in YYYY-MM-DD HH:MM:SS format."},
			"log_type": {"type": "VARCHAR(10)", "description": "Punch direction.", "enum": ["IN", "OUT"]},
			"device_id": {"type": "VARCHAR(140)", "description": "Device identifier (e.g. 'GPS Web Clock', 'Biometric Scanner')."},
			"latitude": {"type": "DECIMAL(12,8)", "description": "GPS latitude coordinate of clock-in/out."},
			"longitude": {"type": "DECIMAL(12,8)", "description": "GPS longitude coordinate of clock-in/out."},
			"distance_from_office": {"type": "DECIMAL(10,2)", "description": "Distance in meters from assigned office geofence."},
		},
	},
	"tabShift Type": {
		"table_name": "tabShift Type",
		"description": "Work shift timing configurations, auto-attendance rules, and hour thresholds.",
		"row_represents": "One defined work shift schedule and policy.",
		"primary_key": "name",
		"columns": {
			"name": {"type": "VARCHAR(140)", "description": "Shift type document ID.", "is_primary_key": True},
			"shift_name": {"type": "VARCHAR(140)", "description": "Shift name (e.g. 'Day Shift', 'Night Shift')."},
			"start_time": {"type": "TIME", "description": "Shift begin time (e.g. '09:00:00' or '22:00:00')."},
			"end_time": {"type": "TIME", "description": "Shift end time (e.g. '17:00:00' or '06:00:00')."},
			"late_entry_grace_period": {"type": "INT", "description": "Grace period in minutes before marking late entry (standard: 30 minutes)."},
			"working_hours_threshold_for_half_day": {"type": "DECIMAL(5,2)", "description": "Minimum hours required for Half Day status (e.g. 4.0)."},
			"working_hours_threshold_for_present": {"type": "DECIMAL(5,2)", "description": "Minimum hours required for Full Day Present status (e.g. 8.0)."},
		},
	},
	"tabPayroll": {
		"table_name": "tabPayroll",
		"description": "Batch payroll processing runs and disbursements across the organization.",
		"row_represents": "A single periodic payroll processing run.",
		"primary_key": "name",
		"columns": {
			"name": {"type": "VARCHAR(140)", "description": "Payroll batch ID (e.g. 'PAY-2026-09-001').", "is_primary_key": True},
			"payroll_title": {"type": "VARCHAR(140)", "description": "Descriptive title (e.g. 'September 2026 Monthly Payroll')."},
			"start_date": {"type": "DATE", "description": "Pay period start date in YYYY-MM-DD format."},
			"end_date": {"type": "DATE", "description": "Pay period end date in YYYY-MM-DD format."},
			"total_amount": {"type": "DECIMAL(18,2)", "description": "Total net currency disbursed across all employees."},
			"status": {"type": "VARCHAR(50)", "description": "Payroll run lifecycle state.", "enum": ["Draft", "Processing", "Completed"]},
		},
	},
}


# =====================================================================
# 2. SCHEMA & WHITELIST CONFIGURATIONS
# =====================================================================

ALLOWED_TABLES = {
	"tabEmployee": {
		"name", "creation", "modified", "modified_by", "owner", "docstatus",
		"full_name", "email", "phone", "department", "designation",
		"date_of_joining", "reporting_manager", "employment_type", "status",
		"basic_salary", "skills", "profile_image", "user_id", "naming_series",
		"office_location"
	},
	"tabDepartment": {
		"name", "creation", "modified", "modified_by", "owner", "docstatus",
		"department_name", "department_head", "parent_department", "cost_center"
	},
	"tabLeave Application": {
		"name", "creation", "modified", "modified_by", "owner", "docstatus",
		"workflow_state", "employee", "leave_type", "from_date", "to_date",
		"total_days", "reason", "status", "approver"
	},
	"tabLeave Type": {
		"name", "creation", "modified", "modified_by", "owner", "docstatus",
		"leave_type_name", "max_days_per_year", "carry_forward"
	},
	"tabSalary Slip": {
		"name", "creation", "modified", "modified_by", "owner", "docstatus",
		"employee", "salary_month", "basic_pay", "hra", "allowances",
		"deductions", "gross_pay", "leave_deduction", "net_pay", "select"
	},
	"tabSalary Slip Allowance": {
		"name", "creation", "modified", "modified_by", "owner", "docstatus",
		"parent", "parenttype", "parentfield", "allowance_name", "amount", "idx"
	},
	"tabSalary Slip Deduction": {
		"name", "creation", "modified", "modified_by", "owner", "docstatus",
		"parent", "parenttype", "parentfield", "deduction_name", "amount", "idx"
	},
	"tabAttendance": {
		"name", "creation", "modified", "modified_by", "owner", "docstatus",
		"employee", "employee_name", "attendance_date", "status", "shift",
		"in_time", "out_time", "working_hours", "late_entry", "early_exit",
		"leave_type", "leave_application", "remarks"
	},
	"tabShift Type": {
		"name", "creation", "modified", "modified_by", "owner", "docstatus",
		"shift_name", "start_time", "end_time", "enable_auto_attendance",
		"late_entry_grace_period", "early_exit_grace_period",
		"working_hours_threshold_for_half_day", "working_hours_threshold_for_absent",
		"working_hours_threshold_for_present", "begin_check_in_before_shift_start_time",
		"allow_check_out_after_shift_end_time", "process_attendance_after",
		"last_sync_of_checkin", "description"
	},
	"tabShift Assignment": {
		"name", "creation", "modified", "modified_by", "owner", "docstatus",
		"employee", "employee_name", "shift_type", "start_date", "end_date", "status"
	},
	"tabEmployee Checkin": {
		"name", "creation", "modified", "modified_by", "owner", "docstatus",
		"employee", "employee_name", "time", "log_type", "shift",
		"shift_start", "shift_end", "skip_auto_attendance", "attendance", "device_id",
		"attendance_source", "latitude", "longitude", "accuracy",
		"distance_from_office", "office_location"
	},
	"tabOffice Location": {
		"name", "creation", "modified", "modified_by", "owner", "docstatus",
		"office_name", "latitude", "longitude", "allowed_radius", "max_accuracy",
		"is_active", "address"
	},
	"tabPayroll": {
		"name", "creation", "modified", "modified_by", "owner", "docstatus",
		"payroll_title", "start_date", "end_date", "total_amount", "status"
	},
}

# Tables that regular Employees are completely prohibited from querying
EMPLOYEE_PROHIBITED_TABLES = {"tabPayroll"}

# Dangerous SQL function names that could leak info, cause DoS, or access the OS
DANGEROUS_FUNCTIONS = {
	"load_file", "benchmark", "sleep", "sys_eval", "sys_exec", "version",
	"user", "system_user", "session_user", "current_user", "schema",
	"database", "connection_id", "get_lock", "release_lock"
}

MAX_SERVER_LIMIT = 50
DEFAULT_SERVER_LIMIT = 20


# =====================================================================
# 3. CUSTOM EXCEPTIONS
# =====================================================================

class SQLValidationError(Exception):
	"""Base error for SQL validation failures."""
	def __init__(self, message, code="SQL_VALIDATION_ERROR", status_code=400):
		super().__init__(message)
		self.message = message
		self.code = code
		self.status_code = status_code

class JSONParseError(SQLValidationError):
	def __init__(self, message):
		super().__init__(message, code="JSON_PARSE_ERROR", status_code=400)

class ASTValidationError(SQLValidationError):
	def __init__(self, message):
		super().__init__(message, code="AST_VALIDATION_ERROR", status_code=400)

class SecurityViolationError(SQLValidationError):
	def __init__(self, message):
		super().__init__(message, code="SECURITY_VIOLATION", status_code=403)

class RBACViolationError(SQLValidationError):
	def __init__(self, message, status_code=403):
		super().__init__(message, code="RBAC_VIOLATION", status_code=status_code)



# =====================================================================
# 4. PIPELINE STAGE FUNCTIONS
# =====================================================================

def parse_llm_json(raw_input):
	"""
	Stage 1: Parse JSON
	Cleans LLM markdown fencing (```json ... ```) and safely deserializes JSON.
	"""
	if isinstance(raw_input, dict):
		return raw_input

	if not isinstance(raw_input, str):
		raise JSONParseError(f"Expected string or dict input, received: {type(raw_input).__name__}")

	cleaned = raw_input.strip()

	# Strip markdown codeblocks
	if cleaned.startswith("```"):
		lines = cleaned.splitlines()
		if lines and lines[0].startswith("```"):
			lines = lines[1:]
		if lines and lines[-1].strip() == "```":
			lines = lines[:-1]
		cleaned = "\n".join(lines).strip()

	# Also handle embedded JSON within text if needed
	if not cleaned.startswith("{"):
		start_idx = cleaned.find("{")
		end_idx = cleaned.rfind("}")
		if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
			cleaned = cleaned[start_idx:end_idx + 1]

	try:
		data = json.loads(cleaned)
		if not isinstance(data, dict):
			raise JSONParseError("LLM JSON root must be a dictionary object.")
		return data
	except json.JSONDecodeError as e:
		raise JSONParseError(f"Failed to parse LLM response as JSON: {str(e)}")


def check_status(payload):
	"""
	Stage 2: Check status == "sql"
	Routes non-SQL responses (clarification/error) or extracts SQL string.
	"""
	status = payload.get("status")
	if not status:
		raise ASTValidationError("Missing 'status' field in LLM response JSON.")

	if status != "sql":
		# Non-SQL response (e.g. clarification, greeting, error message)
		message = payload.get("message") or payload.get("explanation") or "No query required."
		return {
			"is_sql": False,
			"status": status,
			"message": message,
			"sql": None
		}

	sql = payload.get("sql")
	if not sql or not isinstance(sql, str) or not sql.strip():
		raise ASTValidationError("LLM JSON status is 'sql' but 'sql' query field is missing or empty.")

	return {
		"is_sql": True,
		"status": "sql",
		"message": payload.get("explanation") or "",
		"sql": sql.strip()
	}


def validate_sql_parser_ast(sql_query):
	"""
	Stage 3: Validate SQL Parser / AST
	Uses sqlglot to parse the query against MySQL/MariaDB dialect.
	Enforces exactly ONE query statement (blocking multi-statement injection).
	"""
	# Check for non-printable or suspicious characters
	if "\x00" in sql_query:
		raise SecurityViolationError("Null byte detected in SQL query.")

	try:
		statements = sqlglot.parse(sql_query, read="mysql")
	except Exception as e:
		raise ASTValidationError(f"SQL Syntax / AST Parse Error: {str(e)}")

	if not statements:
		raise ASTValidationError("No valid SQL statement found in query string.")

	if len(statements) > 1:
		raise SecurityViolationError(f"Multi-statement queries are strictly prohibited (found {len(statements)} statements).")

	ast = statements[0]
	if ast is None:
		raise ASTValidationError("Unable to generate AST for the provided query.")

	return ast


def validate_select_only(ast):
	"""
	Stage 4: Validate SELECT-only
	Ensures root expression is Select / Union and contains zero mutating expressions,
	DDL operations, into outfile, or dangerous functions.
	"""
	# Root MUST be a Select or Union of Selects
	if not isinstance(ast, (exp.Select, exp.Union)):
		raise SecurityViolationError(f"Only SELECT queries are permitted. Statement type '{type(ast).__name__}' is blocked.")

	# Check for forbidden statement / expression types anywhere in the AST
	forbidden_ast_nodes = (
		exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter, exp.Create,
		exp.Command, exp.Into, exp.Pragma, exp.TruncateTable, exp.Set,
		exp.Transaction, exp.Commit, exp.Rollback
	)
	for node in ast.find_all(forbidden_ast_nodes):
		raise SecurityViolationError(f"Mutating or administrative SQL operation '{type(node).__name__}' is forbidden.")

	# Check for dangerous functions
	for func in ast.find_all(exp.Anonymous, exp.Func):
		fname = func.name.lower() if hasattr(func, "name") and func.name else ""
		if not fname and hasattr(func, "key"):
			fname = str(func.key).lower()
		if fname in DANGEROUS_FUNCTIONS:
			raise SecurityViolationError(f"SQL function '{fname}' is forbidden for security reasons.")

	return ast


def validate_tables(ast):
	"""
	Stage 5: Validate tables
	Extracts all exp.Table nodes from the AST and checks against ALLOWED_TABLES.
	Blocks system tables (tabUser, information_schema, mysql, etc.).
	"""
	tables_found = set()
	for table_node in ast.find_all(exp.Table):
		# Clean table name: strip backticks, catalog/db qualifiers
		tbl_name = table_node.name.strip("` \t\r\n")
		# If table has a db prefix like `hospital.localhost`.`tabEmployee`
		if table_node.db:
			db_prefix = table_node.db.strip("` \t\r\n").lower()
			if db_prefix in ["mysql", "information_schema", "performance_schema", "sys"]:
				raise SecurityViolationError(f"Access to database schema '{db_prefix}' is strictly prohibited.")
		tables_found.add(tbl_name)

	if not tables_found:
		raise ASTValidationError("Query must target at least one database table.")

	for tbl in tables_found:
		if tbl not in ALLOWED_TABLES:
			raise SecurityViolationError(f"Table '{tbl}' is not permitted or does not exist in the allowed schema.")

	return list(tables_found)


def validate_columns(ast):
	"""
	Stage 6: Validate columns
	Extracts all exp.Column nodes from the AST and verifies they are permitted
	fields in the queried tables. Blocks hidden sensitive system columns.
	"""
	# Map table names to their allowed columns
	tables_in_query = {t.name.strip("` \t\r\n") for t in ast.find_all(exp.Table)}
	all_allowed_columns = set()
	for tbl in tables_in_query:
		if tbl in ALLOWED_TABLES:
			all_allowed_columns.update(ALLOWED_TABLES[tbl])

	# Standard SQL columns / aliases that are always safe
	common_allowed = {"count", "sum", "avg", "min", "max", "round", "*", "1"}

	for col_node in ast.find_all(exp.Column):
		col_name = col_node.name.strip("` \t\r\n")
		if not col_name:
			continue

		# If column has explicit table reference, check specifically
		if col_node.table:
			tbl_ref = col_node.table.strip("` \t\r\n")
			# Check if tbl_ref is a known table
			if tbl_ref in ALLOWED_TABLES and col_name not in ALLOWED_TABLES[tbl_ref]:
				# Could be an alias or wildcard
				if col_name not in common_allowed:
					raise ASTValidationError(f"Column '{col_name}' does not exist on table '{tbl_ref}'.")
		else:
			# Check if column belongs to any table in query
			if col_name not in all_allowed_columns and col_name.lower() not in common_allowed:
				# Also check if it's an alias defined in SELECT
				select_aliases = {
					s.alias.strip("` \t\r\n") for s in ast.find_all(exp.Alias) if hasattr(s, "alias") and s.alias
				}
				if col_name not in select_aliases:
					# To be safe, raise if column is totally unrecognizable
					raise ASTValidationError(f"Column '{col_name}' is not recognized in the queried schema.")

	return True


def enforce_rbac(ast, user=None, role=None, linked_emp=None):
	"""
	Stage 7: Enforce RBAC Programmatically
	Never trusts the LLM for access control.
	For regular Employees:
	- Blocks access to prohibited tables (e.g. tabPayroll)
	- Programmatically injects AST WHERE conditions:
	  - tabEmployee: name = '<emp_id>'
	  - tabSalary Slip: employee = '<emp_id>'
	  - tabLeave Application: (employee = '<emp_id>' OR approver = '<emp_id>')
	  - tabAttendance: employee = '<emp_id>'
	  - tabSalary Slip Allowance / Deduction: parent IN (SELECT name FROM `tabSalary Slip` WHERE employee = '<emp_id>')
	"""
	if not user:
		user = frappe.session.user if hasattr(frappe, "session") else "Guest"

	if not role:
		from employee_management_system.employee_management_system.api import _get_user_app_role
		role = _get_user_app_role(user)

	if role == "Guest" or not user or user == "Guest":
		raise RBACViolationError("Authentication required to execute queries.", status_code=401)

	# Administrator and HR have global read permissions across permitted tables
	if role in ["Administrator", "HR"]:
		return ast

	# Employee Role: Strict Self-Scoping & Data Isolation
	if role == "Employee":
		if not linked_emp:
			from employee_management_system.employee_management_system.api import _get_linked_employee
			linked_emp = _get_linked_employee(user)

		emp_id = linked_emp.get("name") if linked_emp else None
		if not emp_id:
			raise RBACViolationError("No active Employee record is linked to your user account. Access denied.")

		# Check for prohibited tables for Employee role
		tables_in_query = {t.name.strip("` \t\r\n") for t in ast.find_all(exp.Table)}
		forbidden_hits = tables_in_query.intersection(EMPLOYEE_PROHIBITED_TABLES)
		if forbidden_hits:
			raise RBACViolationError(f"Role 'Employee' is not permitted to access table(s): {', '.join(forbidden_hits)}.")

		# Programmatically inject ownership conditions into AST
		if "tabEmployee" in tables_in_query:
			emp_filter = exp.EQ(
				this=exp.column("name", table="tabEmployee"),
				expression=exp.Literal.string(emp_id)
			)
			ast = ast.where(emp_filter)

		if "tabSalary Slip" in tables_in_query:
			slip_filter = exp.EQ(
				this=exp.column("employee", table="tabSalary Slip"),
				expression=exp.Literal.string(emp_id)
			)
			ast = ast.where(slip_filter)

		if "tabLeave Application" in tables_in_query:
			leave_filter = exp.Or(
				this=exp.EQ(this=exp.column("employee", table="tabLeave Application"), expression=exp.Literal.string(emp_id)),
				expression=exp.EQ(this=exp.column("approver", table="tabLeave Application"), expression=exp.Literal.string(emp_id))
			)
			ast = ast.where(leave_filter)

		if "tabAttendance" in tables_in_query:
			att_filter = exp.EQ(
				this=exp.column("employee", table="tabAttendance"),
				expression=exp.Literal.string(emp_id)
			)
			ast = ast.where(att_filter)

		if "tabShift Assignment" in tables_in_query:
			sa_filter = exp.EQ(
				this=exp.column("employee", table="tabShift Assignment"),
				expression=exp.Literal.string(emp_id)
			)
			ast = ast.where(sa_filter)

		if "tabEmployee Checkin" in tables_in_query:
			ec_filter = exp.EQ(
				this=exp.column("employee", table="tabEmployee Checkin"),
				expression=exp.Literal.string(emp_id)
			)
			ast = ast.where(ec_filter)

		if "tabSalary Slip Allowance" in tables_in_query and "tabSalary Slip" not in tables_in_query:
			subq = sqlglot.parse_one(f"SELECT name FROM `tabSalary Slip` WHERE employee = '{emp_id}'", read="mysql")
			allowance_filter = exp.In(
				this=exp.column("parent", table="tabSalary Slip Allowance"),
				query=subq
			)
			ast = ast.where(allowance_filter)

		if "tabSalary Slip Deduction" in tables_in_query and "tabSalary Slip" not in tables_in_query:
			subq = sqlglot.parse_one(f"SELECT name FROM `tabSalary Slip` WHERE employee = '{emp_id}'", read="mysql")
			deduction_filter = exp.In(
				this=exp.column("parent", table="tabSalary Slip Deduction"),
				query=subq
			)
			ast = ast.where(deduction_filter)

	return ast


def add_server_side_limit(ast, max_limit=MAX_SERVER_LIMIT):
	"""
	Stage 8: Add server-side LIMIT
	If query has no LIMIT, injects LIMIT DEFAULT_SERVER_LIMIT.
	If query has a LIMIT > max_limit, clamps it down to max_limit.
	"""
	limit_node = ast.args.get("limit")

	if not limit_node:
		# No limit provided by LLM: inject default server limit
		ast = ast.limit(DEFAULT_SERVER_LIMIT)
	else:
		try:
			val = int(limit_node.expression.this)
			if val > max_limit or val <= 0:
				ast = ast.limit(max_limit)
		except (ValueError, AttributeError):
			ast = ast.limit(max_limit)

	return ast


def execute_mariadb(ast):
	"""
	Stage 9: Execute MariaDB
	Compiles the fully validated, RBAC-enforced, and limited AST to MariaDB SQL,
	and executes safely using frappe.db.sql(..., as_dict=True).
	"""
	final_sql = ast.sql(dialect="mysql")

	try:
		rows = frappe.db.sql(final_sql, as_dict=True)
		columns = list(rows[0].keys()) if rows else []
		return {
			"executed_sql": final_sql,
			"rows": rows,
			"columns": columns,
			"row_count": len(rows),
		}
	except Exception as e:
		raise SQLValidationError(f"Database execution error: {str(e)}")


def format_markdown_table(executed_sql, rows, explanation=None):
	"""
	Stage 10: Format Output
	Constructs a clean Markdown response with a fenced SQL code block
	and a formatted Markdown table for direct UI consumption.
	"""
	blocks = []

	if explanation:
		blocks.append(f"**{explanation}**\n")

	clean_sql = executed_sql.strip().rstrip(";") + ";"
	blocks.append(f"```sql\n{clean_sql}\n```")

	if rows:
		headers = list(rows[0].keys())
		hdr_line = "| " + " | ".join(headers) + " |"
		sep_line = "| " + " | ".join(["---"] * len(headers)) + " |"
		data_lines = []
		for r in rows:
			vals = []
			for h in headers:
				v = r.get(h)
				if v is None:
					vals.append("-")
				elif isinstance(v, (int, float)):
					if any(k in h.lower() for k in ["salary", "pay", "gross", "net", "amount"]):
						vals.append(f"${v:,.2f}" if isinstance(v, float) else f"${v:,}")
					else:
						vals.append(str(v))
				else:
					vals.append(str(v).replace("|", "\\|").replace("\n", " "))
			data_lines.append("| " + " | ".join(vals) + " |")

		table_md = hdr_line + "\n" + sep_line + "\n" + "\n".join(data_lines)
		if len(rows) >= MAX_SERVER_LIMIT:
			table_md += f"\n\n*Displaying maximum {len(rows)} records.*"
		blocks.append(table_md)
	else:
		blocks.append("*0 matching records found.*")

	return "\n\n".join(blocks)


# =====================================================================
# 5. THREE SECURITY PILLARS & FULL PIPELINE
# =====================================================================

def ast_check(sql_query):
	"""
	Pillar 1: AST Check
	- Parses SQL query into AST using sqlglot (MySQL/MariaDB dialect)
	- Validates single-statement constraint
	- Validates SELECT-only operations and blocks dangerous functions
	- Validates allowed tables against DocType whitelist
	- Validates allowed columns against schema whitelist
	Returns: (ast, tables_found)
	"""
	ast = validate_sql_parser_ast(sql_query)
	ast = validate_select_only(ast)
	tables_found = validate_tables(ast)
	validate_columns(ast)
	return ast, tables_found


def rbac_filter(ast, user=None, role=None, linked_emp=None):
	"""
	Pillar 2: RBAC Filter
	- Programmatically inspects AST and injects WHERE filters based on role
	- Restricts regular Employee users to their own linked records
	- Prohibits horizontal escalation and unauthorized access to payroll
	"""
	return enforce_rbac(ast, user=user, role=role, linked_emp=linked_emp)


def limit_filter(ast, max_limit=MAX_SERVER_LIMIT):
	"""
	Pillar 3: LIMIT
	- Injects default server limit (20) when absent
	- Clamps excessive limits to maximum allowed ceiling (50)
	"""
	return add_server_side_limit(ast, max_limit=max_limit)


def run_sql_guard(sql_query, user=None, role=None, linked_emp=None, max_limit=MAX_SERVER_LIMIT):
	"""
	Executes the 3 security pillars of sql_guard.py:
	AST Check -> RBAC Filter -> LIMIT -> MariaDB execution.
	"""
	# 1. AST Check
	ast, tables_found = ast_check(sql_query)

	# 2. RBAC Filter
	ast = rbac_filter(ast, user=user, role=role, linked_emp=linked_emp)

	# 3. LIMIT
	ast = limit_filter(ast, max_limit=max_limit)

	# 4. MariaDB Execution
	exec_result = execute_mariadb(ast)
	exec_result["tables"] = tables_found
	return exec_result


def process_llm_pipeline(raw_llm_input, user=None, role=None, linked_emp=None, max_limit=MAX_SERVER_LIMIT):
	"""
	Executes the complete validation pipeline:
	LLM JSON -> Parse JSON -> Check status == sql -> AST Check
	         -> RBAC Filter -> LIMIT -> Execute MariaDB -> Format Output
	"""
	# 1. Parse JSON
	payload = parse_llm_json(raw_llm_input)

	# 2. Check status == "sql"
	status_info = check_status(payload)
	if not status_info["is_sql"]:
		return {
			"success": True,
			"is_sql": False,
			"status": status_info["status"],
			"message": status_info["message"],
			"markdown": status_info["message"],
			"executed_sql": None,
			"data": [],
			"columns": [],
			"row_count": 0,
			"tables": []
		}

	sql_query = status_info["sql"]
	explanation = status_info["message"]

	# Run 3 Pillars & MariaDB Execution
	exec_result = run_sql_guard(sql_query, user=user, role=role, linked_emp=linked_emp, max_limit=max_limit)

	# Format Output
	markdown_resp = format_markdown_table(
		exec_result["executed_sql"],
		exec_result["rows"],
		explanation=explanation
	)

	return {
		"success": True,
		"is_sql": True,
		"status": "sql",
		"message": explanation,
		"markdown": markdown_resp,
		"executed_sql": exec_result["executed_sql"],
		"data": exec_result["rows"],
		"columns": exec_result["columns"],
		"row_count": exec_result["row_count"],
		"tables": exec_result.get("tables", [])
	}
