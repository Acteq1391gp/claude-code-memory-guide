# Full Setup — Claude Code + Memory System

Complete guide: subscription, installation, and memory configuration.

---

## Prerequisites

- Linux, macOS, or Windows (WSL)
- Node.js 18+

---

## Step 1 — Subscription

1. Go to **https://claude.ai**
2. Sign up or log in
3. Subscribe to a plan:
   - **Claude Pro** ($20/mo) — solid for regular use
   - **Claude Max** ($100 or $200/mo) — higher limits for heavy work
4. This gives access to Claude Code without separate API billing

---

## Step 2 — Install Node.js (if needed)

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
Download LTS from https://nodejs.org, or use WSL and follow Ubuntu instructions.

**Verify:**
```bash
node --version   # should be 18+
```

---

## Step 3 — Install Claude Code

```bash
npm install -g @anthropic-ai/claude-code
```

Or without global install:
```bash
npx @anthropic-ai/claude-code
```

---

## Step 4 — First Launch

```bash
cd ~/projects   # your working directory
claude
```

First launch:
1. Select **"Claude.ai account"**
2. Browser opens — log in
3. Confirm auth
4. You're in

---

## Step 5 — VS Code Extension (optional)

1. Open VS Code
2. Extensions → search **"Claude Code"**
3. Install (by Anthropic)
4. `Ctrl+Shift+P` → **"Claude Code: Open"**

---

## Step 6 — Set Up Memory

Follow the [Memory Setup Guide](memory-setup.md).

**Quick version:**
1. Create `CLAUDE.md` in your working directory
2. Tell Claude: "Remember: my name is [name], I work on [what]"
3. Claude creates memory files automatically

---

## Step 7 — Permissions (optional)

```bash
nano ~/.claude/settings.json
```

```json
{
  "permissions": {
    "allow": [
      "Read",
      "Edit",
      "Write",
      "Glob",
      "Grep",
      "Bash(git *)",
      "Bash(npm *)",
      "Bash(node *)",
      "Bash(ls *)",
      "Bash(python3 *)"
    ]
  }
}
```

Or interactively: `/permissions` inside a session.

---

## Step 8 — Verify

```bash
cd ~/projects
claude
```

Ask: `Who are you? What do you know about me?`

If it works — Claude reads your rules and memory.

---

## Checklist

- [ ] Subscription at claude.ai
- [ ] Node.js 18+
- [ ] `npm install -g @anthropic-ai/claude-code`
- [ ] First launch + auth
- [ ] `CLAUDE.md` created ([guide](memory-setup.md))
- [ ] Memory configured ([guide](memory-setup.md))
- [ ] Verified — Claude knows who you are

---

## Useful Commands

| Command | What it does |
|---------|-------------|
| `/help` | Help |
| `/permissions` | Manage permissions |
| `/clear` | Clear session context |
| `/compact` | Compress context |
| `Ctrl+C` | Exit |

---

## Links

- Docs: https://docs.anthropic.com/en/docs/claude-code
- Subscription: https://claude.ai
- Node.js: https://nodejs.org
- GitHub: https://github.com/anthropics/claude-code

---

Next → [Memory Setup Guide](memory-setup.md)
