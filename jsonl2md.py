#!/usr/bin/env python3
"""jsonl2md - list and export Claude Code sessions as markdown.

Subcommands:
  list-sessions          List non-archived, user-titled sessions in the target cwd.
  export-session <title> Export one session to markdown (filename = title).
  export-session --all   Export every session matching the filter.
  render <path.jsonl>    Render a JSONL file directly to stdout (no metadata lookup).

Sessions are discovered from Claude.app's metadata at
    ~/Library/Application Support/Claude/claude-code-sessions/<workspace>/<device>/local_*.json
and the actual transcripts are read from
    ~/.claude/projects/<cwd-with-slashes-as-dashes>/<cliSessionId>.jsonl
"""

import argparse
import glob
import json
import os
import re
import sys

DEFAULT_CWD = "/Users/derekbredensteiner/Documents/PlatformIO/Projects/soda-flavor-injector"
META_ROOT = os.path.expanduser("~/Library/Application Support/Claude/claude-code-sessions")
JSONL_ROOT = os.path.expanduser("~/.claude/projects")


def iter_records(text):
    decoder = json.JSONDecoder()
    i, n = 0, len(text)
    while i < n:
        while i < n and text[i].isspace():
            i += 1
        if i >= n:
            break
        obj, end = decoder.raw_decode(text, i)
        yield obj
        i = end


def extract_message(obj):
    msg = obj.get("message") or {}
    role = msg.get("role") or obj.get("type")
    content = msg.get("content")
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        text = "\n\n".join(p.get("text", "") for p in content if p.get("type") == "text")
    else:
        text = ""
    return role, text.strip()


def render_md(records):
    blocks = []
    for obj in records:
        role, text = extract_message(obj)
        if role not in ("user", "assistant") or not text:
            continue
        label = "User" if role == "user" else "Assistant"
        blocks.append(f"---\n\n# {label}\n\n---\n\n{text}\n")
    return "\n".join(blocks)


def list_sessions(target_cwd):
    out = []
    for p in glob.glob(f"{META_ROOT}/*/*/local_*.json"):
        try:
            m = json.load(open(p))
        except Exception:
            continue
        if m.get("cwd") != target_cwd:
            continue
        if m.get("isArchived"):
            continue
        if m.get("titleSource") != "user":
            continue
        out.append(m)
    out.sort(key=lambda m: m.get("lastActivityAt", 0), reverse=True)
    return out


def jsonl_path_for(cli_session_id, cwd):
    return os.path.join(JSONL_ROOT, cwd.replace("/", "-"), f"{cli_session_id}.jsonl")


def safe_name(name):
    return re.sub(r"[/\\:]+", "_", name).strip()


def cmd_list_sessions(args):
    for s in list_sessions(args.cwd):
        print(s["title"])


def cmd_export_session(args):
    sessions = list_sessions(args.cwd)
    if args.all:
        targets = sessions
    elif args.title:
        targets = [s for s in sessions if s["title"] == args.title]
        if not targets:
            print(f"No non-archived user-titled session named {args.title!r} in {args.cwd}", file=sys.stderr)
            sys.exit(1)
    else:
        print("export-session: provide a title or --all", file=sys.stderr)
        sys.exit(2)
    os.makedirs(args.out, exist_ok=True)
    for s in targets:
        cli_id = s.get("cliSessionId")
        if not cli_id:
            print(f"missing cliSessionId in metadata: {s.get('title')!r}", file=sys.stderr)
            continue
        jsonl = jsonl_path_for(cli_id, s["cwd"])
        if not os.path.exists(jsonl):
            print(f"missing transcript: {jsonl}", file=sys.stderr)
            continue
        md = render_md(iter_records(open(jsonl).read()))
        base = safe_name(s["title"])
        md_path = os.path.join(args.out, base + ".md")
        with open(md_path, "w") as f:
            f.write(md)
        print(md_path)


def cmd_render(args):
    text = open(args.path).read() if args.path else sys.stdin.read()
    sys.stdout.write(render_md(iter_records(text)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_ls = sub.add_parser("list-sessions", help="list sessions")
    p_ls.add_argument("--cwd", default=DEFAULT_CWD)
    p_ls.set_defaults(func=cmd_list_sessions)

    p_es = sub.add_parser("export-session", help="export session(s) to .md")
    p_es.add_argument("title", nargs="?")
    p_es.add_argument("--all", action="store_true")
    p_es.add_argument("--cwd", default=DEFAULT_CWD)
    p_es.add_argument("--out", default=".")
    p_es.set_defaults(func=cmd_export_session)

    p_ren = sub.add_parser("render", help="render a JSONL file or stdin")
    p_ren.add_argument("path", nargs="?")
    p_ren.set_defaults(func=cmd_render)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
