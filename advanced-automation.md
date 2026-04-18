# Advanced Automation — Full Memory Pipeline

When the basic setup from [memory-setup.md](memory-setup.md) stops scaling (100+ memory files, multi-hour sessions, multiple input sources), this guide covers the automation layer: hooks that fire on their own, a warm-model daemon, a nightly cron pipeline, and a Karpathy-style compiler powered by a free LLM.

Everything here is additive — you can adopt pieces independently.

---

## Table of Contents

1. [Why automate](#why-automate)
2. [Hook map](#hook-map)
3. [UserPromptSubmit — auto semantic search injection](#userpromptsubmit--auto-semantic-search-injection)
4. [SessionEnd / Stop / PreCompact — auto archive + mine](#sessionend--stop--precompact--auto-archive--mine)
5. [MemPalace daemon — warm model via Unix socket](#mempalace-daemon--warm-model-via-unix-socket)
6. [Nightly cron — mine, compile, systematize](#nightly-cron--mine-compile-systematize)
7. [Karpathy compile with a free LLM (key rotation)](#karpathy-compile-with-a-free-llm-key-rotation)
8. [BOOT_CONTEXT — a high-signal manual anchor](#boot_context--a-high-signal-manual-anchor)
9. [Multi-source ingestion](#multi-source-ingestion)
10. [Tradeoffs and gotchas](#tradeoffs-and-gotchas)

---

## Why automate

The basic setup has one problem: **you have to remember to remember**. You run `mempalace mine` manually, you decide when to compile wikis, you ask Claude to load context.

Automation moves that work into the background:

- **Hooks** fire on session events (start, end, compact, prompt) — no clicks required
- **A daemon** keeps the embedding model warm, so semantic search is <300ms instead of 3+ seconds
- **Nightly cron** handles mining, compilation, and index rebuilds while you sleep
- **Multi-source ingestion** pulls in notes from Telegram, web clippers, and external repos without manual copy-paste

Net effect: memory grows even when you're not thinking about it, and relevant slices of it show up in your context without you having to fetch them.

---

## Hook map

Claude Code exposes several events. Here's the full picture:

| Event | When it fires | Typical use |
|-------|---------------|-------------|
| `SessionStart` | Before the first prompt | Inject boot context, identity, recent log |
| `UserPromptSubmit` | Every user message | Auto-run semantic search, inject top-K snippets |
| `Stop` | When Claude finishes a turn | Archive transcript, mine new memory |
| `PreCompact` | Before context compression | Same as Stop — last chance to save state |
| `SessionEnd` | When the session closes | Final flush, background processing |

All hooks live in `~/.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [{ "type": "command", "command": "python3 ~/.claude/hooks/session-start.py", "timeout": 15 }] }
    ],
    "UserPromptSubmit": [
      { "hooks": [{ "type": "command", "command": "python3 ~/.claude/hooks/user-prompt-search.py", "timeout": 15 }] }
    ],
    "Stop": [
      { "hooks": [{ "type": "command", "command": "bash ~/.claude/hooks/auto_memory.sh" }] }
    ],
    "PreCompact": [
      { "hooks": [{ "type": "command", "command": "bash ~/.claude/hooks/auto_memory.sh" }] }
    ],
    "SessionEnd": [
      { "hooks": [{ "type": "command", "command": "python3 ~/.claude/hooks/session-end.py" }] }
    ]
  }
}
```

Python and bash both work; pick whichever you debug faster. All hooks return JSON with `hookSpecificOutput.additionalContext` to inject text into Claude's context, or exit 0 silently to do nothing.

---

## UserPromptSubmit — auto semantic search injection

The most useful hook of the bunch. On every user message, it:

1. Checks if the message contains **strategic keywords** (project names, status questions, finance, decisions)
2. If yes — runs a semantic search against your MemPalace
3. Injects the top-5 snippets as `additionalContext`

This way, every time you ask "what's the status of X?" — relevant memories are already in context before Claude generates a single token. No tool call needed.

**Key insight:** filter by keyword first. Running semantic search on *every* "hey" or "thanks" wastes tokens and latency. A ~100-pattern regex keeps overhead under 1% of messages.

### Sketch

```python
#!/usr/bin/env python3
"""UserPromptSubmit hook — auto-inject memory search."""
import json, re, socket, sys

DAEMON_SOCKET = "/tmp/mempalace-daemon.sock"

# Narrow list — only fire on strategic questions.
STRATEGIC_PATTERNS = [
    # Project names (customize for your stack)
    r"\bmyproject\b", r"\bbackend\b",
    # Status
    r"status", r"ready\b", r"progress", r"stuck",
    # Finance / decisions
    r"money", r"revenue", r"plan\b", r"decision",
    # Memory references
    r"remember", r"we (did|decided|built)",
]

data = json.loads(sys.stdin.read())
prompt = data.get("prompt", "").lower()

if not any(re.search(p, prompt) for p in STRATEGIC_PATTERNS):
    sys.exit(0)  # not strategic — skip silently

# Query daemon (fast path) — fall back to CLI if daemon is down
try:
    s = socket.socket(socket.AF_UNIX)
    s.settimeout(2)
    s.connect(DAEMON_SOCKET)
    s.sendall(json.dumps({"query": prompt[:250], "limit": 5}).encode() + b"\n")
    resp = json.loads(s.recv(65536).decode())
    results = resp.get("results", [])
except Exception:
    results = []

if not results:
    sys.exit(0)

context = "## Memory hit\n\n" + "\n\n".join(
    f"[{i+1}] {r['source']} (sim {r['similarity']:.3f}):\n{r['snippet'][:500]}"
    for i, r in enumerate(results)
)

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": context,
    }
}))
```

**What to keep in mind:**

- Keyword list is yours — tune it to your projects. Too broad = noise. Too narrow = missed context.
- Inject a short disclaimer (`_auto-injected — verify before citing_`) so Claude treats it as hints, not facts.
- Cap snippet length (~500 chars) — 5 snippets × 500 chars ≈ 2.5K tokens, affordable.
- Timeouts matter: if the daemon is stuck, don't block the user's prompt.

---

## SessionEnd / Stop / PreCompact — auto archive + mine

Every turn, Claude Code writes a JSONL transcript to `~/.claude/projects/<path>/*.jsonl`. You want to:

1. **Archive** it — transcripts can be compacted or rotated, keep a copy elsewhere
2. **Mine** it into MemPalace so future semantic searches see it
3. **Compile** it into wiki-style notes when it's mature enough

A single shell script wired to Stop/PreCompact does all three:

```bash
#!/bin/bash
# ~/.claude/hooks/auto_memory.sh
set -e

MEMORY="$HOME/.claude/projects/<your-path>/memory"
RAW_ARCHIVE="$HOME/backups/memory_raw_sessions"
PALACE_VENV="$HOME/.mempalace-venv"
SESSION_DIR="$HOME/.claude/projects/<your-path>"

mkdir -p "$RAW_ARCHIVE"

# 1. Archive raw JSONL (idempotent — only copies newer files)
for jsonl in "$SESSION_DIR"/*.jsonl; do
    [ -f "$jsonl" ] || continue
    base=$(basename "$jsonl")
    if [ ! -f "$RAW_ARCHIVE/$base" ] || [ "$jsonl" -nt "$RAW_ARCHIVE/$base" ]; then
        cp "$jsonl" "$RAW_ARCHIVE/$base" 2>/dev/null || true
    fi
done

# 2. Mine new files into MemPalace (skips already-indexed)
if [ -d "$PALACE_VENV" ]; then
    source "$PALACE_VENV/bin/activate"
    mempalace mine "$MEMORY" --wing memory_wiki 2>/dev/null || true
    deactivate
fi

# 3. Compile mature sessions into wiki notes (see Karpathy section)
[ -f "$HOME/.claude/compile_sessions.py" ] && \
    python3 "$HOME/.claude/compile_sessions.py" --run 2>/dev/null || true
```

**Gotchas:**

- Run this on both `Stop` and `PreCompact`. Stop fires when Claude's done; PreCompact fires before compression, which may trim state you haven't archived yet.
- Use `set -e` carefully — you don't want a single failure to block the next step. The example falls back gracefully with `|| true`.
- Don't block on heavy work. If compilation takes 30+ seconds, spawn it in the background (`nohup python3 ... &`).

---

## MemPalace daemon — warm model via Unix socket

Cold MemPalace queries take 3–5 seconds because the embedding model loads on every invocation. A daemon keeps it loaded in memory and answers over a Unix socket in <300ms.

### Daemon skeleton

```python
#!/usr/bin/env python3
"""MemPalace daemon — Unix socket server with warm embedding model."""
import json, os, socket, sys, threading

sys.path.insert(0, f"{os.path.expanduser('~')}/.mempalace-venv/lib/python3.12/site-packages")
from mempalace.palace import get_collection

PALACE_PATH = os.path.expanduser("~/.mempalace/palace")
SOCKET_PATH = "/tmp/mempalace-daemon.sock"

COLLECTION = get_collection(PALACE_PATH, create=False)
# Warm-up query so the model is in RAM
COLLECTION.query(query_texts=["warmup"], n_results=1, include=["distances"])

def handle(conn):
    try:
        data = conn.recv(4096).decode()
        req = json.loads(data.strip())
        res = COLLECTION.query(
            query_texts=[req["query"][:250]],
            n_results=min(req.get("limit", 5), 20),
            include=["documents", "metadatas", "distances"],
        )
        results = [
            {"source": m.get("source_file", ""), "snippet": d, "similarity": 1 - dist}
            for d, m, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0])
        ]
        conn.sendall((json.dumps({"results": results}) + "\n").encode())
    finally:
        conn.close()

try: os.unlink(SOCKET_PATH)
except FileNotFoundError: pass

srv = socket.socket(socket.AF_UNIX)
srv.bind(SOCKET_PATH)
os.chmod(SOCKET_PATH, 0o600)
srv.listen(8)

while True:
    conn, _ = srv.accept()
    threading.Thread(target=handle, args=(conn,), daemon=True).start()
```

### Running it

A systemd user unit is the cleanest option:

```ini
# ~/.config/systemd/user/mempalace-daemon.service
[Unit]
Description=MemPalace daemon

[Service]
ExecStart=/home/%u/.mempalace-venv/bin/python /home/%u/.claude/hooks/mempalace-daemon.py
Restart=on-failure

[Install]
WantedBy=default.target
```

```bash
systemctl --user enable --now mempalace-daemon
```

For macOS, use `launchd` (`~/Library/LaunchAgents/`) with a plist that keeps the process alive.

### Clients fall back

UserPromptSubmit should try the daemon first, fall back to the CLI if the socket isn't there. This way a crashed daemon degrades to slow searches instead of no searches.

---

## Nightly cron — mine, compile, systematize

Some work doesn't belong in a hook — it's too slow, or it can wait. Run it once a day at 6 AM:

```bash
# ~/.claude/hooks/nightly_memory.sh
#!/bin/bash
set -e
LOCK=/tmp/nightly_memory.lock
exec 200>"$LOCK"
flock -n 200 || exit 0

LOG=/var/log/nightly_memory.log
MEMORY="$HOME/.claude/projects/<your-path>/memory"
PALACE_VENV="$HOME/.mempalace-venv"

log() { echo "[$(date '+%F %T')] $*" >> "$LOG"; }
log "=== START ==="

source "$PALACE_VENV/bin/activate"

# 1. Mine fresh notes
mempalace mine "$MEMORY" --wing memory_wiki >> "$LOG" 2>&1

# 2. (Optional) AAAK compression — see tradeoffs section.
#    The MemPalace authors report 96.6% -> 84.2% accuracy regression vs raw.
#    Skip unless you need the token savings.
# mempalace compress --wing memory_wiki

deactivate

# 3. Karpathy compile (sessions -> concepts)
python3 "$HOME/.claude/memory-scripts/compile_local.py" >> "$LOG" 2>&1

# 4. Rebuild hub + reports from compiled concepts
python3 "$HOME/.claude/memory-scripts/systematize_concepts.py" >> "$LOG" 2>&1

log "=== DONE ==="
```

Cron entry:

```
0 6 * * * /bin/bash $HOME/.claude/hooks/nightly_memory.sh
```

**`flock` is not optional** — cron can overlap with a hook-triggered run and corrupt the ChromaDB collection. The `flock -n` exits silently if another instance is active.

---

## Karpathy compile with a free LLM (key rotation)

Andrej Karpathy's knowledge-base idea: don't keep raw session transcripts forever — compile them into topic-based notes with tags. MemPalace handles semantic retrieval; the compiler handles abstraction.

**Tool choice:** any LLM works, but running this for free is a win. Cerebras, Groq, and similar providers give generous rate limits on their web-tier API keys. Rotate across 5–10 keys and you can run nightly compilation for $0.

### Rough shape

```python
#!/usr/bin/env python3
"""Compile raw session notes into tagged concept files."""
import hashlib, random, re
from pathlib import Path
import httpx

ENV_FILE = Path("/path/to/your/.env")
API_URL = "https://api.cerebras.ai/v1/chat/completions"
MODEL = "qwen-3-235b-a22b-instruct-2507"  # free tier, generous limits

SESSION_DIR = Path.home() / ".claude/projects/<path>/memory/sessions"
CONCEPT_DIR = Path.home() / ".claude/projects/<path>/memory/concepts"
STATE_FILE = Path.home() / ".claude/memory-scripts/compile_local_state.json"

def load_keys() -> list[str]:
    """Parse rotating API keys from .env: LLM_KEY_CEREBRAS_1=..., _2=..., etc."""
    return [
        m.group(1)
        for line in ENV_FILE.read_text().splitlines()
        if (m := re.match(r"LLM_KEY_CEREBRAS_\d+=(.+)", line.strip()))
    ]

def chat(prompt: str, max_tokens: int = 3000) -> str | None:
    keys = load_keys()
    random.shuffle(keys)
    for key in keys[:8]:  # try up to 8 before giving up
        try:
            r = httpx.post(API_URL, timeout=30,
                headers={"Authorization": f"Bearer {key}"},
                json={"model": MODEL, "max_tokens": max_tokens,
                      "messages": [{"role": "user", "content": prompt}]})
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"]
        except Exception:
            continue
    return None

PROMPT_TEMPLATE = """You are compiling a raw session log into a structured concept note.

Input: session transcript, possibly noisy, with code and side chatter.

Output: markdown with this frontmatter:
---
name: <snake_case_topic>
description: <one-line gist>
type: concept
tags: [<3-7 tags>]
---

Then 3-6 sections with headings. Lead with decisions and why; demote code to the bottom.

Session:
---
{content}
---"""

def compile_file(path: Path) -> None:
    content = path.read_text()[:12000]  # Cerebras max_tokens headroom
    out = chat(PROMPT_TEMPLATE.format(content=content))
    if not out:
        return

    # Extract name from the frontmatter the model produced
    m = re.search(r"name:\s*(\w+)", out)
    slug = m.group(1) if m else f"concept_{hashlib.sha1(path.name.encode()).hexdigest()[:8]}"
    (CONCEPT_DIR / f"{slug}.md").write_text(out)

for session in SESSION_DIR.glob("*.md"):
    # Skip already-compiled (check state file in real code)
    compile_file(session)
```

### Why this pattern scales

- Raw transcripts rot — nobody reads a 2000-line session log three months later
- Compiled concepts are short, tagged, and grep-friendly
- The original is still in MemPalace for semantic lookup
- Tags created by the model aren't perfect, but they're vastly better than none

### Systematize step

After compilation, run `systematize_concepts.py`:

- Merges near-duplicates (cosine sim > 0.9 on embeddings)
- Regenerates `Concepts.md` hub with links and frontmatter descriptions
- Drops weak/short concepts into `_weak.md` for manual review

This keeps the concept folder from accreting noise over time.

---

## BOOT_CONTEXT — a high-signal manual anchor

`mempalace wake-up` gives you ~1300 tokens of identity. That's great, but it's generated — it may miss recent context or deprioritize things you consider load-bearing.

A `BOOT_CONTEXT.md` file, manually maintained, complements wake-up with high-signal information that you want Claude to see **every session, every time**:

```markdown
# BOOT CONTEXT — read first, every session

## Who you're working with
- [1-2 lines: role, comms style, language preferences]

## What we're building (not optional reading)
- [Project name]: [one paragraph — what it actually is, not marketing copy]
- Stack: [fixed decisions — don't revisit these each session]
- Timeline: [dated milestones]

## Active incidents / frozen decisions
- [INC-YYYYMMDD-1] — [title] — [1 line lesson]
- [Decision 2026-MM-DD]: [what was decided + why — so Claude doesn't pitch alternatives]

## Where things live
- Memory vault: ~/.claude/projects/.../memory/
- Changelog: ~/projects/X/projectfasc.md
- [etc.]
```

The SessionStart hook injects this file's contents as additional context. Keep it under 15KB — longer and you're paying tokens on every session start for stale info.

---

## Multi-source ingestion

Your memory is only as useful as what lands in it. Beyond session transcripts, common sources worth wiring up:

| Source | Mechanism | Lands in |
|--------|-----------|----------|
| Telegram bot DMs | Bot that parses messages → markdown | `memory/tg_sessions/YYYY-MM-DD.md` |
| Obsidian Web Clipper | Browser extension saves articles | `memory/raw/clips/*.md` |
| External codebases / docs | `mempalace mine <path> --wing <name>` | Dedicated wing |
| Daily journal | `echo >> memory/daily/$(date +%F).md` from any script | `memory/daily/` |

All of these get mined by the nightly cron. Wings keep them separate from your core memory so semantic searches can be filtered (`search "auth flow" --wing backend_repo`).

---

## Tradeoffs and gotchas

### 1. AAAK compression regresses accuracy

MemPalace ships an experimental AAAK dialect that packs repeated entities into fewer tokens. The authors' own benchmarks show **96.6% → 84.2% R@5 regression on LongMemEval** vs raw mode. Unless you're token-constrained, **stay on raw**.

### 2. `mempalace compress` is destructive if misconfigured

Compression rewrites entries. If you point it at the wrong wing, you've lossy-encoded your main memory. Always compress a wing-specific subset, never the whole palace.

### 3. Hook timeouts swallow errors

A hook that throws an exception often exits silently with no output in Claude's UI. Log to a file (`>> ~/.claude/hooks/debug.log`) during development. Remove after.

### 4. ChromaDB lock contention

If your nightly cron overlaps with a Stop hook mining, ChromaDB can deadlock on the collection lock. `flock -n` on the nightly script fixes this. Also: don't run two MCP servers against the same collection.

### 5. Knowledge graph stays empty unless you use it

If you also run `mcp-server-memory` alongside MemPalace (for explicit entity/relation graphs), check `total_edges` occasionally. It silently stays at 0 if nothing writes to it. Either wire it in or remove from `settings.json`.

### 6. Don't commit secrets to your memory repo

If you version your `memory/` directory with git (recommended for backup), `secrets/` must be in `.gitignore` from day one. One missed commit means rotating every key in it. A precommit hook that greps for `sk-`, `csk-`, `ghp_`, `gho_`, `aws_` patterns catches accidents before they reach remote.

---

## Putting it together

Adoption order that makes sense:

1. **Basic memory-setup.md** first — CLAUDE.md, MEMORY.md, a few memory files. Don't skip this.
2. **Add SessionStart hook** with MemPalace wake-up + BOOT_CONTEXT. Immediate win.
3. **Add Stop/PreCompact** with `auto_memory.sh`. Memory starts growing on its own.
4. **Add UserPromptSubmit** with keyword filter. Auto-injected snippets save tool calls.
5. **Install the daemon** once you feel cold-query latency. ~300ms feels instant.
6. **Add nightly cron** when you hit 100+ memory files and want compilation.
7. **Wire multi-source ingestion** as you find sources worth pulling in.

You can skip or reorder any step — they compose.
