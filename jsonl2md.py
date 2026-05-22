#!/usr/bin/env python3
"""jsonl2md - list and export Claude conversations from the macOS Claude.app as markdown.

Two sources, each with a list verb and an export verb, plus a standalone renderer:

  Claude Code sessions (a project on disk):
    list-sessions          List non-archived, user-titled sessions in --cwd.
    export-session <title> Export one session to .md (filename = title).
    export-session --all   Export every session matching the filter.

  Claude.ai chats (desktop app sidebar):
    list-chats             List the top --limit chats in sidebar order.
    export-chat <name>     Export one chat to .md (filename = chat name).
    export-chat --all      Export every chat in the top --limit window.

  Standalone:
    render <path.jsonl>    Render any Claude Code .jsonl (or stdin) to .md on stdout.

Sessions are discovered from Claude.app's metadata at
    ~/Library/Application Support/Claude/claude-code-sessions/<workspace>/<device>/local_*.json
with transcripts at
    ~/.claude/projects/<cwd-with-slashes-as-dashes>/<cliSessionId>.jsonl
Chats are fetched from claude.ai using cookies decrypted from the desktop app's cookie store.
"""

import argparse
import glob
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
from urllib.request import Request, urlopen

DEFAULT_CWD = "/Users/derekbredensteiner/Documents/PlatformIO/Projects/soda-flavor-injector"
META_ROOT = os.path.expanduser("~/Library/Application Support/Claude/claude-code-sessions")
JSONL_ROOT = os.path.expanduser("~/.claude/projects")
CLAUDE_APP_DIR = os.path.expanduser("~/Library/Application Support/Claude")
COOKIE_DB = os.path.join(CLAUDE_APP_DIR, "Cookies")
KEYCHAIN_SERVICE = "Claude Safe Storage"
KEYCHAIN_ACCOUNT = "Claude Key"


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


def _claude_app_aes_key():
    pw = subprocess.run(
        ["security", "find-generic-password", "-wa", KEYCHAIN_ACCOUNT, "-s", KEYCHAIN_SERVICE],
        capture_output=True, text=True, check=True,
    ).stdout.strip().encode()
    return hashlib.pbkdf2_hmac("sha1", pw, b"saltysalt", 1003, 16)


def _decrypt_cookie(encrypted, key):
    # Chromium v10/v11 format on macOS: 3-byte version prefix, then AES-128-CBC
    # ciphertext (IV = 16 spaces). Plaintext is 32-byte SHA-256 prefix + value.
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    body = encrypted[3:]
    d = Cipher(algorithms.AES(key), modes.CBC(b" " * 16), backend=default_backend()).decryptor()
    pt = d.update(body) + d.finalize()
    return pt[32:-pt[-1]].decode("utf-8", errors="replace")


def _claude_ai_credentials():
    key = _claude_app_aes_key()
    db = sqlite3.connect(COOKIE_DB)
    rows = db.execute(
        "SELECT name, value, encrypted_value FROM cookies WHERE host_key LIKE '%claude.ai%'"
    ).fetchall()
    cookies = {}
    for name, value, enc in rows:
        cookies[name] = value if value else _decrypt_cookie(enc, key)
    return cookies


def _claude_ai_get(path, cookies):
    org = cookies["lastActiveOrg"]
    cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())
    url = f"https://claude.ai/api/organizations/{org}{path}"
    req = Request(url, headers={
        "Cookie": cookie_header,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://claude.ai/",
        "Origin": "https://claude.ai",
    })
    with urlopen(req, timeout=20) as resp:
        return json.loads(resp.read())


def list_chats(limit):
    return _claude_ai_get(f"/chat_conversations?limit={limit}", _claude_ai_credentials())


def fetch_chat(uuid, cookies=None):
    cookies = cookies or _claude_ai_credentials()
    return _claude_ai_get(
        f"/chat_conversations/{uuid}?tree=True&rendering_mode=messages&render_all_tools=true",
        cookies,
    )


def chat_to_records(chat):
    for m in chat.get("chat_messages", []):
        role = "user" if m.get("sender") == "human" else "assistant"
        text = "\n\n".join(c.get("text", "") for c in m.get("content", []) if c.get("type") == "text")
        yield {"message": {"role": role, "content": text}}


def cmd_list_sessions(args):
    for s in list_sessions(args.cwd):
        print(s["title"])


def cmd_list_chats(args):
    for c in list_chats(args.limit):
        print(c.get("name") or "(untitled)")


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


def cmd_export_chat(args):
    cookies = _claude_ai_credentials()
    chats = list_chats(args.limit)
    if args.all:
        targets = chats
    elif args.name:
        targets = [c for c in chats if (c.get("name") or "") == args.name]
        if not targets:
            print(
                f"No chat named {args.name!r} in the top {args.limit}. "
                f"Try 'jsonl2md.py list-chats --limit N' to widen the search.",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        print("export-chat: provide a name or --all", file=sys.stderr)
        sys.exit(2)
    os.makedirs(args.out, exist_ok=True)
    for c in targets:
        chat = fetch_chat(c["uuid"], cookies)
        md = render_md(chat_to_records(chat))
        base = safe_name(c.get("name") or c["uuid"])
        md_path = os.path.join(args.out, base + ".md")
        with open(md_path, "w") as f:
            f.write(md)
        print(md_path)


def cmd_render(args):
    text = open(args.path).read() if args.path else sys.stdin.read()
    sys.stdout.write(render_md(iter_records(text)))


EPILOG = """\
examples:
  # Claude Code sessions (current project on disk)
  jsonl2md.py list-sessions
  jsonl2md.py list-sessions --cwd /path/to/other/project
  jsonl2md.py export-session "Professor - done"
  jsonl2md.py export-session "Professor - done" --out ~/Desktop
  jsonl2md.py export-session --all --out ./exports

  # Claude.ai chats (desktop app sidebar)
  jsonl2md.py list-chats
  jsonl2md.py list-chats --limit 50
  jsonl2md.py export-chat "Go to Market Strategy"
  jsonl2md.py export-chat --all --limit 10 --out ./chat-exports

  # Standalone: any Claude Code .jsonl on disk
  jsonl2md.py render path/to/session.jsonl > out.md
  cat session.jsonl | jsonl2md.py render > out.md
"""


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = ap.add_subparsers(
        dest="cmd",
        metavar="{list-sessions,export-session,list-chats,export-chat,render}",
    )

    p_ls = sub.add_parser("list-sessions", help="list non-archived, user-titled Claude Code sessions")
    p_ls.add_argument("--cwd", default=DEFAULT_CWD,
                     help=f"project path to filter by (default: {DEFAULT_CWD})")
    p_ls.set_defaults(func=cmd_list_sessions)

    p_es = sub.add_parser(
        "export-session",
        help="export Claude Code session(s) to .md",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_es.add_argument("title", nargs="?",
                     help="exact session title (use 'list-sessions' to see them); omit when using --all")
    p_es.add_argument("--all", action="store_true",
                     help="export every visible session in the target cwd")
    p_es.add_argument("--cwd", default=DEFAULT_CWD,
                     help=f"project path to filter by (default: {DEFAULT_CWD})")
    p_es.add_argument("--out", default=".",
                     help="output directory (default: current dir)")
    p_es.set_defaults(func=cmd_export_session)

    p_lc = sub.add_parser("list-chats", help="list main Claude.ai chats from the desktop app sidebar")
    p_lc.add_argument("--limit", type=int, default=30,
                     help="how many recent chats to fetch (default: 30)")
    p_lc.set_defaults(func=cmd_list_chats)

    p_ec = sub.add_parser(
        "export-chat",
        help="export Claude.ai chat(s) to .md",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_ec.add_argument("name", nargs="?",
                     help="exact chat name (use 'list-chats' to see them); omit when using --all")
    p_ec.add_argument("--all", action="store_true",
                     help="export every chat in the top --limit window")
    p_ec.add_argument("--limit", type=int, default=30,
                     help="how many recent chats to consider (default: 30)")
    p_ec.add_argument("--out", default=".",
                     help="output directory (default: current dir)")
    p_ec.set_defaults(func=cmd_export_chat)

    p_ren = sub.add_parser("render", help="render a JSONL file or stdin to markdown on stdout")
    p_ren.add_argument("path", nargs="?",
                      help="path to a .jsonl file (omit to read from stdin)")
    p_ren.set_defaults(func=cmd_render)

    args = ap.parse_args()
    if not args.cmd:
        ap.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()
