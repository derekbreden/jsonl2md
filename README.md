# jsonl2md

List and export Claude Code sessions as markdown + PDF.

Built for macOS / Claude.app. Reads session metadata (titles, archive state) from
`~/Library/Application Support/Claude/claude-code-sessions/` and transcripts from
`~/.claude/projects/`.

## Install

```sh
pip install -r requirements.txt
```

## Usage

```sh
# What sessions are visible (non-archived, user-titled) for the default project?
./jsonl2md.py list

# Export one by title — produces .md and .pdf side by side.
./jsonl2md.py export "Professor - done"

# Export every visible session.
./jsonl2md.py export --all --out ./exports

# Different project.
./jsonl2md.py list --cwd /Users/me/some-other-project

# Bypass the metadata lookup — render any JSONL file (or stdin) to stdout.
./jsonl2md.py render path/to/session.jsonl > transcript.md
```

The default `--cwd` is hardcoded to `soda-flavor-injector` (the project this tool was built for); override with `--cwd` for anything else.

## Filter

`list` and `export` (without `--all` selecting more) only consider sessions where:

- `cwd` matches `--cwd`
- `isArchived` is false
- `titleSource` is `"user"` (i.e. you've explicitly named it)

This matches the visible sidebar in Claude.app.

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

`samples/` holds two real exports — `Professor - done` and `Chief of Staff - Beta Testers` — each as both `.md` and `.pdf`.
