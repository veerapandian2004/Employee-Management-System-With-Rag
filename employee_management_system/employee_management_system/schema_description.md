# EMS Database Schema Reference & Data Dictionary

This document provides a comprehensive reference for the Employee Management System (EMS) MariaDB database. It describes what each table and row represents, every column's data type, purpose, valid enum values, primary/foreign key relationships, and query patterns to ensure accurate LLM SQL generation.

---

## 1. Core Tables Overview

| Table Name | Entity / Domain | Primary Key | Row Represents |
| :--- | :--- | :--- | :--- |
| `tabEmployee` | Workforce Directory | `name` (`EMP-xxx`) | One unique employee in the company |
| `tabDepartment` | Org Hierarchy | `name` | One business department or cost center |
| `tabLeave Application` | Time Off Management | `name` | One leave application request filed by an employee |
| `tabLeave Type` | Leave Policy Master | `name` | One category of leave entitlement and annual quota |
| `tabSalary Slip` | Payroll & Compensation | `name` (`SAL-xxx`) | One monthly salary payslip for one employee |
| `tabSalary Slip Allowance` | Child Table | `name` | An individual recurring allowance line item |
| `tabSalary Slip Deduction` | Child Table | `name` | An individual recurring deduction line item |
| `tabAttendance` | Daily Attendance | `name` (`ATT-xxx`) | One employee's official attendance for one calendar date |
| `tabEmployee Checkin` | Biometric & GPS Punches | `name` (`CHECKIN-xxx`)| An individual biometric or geofenced clock-in/out punch |
| `tabShift Type` | Shift Configurations | `name` | Operating shift timing definitions, grace periods, and weekly offs |
| `tabShift Assignment` | Staff Scheduling | `name` | Binds an employee to a shift schedule for a date range |
| `tabOffice Location` | Geofence Coordinates | `name` | An authorized corporate office site with permitted radius |
| `tabHoliday` | Company Holiday Calendar | `name` | An official public or company holiday date |
| `tabPayroll` | Payroll Processing Runs | `name` (`PAY-xxx`) | A periodic batch payroll run across departments |
| `tabChat Session` | AI Chat Persistence | `name` (`CS-xxx`) | A conversation session thread with user and message history |

---

## 2. Table & Column Definitions

### 2.1 `tabEmployee`
- **Description**: Workforce master table storing individual employee profiles, employment terms, and compensation.
- **Row Represents**: One unique employee in the organization.
- **Primary Key**: `name` (e.g. `'EMP-001'`, `'EMP-0008'`). Used as foreign key across attendance, leaves, and salary slips.

| Column | Data Type | Constraints / Enums | Description |
| :--- | :--- | :--- | :--- |
| `name` | `VARCHAR(140)` | Primary Key | Unique Employee ID (e.g., `'EMP-001'`). |
| `full_name` | `VARCHAR(140)` | Mandatory | Full legal name of the employee (e.g., `'Sarah Jenkins'`, `'David Chen'`). |
| `email` | `VARCHAR(140)` | Mandatory, Unique | Work email address used for login and notifications. |
| `phone` | `VARCHAR(140)` | Optional | Telephone contact number. |
| `department` | `VARCHAR(140)` | Links to `tabDepartment` | Department name (e.g., `'Engineering'`, `'Executive & HR'`, `'Finance'`). |
| `designation` | `VARCHAR(140)` | Optional | Job title / position (e.g., `'Chief Technology Officer'`, `'Senior Software Engineer'`). |
| `date_of_joining` | `DATE` | `YYYY-MM-DD` | Official start date of employment. |
| `reporting_manager`| `VARCHAR(140)` | Links to `tabEmployee` | Employee ID or supervisor name. |
| `employment_type` | `VARCHAR(50)` | `'Full-Time'`, `'Part-Time'`, `'Contract'`, `'Intern'` | Contract classification. |
| `status` | `VARCHAR(50)` | `'Active'`, `'On Leave'`, `'Suspended'`, `'Terminated'` | Current lifecycle status. Active staff have `status = 'Active'`. Note: On-leave status is dynamically reconciled with approved leave applications covering today (`from_date <= today <= to_date`) or today's attendance; expired `'On Leave'` database records are automatically self-healed back to `'Active'` via `get_employees`. |
| `basic_salary` | `DECIMAL(18,2)`| Numeric | Base monthly or annual compensation (e.g., `75000.00`, `95000.00`). |
| `skills` | `TEXT` | CSV | Technical and professional competencies. |
| `user_id` | `VARCHAR(140)` | Links to `tabUser` | Associated Frappe login email. |
| `office_location` | `VARCHAR(140)` | Links to `tabOffice Location` | Assigned physical office (e.g., `'Main Office'`). |

---

### 2.2 `tabDepartment`
- **Description**: Organizational department master definitions and hierarchy.
- **Row Represents**: One distinct business department or cost center.
- **Primary Key**: `name` (e.g., `'Engineering'`, `'Human Resources'`, `'Finance'`).

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `name` | `VARCHAR(140)` | Primary Key | Unique department ID / identifier. |
| `department_name` | `VARCHAR(140)` | Mandatory | Display name of the department. |
| `department_head` | `VARCHAR(140)` | Links to `tabEmployee` | Employee ID or name of the department head. |
| `parent_department` | `VARCHAR(140)`| Links to `tabDepartment` | Parent department for org hierarchy. |
| `cost_center` | `VARCHAR(140)` | Optional | Financial cost center code. |

---

### 2.3 `tabLeave Application`
- **Description**: Employee time-off requests, dates, reasons, and approval/cancellation lifecycle states.
- **Row Represents**: A single leave request filed by an employee.
- **Primary Key**: `name`
- **Foreign Keys**: `employee` references `tabEmployee.name`.

| Column | Data Type | Constraints / Enums | Description |
| :--- | :--- | :--- | :--- |
| `name` | `VARCHAR(140)` | Primary Key | Document ID. |
| `employee` | `VARCHAR(140)` | Links to `tabEmployee.name` | Employee ID (e.g. `'EMP-001'`). Join with `tabEmployee` on `tabEmployee.name = tabLeave Application.employee` to get `full_name`. |
| `leave_type` | `VARCHAR(140)` | Links to `tabLeave Type` | Category of leave (e.g., `'Annual Leave'`, `'Casual Leave'`). |
| `from_date` | `DATE` | `YYYY-MM-DD` | Start date inclusive. |
| `to_date` | `DATE` | `YYYY-MM-DD` | End date inclusive. |
| `total_days` | `DECIMAL(5,1)` | Float | Total working days requested (e.g., `1.0`, `3.0`). |
| `reason` | `TEXT` | Optional | Reason provided by applicant. |
| `status` | `VARCHAR(50)` | `'Pending'`, `'Approved'`, `'Rejected'`, `'Cancelled'` | Workflow state. **An employee is only on leave if `status = 'Approved'`**. |
| `approver` | `VARCHAR(140)` | Optional | User or Employee who approved/rejected the request. |
| `cancellation_reason`| `TEXT` | Optional | Audit reason supplied when leave is cancelled. |
| `cancelled_by` | `VARCHAR(140)` | Links to `tabUser` | User who executed the cancellation. |
| `cancelled_at` | `DATETIME` | `YYYY-MM-DD HH:MM:SS` | Timestamp when cancellation was finalized. |

---

### 2.4 `tabLeave Type`
- **Description**: Master leave policy rules, annual quota allocations, and rollover rules.
- **Row Represents**: One category of leave entitlement.
- **Primary Key**: `name` / `leave_type_name`

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `name` | `VARCHAR(140)` | Primary Key | Document ID. |
| `leave_type_name` | `VARCHAR(140)` | Unique | Display name of leave type (e.g., `'Annual Leave'`). |
| `max_days_per_year`| `INT` | Non-negative | Annual allocated quota in days per employee. `0` denotes unpaid leave / Loss of Pay. |
| `carry_forward` | `INT` | `0` or `1` | `1` if unused days roll over into next calendar year, `0` if they lapse. |

---

### 2.5 `tabSalary Slip`
- **Description**: Monthly employee payroll statements, gross pay, Loss of Pay deductions, net pay disbursement, and email dispatch status.
- **Row Represents**: A single monthly salary slip for one employee.
- **Primary Key**: `name` (e.g., `'SAL-2026-09-0001'`).
- **Foreign Keys**: `employee` references `tabEmployee.name`.

| Column | Data Type | Constraints / Enums | Description |
| :--- | :--- | :--- | :--- |
| `name` | `VARCHAR(140)` | Primary Key | Salary slip ID. |
| `employee` | `VARCHAR(140)` | Links to `tabEmployee.name` | Foreign key referencing employee. |
| `salary_month` | `VARCHAR(20)` | `'YYYY-MM'` | Pay period month (e.g., `'2026-09'`). |
| `basic_pay` | `DECIMAL(18,2)`| Numeric | Base pay amount before allowances or deductions. |
| `hra` | `DECIMAL(18,2)`| Numeric | House Rent Allowance (typically 40% of basic). |
| `gross_pay` | `DECIMAL(18,2)`| Numeric | Total pre-tax compensation (`basic_pay` + allowances). |
| `absent_days` | `DECIMAL(5,1)` | Float | Unworked absent days derived from `tabAttendance`. |
| `unpaid_leave_days`| `DECIMAL(5,1)`| Float | Unpaid leave days derived from `tabAttendance`. |
| `lop_days` | `DECIMAL(5,1)` | Float | Total Loss of Pay days (`absent_days + unpaid_leave_days`). |
| `lop_deduction` | `DECIMAL(18,2)`| Numeric | Automated Loss of Pay deduction ($(\text{basic\_pay}/\text{month\_days}) \times \text{lop\_days}$). |
| `leave_deduction` | `DECIMAL(18,2)`| Numeric | General leave deduction / LOP deduction. |
| `net_pay` | `DECIMAL(18,2)`| Numeric | Final take-home pay disbursed to the employee ($\text{gross} - \text{deductions} - \text{lop\_deduction}$). |
| `select` | `VARCHAR(50)` | `'Draft'`, `'Submitted'`, `'Paid'` | Payment status. **Always escape in SQL as `` `select` ``**. |
| `email_status` | `VARCHAR(50)` | `'Pending'`, `'Sent'`, `'Failed'` | Delivery status of salary slip PDF dispatch. |
| `email_sent_at` | `DATETIME` | `YYYY-MM-DD HH:MM:SS` | Timestamp when salary slip was emailed to employee. |

---

### 2.6 `tabAttendance`
- **Description**: Daily employee attendance tracking, shift timings, in/out timestamps, and working hours.
- **Row Represents**: The official daily attendance record for one employee on a specific date.
- **Primary Key**: `name` (e.g., `'ATT-00052'`).
- **Foreign Keys**: `employee` references `tabEmployee.name`.

| Column | Data Type | Constraints / Enums | Description |
| :--- | :--- | :--- | :--- |
| `name` | `VARCHAR(140)` | Primary Key | Attendance record ID. |
| `employee` | `VARCHAR(140)` | Links to `tabEmployee.name` | Employee ID (e.g., `'EMP-001'`). |
| `employee_name` | `VARCHAR(140)` | Cached String | Cached employee full name for fast access without joining. |
| `attendance_date` | `DATE` | `YYYY-MM-DD` | Date of attendance. |
| `status` | `VARCHAR(50)` | `'Present'`, `'Half Day'`, `'Absent'`, `'On Leave'`, `'Holiday'`, `'Weekly Off'` | Official daily attendance verdict governed by strict priority rules. |
| `shift` | `VARCHAR(140)` | Links to `tabShift Type` | Assigned shift (e.g., `'Day Shift'`). |
| `in_time` | `DATETIME` | `YYYY-MM-DD HH:MM:SS` | Timestamp of first clock-in of the day. |
| `out_time` | `DATETIME` | `YYYY-MM-DD HH:MM:SS` | Timestamp of final clock-out of the day. |
| `working_hours` | `DECIMAL(6,2)` | Float | Total hours worked during the shift. |
| `late_entry` | `INT` | `0` or `1` | `1` if first_in exceeded shift grace period (> 30 mins after shift start). Clock-in within 30 mins is `0`. |
| `early_exit` | `INT` | `0` or `1` | `1` if last_out was before shift departure cutoff. |
| `auto_clocked_out` | `INT` | `0` or `1` | `1` if automatically clocked out by the system. |
| `clock_out_reason` | `VARCHAR(140)` | String | Reason: `'Left Office Location'` or `'Shift Completed'`. |
| `auto_clock_out_time` | `DATETIME` | `YYYY-MM-DD HH:MM:SS` | Timestamp when auto clock-out occurred. |
| `leave_application`| `VARCHAR(140)` | Links to `tabLeave Application` | Associated leave application when status is `'On Leave'`. |
| `leave_type` | `VARCHAR(140)` | Links to `tabLeave Type` | Associated leave type. |
| `remarks` | `VARCHAR(255)` | String | Audit notes and shift details. |

---

### 2.7 `tabEmployee Checkin`
- **Description**: Raw biometric and geofenced GPS punch transactions for clock-in and clock-out.
- **Row Represents**: An individual biometric or GPS punch event (`IN` or `OUT`).
- **Primary Key**: `name` (e.g., `'CHECKIN-000115'`).
- **Foreign Keys**: `employee` references `tabEmployee.name`.

| Column | Data Type | Constraints / Enums | Description |
| :--- | :--- | :--- | :--- |
| `name` | `VARCHAR(140)` | Primary Key | Punch transaction ID. |
| `employee` | `VARCHAR(140)` | Links to `tabEmployee.name` | Employee ID. |
| `time` | `DATETIME` | `YYYY-MM-DD HH:MM:SS` | Server timestamp of punch event. |
| `log_type` | `VARCHAR(10)` | `'IN'`, `'OUT'` | Punch direction (`'IN'` for clock-in, `'OUT'` for clock-out). |
| `device_id` | `VARCHAR(140)` | String | Origin device (e.g., `'GPS Web Clock'`). |
| `shift` | `VARCHAR(140)` | Links to `tabShift Type` | Operating shift associated with punch session (e.g., `'Day Shift'`). |
| `shift_start` | `DATETIME` | `YYYY-MM-DD HH:MM:SS` | Scheduled shift start timestamp. |
| `shift_end` | `DATETIME` | `YYYY-MM-DD HH:MM:SS` | Scheduled shift end timestamp. |
| `latitude` | `DECIMAL(12,8)`| Float | GPS latitude. |
| `longitude` | `DECIMAL(12,8)`| Float | GPS longitude. |
| `accuracy` | `DECIMAL(10,2)`| Meters | GPS accuracy reading from browser device. |
| `distance_from_office` | `DECIMAL(10,2)`| Meters | Distance in meters from office center geofence. |
| `office_location` | `VARCHAR(140)` | Links to `tabOffice Location` | Assigned office geofence used for validation. |
| `is_auto_clock_out` | `INT` | `0` or `1` | `1` if punch was automatically generated by system. |
| `clock_out_reason` | `VARCHAR(140)` | String | `'Left Office Location'`, `'Shift Completed'`, or `'Auto Clock-Out'`. |

---

### 2.8 `tabShift Type`
- **Description**: Work shift timing configurations, weekly off days, auto-attendance rules, and hour thresholds.
- **Row Represents**: One defined work shift schedule and policy.
- **Primary Key**: `name` / `shift_name`.

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `name` | `VARCHAR(140)` | Primary Key | Name of shift (e.g., `'Day Shift'`, `'Night Shift'`). |
| `shift_name` | `VARCHAR(140)` | String | Descriptive shift label. |
| `start_time` | `TIME` | `HH:MM:SS` | Shift begin time (e.g., `'09:00:00'`). |
| `end_time` | `TIME` | `HH:MM:SS` | Shift end time (e.g., `'18:00:00'`). |
| `weekly_off_days` | `VARCHAR(140)` | CSV | Configured weekly rest days (e.g., `'Saturday, Sunday'`, `'Sunday'`). |
| `late_entry_grace_period` | `INT` | Minutes | Grace period in minutes for late arrival (standard: `30` mins; clock-in up to 30 mins after shift start is not late). |
| `early_exit_grace_period` | `INT` | Minutes | Grace period in minutes for early departure. |
| `working_hours_threshold_for_half_day` | `DECIMAL(5,2)` | Hours | Minimum hours required for Half Day status (e.g., `4.0`). |
| `working_hours_threshold_for_present` | `DECIMAL(5,2)` | Hours | Minimum hours required for Full Day Present status (e.g., `8.0`). |
| `is_active` | `INT` | `0` or `1` | Whether shift type is active. |

---

### 2.9 `tabShift Assignment`
- **Description**: Schedules employees to shifts for specific date ranges.
- **Row Represents**: Binds one employee to a shift schedule with active lifecycle status.
- **Primary Key**: `name`.

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `name` | `VARCHAR(140)` | Primary Key | Unique assignment ID. |
| `employee` | `VARCHAR(140)` | Links to `tabEmployee.name` | Target employee ID. |
| `shift_type` | `VARCHAR(140)` | Links to `tabShift Type.name` | Associated shift type. |
| `start_date` | `DATE` | `YYYY-MM-DD` | Start date of shift schedule. |
| `end_date` | `DATE` | `YYYY-MM-DD` | End date of shift schedule (optional). |
| `status` | `VARCHAR(50)` | `'Active'`, `'Inactive'` | Assignment status. |

---

### 2.10 `tabHoliday`
- **Description**: Company official holiday calendar master table.
- **Row Represents**: An official company holiday on a specific calendar date.
- **Primary Key**: `name`.

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `name` | `VARCHAR(140)` | Primary Key | Unique holiday ID. |
| `holiday_name` | `VARCHAR(140)` | Mandatory | Holiday title (e.g., `'New Year'`, `'Gandhi Jayanti'`). |
| `holiday_date` | `DATE` | `YYYY-MM-DD`, Mandatory | The calendar date of the holiday. |
| `description` | `TEXT` | Optional | Additional details or regional observance notes. |

---

### 2.11 `tabPayroll`
- **Description**: Periodic batch payroll runs, financial aggregates, and processing summaries.
- **Row Represents**: A batch payroll generation execution for an organization or department.
- **Primary Key**: `name` (e.g., `'PAY-2026-09-001'`).

| Column | Data Type | Constraints / Enums | Description |
| :--- | :--- | :--- | :--- |
| `name` | `VARCHAR(140)` | Primary Key | Batch payroll run identifier. |
| `payroll_title` | `VARCHAR(140)` | String | Descriptive cycle title (e.g., `'Payroll 2026-09 - Engineering'`). |
| `salary_month` | `VARCHAR(20)` | `'YYYY-MM'` | Target salary month. |
| `start_date` | `DATE` | `YYYY-MM-DD` | Cycle beginning date. |
| `end_date` | `DATE` | `YYYY-MM-DD` | Cycle ending date. |
| `department` | `VARCHAR(140)` | String | Filtered department or `'All'`. |
| `designation` | `VARCHAR(140)` | String | Filtered designation or `'All'`. |
| `total_employees` | `INT` | Non-negative | Count of eligible employees matching filters. |
| `successful_slips`| `INT` | Non-negative | Number of successfully processed/skipped slips. |
| `failed_slips` | `INT` | Non-negative | Number of slips that encountered errors. |
| `total_amount` | `DECIMAL(18,2)`| Currency | Total net currency disbursed across all generated slips. |
| `status` | `VARCHAR(50)` | `'Draft'`, `'Processing'`, `'Completed'`, `'Completed with Errors'`, `'Failed'` | Execution status. |
| `failure_details`| `TEXT` | Optional | Line-separated error traces for any failed slips. |

---

### 2.12 `tabChat Session`
- **Description**: Conversational history persistence for the AI Assistant.
- **Row Represents**: An ongoing or archived multi-turn chat session.
- **Primary Key**: `name` (e.g., `'CS-00001'`).

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `name` | `VARCHAR(140)` | Primary Key | Chat session ID. |
| `title` | `VARCHAR(255)` | String | Topic summary / initial user prompt preview. |
| `user_id` | `VARCHAR(140)` | Links to `tabUser` | User who initiated and owns the chat session. |
| `created_at` | `DATETIME` | `YYYY-MM-DD HH:MM:SS` | Timestamp when session was created. |
| `updated_at` | `DATETIME` | `YYYY-MM-DD HH:MM:SS` | Timestamp of latest message exchange. |
| `messages` | `LONGTEXT` | JSON | Serialized message list containing role, content, and metadata. |

---

## 3. High-Accuracy SQL Query Patterns

### Pattern 1: Today's Working Employees
Finds active staff members who are not currently on an approved leave:
```sql
SELECT name, full_name, designation, department, basic_salary, status 
FROM `tabEmployee` 
WHERE status = 'Active' 
  AND name NOT IN (
    SELECT employee 
    FROM `tabLeave Application` 
    WHERE status = 'Approved' 
      AND CURDATE() BETWEEN from_date AND to_date
  ) 
ORDER BY full_name ASC;
```

### Pattern 2: Today's Leave Employees (with Names)
Retrieves employees currently absent on approved leave today:
```sql
SELECT 
  la.name AS leave_id,
  la.employee,
  e.full_name AS employee_name,
  la.leave_type,
  la.from_date,
  la.to_date,
  la.total_days,
  la.status
FROM `tabLeave Application` la
JOIN `tabEmployee` e ON la.employee = e.name
WHERE la.status = 'Approved'
  AND CURDATE() BETWEEN la.from_date AND la.to_date;
```

### Pattern 3: Today's Attendance Breakdown (Status Priority Aware)
Summary of daily workforce presence across statuses:
```sql
SELECT 
  status, 
  COUNT(*) AS employee_count 
FROM `tabAttendance` 
WHERE attendance_date = CURDATE() 
GROUP BY status 
ORDER BY FIELD(status, 'Holiday', 'Weekly Off', 'On Leave', 'Present', 'Half Day', 'Absent');
```

### Pattern 4: Loss of Pay & Absenteeism Analysis for Current Month
Identifies employees with unexcused absences or unpaid leaves impacting payroll:
```sql
SELECT 
  employee,
  employee_name,
  SUM(CASE WHEN status = 'Absent' THEN 1.0 WHEN status = 'Half Day' THEN 0.5 ELSE 0.0 END) AS total_absent_days,
  SUM(CASE WHEN status = 'On Leave' AND leave_type LIKE '%Unpaid%' THEN 1.0 ELSE 0.0 END) AS unpaid_leave_days
FROM `tabAttendance`
WHERE attendance_date BETWEEN DATE_FORMAT(NOW(), '%Y-%m-01') AND LAST_DAY(NOW())
GROUP BY employee, employee_name
HAVING (total_absent_days + unpaid_leave_days) > 0
ORDER BY total_absent_days DESC;
```

### Pattern 5: Monthly Salary Slip Payout Totals & Delivery Status
Aggregates payroll disbursement and email delivery status for a salary month:
```sql
SELECT 
  salary_month,
  COUNT(*) AS total_slips,
  SUM(gross_pay) AS total_gross_disbursed,
  SUM(lop_deduction) AS total_lop_deductions,
  SUM(net_pay) AS total_net_disbursed,
  SUM(CASE WHEN email_status = 'Sent' THEN 1 ELSE 0 END) AS emails_sent,
  SUM(CASE WHEN email_status = 'Failed' THEN 1 ELSE 0 END) AS emails_failed
FROM `tabSalary Slip`
WHERE salary_month = '2026-09'
GROUP BY salary_month;
```

### Pattern 6: Upcoming Official Company Holidays
Lists holidays scheduled within the next 60 days:
```sql
SELECT holiday_name, holiday_date, description
FROM `tabHoliday`
WHERE holiday_date >= CURDATE()
ORDER BY holiday_date ASC
LIMIT 10;
```
