# Full Setup — Claude Code + Production Memory System

A complete, linear walkthrough: from zero (no Claude Code installed) to a production memory system with auto-archival, semantic search, a warm-model daemon, nightly compilation, and multi-source ingestion.

Each step builds on the previous one. You can stop at any point — each stage is useful on its own.

---

## Table of Contents

- [What you're building](#what-youre-building)
- [Prerequisites](#prerequisites)
- [Part 1 — Claude Code installed and running](#part-1--claude-code-installed-and-running)
- [Part 2 — Basic memory (CLAUDE.md + MEMORY.md)](#part-2--basic-memory-claudemd--memorymd)
- [Part 3 — MemPalace semantic layer](#part-3--mempalace-semantic-layer)
- [Part 4 — SessionStart hook (first automation)](#part-4--sessionstart-hook-first-automation)
- [Part 5 — Auto-capture (Stop / PreCompact / SessionEnd)](#part-5--auto-capture-stop--precompact--sessionend)
- [Part 6 — Quality of life: UserPromptSubmit + warm daemon](#part-6--quality-of-life-userpromptsubmit--warm-daemon)
- [Part 7 — Nightly cron: mine, compile, systematize](#part-7--nightly-cron-mine-compile-systematize)
- [Part 8 — Multi-source ingestion](#part-8--multi-source-ingestion)
- [Part 9 — Operating it](#part-9--operating-it)
- [Part 10 — Troubleshooting](#part-10--troubleshooting)
- [End-to-end verification](#end-to-end-verification)

---

## What you're building

By the end, you'll have a system where:

1. **CLAUDE.md** is auto-loaded on every session with your rules, identity, and project facts
2. **MEMORY.md** indexes all your stored memories
3. **MemPalace** holds a semantic vector store (local, free) with 12K+ drawers of mineable knowledge
4. **SessionStart hook** injects a BOOT_CONTEXT + recent daily log + wake-up identity into every fresh session
5. **UserPromptSubmit hook** auto-runs semantic search when you ask strategic questions and injects top results
6. **Stop / PreCompact / SessionEnd** archive every transcript, mine fresh notes, and compile sessions into concept files
7. **MemPalace daemon** answers semantic queries in <300ms via a Unix socket
8. **Nightly cron** mines, compresses, runs a free-LLM Karpathy compile, and rebuilds hubs
9. **Multi-source ingestion** pulls notes from Telegram bots, web clippers, and external repos

A production system that grows on its own, even when you're not thinking about it.

---

## Prerequisites

- Linux, macOS, or Windows (WSL)
- Node.js 18+
- Python 3.10+ (for hooks and the daemon)
- A Claude.ai subscription (Pro or Max)

Skip sections you already have.

---

## Part 1 — Claude Code installed and running

### 1.1 Subscribe to Claude

1. https://claude.ai → sign up / log in
2. Subscribe:
   - **Claude Pro** ($20/mo) — regular use
   - **Claude Max** ($100 or $200/mo) — heavy use, higher limits
3. This gives Claude Code access without separate API billing

### 1.2 Install Node.js

**Ubuntu/Debian:**
```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo bash -
sudo apt install -y nodejs
```

**macOS:**
```bash
brew install node
```

**Windows:**
Install LTS from https://nodejs.org, or use WSL + the Ubuntu instructions.

Verify:
```bash
node --version   # 18+
```

### 1.3 Install Claude Code

```bash
npm install -g @anthropic-ai/claude-code
```

Or without global install:
```bash
npx @anthropic-ai/claude-code
```

### 1.4 First launch

```bash
mkdir -p ~/projects && cd ~/projects
claude
```

1. Select **"Claude.ai account"**
2. Browser opens — log in
3. Confirm auth
4. Back in the terminal

Type `exit` to quit. You'll come back to this directory for the rest of the guide.

### 1.5 VS Code extension (optional)

VS Code users: Extensions → search **"Claude Code"** → install by Anthropic. `Ctrl+Shift+P` → **"Claude Code: Open"**.

### 1.6 Initial permissions

```bash
mkdir -p ~/.claude
nano ~/.claude/settings.json
```

```json
{
  "permissions": {
    "allow": [
      "Read(*)",
      "Edit(*)",
      "Write(*)",
      "Glob(*)",
      "Grep(*)",
      "Bash(git *)",
      "Bash(npm *)",
      "Bash(python3 *)",
      "Bash(ls *)"
    ]
  }
}
```

Widen as needed via `/permissions` inside a session.

---

## Part 2 — Basic memory (CLAUDE.md + MEMORY.md)

The foundation. Two files. Claude reads them on every session, automatically.

### 2.1 CLAUDE.md — your rules and identity

```bash
cd ~/projects
nano CLAUDE.md
```

```markdown
# My Assistant

## Identity
- Role: personal developer assistant
- Style: direct, no fluff, get things done

## About me
- [Your name, what you do]
- Stack: [languages, frameworks]
- Communication: [English / Russian / whatever]

## Hard rules
1. Read files BEFORE modifying them.
2. Don't touch code that wasn't asked about.
3. Verify before reporting "done".
4. One task at 100% beats ten at 60%.
5. Don't add docstrings or comments to unchanged code.

## Where things live
- Memory: ~/.claude/projects/-home-<user>-projects/memory/
- Changelog: ~/projects/<project>/projectfasc.md
- Rules: ~/projects/CLAUDE.md (this file)
```

### 2.2 Find your memory directory

The path is derived from where you launch `claude` (URL-encoded absolute path).

Easiest way:
```bash
claude
```

Ask Claude: `remember: test — show the path where memory is stored`.

It'll reveal a path like `~/.claude/projects/-home-user-projects/memory/`.

### 2.3 MEMORY.md — the index

```bash
MEM=~/.claude/projects/<your-encoded-path>/memory
mkdir -p "$MEM"
nano "$MEM/MEMORY.md"
```

```markdown
# Memory Index

## User
- [user_profile.md](user_profile.md) — role, stack, preferences

## Feedback
- [feedback_workflow.md](feedback_workflow.md) — behavioral rules

## Project
- [project_main.md](project_main.md) — current project context

## Reference
- [reference_links.md](reference_links.md) — external resources
```

Rules for the index:
- One line per file, under 150 chars
- Max ~200 lines (Claude Code truncates after that)
- A table of contents, not a content dump

### 2.4 First memory files

Each file uses YAML frontmatter:

```bash
nano "$MEM/user_profile.md"
```

```markdown
---
name: user_profile
description: Backend developer, Python + Go, prefers terse answers
type: user
---

Alex. Backend developer, 5 years experience. Works solo.
Stack: Python + Go, PostgreSQL, Docker.
Prefers short answers. No corporate speak.
Strong in databases — don't over-explain SQL.
New to frontend — explain React in detail.
```

```bash
nano "$MEM/feedback_workflow.md"
```

```markdown
---
name: feedback_workflow
description: Don't refactor neighboring code; verify before reporting done
type: feedback
---

## No drive-by refactors
Change only what was asked. Don't "improve" surrounding code.

**Why:** Creates noise in diffs; user controls when to modify each file.

**How to apply:** If I didn't ask for it — don't touch it.

## Verify before "done"
Never report a task done without running the actual thing.

**Why:** Lost trust by claiming tests passed when the test file was skipped.

**How to apply:** Run it. Check output. Confirm. Then report.
```

### 2.5 Check it works

```bash
cd ~/projects
claude
```

Ask: `Who am I? What are my hard rules?`

If Claude answers from `user_profile.md` and `CLAUDE.md` — basic memory is live.

---

## Part 3 — MemPalace semantic layer

File-based memory has a limit: you have to know which file to look in. MemPalace adds **vector semantic search** — find memories by meaning.

[MemPalace](https://github.com/milla-jovovich/mempalace) is open source, free, MIT-licensed. It runs locally using ChromaDB — nothing leaves your machine.

### 3.1 Install

```bash
python3 -m venv ~/.mempalace-venv
source ~/.mempalace-venv/bin/activate
pip install mempalace
mempalace --version
deactivate
```

Binary stays at `~/.mempalace-venv/bin/mempalace`.

### 3.2 Initialize

```bash
~/.mempalace-venv/bin/mempalace init
nano ~/.mempalace/identity.txt
```

```
Name: Alex
Role: Backend developer, Python + Go
Projects: e-commerce API (Django), CLI tools (Go)
Stack: Django, PostgreSQL, Redis, Docker
Key rules:
- Verify before presenting results
- Don't modify code that wasn't asked about
- Speed over perfection for MVP work
```

### 3.3 Mine your memory directory

```bash
MEMPALACE=~/.mempalace-venv/bin/mempalace
$MEMPALACE mine ~/.claude/projects/<your-path>/memory/ --wing memory
```

This embeds every markdown file into ChromaDB. `--wing memory` namespaces them (you'll add more wings later — `--wing docs`, `--wing codebase`, etc.).

### 3.4 Try it

```bash
$MEMPALACE search "what's my stack"
$MEMPALACE wake-up    # ~1300 tokens of identity + critical facts
```

If search returns your memories — the semantic layer works.

### 3.5 Register MemPalace as an MCP server

Give Claude Code direct access via MCP:

```json
// ~/.claude/settings.json — add to mcpServers
{
  "mcpServers": {
    "mempalace": {
      "command": "/home/<you>/.mempalace-venv/bin/python",
      "args": ["-m", "mempalace.mcp_server"]
    }
  }
}
```

Also add `"mcp__mempalace__*"` to the `permissions.allow` array.

Now Claude Code can call `mcp__mempalace__mempalace_search(...)` directly — no shell-out needed.

---

## Part 4 — SessionStart hook (first automation)

A hook is a script that fires on a Claude Code event. Your first hook injects context on every session start — `BOOT_CONTEXT.md` + the last daily log + MemPalace wake-up.

### 4.1 Write BOOT_CONTEXT.md

This file is high-signal, manually maintained, and loaded every session. It complements `mempalace wake-up` with things you want Claude to see literally every time:

```bash
MEM=~/.claude/projects/<your-path>/memory
nano "$MEM/BOOT_CONTEXT.md"
```

```markdown
# BOOT CONTEXT — read first, every session

## Who you're working with
- Alex. Solo backend dev. Prefers terse answers.

## What we're building (not optional reading)
- MyApp — e-commerce API. Django + PostgreSQL.
- Launch: 2026-06-01. Feature freeze: 2026-05-15.
- Stack is **fixed** — don't pitch alternatives.

## Active decisions (don't re-litigate)
- 2026-04-10: Django over FastAPI. Reason: team familiarity, deadline pressure.
- 2026-04-12: PostgreSQL over MySQL. Reason: need JSONB for product metadata.

## Where things live
- Vault: ~/.claude/projects/.../memory/
- Changelog: ~/projects/myapp/projectfasc.md
- Build log: ~/projects/myapp/BUILD_LOG.md
```

Keep under ~15KB. Longer → you're paying tokens for stale info.

### 4.2 Write the SessionStart hook

```bash
mkdir -p ~/.claude/hooks
nano ~/.claude/hooks/session-start.py
```

```python
#!/usr/bin/env python3
"""SessionStart hook — inject BOOT_CONTEXT + recent daily log + wake-up."""
import json, subprocess, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

MEMORY_DIR = Path.home() / ".claude/projects/<your-path>/memory"
BOOT_CONTEXT = MEMORY_DIR / "BOOT_CONTEXT.md"
DAILY_DIR = MEMORY_DIR / "daily"
MEMPALACE_BIN = Path.home() / ".mempalace-venv/bin/mempalace"
MAX_CONTEXT_CHARS = 64_000

def boot_context() -> str:
    return BOOT_CONTEXT.read_text() if BOOT_CONTEXT.exists() else ""

def recent_log() -> str:
    today = datetime.now(timezone.utc).astimezone()
    for offset in range(2):
        p = DAILY_DIR / f"{(today - timedelta(days=offset)).strftime('%Y-%m-%d')}.md"
        if p.exists():
            lines = p.read_text().splitlines()
            return "\n".join(lines[-30:])
    return ""

def wake_up() -> str:
    if not MEMPALACE_BIN.exists():
        return ""
    try:
        r = subprocess.run([str(MEMPALACE_BIN), "wake-up"], capture_output=True, timeout=5, text=True)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""

sections = [
    ("BOOT CONTEXT", boot_context()),
    ("Identity + critical facts", wake_up()),
    ("Recent daily log", recent_log()),
]
output = "\n\n---\n\n".join(f"## {name}\n\n{body}" for name, body in sections if body)[:MAX_CONTEXT_CHARS]

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": output,
    }
}))
```

```bash
chmod +x ~/.claude/hooks/session-start.py
```

### 4.3 Wire it into settings.json

```json
// ~/.claude/settings.json — add to hooks
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/session-start.py",
            "timeout": 15,
            "statusMessage": "Loading context..."
          }
        ]
      }
    ]
  }
}
```

### 4.4 Verify

```bash
cd ~/projects
claude
```

Ask: `What do you know from BOOT_CONTEXT?`

Claude should cite your decisions and project facts without reading the file explicitly — it already has them in context from the hook.

---

## Part 5 — Auto-capture (Stop / PreCompact / SessionEnd)

Every Claude Code session writes a JSONL transcript. You want those archived, mined, and (eventually) compiled. One shell script handles all three, wired to `Stop` and `PreCompact`.

### 5.1 Write auto_memory.sh

```bash
nano ~/.claude/hooks/auto_memory.sh
```

```bash
#!/bin/bash
# Archive JSONL transcripts, mine new memory files into MemPalace.
set +e

MEMORY="$HOME/.claude/projects/<your-path>/memory"
RAW_ARCHIVE="$HOME/backups/memory_raw_sessions"
PALACE_VENV="$HOME/.mempalace-venv"
SESSION_DIR="$HOME/.claude/projects/<your-path>"

mkdir -p "$RAW_ARCHIVE"

# 1. Archive raw JSONL (idempotent — only newer files)
for jsonl in "$SESSION_DIR"/*.jsonl; do
    [ -f "$jsonl" ] || continue
    base=$(basename "$jsonl")
    if [ ! -f "$RAW_ARCHIVE/$base" ] || [ "$jsonl" -nt "$RAW_ARCHIVE/$base" ]; then
        cp "$jsonl" "$RAW_ARCHIVE/$base" 2>/dev/null
    fi
done

# 2. Mine new memory files (skips already-indexed)
if [ -d "$PALACE_VENV" ]; then
    source "$PALACE_VENV/bin/activate"
    mempalace mine "$MEMORY" --wing memory 2>/dev/null
    deactivate
fi
```

```bash
chmod +x ~/.claude/hooks/auto_memory.sh
```

### 5.2 Wire it up

```json
// ~/.claude/settings.json — add to hooks
"Stop": [
  { "hooks": [{ "type": "command", "command": "bash ~/.claude/hooks/auto_memory.sh" }] }
],
"PreCompact": [
  { "hooks": [{ "type": "command", "command": "bash ~/.claude/hooks/auto_memory.sh" }] }
]
```

### 5.3 SessionEnd — full flush

`SessionEnd` fires once, when the session window closes. Use it to convert the transcript into a markdown session file for long-term retention:

```bash
nano ~/.claude/hooks/session-end.py
```

```python
#!/usr/bin/env python3
"""SessionEnd hook — save the transcript to a markdown session file."""
import json, os, sys
from datetime import datetime, timezone
from pathlib import Path

if os.environ.get("CLAUDE_INVOKED_BY"):
    sys.exit(0)  # nested invocation — skip

MEMORY = Path.home() / ".claude/projects/<your-path>/memory"
SESSIONS = MEMORY / "sessions"
SESSIONS.mkdir(parents=True, exist_ok=True)

data = json.loads(sys.stdin.read())
transcript_path = Path(data.get("transcript_path", ""))
if not transcript_path.exists():
    sys.exit(0)

turns = []
with open(transcript_path) as f:
    for line in f:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        role = entry.get("type", "")
        content = entry.get("message", {}).get("content", "")
        if isinstance(content, list):
            content = "\n".join(c.get("text", "") for c in content if isinstance(c, dict))
        if role in ("user", "assistant") and content.strip():
            turns.append(f"### {role}\n\n{content}")

out = SESSIONS / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d_%H%M')}.md"
out.write_text("\n\n".join(turns[-60:]))  # last 60 turns is enough
```

```json
// ~/.claude/settings.json
"SessionEnd": [
  { "hooks": [{ "type": "command", "command": "python3 ~/.claude/hooks/session-end.py" }] }
]
```

Now every finished session becomes a persistent markdown file in `memory/sessions/`, ready for mining and later compilation.

---

## Part 6 — Quality of life: UserPromptSubmit + warm daemon

Two upgrades that make semantic memory feel instant.

### 6.1 MemPalace daemon (warm model)

Cold queries take 3-5 seconds because the embedding model reloads. A daemon keeps it in RAM and answers in <300ms.

```bash
nano ~/.claude/hooks/mempalace-daemon.py
```

```python
#!/usr/bin/env python3
"""MemPalace daemon — Unix socket server, warm embedding model."""
import json, os, socket, sys, threading

sys.path.insert(0, f"{os.path.expanduser('~')}/.mempalace-venv/lib/python3.12/site-packages")
from mempalace.palace import get_collection

PALACE_PATH = os.path.expanduser("~/.mempalace/palace")
SOCKET_PATH = "/tmp/mempalace-daemon.sock"

COLLECTION = get_collection(PALACE_PATH, create=False)
COLLECTION.query(query_texts=["warmup"], n_results=1, include=["distances"])
print("[daemon] model warm", flush=True)

def handle(conn):
    try:
        req = json.loads(conn.recv(4096).decode().strip())
        res = COLLECTION.query(
            query_texts=[req["query"][:250]],
            n_results=min(req.get("limit", 5), 20),
            include=["documents", "metadatas", "distances"],
        )
        out = [
            {"source": m.get("source_file", ""), "snippet": d, "similarity": 1 - dist}
            for d, m, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0])
        ]
        conn.sendall((json.dumps({"results": out}) + "\n").encode())
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

Run it under systemd (Linux) or launchd (macOS).

**Linux systemd user service:**

```bash
mkdir -p ~/.config/systemd/user
nano ~/.config/systemd/user/mempalace-daemon.service
```

```ini
[Unit]
Description=MemPalace daemon

[Service]
ExecStart=/home/%u/.mempalace-venv/bin/python /home/%u/.claude/hooks/mempalace-daemon.py
Restart=on-failure

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now mempalace-daemon
systemctl --user status mempalace-daemon
```

### 6.2 UserPromptSubmit — auto semantic search

On every user message, detect strategic keywords. If matched → semantic search → inject top-5 snippets.

```bash
nano ~/.claude/hooks/user-prompt-search.py
```

```python
#!/usr/bin/env python3
"""UserPromptSubmit hook — auto semantic search injection."""
import json, re, socket, sys

DAEMON_SOCKET = "/tmp/mempalace-daemon.sock"
MAX_SNIPPET = 500

# Narrow keyword list — only fire on strategic / memory-seeking questions.
# Tune to your projects.
STRATEGIC = [
    # Project names (examples — replace with yours)
    r"\bmyapp\b", r"\bmain[_ ]?project\b",
    # Status / progress
    r"\bstatus\b", r"\bprogress\b", r"\bstuck\b", r"\bready\b",
    # Decisions / strategy
    r"\bdecision\b", r"\bplan\b", r"\broadmap\b", r"\bshould we\b",
    # Memory
    r"\bremember\b", r"\bwe (did|decided|built|shipped)\b",
    r"\bwhy (did|do) we\b",
]

data = json.loads(sys.stdin.read())
prompt = data.get("prompt", "").lower()

if not any(re.search(p, prompt) for p in STRATEGIC):
    sys.exit(0)

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

context = "## 🔍 Memory hit\n\n" + "\n\n".join(
    f"[{i+1}] {r['source']} (sim {r['similarity']:.3f}):\n{r['snippet'][:MAX_SNIPPET]}"
    for i, r in enumerate(results)
) + "\n\n_Auto-injected. Verify before citing._"

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": context,
    }
}))
```

```bash
chmod +x ~/.claude/hooks/user-prompt-search.py
```

```json
// settings.json
"UserPromptSubmit": [
  {
    "hooks": [
      {
        "type": "command",
        "command": "python3 ~/.claude/hooks/user-prompt-search.py",
        "timeout": 15
      }
    ]
  }
]
```

### 6.3 Test

Start a new session. Ask: `what was the status of MyApp?`

If the keyword matches, you'll see memory snippets appear in context before Claude generates its first token. No tool call, no waiting.

---

## Part 7 — Nightly cron: mine, compile, systematize

Heavy work that doesn't belong in a session hook: full re-mining, Karpathy-style compilation, hub rebuilding.

### 7.1 Nightly script

```bash
nano ~/.claude/hooks/nightly_memory.sh
```

```bash
#!/bin/bash
# Nightly pipeline: mine → compile → systematize.
set -e
LOCK=/tmp/nightly_memory.lock
exec 200>"$LOCK"
flock -n 200 || exit 0      # skip silently if another instance is running

LOG=/var/log/nightly_memory.log
MEMORY="$HOME/.claude/projects/<your-path>/memory"
PALACE_VENV="$HOME/.mempalace-venv"

log() { echo "[$(date '+%F %T')] $*" >> "$LOG"; }
log "=== START ==="

source "$PALACE_VENV/bin/activate"
mempalace mine "$MEMORY" --wing memory 2>&1 | tee -a "$LOG"
# Skip AAAK compression — authors report 96.6% → 84.2% accuracy regression.
# mempalace compress --wing memory
deactivate

# Karpathy compile (see 7.2)
python3 "$HOME/.claude/memory-scripts/compile_local.py" >> "$LOG" 2>&1 || log "compile failed"

# Hub rebuild + weak concept cleanup (see 7.3)
python3 "$HOME/.claude/memory-scripts/systematize_concepts.py" >> "$LOG" 2>&1 || log "systematize failed"

log "=== DONE ==="
```

Install in crontab:
```bash
chmod +x ~/.claude/hooks/nightly_memory.sh
crontab -e
```
```
0 6 * * * /bin/bash $HOME/.claude/hooks/nightly_memory.sh
```

`flock` is critical — cron + hook overlap can corrupt ChromaDB.

### 7.2 Karpathy compile with a free LLM

Compile raw session transcripts into tagged concept notes using a rotating pool of free-tier API keys.

Cerebras, Groq, and others give generous free tiers. Collect 5-10 keys, rotate per request, and you can run nightly compilation for $0.

```bash
mkdir -p ~/.claude/memory-scripts
nano ~/.claude/memory-scripts/compile_local.py
```

```python
#!/usr/bin/env python3
"""Compile session transcripts into tagged concept notes via free LLM."""
import hashlib, json, random, re
from pathlib import Path
import httpx

ENV_FILE = Path.home() / ".env-llm-keys"
API_URL = "https://api.cerebras.ai/v1/chat/completions"
MODEL = "qwen-3-235b-a22b-instruct-2507"

MEM = Path.home() / ".claude/projects/<your-path>/memory"
SESSIONS = MEM / "sessions"
CONCEPTS = MEM / "concepts"
STATE = Path.home() / ".claude/memory-scripts/compile_state.json"

CONCEPTS.mkdir(parents=True, exist_ok=True)

def load_keys() -> list[str]:
    if not ENV_FILE.exists():
        return []
    return [
        m.group(1)
        for line in ENV_FILE.read_text().splitlines()
        if (m := re.match(r"LLM_KEY_CEREBRAS_\d+=(.+)", line.strip()))
    ]

def chat(prompt: str) -> str | None:
    keys = load_keys()
    random.shuffle(keys)
    for key in keys[:8]:
        try:
            r = httpx.post(
                API_URL, timeout=30,
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": MODEL, "max_tokens": 3000,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"]
        except Exception:
            continue
    return None

PROMPT = """Compile this raw session transcript into a structured concept note.

Output format (strict):

---
name: <snake_case>
description: <one-line gist>
type: concept
tags: [<3-7 tags>]
---

Then 3-6 sections with H2 headings. Lead with decisions and why; demote code to the bottom.

Session:
---
{content}
---"""

def state_load() -> dict:
    return json.loads(STATE.read_text()) if STATE.exists() else {}

def state_save(s: dict) -> None:
    STATE.write_text(json.dumps(s))

def file_hash(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]

state = state_load()
for session in SESSIONS.glob("*.md"):
    h = file_hash(session)
    if state.get(str(session)) == h:
        continue  # already compiled this version

    content = session.read_text()[:12000]
    out = chat(PROMPT.format(content=content))
    if not out:
        continue

    m = re.search(r"name:\s*([\w_]+)", out)
    slug = m.group(1) if m else f"concept_{h[:8]}"
    (CONCEPTS / f"{slug}.md").write_text(
        out + f"\n\n---\n_compiled_by: cerebras-qwen-235b_\n_source: {session.name}_\n"
    )
    state[str(session)] = h
    print(f"compiled: {session.name} → {slug}.md")

state_save(state)
```

Put your keys in `~/.env-llm-keys`:
```
LLM_KEY_CEREBRAS_1=csk-xxxx...
LLM_KEY_CEREBRAS_2=csk-yyyy...
```

⚠️ **Do not commit this file** — see the secrets section in Part 9.

### 7.3 Systematize — hub rebuild + dedup

Concept files drift. Near-duplicates, stubs, stale entries. `systematize_concepts.py` cleans this up.

```bash
nano ~/.claude/memory-scripts/systematize_concepts.py
```

```python
#!/usr/bin/env python3
"""Hub rebuild + near-duplicate merge + weak concept cleanup."""
from pathlib import Path
import re

MEM = Path.home() / ".claude/projects/<your-path>/memory"
CONCEPTS = MEM / "concepts"
HUB = CONCEPTS / "Concepts.md"
WEAK = CONCEPTS / "_weak.md"

def parse_frontmatter(text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}
    result = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            result[k.strip()] = v.strip()
    return result

weak, entries = [], []
for p in sorted(CONCEPTS.glob("*.md")):
    if p.name.startswith("_") or p.name == "Concepts.md":
        continue
    text = p.read_text()
    meta = parse_frontmatter(text)
    if len(text) < 400 or not meta.get("name"):
        weak.append(p.name)
        continue
    entries.append((meta.get("name", p.stem), meta.get("description", ""), p.name))

HUB.write_text(
    "# Concepts Hub\n\n"
    + "\n".join(f"- [{name}]({fname}) — {desc}" for name, desc, fname in entries)
)
WEAK.write_text(
    "# Weak concepts (review or delete)\n\n"
    + "\n".join(f"- [[{w}]]" for w in weak)
)
print(f"concepts: {len(entries)} strong, {len(weak)} weak")
```

Real-world extensions: compute cosine similarity on descriptions, merge pairs with similarity >0.9, move originals to `_duplicates.md` for manual review.

---

## Part 8 — Multi-source ingestion

Your memory is only as rich as what lands in it. Beyond session transcripts, wire up the sources where you actually do thinking.

| Source | How | Lands in |
|--------|-----|----------|
| Telegram bot | Bot reads messages → parser → markdown | `memory/tg_sessions/YYYY-MM-DD.md` |
| Obsidian Web Clipper | Browser extension saves articles | `memory/raw/clips/*.md` |
| External codebase | `mempalace mine <path> --wing <name>` | Dedicated wing, filter on search |
| Daily journal | `echo >> memory/daily/$(date +%F).md` | `memory/daily/` |
| Incident log | `INCIDENTS.md` with `INC-YYYYMMDD-N` IDs | Memory root, referenced by slug |

All of these get mined by the nightly cron. Wings keep them namespaced — `--wing docs` searches only documentation, `--wing codebase` only code, `--wing memory` only your notes.

### Example: Obsidian Web Clipper setup

1. Install [Obsidian Web Clipper](https://obsidian.md/clipper) browser extension
2. Configure output directory: `~/.claude/projects/<path>/memory/raw/clips/`
3. Clip articles — they appear as markdown with frontmatter
4. Nightly mine picks them up

### Example: Telegram session parser

Run a small bot that forwards your own messages to a parser script that writes to `memory/tg_sessions/YYYY-MM-DD.md`. Nightly mine picks those up too.

---

## Part 9 — Operating it

### 9.1 Backup and sync

**Git push:**

```bash
cd ~/.claude/projects/<your-path>/memory
git init
# IMPORTANT — see secrets section below
nano .gitignore
git add .
git commit -m "initial memory"
```

Push to GitHub (private repo recommended). Now any machine can `git pull` for backup.

**Multi-machine sync:**

- **Obsidian Sync** ($10/mo) — paid, reliable
- **Unison** — free, rsync-based, bi-directional
- **Syncthing** — free, peer-to-peer
- **git pull/push on a timer** — simple, works

Pick one. Don't run two simultaneously — they'll fight over file locks.

### 9.2 Secrets in git — the precommit guard

If you version your memory directory with git, secrets **must** be ignored from day one. One missed commit = rotate every key.

```bash
nano .gitignore
```

```
.DS_Store
._*
.obsidian/
.trash/
*.bak*
__pycache__/
secrets/
.env*
*.key
```

Add a precommit hook that greps for secret patterns:

```bash
nano .git/hooks/pre-commit
```

```bash
#!/bin/bash
# Block commits containing likely secrets.
patterns='(csk-[a-z0-9]{40,}|sk-[a-zA-Z0-9]{30,}|ghp_[A-Za-z0-9]{30,}|gho_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16})'
if git diff --cached | grep -E "$patterns" > /dev/null; then
    echo "❌ commit blocked — looks like a secret was staged"
    echo "   patterns detected:"
    git diff --cached | grep -oE "$patterns" | sort -u
    exit 1
fi
```

```bash
chmod +x .git/hooks/pre-commit
```

### 9.3 Incident log

When something breaks in a way that costs real money/time, log it:

```bash
nano "$MEM/INCIDENTS.md"
```

```markdown
# Incidents

- [INC-20260329-1](concepts/incident_groq_direct_ip_ban.md) — Lost 151 Groq keys using direct IP. Lesson: always go through proxy.
- [INC-20260416-1](concepts/incident_secrets_in_git.md) — Pushed secrets/ to GitHub (private repo, but PAT also leaked). Lesson: precommit guard + .gitignore day one.
```

Reference by slug from concepts, boot context, feedback. Makes "why do we do X this way" a one-hop lookup.

### 9.4 Changelog per project

```bash
nano ~/projects/myapp/projectfasc.md
```

```markdown
# Changelog

## 2026-04-16
| Time | Action | Details |
|------|--------|---------|
| 14:30 | Auth fix | JWT expiry was 0, changed to 24h |
| 15:10 | New endpoint | /api/stats aggregated analytics |
```

Add to CLAUDE.md: *"Every code change, fix, or server action — write to projectfasc.md IMMEDIATELY."*

The SessionStart hook can tail the changelog too — add it to the hook's output.

### 9.5 BUILD_LOG.md for active development

For projects under active build, keep a detailed log with `[APPROVED]` markers:

```markdown
## Header Component [APPROVED]
- Logo: logo-v3.png
- Font: Inter 600, color: #1a1a1a
- DO NOT CHANGE — approved
```

`[APPROVED]` = never modify without explicit request. Prevents "helpful" drive-by changes to things you've already signed off on.

---

## Part 10 — Troubleshooting

### Hook runs but nothing happens

Hooks that crash usually exit silently with no UI indication. Add logging during development:

```bash
# In your hook
exec 2>> ~/.claude/hooks/debug.log
set -x
```

Check `~/.claude/hooks/debug.log`. Remove once the hook is stable.

### Hook output doesn't appear in Claude's context

The hook must output JSON with the exact shape:
```json
{ "hookSpecificOutput": { "hookEventName": "...", "additionalContext": "..." } }
```

No stdout besides that JSON. Any stray `print()` corrupts the response.

### Daemon won't start

```bash
systemctl --user status mempalace-daemon
journalctl --user -u mempalace-daemon -n 50
```

Common: Python path wrong in the `.service` file, venv not activated, socket already in use (stale `/tmp/mempalace-daemon.sock` — delete it).

### MemPalace: ChromaDB lock contention

Symptom: `mempalace mine` hangs or errors with "collection locked".

Cause: nightly cron overlapped with a Stop-hook mine. `flock -n` on the nightly script prevents it. Also: don't run two MCP servers against the same collection.

### UserPromptSubmit fires too often

Tighten `STRATEGIC_PATTERNS`. Test:
```python
# In a REPL
import re
patterns = [r"\bstatus\b", ...]
test = "what's the status"
any(re.search(p, test.lower()) for p in patterns)
```

### Cerebras / Groq keys rate-limit

Rotate more keys. The compile script picks 8 random keys per request — if all 8 rate-limit, the request fails and retries on the next nightly run. For a 100-session backlog, you may want a longer time budget or more keys.

---

## End-to-end verification

A checklist to confirm the whole pipeline works:

- [ ] `CLAUDE.md` in your working directory
- [ ] `MEMORY.md` index in `~/.claude/projects/<path>/memory/`
- [ ] At least one `user_*`, `feedback_*`, `project_*` memory file
- [ ] `BOOT_CONTEXT.md` with high-signal facts
- [ ] `mempalace --version` works; `mempalace search <test>` returns results
- [ ] SessionStart hook injects context (ask Claude: *"what was in BOOT_CONTEXT?"*)
- [ ] Stop hook fires — check `~/backups/memory_raw_sessions/` fills with JSONL copies
- [ ] SessionEnd produces files in `memory/sessions/`
- [ ] MemPalace daemon active: `systemctl --user status mempalace-daemon`
- [ ] UserPromptSubmit fires on keyword questions (check `~/.claude/hooks/debug.log`)
- [ ] Nightly cron registered: `crontab -l | grep nightly_memory`
- [ ] Git repo for memory has `.gitignore` covering `secrets/`, `.env*`
- [ ] Precommit hook blocks test secret:
  ```bash
  echo "csk-fakekeyfortesting012345678901234567890" >> test.md
  git add test.md && git commit -m "test"   # should FAIL
  ```

If all checked — you have the full system.

---

## Where to go next

- **[memory-setup.md](memory-setup.md)** — deeper tour of the memory file format, frontmatter, and types
- **[advanced-automation.md](advanced-automation.md)** — reference doc for all automation components
- **[examples/](examples/)** — real templates for CLAUDE.md, MEMORY.md, and memory files

---

## Useful commands inside Claude Code

| Command | What it does |
|---------|-------------|
| `/help` | Help menu |
| `/permissions` | Manage tool permissions |
| `/clear` | Clear session context |
| `/compact` | Compress context |
| `/model` | Switch model |
| `Ctrl+C` | Exit |

---

## Links

- Claude Code docs: https://docs.anthropic.com/en/docs/claude-code
- Claude subscription: https://claude.ai
- MemPalace: https://github.com/milla-jovovich/mempalace
- Claude Code repo: https://github.com/anthropics/claude-code
