#!/usr/bin/env python3
"""jsonl2md - list and export Claude Code sessions as markdown + PDF.

Subcommands:
  list                   List non-archived, user-titled sessions in the target cwd.
  export <title>         Export one session to markdown + PDF (filename = title).
  export --all           Export every session matching the filter.
  render <path.jsonl>    Render a JSONL file directly to stdout (no metadata lookup).

Sessions are discovered from Claude.app's metadata at
    ~/Library/Application Support/Claude/claude-code-sessions/<workspace>/<device>/local_*.json
and the actual transcripts are read from
    ~/.claude/projects/<cwd-with-slashes-as-dashes>/<cliSessionId>.jsonl
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


PDF_CSS = """
@page { margin: 0.8in; size: letter; }
body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 10.5pt; line-height: 1.45; }
h1 { font-size: 13pt; margin: 0.6em 0; }
h2 { font-size: 12pt; }
h3 { font-size: 11pt; }
hr { border: none; border-top: 1px solid #999; margin: 0.6em 0; }
code { font-family: SFMono-Regular, Menlo, monospace; font-size: 9.5pt; background: #f4f4f4; padding: 1px 4px; border-radius: 3px; }
pre { background: #f4f4f4; padding: 8px; border-radius: 4px; }
pre code { background: none; padding: 0; }
blockquote { border-left: 3px solid #bbb; margin-left: 0; padding-left: 12px; color: #555; }
table { border-collapse: collapse; }
td, th { border: 1px solid #ccc; padding: 4px 8px; }
"""


def write_pdf(md_text, out_path):
    import markdown as md_lib
    from weasyprint import HTML
    html_body = md_lib.markdown(md_text, extensions=["fenced_code", "tables"])
    html = f"<html><head><meta charset='utf-8'><style>{PDF_CSS}</style></head><body>{html_body}</body></html>"
    HTML(string=html).write_pdf(out_path)


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


def list_chats(limit):
    cookies = _claude_ai_credentials()
    org = cookies["lastActiveOrg"]
    cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())
    url = f"https://claude.ai/api/organizations/{org}/chat_conversations?limit={limit}"
    req = Request(url, headers={
        "Cookie": cookie_header,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://claude.ai/",
        "Origin": "https://claude.ai",
    })
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def cmd_list(args):
    for s in list_sessions(args.cwd):
        print(s["title"])


def cmd_chats(args):
    for c in list_chats(args.limit):
        print(c.get("name") or "(untitled)")


def cmd_export(args):
    sessions = list_sessions(args.cwd)
    if args.all:
        targets = sessions
    elif args.title:
        targets = [s for s in sessions if s["title"] == args.title]
        if not targets:
            print(f"No non-archived user-titled session named {args.title!r} in {args.cwd}", file=sys.stderr)
            sys.exit(1)
    else:
        print("export: provide a title or --all", file=sys.stderr)
        sys.exit(2)
    os.makedirs(args.out, exist_ok=True)
    for s in targets:
        jsonl = jsonl_path_for(s["cliSessionId"], s["cwd"])
        if not os.path.exists(jsonl):
            print(f"missing transcript: {jsonl}", file=sys.stderr)
            continue
        md = render_md(iter_records(open(jsonl).read()))
        base = safe_name(s["title"])
        md_path = os.path.join(args.out, base + ".md")
        with open(md_path, "w") as f:
            f.write(md)
        line = md_path
        if not args.no_pdf:
            pdf_path = os.path.join(args.out, base + ".pdf")
            write_pdf(md, pdf_path)
            line += "  +  " + pdf_path
        print(line)


def cmd_render(args):
    text = open(args.path).read() if args.path else sys.stdin.read()
    sys.stdout.write(render_md(iter_records(text)))


EPILOG = """\
examples:
  jsonl2md.py list                                    # show Claude Code session titles in default project
  jsonl2md.py list --cwd /path/to/other/project       # ... in another project
  jsonl2md.py chats                                   # show top 30 Claude.ai sidebar chats
  jsonl2md.py chats --limit 50                        # ... top 50
  jsonl2md.py export "Professor - done"               # write .md and .pdf to current dir
  jsonl2md.py export "Professor - done" --out ~/Desktop
  jsonl2md.py export "Professor - done" --no-pdf      # skip the PDF, .md only
  jsonl2md.py export --all --out ./exports            # export every visible Claude Code session
  jsonl2md.py render path/to/session.jsonl > out.md   # raw render, no metadata lookup
  cat session.jsonl | jsonl2md.py render > out.md
"""


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = ap.add_subparsers(dest="cmd", metavar="{list,export,render}")

    p_list = sub.add_parser("list", help="list non-archived, user-titled sessions")
    p_list.add_argument("--cwd", default=DEFAULT_CWD,
                        help=f"project path to filter by (default: {DEFAULT_CWD})")
    p_list.set_defaults(func=cmd_list)

    p_exp = sub.add_parser(
        "export",
        help="export session(s) to .md (+ .pdf)",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_exp.add_argument("title", nargs="?",
                       help="exact session title (use 'list' to see them); omit when using --all")
    p_exp.add_argument("--all", action="store_true",
                       help="export every visible session in the target cwd")
    p_exp.add_argument("--cwd", default=DEFAULT_CWD,
                       help=f"project path to filter by (default: {DEFAULT_CWD})")
    p_exp.add_argument("--out", default=".",
                       help="output directory (default: current dir)")
    p_exp.add_argument("--no-pdf", action="store_true",
                       help="write only the .md file, skip PDF generation")
    p_exp.set_defaults(func=cmd_export)

    p_ren = sub.add_parser("render", help="render a JSONL file or stdin to markdown on stdout")
    p_ren.add_argument("path", nargs="?",
                       help="path to a .jsonl file (omit to read from stdin)")
    p_ren.set_defaults(func=cmd_render)

    p_chats = sub.add_parser("chats", help="list main Claude.ai chats from the desktop app sidebar")
    p_chats.add_argument("--limit", type=int, default=30,
                         help="how many recent chats to fetch (default: 30)")
    p_chats.set_defaults(func=cmd_chats)

    args = ap.parse_args()
    if not args.cmd:
        ap.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()
