#!/usr/bin/env python3
"""
compile.py — Karpathy-style session compiler for Claude Code memory.

Reads Claude Code JSONL transcripts, extracts conversation turns,
and uses an LLM to synthesize memory entries (user facts, feedback,
project state) in the format expected by the memory/ vault.

Multi-provider: Cerebras → Groq → SambaNova → OpenAI → Anthropic
Priority order determined by COMPILE_PROVIDER env var or config.yaml.

Usage:
    python compile.py                        # auto-detect latest session
    python compile.py --session <path.jsonl> # specific session file
    python compile.py --provider cerebras    # override provider
    python compile.py --dry-run              # print without saving

Output:
    memory/sessions/YYYY-MM-DD.md  — appended session summary
    memory/concepts/<name>.md      — new concept files if detected
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------

PROVIDERS = {}

def _load_cerebras():
    try:
        from cerebras.cloud.sdk import Cerebras
        key = os.environ.get("CEREBRAS_API_KEY") or _cfg("cerebras.api_key")
        if not key:
            return None
        client = Cerebras(api_key=key)
        model = os.environ.get("CEREBRAS_MODEL") or _cfg("cerebras.model") or "llama-3.3-70b"

        def call(prompt, system=""):
            msgs = []
            if system:
                msgs.append({"role": "system", "content": system})
            msgs.append({"role": "user", "content": prompt})
            r = client.chat.completions.create(model=model, messages=msgs, max_tokens=2000)
            return r.choices[0].message.content
        return call
    except Exception:
        return None

def _load_groq():
    try:
        from groq import Groq
        key = os.environ.get("GROQ_API_KEY") or _cfg("groq.api_key")
        if not key:
            return None
        client = Groq(api_key=key)
        model = os.environ.get("GROQ_MODEL") or _cfg("groq.model") or "llama-3.3-70b-versatile"

        def call(prompt, system=""):
            msgs = []
            if system:
                msgs.append({"role": "system", "content": system})
            msgs.append({"role": "user", "content": prompt})
            r = client.chat.completions.create(model=model, messages=msgs, max_tokens=2000)
            return r.choices[0].message.content
        return call
    except Exception:
        return None

def _load_sambanova():
    try:
        import openai
        key = os.environ.get("SAMBANOVA_API_KEY") or _cfg("sambanova.api_key")
        if not key:
            return None
        client = openai.OpenAI(
            api_key=key,
            base_url="https://api.sambanova.ai/v1"
        )
        model = os.environ.get("SAMBANOVA_MODEL") or _cfg("sambanova.model") or "Meta-Llama-3.1-70B-Instruct"

        def call(prompt, system=""):
            msgs = []
            if system:
                msgs.append({"role": "system", "content": system})
            msgs.append({"role": "user", "content": prompt})
            r = client.chat.completions.create(model=model, messages=msgs, max_tokens=2000)
            return r.choices[0].message.content
        return call
    except Exception:
        return None

def _load_openai():
    try:
        import openai
        key = os.environ.get("OPENAI_API_KEY") or _cfg("openai.api_key")
        if not key:
            return None
        client = openai.OpenAI(api_key=key)
        model = os.environ.get("OPENAI_MODEL") or _cfg("openai.model") or "gpt-4o-mini"

        def call(prompt, system=""):
            msgs = []
            if system:
                msgs.append({"role": "system", "content": system})
            msgs.append({"role": "user", "content": prompt})
            r = client.chat.completions.create(model=model, messages=msgs, max_tokens=2000)
            return r.choices[0].message.content
        return call
    except Exception:
        return None

def _load_anthropic():
    try:
        import anthropic
        key = os.environ.get("ANTHROPIC_API_KEY") or _cfg("anthropic.api_key")
        if not key:
            return None
        client = anthropic.Anthropic(api_key=key)
        model = os.environ.get("ANTHROPIC_MODEL") or _cfg("anthropic.model") or "claude-haiku-4-5-20251001"

        def call(prompt, system=""):
            kwargs = {"model": model, "max_tokens": 2000,
                      "messages": [{"role": "user", "content": prompt}]}
            if system:
                kwargs["system"] = system
            r = client.messages.create(**kwargs)
            return r.content[0].text
        return call
    except Exception:
        return None

PROVIDER_ORDER = [
    ("cerebras",  _load_cerebras),
    ("groq",      _load_groq),
    ("sambanova", _load_sambanova),
    ("openai",    _load_openai),
    ("anthropic", _load_anthropic),
]

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

_config_cache = None

def _load_config():
    global _config_cache
    if _config_cache is not None:
        return _config_cache
    cfg_path = Path(__file__).parent / "config.yaml"
    if yaml and cfg_path.exists():
        with open(cfg_path) as f:
            _config_cache = yaml.safe_load(f) or {}
    else:
        _config_cache = {}
    return _config_cache

def _cfg(dotpath: str):
    """config.yaml lookup: 'cerebras.api_key' → config['cerebras']['api_key']"""
    cfg = _load_config()
    parts = dotpath.split(".")
    val = cfg
    for p in parts:
        if not isinstance(val, dict):
            return None
        val = val.get(p)
    return val

# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------

def get_llm(preferred: str = None):
    order = PROVIDER_ORDER[:]
    pref = preferred or os.environ.get("COMPILE_PROVIDER") or _cfg("provider")
    if pref:
        order.sort(key=lambda x: 0 if x[0] == pref else 1)

    for name, loader in order:
        fn = loader()
        if fn:
            print(f"[compile] provider: {name}")
            return fn

    print("[compile] ERROR: no LLM provider available.")
    print("  Set one of: CEREBRAS_API_KEY, GROQ_API_KEY, SAMBANOVA_API_KEY,")
    print("              OPENAI_API_KEY, ANTHROPIC_API_KEY")
    print("  Or fill scripts/config.yaml")
    sys.exit(1)

# ---------------------------------------------------------------------------
# JSONL parsing
# ---------------------------------------------------------------------------

def find_latest_session() -> Path:
    """Find the most recently modified .jsonl file in Claude Code project dirs."""
    base = Path.home() / ".claude" / "projects"
    if not base.exists():
        print(f"[compile] Claude projects dir not found: {base}")
        sys.exit(1)

    candidates = sorted(base.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        print("[compile] No .jsonl session files found.")
        sys.exit(1)
    return candidates[0]


def extract_turns(jsonl_path: Path, max_chars: int = 40_000) -> str:
    """Extract human + assistant turns from JSONL, truncated to max_chars."""
    lines = []
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

                role = obj.get("role") or obj.get("type")
                content = obj.get("content") or obj.get("message") or ""

                if isinstance(content, list):
                    parts = []
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            parts.append(block.get("text", ""))
                    content = "\n".join(parts)

                if role and content and isinstance(content, str):
                    lines.append(f"[{role}]: {content[:2000]}")
    except Exception as e:
        print(f"[compile] Failed to read {jsonl_path}: {e}")
        sys.exit(1)

    full = "\n\n".join(lines)
    if len(full) > max_chars:
        full = full[-max_chars:]  # keep tail (most recent)
    return full

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM = """You are a memory compiler for Claude Code sessions.
Your job: read a conversation transcript and extract persistent knowledge
in structured Markdown format for an Obsidian-style memory vault.

Output ONLY valid Markdown. No extra commentary.
"""

PROMPT_SESSION = """Analyze this Claude Code session transcript and write a concise session summary.

Format:
---
## Session {date}

### Shipped
- bullet list of completed tasks

### Decisions
- bullet list of key decisions made

### Open
- bullet list of unresolved items / next steps

### Insights
- any non-obvious facts, gotchas, or lessons learned
---

TRANSCRIPT (last portion):
{transcript}
"""

PROMPT_MEMORIES = """Analyze this Claude Code session transcript and extract persistent memory entries.

For each distinct piece of knowledge worth remembering, output a block like:

=== MEMORY ===
type: feedback|user|project|concept
name: snake_case_name
description: one line for search
body: |
  The memory content (2-10 lines).
  For feedback: rule + Why: + How to apply:
  For project: fact + Why: + How to apply:
=== END ===

Only output entries for genuinely new, non-obvious, persistent facts.
Skip ephemeral task details. Output nothing if nothing worth saving.

TRANSCRIPT (last portion):
{transcript}
"""

# ---------------------------------------------------------------------------
# Memory vault helpers
# ---------------------------------------------------------------------------

def find_memory_root() -> Path | None:
    """Look for memory/ vault in common locations."""
    candidates = [
        Path.home() / ".claude" / "projects" / "-root" / "memory",
        Path.home() / "dj-memory",
        Path("memory"),
    ]
    custom = _cfg("memory_path")
    if custom:
        candidates.insert(0, Path(custom))

    for p in candidates:
        if p.exists() and p.is_dir():
            return p
    return None


def save_session_log(memory_root: Path, date_str: str, summary: str, dry_run: bool):
    sessions_dir = memory_root / "sessions"
    sessions_dir.mkdir(exist_ok=True)
    out = sessions_dir / f"{date_str}.md"

    block = f"\n\n<!-- compiled by compile.py -->\n{summary.strip()}\n"
    if dry_run:
        print(f"\n--- would append to {out} ---\n{block}\n---")
    else:
        with open(out, "a") as f:
            f.write(block)
        print(f"[compile] Session log → {out}")


def parse_memory_blocks(text: str) -> list[dict]:
    blocks = []
    parts = text.split("=== MEMORY ===")
    for part in parts[1:]:
        end = part.find("=== END ===")
        if end == -1:
            continue
        raw = part[:end].strip()
        entry = {}
        lines = raw.splitlines()
        body_lines = []
        in_body = False
        for line in lines:
            if in_body:
                body_lines.append(line)
            elif line.startswith("type:"):
                entry["type"] = line.split(":", 1)[1].strip()
            elif line.startswith("name:"):
                entry["name"] = line.split(":", 1)[1].strip()
            elif line.startswith("description:"):
                entry["description"] = line.split(":", 1)[1].strip()
            elif line.startswith("body:"):
                in_body = True
        if body_lines:
            # strip common leading whitespace from body (yaml block scalar indent)
            min_indent = min((len(l) - len(l.lstrip()) for l in body_lines if l.strip()), default=0)
            entry["body"] = "\n".join(l[min_indent:] for l in body_lines)
        if "name" in entry and "body" in entry:
            blocks.append(entry)
    return blocks


def save_memories(memory_root: Path, blocks: list[dict], date_str: str, dry_run: bool):
    for entry in blocks:
        name = entry.get("name", "unnamed").replace(" ", "_").lower()
        etype = entry.get("type", "concept")
        folder_map = {
            "feedback": "feedback",
            "user": "user",
            "project": "projects",
            "concept": "concepts",
        }
        folder = folder_map.get(etype, "concepts")
        dest_dir = memory_root / folder
        dest_dir.mkdir(exist_ok=True)
        dest = dest_dir / f"{name}.md"

        content = f"""---
name: {name}
description: {entry.get('description', '')}
type: {etype}
created: {date_str}
---

{entry['body'].strip()}
"""
        if dry_run:
            print(f"\n--- would write {dest} ---\n{content}\n---")
        else:
            if dest.exists():
                print(f"[compile] SKIP (exists): {dest}")
            else:
                dest.write_text(content)
                print(f"[compile] Memory → {dest}")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Compile Claude Code session to memory")
    parser.add_argument("--session", help="Path to .jsonl session file")
    parser.add_argument("--provider", help="LLM provider override")
    parser.add_argument("--dry-run", action="store_true", help="Print without saving")
    parser.add_argument("--no-memories", action="store_true", help="Skip memory extraction")
    args = parser.parse_args()

    session_path = Path(args.session) if args.session else find_latest_session()
    print(f"[compile] session: {session_path}")

    transcript = extract_turns(session_path)
    print(f"[compile] transcript: {len(transcript):,} chars")

    llm = get_llm(args.provider)
    date_str = datetime.now().strftime("%Y-%m-%d")

    # 1. Session summary
    print("[compile] generating session summary...")
    t0 = time.time()
    summary = llm(PROMPT_SESSION.format(date=date_str, transcript=transcript), SYSTEM)
    print(f"[compile] summary done ({time.time()-t0:.1f}s)")

    memory_root = find_memory_root()
    if memory_root:
        save_session_log(memory_root, date_str, summary, args.dry_run)
    else:
        print("[compile] memory vault not found — printing summary:\n")
        print(summary)

    if args.no_memories:
        return

    # 2. Memory extraction
    print("[compile] extracting memory entries...")
    t0 = time.time()
    raw_memories = llm(PROMPT_MEMORIES.format(transcript=transcript), SYSTEM)
    print(f"[compile] extraction done ({time.time()-t0:.1f}s)")

    blocks = parse_memory_blocks(raw_memories)
    print(f"[compile] found {len(blocks)} memory entries")

    if memory_root and blocks:
        save_memories(memory_root, blocks, date_str, args.dry_run)
    elif blocks:
        print("[compile] memory vault not found — printing entries:\n")
        print(raw_memories)


if __name__ == "__main__":
    main()
