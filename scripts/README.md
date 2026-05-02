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

## Setup — 2 steps

```bash
# 1. Install
pip install openai pyyaml

# 2. Set your key + provider URL (model is auto-detected)
export LLM_API_KEY="your-key"
export LLM_BASE_URL="https://api.groq.com/openai/v1"

python scripts/compile.py
```

**Model is selected automatically** — the script calls `/v1/models`, sees what's available, picks the best one. No model name needed.

**Free options (zero cost to start):**
- Groq: [console.groq.com](https://console.groq.com) → free tier
  ```
  LLM_BASE_URL=https://api.groq.com/openai/v1
  ```
- Cerebras: [cloud.cerebras.ai](https://cloud.cerebras.ai) → free tier
  ```
  LLM_BASE_URL=https://api.cerebras.ai/v1
  ```

Works with **any OpenAI-compatible API**: Groq, Cerebras, SambaNova, OpenRouter,
Together AI, Mistral, local Ollama — anything that speaks `/v1/chat/completions`.

If a model hits a rate limit, the script automatically falls back to the next available model.

## Named provider env vars (alternative)

If you don't want to set `LLM_BASE_URL`, just set the named var and the script
figures out the URL itself:

```
CEREBRAS_API_KEY=<key>   → https://api.cerebras.ai/v1   (auto)
GROQ_API_KEY=<key>       → https://api.groq.com/openai/v1 (auto)
SAMBANOVA_API_KEY=<key>  → https://api.sambanova.ai/v1   (auto)
OPENAI_API_KEY=<key>     → https://api.openai.com/v1     (auto)
ANTHROPIC_API_KEY=<key>  → Anthropic SDK                 (auto)
```

Priority: `LLM_API_KEY` → Cerebras → Groq → SambaNova → OpenAI → Anthropic

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
