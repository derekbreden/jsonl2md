# The Salon Protocol

A way to run several Claude Code sessions as a **salon** — independent, long-lived
conversation threads (some of them deliberately adversarial) — and route curated
excerpts between them, with **you** as the switchboard.

This is not agent-to-agent orchestration. A2A / MCP / "agent-as-tool" all exist to
let one agent call another *without* a human in the routing loop. The salon is the
inverse: the agents never address each other; you hand-carry what crosses, when it
crosses, and to whom. The value is your editorial judgment. The closest old idea is
the **blackboard** architecture — anonymous knowledge sources that only read/write a
shared medium, with a *control component* deciding who acts next. You are that control
component.

## The one rule

You stay the mediator. You **open** a connection by naming a peer and authorizing a
relay; you **close** it by withholding the next authorization. Nothing crosses between
two threads unless you, per message, send it.

## The two primitives

| Need | Tool | Why it fits |
| --- | --- | --- |
| **Read** "what's new in thread A since I last shared" | `jsonl2md.py delta "<A title>"` | per-session cursor; previews by default, advances only on `--commit` |
| **Cross** an excerpt into live thread B | `mcp__ccd_session_mgmt__send_message(session_id, message)` | lands as a labelled `From {A title}` user turn; **always asks you to confirm**; disabled in unsupervised/bypass mode |
| **Find** B's `session_id` | `mcp__ccd_session_mgmt__list_sessions()` / `search_session_transcripts(query)` | the confirm dialog + the `From {title}` label are your guards against a wrong target |

`send_message`'s mandatory confirm is the gate. You can read the exact outgoing
payload and decline (or decline and ask A to trim) before anything crosses. That is
the switchboard, enforced by the harness, not by discipline.

## The physical limit (set expectations here)

**No mechanism wakes an idle session.** `send_message` *enqueues* a user turn in B; B
acts on it the next time B runs. If B is parked at its prompt, the relayed turn sits
unread until you focus B and let it go. So:

- "Real-time" only exists while both threads are actively looping.
- Otherwise the salon is a **human-clocked mailbox** — which is the point. You are the clock.

Don't try to build around this. The hooks can't fix it (`Stop` hooks fire only when a
session takes a turn; a parked session takes none), and a daemon can't fix it
(`send_message` is the only injection seam, and it always prompts and always queues).

## The workflow

### Open
Decide the pairing. In thread A, get B's id:

```
mcp__ccd_session_mgmt__list_sessions()
```

Then tell A, in plain language, the standing instruction — this *is* the open:

> You are relaying to session **"<B title>"** (id `<uuid>`). When I say **relay**, call
> `send_message` to that id with **only your most recent finding**, verbatim, no preamble.
> If I say **relay since last**, I'll paste the new turns; relay exactly those.

(Because the binding lives in A's context, re-state it after a compaction, or pin it
in the project's `CLAUDE.md`.)

### Relay (A → B)
Type `relay`. A calls `send_message(session_id=<B>, message="<its last finding>")`. You
confirm (or decline). On confirm it lands in B as a `From {A}` user turn. B treats it
like any prompt on its next turn.

For a multi-turn delta instead of "last finding," run the cursor:

```
jsonl2md.py delta "<A title>"            # preview the new turns
jsonl2md.py delta "<A title>" --commit   # once you've actually relayed them
```

Paste that into A's `relay`, or straight into B yourself.

### Reply (B → A)
B, seeing a `From {A}` turn, replies by calling `send_message` back to A's id (tell B
once, or include "reply via send_message to id `<A-uuid>`" in the relayed payload). You
confirm the return hop in B's window. It lands in A as `From {B}`. Two symmetric,
independently-confirmed sends = a genuine round-trip, no copy-paste-back.

### Close
Stop authorizing relays — decline the next confirm, or tell A "stop relaying to B."
Silence is closed; there's no background channel to tear down. To fully drop the
binding, clear A's instruction.

## Honest limits

- **Idle peers don't auto-process** (see above) — nudge B's window for the relay to land.
- **Two confirms per round-trip.** That friction *is* the mediation; it's also friction.
- **Off in bypass/unsupervised mode** — `send_message` is unavailable when running headless.
- **No edit-in-flight.** The confirm is accept/decline; to alter a payload, decline and
  ask the agent to rephrase.
- **Echo risk.** A relayed turn becomes a real user turn in B's transcript, so a later
  `delta "B"` will re-emit it. Curate; don't ping-pong the same text.

## Optional: wire it into a project

Paste a pointer into a project's `CLAUDE.md` so any session there knows the protocol:

```markdown
## Relaying between sessions (Salon Protocol)
To hand a finding to another live session, call mcp__ccd_session_mgmt__send_message
with that session's id (find it via list_sessions). It always prompts the user to
confirm. Relay only the most recent finding unless told "relay since last." See
~/jsonl2md/SALON.md.
```
