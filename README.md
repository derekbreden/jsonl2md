# jsonl2md

Export Claude conversations from the macOS Claude.app desktop client to clean Markdown and PDF.

This is a personal tool, put on GitHub in case it helps someone with the same setup. It is not a polished, configurable, cross-platform library — read the next section before assuming it'll work for you.

## Who this is for

You'll get value from this if **all** of the following are true:

- You're on **macOS** and use [Claude.app](https://claude.ai/download) (the desktop client).
- You want plain Markdown / PDF transcripts of either:
  - **Claude Code sessions** that show in the Claude.app sidebar — i.e. ones you've given a custom title and not archived, **or**
  - **Main Claude.ai chats** from the same desktop app's sidebar (recent N).
- You want **just the spoken text** — what you typed and what Claude wrote back. Nothing else.

You will *not* get value from this if:

- You're on **Linux or Windows**. Cookie decryption uses the macOS Keychain; session paths are macOS-specific.
- You want **tool calls, tool results, thinking blocks, system reminders, attachments, or files** in the output. They are dropped on purpose.
- You want to export **Claude Code sessions you haven't given a custom title to**, or sessions you've archived. The filter requires `titleSource: "user"` and `isArchived: false`. There is no flag to widen this.
- You need a **UI, fuzzy matching, partial-name search, paging beyond a single `--limit`, or anything beyond a list-and-export CLI**.

When I went looking for a tool that did this, I couldn't find one. Maybe the audience is small, but it's not zero.

## What it does

Five subcommands, three sources, two output formats:

| Command | What it does |
| --- | --- |
| `list` | Print Claude Code session titles in the current project. Filter: non-archived + user-titled. Matches the Claude.app sidebar. |
| `export "<title>"` | Render that session's `.jsonl` transcript to `.md` and `.pdf` side by side. Supports `--all`. |
| `chats` | Print main Claude.ai sidebar chats from the desktop app, in sidebar order. |
| `export-chat "<name>"` | Export one of them to `.md` and `.pdf`. Supports `--all`. |
| `render <path.jsonl>` | Standalone: render any Claude Code `.jsonl` file (or stdin) to Markdown on stdout. No metadata lookup. |

`export` and `export-chat` both accept `--out <dir>` and `--no-pdf`.

Run `./jsonl2md.py` with no arguments to see the full help and example commands.

## Install

```sh
pip install -r requirements.txt
```

That installs `markdown`, `weasyprint`, and `cryptography`.

## Usage

```sh
./jsonl2md.py list                                   # Claude Code sidebar (current project)
./jsonl2md.py list --cwd /Users/me/some-other-project

./jsonl2md.py export "Professor - done"              # one session → .md + .pdf in cwd
./jsonl2md.py export "Professor - done" --out ~/Desktop
./jsonl2md.py export "Professor - done" --no-pdf
./jsonl2md.py export --all --out ./exports

./jsonl2md.py chats                                  # main Claude.ai sidebar (top 30)
./jsonl2md.py chats --limit 50

./jsonl2md.py export-chat "Go to Market Strategy"
./jsonl2md.py export-chat --all --limit 10 --out ./chat-exports

./jsonl2md.py render path/to/session.jsonl > out.md  # raw, no metadata
cat session.jsonl | ./jsonl2md.py render > out.md
```

## How it finds things

**Claude Code sessions:**

- Metadata is read from `~/Library/Application Support/Claude/claude-code-sessions/<workspace>/<device>/local_*.json`. Each metadata file has `cliSessionId`, `cwd`, `title`, `titleSource`, `isArchived`, `lastActivityAt`. The filter is `cwd == --cwd` AND `isArchived == false` AND `titleSource == "user"`.
- Transcripts are at `~/.claude/projects/<cwd-with-/-replaced-by-->/<cliSessionId>.jsonl`.

**Main Claude.ai chats:**

- The script reads encrypted cookies from `~/Library/Application Support/Claude/Cookies` and decrypts them with the AES key stored in your macOS Keychain under `Claude Safe Storage` / `Claude Key`. The first run prompts for keychain access — pick **Always Allow** if you want it silent thereafter.
- It then calls `https://claude.ai/api/organizations/<lastActiveOrg>/chat_conversations` and `/chat_conversations/<uuid>` with that session cookie.

## Output format

Every user/assistant turn renders as:

```
---

# User

---

{content}
```

The `---` lines are wrapped in blank lines so they render as horizontal rules in any standard Markdown viewer; the `# User` / `# Assistant` between them gives an unambiguous, scrollable speaker label.

PDF is `markdown` → HTML → `weasyprint`. Letter paper, light styling, monospace code blocks. Edit `PDF_CSS` in `jsonl2md.py` if you want something different.

## Intentional trade-offs

This list exists because each item is a thing somebody might reasonably want different and won't get without forking:

- **`DEFAULT_CWD` is hardcoded to the author's project path.** Pass `--cwd` every time, or change the constant at the top of `jsonl2md.py` in your fork.
- **The session filter is fixed.** `list` and `export` only see custom-titled, non-archived sessions in the target cwd. There is no flag to widen it. Sessions you never named are invisible to this tool — that's the whole point of the filter, since it matches Claude.app's visible sidebar exactly.
- **`chats` and `export-chat --all` are bounded by `--limit`** (default 30). The Claude.ai API supports paging; I have never needed it. Bump the limit if you need older chats.
- **Tool calls, tool results, thinking blocks, system messages, attachments, and files are unconditionally stripped.** There is no flag to include them. The whole reason the tool exists is to produce a transcript of just the spoken text.
- **Output filenames are the session/chat title verbatim**, with `/`, `\`, and `:` replaced by `_`. Filename collisions silently overwrite.
- **macOS only.** The cookie decryption format, keychain service name, and filesystem paths are all macOS-specific. A Linux/Windows port would need new code in three places.
- **No license file.** Treat it as a reference implementation; copy what's useful.

## Samples

`samples/` has two real exports — `Professor - done` and `Chief of Staff - Beta Testers` — each as both `.md` and `.pdf`, so you can see what the output looks like before installing anything.
