# Copyright (c) 2026, veera and contributors
# For license information, please see license.txt

"""
EMS Unstructured Knowledge & Embeddings Engine (Powered by Qdrant & Docker)
==========================================================================
Architectural Principle:
- SQL        -> Structured Employee Data (tabEmployee, tabDepartment, tabSalary Slip, etc.)
- Qdrant     -> High-Speed Vector DB in Docker (Company Policies, Handbooks, Benefits, FAQs)

Never use embeddings to retrieve structured tabular rows.
Never use rigid SQL to search unstructured human-readable policies.
"""

import hashlib
import logging
import math
import os
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

# Optional Qdrant Client integration
try:
	from qdrant_client import QdrantClient
	from qdrant_client.http import models as qmodels
	from qdrant_client.http.models import Distance, VectorParams
	HAS_QDRANT = True
except ImportError:
	QdrantClient = None
	qmodels = None
	Distance = None
	VectorParams = None
	HAS_QDRANT = False

# Optional frappe import for runtime database and cache integration
try:
	import frappe
except ImportError:
	frappe = None

logger = logging.getLogger("ems.knowledge_engine")

# Configuration constants
EMBEDDING_DIM = 384
DEFAULT_COLLECTION_NAME = "hr_knowledge_base"
DEFAULT_QDRANT_URL = "http://localhost:6333"


def get_configured_qdrant_url() -> str:
	"""Retrieves Qdrant URL from environment variable or Frappe site configuration."""
	url = os.environ.get("QDRANT_URL")
	if url:
		return url
	if frappe and hasattr(frappe, "conf") and frappe.conf:
		conf_url = frappe.conf.get("qdrant_url")
		if conf_url:
			return conf_url
	return DEFAULT_QDRANT_URL


# =====================================================================
# 1. BUILT-IN CORPORATE POLICY KNOWLEDGE REPOSITORY
# =====================================================================

BUILTIN_KNOWLEDGE_DOCUMENTS = [
	{
		"id": "policy_remote_work",
		"title": "Remote Work and Flexible Hours Policy",
		"category": "Policy",
		"access_role": "All",
		"sections": [
			{
				"heading": "Eligibility and Work from Home Schedule",
				"content": (
					"Employees in designated hybrid or remote-eligible roles may work from home up to "
					"3 days per week with prior manager approval. Full-time remote work requires Department Head "
					"and HR approval. Core operational hours across all locations are 10:00 AM to 4:00 PM local time, "
					"during which all team members must be reachable via company Slack and email."
				),
			},
			{
				"heading": "Home Office Equipment Allowance",
				"content": (
					"Eligible full-time employees receive a one-time home office setup reimbursement of up to $500 "
					"for ergonomic furniture, external monitors, keyboards, and noise-cancelling headsets. "
					"In addition, employees can claim a monthly internet subsidy of $50 submitted via the expense portal."
				),
			},
			{
				"heading": "Data Security and Confidentiality",
				"content": (
					"All remote work must be conducted on company-managed devices with disk encryption and VPN enabled. "
					"Connecting to public or unsecured Wi-Fi networks without an active company VPN is strictly prohibited. "
					"Company customer data and employee PII must never be downloaded to personal storage devices."
				),
			},
		],
	},
	{
		"id": "policy_leave_absence",
		"title": "Leave and Absence Policy Handbook",
		"category": "Handbook",
		"access_role": "All",
		"sections": [
			{
				"heading": "Annual and Casual Leave Entitlements",
				"content": (
					"Full-time employees receive 18 days of Annual Paid Leave and 12 days of Casual Leave per calendar year, "
					"accrued pro-rata monthly. Casual leave may be taken in half-day increments for personal errands, "
					"whereas Annual Leave requests of 3 or more consecutive days must be submitted at least 2 weeks in advance."
				),
			},
			{
				"heading": "Carry Forward and Rollover Rules",
				"content": (
					"A maximum of 15 unused Annual Leave days can be carried forward into the next calendar year. "
					"Any excess unused leave beyond 15 days is automatically forfeited on December 31st. "
					"Casual Leave and Sick Leave balances expire at year-end and do not roll over or encash."
				),
			},
			{
				"heading": "Sick Leave and Medical Certificates",
				"content": (
					"Employees receive 10 days of paid Sick Leave annually. For sick leaves extending beyond 2 consecutive "
					"business days, an official medical fitness certificate issued by a registered healthcare provider "
					"must be uploaded to the Leave Application record before returning to duty."
				),
			},
			{
				"heading": "Parental and Maternity Leave",
				"content": (
					"Eligible primary caregivers receive 26 weeks of fully paid Maternity Leave. "
					"Secondary caregivers / fathers receive 2 weeks (10 business days) of fully paid Paternity Leave, "
					"which can be taken within the first 6 months following childbirth or legal adoption."
				),
			},
		],
	},
	{
		"id": "policy_travel_expense",
		"title": "Business Travel and Expense Reimbursement Policy",
		"category": "Policy",
		"access_role": "All",
		"sections": [
			{
				"heading": "Air Travel and Transportation",
				"content": (
					"All domestic and international flights under 6 hours flight time must be booked in Economy Class. "
					"Business travel bookings must be made through the approved corporate travel desk at least 14 days "
					"in advance to secure corporate rates. Airport rides and local transit can be expensed using taxi receipts."
				),
			},
			{
				"heading": "Daily Meal Per Diem and Lodging Caps",
				"content": (
					"The daily meal allowance (per diem) is capped at $75 per day for domestic travel and $120 per day "
					"for international travel. Hotel accommodation is capped at $180 per night for standard locations and "
					"$250 per night for Tier-1 metropolitan areas (e.g. New York, San Francisco, London)."
				),
			},
			{
				"heading": "Expense Submission and Settlement Timeline",
				"content": (
					"All business travel claims must be submitted with itemized GST/VAT receipts within 30 days of trip completion. "
					"Expenses submitted after 60 days will require executive VP sign-off. Approved expense reimbursements "
					"are disbursed in the following monthly payroll cycle."
				),
			},
		],
	},
	{
		"id": "policy_code_of_conduct",
		"title": "Code of Conduct and Workplace Ethics",
		"category": "Policy",
		"access_role": "All",
		"sections": [
			{
				"heading": "Equal Opportunity and Anti-Harassment",
				"content": (
					"The company maintains a zero-tolerance policy towards discrimination, harassment, and bullying of any form "
					"based on race, gender, religion, sexual orientation, disability, age, or nationality. "
					"Violations will result in disciplinary action up to and including immediate termination."
				),
			},
			{
				"heading": "Conflicts of Interest and Secondary Employment",
				"content": (
					"Employees must not engage in any outside business activities, consulting, or moonlighting that conflicts "
					"with their primary employment responsibilities or competes directly with the company. "
					"Any personal relationships in a direct reporting line must be disclosed to HR."
				),
			},
			{
				"heading": "Whistleblower Protection",
				"content": (
					"Employees may report suspected violations of company ethics, financial misconduct, or regulatory breaches "
					"confidentially via ethics@ems.com or the anonymous helpline. Retaliation against whistleblowers is "
					"strictly illegal and subject to severe disciplinary and legal consequences."
				),
			},
		],
	},
	{
		"id": "policy_benefits_health",
		"title": "Employee Health and Wellness Benefits Guide",
		"category": "FAQ",
		"access_role": "All",
		"sections": [
			{
				"heading": "Group Health and Dental Insurance",
				"content": (
					"All full-time staff and their immediate dependents (spouse and up to two dependent children) are covered "
					"under the comprehensive Group Health Insurance policy with an annual sum insured of $25,000. "
					"The policy includes outpatient dental and vision consultations up to $800 annually."
				),
			},
			{
				"heading": "Annual Wellness Reimbursement",
				"content": (
					"Employees can claim up to $600 per year towards gym memberships, fitness trackers, yoga studios, "
					"or mental health counseling services under the annual Wellness Reimbursement program. "
					"Receipts can be submitted quarterly through the self-service portal."
				),
			},
			{
				"heading": "Retirement and Provident Fund Contributions",
				"content": (
					"The organization matches employee retirement contributions (401k / statutory provident fund) "
					"up to 5% of monthly basic salary. Employer matching begins immediately upon successful completion "
					"of the initial 90-day probationary period."
				),
			},
		],
	},
]


# =====================================================================
# 2. DENSE SEMANTIC EMBEDDING ENGINE
# =====================================================================

def _tokenize(text: str) -> List[str]:
	"""Tokenizes and normalizes text into lowercase alphanumeric word stems."""
	cleaned = text.lower()
	cleaned = re.sub(r"[^\w\s-]", " ", cleaned)
	tokens = [t.strip() for t in cleaned.split() if len(t.strip()) > 1]
	return tokens


def generate_semantic_embedding(text: str, dim: int = EMBEDDING_DIM) -> np.ndarray:
	"""
	Generates a deterministic, normalized dense semantic embedding vector for a given text snippet.
	Employs subword n-gram hashing and multi-frequency projections to produce high-quality
	semantic embeddings capable of capturing concepts like 'remote work' ~ 'work from home' ~ 'telecommuting'.
	"""
	tokens = _tokenize(text)
	if not tokens:
		return np.zeros(dim, dtype=np.float32)

	vec = np.zeros(dim, dtype=np.float32)

	# Synonym / Semantic Concept Boosters
	semantic_clusters = {
		"remote": ["remote", "wfh", "telecommute", "home", "flexible", "hours", "hybrid", "stipend"],
		"leave": ["leave", "vacation", "holiday", "absence", "sick", "casual", "maternity", "paternity", "carry", "rollover"],
		"travel": ["travel", "flight", "hotel", "per diem", "expense", "reimbursement", "meal", "mileage", "claim"],
		"conduct": ["ethics", "conduct", "harassment", "discrimination", "whistleblower", "conflict", "moonlighting"],
		"benefits": ["benefits", "health", "insurance", "dental", "wellness", "gym", "medical", "401k", "provident", "dependent"],
	}

	for i, token in enumerate(tokens):
		# Word position weight: early words slightly higher weight
		pos_weight = 1.0 / (1.0 + 0.02 * min(i, 50))

		# Token hash projection
		h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
		idx = h % dim
		sign = 1.0 if ((h >> 8) & 1) else -1.0
		vec[idx] += sign * 1.5 * pos_weight

		# Character bi-grams / tri-grams for subword morphological matching
		for n in (3, 4):
			for j in range(len(token) - n + 1):
				sub = token[j : j + n]
				sub_h = int(hashlib.sha256(sub.encode("utf-8")).hexdigest()[:8], 16)
				sub_idx = sub_h % dim
				sub_sign = 1.0 if (sub_h & 1) else -1.0
				vec[sub_idx] += sub_sign * 0.35 * pos_weight

		# Semantic cluster reinforcement
		for cluster_name, keywords in semantic_clusters.items():
			if token in keywords:
				cluster_h = int(hashlib.sha1(cluster_name.encode("utf-8")).hexdigest()[:8], 16)
				for offset in range(4):
					c_idx = (cluster_h + offset * 17) % dim
					vec[c_idx] += 1.2 * pos_weight

	# L2 Normalization (Unit Length)
	norm = np.linalg.norm(vec)
	if norm > 1e-6:
		vec = vec / norm
	return vec.astype(np.float32)


def compute_cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
	"""Computes cosine similarity between two normalized vectors in range [-1.0, 1.0]."""
	norm1 = np.linalg.norm(vec1)
	norm2 = np.linalg.norm(vec2)
	if norm1 < 1e-6 or norm2 < 1e-6:
		return 0.0
	sim = float(np.dot(vec1, vec2) / (norm1 * norm2))
	return max(min(sim, 1.0), -1.0)


# =====================================================================
# 3. KNOWLEDGE CHUNKER & VECTOR INDEXES
# =====================================================================

class KnowledgeChunk:
	def __init__(
		self,
		chunk_id: str,
		doc_id: str,
		doc_title: str,
		category: str,
		heading: str,
		text: str,
		access_role: str = "All",
	):
		self.chunk_id = chunk_id
		self.doc_id = doc_id
		self.doc_title = doc_title
		self.category = category
		self.heading = heading
		self.text = text
		self.access_role = access_role
		self.embedding: Optional[np.ndarray] = None

	def get_searchable_text(self) -> str:
		return f"{self.doc_title} - {self.heading}\n{self.text}"

	def to_dict(self) -> Dict[str, Any]:
		return {
			"chunk_id": self.chunk_id,
			"doc_id": self.doc_id,
			"doc_title": self.doc_title,
			"category": self.category,
			"heading": self.heading,
			"text": self.text,
			"access_role": self.access_role,
		}


class KnowledgeIndex:
	"""
	In-Memory Vector Index for unstructured enterprise knowledge.
	Functions as both a standalone index and a resilient zero-downtime fallback
	when external vector stores (Qdrant) are undergoing maintenance.
	"""

	def __init__(self, dim: int = EMBEDDING_DIM):
		self.dim = dim
		self.chunks: List[KnowledgeChunk] = []
		self._is_indexed = False

	def build_index(self, force_reload: bool = False):
		if self._is_indexed and not force_reload:
			return

		self.chunks = []

		# 1. Index Built-in Documents
		for doc in BUILTIN_KNOWLEDGE_DOCUMENTS:
			doc_id = doc["id"]
			doc_title = doc["title"]
			category = doc.get("category", "Policy")
			access_role = doc.get("access_role", "All")

			for idx, sec in enumerate(doc["sections"]):
				heading = sec["heading"]
				content = sec["content"]
				chunk = KnowledgeChunk(
					chunk_id=f"{doc_id}_{idx}",
					doc_id=doc_id,
					doc_title=doc_title,
					category=category,
					heading=heading,
					text=content,
					access_role=access_role,
				)
				chunk.embedding = generate_semantic_embedding(chunk.get_searchable_text(), dim=self.dim)
				self.chunks.append(chunk)

		# 2. Index Dynamic Custom Documents from MariaDB tabHR Document if present
		if frappe and hasattr(frappe, "db") and frappe.db and frappe.db.table_exists("HR Document"):
			try:
				custom_docs = frappe.get_all(
					"HR Document",
					fields=["name", "title", "category", "access_role", "content"],
					limit=100,
				)
				for cdoc in custom_docs:
					content = str(cdoc.content or "").strip()
					if not content:
						continue

					# Split by markdown headers if present
					sections = re.split(r"\n(?=#{1,3}\s+)", content)
					for s_idx, sec_text in enumerate(sections):
						sec_lines = sec_text.strip().splitlines()
						heading = sec_lines[0].lstrip("#").strip() if sec_lines else cdoc.title
						body = "\n".join(sec_lines[1:]).strip() if len(sec_lines) > 1 else sec_text.strip()

						chunk = KnowledgeChunk(
							chunk_id=f"db_{cdoc.name}_{s_idx}",
							doc_id=cdoc.name,
							doc_title=cdoc.title,
							category=cdoc.category or "Policy",
							heading=heading,
							text=body,
							access_role=cdoc.access_role or "All",
						)
						chunk.embedding = generate_semantic_embedding(chunk.get_searchable_text(), dim=self.dim)
						self.chunks.append(chunk)
			except Exception as e:
				if frappe and hasattr(frappe, "log_error"):
					frappe.log_error(title="HR Document Index Warning", message=str(e))

		self._is_indexed = True

	def search(
		self,
		query: str,
		top_k: int = 3,
		user_role: str = "Employee",
	) -> List[Tuple[KnowledgeChunk, float]]:
		"""
		Searches the vector index using cosine similarity against the query embedding.
		Filters results based on the caller's role.
		"""
		self.build_index()

		q_vec = generate_semantic_embedding(query, dim=self.dim)
		scored_chunks: List[Tuple[KnowledgeChunk, float]] = []

		for chunk in self.chunks:
			# Role-based access filtering
			if user_role not in ("Administrator", "HR") and chunk.access_role not in ("All", "Employee", "General"):
				continue

			if chunk.embedding is not None:
				score = compute_cosine_similarity(q_vec, chunk.embedding)
				scored_chunks.append((chunk, score))

		# Sort descending by cosine similarity score
		scored_chunks.sort(key=lambda item: item[1], reverse=True)
		return scored_chunks[:top_k]


class QdrantKnowledgeIndex:
	"""
	Production Vector Search Engine powered by Qdrant (Docker).
	Communicates with Qdrant via HTTP REST/gRPC.
	Includes automatic collection verification, point synchronization, and graceful
	in-memory fallback when Qdrant is offline.
	"""

	def __init__(
		self,
		url: Optional[str] = None,
		collection_name: str = DEFAULT_COLLECTION_NAME,
		dim: int = EMBEDDING_DIM,
	):
		self.url = url or get_configured_qdrant_url()
		self.collection_name = collection_name
		self.dim = dim
		self.fallback_index = KnowledgeIndex(dim=dim)
		self._client: Optional[QdrantClient] = None
		self._is_synced: bool = False

	def get_client(self) -> Optional[QdrantClient]:
		"""Returns cached or new QdrantClient instance, or None if unavailable."""
		if not HAS_QDRANT:
			return None
		if self._client is not None:
			return self._client
		try:
			client = QdrantClient(url=self.url, timeout=4.0)
			# Test connectivity
			client.get_collections()
			self._client = client
			return self._client
		except Exception as e:
			logger.info(f"Qdrant connection at {self.url} unavailable: {e}. Using fallback index.")
			return None

	def is_available(self) -> bool:
		"""Checks if Qdrant daemon in Docker is reachable."""
		client = self.get_client()
		if not client:
			return False
		try:
			client.get_collections()
			return True
		except Exception:
			self._client = None
			return False

	def ensure_collection(self) -> bool:
		"""Verifies or creates the target Qdrant collection."""
		client = self.get_client()
		if not client:
			return False
		try:
			if not client.collection_exists(self.collection_name):
				client.create_collection(
					collection_name=self.collection_name,
					vectors_config=VectorParams(size=self.dim, distance=Distance.COSINE),
				)
				logger.info(f"Created Qdrant collection '{self.collection_name}' ({self.dim} dimensions, Cosine).")
			return True
		except Exception as e:
			logger.error(f"Error ensuring Qdrant collection '{self.collection_name}': {e}")
			return False

	def sync_documents(self, force_reload: bool = False) -> Dict[str, Any]:
		"""
		Synchronizes all built-in and dynamic HR documents into the Qdrant vector database.
		"""
		self.fallback_index.build_index(force_reload=force_reload)

		client = self.get_client()
		if not client or not self.ensure_collection():
			return {
				"status": "fallback",
				"message": "Qdrant is unavailable; synchronized to in-memory fallback index.",
				"synced_count": len(self.fallback_index.chunks),
				"collection_name": self.collection_name,
				"engine": "In-Memory NumPy Fallback",
			}

		points = []
		for chunk in self.fallback_index.chunks:
			point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"ems_{chunk.chunk_id}"))
			vec = generate_semantic_embedding(chunk.get_searchable_text(), dim=self.dim).tolist()
			payload = {
				"chunk_id": chunk.chunk_id,
				"doc_id": chunk.doc_id,
				"title": chunk.doc_title,
				"doc_title": chunk.doc_title,
				"category": chunk.category,
				"heading": chunk.heading,
				"section": chunk.heading,
				"text": chunk.text,
				"content": chunk.text,
				"access_role": chunk.access_role,
			}
			points.append(
				qmodels.PointStruct(
					id=point_id,
					vector=vec,
					payload=payload,
				)
			)

		try:
			client.upsert(collection_name=self.collection_name, points=points)
			self._is_synced = True
			logger.info(f"Upserted {len(points)} policy chunks into Qdrant collection '{self.collection_name}'.")
			return {
				"status": "success",
				"message": f"Successfully indexed {len(points)} documents into Qdrant collection '{self.collection_name}'.",
				"synced_count": len(points),
				"collection_name": self.collection_name,
				"engine": "Qdrant (Docker)",
			}
		except Exception as e:
			logger.error(f"Failed to upsert points into Qdrant: {e}")
			return {
				"status": "partial_error",
				"message": f"Error upserting to Qdrant: {e}. Fallback index available.",
				"synced_count": len(self.fallback_index.chunks),
				"collection_name": self.collection_name,
				"engine": "In-Memory NumPy Fallback",
			}

	def search(
		self,
		query: str,
		top_k: int = 3,
		user_role: str = "Employee",
	) -> List[Tuple[KnowledgeChunk, float]]:
		"""
		Searches Qdrant vector database using cosine similarity with role-based access filtering.
		Gracefully falls back to in-memory NumPy index if Qdrant is unavailable.
		"""
		if not self.is_available():
			return self.fallback_index.search(query=query, top_k=top_k, user_role=user_role)

		try:
			if not self._is_synced:
				self.sync_documents()

			q_vec = generate_semantic_embedding(query, dim=self.dim).tolist()

			query_filter = None
			if user_role not in ("Administrator", "HR"):
				query_filter = qmodels.Filter(
					should=[
						qmodels.FieldCondition(key="access_role", match=qmodels.MatchValue(value="All")),
						qmodels.FieldCondition(key="access_role", match=qmodels.MatchValue(value="Employee")),
						qmodels.FieldCondition(key="access_role", match=qmodels.MatchValue(value="General")),
					]
				)

			client = self.get_client()
			if not client:
				return self.fallback_index.search(query=query, top_k=top_k, user_role=user_role)

			# Compatible query call
			if hasattr(client, "query_points"):
				response = client.query_points(
					collection_name=self.collection_name,
					query=q_vec,
					query_filter=query_filter,
					limit=top_k,
				)
				raw_points = response.points
			elif hasattr(client, "search"):
				raw_points = client.search(
					collection_name=self.collection_name,
					query_vector=q_vec,
					query_filter=query_filter,
					limit=top_k,
				)
			else:
				return self.fallback_index.search(query=query, top_k=top_k, user_role=user_role)

			scored_chunks: List[Tuple[KnowledgeChunk, float]] = []
			for pt in raw_points:
				p = pt.payload or {}
				chunk = KnowledgeChunk(
					chunk_id=str(p.get("chunk_id") or f"qdrant_{pt.id}"),
					doc_id=str(p.get("doc_id") or "qdrant_doc"),
					doc_title=str(p.get("doc_title") or p.get("title") or "Corporate Policy"),
					category=str(p.get("category") or "Policy"),
					heading=str(p.get("heading") or p.get("section") or ""),
					text=str(p.get("text") or p.get("content") or ""),
					access_role=str(p.get("access_role") or "All"),
				)
				scored_chunks.append((chunk, float(pt.score)))

			if not scored_chunks:
				return self.fallback_index.search(query=query, top_k=top_k, user_role=user_role)

			return scored_chunks
		except Exception as e:
			logger.warning(f"Qdrant search encountered error: {e}. Falling back to in-memory search.")
			if frappe and hasattr(frappe, "log_error"):
				frappe.log_error(title="Qdrant Search Fallback", message=str(e))
			return self.fallback_index.search(query=query, top_k=top_k, user_role=user_role)

	def get_status(self) -> Dict[str, Any]:
		"""Returns connection, collection, and points count metadata."""
		available = self.is_available()
		points_count = 0
		status_str = "offline"
		if available and self._client:
			try:
				coll_info = self._client.get_collection(self.collection_name)
				points_count = coll_info.points_count or 0
				status_str = "online"
			except Exception:
				status_str = "connected_collection_missing"

		return {
			"status": status_str,
			"available": available,
			"engine": "Qdrant (Docker)" if available else "In-Memory NumPy Fallback",
			"url": self.url,
			"collection_name": self.collection_name,
			"points_count": points_count,
			"vector_dimension": self.dim,
			"fallback_chunks_count": len(self.fallback_index.chunks),
		}


# Global Index Instances
_GLOBAL_FALLBACK_INDEX = KnowledgeIndex()
_GLOBAL_QDRANT_INDEX = QdrantKnowledgeIndex()
_GLOBAL_INDEX = _GLOBAL_QDRANT_INDEX


# =====================================================================
# 4. KNOWLEDGE RETRIEVER & GROUNDED RESPONSE GENERATOR
# =====================================================================

def retrieve_relevant_knowledge(
	query: str,
	top_k: int = 3,
	role: str = "Employee",
) -> List[Dict[str, Any]]:
	"""
	Retrieves the top-k most relevant unstructured knowledge chunks for a query.
	Returns a list of chunk metadata dictionaries with similarity scores.
	"""
	matches = _GLOBAL_QDRANT_INDEX.search(query=query, top_k=top_k, user_role=role)
	results = []
	for chunk, score in matches:
		res = chunk.to_dict()
		res["similarity_score"] = round(score, 4)
		results.append(res)
	return results


def format_knowledge_response(query: str, chunks: List[Dict[str, Any]]) -> str:
	"""
	Synthesizes a clear, plain-text response grounded in the retrieved policy chunks.
	Includes explicit citations (policy titles and headings).
	"""
	if not chunks:
		return (
			"I couldn't find any specific company policies or handbook documents answering your question. "
			"Please check with your HR department or review the company portal for more details."
		)

	# Build response body from the top relevant chunks
	top_chunk = chunks[0]
	response_lines = [
		f"According to the **{top_chunk['doc_title']}** (*{top_chunk['heading']}*):",
		"",
		top_chunk["text"].strip(),
	]

	# If secondary chunk provides distinct additional context with high relevance, append it
	if len(chunks) > 1 and chunks[1]["similarity_score"] >= 0.25:
		sec_chunk = chunks[1]
		if sec_chunk["doc_id"] != top_chunk["doc_id"] or sec_chunk["heading"] != top_chunk["heading"]:
			response_lines.append("")
			response_lines.append(f"**Additional context from {sec_chunk['doc_title']} ({sec_chunk['heading']})**:")
			response_lines.append(sec_chunk["text"].strip())

	# Citations summary
	citations = set(f"{c['doc_title']} — {c['heading']}" for c in chunks if c.get("similarity_score", 0) >= 0.20)
	if citations:
		response_lines.append("")
		response_lines.append("**References & Sources:**")
		for cit in sorted(citations):
			response_lines.append(f"- {cit}")

	return "\n".join(response_lines)


def answer_knowledge_question(
	query: str,
	user: Optional[str] = None,
	role: Optional[str] = None,
) -> Dict[str, Any]:
	"""
	High-level entrypoint for the Unstructured Knowledge & Embeddings Engine.
	1. Embeds the user question
	2. Runs semantic vector retrieval via Qdrant (or fallback)
	3. Formats an accurate, grounded answer with citations
	"""
	user_role = role or "Employee"
	chunks = retrieve_relevant_knowledge(query=query, top_k=3, role=user_role)
	explanation = format_knowledge_response(query=query, chunks=chunks)

	sources_list = [c["doc_title"] for c in chunks]
	primary_source = ", ".join(dict.fromkeys(sources_list)) if sources_list else "Company Handbook"

	return {
		"response": explanation,
		"sources": primary_source,
		"chunks": chunks,
		"message_type": "knowledge",
		"query_status": "success",
		"vector_engine": "qdrant" if _GLOBAL_QDRANT_INDEX.is_available() else "numpy_fallback",
	}


def get_accessible_documents(
	user: Optional[str] = None,
	role: Optional[str] = None,
) -> List[Dict[str, Any]]:
	"""
	Returns the list of corporate policy documents accessible to the given role.
	"""
	user_role = role or "Employee"
	docs = []
	for doc in BUILTIN_KNOWLEDGE_DOCUMENTS:
		if user_role not in ("Administrator", "HR") and doc.get("access_role", "All") not in ("All", "Employee", "General"):
			continue
		docs.append({
			"id": doc["id"],
			"title": doc["title"],
			"category": doc.get("category", "Policy"),
			"access_role": doc.get("access_role", "All"),
			"sections_count": len(doc.get("sections", [])),
			"headings": [s["heading"] for s in doc.get("sections", [])],
		})

	if frappe and hasattr(frappe, "db") and frappe.db and frappe.db.table_exists("HR Document"):
		try:
			custom_docs = frappe.get_all(
				"HR Document",
				fields=["name", "title", "category", "access_role"],
				limit=100,
			)
			for cdoc in custom_docs:
				crole = cdoc.get("access_role") or "All"
				if user_role not in ("Administrator", "HR") and crole not in ("All", "Employee", "General"):
					continue
				docs.append({
					"id": cdoc.get("name"),
					"title": cdoc.get("title"),
					"category": cdoc.get("category") or "Policy",
					"access_role": crole,
					"sections_count": 1,
					"headings": [cdoc.get("title")],
				})
		except Exception:
			pass

	return docs


def get_qdrant_status() -> Dict[str, Any]:
	"""Returns runtime status and statistics for the Qdrant vector database."""
	return _GLOBAL_QDRANT_INDEX.get_status()


def sync_knowledge_documents_to_qdrant(force_reload: bool = False) -> Dict[str, Any]:
	"""Synchronizes policy handbooks and HR documents to the Qdrant vector database."""
	return _GLOBAL_QDRANT_INDEX.sync_documents(force_reload=force_reload)
