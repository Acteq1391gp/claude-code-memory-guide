# Scripts

These scripts automate the memory pipeline: session ends → LLM compiles transcript → memory files written → Claude reads them next session.

## Flow

```
Claude Code session (JSONL transcript)
    │
    ▼
compile.py ──► LLM (Cerebras / Groq / SambaNova / OpenAI / Anthropic)
    │                        ↑
    │              picks first available key
    ▼
memory/sessions/YYYY-MM-DD.md   ← session summary appended
memory/concepts/<name>.md       ← new concept files created
    │
    ▼
Next Claude session reads MEMORY.md → loads relevant files → full context
```

## Files

| Script | Purpose |
|--------|---------|
| `compile.py` | Compile session transcript → memory entries via LLM |
| `memory_logger.py` | Parse session → log all memory read/write ops |
| `config.yaml` | API keys + provider config (gitignored) |

## Setup

```bash
# 1. Install deps
pip install anthropic openai groq cerebras-cloud-sdk pyyaml

# 2. Set your key (cheapest option first)
export CEREBRAS_API_KEY="your-key"   # free tier available
# or
export GROQ_API_KEY="your-key"       # free tier available
# or any other supported provider

# 3. Run after a session
python scripts/compile.py
```

## Provider Priority

compile.py tries providers in this order (first available wins):

```
Cerebras → Groq → SambaNova → OpenAI → Anthropic
```

Override with env var or config.yaml:
```bash
export COMPILE_PROVIDER=groq
python scripts/compile.py
```

Or put in `scripts/config.yaml`:
```yaml
provider: cerebras
cerebras:
  api_key: "your-key"
  model: "llama-3.3-70b"
```

## Auto-run via Claude Code Hooks

Wire compile.py to run automatically when a session ends (Stop hook) or before context compression (PreCompact hook).

In your Claude Code settings (`~/.claude/settings.json`):

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "cd /path/to/your/project && python scripts/compile.py --no-memories 2>/dev/null || true"
          }
        ]
      }
    ],
    "PreCompact": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "cd /path/to/your/project && python scripts/compile.py 2>/dev/null || true"
          }
        ]
      }
    ]
  }
}
```

`|| true` prevents hook errors from blocking Claude Code.

## Memory Logger

See what memory operations happened in a session:

```bash
# latest session
python scripts/memory_logger.py

# specific session
python scripts/memory_logger.py --session ~/.claude/projects/-root/abc123.jsonl

# last 20 ops only
python scripts/memory_logger.py --tail 20

# append to today's session log
python scripts/memory_logger.py --append-session
```

## Dry Run

Test without writing any files:

```bash
python scripts/compile.py --dry-run
```

## config.yaml

Copy `config.yaml`, fill in your keys, **add to .gitignore**:

```bash
echo "scripts/config.yaml" >> .gitignore
```

Keys in config.yaml are overridden by environment variables.
