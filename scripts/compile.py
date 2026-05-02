#!/usr/bin/env python3
"""
compile.py — Karpathy-style session compiler for Claude Code memory.

Reads Claude Code JSONL transcripts, extracts conversation turns,
and uses an LLM to synthesize memory entries (user facts, feedback,
project state) in the format expected by the memory/ vault.

Quickstart — set ANY one of these and it works:

    export LLM_API_KEY="your-key"          # universal: works with any OpenAI-compatible API
    export LLM_BASE_URL="https://..."      # optional: defaults to OpenAI
    export LLM_MODEL="llama-3.3-70b"       # optional: defaults to gpt-4o-mini

Named providers (auto-detected from their env vars):

    CEREBRAS_API_KEY   → api.cerebras.ai   (free tier)
    GROQ_API_KEY       → api.groq.com      (free tier)
    SAMBANOVA_API_KEY  → api.sambanova.ai
    OPENAI_API_KEY     → api.openai.com
    ANTHROPIC_API_KEY  → api.anthropic.com

Priority: LLM_API_KEY → Cerebras → Groq → SambaNova → OpenAI → Anthropic

Usage:
    python compile.py                        # auto-detect latest session
    python compile.py --session <path.jsonl> # specific session file
    python compile.py --provider cerebras    # override named provider
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
# Provider registry — auto-detect model from /v1/models
# ---------------------------------------------------------------------------

# Known providers: key env var → (base_url, preferred model names in priority order)
# The script calls /v1/models and picks the first available from the priority list.
# If none match, it falls back to the first model returned by the API.
KNOWN_PROVIDERS = [
    {
        "name":     "cerebras",
        "key_env":  "CEREBRAS_API_KEY",
        "cfg_key":  "cerebras.api_key",
        "base_url": "https://api.cerebras.ai/v1",
        "priority": [
            "qwen-3-235b-a22b-instruct-2507",
            "gpt-oss-120b",
            "llama3.1-8b",
        ],
    },
    {
        "name":     "groq",
        "key_env":  "GROQ_API_KEY",
        "cfg_key":  "groq.api_key",
        "base_url": "https://api.groq.com/openai/v1",
        "priority": [
            "llama-3.3-70b-versatile",
            "llama-3.1-70b-versatile",
            "llama3-70b-8192",
            "mixtral-8x7b-32768",
        ],
    },
    {
        "name":     "sambanova",
        "key_env":  "SAMBANOVA_API_KEY",
        "cfg_key":  "sambanova.api_key",
        "base_url": "https://api.sambanova.ai/v1",
        "priority": [
            "Meta-Llama-3.3-70B-Instruct",
            "Meta-Llama-3.1-70B-Instruct",
            "Meta-Llama-3.1-8B-Instruct",
        ],
    },
    {
        "name":     "openai",
        "key_env":  "OPENAI_API_KEY",
        "cfg_key":  "openai.api_key",
        "base_url": "https://api.openai.com/v1",
        "priority": [
            "gpt-4o-mini",
            "gpt-4o",
            "gpt-3.5-turbo",
        ],
    },
]


def _fetch_models(client) -> list[str]:
    """Fetch available model IDs from /v1/models. Returns [] on error."""
    try:
        resp = client.models.list()
        return [m.id for m in resp.data]
    except Exception:
        return []


def _pick_model(available: list[str], priority: list[str]) -> str | None:
    """Pick first model from priority list that exists in available. Falls back to first available."""
    for p in priority:
        if p in available:
            return p
    # fuzzy fallback: partial match
    for p in priority:
        for a in available:
            if p.lower() in a.lower() or a.lower() in p.lower():
                return a
    return available[0] if available else None


def _make_caller(client, model: str, fallback_models: list[str] = None):
    def call(prompt, system=""):
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": prompt})
        models_to_try = [model] + [m for m in (fallback_models or []) if m != model]
        last_err = None
        for m in models_to_try:
            try:
                r = client.chat.completions.create(model=m, messages=msgs, max_tokens=2000)
                if m != model:
                    print(f"[compile] fell back to model: {m}")
                return r.choices[0].message.content
            except Exception as e:
                last_err = e
                if "429" in str(e) or "rate" in str(e).lower() or "quota" in str(e).lower():
                    continue
                raise
        raise last_err
    return call


def _load_provider(spec: dict):
    """Try to load a named provider. Returns callable or None."""
    try:
        import openai as _openai
    except ImportError:
        return None

    key = os.environ.get(spec["key_env"]) or _cfg(spec["cfg_key"])
    if not key:
        return None

    # allow model override via env / config
    model_override = (
        os.environ.get(spec["name"].upper() + "_MODEL")
        or _cfg(spec["name"] + ".model")
    )

    try:
        client = _openai.OpenAI(api_key=key, base_url=spec["base_url"])
        if model_override:
            model = model_override
        else:
            available = _fetch_models(client)
            model = _pick_model(available, spec["priority"])
            if not model:
                return None
        print(f"[compile] provider: {spec['name']}  model: {model}")
        return _make_caller(client, model, fallback_models=available)
    except Exception:
        return None


def _load_universal():
    """LLM_API_KEY + LLM_BASE_URL — any OpenAI-compatible API, model auto-detected."""
    try:
        import openai as _openai
    except ImportError:
        return None

    key = os.environ.get("LLM_API_KEY") or _cfg("llm.api_key")
    if not key:
        return None

    base_url = os.environ.get("LLM_BASE_URL") or _cfg("llm.base_url") or "https://api.openai.com/v1"
    model_override = os.environ.get("LLM_MODEL") or _cfg("llm.model")

    # generic priority list used when no explicit model given
    generic_priority = [
        "llama-3.3-70b-versatile", "llama-3.1-70b-versatile",
        "qwen-3-235b-a22b-instruct-2507", "gpt-oss-120b",
        "Meta-Llama-3.3-70B-Instruct", "gpt-4o-mini",
        "llama3.1-8b", "llama3-70b-8192",
    ]

    try:
        client = _openai.OpenAI(api_key=key, base_url=base_url)
        if model_override:
            model = model_override
        else:
            available = _fetch_models(client)
            model = _pick_model(available, generic_priority) or "gpt-4o-mini"
        print(f"[compile] provider: universal ({base_url.split('/')[2]})  model: {model}")
        return _make_caller(client, model, fallback_models=available)
    except Exception:
        return None


def _load_anthropic():
    """Anthropic — separate SDK, no /v1/models auto-detect."""
    try:
        import anthropic
    except ImportError:
        return None

    key = os.environ.get("ANTHROPIC_API_KEY") or _cfg("anthropic.api_key")
    if not key:
        return None

    model = os.environ.get("ANTHROPIC_MODEL") or _cfg("anthropic.model") or "claude-haiku-4-5-20251001"

    try:
        client = anthropic.Anthropic(api_key=key)
        print(f"[compile] provider: anthropic  model: {model}")

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
    pref = preferred or os.environ.get("COMPILE_PROVIDER") or _cfg("provider")

    # Build ordered list: universal first, then named providers, then anthropic
    named = list(KNOWN_PROVIDERS)
    if pref:
        named.sort(key=lambda s: 0 if s["name"] == pref else 1)

    loaders = [("universal", _load_universal)]
    loaders += [(s["name"], lambda s=s: _load_provider(s)) for s in named]
    loaders += [("anthropic", _load_anthropic)]

    for name, loader in loaders:
        fn = loader()
        if fn:
            return fn

    print("[compile] ERROR: no LLM provider available.")
    print("  Set any one of these env vars:")
    print("    LLM_API_KEY=<key> LLM_BASE_URL=https://api.groq.com/openai/v1")
    print("    CEREBRAS_API_KEY=<key>")
    print("    GROQ_API_KEY=<key>")
    print("    SAMBANOVA_API_KEY=<key>")
    print("    OPENAI_API_KEY=<key>")
    print("    ANTHROPIC_API_KEY=<key>")
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


MEMORY_INDEX_SECTIONS = {
    "feedback": "## 💬 FEEDBACK",
    "user":     "## 👤 USER",
    "project":  "## 📁 PROJECTS",
    "concept":  "## 🧠 CONCEPTS",
}


def update_memory_index(memory_root: Path, name: str, description: str, etype: str, dry_run: bool):
    """Append wikilink entry to MEMORY.md under the right section (creates section if missing)."""
    index_path = memory_root / "MEMORY.md"
    if not index_path.exists():
        return

    text = index_path.read_text(errors="replace")

    # Skip if already referenced
    if f"[[{name}]]" in text or f"[[{name}|" in text:
        print(f"[compile] MEMORY.md already has [[{name}]] — skip")
        return

    line = f"- [[{name}|{description}]]\n"
    section_header = MEMORY_INDEX_SECTIONS.get(etype, "## 🧠 CONCEPTS")

    if section_header in text:
        # Insert after the section header line
        idx = text.index(section_header)
        end_of_header = text.index("\n", idx) + 1
        new_text = text[:end_of_header] + line + text[end_of_header:]
    else:
        # Section doesn't exist — append at end
        new_text = text.rstrip() + f"\n\n{section_header}\n{line}"

    if dry_run:
        print(f"\n--- would add to MEMORY.md ---\n{line}---")
    else:
        index_path.write_text(new_text)
        print(f"[compile] MEMORY.md ← [[{name}]]")


def save_memories(memory_root: Path, blocks: list[dict], date_str: str, dry_run: bool):
    for entry in blocks:
        name = entry.get("name", "unnamed").replace(" ", "_").lower()
        etype = entry.get("type", "concept")
        description = entry.get("description", "")
        folder_map = {
            "feedback": "feedback",
            "user":     "user",
            "project":  "projects",
            "concept":  "concepts",
        }
        folder = folder_map.get(etype, "concepts")
        dest_dir = memory_root / folder
        dest_dir.mkdir(exist_ok=True)
        dest = dest_dir / f"{name}.md"

        content = f"""---
name: {name}
description: {description}
type: {etype}
created: {date_str}
---

{entry['body'].strip()}
"""
        if dry_run:
            print(f"\n--- would write {dest} ---\n{content}\n---")
            update_memory_index(memory_root, name, description, etype, dry_run=True)
        else:
            if dest.exists():
                print(f"[compile] SKIP (exists): {dest}")
            else:
                dest.write_text(content)
                print(f"[compile] Memory → {dest}")
                update_memory_index(memory_root, name, description, etype, dry_run=False)

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
