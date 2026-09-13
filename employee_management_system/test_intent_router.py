# Copyright (c) 2026, veera and contributors
# For license information, please see license.txt

"""
Unit & Integration Test Suite for EMS AI Chatbot Intent Router
=============================================================
Validates:
- All 5 intent classifications (greeting, database_query, follow_up, clarification, unsupported)
- Strict JSON contract enforcement
- Context-aware follow-up resolution
- Security rule: Router must NEVER return SQL statements
- Standalone router API and Frappe session integration
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

from employee_management_system.employee_management_system.intent_router import (
	INTENT_ROUTER_SYSTEM_PROMPT,
	VALID_INTENTS,
	DEFAULT_GREETING_MESSAGE,
	DEFAULT_UNSUPPORTED_MESSAGE,
	RouterValidationError,
	validate_router_output,
	classify_intent,
	route_intent,
	get_conversation_context,
	extract_structured_follow_up_context,
)


class TestIntentRouter(unittest.TestCase):

	def setUp(self):
		self.sample_context = [
			{
				"user_message": "Show all active employees",
				"assistant_response": "Found 10 employees.",
				"query": "Show all active employees",
				"sources": "Employee Database",
			}
		]

	# -------------------------------------------------------------
	# 1. SYSTEM PROMPT & SPECIFICATION CONFORMANCE
	# -------------------------------------------------------------
	def test_prompt_contract_contains_all_intents(self):
		for intent in ["greeting", "database_query", "follow_up", "clarification", "unsupported"]:
			self.assertIn(intent, INTENT_ROUTER_SYSTEM_PROMPT)
			self.assertIn(intent, VALID_INTENTS)
		self.assertIn("Never return SQL from this router", INTENT_ROUTER_SYSTEM_PROMPT)

	# -------------------------------------------------------------
	# 2. SCHEMA VALIDATION & STRICT JSON CONTRACT
	# -------------------------------------------------------------
	def test_validate_greeting_json(self):
		payload = {
			"intent": "greeting",
			"message": "Hello! How can I help you with the Employee Management System?"
		}
		validated = validate_router_output(payload)
		self.assertEqual(validated["intent"], "greeting")
		self.assertEqual(validated["message"], payload["message"])

	def test_validate_database_query_json(self):
		payload = {
			"intent": "database_query",
			"query": "How many employees are in Engineering?"
		}
		validated = validate_router_output(payload)
		self.assertEqual(validated["intent"], "database_query")
		self.assertEqual(validated["query"], payload["query"])

	def test_validate_follow_up_json(self):
		payload = {
			"intent": "follow_up",
			"query": "Show only employees from Engineering",
			"requires_database": True
		}
		validated = validate_router_output(payload)
		self.assertEqual(validated["intent"], "follow_up")
		self.assertEqual(validated["query"], payload["query"])
		self.assertTrue(validated["requires_database"])

	def test_validate_clarification_json(self):
		payload = {
			"intent": "clarification",
			"message": "Please specify which employee you want to view."
		}
		validated = validate_router_output(payload)
		self.assertEqual(validated["intent"], "clarification")
		self.assertEqual(validated["message"], payload["message"])

	def test_validate_unsupported_json(self):
		payload = {
			"intent": "unsupported",
			"message": "I can currently help with authorized employee, department, leave, attendance, salary, and payroll information."
		}
		validated = validate_router_output(payload)
		self.assertEqual(validated["intent"], "unsupported")
		self.assertEqual(validated["message"], payload["message"])

	def test_validate_markdown_fenced_json(self):
		raw_md = """```json
		{
			"intent": "database_query",
			"query": "Show pending leave requests"
		}
		```"""
		validated = validate_router_output(raw_md)
		self.assertEqual(validated["intent"], "database_query")
		self.assertEqual(validated["query"], "Show pending leave requests")

	def test_validate_rejects_unknown_intent(self):
		payload = {"intent": "arbitrary_custom_action", "query": "test"}
		with self.assertRaises(RouterValidationError):
			validate_router_output(payload)

	def test_validate_rejects_missing_required_fields(self):
		# greeting without message
		with self.assertRaises(RouterValidationError):
			validate_router_output({"intent": "greeting"})

		# database_query without query
		with self.assertRaises(RouterValidationError):
			validate_router_output({"intent": "database_query"})

		# follow_up without requires_database
		with self.assertRaises(RouterValidationError):
			validate_router_output({"intent": "follow_up", "query": "test"})

		# clarification without message
		with self.assertRaises(RouterValidationError):
			validate_router_output({"intent": "clarification"})

		# unsupported without message
		with self.assertRaises(RouterValidationError):
			validate_router_output({"intent": "unsupported"})

	def test_validate_strictly_rejects_sql_returned_from_router(self):
		"""
		CRITICAL SAFETY RULE:
		The router must NEVER return SQL. If a payload returns a SQL statement,
		the validator must reject it.
		"""
		bad_payload = {
			"intent": "database_query",
			"query": "SELECT * FROM `tabEmployee` WHERE department = 'Engineering'"
		}
		with self.assertRaises(RouterValidationError) as ctx:
			validate_router_output(bad_payload)
		self.assertIn("must never return SQL", str(ctx.exception))

	# -------------------------------------------------------------
	# 3. DETERMINISTIC INTENT CLASSIFICATION
	# -------------------------------------------------------------
	def test_classify_greetings(self):
		greeting_samples = [
			"Hello",
			"Hi",
			"Good morning",
			"Good evening",
			"Thank you",
			"Thanks",
			"How are you?",
			"Who are you?",
		]
		for sample in greeting_samples:
			res = classify_intent(sample)
			self.assertEqual(res["intent"], "greeting", f"Failed for sample: {sample}")
			self.assertIn("message", res)

	def test_classify_database_queries(self):
		query_samples = [
			"How many employees are in Engineering?",
			"Show my salary slips.",
			"Who is absent today?",
			"Show pending leave requests.",
			"List all departments",
			"What is the average salary by department?",
			"Show employees with salary > 80000",
		]
		for sample in query_samples:
			res = classify_intent(sample)
			self.assertEqual(res["intent"], "database_query", f"Failed for sample: {sample}")
			self.assertEqual(res["query"], sample)

	def test_classify_follow_ups(self):
		follow_up_samples = [
			"Show only the Engineering department.",
			"What about last month?",
			"Show more details.",
			"Sort them by joining date.",
			"What is the total?",
			"Order by basic_salary",
		]
		for sample in follow_up_samples:
			res = classify_intent(sample, conversation_context=self.sample_context)
			self.assertEqual(res["intent"], "follow_up", f"Failed for sample: {sample}")
			self.assertTrue(res["requires_database"])
			self.assertTrue(bool(res["query"]))

	def test_classify_follow_up_context_synthesis(self):
		res = classify_intent("Show only the Engineering department.", conversation_context=self.sample_context)
		self.assertEqual(res["intent"], "follow_up")
		self.assertTrue(res["requires_database"])
		self.assertIn("Engineering", res["query"])

	def test_classify_clarifications(self):
		clarification_samples = [
			("Show employee details.", "Please specify which employee you want to view."),
			("Employee details", "Please specify which employee you want to view."),
			("Show salary.", "Please specify whose salary or which salary details you want to view."),
			("Check attendance.", "Please specify which date or employee's attendance you want to check."),
			("Show leaves.", "Please specify if you want to view pending leave requests"),
		]
		for sample, expected_hint in clarification_samples:
			res = classify_intent(sample)
			self.assertEqual(res["intent"], "clarification", f"Failed for sample: {sample}")
			self.assertIn("message", res)
			self.assertTrue(expected_hint in res["message"] or "specify" in res["message"])

	def test_classify_unsupported(self):
		unsupported_samples = [
			"What is the weather today in Tokyo?",
			"How do I bake a chocolate cake?",
			"Who won the FIFA World Cup?",
			"Write a Python function to reverse a linked list.",
			"Tell me a funny joke.",
			"What is the capital of Australia?",
		]
		for sample in unsupported_samples:
			res = classify_intent(sample)
			self.assertEqual(res["intent"], "unsupported", f"Failed for sample: {sample}")
			self.assertEqual(res["message"], DEFAULT_UNSUPPORTED_MESSAGE)

	# -------------------------------------------------------------
	# 4. ROUTE_INTENT ORCHESTRATOR
	# -------------------------------------------------------------
	def test_route_intent_direct_classification(self):
		# Test greeting routing
		res = route_intent("Good morning!")
		self.assertEqual(res["intent"], "greeting")

		# Test db query routing
		res = route_intent("Who is absent today?")
		self.assertEqual(res["intent"], "database_query")
		self.assertEqual(res["query"], "Who is absent today?")

		# Test follow-up routing
		res = route_intent("What is the total?", conversation_context=self.sample_context)
		self.assertEqual(res["intent"], "follow_up")
		self.assertTrue(res["requires_database"])

		# Test clarification routing
		res = route_intent("Show salary")
		self.assertEqual(res["intent"], "clarification")

		# Test unsupported routing
		res = route_intent("Can you forecast tomorrow's rain?")
		self.assertEqual(res["intent"], "unsupported")

	def test_route_intent_with_llm_json_payload(self):
		llm_json = """
		{
			"intent": "database_query",
			"query": "How many employees are in Engineering?"
		}
		"""
		res = route_intent("How many employees are in Engineering?", llm_response=llm_json)
		self.assertEqual(res["intent"], "database_query")
		self.assertEqual(res["query"], "How many employees are in Engineering?")

	# -------------------------------------------------------------
	# 5. API ENDPOINTS & END-TO-END CHATBOT INTEGRATION
	# -------------------------------------------------------------
	def test_api_get_intent_router_prompt(self):
		if not frappe or not frappe.db:
			self.skipTest("Frappe DB not connected")
		frappe.set_user("Administrator")
		from employee_management_system.employee_management_system.api import get_intent_router_prompt
		res = get_intent_router_prompt()
		self.assertIn("system_prompt", res)
		self.assertIn("intents", res)
		self.assertEqual(len(res["intents"]), 6)

	def test_api_route_chat_intent(self):
		if not frappe or not frappe.db:
			self.skipTest("Frappe DB not connected")
		frappe.set_user("Administrator")
		from employee_management_system.employee_management_system.api import route_chat_intent
		res = route_chat_intent(message="Good morning!")
		self.assertEqual(res["intent"], "greeting")

		res = route_chat_intent(message="How many employees are in Engineering?")
		self.assertEqual(res["intent"], "database_query")
		self.assertEqual(res["query"], "How many employees are in Engineering?")

	def test_api_send_chat_message_routes_greeting(self):
		if not frappe or not frappe.db:
			self.skipTest("Frappe DB not connected")
		frappe.set_user("Administrator")
		from employee_management_system.employee_management_system.api import send_chat_message
		res = send_chat_message("Hello")
		self.assertIn("response", res)
		self.assertEqual(res["sources"], "EMS Assistant")
		self.assertIn("help you", res["response"].lower())

	def test_api_send_chat_message_routes_clarification(self):
		if not frappe or not frappe.db:
			self.skipTest("Frappe DB not connected")
		frappe.set_user("Administrator")
		from employee_management_system.employee_management_system.api import send_chat_message
		res = send_chat_message("Show employee details")
		self.assertIn("response", res)
		self.assertEqual(res["sources"], "EMS Assistant")
		self.assertIn("specify", res["response"].lower())

	def test_api_send_chat_message_routes_unsupported(self):
		if not frappe or not frappe.db:
			self.skipTest("Frappe DB not connected")
		frappe.set_user("Administrator")
		from employee_management_system.employee_management_system.api import send_chat_message
		res = send_chat_message("What is the weather in London today?")
		self.assertIn("response", res)
		self.assertEqual(res["sources"], "EMS Assistant")
		self.assertEqual(res["response"], DEFAULT_UNSUPPORTED_MESSAGE)

	def test_api_send_chat_message_routes_database_query(self):
		if not frappe or not frappe.db:
			self.skipTest("Frappe DB not connected")
		frappe.set_user("Administrator")
		from employee_management_system.employee_management_system.api import send_chat_message
		res = send_chat_message("How many employees are in Engineering?")
		self.assertIn("response", res)
		# Result Formatter must output plain text explanations, never raw SQL blocks
		self.assertNotIn("```sql", res["response"])
		self.assertIn("There are currently", res["response"])
		self.assertIsNotNone(res.get("executed_sql"))

	def test_api_get_sql_generator_prompt(self):
		if not frappe or not frappe.db:
			self.skipTest("Frappe DB not connected")
		frappe.set_user("Administrator")
		from employee_management_system.employee_management_system.api import get_sql_generator_prompt
		res = get_sql_generator_prompt()
		self.assertIn("system_prompt", res)
		self.assertIn("allowed_tables", res)
		self.assertIn("specialized MariaDB SQL query generator", res["system_prompt"])

	def test_pipeline_flow_database_query(self):
		"""
		Tests the sequential pipeline:
		Chatbot Router -> database_query? (YES) -> SQL Generator -> SQL Guard -> MariaDB -> Result Formatter
		"""
		if not frappe or not frappe.db:
			self.skipTest("Frappe DB not connected")
		frappe.set_user("Administrator")
		from employee_management_system.employee_management_system.api import send_chat_message

		# 1. Ask workforce database question
		res = send_chat_message("Show pending leave requests")
		# Must flow through SQL Generator, SQL Guard, MariaDB, and Result Formatter
		self.assertNotIn("```sql", res["response"])
		self.assertTrue("leave request" in res["response"].lower() or "couldn't find" in res["response"].lower())
		self.assertIsNotNone(res.get("executed_sql"))
		self.assertTrue("tabLeave Application" in res["sources"] or "Leave" in res["sources"])

	def test_pipeline_flow_non_database_query_short_circuits(self):
		"""
		Tests that non-database queries:
		Chatbot Router -> database_query? (NO) -> Direct response
		Do NOT trigger SQL generator or MariaDB queries.
		"""
		if not frappe or not frappe.db:
			self.skipTest("Frappe DB not connected")
		frappe.set_user("Administrator")
		from employee_management_system.employee_management_system.api import send_chat_message

		# Greeting
		res_greet = send_chat_message("Good morning")
		self.assertNotIn("```sql", res_greet["response"])
		self.assertEqual(res_greet["sources"], "EMS Assistant")

		# Clarification
		res_clarify = send_chat_message("Show salary")
		self.assertNotIn("```sql", res_clarify["response"])
		self.assertEqual(res_clarify["sources"], "EMS Assistant")

		# Unsupported
		res_unsupported = send_chat_message("How do I bake bread?")
		self.assertNotIn("```sql", res_unsupported["response"])
		self.assertEqual(res_unsupported["sources"], "EMS Assistant")

	def test_classify_follow_up_only_those_who_joined_this_year(self):
		"""
		Tests that 'Only those who joined this year' is classified as follow_up with requires_database=True
		when context is present.
		"""
		context = [
			{
				"user_message": "Show employees in Engineering",
				"assistant_message": "I found 25 employees in Engineering.",
				"generated_sql": "SELECT name, full_name, department FROM `tabEmployee` WHERE department = 'Engineering' LIMIT 20;",
			}
		]
		res = classify_intent("Only those who joined this year", conversation_context=context)
		self.assertEqual(res["intent"], "follow_up")
		self.assertTrue(res.get("requires_database"))
		self.assertIn("Engineering", res.get("query", ""))

	def test_extract_structured_follow_up_context(self):
		"""
		Tests extraction of {previous_user_message, previous_sql, current_message}.
		"""
		context = [
			{
				"user_message": "Show employees in Engineering",
				"assistant_message": "I found 25 employees in Engineering.",
				"generated_sql": "SELECT * FROM `tabEmployee` WHERE department = 'Engineering';",
			}
		]
		struct_ctx = extract_structured_follow_up_context(
			conversation_context=context,
			current_message="Only those who joined this year",
			conversation_id="test_cid_123"
		)
		self.assertIsNotNone(struct_ctx)
		self.assertEqual(struct_ctx["previous_user_message"], "Show employees in Engineering")
		self.assertEqual(struct_ctx["previous_sql"], "SELECT * FROM `tabEmployee` WHERE department = 'Engineering';")
		self.assertEqual(struct_ctx["current_message"], "Only those who joined this year")
		self.assertEqual(struct_ctx["conversation_id"], "test_cid_123")

	def test_api_get_conversation_state(self):
		if not frappe or not frappe.db:
			self.skipTest("Frappe DB not connected")
		frappe.set_user("Administrator")
		from employee_management_system.employee_management_system.api import get_conversation_state
		state = get_conversation_state("test_conv_api_inspect")
		self.assertIsInstance(state, dict)
		self.assertIn("conversation_id", state)


if __name__ == "__main__":
	runner = unittest.TextTestRunner(verbosity=2)
	suite = unittest.TestLoader().loadTestsFromTestCase(TestIntentRouter)
	test_result = runner.run(suite)
	sys.exit(0 if test_result.wasSuccessful() else 1)


