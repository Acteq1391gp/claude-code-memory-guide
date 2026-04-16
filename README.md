# Claude Code Memory System — The Complete Guide

A battle-tested guide to building persistent memory for [Claude Code](https://github.com/anthropics/claude-code). This isn't theory — it's a production system running 220+ memory files across 18 categories, refined over months of daily use.

**The problem:** Every new Claude Code session starts from scratch. Claude doesn't remember who you are, what you told it yesterday, or that it broke your config twice doing the same thing.

**The solution:** A file-based memory architecture that gives Claude persistent context — identity, projects, behavioral rules, compiled knowledge, and a full changelog of everything that happened.

---

## What This Guide Covers

| Guide | Who it's for |
|-------|-------------|
| [Full Setup](full-setup.md) | Starting from zero — subscription, installation, memory setup |
| [Memory Setup](memory-setup.md) | Already have Claude Code — just need the memory system |
| [Examples](examples/) | Real CLAUDE.md, MEMORY.md, and memory file templates |

---

## How It Works

```
Session starts
    │
    ▼
Claude reads CLAUDE.md ──────► Identity, rules, style, what NOT to do
    │
    ▼
Claude reads MEMORY.md ──────► Index of all memories (loaded automatically)
    │
    ▼
Claude loads relevant memories ► wiki, feedback, project context
    │
    ▼
Work happens
    │
    ▼
Claude updates memory/ as it goes ► new learnings, corrections, decisions
    │
    ▼
Next session — full context preserved
```

---

## Architecture — The 4-Layer Stack

### Layer 1: CLAUDE.md (The Brain)

The core config file. Claude reads this first, every session. Contains:
- Who you are and who Claude is
- Hard rules (what to never do)
- Where to find things
- Code conventions, style, formatting

```markdown
# My Assistant

## Rules
1. Read files BEFORE modifying them
2. One task at 100% is better than ten at 60%
3. Never show unverified results as success

## Where to find things
- Project details → memory/wiki_*.md
- All rules/feedback → memory/feedback_compiled_*.md
- Last actions → changelog.md

## Style
- No corporate speak
- Tables in VS Code, lists in Telegram
- Check your work before saying "done"
```

### Layer 2: MEMORY.md (The Index)

A single file that indexes all memories. Claude reads this to know what's available. Think of it as a table of contents.

```markdown
# Memory Index

## Hubs — start here
- [[project_HUB]] — all projects by domain
- [[hackathons_HUB]] — active hackathons, deadlines, status

## Wiki — Compiled Knowledge
- [[wiki_infra]] — services, ports, deployments
- [[wiki_hackathons]] — what's submitted, competitors
- [[wiki_keys]] — API keys, providers, farming status

## Feedback — Compiled Rules
- [[feedback_compiled_security]] — proxy rules, key handling
- [[feedback_compiled_workflow]] — execution, persistence
- [[feedback_compiled_quality]] — verification, delegation

## User
- [[user_profile]] — role, preferences, knowledge level
```

### Layer 3: memory/ Directory (The Files)

Individual memory files organized by type:

```
memory/
├── wiki/                    # Compiled knowledge bases
│   ├── wiki_infra.md        # Services, ports, deployments
│   ├── wiki_hackathons.md   # Hackathon status & competitors
│   └── wiki_keys.md         # API providers & key inventory
├── feedback/                # Behavioral rules from corrections
│   ├── feedback_compiled_security.md
│   ├── feedback_compiled_workflow.md
│   └── feedback_compiled_quality.md
├── hubs/                    # Entry points by domain
│   ├── project_HUB.md
│   └── hackathons_HUB.md
├── user/                    # User profile & preferences
│   └── user_profile.md
├── concepts/                # Learned patterns & insights
│   ├── api_key_cemetery.md
│   └── commit_reveal_flow.md
├── connections/             # Links between concepts
├── content/                 # Voice guides, templates
├── reference/               # External system pointers
└── projects/                # Per-project context
```

### Layer 4: Changelog (The Journal)

A running log of everything Claude does. Updated during work, not after.

```markdown
## 2026-04-16: ArcNFTs Launch

| Time | Action | Details |
|------|--------|---------|
| 15:00 | Created repo | Windwalkermonk/arcnfts |
| 15:30 | Contracts | NFTFactory + NFTCollection (ERC-721 + ERC-2981) |
| 16:00 | Frontend | React + Vite, 5 pages |
| 17:00 | Deploy | Vercel live, Arc Testnet |
| 18:00 | Fix | Chain ID hex was wrong, USDC decimals 18 not 6 |
```

---

## Memory File Format

Every memory file uses YAML frontmatter:

```markdown
---
name: feedback_compiled_security
description: Proxy rules, key handling, validation — compiled from corrections
type: feedback
---
# Security Rules

## Proxy
- Groq ONLY through proxy (localhost:11435). Direct = key ban.
- Why: Lost 3 keys before adding proxy rule.

## Key Management
- Read file BEFORE modifying. Reason: lost 151 keys once without reading context.
- Secrets files: keys only, metadata goes in logs.
```

### Memory Types

| Type | Purpose | When to save |
|------|---------|-------------|
| `user` | Who the user is, preferences, knowledge level | Learn something about the user |
| `feedback` | Corrections and confirmed approaches | User says "don't do X" or "yes, exactly like that" |
| `project` | Ongoing work, decisions, deadlines | Learn who/what/why/when about active work |
| `reference` | Pointers to external systems | Discover where info lives outside the codebase |

---

## The Wiki Compilation Method

When you accumulate 50+ small memories on a topic, they become noise. The fix: compile them into topic-based wikis.

**Before:** 47 scattered files about hackathons
**After:** 1 wiki file with everything organized

```markdown
# Hackathons — Compiled Wiki

## Active Projects

| Project | Hackathon | Status | GitHub |
|---------|-----------|--------|--------|
| Division FHE | Fhenix Waves | Submitted | repo/division-fhe |
| Division ARC | HashKey | Submitted | repo/division-arc |

## Competitors
- Fhenix: 186 projects analyzed
- 0G: 87 competitors

## Frontends
- /fhe/ → hackathon-fhenix/frontend/
- /arc/ → hackathon-arc/frontend/
```

### When to compile:
- Topic has 10+ scattered memories
- You keep searching for the same info across multiple files
- A hub page has more than 20 links

---

## The Feedback Loop

This is the most powerful part. When Claude makes a mistake, save the correction as a feedback memory. Claude reads it every session and doesn't repeat the error.

**User:** "don't mock the database in these tests"

**Claude saves:**
```markdown
---
name: feedback_no_db_mocks
description: Integration tests must use real database, not mocks
type: feedback
---
# No Database Mocks in Integration Tests

Integration tests hit a real database, never mocks.

**Why:** Previous quarter, mocked tests passed but production migration failed.
DB mock diverged from real schema and masked the bug.

**How to apply:** Any file in tests/integration/ — use real DB connection.
```

Next session — Claude automatically avoids mocking the database without being told again.

### Real examples of feedback that changed behavior:

| Correction | Saved as | Effect |
|-----------|----------|--------|
| "Read the file before changing it" | `feedback_file_reading.md` | Stopped blind edits, saved hours |
| "Grep first, don't cat entire files" | `feedback_search_discipline.md` | Faster searches, less context waste |
| "Don't show unverified results" | `feedback_compiled_quality.md` | Actually checks output before reporting |
| "One task at 100% > ten at 60%" | `feedback_compiled_quality.md` | Stopped scattered parallel work |

---

## Hub Pattern

When you have many projects/topics, create hub files as entry points:

```markdown
# Projects Hub

## Blockchain
- [[project_sunima]] — flagship L1 chain
- [[project_division_fhe]] — FHE hackathon

## Infrastructure
- [[project_banda]] — agent system (40 agents)
- [[project_mempalace]] — vector memory search

## Trading
- [[project_gate_pulse]] — momentum trader
```

Hubs link to detailed project files. Claude reads the hub first, then drills into what's relevant.

---

## Scaling Guide

| Stage | Files | What to do |
|-------|-------|-----------|
| **Week 1** | 5-10 | CLAUDE.md + a few feedback memories |
| **Month 1** | 30-50 | Add wiki compilations, hub pages |
| **Month 3** | 100-200 | Full architecture: hubs → wikis → concepts → connections |
| **Month 6+** | 200+ | Archive old sessions, weekly orphan review |

### When you hit 200+ files:
- Archive old session logs to `/backups/`
- Review orphan memories weekly (files nothing links to)
- Keep MEMORY.md index under 200 lines (it gets truncated)
- Compile aggressively — 3 files on same topic → 1 wiki

---

## Tips

- **Start small.** CLAUDE.md + 3 feedback files is enough for day one.
- **Save corrections immediately.** Don't wait — the feedback file is worth more than the fix.
- **Save successes too.** If Claude does something right and non-obvious, save it. Otherwise it'll drift away from what worked.
- **Use absolute dates.** "Thursday" means nothing in 2 weeks. Write "2026-04-16".
- **MEMORY.md is an index, not storage.** One line per entry. Content goes in individual files.
- **Don't save what code can tell you.** File paths, git history, architecture — Claude can read those. Save what it can't derive: decisions, context, corrections.

---

## Quick Start (5 minutes)

1. Create `CLAUDE.md` in your project root with your rules
2. Tell Claude: "Remember that I prefer X" or "Save this feedback: never do Y"
3. Claude creates memory files automatically in `memory/`
4. Next session — Claude reads CLAUDE.md + MEMORY.md and knows everything

That's it. The system grows organically from there.

---

## Optional: MemPalace (Vector Search)

For 100+ memories, keyword search isn't enough. [MemPalace](https://github.com/milla-jovovich/mempalace) adds semantic search — find memories by meaning, not just filename.

| Feature | Without MemPalace | With MemPalace |
|---------|-------------------|----------------|
| Find memory | Grep / filename | "What did we decide about auth?" |
| Connections | Manual links | Auto-discovered |
| Duplicates | Manual review | Detected automatically |

---

## License

MIT
