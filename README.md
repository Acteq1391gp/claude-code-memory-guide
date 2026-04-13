# Claude Code Memory System — Setup Guide

A practical guide to setting up persistent memory for [Claude Code](https://github.com/anthropics/claude-code), Anthropic's AI coding assistant.

**The problem:** Every new Claude Code session starts from scratch. Claude doesn't know who you are, what your project does, or what you asked it not to do yesterday.

**The solution:** A file-based memory system that gives Claude persistent context across sessions — your identity, project details, behavioral rules, and a changelog of everything that's been done.

---

## Guides

| Guide | Who it's for |
|-------|-------------|
| [Full Setup](full-setup.md) | Starting from zero — subscription, installation, memory setup |
| [Memory Setup](memory-setup.md) | Already have Claude Code — just need the memory system |

---

## How it works

```
Session starts
    │
    ▼
[Hook] auto-loads MemPalace identity + wiki + changelog (optional)
    │
    ▼
Claude reads CLAUDE.md ────► knows your rules, style, projects
    │
    ▼
Claude reads MEMORY.md ────► loads relevant memories
    │
    ▼
Work happens
    │
    ▼
Updates memory/ + changelog as it goes
    │
    ▼
Next session — full context preserved
```

## The stack

| Layer | What | Required? |
|-------|------|-----------|
| **CLAUDE.md** | Rules, identity, projects | Yes |
| **memory/ files** | Long-term memory (user, feedback, project, reference) | Yes |
| **[MemPalace](https://github.com/milla-jovovich/mempalace)** | Vector search — find memories by meaning | Optional |
| **Session hooks** | Auto-load context at session start | Optional |
| **Wiki compilation** | Compress 50+ files into 5-6 topic wikis (Karpathy method) | When needed |

## Quick start (5 minutes)

1. Create `CLAUDE.md` in your working directory with your rules
2. Ask Claude to "remember: my name is X, I work on Y"
3. Claude creates the memory files automatically
4. Next session — Claude knows who you are

See the guides for detailed setup with examples.

## License

MIT
