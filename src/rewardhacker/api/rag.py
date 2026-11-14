"""RAG spec check: compare a task against the org's written guidelines.

Guidelines (Markdown) are chunked by heading, embedded, and stored in MongoDB. A spec check
embeds the task, retrieves the closest guideline excerpts (Atlas Vector Search, or brute-force
cosine when the index isn't available), and asks the LLM which excerpts the task violates.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from dataclasses import dataclass
from textwrap import dedent
from typing import Protocol

from ..llm import LLM, SpendLedger
from ..taskspec import TASK_FILE, TaskSpec

log = logging.getLogger(__name__)

CHUNK_CHARS = 1200
EMBED_MODEL = "gemini-embedding-001"
EMBED_DIMS = 768
# USD per 1M input tokens. Source: ai.google.dev/gemini-api/docs/pricing (gemini-embedding-001).
EMBED_PRICE_PER_M = 0.15
VECTOR_INDEX = "guideline_vectors"


# ---------- chunking ----------


@dataclass
class Chunk:
    heading: str
    text: str


def chunk_markdown(content: str, max_chars: int = CHUNK_CHARS) -> list[Chunk]:
    """Split on headings, then pack paragraphs so each chunk stays under ``max_chars``."""
    sections: list[tuple[str, list[str]]] = [("", [])]
    stack: list[str] = []
    for line in content.replace("\r\n", "\n").split("\n"):
        m = re.match(r"^(#{1,6})\s+(.*\S)\s*$", line)
        if m:
            level = len(m.group(1))
            stack = stack[: level - 1] + [m.group(2)]
            sections.append((" > ".join(stack), []))
        else:
            sections[-1][1].append(line)

    chunks: list[Chunk] = []
    for heading, lines in sections:
        paras = [p.strip() for p in "\n".join(lines).split("\n\n") if p.strip()]
        buf = ""
        for p in paras:
            while len(p) > max_chars:  # a single huge paragraph
                if buf:
                    chunks.append(Chunk(heading, buf))
                    buf = ""
                chunks.append(Chunk(heading, p[:max_chars]))
                p = p[max_chars:]
            if buf and len(buf) + len(p) + 2 > max_chars:
                chunks.append(Chunk(heading, buf))
                buf = ""
            buf = f"{buf}\n\n{p}" if buf else p
        if buf:
            chunks.append(Chunk(heading, buf))
    return chunks


# ---------- embeddings ----------


class Embedder(Protocol):
    model: str

    def embed(self, texts: list[str], kind: str) -> tuple[list[list[float]], float]:
        """kind: "document" or "query". Returns (unit vectors, cost in USD)."""
        ...


def _normalize(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class GeminiEmbedder:
    model = EMBED_MODEL

    def __init__(self, api_key: str, ledger: SpendLedger):
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self._ledger = ledger

    def embed(self, texts: list[str], kind: str) -> tuple[list[list[float]], float]:
        from google.genai import types

        self._ledger.check()
        task_type = "RETRIEVAL_QUERY" if kind == "query" else "RETRIEVAL_DOCUMENT"
        vectors: list[list[float]] = []
        for i in range(0, len(texts), 100):  # API batch limit
            resp = self._client.models.embed_content(
                model=self.model,
                contents=texts[i : i + 100],
                config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=EMBED_DIMS),
            )
            # Truncated (768-d) embeddings must be re-normalised for cosine similarity.
            vectors += [_normalize(list(e.values)) for e in resp.embeddings]
        # The embed API reports no token usage; ~4 chars/token is a deliberate over-estimate.
        cost = sum(len(t) for t in texts) / 4 * EMBED_PRICE_PER_M / 1_000_000
        self._ledger.record(cost)
        return vectors, cost


class HashEmbedder:
    """Deterministic bag-of-words embedder for tests and offline use. No semantics, no cost."""

    model = "hash-bow"

    def __init__(self, dims: int = 256):
        self.dims = dims

    def embed(self, texts: list[str], kind: str) -> tuple[list[list[float]], float]:
        out = []
        for t in texts:
            v = [0.0] * self.dims
            for word in re.findall(r"[a-z0-9_]{3,}", t.lower()):
                v[int(hashlib.md5(word.encode()).hexdigest(), 16) % self.dims] += 1.0
            out.append(_normalize(v))
        return out, 0.0


# ---------- vector index ----------


@dataclass
class Hit:
    guideline_id: str
    title: str
    heading: str
    text: str
    score: float


class GuidelineIndex(Protocol):
    def add(
        self, org_id: str, guideline_id: str, title: str, chunks: list[Chunk], vectors: list[list[float]]
    ) -> None: ...
    def delete(self, guideline_id: str) -> None: ...
    def search(self, org_id: str, vector: list[float], k: int) -> list[Hit]: ...


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=False))


class MemoryGuidelineIndex:
    def __init__(self) -> None:
        self.docs: list[dict] = []

    def add(self, org_id, guideline_id, title, chunks, vectors) -> None:
        for i, (c, v) in enumerate(zip(chunks, vectors, strict=True)):
            self.docs.append({"org_id": org_id, "guideline_id": guideline_id, "title": title,
                              "heading": c.heading, "text": c.text, "chunk": i, "embedding": v})  # fmt: skip

    def delete(self, guideline_id: str) -> None:
        self.docs = [d for d in self.docs if d["guideline_id"] != guideline_id]

    def search(self, org_id: str, vector: list[float], k: int) -> list[Hit]:
        scored = [(d, _dot(vector, d["embedding"])) for d in self.docs if d["org_id"] == org_id]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [Hit(d["guideline_id"], d["title"], d["heading"], d["text"], s) for d, s in scored[:k]]


class MongoGuidelineIndex:
    """Chunks + embeddings in MongoDB. Uses Atlas Vector Search when the index exists."""

    def __init__(self, uri: str, db_name: str = "rewardhacker"):
        from pymongo import MongoClient

        self._coll = MongoClient(uri, serverSelectionTimeoutMS=10_000, appname="rewardhacker")[db_name][
            "guideline_chunks"
        ]

    def ensure_vector_index(self) -> str:
        """Create the Atlas Vector Search index (idempotent). Atlas builds it asynchronously."""
        from pymongo.operations import SearchIndexModel

        db = self._coll.database
        if self._coll.name not in db.list_collection_names():
            db.create_collection(self._coll.name)  # Atlas can't index a missing collection
        existing = {i["name"] for i in self._coll.list_search_indexes()}
        if VECTOR_INDEX in existing:
            return "exists"
        self._coll.create_search_index(
            SearchIndexModel(
                name=VECTOR_INDEX,
                type="vectorSearch",
                definition={
                    "fields": [
                        {
                            "type": "vector",
                            "path": "embedding",
                            "numDimensions": EMBED_DIMS,
                            "similarity": "cosine",
                        },
                        {"type": "filter", "path": "org_id"},
                    ]
                },
            )
        )
        return "created"

    def add(self, org_id, guideline_id, title, chunks, vectors) -> None:
        docs = [
            {"org_id": org_id, "guideline_id": guideline_id, "title": title, "heading": c.heading,
             "text": c.text, "chunk": i, "embedding": v}
            for i, (c, v) in enumerate(zip(chunks, vectors, strict=True))
        ]  # fmt: skip
        if docs:
            self._coll.insert_many(docs)

    def delete(self, guideline_id: str) -> None:
        self._coll.delete_many({"guideline_id": guideline_id})

    def search(self, org_id: str, vector: list[float], k: int) -> list[Hit]:
        from pymongo.errors import OperationFailure

        try:
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": VECTOR_INDEX,
                        "path": "embedding",
                        "queryVector": vector,
                        "numCandidates": max(50, k * 10),
                        "limit": k,
                        "filter": {"org_id": org_id},
                    }
                },
                {"$project": {"embedding": 0, "_id": 0, "score": {"$meta": "vectorSearchScore"}}},
            ]
            rows = list(self._coll.aggregate(pipeline))
            if rows:
                return [Hit(r["guideline_id"], r["title"], r["heading"], r["text"], r["score"]) for r in rows]
        except OperationFailure as exc:
            log.info("vector search unavailable (%s); using brute-force cosine", exc.code)
        # Fallback: an org's guidelines are small, so scoring every chunk is cheap.
        docs = list(self._coll.find({"org_id": org_id}, {"_id": 0}))
        scored = sorted(((d, _dot(vector, d["embedding"])) for d in docs), key=lambda x: x[1], reverse=True)
        return [Hit(d["guideline_id"], d["title"], d["heading"], d["text"], s) for d, s in scored[:k]]


# ---------- the spec check ----------

SPEC_SYSTEM = """\
You review reinforcement-learning coding tasks (environment + objective + verifier tests +
reference solution) against an organization's written guidelines.

Report only problems that a numbered guideline excerpt supports, and cite that excerpt.
Do not invent rules. If the task follows the excerpts, return an empty list.
Reply with JSON only:
{"summary": "<one sentence>",
 "issues": [{"excerpt": <number>, "severity": "high" | "medium" | "low",
             "issue": "<what in the task breaks the guideline>",
             "suggestion": "<concrete fix>"}]}
"""


def _read(path, limit: int) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return text if len(text) <= limit else text[:limit] + "\n...[truncated]"


def task_material(spec: TaskSpec, limit: int = 9000) -> str:
    """The parts of a task a reviewer would read: task.yaml, tests, reference solution."""
    parts = [f"--- {TASK_FILE} ---\n{_read(spec.root / TASK_FILE, 3000)}"]
    budget = limit
    for folder in (spec.verifier.files, spec.solution.files if spec.solution else None):
        if not folder:
            continue
        root = spec.resolve(folder)
        if not root.is_dir():
            continue
        for f in sorted(p for p in root.rglob("*") if p.is_file())[:10]:
            body = _read(f, min(2500, budget))
            budget -= len(body)
            parts.append(f"--- {f.relative_to(spec.root).as_posix()} ---\n{body}")
            if budget <= 0:
                return "\n\n".join(parts)
    return "\n\n".join(parts)


def run_spec_check(
    spec: TaskSpec, org_id: str, embedder: Embedder, index: GuidelineIndex, llm: LLM, k: int = 6
) -> dict:
    material = task_material(spec)
    query = f"{spec.objective}\nverifier: {spec.verifier.command}\n{material[:1500]}"
    vectors, embed_cost = embedder.embed([query], "query")
    hits = index.search(org_id, vectors[0], k)
    if not hits:
        return {
            "summary": "No guidelines uploaded yet.",
            "issues": [],
            "excerpts": [],
            "cost_usd": embed_cost,
        }

    excerpts = "\n\n".join(
        f"[{i}] {h.title}{' > ' + h.heading if h.heading else ''}\n{h.text}" for i, h in enumerate(hits, 1)
    )
    prompt = dedent("""\
        Guideline excerpts:
        {excerpts}

        Task under review:
        {material}
        """).format(excerpts=excerpts, material=material)
    data, turn = llm.complete_json(SPEC_SYSTEM, prompt)  # BudgetExceeded propagates to the route
    issues = []
    for item in data.get("issues") or []:
        if not isinstance(item, dict):
            continue
        try:
            n = int(item.get("excerpt", 0))
        except (TypeError, ValueError):
            n = 0
        hit = hits[n - 1] if 1 <= n <= len(hits) else None
        sev = str(item.get("severity", "medium")).lower()
        issues.append(
            {
                "severity": sev if sev in ("high", "medium", "low") else "medium",
                "issue": str(item.get("issue", "")).strip(),
                "suggestion": str(item.get("suggestion", "")).strip(),
                "excerpt": n if hit else None,
                "guideline_title": hit.title if hit else None,
                "heading": hit.heading if hit else None,
            }
        )
    return {
        "summary": str(data.get("summary", "")).strip(),
        "issues": [i for i in issues if i["issue"]],
        "excerpts": [
            {
                "n": i,
                "guideline_id": h.guideline_id,
                "title": h.title,
                "heading": h.heading,
                "text": h.text,
                "score": round(h.score, 4),
            }
            for i, h in enumerate(hits, 1)
        ],  # fmt: skip
        "cost_usd": round(embed_cost + turn.cost_usd, 6),
        "model": getattr(llm, "model", ""),
    }
