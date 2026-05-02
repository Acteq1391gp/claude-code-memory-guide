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
pip install openai pyyaml   # minimum — openai package works for all providers below

# 2. Set ANY key you have — one is enough
export LLM_API_KEY="your-key"
export LLM_BASE_URL="https://api.groq.com/openai/v1"   # Groq example
export LLM_MODEL="llama-3.3-70b-versatile"

# 3. Run
python scripts/compile.py
```

Works with **any OpenAI-compatible API**: Groq, Cerebras, SambaNova, OpenRouter,
Together AI, Mistral, local Ollama — anything that speaks `/v1/chat/completions`.

**Free options:**
- Groq: [console.groq.com](https://console.groq.com) → free tier → `base_url: https://api.groq.com/openai/v1`
- Cerebras: [cloud.cerebras.ai](https://cloud.cerebras.ai) → free tier → `base_url: https://api.cerebras.ai/v1`

## Provider Priority

```
LLM_API_KEY (universal)
    → CEREBRAS_API_KEY
    → GROQ_API_KEY
    → SAMBANOVA_API_KEY
    → OPENAI_API_KEY
    → ANTHROPIC_API_KEY
```

Or use `scripts/config.yaml` (gitignored — safe for keys):
```yaml
llm:
  api_key: "your-key"
  base_url: "https://api.groq.com/openai/v1"
  model: "llama-3.3-70b-versatile"
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
