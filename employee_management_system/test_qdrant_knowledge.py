#!/usr/bin/env python3
# Copyright (c) 2026, veera and contributors
# Test suite for Qdrant Vector Database Integration & Resilient Fallback

import unittest
import sys
import os

app_root = "/home/tui013/frappe-benchv/apps/employee_management_system"
if app_root in sys.path:
	sys.path.remove(app_root)
sys.path.insert(0, app_root)
cur_dir = os.path.dirname(os.path.abspath(__file__))
if cur_dir in sys.path:
	sys.path.remove(cur_dir)

try:
	import frappe
	if not getattr(frappe.local, "site", None):
		frappe.init(site="hospital.localhost", sites_path=".")
		frappe.connect()
except Exception:
	pass

from employee_management_system.employee_management_system.knowledge_engine import (
	QdrantKnowledgeIndex,
	KnowledgeIndex,
	generate_semantic_embedding,
	compute_cosine_similarity,
	get_qdrant_status,
	sync_knowledge_documents_to_qdrant,
	retrieve_relevant_knowledge,
	answer_knowledge_question,
	get_accessible_documents,
	EMBEDDING_DIM,
	DEFAULT_COLLECTION_NAME,
)


class TestQdrantKnowledgeEngine(unittest.TestCase):
	"""
	Comprehensive verification suite for Qdrant vector database operations,
	collection indexing, cosine vector retrieval, role-based filtering,
	and zero-downtime offline fallback.
	"""

	@classmethod
	def setUpClass(cls):
		# Sync all documents into Qdrant before tests
		cls.sync_result = sync_knowledge_documents_to_qdrant(force_reload=True)

	def test_01_qdrant_connectivity_and_status(self):
		status = get_qdrant_status()
		self.assertIsInstance(status, dict)
		self.assertTrue(status.get("available"), "Qdrant Docker service should be running and reachable")
		self.assertEqual(status.get("status"), "online")
		self.assertIn("Qdrant", status.get("engine"))
		self.assertEqual(status.get("collection_name"), DEFAULT_COLLECTION_NAME)
		self.assertEqual(status.get("vector_dimension"), EMBEDDING_DIM)
		self.assertGreaterEqual(status.get("points_count", 0), 16)

	def test_02_embedding_generation_dimension_and_norm(self):
		vec = generate_semantic_embedding("Remote work from home allowance", dim=EMBEDDING_DIM)
		self.assertEqual(len(vec), EMBEDDING_DIM)
		norm = float(sum(x * x for x in vec) ** 0.5)
		self.assertAlmostEqual(norm, 1.0, places=4)

	def test_03_qdrant_sync_documents(self):
		res = self.sync_result
		self.assertEqual(res.get("status"), "success")
		self.assertGreaterEqual(res.get("synced_count", 0), 16)
		self.assertEqual(res.get("collection_name"), DEFAULT_COLLECTION_NAME)

	def test_04_semantic_retrieval_remote_work(self):
		query = "Can employees work from home and what is the internet allowance?"
		chunks = retrieve_relevant_knowledge(query=query, top_k=3, role="Employee")
		self.assertTrue(len(chunks) > 0)
		top = chunks[0]
		self.assertIn("Remote Work", top["doc_title"])
		self.assertGreater(top["similarity_score"], 0.25)

	def test_05_semantic_retrieval_leave_policy(self):
		query = "How many casual leave and annual leave days can I take and rollover?"
		chunks = retrieve_relevant_knowledge(query=query, top_k=3, role="Employee")
		self.assertTrue(len(chunks) > 0)
		top = chunks[0]
		self.assertIn("Leave", top["doc_title"])
		self.assertGreater(top["similarity_score"], 0.25)

	def test_06_semantic_retrieval_travel_expense(self):
		query = "What is the daily meal per diem cap for domestic and international travel?"
		chunks = retrieve_relevant_knowledge(query=query, top_k=3, role="Employee")
		self.assertTrue(len(chunks) > 0)
		top = chunks[0]
		self.assertIn("Travel", top["doc_title"])
		self.assertIn("Per Diem", top["heading"])
		self.assertIn("75", top["text"])

	def test_07_answer_knowledge_question_grounded_response(self):
		query = "What health and dental insurance benefits are provided for my family?"
		ans = answer_knowledge_question(query=query, user="DavidChen", role="Employee")
		self.assertEqual(ans.get("query_status"), "success")
		self.assertEqual(ans.get("message_type"), "knowledge")
		self.assertEqual(ans.get("vector_engine"), "qdrant")
		self.assertIn("Health and Wellness", ans.get("response", ""))
		self.assertIn("References & Sources", ans.get("response", ""))

	def test_08_role_based_access_filtering(self):
		# Non-admin/HR employee query
		emp_chunks = retrieve_relevant_knowledge(query="company ethics", top_k=5, role="Employee")
		for c in emp_chunks:
			self.assertIn(c.get("access_role"), ("All", "Employee", "General"))

	def test_09_resilient_fallback_when_qdrant_unreachable(self):
		# Instantiate a Qdrant index with a dummy dead port
		offline_index = QdrantKnowledgeIndex(url="http://127.0.0.1:59999", dim=EMBEDDING_DIM)
		self.assertFalse(offline_index.is_available())
		status = offline_index.get_status()
		self.assertEqual(status.get("status"), "offline")
		self.assertEqual(status.get("engine"), "In-Memory NumPy Fallback")

		# Search should still succeed seamlessly via in-memory fallback
		results = offline_index.search(query="remote work from home schedule", top_k=2, user_role="Employee")
		self.assertTrue(len(results) > 0)
		top_chunk, score = results[0]
		self.assertIn("Remote Work", top_chunk.doc_title)
		self.assertGreater(score, 0.20)

	def test_10_get_accessible_documents_metadata(self):
		docs = get_accessible_documents(role="Employee")
		self.assertGreaterEqual(len(docs), 5)
		titles = [d["title"] for d in docs]
		self.assertIn("Remote Work and Flexible Hours Policy", titles)
		self.assertIn("Leave and Absence Policy Handbook", titles)


if __name__ == "__main__":
	unittest.main(verbosity=2)
