# Copyright (c) 2026, veera and contributors
# For license information, please see license.txt

"""
Unit & Integration Test Suite for SQL Guard & Programmatic RBAC Pipeline
========================================================================
Tests the complete 10-stage pipeline:
LLM JSON -> Parse JSON -> Check status == sql -> Validate SQL Parser / AST
         -> Validate SELECT-only -> Validate tables -> Validate columns
         -> Enforce RBAC -> Add server-side LIMIT -> Execute MariaDB
"""

import os
import sys
import json
import unittest

app_root = "/home/tui013/frappe-benchv/apps/employee_management_system"
if app_root in sys.path:
	sys.path.remove(app_root)
sys.path.insert(0, app_root)
cur_dir = os.path.dirname(os.path.abspath(__file__))
if cur_dir in sys.path:
	sys.path.remove(cur_dir)

# Ensure frappe environment is initialized
import frappe
if not frappe.db:
	frappe.init(site="hospital.localhost")
	frappe.connect()

from employee_management_system.employee_management_system.sql_guard import (
	parse_llm_json,
	check_status,
	validate_sql_parser_ast,
	validate_select_only,
	validate_tables,
	validate_columns,
	enforce_rbac,
	add_server_side_limit,
	execute_mariadb,
	format_markdown_table,
	process_llm_pipeline,
	JSONParseError,
	ASTValidationError,
	SecurityViolationError,
	RBACViolationError,
	SQLValidationError,
	LLM_BACKEND_VALIDATION_PROMPT,
	SQL_GENERATOR_SYSTEM_PROMPT,
	MAX_SERVER_LIMIT,
	DEFAULT_SERVER_LIMIT,
)


class TestSQLGuardPipeline(unittest.TestCase):

	def setUp(self):
		self.admin_user = "Administrator"
		self.hr_user = "hr@ems.com"
		self.employee_user = "emp1@ems.com"
		self.linked_emp = {"name": "EMP-001", "full_name": "Test Employee", "department": "Engineering"}

	def test_sql_generator_prompt_contract(self):
		self.assertIn("specialized MariaDB SQL query generator", SQL_GENERATOR_SYSTEM_PROMPT)
		self.assertIn("Chatbot Router", SQL_GENERATOR_SYSTEM_PROMPT)
		self.assertIn("tabEmployee", SQL_GENERATOR_SYSTEM_PROMPT)
		self.assertEqual(LLM_BACKEND_VALIDATION_PROMPT, SQL_GENERATOR_SYSTEM_PROMPT)


	# -------------------------------------------------------------
	# STAGE 1: PARSE JSON
	# -------------------------------------------------------------
	def test_stage_1_parse_valid_json_string(self):
		raw = '{"status": "sql", "sql": "SELECT name FROM `tabEmployee`"}'
		parsed = parse_llm_json(raw)
		self.assertEqual(parsed["status"], "sql")
		self.assertEqual(parsed["sql"], "SELECT name FROM `tabEmployee`")

	def test_stage_1_parse_markdown_fenced_json(self):
		raw = """```json
{
  "status": "sql",
  "sql": "SELECT name, full_name FROM `tabEmployee` WHERE status = 'Active'"
}
```"""
		parsed = parse_llm_json(raw)
		self.assertEqual(parsed["status"], "sql")

	def test_stage_1_parse_malformed_json_raises_error(self):
		bad_json = '{"status": "sql", "sql": missing_quotes}'
		with self.assertRaises(JSONParseError):
			parse_llm_json(bad_json)

	# -------------------------------------------------------------
	# STAGE 2: CHECK STATUS == "sql"
	# -------------------------------------------------------------
	def test_stage_2_check_status_sql(self):
		payload = {"status": "sql", "sql": "SELECT name FROM `tabEmployee`", "explanation": "List employees"}
		res = check_status(payload)
		self.assertTrue(res["is_sql"])
		self.assertEqual(res["sql"], "SELECT name FROM `tabEmployee`")

	def test_stage_2_check_status_clarification(self):
		payload = {"status": "clarification", "message": "Can you specify which department?"}
		res = check_status(payload)
		self.assertFalse(res["is_sql"])
		self.assertEqual(res["message"], "Can you specify which department?")

	def test_stage_2_missing_status_field(self):
		payload = {"sql": "SELECT 1"}
		with self.assertRaises(ASTValidationError):
			check_status(payload)

	def test_stage_2_status_sql_without_sql_query(self):
		payload = {"status": "sql", "sql": ""}
		with self.assertRaises(ASTValidationError):
			check_status(payload)

	# -------------------------------------------------------------
	# STAGE 3: VALIDATE SQL PARSER / AST
	# -------------------------------------------------------------
	def test_stage_3_ast_valid_query(self):
		sql = "SELECT name, full_name, basic_salary FROM `tabEmployee` WHERE status = 'Active'"
		ast = validate_sql_parser_ast(sql)
		self.assertIsNotNone(ast)

	def test_stage_3_ast_syntax_error(self):
		bad_sql = "SELECT name FROM `tabEmployee` WHERE (status = 'Active'"
		with self.assertRaises(ASTValidationError):
			validate_sql_parser_ast(bad_sql)

	def test_stage_3_multi_statement_injection_blocked(self):
		multi_sql = "SELECT name FROM `tabEmployee`; DROP TABLE `tabEmployee`;"
		with self.assertRaises(SecurityViolationError):
			validate_sql_parser_ast(multi_sql)

	# -------------------------------------------------------------
	# STAGE 4: VALIDATE SELECT-ONLY
	# -------------------------------------------------------------
	def test_stage_4_update_statement_blocked(self):
		sql = "UPDATE `tabEmployee` SET basic_salary = 99999 WHERE name = 'EMP-001'"
		ast = validate_sql_parser_ast(sql)
		with self.assertRaises(SecurityViolationError):
			validate_select_only(ast)

	def test_stage_4_delete_statement_blocked(self):
		sql = "DELETE FROM `tabEmployee` WHERE name = 'EMP-001'"
		ast = validate_sql_parser_ast(sql)
		with self.assertRaises(SecurityViolationError):
			validate_select_only(ast)

	def test_stage_4_insert_statement_blocked(self):
		sql = "INSERT INTO `tabEmployee` (name, full_name) VALUES ('EMP-999', 'Hacker')"
		ast = validate_sql_parser_ast(sql)
		with self.assertRaises(SecurityViolationError):
			validate_select_only(ast)

	def test_stage_4_drop_table_blocked(self):
		sql = "DROP TABLE `tabEmployee`"
		ast = validate_sql_parser_ast(sql)
		with self.assertRaises(SecurityViolationError):
			validate_select_only(ast)

	def test_stage_4_dangerous_function_sleep_blocked(self):
		sql = "SELECT name, SLEEP(5) FROM `tabEmployee`"
		ast = validate_sql_parser_ast(sql)
		with self.assertRaises(SecurityViolationError):
			validate_select_only(ast)

	def test_stage_4_dangerous_function_benchmark_blocked(self):
		sql = "SELECT BENCHMARK(1000000, MD5('test')) FROM `tabEmployee`"
		ast = validate_sql_parser_ast(sql)
		with self.assertRaises(SecurityViolationError):
			validate_select_only(ast)

	# -------------------------------------------------------------
	# STAGE 5: VALIDATE TABLES
	# -------------------------------------------------------------
	def test_stage_5_allowed_tables_accepted(self):
		sql = "SELECT name, department_name FROM `tabDepartment`"
		ast = validate_sql_parser_ast(sql)
		validate_select_only(ast)
		tables = validate_tables(ast)
		self.assertIn("tabDepartment", tables)

	def test_stage_5_system_user_table_blocked(self):
		sql = "SELECT name, password FROM `tabUser`"
		ast = validate_sql_parser_ast(sql)
		validate_select_only(ast)
		with self.assertRaises(SecurityViolationError):
			validate_tables(ast)

	def test_stage_5_information_schema_blocked(self):
		sql = "SELECT table_name FROM information_schema.tables"
		ast = validate_sql_parser_ast(sql)
		validate_select_only(ast)
		with self.assertRaises(SecurityViolationError):
			validate_tables(ast)

	def test_stage_5_union_with_unauthorized_table_blocked(self):
		sql = "SELECT name FROM `tabEmployee` UNION SELECT name FROM `tabUser`"
		ast = validate_sql_parser_ast(sql)
		validate_select_only(ast)
		with self.assertRaises(SecurityViolationError):
			validate_tables(ast)

	# -------------------------------------------------------------
	# STAGE 6: VALIDATE COLUMNS
	# -------------------------------------------------------------
	def test_stage_6_valid_columns_accepted(self):
		sql = "SELECT name, full_name, email, department, designation FROM `tabEmployee`"
		ast = validate_sql_parser_ast(sql)
		self.assertTrue(validate_columns(ast))

	def test_stage_6_invalid_column_rejected(self):
		sql = "SELECT non_existent_column_xyz FROM `tabEmployee`"
		ast = validate_sql_parser_ast(sql)
		with self.assertRaises(ASTValidationError):
			validate_columns(ast)

	# -------------------------------------------------------------
	# STAGE 7: ENFORCE RBAC PROGRAMMATICALLY
	# -------------------------------------------------------------
	def test_stage_7_employee_role_injected_filter_on_tab_employee(self):
		sql = "SELECT name, full_name, basic_salary FROM `tabEmployee` WHERE status = 'Active'"
		ast = validate_sql_parser_ast(sql)
		ast = enforce_rbac(ast, user=self.employee_user, role="Employee", linked_emp=self.linked_emp)
		transpiled = ast.sql(dialect="mysql")

		# Programmatic filter MUST be injected into WHERE clause
		self.assertIn("tabEmployee.name = 'EMP-001'", transpiled)
		self.assertIn("status = 'Active'", transpiled)

	def test_stage_7_employee_role_injected_filter_on_salary_slip(self):
		sql = "SELECT name, employee, net_pay FROM `tabSalary Slip`"
		ast = validate_sql_parser_ast(sql)
		ast = enforce_rbac(ast, user=self.employee_user, role="Employee", linked_emp=self.linked_emp)
		transpiled = ast.sql(dialect="mysql")

		self.assertTrue("employee = 'EMP-001'" in transpiled)
		self.assertTrue("tabSalary Slip" in transpiled)


	def test_stage_7_employee_role_prohibited_from_payroll(self):
		sql = "SELECT payroll_title, total_amount FROM `tabPayroll`"
		ast = validate_sql_parser_ast(sql)
		with self.assertRaises(RBACViolationError):
			enforce_rbac(ast, user=self.employee_user, role="Employee", linked_emp=self.linked_emp)

	def test_stage_7_admin_role_not_restricted(self):
		sql = "SELECT name, full_name, basic_salary FROM `tabEmployee` WHERE status = 'Active'"
		ast = validate_sql_parser_ast(sql)
		ast = enforce_rbac(ast, user=self.admin_user, role="Administrator", linked_emp=None)
		transpiled = ast.sql(dialect="mysql")

		# Admin query should NOT have forced employee self-filter
		self.assertNotIn("tabEmployee.name = 'EMP-001'", transpiled)

	def test_stage_7_guest_user_rejected(self):
		sql = "SELECT name FROM `tabEmployee`"
		ast = validate_sql_parser_ast(sql)
		with self.assertRaises(RBACViolationError):
			enforce_rbac(ast, user="Guest", role="Guest")

	# -------------------------------------------------------------
	# STAGE 8: ADD SERVER-SIDE LIMIT
	# -------------------------------------------------------------
	def test_stage_8_injects_default_limit_when_missing(self):
		sql = "SELECT name, department_name FROM `tabDepartment`"
		ast = validate_sql_parser_ast(sql)
		ast = add_server_side_limit(ast, max_limit=MAX_SERVER_LIMIT)
		transpiled = ast.sql(dialect="mysql")
		self.assertIn(f"LIMIT {DEFAULT_SERVER_LIMIT}", transpiled)

	def test_stage_8_clamps_excessive_limit(self):
		sql = "SELECT name, department_name FROM `tabDepartment` LIMIT 1000"
		ast = validate_sql_parser_ast(sql)
		ast = add_server_side_limit(ast, max_limit=MAX_SERVER_LIMIT)
		transpiled = ast.sql(dialect="mysql")
		self.assertIn(f"LIMIT {MAX_SERVER_LIMIT}", transpiled)
		self.assertNotIn("LIMIT 1000", transpiled)

	def test_stage_8_preserves_smaller_limit(self):
		sql = "SELECT name, department_name FROM `tabDepartment` LIMIT 5"
		ast = validate_sql_parser_ast(sql)
		ast = add_server_side_limit(ast, max_limit=MAX_SERVER_LIMIT)
		transpiled = ast.sql(dialect="mysql")
		self.assertIn("LIMIT 5", transpiled)

	# -------------------------------------------------------------
	# STAGE 9 & 10: EXECUTE MARIADB & FULL END-TO-END PIPELINE
	# -------------------------------------------------------------
	def test_stage_9_and_10_full_pipeline_admin(self):
		raw_llm_json = """
		{
			"status": "sql",
			"sql": "SELECT name, department_name FROM `tabDepartment` ORDER BY department_name ASC",
			"explanation": "List all departments in alphabetical order"
		}
		"""
		result = process_llm_pipeline(raw_llm_json, user=self.admin_user, role="Administrator")
		self.assertTrue(result["success"])
		self.assertTrue(result["is_sql"])
		self.assertIn("tabDepartment", result["tables"])
		self.assertIn("executed_sql", result)
		self.assertIn("markdown", result)
		self.assertIn("```sql", result["markdown"])

	def test_full_pipeline_employee_prompt_injection_prevented(self):
		"""
		CRITICAL TEST:
		Even if the LLM output does NOT include a WHERE clause for EMP-001,
		or attempts to query all employee salaries, the server-side RBAC stage
		programmatically injects `tabEmployee.name = 'EMP-001'` into the AST!
		"""
		untrusted_llm_json = """
		{
			"status": "sql",
			"sql": "SELECT name, full_name, basic_salary FROM `tabEmployee` ORDER BY basic_salary DESC",
			"explanation": "List all company salaries"
		}
		"""
		result = process_llm_pipeline(
			untrusted_llm_json,
			user=self.employee_user,
			role="Employee",
			linked_emp=self.linked_emp
		)
		self.assertTrue(result["success"])
		executed_sql = result["executed_sql"]
		# Programmatic RBAC must be present in the executed MariaDB query
		self.assertIn("tabEmployee.name = 'EMP-001'", executed_sql)
		# Any records returned must strictly belong to EMP-001
		for row in result["data"]:
			self.assertEqual(row["name"], "EMP-001")

	def test_full_pipeline_clarification_response(self):
		clarification_json = """
		{
			"status": "clarification",
			"message": "Hello! You can ask me about employee records, departments, leaves, and salary slips."
		}
		"""
		result = process_llm_pipeline(clarification_json, user=self.admin_user, role="Administrator")
		self.assertTrue(result["success"])
		self.assertFalse(result["is_sql"])
		self.assertEqual(result["status"], "clarification")
		self.assertIn("Hello!", result["message"])


if __name__ == "__main__":
	runner = unittest.TextTestRunner(verbosity=2)
	suite = unittest.TestLoader().loadTestsFromTestCase(TestSQLGuardPipeline)
	test_result = runner.run(suite)
	sys.exit(0 if test_result.wasSuccessful() else 1)
