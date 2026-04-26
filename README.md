# jsonl2md

Convert a Claude Code session JSONL file into a clean User/Assistant markdown transcript.

## Usage

```sh
./jsonl2md.py path/to/session.jsonl > transcript.md
```

Or via stdin:

```sh
cat session.jsonl | ./jsonl2md.py > transcript.md
```

Accepts both strict JSONL (one object per line, the on-disk format Claude Code writes) and pretty-printed multi-object files (what you get if you hand-curate by copying records).

## What it does

For each record where `message.role` is `user` or `assistant`, emits a block like:

```
---

# User

---

{content}
```

`tool_use`, `tool_result`, `thinking`, and system messages are dropped — the output is just the human-readable conversation.

## Sample

`samples/source.jsonl` is a real Claude Code session export. Run the script on it to produce `samples/transcript.md`:

```sh
./jsonl2md.py samples/source.jsonl > samples/transcript.md
```

The committed `samples/transcript.md` is what you should see.
