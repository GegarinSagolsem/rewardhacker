"""Agent traces (the adversary's step-by-step tool calls) live in MongoDB.

They are large, nested and append-only, so they stay out of the relational schema; the run
row in Postgres keeps the summary and the report without the steps.
"""

from __future__ import annotations

from typing import Protocol


class TraceStore(Protocol):
    def save(self, docs: list[dict]) -> None: ...
    def for_run(self, run_id: str) -> list[dict]: ...


class MemoryTraceStore:
    """In-process store for tests and for running without MongoDB."""

    def __init__(self) -> None:
        self.docs: list[dict] = []

    def save(self, docs: list[dict]) -> None:
        self.docs.extend(dict(d) for d in docs)

    def for_run(self, run_id: str) -> list[dict]:
        found = [dict(d) for d in self.docs if d["run_id"] == run_id]
        return sorted(found, key=lambda d: (d["probe"], d["trial"]))


class MongoTraceStore:
    def __init__(self, uri: str, db_name: str = "rewardhacker"):
        from pymongo import ASCENDING, MongoClient

        self._client = MongoClient(uri, serverSelectionTimeoutMS=10_000, appname="rewardhacker")
        self._coll = self._client[db_name]["traces"]
        self._index = [("run_id", ASCENDING), ("probe", ASCENDING), ("trial", ASCENDING)]
        self._indexed = False

    def save(self, docs: list[dict]) -> None:
        if not docs:
            return
        if not self._indexed:
            self._coll.create_index(self._index)
            self._indexed = True
        # insert_many adds _id to the dicts it is given; pass copies.
        self._coll.insert_many([dict(d) for d in docs])

    def for_run(self, run_id: str) -> list[dict]:
        cursor = self._coll.find({"run_id": run_id}, {"_id": 0}).sort(self._index)
        return list(cursor)


def make_trace_store(mongodb_uri: str | None, db_name: str = "rewardhacker") -> TraceStore:
    return MongoTraceStore(mongodb_uri, db_name) if mongodb_uri else MemoryTraceStore()
