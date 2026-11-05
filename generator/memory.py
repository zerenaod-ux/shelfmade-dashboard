#!/usr/bin/env python3
"""
Content Empire — MEMORY LEDGER.

The project's long-term memory. Records every topic/script ever generated so
the system NEVER repeats content and can "advance" over time.

Stored as a human-readable JSON file:
    ~/Documents/ContentEmpire-Studio/memory_ledger.json

Other scripts import this module:
    import memory
    if memory.is_duplicate(topic): skip
    memory.record(niche, topic, script)
    memory.update_status(slug, "posted")

CLI:
    python3 memory.py stats          # show what's been made
    python3 memory.py list           # list all entries
    python3 memory.py list TRADING   # filter by niche
"""

from __future__ import annotations
import json, sys, re, hashlib, datetime
from pathlib import Path

LEDGER = Path.home() / "Documents" / "ContentEmpire-Studio" / "memory_ledger.json"

# ───────────────────────────── core ────────────────────────────────────────
def _normalize(topic: str) -> str:
    """Normalize a topic for duplicate detection (lowercase, alnum only)."""
    return re.sub(r"[^a-z0-9]+", " ", topic.lower()).strip()

def _hash(topic: str) -> str:
    return hashlib.sha1(_normalize(topic).encode()).hexdigest()[:12]

def load() -> dict:
    if LEDGER.exists():
        try:
            return json.loads(LEDGER.read_text())
        except Exception:
            pass
    return {"entries": [], "hashes": {}}

def save(data: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(data, indent=2))

# ───────────────────────────── api ─────────────────────────────────────────
def is_duplicate(topic: str) -> bool:
    """True if this topic (or a near-identical one) was already generated."""
    data = load()
    return _hash(topic) in data["hashes"]

def record(niche: str, topic: str, script: dict | None = None,
           slug: str | None = None, status: str = "generated") -> dict:
    """Add a new entry to memory. Returns the entry."""
    data = load()
    h = _hash(topic)
    slug = slug or re.sub(r"[^a-z0-9]+", "-", topic.lower())[:45].strip("-")
    entry = {
        "id": h,
        "niche": niche,
        "topic": topic,
        "title": (script or {}).get("title", topic),
        "slug": slug,
        "status": status,
        "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    # de-dupe: replace if the same hash exists, else append
    data["entries"] = [e for e in data["entries"] if e["id"] != h]
    data["entries"].append(entry)
    data["hashes"][h] = slug
    save(data)
    return entry

def update_status(slug: str, status: str) -> bool:
    """Mark an entry's status (generated → approved → posted/rejected)."""
    data = load()
    changed = False
    for e in data["entries"]:
        if e["slug"] == slug:
            e["status"] = status
            changed = True
    if changed:
        save(data)
    return changed

def used_topics(niche: str | None = None) -> set:
    data = load()
    return {e["topic"] for e in data["entries"]
            if niche is None or e["niche"] == niche}

def filter_new(topics: list[str]) -> list[str]:
    """Return only the topics that have NOT been generated before."""
    return [t for t in topics if not is_duplicate(t)]

def stats() -> dict:
    data = load()
    by_niche, by_status = {}, {}
    for e in data["entries"]:
        by_niche[e["niche"]]   = by_niche.get(e["niche"], 0) + 1
        by_status[e["status"]] = by_status.get(e["status"], 0) + 1
    return {"total": len(data["entries"]), "by_niche": by_niche,
            "by_status": by_status}

# ───────────────────────────── cli ─────────────────────────────────────────
def _print_stats():
    s = stats()
    print(f"\n🧠 MEMORY LEDGER — {LEDGER}")
    print(f"   Total content ever created: {s['total']}\n")
    if s["by_niche"]:
        print("   By niche:")
        for k, v in sorted(s["by_niche"].items()):
            print(f"     {k:18} {v}")
    if s["by_status"]:
        print("\n   By status:")
        for k, v in sorted(s["by_status"].items()):
            print(f"     {k:18} {v}")
    print()

def _print_list(niche=None):
    data = load()
    rows = [e for e in data["entries"] if niche is None or e["niche"] == niche]
    print(f"\n🧠 {len(rows)} entries" + (f" in {niche}" if niche else "") + ":\n")
    for e in sorted(rows, key=lambda x: x["created_at"], reverse=True):
        print(f"  [{e['status']:9}] {e['niche']:16} {e['title']}")
        print(f"             {e['created_at']}  ({e['slug']})")
    print()

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"
    if cmd == "stats":
        _print_stats()
    elif cmd == "list":
        _print_list(sys.argv[2] if len(sys.argv) > 2 else None)
    else:
        print("Usage: python3 memory.py [stats|list [NICHE]]")
