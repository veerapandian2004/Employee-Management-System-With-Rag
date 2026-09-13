# Copyright (c) 2026, veera and contributors
# For license information, please see license.txt

"""
EMS AI Chatbot Intent Router
============================
The conversation router for the Employee Management System AI Assistant.
Understands user messages and determines how the system should respond.

Key Design Principles:
- Does NOT execute SQL.
- Does NOT enforce permissions (handled downstream by sql_guard.py).
- Classifies requests into strict JSON.
- Never returns SQL from this router.

Available Intent Types:
1. greeting
2. database_query
3. follow_up
4. clarification
5. unsupported
"""

import json
import re
from typing import Any, Dict, List, Optional, Union

# Optional frappe import for runtime context retrieval
try:
	import frappe
except ImportError:
	frappe = None


# =====================================================================
# 1. INTENT ROUTER SYSTEM PROMPT CONTRACT
# =====================================================================

INTENT_ROUTER_SYSTEM_PROMPT = """# EMS AI Chatbot Intent Router

You are the conversation router for the Employee Management System AI Assistant.

Your responsibility is to understand the user's message and determine how the system should respond.

You do NOT execute SQL.

You do NOT enforce permissions.

You classify the request and return strict JSON.

## Available Intent Types

Classify every message into one of the following intents:

### 1. greeting

Use for:
* Hello
* Hi
* Good morning
* Thank you
* General conversation

### 2. database_query

Use when the user requests information that must be retrieved from the Employee Management System database.

Examples:
Use when the user requests structured workforce records from MariaDB tables:
* How many employees are in Engineering?
* Show my salary slips.
* Who is absent today?
* Show pending leave requests.

### 3. follow_up
Role: Triggers the SQL Engine (Text-to-SQL + SQL Guard + MariaDB).
Rule: Never use embeddings to retrieve SQL rows.

### 3. knowledge_query

Use when the user asks about unstructured organizational knowledge, policies, or employee handbooks:
* What is the policy on remote work and flexible hours?
* How does travel expense reimbursement work?
* Explain the code of conduct and anti-harassment policy.
* What are the carry forward rules for annual leave in the handbook?
* What wellness and health benefits are offered?

Role: Triggers the Embeddings Engine (semantic vector search over policy documents).
Rule: Never use SQL to retrieve unstructured knowledge.

### 4. follow_up

Use when the user refers to previous conversation context or previous query results.

Examples:
* Show only the Engineering department.
* What about last month?
* Show more details.
* Sort them by joining date.
* What is the total?

### 4. clarification
### 5. clarification

Use when the user's request is ambiguous and cannot reliably be converted into a database query.
Use when the user's request is ambiguous and cannot reliably be converted into a query.

Examples:
* Show employee details.
* Show salary.
* Check attendance.

### 5. unsupported
### 6. unsupported

Use when the request is unrelated to the Employee Management System.

## Conversation Context Rules

You may receive:
* Previous user messages
* Previous SQL queries
* Previous database results
* Previous assistant responses

Use conversation context only to understand follow-up questions.

Do not treat previous results as permanently accurate.

If a follow-up requires fresh database data, classify it as `database_query` or `follow_up` and allow the backend to execute a new query.

## Response Format

Return JSON only.

For general conversation:
{
  "intent": "greeting",
  "message": "Hello! How can I help you with the Employee Management System?"
}

For a database request:
For a structured database request (SQL):
{
  "intent": "database_query",
  "query": "How many employees are in Engineering?"
}

For an unstructured knowledge request (Embeddings):
{
  "intent": "knowledge_query",
  "query": "What is the policy for working from home?"
}

For a follow-up:
{
  "intent": "follow_up",
  "query": "Show only employees from Engineering",
  "requires_database": true
}

For clarification:
{
  "intent": "clarification",
  "message": "Please specify which employee you want to view."
}

For unsupported requests:
{
  "intent": "unsupported",
  "message": "I can currently help with authorized employee, department, leave, attendance, salary, and payroll information."
  "message": "I can currently help with authorized employee, department, leave, attendance, salary, and payroll information, as well as company policies and handbooks."
}

Never return SQL from this router.
"""

VALID_INTENTS = {
	"greeting",
	"database_query",
	"knowledge_query",
	"follow_up",
	"clarification",
	"unsupported",
}

DEFAULT_GREETING_MESSAGE = "Hello! How can I help you with the Employee Management System?"
DEFAULT_UNSUPPORTED_MESSAGE = (
	"I can currently help with authorized employee, department, leave, attendance, salary, and payroll information."
	"I can currently help with authorized employee, department, leave, attendance, salary, and payroll information, as well as company policies and handbooks."
)


# =====================================================================
# 2. CUSTOM EXCEPTIONS
# =====================================================================

class RouterValidationError(Exception):
	"""Raised when router output fails schema validation or security constraints."""
	def __init__(self, message: str, code: str = "ROUTER_VALIDATION_ERROR"):
		super().__init__(message)
		self.message = message
		self.code = code


# =====================================================================
# 3. SCHEMA VALIDATION & OUTPUT ENFORCEMENT
# =====================================================================

SQL_KEYWORDS_PATTERN = re.compile(
	r"^\s*(SELECT\b|INSERT\b|UPDATE\b|DELETE\b|DROP\b|ALTER\b|CREATE\b|SHOW\s+TABLES|SHOW\s+COLUMNS|TRUNCATE\b|REPLACE\b)",
	re.IGNORECASE,
)


def validate_router_output(raw_output: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
	"""
	Parses and strictly validates the router JSON output against the specification.
	
	Enforces:
	1. Valid JSON object (strips markdown codeblock wrappers).
	2. 'intent' must be one of: greeting, database_query, follow_up, clarification, unsupported.
	3. Never returns SQL from this router (rejects SQL queries in any response field).
	4. Required fields per intent:
	   - greeting: 'message'
	   - database_query: 'query'
	   - follow_up: 'query', 'requires_database' (boolean)
	   - clarification: 'message'
	   - unsupported: 'message'
	"""
	if isinstance(raw_output, dict):
		data = raw_output
	elif isinstance(raw_output, str):
		cleaned = raw_output.strip()
		# Strip markdown codeblocks if present
		if cleaned.startswith("```"):
			lines = cleaned.splitlines()
			if lines and lines[0].startswith("```"):
				lines = lines[1:]
			if lines and lines[-1].strip() == "```":
				lines = lines[:-1]
			cleaned = "\n".join(lines).strip()

		# Extract JSON boundary
		if not cleaned.startswith("{"):
			start_idx = cleaned.find("{")
			end_idx = cleaned.rfind("}")
			if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
				cleaned = cleaned[start_idx : end_idx + 1]

		try:
			data = json.loads(cleaned)
		except json.JSONDecodeError as e:
			raise RouterValidationError(f"Invalid JSON format in router response: {str(e)}")
	else:
		raise RouterValidationError(f"Expected dict or string, received: {type(raw_output).__name__}")

	if not isinstance(data, dict):
		raise RouterValidationError("Router response must be a JSON object dictionary.")

	# Validate 'intent' field
	intent = data.get("intent")
	if not intent:
		raise RouterValidationError("Missing required 'intent' field in router response.")

	if intent not in VALID_INTENTS:
		raise RouterValidationError(
			f"Invalid intent '{intent}'. Must be one of: {', '.join(sorted(VALID_INTENTS))}."
		)

	# Safety Rule: NEVER return SQL from this router
	for field in ("query", "message"):
		val = data.get(field)
		if isinstance(val, str) and SQL_KEYWORDS_PATTERN.search(val.strip()):
			raise RouterValidationError(
				f"Router violation: Detected raw SQL query in field '{field}'. "
				"The Intent Router must never return SQL."
			)

	# Validate required fields per intent
	if intent == "greeting":
		if not data.get("message") or not isinstance(data["message"], str):
			raise RouterValidationError("Intent 'greeting' requires a non-empty 'message' string.")
		return {"intent": "greeting", "message": data["message"].strip()}

	elif intent == "database_query":
		if not data.get("query") or not isinstance(data["query"], str):
			raise RouterValidationError("Intent 'database_query' requires a non-empty 'query' string.")
		return {"intent": "database_query", "query": data["query"].strip()}

	elif intent == "knowledge_query":
		if not data.get("query") or not isinstance(data["query"], str):
			raise RouterValidationError("Intent 'knowledge_query' requires a non-empty 'query' string.")
		return {"intent": "knowledge_query", "query": data["query"].strip()}

	elif intent == "follow_up":
		if not data.get("query") or not isinstance(data["query"], str):
			raise RouterValidationError("Intent 'follow_up' requires a non-empty 'query' string.")
		if "requires_database" not in data or not isinstance(data["requires_database"], bool):
			raise RouterValidationError(
				"Intent 'follow_up' requires a boolean 'requires_database' field (true/false)."
			)
		return {
			"intent": "follow_up",
			"query": data["query"].strip(),
			"requires_database": data["requires_database"],
		}

	elif intent == "clarification":
		if not data.get("message") or not isinstance(data["message"], str):
			raise RouterValidationError("Intent 'clarification' requires a non-empty 'message' string.")
		return {"intent": "clarification", "message": data["message"].strip()}

	elif intent == "unsupported":
		if not data.get("message") or not isinstance(data["message"], str):
			raise RouterValidationError("Intent 'unsupported' requires a non-empty 'message' string.")
		return {"intent": "unsupported", "message": data["message"].strip()}

	return data


# =====================================================================
# 4. DETERMINISTIC INTENT CLASSIFIER & CONTEXT RESOLVER
# =====================================================================

GREETING_PATTERNS = [
	r"^\s*(hi|hello|hey|hiya|hola|howdy)\b",
	r"^\s*good\s+(morning|afternoon|evening|day)\b",
	r"^\s*(thank\s+you|thanks|thx|thank\s+you\s+so\s+much|thanks\s+a\s+lot)\b",
	r"^\s*who\s+are\s+you\b",
	r"^\s*what\s+can\s+you\s+do\b",
	r"^\s*how\s+are\s+you\b",
	r"^\s*help\b",
]

AMBIGUOUS_CLARIFICATION_PATTERNS = [
	(
		r"^\s*(?:show|get|view|display|check|list)?\s*(?:an?\s+)?employee\s*(?:details?|profile|info|information)?\s*$",
		"Please specify which employee you want to view.",
	),
	(
		r"^\s*(?:show|check|view|display|get)?\s*salary\s*$",
		"Please specify whose salary or which salary details you want to view.",
	),
	(
		r"^\s*(?:check|show|view|get|display)?\s*attendance\s*$",
		"Please specify which date or employee's attendance you want to check.",
	),
	(
		r"^\s*(?:check|show|view|get|display)?\s*leaves?\s*$",
		"Please specify if you want to view pending leave requests, leave balances, or a specific employee's leaves.",
	),
	(
		r"^\s*(?:check|show|view|get|display)?\s*(?:department|departments)\s*$",
		"Please specify if you would like to list all departments, view department heads, or see employee counts per department.",
	),
]

STANDALONE_FOLLOW_UPS = [
	r"^\s*show\s+only\b",
	r"^\s*only\b",
	r"^\s*just\s+(?:the\s+|those\s+)?",
	r"^\s*those\s+who\b",
	r"^\s*who\s+joined\b",
	r"^\s*joined\s+this\s+year\b",
	r"^\s*joined\s+last\s+year\b",
	r"^\s*joined\s+in\b",
	r"^\s*who\s+are\b",
	r"^\s*filter(?:ed)?\s+by\b",
	r"^\s*what\s+about\s+last\s+(?:month|year|week|quarter)\b",
	r"^\s*what\s+about\s+yesterday\b",
	r"^\s*what\s+about\s+today\b",
	r"^\s*show\s+more\s+details\b",
	r"^\s*more\s+details\b",
	r"^\s*expand\s+details\b",
	r"^\s*sort\s+(?:them\s+)?by\b",
	r"^\s*order\s+(?:them\s+)?by\b",
	r"^\s*what\s+is\s+the\s+total\s*$",
	r"^\s*what\s+is\s+the\s+count\s*$",
	r"^\s*what\s+is\s+the\s+average\s*$",
	r"^\s*what\s+is\s+the\s+sum\s*$",
]

KNOWLEDGE_PATTERNS = [
	r"\b(?:company\s+|hr\s+|corporate\s+)?polic(?:y|ies)\b",
	r"\bhandbooks?\b",
	r"\bguidelines?\b",
	r"\bcode\s+of\s+conduct\b",
	r"\bworkplace\s+ethics\b",
	r"\banti[- ]harassment\b",
	r"\bwhistleblower\b",
	r"\bremote\s+work\b",
	r"\bwork\s+from\s+home\b",
	r"\bwfh\b",
	r"\bflexible\s+hours\b",
	r"\bcore\s+hours\b",
	r"\btravel\s+(?:and\s+)?expense\b",
	r"\bexpense\s+reimbursement\b",
	r"\btravel\s+reimbursement\b",
	r"\bmeal\s+allowance\b",
	r"\bper\s+diem\b",
	r"\bhotel\s+booking\b",
	r"\bcarry\s+forward\b",
	r"\bleave\s+encashment\b",
	r"\bwellness\s+(?:program|benefits?)\b",
	r"\bhealth\s+(?:and\s+)?wellness\b",
	r"\bbenefits\s+guide\b",
	r"\bmedical\s+(?:coverage|insurance)\b",
	r"\bparental\s+leave\b",
	r"\bmaternity\s+leave\b",
	r"\bpaternity\s+leave\b",
	r"\bbereavement\s+leave\b",
	r"\brules?\s+for\s+(?:annual\s+|sick\s+|casual\s+)?leave\b",
	r"\bclaim\s+reimbursement\b",
	r"\breimbursement\s+(?:process|rules?|limit|procedure|guideline)\b",
]

EMS_DOMAIN_KEYWORDS = [
	"employee", "employees", "staff", "worker", "workers", "colleague", "colleagues",
	"department", "departments", "dept", "depts", "cost center",
	"leave", "leaves", "vacation", "holiday", "sick leave", "casual leave", "time off",
	"salary", "salaries", "slip", "slips", "paystub", "paystubs", "payroll", "payrolls",
	"hra", "allowance", "allowances", "deduction", "deductions", "gross", "net",
	"attendance", "present", "absent", "half day", "check-in", "check in", "clock in",
	"manager", "reporting manager", "designation", "role", "hire", "joined", "joining",
	"disbursement", "outflow", "headcount", "active", "terminated", "suspended",
]

UNSUPPORTED_KEYWORDS = [
	"weather", "forecast", "temperature", "rain", "recipe", "cook", "bake", "cake",
	"movie", "film", "actor", "actress", "song", "music", "lyrics",
	"football", "cricket", "basketball", "world cup", "olympics", "match score",
	"president", "prime minister", "election", "stock market", "crypto", "bitcoin",
	"poem", "poetry", "write a story", "tell me a joke", "python", "javascript", "script",
	"code", "function", "programming", "reverse a", "linked list", "binary tree",
	"translate", "flight", "hotel", "travel to", "capital of",
]


def classify_intent(
	message: str,
	conversation_context: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
	"""
	Deterministically classifies a user message into one of the 5 supported intents:
	1. greeting
	2. database_query
	3. follow_up
	4. clarification
	5. unsupported

	Context rules:
	- Uses conversation_context only to understand follow-up questions.
	- If a follow-up requires fresh database data, classifies as follow_up with requires_database=True.
	"""
	if not message or not str(message).strip():
		return {
			"intent": "clarification",
			"message": "Please enter a question or request regarding the Employee Management System.",
		}

	cleaned = str(message).strip()
	q_lower = cleaned.lower()
	# Normalized version without trailing punctuation for robust matching
	q_clean = re.sub(r"[.?!,;:]+$", "", q_lower).strip()

	# 1. Check GREETING
	for pat in GREETING_PATTERNS:
		if re.search(pat, q_clean):
			# Ensure it's not a compound database question (e.g., "Hi, how many employees are there?")
			has_db_intent = any(k in q_clean for k in EMS_DOMAIN_KEYWORDS)
			has_query_words = any(w in q_clean for w in ["how many", "show", "list", "who", "what", "where", "count"])
			if not (has_db_intent and has_query_words):
				return {
					"intent": "greeting",
					"message": DEFAULT_GREETING_MESSAGE,
				}

	# 2. Check CLARIFICATION (Ambiguous requests)
	for pat, clarification_msg in AMBIGUOUS_CLARIFICATION_PATTERNS:
		if re.search(pat, q_clean):
			return {
				"intent": "clarification",
				"message": clarification_msg,
			}

	# 3. Check FOLLOW-UP
	is_follow_up = False
	for pat in STANDALONE_FOLLOW_UPS:
		if re.search(pat, q_clean):
			is_follow_up = True
			break

	has_context = bool(conversation_context and len(conversation_context) > 0)

	# If there's recent conversation context, check for context pronouns and continuation phrases
	if has_context and not is_follow_up:
		tokens = q_clean.split()
		# Check for pronouns referring back to previous entities: those, them, these, same
		has_referring_pronoun = any(p in tokens for p in ["those", "them", "these", "same"])
		has_joining_filter = any(w in q_clean for w in ["joined this year", "joined last year", "joined in", "who joined", "joining date"])
		if has_referring_pronoun or has_joining_filter:
			is_follow_up = True
		elif len(tokens) <= 6:
			continuation_starters = ("and", "what about", "how about", "in", "for", "with", "only", "just", "sort by", "total", "also", "who")
			if any(q_clean.startswith(starter) for starter in continuation_starters):
				is_follow_up = True

	if is_follow_up:
		# Synthesize resolved follow-up query using conversation context if available
		resolved_query = cleaned
		if has_context and conversation_context:
			last_turn = conversation_context[-1]
			prev_query = (
				last_turn.get("query")
				or last_turn.get("message")
				or last_turn.get("user_message")
				or ""
			)
			if prev_query:
				if q_clean.startswith("show only"):
					dept_part = cleaned[len("show only"):].strip().rstrip(".?!")
					resolved_query = f"{prev_query} (filtered: {dept_part})"
				elif q_clean.startswith("what about") or q_clean.startswith("how about"):
					resolved_query = f"{prev_query} for {cleaned}"
				elif q_clean.startswith("sort"):
					resolved_query = f"{prev_query} ordered by {cleaned}"
				elif q_clean.startswith("only"):
					filter_part = cleaned[len("only"):].strip().rstrip(".?!")
					resolved_query = f"{prev_query} (filtered: {filter_part})"
				else:
					resolved_query = f"{prev_query} (refined: {cleaned})"

		return {
			"intent": "follow_up",
			"query": resolved_query,
			"requires_database": True,
		}

	# 4. Check UNSUPPORTED (Requests unrelated to Employee Management System)
	# 4. Check KNOWLEDGE_QUERY (Unstructured knowledge: policies, handbooks, guidelines, ethics, benefits)
	# Dispatched to Embeddings Engine (semantic vector search over policy documents).
	# Note: Tabular record requests (e.g., "Show salary slips", "List employees") use SQL Engine.
	has_record_fetch_prefix = bool(
		re.search(
			r"^\s*(?:how\s+many|count|sum|total|average|show|list|who\s+is|who\s+are)\s+(?:all\s+)?(?:employees?|staff|workers?|salary\s+slips?|attendances?|leaves?\s+applications?)",
			q_clean,
		)
	)
	if not has_record_fetch_prefix:
		for pat in KNOWLEDGE_PATTERNS:
			if re.search(pat, q_clean):
				return {
					"intent": "knowledge_query",
					"query": cleaned,
				}

	# 5. Check UNSUPPORTED (Requests unrelated to Employee Management System)
	has_unsupported_term = any(k in q_clean for k in UNSUPPORTED_KEYWORDS)
	has_ems_term = any(k in q_clean for k in EMS_DOMAIN_KEYWORDS)

	if has_unsupported_term and not has_ems_term:
		return {
			"intent": "unsupported",
			"message": DEFAULT_UNSUPPORTED_MESSAGE,
		}

	is_general_question = any(q_clean.startswith(w) for w in [
		"who won", "what is the weather", "how to bake", "recipe for",
		"write a poem", "tell me a joke", "what is the capital", "translate", "write code",
		"write a", "can you write", "how do i", "how to", "who is the president",
	])
	if is_general_question and not has_ems_term:
		return {
			"intent": "unsupported",
			"message": DEFAULT_UNSUPPORTED_MESSAGE,
		}

	# If no EMS domain keywords and not in conversation context, classify as unsupported
	if not has_ems_term and not has_context:
		return {
			"intent": "unsupported",
			"message": DEFAULT_UNSUPPORTED_MESSAGE,
		}

	# 5. Default to DATABASE_QUERY for workforce/system inquiries
	return {
		"intent": "database_query",
		"query": cleaned,
	}


# =====================================================================
# 5. ROUTER ORCHESTRATOR & CONTEXT BUILDER
# =====================================================================

def get_conversation_context(
	user: Optional[str] = None,
	conversation_id: Optional[str] = None,
	explicit_context: Optional[List[Dict[str, Any]]] = None,
	limit: int = 5,
) -> List[Dict[str, Any]]:
	"""
	Retrieves recent conversation context for contextual follow-up understanding.
	Strictly bounds the context window (min 1, max 10 messages) to prevent
	unbounded prompt bloat to the LLM.
	Can be filtered by conversation_id and/or user.
	"""
	if explicit_context and isinstance(explicit_context, list):
		return explicit_context[-10:]

	if not frappe or not hasattr(frappe, "db") or not frappe.db:
		return []

	if not user:
		user = frappe.session.user if hasattr(frappe, "session") else None

	if not user or user == "Guest":
		return []

	if not frappe.db.exists("DocType", "Chat Message"):
		return []

	# Enforce small context window (default 5, ceiling 10)
	bounded_limit = min(max(int(limit or 5), 1), 10)

	try:
		filters = {}
		if conversation_id:
			filters["conversation_id"] = conversation_id
		if user:
			filters["user"] = user

		records = frappe.get_all(
			"Chat Message",
			fields=[
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
				"message",
				"response",
				"sources",
				"creation",
			],
			filters=filters,
			order_by="creation desc",
			limit=bounded_limit,
		)

		# If conversation_id yielded no records, fallback to user
		if not records and conversation_id and user:
			records = frappe.get_all(
				"Chat Message",
				fields=[
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
					"message",
					"response",
					"sources",
					"creation",
				],
				filters={"user": user},
				order_by="creation desc",
				limit=bounded_limit,
			)

		# Reverse to chronological order
		return [
			{
				"user_message": r.user_message or r.message,
				"assistant_response": r.assistant_message or r.response,
				"assistant_message": r.assistant_message or r.response,
				"generated_sql": r.generated_sql,
				"query_status": r.query_status,
				"message_type": r.message_type,
				"conversation_id": r.conversation_id,
				"sources": r.sources,
				"timestamp": str(r.created_at or r.creation),
			}
			for r in reversed(records)
		]
	except Exception:
		return []


def extract_structured_follow_up_context(
	conversation_context: Optional[List[Dict[str, Any]]] = None,
	current_message: str = "",
	conversation_id: Optional[str] = None,
	user: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
	"""
	Extracts a small, structured follow-up context dictionary:
	{
	    "previous_user_message": "Show employees in Engineering",
	    "previous_sql": "SELECT ... WHERE department = 'Engineering'",
	    "previous_assistant_message": "I found 25 employees in Engineering.",
	    "current_message": "Only those who joined this year",
	    "conversation_id": "..."
	}
	Scans the bounded context window to find the most recent user message
	and executed SQL query. Returns None if no conversation history exists.
	"""
	if conversation_context is None:
		conversation_context = get_conversation_context(
			user=user,
			conversation_id=conversation_id,
			limit=10,
		)

	if not conversation_context:
		return None

	prev_user_msg = ""
	prev_sql = ""
	prev_asst_msg = ""

	# Scan backwards for the latest turn with query/sql
	for turn in reversed(conversation_context):
		u_msg = turn.get("user_message") or turn.get("message") or turn.get("query")
		sql = turn.get("generated_sql") or turn.get("executed_sql") or turn.get("sql")
		a_msg = turn.get("assistant_message") or turn.get("assistant_response") or turn.get("response")

		if not prev_user_msg and u_msg:
			prev_user_msg = str(u_msg).strip()
		if not prev_sql and sql:
			prev_sql = str(sql).strip()
		if not prev_asst_msg and a_msg:
			prev_asst_msg = str(a_msg).strip()

		if prev_user_msg and prev_sql:
			break

	if not prev_user_msg and not prev_sql:
		return None

	return {
		"previous_user_message": prev_user_msg,
		"previous_sql": prev_sql,
		"previous_assistant_message": prev_asst_msg,
		"current_message": str(current_message or "").strip(),
		"conversation_id": conversation_id or "",
	}


def route_intent(
	message: str,
	conversation_context: Optional[List[Dict[str, Any]]] = None,
	llm_response: Optional[Union[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
	"""
	Main Entrypoint for the Intent Router.
	
	If llm_response is supplied:
	  Validates and enforces the strict JSON response format contract.
	If llm_response is not supplied:
	  Classifies the incoming message using intelligent pattern matching
	  and conversation context, and returns a verified JSON dictionary.

	Guarantees:
	- Strict JSON returned
	- No SQL ever returned from this router
	- Exactly one of the 5 valid intents
	"""
	if llm_response is not None:
		return validate_router_output(llm_response)

	classified = classify_intent(message, conversation_context=conversation_context)
	return validate_router_output(classified)

