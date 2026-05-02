#!/usr/bin/env python3
"""
memory_logger.py — log memory read/write operations from Claude Code sessions.

Parses JSONL transcripts and finds tool calls for memory operations:
  - Read / Write / Edit on memory/ paths
  - mcp__mempalace__* calls (MemPalace MCP)
  - TodoWrite with memory-related content

Outputs a human-readable log + optional append to memory/sessions/YYYY-MM-DD.md.

Usage:
    python memory_logger.py                        # latest session
    python memory_logger.py --session <path.jsonl>
    python memory_logger.py --output log.md        # save to file
    python memory_logger.py --tail 50              # last N operations
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Parse tool calls from JSONL
# ---------------------------------------------------------------------------

MEMORY_PATH_PATTERN = re.compile(r"memory/|\.claude/projects/.*memory")
MCP_MEMPALACE = re.compile(r"mcp__mempalace__")

TOOL_ICONS = {
    "Read":   "📖",
    "Write":  "✍️",
    "Edit":   "✏️",
    "mcp__mempalace__mempalace_search":       "🔍",
    "mcp__mempalace__mempalace_get_drawer":   "📂",
    "mcp__mempalace__mempalace_add_drawer":   "➕",
    "mcp__mempalace__mempalace_update_drawer":"♻️",
    "mcp__mempalace__mempalace_delete_drawer":"🗑️",
    "mcp__mempalace__mempalace_kg_add":       "🕸️",
    "mcp__mempalace__mempalace_kg_query":     "🔎",
    "TodoWrite": "✅",
}


def _text_from_content(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(block.get("text", "") or str(block.get("input", "")))
        return " | ".join(p for p in parts if p)
    return str(content)


def _extract_tool_calls(obj: dict) -> list[dict]:
    """Extract tool_use blocks from a message object."""
    calls = []
    content = obj.get("content", [])
    if not isinstance(content, list):
        return calls
    for block in content:
        if isinstance(block, dict) and block.get("type") == "tool_use":
            calls.append({
                "name": block.get("name", ""),
                "input": block.get("input", {}),
            })
    return calls


def _extract_tool_results(obj: dict) -> dict:
    """Map tool_use_id → result text from tool_result blocks."""
    results = {}
    content = obj.get("content", [])
    if not isinstance(content, list):
        return results
    for block in content:
        if isinstance(block, dict) and block.get("type") == "tool_result":
            tid = block.get("tool_use_id", "")
            val = block.get("content", "")
            results[tid] = _text_from_content(val)[:500]
    return results


def is_memory_op(tool_name: str, tool_input: dict) -> bool:
    """Decide if this tool call touches memory."""
    if MCP_MEMPALACE.match(tool_name):
        return True
    if tool_name in ("Read", "Write", "Edit"):
        path = tool_input.get("file_path", "") or ""
        return bool(MEMORY_PATH_PATTERN.search(path))
    if tool_name == "TodoWrite":
        todos = tool_input.get("todos", [])
        return any("memory" in str(t).lower() for t in todos)
    return False


def summarize_op(tool_name: str, tool_input: dict) -> str:
    if tool_name in ("Read", "Write", "Edit"):
        path = tool_input.get("file_path", "?")
        if tool_name == "Edit":
            old = str(tool_input.get("old_string", ""))[:60]
            new = str(tool_input.get("new_string", ""))[:60]
            return f"`{path}` — `{old}` → `{new}`"
        return f"`{path}`"
    if MCP_MEMPALACE.match(tool_name):
        op = tool_name.replace("mcp__mempalace__mempalace_", "")
        key = next((tool_input.get(k, "") for k in ("query", "name", "path", "id") if k in tool_input), "")
        return f"{op}: {str(key)[:80]}"
    if tool_name == "TodoWrite":
        todos = tool_input.get("todos", [])
        return f"{len(todos)} todos"
    return str(tool_input)[:100]


def parse_session(jsonl_path: Path) -> list[dict]:
    ops = []
    try:
        with open(jsonl_path, errors="replace") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                role = obj.get("role") or obj.get("type", "")
                if role not in ("assistant",):
                    continue

                for call in _extract_tool_calls(obj):
                    name = call["name"]
                    inp = call["input"]
                    if is_memory_op(name, inp):
                        icon = TOOL_ICONS.get(name, "🔧")
                        ops.append({
                            "tool": name,
                            "icon": icon,
                            "summary": summarize_op(name, inp),
                            "ts": obj.get("timestamp", ""),
                        })
    except Exception as e:
        print(f"[memory_logger] read error: {e}")
        sys.exit(1)
    return ops


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def format_log(ops: list[dict], session_path: Path) -> str:
    lines = [f"# Memory Operations Log", f"", f"**Session:** `{session_path.name}`",
             f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
             f"**Total ops:** {len(ops)}", ""]

    if not ops:
        lines.append("_No memory operations found._")
        return "\n".join(lines)

    # Group by tool category
    reads = [o for o in ops if o["tool"] in ("Read",) or "search" in o["tool"] or "get" in o["tool"] or "query" in o["tool"]]
    writes = [o for o in ops if o["tool"] in ("Write", "Edit") or "add" in o["tool"] or "update" in o["tool"] or "kg_add" in o["tool"]]
    other = [o for o in ops if o not in reads and o not in writes]

    def section(title, items):
        if not items:
            return []
        out = [f"## {title} ({len(items)})", ""]
        for op in items:
            out.append(f"- {op['icon']} **{op['tool'].replace('mcp__mempalace__', '')}**: {op['summary']}")
        out.append("")
        return out

    lines += section("Reads / Searches", reads)
    lines += section("Writes / Updates", writes)
    lines += section("Other", other)

    return "\n".join(lines)


def find_latest_session() -> Path:
    base = Path.home() / ".claude" / "projects"
    if not base.exists():
        print(f"[memory_logger] {base} not found")
        sys.exit(1)
    candidates = sorted(base.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        print("[memory_logger] no .jsonl sessions found")
        sys.exit(1)
    return candidates[0]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Log memory operations from Claude Code session")
    parser.add_argument("--session", help="Path to .jsonl session file")
    parser.add_argument("--output", help="Save log to this file")
    parser.add_argument("--tail", type=int, default=0, help="Show only last N operations")
    parser.add_argument("--append-session", action="store_true",
                        help="Append to memory/sessions/YYYY-MM-DD.md")
    args = parser.parse_args()

    session_path = Path(args.session) if args.session else find_latest_session()
    print(f"[memory_logger] session: {session_path}")

    ops = parse_session(session_path)
    print(f"[memory_logger] found {len(ops)} memory operations")

    if args.tail and len(ops) > args.tail:
        ops = ops[-args.tail:]

    log = format_log(ops, session_path)

    if args.output:
        Path(args.output).write_text(log)
        print(f"[memory_logger] saved → {args.output}")
    elif args.append_session:
        # find memory vault
        candidates = [
            Path.home() / ".claude" / "projects" / "-root" / "memory",
            Path.home() / "dj-memory",
            Path("memory"),
        ]
        vault = next((p for p in candidates if p.exists()), None)
        if vault:
            date_str = datetime.now().strftime("%Y-%m-%d")
            dest = vault / "sessions" / f"{date_str}.md"
            dest.parent.mkdir(exist_ok=True)
            with open(dest, "a") as f:
                f.write(f"\n\n<!-- memory_logger.py -->\n{log}\n")
            print(f"[memory_logger] appended → {dest}")
        else:
            print("[memory_logger] vault not found, printing:\n")
            print(log)
    else:
        print(log)


if __name__ == "__main__":
    main()
