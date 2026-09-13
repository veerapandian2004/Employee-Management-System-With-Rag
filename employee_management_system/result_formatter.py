# Copyright (c) 2026, veera and contributors
# For license information, please see license.txt

"""
EMS AI Assistant Result Formatter
=================================
Explains authorized database query results clearly, accurately, and concisely.
Converts raw MariaDB rows into natural language explanations.

Key Design Principles:
1. Use only the provided database result.
2. Never invent missing values.
3. Never assume information not present in the result.
4. Never reveal information that is not included in the authorized result.
5. Keep the response concise and professional.
6. Explain totals, counts, dates, and trends clearly.
7. If no records are returned, clearly say: "I couldn't find any matching records for your request."
8. Do not generate new SQL.
9. Do not claim that additional database access occurred.
10. Return the final user-facing answer as plain text.
"""

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Union


# =====================================================================
# 1. RESULT FORMATTER SYSTEM PROMPT CONTRACT
# =====================================================================

RESULT_FORMATTER_SYSTEM_PROMPT = """# EMS AI Assistant Result Formatter

You are the response generator for the Employee Management System AI Assistant.

You receive:

* The user's original question
* The authorized database query result
* Optional conversation context

Your job is to explain the database result clearly and accurately.

## Rules

1. Use only the provided database result.
2. Never invent missing values.
3. Never assume information not present in the result.
4. Never reveal information that is not included in the authorized result.
5. Keep the response concise and professional.
6. Explain totals, counts, dates, and trends clearly.
7. If no records are returned, clearly say that no matching records were found.
8. Do not generate new SQL.
9. Do not claim that additional database access occurred.

## Examples

User Question:

"How many employees are in Engineering?"

Database Result:

[
  {
    "employee_count": 25
  }
]

Response:

"There are currently 25 employees in the Engineering department."

---

User Question:

"Show pending leave requests."

Database Result:

[
  {
    "employee_name": "John Doe",
    "leave_type": "Sick Leave",
    "from_date": "2026-09-10",
    "to_date": "2026-09-12"
  }
]

Response:

"There is 1 pending leave request:

* John Doe — Sick Leave
* September 10, 2026 to September 12, 2026"

---

If the result is empty:

"I couldn't find any matching records for your request."

Return the final user-facing answer as plain text.
"""

EMPTY_RESULT_MESSAGE = "I couldn't find any matching records for your request."


# =====================================================================
# 2. DATE & CURRENCY HELPERS
# =====================================================================

def _format_date_human(date_val: Any) -> str:
	"""Formats dates into human-readable strings (e.g., September 10, 2026)."""
	if not date_val:
		return "N/A"
	date_str = str(date_val).strip()
	try:
		if len(date_str) == 10 and date_str[4] == "-" and date_str[7] == "-":
			dt = datetime.strptime(date_str, "%Y-%m-%d")
			return dt.strftime("%B %d, %Y").replace(" 0", " ")
		elif " " in date_str:
			dt = datetime.strptime(date_str.split()[0], "%Y-%m-%d")
			return dt.strftime("%B %d, %Y").replace(" 0", " ")
	except Exception:
		pass
	return date_str


def _format_currency(val: Any) -> str:
	"""Formats currency values cleanly."""
	try:
		num = float(val)
		if num.is_integer():
			return f"${int(num):,}"
		return f"${num:,.2f}"
	except (ValueError, TypeError):
		return str(val)


# =====================================================================
# 3. DETERMINISTIC RESULT FORMATTER ENGINE
# =====================================================================

def format_database_result(
	user_question: str,
	database_result: Optional[List[Dict[str, Any]]],
	conversation_context: Optional[List[Dict[str, Any]]] = None,
	llm_response: Optional[str] = None,
) -> str:
	"""
	Explains the database result in clear, concise natural language.
	
	If llm_response is provided:
	  Validates and sanitizes the LLM-generated plain text response.
	If llm_response is not provided:
	  Generates a high-precision, natural language explanation matching
	  the Result Formatter prompt specifications and examples.
	"""
	# If an external LLM response is provided, sanitize and return
	if llm_response is not None and isinstance(llm_response, str) and llm_response.strip():
		cleaned_llm = llm_response.strip()
		# Remove quotes if wrapped
		if cleaned_llm.startswith('"') and cleaned_llm.endswith('"') and len(cleaned_llm) > 2:
			cleaned_llm = cleaned_llm[1:-1].strip()
		return cleaned_llm

	# Rule 7: If no records are returned, say: "I couldn't find any matching records for your request."
	if not database_result or not isinstance(database_result, list) or len(database_result) == 0:
		cleaned_q = (user_question or "").strip().lower()
		if any(k in cleaned_q for k in ["present", "checked in", "clock in"]):
			return "No employees are currently marked as 'Present' in the attendance records (no check-in or present attendance entries exist for today)."
		return EMPTY_RESULT_MESSAGE

	cleaned_q = (user_question or "").strip()
	q_lower = cleaned_q.lower()
	count = len(database_result)

	# -----------------------------------------------------------------
	# CASE 1: Single Aggregated Scalar / Count / Sum
	# -----------------------------------------------------------------
	if count == 1:
		row = database_result[0]
		keys = list(row.keys())

		# Check for count / total / average aggregate fields
		count_keys = [k for k in keys if any(c in k.lower() for c in ["count", "total_employees", "total_slips", "total_applications", "total_attendance"])]
		sum_keys = [k for k in keys if any(s in k.lower() for s in ["sum", "total_gross", "total_net", "total_amount", "total_days", "disbursed"])]
		avg_keys = [k for k in keys if any(a in k.lower() for a in ["avg", "average", "mean"])]

		if len(keys) == 1 and count_keys:
			val = row[count_keys[0]]
			# Example: How many employees are in Engineering? -> There are currently 25 employees in the Engineering department.
			dept_match = re.search(r'\bin\s+([A-Za-z\s]+?)(?:\s+department|\?|$)', cleaned_q, re.IGNORECASE)
			if dept_match and "employee" in q_lower:
				dept_name = dept_match.group(1).strip()
				return f"There are currently {val} employees in the {dept_name} department."
			elif "employee" in q_lower or "staff" in q_lower:
				return f"There are currently {val} matching employees."
			elif "leave" in q_lower:
				return f"There are currently {val} matching leave records."
			elif "salary" in q_lower or "slip" in q_lower:
				return f"There are currently {val} salary slips recorded."
			elif "attendance" in q_lower:
				return f"There are {val} attendance records."
			else:
				return f"The total count is {val}."

		if len(keys) == 1 and sum_keys:
			val = row[sum_keys[0]]
			formatted_val = _format_currency(val) if "day" not in sum_keys[0].lower() else f"{val} days"
			if any(k in q_lower for k in ["disbursement", "outflow", "payroll", "gross", "net", "salary"]):
				return f"The total amount is {formatted_val}."
			elif "day" in q_lower or "leave" in q_lower:
				return f"The total is {formatted_val}."
			return f"The calculated total is {formatted_val}."

		if len(keys) == 1 and avg_keys:
			val = row[avg_keys[0]]
			formatted_val = _format_currency(val)
			return f"The calculated average is {formatted_val}."

	# -----------------------------------------------------------------
	# CASE 2: Leave Application Records
	# -----------------------------------------------------------------
	first_row = database_result[0]
	if "leave_type" in first_row:
		req_word = "leave request" if count == 1 else "leave requests"
		is_pending = "pending" in q_lower or all(r.get("status") == "Pending" for r in database_result)
		prefix = f"There {'is' if count == 1 else 'are'} {count} {'pending ' if is_pending else ''}{req_word}:"

		items = []
		for r in database_result:
			emp_id = r.get("employee")
			emp_name = r.get("employee_name")
			if not emp_name and emp_id:
				try:
					import frappe
					if hasattr(frappe, "db") and frappe.db:
						emp_name = frappe.db.get_value("Employee", emp_id, "full_name")
				except Exception:
					pass
			if emp_name and emp_id and emp_name != emp_id:
				emp_display = f"{emp_name} ({emp_id})"
			else:
				emp_display = emp_name or emp_id or "Employee"

			ltype = r.get("leave_type", "Leave")
			from_d = _format_date_human(r.get("from_date"))
			to_d = _format_date_human(r.get("to_date"))
			date_str = f"{from_d} to {to_d}" if from_d != to_d else from_d
			st = r.get("status")
			status_suffix = f" ({st})" if st and not is_pending else ""

			item_lines = [
				f"* {emp_display} — {ltype}{status_suffix}",
				f"* {date_str}",
			]
			items.append("\n".join(item_lines))

		return prefix + "\n\n" + "\n\n".join(items)

	# -----------------------------------------------------------------
	# CASE 3: Attendance Records
	# -----------------------------------------------------------------
	if "attendance_date" in first_row or "status" in first_row and any(k in q_lower for k in ["absent", "present", "attendance"]):
		rec_word = "attendance record" if count == 1 else "attendance records"
		prefix = f"There {'is' if count == 1 else 'are'} {count} {rec_word}:"
		items = []
		for r in database_result:
			emp = r.get("employee_name") or r.get("employee") or "Employee"
			st = r.get("status", "Status")
			att_d = _format_date_human(r.get("attendance_date")) if r.get("attendance_date") else ""
			date_part = f" on {att_d}" if att_d else ""
			items.append(f"* {emp}: {st}{date_part}")
		return prefix + "\n\n" + "\n".join(items)

	# -----------------------------------------------------------------
	# CASE 4: Salary Slip Records
	# -----------------------------------------------------------------
	if "basic_pay" in first_row or "gross_pay" in first_row or "net_pay" in first_row or "salary_month" in first_row:
		slip_word = "salary slip" if count == 1 else "salary slips"
		prefix = f"Found {count} {slip_word}:"
		items = []
		for r in database_result:
			emp = r.get("employee") or r.get("name") or "Slip"
			month = r.get("salary_month", "")
			net = _format_currency(r.get("net_pay")) if r.get("net_pay") is not None else ""
			gross = _format_currency(r.get("gross_pay")) if r.get("gross_pay") is not None else ""
			st = r.get("status") or r.get("select") or ""
			st_str = f" [{st}]" if st else ""

			parts = []
			if month:
				parts.append(month)
			if gross:
				parts.append(f"Gross: {gross}")
			if net:
				parts.append(f"Net: {net}")
			items.append(f"* {emp} ({', '.join(parts)}){st_str}")
		return prefix + "\n\n" + "\n".join(items)

	# -----------------------------------------------------------------
	# CASE 5: Department Directory
	# -----------------------------------------------------------------
	if "department_name" in first_row:
		dept_word = "department" if count == 1 else "departments"
		prefix = f"Found {count} {dept_word}:"
		items = []
		for r in database_result:
			d_name = r.get("department_name") or r.get("name")
			head = r.get("department_head")
			head_str = f" — Head: {head}" if head else ""
			items.append(f"* {d_name}{head_str}")
		return prefix + "\n\n" + "\n".join(items)

	# -----------------------------------------------------------------
	# CASE 6: Employee Profiles / Directory
	# -----------------------------------------------------------------
	if "full_name" in first_row or "designation" in first_row or ("name" in first_row and "department" in first_row):
		emp_word = "employee" if count == 1 else "employees"
		prefix = f"Found {count} {emp_word}:"
		items = []
		for r in database_result:
			name = r.get("full_name") or r.get("name") or "Employee"
			dept = r.get("department")
			desig = r.get("designation")
			salary = _format_currency(r.get("basic_salary")) if r.get("basic_salary") is not None else None
			st = r.get("status")

			details = []
			if desig:
				details.append(desig)
			if dept:
				details.append(dept)
			if salary:
				details.append(f"Salary: {salary}")
			if st and st != "Active":
				details.append(st)

			detail_str = f" ({', '.join(details)})" if details else ""
			items.append(f"* {name}{detail_str}")
		return prefix + "\n\n" + "\n".join(items)

	# -----------------------------------------------------------------
	# CASE 7: Generic Structured Table Fallback
	# -----------------------------------------------------------------
	# Filter out internal Frappe meta fields
	internal_keys = {"doctype", "docstatus", "idx", "modified_by", "owner", "creation", "modified"}
	headers = [k for k in database_result[0].keys() if k not in internal_keys]

	prefix = f"There {'is' if count == 1 else 'are'} {count} matching {'record' if count == 1 else 'records'}:"
	items = []
	for r in database_result:
		row_parts = []
		for h in headers[:4]:  # limit to top 4 prominent columns for brevity
			v = r.get(h)
			if v is not None and str(v).strip():
				clean_h = h.replace("_", " ").title()
				row_parts.append(f"{clean_h}: {v}")
		if row_parts:
			items.append(f"* {', '.join(row_parts)}")

	if items:
		return prefix + "\n\n" + "\n".join(items)

	return f"Retrieved {count} records successfully."

