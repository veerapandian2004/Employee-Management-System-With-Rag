# Copyright (c) 2026, veera and contributors
# For license information, please see license.txt

"""
CHAT ORCHESTRATOR
=================
Central coordinator for the Employee Management System AI Chatbot.

Architecture:
                    React Chat UI
                         │
                         ▼
                  send_chat_message
                         │
                         ▼
                 CHAT ORCHESTRATOR
                         │
        ┌────────────┬───┴───────────┬──────────────┐
        │            │               │              │
        ▼            ▼               ▼              ▼
    Greeting   Clarification     Knowledge       Database
        │            │               │              │
        ▼            ▼               ▼              ▼
     Direct        Direct       Embeddings     SQL Generator
     Response      Response       Engine            │
                                     │              ▼
                               (Semantic Search) sql_guard.py
                                     │              │
                                     │              ▼
                                     │           MariaDB
                                     │              │
                                     │              ▼
                                     │        Result Formatter
                                     │              │
                                     └──────┬───────┘
                                            ▼
                                      Chat Response
                                            │
                                            ▼
                                     tabChat Message

tabChat Message Schema:
- name
- user
- role
- conversation_id
- message_type (user, assistant, sql, error, clarification, knowledge)
- user_message
- assistant_message
- generated_sql
- query_status (success, error, clarification, not_applicable)
- created_at
"""

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

import frappe
from frappe import _
from frappe.utils import now_datetime

from employee_management_system.employee_management_system.intent_router import (
	route_intent,
	get_conversation_context,
	extract_structured_follow_up_context,
	DEFAULT_GREETING_MESSAGE,
	DEFAULT_UNSUPPORTED_MESSAGE,
	RouterValidationError,
)
from employee_management_system.employee_management_system.sql_guard import (
	run_sql_guard,
	process_llm_pipeline,
	SQLValidationError,
	MAX_SERVER_LIMIT,
)
from employee_management_system.employee_management_system.result_formatter import (
	format_database_result,
	EMPTY_RESULT_MESSAGE,
)
from employee_management_system.employee_management_system.knowledge_engine import (
	answer_knowledge_question,
)


def get_structured_conversation_state(conversation_id: str, user: Optional[str] = None) -> Dict[str, Any]:
	"""
	Retrieves the separately stored structured conversation state for a conversation_id.
	First checks the fast in-memory / redis cache (frappe.cache()).
	If not found, reconstructs state from bounded history (last 5-10 messages) in tabChat Message.
	"""
	if not conversation_id:
		return {}

	cache_key = f"ems_conv_state:{conversation_id}"
	try:
		if frappe and hasattr(frappe, "cache") and frappe.cache():
			cached = frappe.cache().get_value(cache_key)
			if cached:
				if isinstance(cached, str):
					return json.loads(cached)
				elif isinstance(cached, dict):
					return cached
	except Exception:
		pass

	# Reconstruct from tabChat Message (bounded to last 10 messages)
	structured_context = extract_structured_follow_up_context(
		conversation_id=conversation_id,
		user=user,
		current_message=""
	)
	if structured_context:
		state = {
			"conversation_id": conversation_id,
			"user": user or "",
			"last_user_message": structured_context.get("previous_user_message", ""),
			"last_sql": structured_context.get("previous_sql", ""),
			"last_assistant_message": structured_context.get("previous_assistant_message", ""),
			"updated_at": str(now_datetime()),
		}
		set_structured_conversation_state(conversation_id, state)
		return state

	return {
		"conversation_id": conversation_id,
		"user": user or "",
		"last_user_message": "",
		"last_sql": "",
		"last_assistant_message": "",
		"updated_at": str(now_datetime()),
	}


def set_structured_conversation_state(conversation_id: str, state: Dict[str, Any]) -> None:
	"""
	Stores structured conversation state separately in frappe.cache()
	with a 24-hour expiration window.
	"""
	if not conversation_id or not state:
		return
	cache_key = f"ems_conv_state:{conversation_id}"
	try:
		if frappe and hasattr(frappe, "cache") and frappe.cache():
			frappe.cache().set_value(cache_key, json.dumps(state), expires_in_sec=86400)
	except Exception:
		pass


def combine_follow_up_sql(
	follow_up_context: Dict[str, Any],
	user: Optional[str] = None,
	role: Optional[str] = None,
	linked_emp: Optional[dict] = None
) -> Optional[Tuple[str, str]]:
	"""
	Combines the conditions of previous_sql with the refinements in current_message.
	Example:
	  previous_sql: SELECT ... FROM `tabEmployee` WHERE department = 'Engineering' ...
	  current_message: "Only those who joined this year"
	Produces:
	  SELECT ... FROM `tabEmployee` WHERE department = 'Engineering' AND YEAR(date_of_joining) = YEAR(CURDATE()) ...
	"""
	if not follow_up_context or not isinstance(follow_up_context, dict):
		return None

	prev_sql = (follow_up_context.get("previous_sql") or "").strip()
	current_msg = (follow_up_context.get("current_message") or "").strip()
	q_lower = current_msg.lower()

	if not prev_sql:
		return None

	is_employee = (role == "Employee")
	emp_id = (linked_emp.get("name") if linked_emp else None) or ""

	# 1. Identify table
	table_match = re.search(r"FROM\s+[`']?([a-zA-Z0-9_\s]+?)[`']?(?:\s+WHERE|\s+ORDER|\s+GROUP|\s+LIMIT|;|\s*$)", prev_sql, re.IGNORECASE)
	if not table_match:
		return None
	table_name = table_match.group(1).strip()

	# 2. Extract existing WHERE clause
	where_match = re.search(r"\bWHERE\s+(.*?)(?:\s+ORDER\s+BY|\s+GROUP\s+BY|\s+LIMIT|;|\s*$)", prev_sql, re.IGNORECASE)
	existing_where = where_match.group(1).strip() if where_match else ""

	# Split existing WHERE conditions by AND (clean conditions)
	existing_conditions = []
	if existing_where:
		parts = [p.strip() for p in re.split(r"\bAND\b", existing_where, flags=re.IGNORECASE) if p.strip()]
		for p in parts:
			existing_conditions.append(p)

	new_conditions = []
	order_by_clause = ""
	select_clause = ""

	# 3. Process table-specific refinements
	if table_name == "tabEmployee":
		# Joining date filters
		if any(k in q_lower for k in ["joined this year", "joining this year", "current year", "who joined this year"]):
			new_conditions.append("YEAR(date_of_joining) = YEAR(CURDATE())")
			order_by_clause = "ORDER BY date_of_joining DESC"
		elif "joined last year" in q_lower:
			new_conditions.append("YEAR(date_of_joining) = YEAR(CURDATE()) - 1")
			order_by_clause = "ORDER BY date_of_joining DESC"
		else:
			join_year_match = re.search(r"joined\s+(?:in\s+)?(20\d\d)", q_lower)
			if join_year_match:
				yr = join_year_match.group(1)
				new_conditions.append(f"YEAR(date_of_joining) = {yr}")
				order_by_clause = "ORDER BY date_of_joining DESC"
			else:
				after_year_match = re.search(r"joined\s+after\s+(20\d\d)", q_lower)
				if after_year_match:
					yr = after_year_match.group(1)
					new_conditions.append(f"YEAR(date_of_joining) > {yr}")
					order_by_clause = "ORDER BY date_of_joining DESC"

		# Status filters
		if "active" in q_lower:
			new_conditions.append("status = 'Active'")
		elif "on leave" in q_lower:
			new_conditions.append("status = 'On Leave'")
		elif "suspended" in q_lower:
			new_conditions.append("status = 'Suspended'")
		elif "terminated" in q_lower:
			new_conditions.append("status = 'Terminated'")

		# Salary numeric filter (> or <)
		sal_match = re.search(r'(?:salary|earns?|paid|earning)?\s*(?:>|<|>=|<=|=|more than|greater than|less than|above|over)?\s*(\$?\d[\d,]*)', q_lower)
		if not sal_match or not sal_match.group(1):
			sal_match = re.search(r'\b(\d{4,})\b', q_lower)
		if sal_match:
			val_str = re.sub(r'[^\d]', '', sal_match.group(1) if hasattr(sal_match, 'group') else sal_match)
			if val_str and int(val_str) > 0:
				val = int(val_str)
				if any(k in q_lower for k in ["less", "under", "below", "<"]):
					new_conditions.append(f"basic_salary < {val}")
				else:
					new_conditions.append(f"basic_salary > {val}")

		# Name pattern filters (starts with, begins with, ends with, contains)
		starts_with_match = re.search(r"(?:starting|starts?|beginning|begins?)\s*(?:with\s+(?:the\s+)?letter|with)\s*['\"`]?([a-zA-Z]+)['\"`]?", q_lower, re.IGNORECASE)
		if starts_with_match:
			prefix = starts_with_match.group(1).strip()
			new_conditions.append(f"full_name LIKE '{prefix}%'")
		else:
			ends_with_match = re.search(r"(?:ending|ends?)\s*(?:with\s+(?:the\s+)?letter|with)\s*['\"`]?([a-zA-Z]+)['\"`]?", q_lower, re.IGNORECASE)
			if ends_with_match:
				suffix = ends_with_match.group(1).strip()
				new_conditions.append(f"full_name LIKE '%{suffix}'")
			else:
				contains_match = re.search(r"(?:name|names)\s+(?:containing|contains?|having)\s*['\"`]?([a-zA-Z]+)['\"`]?", q_lower, re.IGNORECASE)
				if contains_match:
					substr = contains_match.group(1).strip()
					new_conditions.append(f"full_name LIKE '%{substr}%'")

		# Role / Designation filter
		if "software engineer" in q_lower or "software developer" in q_lower:
			new_conditions.append("designation LIKE '%Software Engineer%'")
		elif "qa engineer" in q_lower or "qa" in q_lower:
			new_conditions.append("designation LIKE '%QA%'")
		elif "director" in q_lower:
			new_conditions.append("designation LIKE '%Director%'")
		elif "cto" in q_lower or "chief technology officer" in q_lower:
			new_conditions.append("designation LIKE '%Chief Technology Officer%'")
		elif "manager" in q_lower or "managers" in q_lower:
			new_conditions.append("designation LIKE '%Manager%'")
		elif "developer" in q_lower or "developers" in q_lower:
			new_conditions.append("designation LIKE '%Developer%'")
		elif "engineer" in q_lower or "engineers" in q_lower and "engineering" not in q_lower:
			new_conditions.append("designation LIKE '%Engineer%'")

		# Sorting & projection
		if any(k in q_lower for k in ["sort by joining", "order by joining", "sort by date", "by joining date"]):
			order_by_clause = "ORDER BY date_of_joining DESC"
		elif any(k in q_lower for k in ["sort by salary", "highest salary", "top earner", "max salary"]):
			order_by_clause = "ORDER BY basic_salary DESC"
		elif any(k in q_lower for k in ["sort by name", "alphabetical"]):
			order_by_clause = "ORDER BY full_name ASC"

		if "count" in q_lower or "how many" in q_lower or "total" in q_lower:
			select_clause = "SELECT COUNT(*) AS employee_count"
			order_by_clause = ""
		else:
			if any("date_of_joining" in c for c in new_conditions) or "date_of_joining" in order_by_clause:
				select_clause = "SELECT name, full_name, designation, department, date_of_joining, status, basic_salary"
			else:
				select_clause = "SELECT name, full_name, designation, department, email, phone, status, basic_salary"

	elif table_name == "tabLeave Application":
		if "sick" in q_lower:
			new_conditions.append("leave_type = 'Sick Leave'")
		elif "casual" in q_lower:
			new_conditions.append("leave_type = 'Casual Leave'")
		elif "annual" in q_lower:
			new_conditions.append("leave_type = 'Annual Leave'")

		if "pending" in q_lower:
			new_conditions.append("status = 'Pending'")
		elif "approved" in q_lower:
			new_conditions.append("status = 'Approved'")
		elif "rejected" in q_lower:
			new_conditions.append("status = 'Rejected'")

		if "count" in q_lower or "how many" in q_lower or "total" in q_lower:
			select_clause = "SELECT COUNT(*) AS total_applications"
			order_by_clause = ""
		else:
			select_clause = "SELECT name, employee, leave_type, from_date, to_date, total_days, status"
			order_by_clause = "ORDER BY creation DESC"

	elif table_name == "tabSalary Slip":
		if "paid" in q_lower:
			new_conditions.append("`select` = 'Paid'")
		elif "draft" in q_lower:
			new_conditions.append("`select` = 'Draft'")
		elif "submitted" in q_lower:
			new_conditions.append("`select` = 'Submitted'")

		if "count" in q_lower or "how many" in q_lower:
			select_clause = "SELECT COUNT(*) AS total_salary_slips"
			order_by_clause = ""
		elif any(k in q_lower for k in ["total", "sum", "disbursement"]):
			select_clause = "SELECT SUM(gross_pay) AS total_gross_disbursed, SUM(net_pay) AS total_net_disbursed, COUNT(*) AS total_slips"
			order_by_clause = ""
		else:
			select_clause = "SELECT name, employee, salary_month, basic_pay, hra, gross_pay, net_pay, `select` AS status"
			order_by_clause = "ORDER BY creation DESC"

	elif table_name == "tabAttendance":
		if "yesterday" in q_lower:
			existing_conditions = [c for c in existing_conditions if "attendance_date" not in c]
			new_conditions.append("attendance_date = DATE_SUB(CURDATE(), INTERVAL 1 DAY)")
		elif "today" in q_lower:
			existing_conditions = [c for c in existing_conditions if "attendance_date" not in c]
			new_conditions.append("attendance_date = CURDATE()")

		if "absent" in q_lower:
			existing_conditions = [c for c in existing_conditions if "status =" not in c]
			new_conditions.append("status = 'Absent'")
		elif "present" in q_lower:
			existing_conditions = [c for c in existing_conditions if "status =" not in c]
			new_conditions.append("status = 'Present'")

		if "count" in q_lower or "how many" in q_lower:
			select_clause = "SELECT COUNT(*) AS total_attendance"
			order_by_clause = ""
		else:
			select_clause = "SELECT employee, employee_name, attendance_date, status"
			order_by_clause = "ORDER BY attendance_date DESC"

	else:
		return None

	# Combine conditions avoiding duplicates
	combined_conditions = []
	for c in existing_conditions:
		if c not in combined_conditions:
			combined_conditions.append(c)
	for c in new_conditions:
		if c not in combined_conditions:
			combined_conditions.append(c)

	if is_employee and emp_id:
		if table_name == "tabEmployee":
			if not any("name =" in c for c in combined_conditions):
				combined_conditions.append(f"name = '{emp_id}'")
		elif not any("employee =" in c for c in combined_conditions):
			combined_conditions.append(f"employee = '{emp_id}'")

	where_str = " WHERE " + " AND ".join(combined_conditions) if combined_conditions else ""
	limit_str = "LIMIT 20" if select_clause.startswith("SELECT name") or select_clause.startswith("SELECT employee") else ""

	if not order_by_clause and limit_str:
		order_by_clause = "ORDER BY creation DESC" if table_name in ("tabLeave Application", "tabSalary Slip") else "ORDER BY name ASC"

	parts = [select_clause, f"FROM `{table_name}`"]
	if where_str:
		parts.append(where_str.strip())
	if order_by_clause:
		parts.append(order_by_clause.strip())
	if limit_str and not select_clause.startswith("SELECT COUNT") and not select_clause.startswith("SELECT SUM"):
		parts.append(limit_str.strip())

	sql = " ".join(parts).strip() + ";"
	return sql, table_name


def generate_sql_for_question(
	message: str,
	user: str = None,
	role: str = None,
	linked_emp: dict = None,
	follow_up_context: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str]:
	"""
	SQL Generator Model: Translates verified workforce inquiries into MariaDB SELECT queries.
	Single-job model matching schema requirements for tabEmployee, tabDepartment,
	tabLeave Application, tabLeave Type, tabSalary Slip, tabAttendance, and tabPayroll.
	When follow_up_context is provided, combines existing previous_sql conditions with
	refinements in current_message.
	"""
	# If structured follow-up context is supplied, attempt condition combination
	if follow_up_context and follow_up_context.get("previous_sql"):
		combined = combine_follow_up_sql(follow_up_context, user=user, role=role, linked_emp=linked_emp)
		if combined:
			return combined

	q = str(message).strip().lower()
	is_employee = (role == "Employee")
	emp_id = (linked_emp.get("name") if linked_emp else None) or ""

	# 1. Attendance Database
	if any(k in q for k in ["attendance", "present", "absent", "half day", "check in", "clock"]):
		where_clauses = []
		if is_employee and emp_id:
			where_clauses.append(f"employee = '{emp_id}'")
		if "today" in q or "curdate" in q or "now" in q:
			where_clauses.append("attendance_date = CURDATE()")
		if "present" in q:
			where_clauses.append("status = 'Present'")
		elif "absent" in q:
			where_clauses.append("status = 'Absent'")

		if "count" in q or "how many" in q:
			if "by status" in q or "per status" in q:
				sql = "SELECT status, COUNT(*) AS total_count FROM `tabAttendance`"
				if where_clauses:
					sql += " WHERE " + " AND ".join(where_clauses)
				sql += " GROUP BY status;"
			else:
				sql = "SELECT COUNT(*) AS total_attendance FROM `tabAttendance`"
				if where_clauses:
					sql += " WHERE " + " AND ".join(where_clauses)
				sql += ";"
		else:
			sql = "SELECT employee, employee_name, attendance_date, status FROM `tabAttendance`"
			if where_clauses:
				sql += " WHERE " + " AND ".join(where_clauses)
			sql += " ORDER BY attendance_date DESC LIMIT 20;"
		return sql, "tabAttendance"

	# 2. Salary Slip & Payroll Database
	is_asking_for_employee_records = any(k in q for k in ["employee", "employees", "staff", "worker", "colleague"]) and not any(k in q for k in ["slip", "slips", "paystub", "paystubs"])
	if not is_asking_for_employee_records and any(k in q for k in ["salary", "pay", "paystub", "slip", "compensation", "disbursement", "earnings", "deduction", "payroll", "gross", "net"]):
		where_clauses = []
		if is_employee and emp_id:
			where_clauses.append(f"employee = '{emp_id}'")

		if "paid" in q:
			where_clauses.append("`select` = 'Paid'")
		elif "draft" in q:
			where_clauses.append("`select` = 'Draft'")
		elif "submitted" in q:
			where_clauses.append("`select` = 'Submitted'")

		if any(k in q for k in ["total", "sum", "disbursement", "outflow", "overall pay"]):
			if "by month" in q or "per month" in q or "each month" in q:
				sql = "SELECT salary_month, SUM(gross_pay) AS total_gross, SUM(net_pay) AS total_net, COUNT(*) AS total_slips FROM `tabSalary Slip`"
				if where_clauses:
					sql += " WHERE " + " AND ".join(where_clauses)
				sql += " GROUP BY salary_month ORDER BY salary_month DESC;"
			else:
				sql = "SELECT SUM(gross_pay) AS total_gross_disbursed, SUM(net_pay) AS total_net_disbursed, COUNT(*) AS total_slips FROM `tabSalary Slip`"
				if where_clauses:
					sql += " WHERE " + " AND ".join(where_clauses)
				sql += ";"
		elif any(k in q for k in ["highest", "top", "max", "most"]):
			sql = "SELECT name, employee, salary_month, gross_pay, net_pay FROM `tabSalary Slip`"
			if where_clauses:
				sql += " WHERE " + " AND ".join(where_clauses)
			sql += " ORDER BY net_pay DESC LIMIT 5;"
		elif any(k in q for k in ["lowest", "min", "least"]):
			sql = "SELECT name, employee, salary_month, gross_pay, net_pay FROM `tabSalary Slip`"
			if where_clauses:
				sql += " WHERE " + " AND ".join(where_clauses)
			sql += " ORDER BY net_pay ASC LIMIT 5;"
		elif "count" in q or "how many" in q:
			sql = "SELECT COUNT(*) AS total_salary_slips FROM `tabSalary Slip`"
			if where_clauses:
				sql += " WHERE " + " AND ".join(where_clauses)
			sql += ";"
		else:
			sql = "SELECT name, employee, salary_month, basic_pay, hra, gross_pay, net_pay, `select` AS status FROM `tabSalary Slip`"
			if where_clauses:
				sql += " WHERE " + " AND ".join(where_clauses)
			sql += " ORDER BY creation DESC LIMIT 15;"
		return sql, "tabSalary Slip"

	# 3. Leave Application & Policy Database
	if any(k in q for k in ["leave", "vacation", "sick", "balance", "days off", "holiday", "time off"]):
		if "type" in q or "policy" in q or "policies" in q or "entitlement" in q:
			sql = "SELECT leave_type_name, max_days_per_year, carry_forward FROM `tabLeave Type` ORDER BY leave_type_name ASC;"
			return sql, "tabLeave Type"

		where_clauses = []
		if is_employee and emp_id:
			where_clauses.append(f"employee = '{emp_id}'")

		if any(k in q for k in ["today", "now", "current", "curdate"]):
			where_clauses.append("CURDATE() BETWEEN from_date AND to_date")
			if not any(k in q for k in ["pending", "rejected"]):
				where_clauses.append("status = 'Approved'")
		elif "pending" in q:
			where_clauses.append("status = 'Pending'")
		elif "approved" in q:
			where_clauses.append("status = 'Approved'")
		elif "rejected" in q:
			where_clauses.append("status = 'Rejected'")

		if any(k in q for k in ["count", "how many", "total days"]):
			if "by employee" in q or "per employee" in q:
				sql = "SELECT employee, COUNT(*) AS request_count, SUM(total_days) AS total_days_taken FROM `tabLeave Application`"
				if where_clauses:
					sql += " WHERE " + " AND ".join(where_clauses)
				sql += " GROUP BY employee ORDER BY total_days_taken DESC;"
			elif "by type" in q or "per type" in q or "by leave type" in q:
				sql = "SELECT leave_type, COUNT(*) AS request_count, SUM(total_days) AS total_days FROM `tabLeave Application`"
				if where_clauses:
					sql += " WHERE " + " AND ".join(where_clauses)
				sql += " GROUP BY leave_type ORDER BY request_count DESC;"
			else:
				sql = "SELECT COUNT(*) AS total_applications, SUM(total_days) AS total_days_requested FROM `tabLeave Application`"
				if where_clauses:
					sql += " WHERE " + " AND ".join(where_clauses)
				sql += ";"
		else:
			sql = "SELECT name, employee, leave_type, from_date, to_date, total_days, status FROM `tabLeave Application`"
			if where_clauses:
				sql += " WHERE " + " AND ".join(where_clauses)
			sql += " ORDER BY creation DESC LIMIT 15;"
		return sql, "tabLeave Application"

	# 4. Department Directory
	if any(k in q for k in ["department", "dept", "division", "branch"]):
		if not any(k in q for k in ["employee", "staff", "headcount", "people"]):
			where_clauses = []
			if "without head" in q or "no head" in q or "unassigned" in q:
				where_clauses.append("(department_head IS NULL OR department_head = '')")
			sql = "SELECT name, department_name, department_head, parent_department FROM `tabDepartment`"
			if where_clauses:
				sql += " WHERE " + " AND ".join(where_clauses)
			sql += " ORDER BY department_name ASC;"
			return sql, "tabDepartment"

	# 5. Employee Database (tabEmployee)
	is_working_today = any(k in q for k in ["working today", "working employee", "who is working", "employees working", "working staff", "staff working", "working now"])
	if is_working_today and not is_employee:
		sql = (
			"SELECT name, full_name, designation, department, basic_salary, status "
			"FROM `tabEmployee` "
			"WHERE status = 'Active' "
			"AND name NOT IN ("
			"SELECT employee FROM `tabLeave Application` "
			"WHERE status = 'Approved' AND CURDATE() BETWEEN from_date AND to_date"
			") "
			"ORDER BY full_name ASC LIMIT 25;"
		)
		return sql, "tabEmployee"

	where_clauses = []
	if is_employee and emp_id:
		where_clauses.append(f"name = '{emp_id}'")
	else:
		if "active" in q:
			where_clauses.append("status = 'Active'")
		elif "on leave" in q:
			where_clauses.append("status = 'On Leave'")
		elif "suspended" in q:
			where_clauses.append("status = 'Suspended'")
		elif "terminated" in q:
			where_clauses.append("status = 'Terminated'")

		# Name pattern filters (starts with, begins with, ends with, contains)
		starts_with_match = re.search(r"(?:starting|starts?|beginning|begins?)\s*(?:with\s+(?:the\s+)?letter|with)\s*['\"`]?([a-zA-Z]+)['\"`]?", q, re.IGNORECASE)
		if starts_with_match:
			prefix = starts_with_match.group(1).strip()
			where_clauses.append(f"full_name LIKE '{prefix}%'")
		else:
			ends_with_match = re.search(r"(?:ending|ends?)\s*(?:with\s+(?:the\s+)?letter|with)\s*['\"`]?([a-zA-Z]+)['\"`]?", q, re.IGNORECASE)
			if ends_with_match:
				suffix = ends_with_match.group(1).strip()
				where_clauses.append(f"full_name LIKE '%{suffix}'")
			else:
				contains_match = re.search(r"(?:name|names)\s+(?:containing|contains?|having)\s*['\"`]?([a-zA-Z]+)['\"`]?", q, re.IGNORECASE)
				if contains_match:
					substr = contains_match.group(1).strip()
					where_clauses.append(f"full_name LIKE '%{substr}%'")

		# Designation filters
		if "software engineer" in q or "software developer" in q:
			where_clauses.append("designation LIKE '%Software Engineer%'")
		elif "qa engineer" in q or "qa" in q or "tester" in q:
			where_clauses.append("designation LIKE '%QA%'")
		elif "director" in q or "hr director" in q:
			where_clauses.append("designation LIKE '%Director%'")
		elif "cto" in q or "chief technology officer" in q:
			where_clauses.append("designation LIKE '%Chief Technology Officer%'")
		elif "manager" in q or "managers" in q:
			where_clauses.append("designation LIKE '%Manager%'")
		elif "developer" in q or "developers" in q:
			where_clauses.append("designation LIKE '%Developer%'")
		elif ("engineer" in q or "engineers" in q) and "engineering" not in q:
			where_clauses.append("designation LIKE '%Engineer%'")

		# Check actual departments in system
		try:
			existing_depts = [d.department_name for d in frappe.get_all("Department", fields=["department_name"])]
			for d_name in existing_depts:
				if d_name.lower() in q:
					where_clauses.append(f"department = {frappe.db.escape(d_name)}")
					break
		except Exception:
			pass

		# Specific employee name mention (e.g. "show employee David Chen", "details of Alex Rivera")
		if not starts_with_match:
			try:
				existing_emps = frappe.get_all("Employee", fields=["full_name"])
				for emp_rec in existing_emps:
					fname = emp_rec.full_name or ""
					if fname and fname.lower() in q:
						where_clauses.append(f"full_name = {frappe.db.escape(fname)}")
						break
			except Exception:
				pass

		# Salary numeric filter (> or <)
		sal_match = re.search(r'(?:salary|earns?|paid|earning)?\s*(?:>|<|>=|<=|=|more than|greater than|less than|above|over)?\s*(\$?\d[\d,]*)', q)
		if not sal_match or not sal_match.group(1):
			sal_match = re.search(r'\b(\d{4,})\b', q)
		if sal_match:
			val_str = re.sub(r'[^\d]', '', sal_match.group(1) if hasattr(sal_match, 'group') else sal_match)
			if val_str and int(val_str) > 0:
				val = int(val_str)
				if any(k in q for k in ["less", "under", "below", "<"]):
					where_clauses.append(f"basic_salary < {val}")
				else:
					where_clauses.append(f"basic_salary > {val}")

	if "count" in q or "how many" in q or "headcount" in q:
		if "by department" in q or "per department" in q or "each department" in q:
			sql = "SELECT department, COUNT(*) AS employee_count FROM `tabEmployee`"
			if where_clauses:
				sql += " WHERE " + " AND ".join(where_clauses)
			sql += " GROUP BY department ORDER BY employee_count DESC;"
		elif "by status" in q or "per status" in q:
			sql = "SELECT status, COUNT(*) AS employee_count FROM `tabEmployee`"
			if where_clauses:
				sql += " WHERE " + " AND ".join(where_clauses)
			sql += " GROUP BY status;"
		else:
			sql = "SELECT COUNT(*) AS employee_count FROM `tabEmployee`"
			if where_clauses:
				sql += " WHERE " + " AND ".join(where_clauses)
			sql += ";"
	elif any(k in q for k in ["average", "avg", "mean"]):
		if "by department" in q or "per department" in q:
			sql = "SELECT department, ROUND(AVG(basic_salary), 2) AS avg_basic_salary, COUNT(*) AS employee_count FROM `tabEmployee`"
			if where_clauses:
				sql += " WHERE " + " AND ".join(where_clauses)
			sql += " GROUP BY department ORDER BY avg_basic_salary DESC;"
		else:
			sql = "SELECT ROUND(AVG(basic_salary), 2) AS avg_company_salary, COUNT(*) AS total_staff FROM `tabEmployee`"
			if where_clauses:
				sql += " WHERE " + " AND ".join(where_clauses)
			sql += ";"
	elif any(k in q for k in ["highest paid", "top earner", "highest salary", "highest", "max"]):
		sql = "SELECT name, full_name, designation, department, basic_salary FROM `tabEmployee`"
		if where_clauses:
			sql += " WHERE " + " AND ".join(where_clauses)
		sql += " ORDER BY basic_salary DESC LIMIT 5;"
	elif any(k in q for k in ["lowest paid", "lowest salary", "least paid"]):
		sql = "SELECT name, full_name, designation, department, basic_salary FROM `tabEmployee`"
		if where_clauses:
			sql += " WHERE " + " AND ".join(where_clauses)
		sql += " ORDER BY basic_salary ASC LIMIT 5;"
	elif any(k in q for k in ["recent", "newest", "recently joined", "latest join"]):
		sql = "SELECT name, full_name, designation, department, date_of_joining FROM `tabEmployee`"
		if where_clauses:
			sql += " WHERE " + " AND ".join(where_clauses)
		sql += " ORDER BY date_of_joining DESC LIMIT 10;"
	else:
		sql = "SELECT name, full_name, designation, department, email, phone, status, basic_salary FROM `tabEmployee`"
		if where_clauses:
			sql += " WHERE " + " AND ".join(where_clauses)
		sql += " ORDER BY full_name ASC LIMIT 20;"

	return sql, "tabEmployee"


def save_chat_message_record(
	user: str,
	role: str = "Administrator",
	conversation_id: Optional[str] = None,
	message_type: str = "assistant",
	user_message: Optional[str] = None,
	assistant_message: Optional[str] = None,
	generated_sql: Optional[str] = None,
	query_status: str = "success",
	created_at: Any = None,
	sources: Optional[str] = None,
) -> Any:
	"""
	Direct functional helper to save records to tabChat Message adhering to the updated schema:
	- name
	- user
	- role
	- conversation_id
	- message_type (user, assistant, sql, error, clarification)
	- user_message
	- assistant_message
	- generated_sql
	- query_status (success, error, clarification, not_applicable)
	- created_at
	"""
	if not created_at:
		created_at = now_datetime()
	cid = conversation_id or f"conv_{user}_{created_at.strftime('%Y%m%d')}"

	try:
		if frappe.db.table_exists("Chat Message") or frappe.db.exists("DocType", "Chat Message"):
			chat_doc = frappe.get_doc({
				"doctype": "Chat Message",
				"user": user,
				"role": role or "Administrator",
				"conversation_id": cid,
				"message_type": message_type,
				"user_message": user_message or "",
				"assistant_message": assistant_message or "",
				"generated_sql": generated_sql,
				"query_status": query_status,
				"created_at": created_at,
				# Backward compatibility fields
				"message": user_message or "",
				"response": assistant_message or "",
				"timestamp": created_at,
				"sources": sources or "EMS Assistant",
			})
			chat_doc.insert(ignore_permissions=True)
			frappe.db.commit()
			return chat_doc
	except Exception as e:
		frappe.log_error(title="Chat Message Save Error", message=str(e))
	return None


class ChatOrchestrator:
	"""
	CHAT ORCHESTRATOR
	=================
	The central coordinating brain of the AI Assistant.
	Coordinates:
	send_chat_message -> CHAT ORCHESTRATOR ->
	  - Greeting -> Direct Response (message_type='assistant', query_status='not_applicable')
	  - Clarification -> Direct Response (message_type='clarification', query_status='clarification')
	  - Database -> SQL Generator -> sql_guard.py (AST Check, RBAC Filter, LIMIT)
	             -> MariaDB -> Query Results -> Result Formatter
	             (message_type='sql', query_status='success')
	All paths converge into Chat Response and persist to tabChat Message.
	"""

	def __init__(
		self,
		user: Optional[str] = None,
		role: Optional[str] = None,
		linked_emp: Optional[dict] = None,
		conversation_id: Optional[str] = None
	):
		self.user = user or (frappe.session.user if frappe.session else "Administrator")
		self.role = role or "Administrator"
		self.linked_emp = linked_emp
		self.conversation_id = conversation_id

	def handle_greeting(self, intent_res: Dict[str, Any], message: str) -> Dict[str, Any]:
		"""
		Branch 1: Greeting
		Produces a direct conversational response without database or SQL overhead.
		"""
		return {
			"response": intent_res.get("message") or DEFAULT_GREETING_MESSAGE,
			"sources": "EMS Assistant",
			"executed_sql": None,
			"message_type": "assistant",
			"query_status": "not_applicable",
		}

	def handle_clarification(self, intent_res: Dict[str, Any], message: str) -> Dict[str, Any]:
		"""
		Branch 2: Clarification / Unsupported
		Produces a direct response requesting specifics or explaining available domains.
		"""
		msg = intent_res.get("message")
		intent = intent_res.get("intent")
		if not msg:
			if intent == "unsupported":
				msg = DEFAULT_UNSUPPORTED_MESSAGE
			else:
				msg = "Please specify which record or department you would like to view."
		return {
			"response": msg,
			"sources": "EMS Assistant",
			"executed_sql": None,
			"message_type": "clarification",
			"query_status": "clarification" if intent == "clarification" else "not_applicable",
		}

	def handle_knowledge(self, intent_res: Dict[str, Any], message: str) -> Dict[str, Any]:
		"""
		Branch 4: Knowledge Base (Embeddings Engine)
		Produces semantically matched policy answers from unstructured knowledge documents
		using dense vector embeddings and cosine similarity retrieval.
		Rule: Strictly for unstructured knowledge (policies, handbooks, guidelines, FAQs).
		Never executes SQL or queries tabular employee data.
		"""
		effective_query = intent_res.get("query") or message
		res = answer_knowledge_question(
			query=effective_query,
			user=self.user,
			role=self.role,
		)
		return {
			"response": res.get("response"),
			"sources": res.get("sources", "Corporate Policy Handbook"),
			"executed_sql": None,
			"message_type": "knowledge",
			"query_status": "success",
			"vector_engine": res.get("vector_engine", "qdrant"),
			"chunks": res.get("chunks", []),
			"document_count": res.get("document_count", 0),
		}

	def handle_database(
		self,
		intent_res: Dict[str, Any],
		message: str,
		conversation_context: Optional[List[Dict[str, Any]]] = None,
		follow_up_context: Optional[Dict[str, Any]] = None,
	) -> Dict[str, Any]:
		"""
		Branch 3: Database Query
		1. SQL Generator: Translates question to MariaDB SELECT statement
		   (combining conditions when follow_up_context is present)
		2. sql_guard.py: AST Check -> RBAC Filter -> LIMIT
		3. MariaDB: Safely executes query
		4. Query Results: Returns raw database rows
		5. Result Formatter: Explains result in clear plain text
		"""
		effective_query = intent_res.get("query") or message
		is_follow_up = (intent_res.get("intent") == "follow_up")

		# Extract structured follow-up context ONLY when intent is follow_up
		if is_follow_up and follow_up_context is None:
			structured_ctx = extract_structured_follow_up_context(
				conversation_context=conversation_context,
				current_message=message,
				conversation_id=self.conversation_id,
				user=self.user,
			)
			if not structured_ctx:
				cached_state = get_structured_conversation_state(self.conversation_id, user=self.user)
				if cached_state.get("last_sql"):
					structured_ctx = {
						"previous_user_message": cached_state.get("last_user_message", ""),
						"previous_sql": cached_state.get("last_sql", ""),
						"previous_assistant_message": cached_state.get("last_assistant_message", ""),
						"current_message": message,
						"conversation_id": self.conversation_id,
					}
			follow_up_context = structured_ctx
		elif not is_follow_up:
			follow_up_context = None

		# 1. SQL Generator
		raw_sql, table_name = generate_sql_for_question(
			message=effective_query,
			user=self.user,
			role=self.role,
			linked_emp=self.linked_emp,
			follow_up_context=follow_up_context,
		)

		# 2. sql_guard.py (AST Check, RBAC Filter, LIMIT) & 3. MariaDB Execution
		try:
			exec_result = run_sql_guard(
				sql_query=raw_sql,
				user=self.user,
				role=self.role,
				linked_emp=self.linked_emp,
				max_limit=MAX_SERVER_LIMIT,
			)
			executed_sql = exec_result.get("executed_sql")
			rows = exec_result.get("rows", [])
			tables_found = exec_result.get("tables", [table_name])

			# 4. Result Formatter (Second LLM Stage)
			plain_text_explanation = format_database_result(
				user_question=effective_query,
				database_result=rows,
				conversation_context=conversation_context,
			)

			# 5. Update separate structured conversation state
			set_structured_conversation_state(
				conversation_id=self.conversation_id,
				state={
					"conversation_id": self.conversation_id,
					"user": self.user,
					"last_user_message": message,
					"last_sql": executed_sql,
					"last_table": table_name,
					"last_assistant_message": plain_text_explanation,
					"updated_at": str(now_datetime()),
				}
			)

			return {
				"response": plain_text_explanation,
				"sources": ", ".join(tables_found) if tables_found else table_name,
				"executed_sql": executed_sql,
				"message_type": "sql",
				"query_status": "success",
				"follow_up_context": follow_up_context,
			}

		except SQLValidationError as e:
			return {
				"response": f"**Validation Error**: {e.message}",
				"sources": "SQL Guard",
				"executed_sql": None,
				"message_type": "error",
				"query_status": "error",
			}

	def persist_to_chat_message(
		self,
		user: str,
		user_message: str,
		assistant_message: str,
		role: Optional[str] = None,
		conversation_id: Optional[str] = None,
		message_type: str = "assistant",
		generated_sql: Optional[str] = None,
		query_status: str = "success",
		sources: str = "EMS Assistant",
		created_at: Any = None,
	) -> Any:
		"""
		Persists interaction into tabChat Message according to schema:
		- name
		- user
		- role
		- conversation_id
		- message_type (user, assistant, sql, error, clarification)
		- user_message
		- assistant_message
		- generated_sql
		- query_status (success, error, clarification, not_applicable)
		- created_at
		(also maintains message, response, timestamp, sources for backward compatibility)
		"""
		return save_chat_message_record(
			user=user,
			role=role or self.role or "Administrator",
			conversation_id=conversation_id or self.conversation_id,
			message_type=message_type,
			user_message=user_message,
			assistant_message=assistant_message,
			generated_sql=generated_sql,
			query_status=query_status,
			created_at=created_at,
			sources=sources,
		)

	def orchestrate(
		self,
		message: str,
		conversation_context: Optional[List[Dict[str, Any]]] = None,
		conversation_id: Optional[str] = None,
	) -> Dict[str, Any]:
		"""
		Main orchestration loop executing the full architecture:
		React Chat UI -> send_chat_message -> CHAT ORCHESTRATOR
		              -> Greeting / Clarification / Database
		              -> Chat Response -> tabChat Message
		"""
		cleaned_msg = str(message or "").strip()
		if not cleaned_msg:
			frappe.throw(_("Message is required"))

		timestamp = now_datetime()
		cid = conversation_id or self.conversation_id or f"conv_{self.user}_{timestamp.strftime('%Y%m%d')}"
		self.conversation_id = cid

		# If explicit conversation_context is not provided, fetch from chat history bounded to 5 messages
		if conversation_context is None:
			conversation_context = get_conversation_context(user=self.user, conversation_id=cid, limit=5)
		elif isinstance(conversation_context, str):
			conversation_context = frappe.parse_json(conversation_context)

		# Allow direct SQL JSON payloads for programmatic testing / dev tools
		is_json_input = cleaned_msg.startswith("{") or cleaned_msg.startswith("```json") or cleaned_msg.startswith("```")
		if is_json_input:
			try:
				pipeline_res = process_llm_pipeline(
					cleaned_msg,
					user=self.user,
					role=self.role,
					linked_emp=self.linked_emp
				)
				executed_sql = pipeline_res.get("executed_sql")
				db_rows = pipeline_res.get("data", [])
				# Result Formatter plain text
				final_response = format_database_result(
					user_question="Database query",
					database_result=db_rows,
					conversation_context=conversation_context,
				)
				sources_str = ", ".join(pipeline_res.get("tables", [])) or "MariaDB Database"
				message_type = "sql"
				query_status = "success"
			except SQLValidationError as e:
				final_response = f"**Security / Validation Error**: {e.message}"
				sources_str = "SQL Guard"
				executed_sql = None
				message_type = "error"
				query_status = "error"

			self.persist_to_chat_message(
				user=self.user,
				user_message=cleaned_msg,
				assistant_message=final_response,
				role=self.role,
				conversation_id=cid,
				message_type=message_type,
				generated_sql=executed_sql,
				query_status=query_status,
				sources=sources_str,
				created_at=timestamp
			)

			return {
				"message": cleaned_msg,
				"response": final_response,
				"user_message": cleaned_msg,
				"assistant_message": final_response,
				"role": self.role,
				"conversation_id": cid,
				"message_type": message_type,
				"generated_sql": executed_sql,
				"query_status": query_status,
				"created_at": timestamp.strftime("%Y-%m-%d %H:%M:%S") if hasattr(timestamp, "strftime") else str(timestamp),
				"executed_sql": executed_sql,
				"sources": sources_str,
				"timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S") if hasattr(timestamp, "strftime") else str(timestamp),
			}

		# Step 1: CHAT ORCHESTRATOR Route Intent
		intent_res = route_intent(cleaned_msg, conversation_context=conversation_context)
		intent_type = intent_res.get("intent")

		# Step 2: Branch Dispatch
		if intent_type == "greeting":
			# Branch 1: Greeting -> Direct Response
			branch_res = self.handle_greeting(intent_res, cleaned_msg)

		elif intent_type in ("clarification", "unsupported"):
			# Branch 2: Clarification -> Direct Response
			branch_res = self.handle_clarification(intent_res, cleaned_msg)

		elif intent_type == "knowledge_query":
			# Branch 4: Knowledge Base -> Embeddings Engine
			branch_res = self.handle_knowledge(intent_res, cleaned_msg)

		else:
			# Branch 3: Database Query (database_query or follow_up requiring DB)
			branch_res = self.handle_database(intent_res, cleaned_msg, conversation_context=conversation_context)

		final_response = branch_res["response"]
		sources_str = branch_res.get("sources", "EMS Assistant")
		executed_sql = branch_res.get("executed_sql")
		message_type = branch_res.get("message_type", "assistant")
		query_status = branch_res.get("query_status", "success")

		# Step 3: Persist Chat Response to tabChat Message
		self.persist_to_chat_message(
			user=self.user,
			user_message=cleaned_msg,
			assistant_message=final_response,
			role=self.role,
			conversation_id=cid,
			message_type=message_type,
			generated_sql=executed_sql,
			query_status=query_status,
			sources=sources_str,
			created_at=timestamp
		)

		return {
			"message": cleaned_msg,
			"response": final_response,
			"user_message": cleaned_msg,
			"assistant_message": final_response,
			"role": self.role,
			"conversation_id": cid,
			"message_type": message_type,
			"generated_sql": executed_sql,
			"query_status": query_status,
			"created_at": timestamp.strftime("%Y-%m-%d %H:%M:%S") if hasattr(timestamp, "strftime") else str(timestamp),
			"executed_sql": executed_sql,
			"sources": sources_str,
			"timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S") if hasattr(timestamp, "strftime") else str(timestamp),
		}


def orchestrate_chat_message(
	message: str,
	user: str = None,
	role: str = None,
	linked_emp: dict = None,
	conversation_context: Optional[List[Dict[str, Any]]] = None,
	conversation_id: Optional[str] = None,
) -> Dict[str, Any]:
	"""
	Functional entrypoint for the CHAT ORCHESTRATOR.
	"""
	orchestrator = ChatOrchestrator(user=user, role=role, linked_emp=linked_emp, conversation_id=conversation_id)
	return orchestrator.orchestrate(message, conversation_context=conversation_context, conversation_id=conversation_id)
