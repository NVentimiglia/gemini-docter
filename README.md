# gemini-docter

Analyzes AI coding sessions (Gemini, Claude, Cursor, Copilot) for behavioral anti-patterns and generates rules for GEMINI.md / AGENTS.md.

Ported from [claude-doctor](https://github.com/nicholasventi/claude-doctor) with multi-provider support.

## How it works

1. **Hooks capture data in real-time** - a Gemini CLI `AfterAgent` hook writes conversation turns to `~/.gemini-docter/transcripts/<session-id>.jsonl`
2. **Signal detection** runs on the JSONL files, looking for correction-heavy sessions, edit-thrashing, error loops, and more
3. **Rules are generated** for your GEMINI.md or AGENTS.md

> **Note**: Antigravity's `.pb` conversation files are encrypted and cannot be analyzed directly. The hooks capture data going forward after installation.

## Installation

gemini-docter is a **machine-level tool** — install it once and it monitors all your sessions,
regardless of which project you're working in. You do not add it to individual projects.

### 1. Clone to a permanent location

```bash
git clone https://github.com/nventimiglia/gemini-docter D:/Tools/gemini-docter
cd D:/Tools/gemini-docter
```

```windows
py -3 -m pip install -r requirements.txt
```

```mac
python3 -m pip install -r requirements.txt
```

### 2. Install hooks (once)

```windows
py install_hooks.py
```

```mac
python3 install_hooks.py
```

This writes two entries into `~/.gemini/settings.json` pointing at the hook scripts in this
directory. After restarting Gemini CLI, every session will be captured automatically.

### 3. Analyze

Run from the `gemini-docter` directory at any time:

```windows
py run.py                 # full analysis of all captured sessions
py run.py --rules         # generate rules for GEMINI.md
py run.py status          # check hook health and provider availability
```

```mac
python3 run.py            # full analysis of all captured sessions
python3 run.py --rules    # generate rules for GEMINI.md
python3 run.py status     # check hook health and provider availability
```

### Filtering to a specific project

```windows
py run.py -p myproject
```

```mac
python3 run.py -p myproject
```

### No hooks needed for Claude Code

Claude Code sessions are already stored in `~/.claude/projects/`. Use `--providers claude`
to analyze them without any hook installation:

```windows
py run.py --providers claude
py run.py --providers gemini,claude
```

```mac
python3 run.py --providers claude
python3 run.py --providers gemini,claude
```

## Multi-provider support

By default only the `gemini` provider (hook-captured transcripts) is enabled. To include other providers:

```windows
py run.py --providers gemini,claude
py run.py --providers gemini,claude,cursor,copilot
```

```mac
python3 run.py --providers gemini,claude
python3 run.py --providers gemini,claude,cursor,copilot
```

| Provider | Source | Notes |
|---|---|---|
| `gemini` | `~/.gemini-docter/transcripts/` | Requires hook installation |
| `claude` | `~/.claude/projects/` | Claude Code transcripts (same JSONL format) |
| `cursor` | Cursor SQLite workspace databases | Schema may vary by version |
| `copilot` | GitHub Copilot Chat JSON session files | Path varies by OS |

## CLI reference

```windows
py run.py                       # analyze all sessions
py run.py <session-id>          # check a specific session
py run.py --rules               # generate rules
py run.py status                # health check
py run.py --install             # install hooks
py run.py --uninstall           # remove hooks
```

```mac
python3 run.py                  # analyze all sessions
python3 run.py <session-id>     # check a specific session
python3 run.py --rules          # generate rules
python3 run.py status           # health check
python3 run.py --install        # install hooks
python3 run.py --uninstall      # remove hooks
```

## Signals detected

| Signal | Description |
|---|---|
| `correction-heavy` | 20%+ user messages start with "no", "wrong", "wait" |
| `keep-going-loop` | User repeatedly says "keep going" / "continue" |
| `repeated-instructions` | Same instruction rephrased within 5 turns (Jaccard >60%) |
| `negative-drift` | Messages get shorter and more corrective over time |
| `rapid-corrections` | User responds within 10s of agent output |
| `high-turn-ratio` | User sends 1.5x+ messages per agent response |
| `negative-sentiment` | VADER sentiment score below threshold |
| `user-interrupts` | User interrupted the agent |
| `edit-thrashing` | Same file edited 5+ times in one session |
| `large-file-write` | Full file write of 150+ lines (prefer targeted edits) |
| `error-loop` | 3+ consecutive tool failures without changing approach |
| `excessive-exploration` | Read-to-edit ratio above 10:1 |

## Configuration

Edit `~/.gemini-docter/config.json` to customize:

```json
{
  "providers": ["gemini", "claude"],
  "max_line_length": 80,
  "enable_rfc2119": true,
  "thresholds": {
    "THRASHING_EDIT_THRESHOLD": 3
  }
}
```

## Hook schema verification

During initial setup, each hook writes the raw Gemini CLI event data to `~/.gemini-docter/debug/<session-id>_raw.jsonl`. Inspect these files to verify the hook input schema matches expectations. The hook format is based on `gemini-cli-core` v0.38 and may change in future versions.

## Requirements

- Python 3.10+
- `vaderSentiment` (optional - falls back to word-list scoring if not installed)

```bash
pip install -r requirements.txt
```

## License

MIT - see [LICENSE](LICENSE).
