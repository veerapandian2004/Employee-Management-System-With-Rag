# Copyright (c) 2026, veera and contributors
# For license information, please see license.txt

"""
Unit & Integration Test Suite for CHAT ORCHESTRATOR & Chat History Persistence
==============================================================================
Validates:
- Complete Chat Orchestrator pipeline
- Exact schema for tabChat Message:
  name, user, role, conversation_id, message_type, user_message,
  assistant_message, generated_sql, query_status, created_at
- Recommended message_type values:
  user, assistant, sql, error, clarification
- SQL Guard 3 pillars: AST Check, RBAC Filter, LIMIT
- Retrieval via get_chat_history API
"""

import os
import sys
import unittest

app_root = "/home/tui013/frappe-benchv/apps/employee_management_system"
if app_root in sys.path:
	sys.path.remove(app_root)
sys.path.insert(0, app_root)
cur_dir = os.path.dirname(os.path.abspath(__file__))
if cur_dir in sys.path:
	sys.path.remove(cur_dir)

# Ensure frappe environment is initialized when running with bench python
try:
	import frappe
	if not frappe.db:
		frappe.init(site="hospital.localhost")
		frappe.connect()
except Exception:
	pass

from employee_management_system.employee_management_system.orchestrator import (
	ChatOrchestrator,
	orchestrate_chat_message,
	generate_sql_for_question,
	combine_follow_up_sql,
	save_chat_message_record,
	get_structured_conversation_state,
	set_structured_conversation_state,
)
from employee_management_system.employee_management_system.intent_router import (
	get_conversation_context,
	extract_structured_follow_up_context,
)
from employee_management_system.employee_management_system.sql_guard import (
	ast_check,
	rbac_filter,
	limit_filter,
	run_sql_guard,
)
from employee_management_system.employee_management_system.api import (
	send_chat_message,
	get_chat_history,
	save_chat_message,
	get_conversation_state,
)


class TestChatOrchestrator(unittest.TestCase):

	def setUp(self):
		if frappe and frappe.db:
			frappe.set_user("Administrator")

	# -------------------------------------------------------------
	# 1. ORCHESTRATOR BRANCH 1: GREETING -> DIRECT RESPONSE
	# -------------------------------------------------------------
	def test_orchestrator_greeting_direct_response(self):
		orchestrator = ChatOrchestrator(user="Administrator", role="Administrator")
		res = orchestrator.orchestrate("Good morning!")
		self.assertIn("response", res)
		self.assertIn("help you", res["response"].lower())
		self.assertIsNone(res["executed_sql"])
		self.assertEqual(res["sources"], "EMS Assistant")
		self.assertEqual(res["message_type"], "assistant")
		self.assertEqual(res["query_status"], "not_applicable")

	# -------------------------------------------------------------
	# 2. ORCHESTRATOR BRANCH 2: CLARIFICATION -> DIRECT RESPONSE
	# -------------------------------------------------------------
	def test_orchestrator_clarification_direct_response(self):
		orchestrator = ChatOrchestrator(user="Administrator", role="Administrator")
		res = orchestrator.orchestrate("Show employee details")
		self.assertIn("response", res)
		self.assertIn("specify", res["response"].lower())
		self.assertIsNone(res["executed_sql"])
		self.assertEqual(res["sources"], "EMS Assistant")
		self.assertEqual(res["message_type"], "clarification")
		self.assertEqual(res["query_status"], "clarification")

	def test_orchestrator_unsupported_direct_response(self):
		orchestrator = ChatOrchestrator(user="Administrator", role="Administrator")
		res = orchestrator.orchestrate("What is the recipe for chocolate cake?")
		self.assertIn("response", res)
		self.assertIn("authorized employee", res["response"].lower())
		self.assertIsNone(res["executed_sql"])
		self.assertEqual(res["sources"], "EMS Assistant")
		self.assertEqual(res["message_type"], "clarification")

	# -------------------------------------------------------------
	# 3. ORCHESTRATOR BRANCH 3: DATABASE -> SQL GENERATOR -> SQL GUARD
	#                          -> MARIADB -> RESULT FORMATTER
	# -------------------------------------------------------------
	def test_orchestrator_database_full_pipeline(self):
		orchestrator = ChatOrchestrator(user="Administrator", role="Administrator")
		res = orchestrator.orchestrate("How many employees are in Engineering?")
		self.assertIn("response", res)
		# Result Formatter explanation
		self.assertIn("There are currently", res["response"])
		self.assertIsNotNone(res["executed_sql"])
		self.assertIn("SELECT", res["executed_sql"].upper())
		self.assertIn("tabEmployee", res["executed_sql"])
		self.assertEqual(res["message_type"], "sql")
		self.assertEqual(res["query_status"], "success")

	# -------------------------------------------------------------
	# 4. SQL GUARD 3 PILLARS: AST CHECK, RBAC FILTER, LIMIT
	# -------------------------------------------------------------
	def test_sql_guard_ast_check(self):
		sql = "SELECT name, full_name FROM `tabEmployee` WHERE status = 'Active'"
		ast, tables = ast_check(sql)
		self.assertIn("tabEmployee", tables)

	def test_sql_guard_rbac_filter_employee(self):
		sql = "SELECT name, full_name FROM `tabEmployee`"
		ast, _ = ast_check(sql)
		guarded_ast = rbac_filter(ast, user="test@ems.com", role="Employee", linked_emp={"name": "EMP-0005"})
		final_sql = guarded_ast.sql(dialect="mysql")
		self.assertIn("EMP-0005", final_sql)

	def test_sql_guard_limit_filter(self):
		sql = "SELECT name FROM `tabEmployee`"
		ast, _ = ast_check(sql)
		guarded_ast = limit_filter(ast)
		final_sql = guarded_ast.sql(dialect="mysql")
		self.assertIn("LIMIT 20", final_sql)

	def test_sql_guard_run_sql_guard_full(self):
		sql = "SELECT name, full_name FROM `tabEmployee` LIMIT 5"
		exec_res = run_sql_guard(sql, user="Administrator", role="Administrator")
		self.assertIn("executed_sql", exec_res)
		self.assertIn("rows", exec_res)
		self.assertTrue(isinstance(exec_res["rows"], list))

	# -------------------------------------------------------------
	# 5. TABCHAT MESSAGE SCHEMA VALIDATION
	# -------------------------------------------------------------
	def test_tab_chat_message_schema_columns(self):
		if not frappe or not frappe.db or not frappe.db.table_exists("Chat Message"):
			self.skipTest("tabChat Message table not available")

		columns = [c[0] for c in frappe.db.sql("DESC `tabChat Message`")]
		expected_fields = [
			"name",
			"user",
			"role",
			"conversation_id",
			"message_type",
			"user_message",
			"assistant_message",
			"generated_sql",
			"query_status",
			"created_at",
		]
		for ef in expected_fields:
			self.assertIn(ef, columns, f"Expected column '{ef}' in tabChat Message")

	# -------------------------------------------------------------
	# 6. PERSISTENCE IN tabChat Message WITH UPDATED SCHEMA
	# -------------------------------------------------------------
	def test_orchestrator_persists_all_fields_to_tab_chat_message(self):
		if not frappe or not frappe.db or not frappe.db.table_exists("Chat Message"):
			self.skipTest("tabChat Message table not available")

		unique_msg = f"Testing schema persistence {frappe.utils.now()}"
		unique_cid = f"test_conv_{frappe.generate_hash(length=8)}"
		res = send_chat_message(unique_msg, conversation_id=unique_cid)

		# Query MariaDB directly to verify tabChat Message row exists and contains all fields
		last_msg = frappe.db.sql(
			"""
			SELECT name, user, role, conversation_id, message_type, user_message, 
			       assistant_message, generated_sql, query_status, created_at
			FROM `tabChat Message` 
			WHERE user_message = %s 
			ORDER BY creation DESC LIMIT 1
			""",
			(unique_msg,),
			as_dict=True,
		)
		self.assertTrue(len(last_msg) > 0, "Expected chat message to be saved to tabChat Message")
		row = last_msg[0]
		self.assertEqual(row["user"], "Administrator")
		self.assertEqual(row["conversation_id"], unique_cid)
		self.assertEqual(row["user_message"], unique_msg)
		self.assertEqual(row["assistant_message"], res["response"])
		self.assertIsNotNone(row["message_type"])
		self.assertIsNotNone(row["query_status"])
		self.assertIsNotNone(row["created_at"])

	# -------------------------------------------------------------
	# 7. RECOMMENDED MESSAGE TYPES: user, assistant, sql, error, clarification
	# -------------------------------------------------------------
	def test_save_chat_message_all_recommended_types(self):
		if not frappe or not frappe.db or not frappe.db.table_exists("Chat Message"):
			self.skipTest("tabChat Message table not available")

		for m_type in ["user", "assistant", "sql", "error", "clarification"]:
			doc = save_chat_message_record(
				user="Administrator",
				role="Administrator",
				conversation_id="test_types_conv",
				message_type=m_type,
				user_message=f"Test message for {m_type}",
				assistant_message=f"Response for {m_type}",
				generated_sql="SELECT 1;" if m_type in ("sql", "error") else None,
				query_status="error" if m_type == "error" else "success",
			)
			self.assertIsNotNone(doc)
			self.assertEqual(doc.message_type, m_type)

	# -------------------------------------------------------------
	# 8. API GET CHAT HISTORY RETURNS ALL SCHEMA FIELDS
	# -------------------------------------------------------------
	def test_api_get_chat_history_returns_all_schema_fields(self):
		if not frappe or not frappe.db or not frappe.db.table_exists("Chat Message"):
			self.skipTest("tabChat Message table not available")

		history = get_chat_history()
		self.assertTrue(isinstance(history, list))
		if history:
			first = history[0]
			for fld in [
				"name", "user", "role", "conversation_id", "message_type",
				"user_message", "assistant_message", "generated_sql", "query_status", "created_at"
			]:
				self.assertIn(fld, first, f"Field '{fld}' missing from get_chat_history payload")

	# -------------------------------------------------------------
	# 9. FOLLOW-UP SQL CONDITION COMBINATION: Engineering & Joined This Year
	# -------------------------------------------------------------
	def test_follow_up_sql_condition_combination_engineering_joined_this_year(self):
		follow_up_ctx = {
			"previous_user_message": "Show employees in Engineering",
			"previous_sql": "SELECT name, full_name, designation, department, email, phone, status, basic_salary FROM `tabEmployee` WHERE department = 'Engineering' ORDER BY full_name ASC LIMIT 20;",
			"current_message": "Only those who joined this year"
		}
		combined_sql, table = generate_sql_for_question(
			message="Only those who joined this year",
			user="Administrator",
			role="Administrator",
			follow_up_context=follow_up_ctx
		)
		self.assertEqual(table, "tabEmployee")
		self.assertIn("tabEmployee", combined_sql)
		# Both conditions combined with AND
		self.assertIn("department = 'Engineering'", combined_sql)
		self.assertIn("YEAR(date_of_joining) = YEAR(CURDATE())", combined_sql)
		self.assertIn("date_of_joining", combined_sql)

	# -------------------------------------------------------------
	# 10. FOLLOW-UP SQL CONDITION COMBINATION: Leave Requests
	# -------------------------------------------------------------
	def test_follow_up_sql_condition_combination_leaves(self):
		follow_up_ctx = {
			"previous_user_message": "Show pending leave requests",
			"previous_sql": "SELECT name, employee, leave_type, from_date, to_date, total_days, status FROM `tabLeave Application` WHERE status = 'Pending' ORDER BY creation DESC LIMIT 15;",
			"current_message": "Only for Sick Leave"
		}
		combined_sql, table = generate_sql_for_question(
			message="Only for Sick Leave",
			user="Administrator",
			role="Administrator",
			follow_up_context=follow_up_ctx
		)
		self.assertEqual(table, "tabLeave Application")
		self.assertIn("status = 'Pending'", combined_sql)
		self.assertIn("leave_type = 'Sick Leave'", combined_sql)

	# -------------------------------------------------------------
	# 11. STRUCTURED CONVERSATION STATE CACHING & RETRIEVAL
	# -------------------------------------------------------------
	def test_structured_conversation_state_caching(self):
		cid = "conv_test_structured_state_999"
		test_state = {
			"conversation_id": cid,
			"user": "Administrator",
			"last_user_message": "Show employees in Engineering",
			"last_sql": "SELECT * FROM `tabEmployee` WHERE department = 'Engineering'",
			"last_assistant_message": "I found 25 employees in Engineering.",
			"updated_at": "2026-09-08 12:00:00"
		}
		set_structured_conversation_state(cid, test_state)
		retrieved = get_structured_conversation_state(cid, user="Administrator")
		self.assertEqual(retrieved.get("last_user_message"), "Show employees in Engineering")
		self.assertIn("Engineering", retrieved.get("last_sql", ""))

	# -------------------------------------------------------------
	# 12. BOUNDED CONTEXT WINDOW ENFORCEMENT (MAX 10 MESSAGES)
	# -------------------------------------------------------------
	def test_bounded_context_window_enforcement(self):
		# Even if a user asks for 100 messages, the system bounds it to max 10
		bounded = get_conversation_context(user="Administrator", limit=100)
		self.assertLessEqual(len(bounded), 10)

	# -------------------------------------------------------------
	# 13. END-TO-END MULTI-TURN ORCHESTRATION WITH FOLLOW-UP REFINEMENT
	# -------------------------------------------------------------
	def test_end_to_end_follow_up_conversation_multi_turn(self):
		import uuid
		cid = f"conv_multiturn_{uuid.uuid4().hex[:8]}"
		orchestrator = ChatOrchestrator(user="Administrator", role="Administrator", conversation_id=cid)

		# Turn 1: Initial query
		res1 = orchestrator.orchestrate("Show employees in Engineering", conversation_id=cid)
		self.assertEqual(res1["message_type"], "sql")
		self.assertIn("tabEmployee", res1["executed_sql"])
		self.assertIn("department = 'Engineering'", res1["executed_sql"])

		# Turn 2: Follow-up query referring back to "those"
		res2 = orchestrator.orchestrate("Only those who joined this year", conversation_id=cid)
		self.assertEqual(res2["message_type"], "sql")
		self.assertIn("tabEmployee", res2["executed_sql"])
		self.assertIn("department = 'Engineering'", res2["executed_sql"])
		self.assertIn("YEAR(date_of_joining)", res2["executed_sql"])

	# -------------------------------------------------------------
	# 14. EMPLOYEE NAME PATTERN MATCHING (STARTS WITH / BEGINS WITH)
	# -------------------------------------------------------------
	def test_name_pattern_matching_starts_with(self):
		sql, table = generate_sql_for_question("list out the employee name whose name start with 'h'", user="hr@ems.com", role="HR")
		self.assertEqual(table, "tabEmployee")
		self.assertIn("full_name LIKE 'h%'", sql)

		sql_s, table_s = generate_sql_for_question("employees whose name starts with 's'", user="hr@ems.com", role="HR")
		self.assertEqual(table_s, "tabEmployee")
		self.assertIn("full_name LIKE 's%'", sql_s)


if __name__ == "__main__":
	runner = unittest.TextTestRunner(verbosity=2)
	suite = unittest.TestLoader().loadTestsFromTestCase(TestChatOrchestrator)
	test_result = runner.run(suite)
	sys.exit(0 if test_result.wasSuccessful() else 1)

