# jsonl2md

List and export Claude conversations from the macOS Claude.app desktop client as markdown.

Two sources, each with a list verb and an export verb, plus a standalone renderer:

| Source | List | Export |
| --- | --- | --- |
| Claude Code sessions (current project) | `list-sessions` | `export-session "<title>"` |
| Claude.ai chats (desktop app sidebar)  | `list-chats`    | `export-chat "<name>"` |

`export-session` and `export-chat` both accept `--all` and `--out <dir>`. The chat commands also accept `--limit N` (default 30) since the Claude.ai API is paged.

Plus `render <path.jsonl>` — standalone, render any Claude Code transcript file (or stdin) to Markdown on stdout, no metadata lookup.

## Install

```sh
pip install -r requirements.txt
```

That installs `cryptography` (used to decrypt Claude.app's cookie store on macOS).

## Usage

```sh
# Claude Code sessions (current project on disk)
./jsonl2md.py list-sessions
./jsonl2md.py list-sessions --cwd /Users/me/some-other-project
./jsonl2md.py export-session "Professor - done"
./jsonl2md.py export-session "Professor - done" --out ~/Desktop
./jsonl2md.py export-session --all --out ./exports

# Claude.ai chats (desktop app sidebar)
./jsonl2md.py list-chats
./jsonl2md.py list-chats --limit 50
./jsonl2md.py export-chat "Go to Market Strategy"
./jsonl2md.py export-chat --all --limit 10 --out ./chat-exports

# Standalone: any Claude Code .jsonl file
./jsonl2md.py render path/to/session.jsonl > out.md
cat session.jsonl | ./jsonl2md.py render > out.md
```

The default `--cwd` is hardcoded to `soda-flavor-injector` (the project this tool was built for); override with `--cwd` for anything else.

## How it finds things

**Claude Code sessions:**

- Metadata at `~/Library/Application Support/Claude/claude-code-sessions/<workspace>/<device>/local_*.json`. The filter is `cwd == --cwd` AND `isArchived == false` AND `titleSource == "user"`.
- Transcripts at `~/.claude/projects/<cwd-with-/-replaced-by-->/<cliSessionId>.jsonl`.

**Claude.ai chats:**

- Cookies decrypted from `~/Library/Application Support/Claude/Cookies` using the AES key in macOS Keychain (`Claude Safe Storage` / `Claude Key`). First run prompts — pick **Always Allow** to silence it.
- Then `https://claude.ai/api/organizations/<lastActiveOrg>/chat_conversations` and `/chat_conversations/<uuid>`.

## Output format

Each user/assistant turn renders as:

```
---

# User

---

{content}
```

`tool_use`, `tool_result`, `thinking`, and system records are dropped — the output is just the human-readable conversation.

## Samples

`samples/` holds two real exports — `Professor - done` and `Chief of Staff - Beta Testers` — as `.md` files.
