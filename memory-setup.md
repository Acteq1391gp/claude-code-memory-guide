# Claude Code Memory System — Setup Guide

A battle-tested memory architecture for Claude Code. Four layers that work together so Claude remembers who you are, what you're building, and what mistakes not to repeat.

---

## Table of Contents

1. [Architecture](#architecture)
2. [Layer 1 — CLAUDE.md (Rules)](#layer-1--claudemd-rules)
3. [Layer 2 — Memory Files (Long-term Memory)](#layer-2--memory-files-long-term-memory)
4. [Layer 3 — MemPalace (Vector Memory)](#layer-3--mempalace-vector-memory)
5. [Layer 4 — Session Hooks (Auto-loading)](#layer-4--session-hooks-auto-loading)
6. [Advanced: Wiki Compilation (Karpathy Method)](#advanced-wiki-compilation-karpathy-method)
7. [Advanced: Channel Bridge](#advanced-channel-bridge)
8. [Advanced: Changelog](#advanced-changelog)
9. [Putting It All Together](#putting-it-all-together)
10. [FAQ](#faq)

---

## Architecture

```
Session starts
    │
    ▼
[Hook] load_context.sh fires automatically (optional)
    │
    ├──► MemPalace wake-up → identity + critical facts (~1300 tokens)
    ├──► Wiki compilations → compressed knowledge (~5-7K tokens)
    └──► Changelog tail → latest changes
    │
    ▼
Claude reads CLAUDE.md ──► rules, identity, projects (automatic)
    │
    ▼
Claude reads MEMORY.md ──► index of all memories (automatic)
    │
    ▼
Work happens — Claude updates memory + changelog as it goes
    │
    ▼
Next session — full context preserved
```

**File structure:**
```
Working directory (e.g. ~/projects/)
├── CLAUDE.md                          # [Layer 1] Rules — auto-loaded
└── my-project/
    └── projectfasc.md                 # Changelog (optional)

~/.claude/
├── settings.json                      # Permissions + hooks
├── load_context.sh                    # [Layer 4] Session hook (optional)
└── projects/
    └── <encoded-path>/
        └── memory/
            ├── MEMORY.md              # [Layer 2] Memory index
            ├── user_profile.md        # Memory files
            ├── feedback_*.md
            ├── project_*.md
            └── wiki_*.md              # Compiled knowledge (advanced)

~/.mempalace/                          # [Layer 3] Vector memory (optional)
├── config.json
├── identity.txt
└── palace/                            # ChromaDB vector store
```

---

## Layer 1 — CLAUDE.md (Rules)

The foundation. Claude **automatically** reads `CLAUDE.md` from the working directory at every session start.

**Create it:**
```bash
nano ~/projects/CLAUDE.md
```

### Template

```markdown
# My AI Assistant

## Identity
- Name: [pick a name or leave as Claude]
- Role: personal assistant and developer
- Style: direct, no fluff, get things done

## About Me
- [Your name, what you do]
- Stack: [your languages and frameworks]
- [How you like to communicate]

## Rules — Always Active

### Task Execution
- Got a task — do it immediately. Don't ask "should I?" or "are you sure?".
- If something breaks — fix first, explain after.
- Don't touch code that wasn't asked about. No drive-by refactors.
- Don't add docstrings, comments, or type hints to unchanged code.

### Quality
- Unverified result = no result. Test before presenting.
- One task at 100% beats ten at 60%.

### Memory
- Every important decision → save to memory/ immediately.
- Every code change → write to changelog immediately.
- Not at end of session. As you go.

### Before Modifying Existing Code
1. Read the file completely
2. Understand what it does and what depends on it
3. Explain what you'll change and why
4. Then do it

## Projects
| Project | Path | Purpose |
|---------|------|---------|
| my-app | ~/projects/my-app/ | Main project |

## Environment
- OS: [Ubuntu / macOS / etc.]
- [Any relevant infrastructure details]
```

### What goes in CLAUDE.md
- Identity and style
- Hard rules (always/never do X)
- Project paths, infrastructure
- Work protocols

### What does NOT go in CLAUDE.md
- Temporary tasks (use memory)
- Secrets (if sharing the file)
- Daily-changing info (use memory files)

---

## Layer 2 — Memory Files (Long-term Memory)

File-based memory that persists across sessions. Each memory is a markdown file with metadata.

### Where it lives

The path depends on where you launch Claude:
- From `/root/` → `~/.claude/projects/-root/memory/`
- From `~/projects/myapp/` → `~/.claude/projects/-home-user-projects-myapp/memory/`

**Easiest way to find it:** tell Claude "Remember: test" and it'll show you the path.

### Create the index

```bash
nano ~/.claude/projects/<your-path>/memory/MEMORY.md
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

**Index rules:**
- One line per file, under 150 characters
- Max 200 lines (truncated after)
- Just a table of contents — content in separate files
- Organize by topic, not by date

### Memory file format

```markdown
---
name: memory_name
description: one-line summary (Claude uses this to decide relevance)
type: user | feedback | project | reference
---

Content here.
```

### Types with examples

#### `user` — who you are

```markdown
---
name: user_profile
description: Backend developer, Python + Go, prefers terse communication
type: user
---

Alex. Backend developer, main stack Python + Go.
5 years experience. Works solo.
Prefers short answers. No corporate speak.
Knows databases well — don't over-explain SQL.
New to frontend — explain React concepts in detail.
```

#### `feedback` — what to do / not do

The most valuable type. Prevents Claude from repeating mistakes.

```markdown
---
name: feedback_code_style
description: Don't add docstrings or refactor code that wasn't asked about
type: feedback
---

Don't add docstrings, comments, or type hints to code that wasn't asked to be changed.

**Why:** Creates noise in diffs. User controls when to document.

**How to apply:** Change only what was requested. Don't "improve" neighboring code.
```

```markdown
---
name: feedback_verification
description: Always verify results before presenting them
type: feedback
---

Never present unverified results. If a tool found 36 bugs — manually check the top 5 first.

**Why:** Lost trust by presenting auto-generated findings that were false positives.

**How to apply:** Run the thing. Check output. Confirm it's real. Then show it.
```

#### `project` — what you're building

```markdown
---
name: project_main_app
description: E-commerce API, launching June, Django + PostgreSQL
type: project
---

E-commerce platform. Django backend + PostgreSQL.
Launch: 2026-06-01. Feature freeze: 2026-05-15.

**Why:** First paying client, deadline is hard.

**How to apply:** Speed over perfection. Ship features, clean up later.
```

#### `reference` — external resources

```markdown
---
name: reference_tools
description: Bug tracker in Linear, CI in GitHub Actions, docs in Notion
type: reference
---

Bug tracker: Linear, project "BACKEND".
CI/CD: GitHub Actions.
Docs: Notion workspace "Product".
Staging: staging.myapp.com
```

### How Claude uses memory
- `MEMORY.md` loads **automatically** every session
- Claude reads relevant files based on the index
- Say "remember: [fact]" → Claude saves it
- Say "forget: [fact]" → Claude removes it
- Claude manages files and index on its own

---

## Layer 3 — MemPalace (Vector Memory)

[MemPalace](https://github.com/milla-jovovich/mempalace) is an open-source long-term memory system created by Milla Jovovich. It adds **semantic vector search** on top of file-based memory — Claude can find relevant context by meaning, not just keywords.

| Feature | Value |
|---------|-------|
| Accuracy | 96.6% on benchmarks (vs ~85% for Mem0) |
| Storage | SQLite + ChromaDB (100% local) |
| Cost | Free (MIT license) |
| Works with | Claude, GPT, Gemini, any LLM |
| Key feature | Semantic search + identity wake-up |

### Why add this

File-based memory (Layer 2) is solid, but has limits:
- Search is keyword-based — misses semantic matches
- You need to know which file to look in
- Doesn't scale well past 100+ files

MemPalace adds:
- **Vector search** — find context by meaning ("how does auth work?" finds JWT-related memories even without the word "JWT")
- **Identity wake-up** — loads your profile + critical facts at session start in ~1300 tokens
- **Knowledge mining** — index codebases, documentation, anything text-based

### Installation

```bash
# Create isolated venv (keeps your system clean)
python3 -m venv ~/.mempalace-venv
source ~/.mempalace-venv/bin/activate

# Install
pip install mempalace

# Verify
mempalace --version

# Deactivate (mempalace binary stays at ~/.mempalace-venv/bin/mempalace)
deactivate
```

### Setup

```bash
# Initialize
~/.mempalace-venv/bin/mempalace init

# Create your identity
nano ~/.mempalace/identity.txt
```

**identity.txt example:**
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

### Index your files

```bash
MEMPALACE=~/.mempalace-venv/bin/mempalace

# Index your memory files
$MEMPALACE mine ~/.claude/projects/<your-path>/memory/ --wing memory

# Index a codebase (optional — useful for large projects)
$MEMPALACE mine ~/projects/my-app/ --wing my-app

# Index documentation (optional)
$MEMPALACE mine ~/docs/ --wing docs
```

### Use it

```bash
# Wake-up — identity + critical facts (used in session hooks)
$MEMPALACE wake-up

# Search by meaning
$MEMPALACE search "authentication flow"
$MEMPALACE search "database connection issues"
```

### Tips
- **Use raw mode, not AAAK.** AAAK compression exists but has accuracy regression (84.2% vs 96.6% raw). Stick with default.
- **Local embeddings** are weaker for exact matches (version numbers, dates, IDs). Use grep for exact text, MemPalace for semantic search.
- **Best used with file-based memory**, not as a replacement. Layer 2 gives you manual control, Layer 3 gives you intelligent search.
- **Re-mine periodically** after significant memory changes: `$MEMPALACE mine <path> --wing <name>`

---

## Layer 4 — Session Hooks (Auto-loading)

A shell script that runs automatically at session start, injecting extra context before you type anything.

### Set up the hook

```bash
nano ~/.claude/settings.json
```

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/load_context.sh",
            "timeout": 15,
            "statusMessage": "Loading context..."
          }
        ]
      }
    ]
  }
}
```

### Create the loader

```bash
nano ~/.claude/load_context.sh
chmod +x ~/.claude/load_context.sh
```

```bash
#!/bin/bash
# Hybrid context loader
# Layer 1: MemPalace wake-up (identity + critical facts)
# Layer 2: Wiki compilations (compressed knowledge)
# Layer 3: Changelog tail (recent changes)

MEMORY_DIR="$HOME/.claude/projects/-root/memory"  # adjust to your path
MEMPALACE_BIN="$HOME/.mempalace-venv/bin/mempalace"
OUTPUT=""

# === MemPalace wake-up (skip if not installed) ===
if [ -x "$MEMPALACE_BIN" ]; then
  WAKE=$("$MEMPALACE_BIN" wake-up 2>/dev/null)
  if [ -n "$WAKE" ]; then
    OUTPUT+="=== Identity + Critical Facts ===\n${WAKE}\n\n---\n\n"
  fi
fi

# === Wiki compilations (compiled knowledge files) ===
for f in "$MEMORY_DIR"/wiki_*.md; do
  [ -f "$f" ] || continue
  OUTPUT+="$(cat "$f")\n\n---\n\n"
done

# === Changelog tail (recent changes) ===
CHANGELOG="$HOME/projects/my-project/projectfasc.md"  # adjust path
if [ -f "$CHANGELOG" ]; then
  OUTPUT+="=== Recent changes ===\n$(tail -100 "$CHANGELOG")\n\n---\n\n"
fi

# Output as hook response (required JSON format)
python3 -c "
import json, sys
content = sys.stdin.read()
print(json.dumps({
  'hookSpecificOutput': {
    'hookEventName': 'SessionStart',
    'additionalContext': content
  }
}))
" <<< "$OUTPUT"
```

**What this does:** Every session start, Claude automatically receives:
1. Your MemPalace identity and critical facts (if installed)
2. Compiled wiki knowledge
3. Recent changelog entries

All injected before you type a single word. The script gracefully skips MemPalace if it's not installed.

---

## Advanced: Wiki Compilation (Karpathy Method)

When you accumulate 30+ memory files, they become noise. Solution: compile them into topic-based wiki files.

**The idea** (inspired by Andrej Karpathy's approach): instead of 100 small files, create 5-6 comprehensive files organized by topic. Each wiki is a deduplicated summary of everything known about that area.

### Before (50+ files):
```
memory/
├── project_auth_bug.md
├── project_auth_fix.md
├── project_deploy_jan.md
├── project_deploy_feb.md
├── feedback_no_docstrings.md
├── feedback_no_refactor.md
├── feedback_verify_first.md
... (43 more)
```

### After (6 files, originals archived):
```
memory/
├── wiki_backend.md           # Architecture, API, database
├── wiki_frontend.md          # UI, components, state
├── wiki_infrastructure.md    # Deploy, CI/CD, servers
├── feedback_compiled.md      # All behavioral rules in one place
├── user_profile.md           # Identity (keep separate)
└── MEMORY.md                 # Index (now 8 lines instead of 50)
```

### Wiki file example

```markdown
---
name: wiki_backend
description: Backend — architecture, API, auth, database, known issues
type: project
---

## Architecture
Django + PostgreSQL + Redis. Deployed on Railway.

## API Endpoints
- /api/auth — JWT, tokens expire in 24h
- /api/products — requires auth, cursor pagination
- /api/orders — requires auth, webhook on status change

## Known Issues
- Connection pool exhaustion over 500 concurrent users
  - Fix: increased pool_size to 20
- Slow query on /api/products with >10K items
  - Fix: added composite index on (category_id, created_at)

## Key Decisions
- Django over FastAPI (Jan 2026): team knows Django, speed to market
- PostgreSQL over MySQL (Jan 2026): needed JSONB for product metadata
```

### How to compile

1. Read all files in a category
2. Extract unique facts, decisions, rules
3. Remove duplicates and outdated info
4. Organize into sections
5. Archive originals to a backup folder

### Benefits
- Index stays small
- Less files to load at session start
- No duplicate info across files
- Easier to maintain

---

## Advanced: Channel Bridge

If you use Claude from multiple places (VS Code + Terminal, or two machines), a bridge file syncs context.

```bash
nano ~/projects/channel_bridge.md
```

```markdown
# Channel Bridge

### 14:30 [Terminal] — fixed auth bug
- Patched JWT expiry in auth.py
- Tests passing
- TODO: deploy to staging

### 13:00 [VS Code] — new endpoint
- Added /api/stats
- [DONE]
```

Add to CLAUDE.md:
```
At session start — read channel_bridge.md for context from the other channel.
After important actions — update it with what you did.
```

Keep max 15 entries, newest on top.

---

## Advanced: Changelog

A running log of every change. Claude writes here as it works.

```bash
nano ~/projects/my-project/projectfasc.md
```

```markdown
# Changelog

## 2026-04-13

| Time | Action | Details |
|------|--------|---------|
| 14:30 | Auth fix | JWT expiry was 0, changed to 24h |
| 15:10 | New endpoint | /api/stats — aggregated analytics |
| 16:00 | Deploy | Pushed to staging, smoke tests passed |
```

Add to CLAUDE.md:
```
Every code change, fix, or server action — write to projectfasc.md IMMEDIATELY.
```

### BUILD_LOG.md (for active development)

When building something big, keep a detailed log in the project folder:

```markdown
# Build Log

## Header Component [APPROVED]
- Logo: logo-v3.png
- Font: Inter 600, color: #1a1a1a
- DO NOT CHANGE — approved

## Auth Flow
- Login form → POST /api/auth/login
- JWT stored in httpOnly cookie
- Redirect to /dashboard
```

`[APPROVED]` = never modify without explicit request. Prevents Claude from "improving" things you already signed off on.

---

## Putting It All Together

### Minimal (5 minutes)
1. Create `CLAUDE.md` with your rules
2. Ask Claude "Remember: [who you are]"
3. Done — Layer 1 + 2

### Standard (20 minutes)
1. `CLAUDE.md` with rules
2. `MEMORY.md` index + a few memory files
3. `projectfasc.md` changelog
4. Rules in CLAUDE.md about updating memory and changelog

### Full (1-2 hours)
1. Everything from standard
2. Install MemPalace, create identity, mine your files
3. `load_context.sh` session hook (with MemPalace wake-up)
4. Hook config in `settings.json`
5. Wiki files compiled from accumulated memories
6. Channel bridge (if multi-device)

### Priority order

```
CLAUDE.md ................ must have
  └── memory/ files ...... should have
      └── changelog ...... nice to have
          └── MemPalace .. semantic search
              └── hooks .. auto-loading
                  └── wiki when files > 30
```

---

## FAQ

**Q: Claude doesn't see my CLAUDE.md?**
A: Make sure it's in the directory you launch `claude` from, or in the git repo root.

**Q: Where is the memory directory?**
A: `~/.claude/projects/<encoded-path>/memory/`. Ask Claude "remember: test" — it'll show the path.

**Q: How many memory files?**
A: Unlimited, but the MEMORY.md index truncates after 200 lines. Compile wiki files when you hit 30+.

**Q: Claude keeps forgetting my rules?**
A: Check that CLAUDE.md is in the right directory. Check that memory files have proper frontmatter (`---` block).

**Q: Can I share CLAUDE.md with my team?**
A: Yes — commit it to your repo. Everyone gets the same rules. Memory (`~/.claude/`) stays per-user.

**Q: How much context does this use?**
A: CLAUDE.md + MEMORY.md index load automatically (usually under 3K tokens). Individual memory files load on demand. Wiki compilations via hook add ~5-7K. Total is well within Claude's context window.

**Q: What's the Karpathy method?**
A: Inspired by Andrej Karpathy's approach to knowledge management. Instead of many small files, compile knowledge into comprehensive topic-based documents. Less duplication, smaller index, faster loading.
