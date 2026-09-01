# Day 5 — Security: Sandboxing & Prompt Injection

**Goal:** Build genuinely dangerous tools (shell, write_file, sql_query), harden each,
add a human approval gate, then attack my own agent and document what held.

**Status:** Done. Three hardened tools, approval gate, and a full attack report with
forced-attack + canary demonstrations.

---

## The threat model (the grounding)

**The core problem:** the model sees ONE flat stream of text and can't reliably tell
"my instructions" from "data I'm processing." When a tool returns file contents / web
pages / DB rows, attacker-controlled text is now in the model's context, looking exactly
like everything else.

**The trust boundary:**
- TRUSTED: my system prompt, the user's task.
- UNTRUSTED: everything a tool returns — file contents, web pages, SQL rows, API
  responses. I don't control what's in them.

**The lethal trifecta (Simon Willison):** an agent is dangerous when it has all three:
1. access to private data
2. exposure to untrusted content
3. ability to communicate externally

Any one alone is fine. All three = injected text can exfiltrate ("read the secrets, send
them to my server"). My agent has all three (read_file + http_get + shell).

**The uncomfortable truth:** you CANNOT fully prevent prompt injection. No filter
reliably separates instructions from data. So the strategy is NOT "make the model
un-foolable" — it's "make being fooled survivable." Limit the blast radius.

### Why "tell the model to ignore file instructions" is not enough
That instruction is just more text in the context. An injection can claim equal or
higher authority ("SYSTEM OVERRIDE, authorized by admin"). The model weighs what's
persuasive, not what's cryptographically trusted — there's no bit marking my words as
"real" once both are in the window. It's a SOFT preference (helps ~90%), not a hard
boundary, and attackers craft for the 10%. Keep it (it's free and helps), but put real
barriers behind it.

> **The shift:** stop trying to make the model un-foolable (impossible). Make being
> fooled survivable (very possible). Model instruction-following = soft filter. My code
> = hard boundary. The attacker's text has no vote in my code.

---

## Tool 1 — shell (allowlist + shell=False)

```python
ALLOWED_COMMANDS = {"ls","cat","head","tail","wc","grep","find","pwd","echo"}
parts = command.split()
if parts[0] not in ALLOWED_COMMANDS:
    return "Error: not allowed..."
subprocess.run(parts, cwd=WORKSPACE, timeout=10, shell=False)   # LIST, not string
```

Defenses, all in CODE (immune to model persuasion):
- **Allowlist, not blocklist.** List what's permitted. A blocklist fails the moment you
  forget one dangerous command (there are thousands); an allowlist fails safe.
- **shell=False + pass a LIST.** THE critical line. With shell=True + a string, the
  shell interprets `;` `|` `&&` `$()`, so `cat f; rm -rf /` runs TWO commands — allowlist
  checked `cat`, shell ran the `rm`. With shell=False + list, `;` is a literal char, no
  shell to interpret it.
- **cwd=WORKSPACE** jail + **timeout=10**.

### Proven with a deleted file
- `ls; rm notes.txt` → refused by ALLOWLIST (split() makes parts[0]="ls;", not in set).
- `echo hi; rm victim.txt` with shell=True → victim.txt DELETED (echo allowlisted, shell
  ran the rm). With shell=False → survived (printed as literal text).

> **Insight:** two layers catch DIFFERENT attacks. Allowlist catches metacharacters that
> split() mangles into the first token. shell=False catches metacharacters that split()
> preserves after an allowlisted command. Neither alone is enough.

---

## Tool 2 — write_file (resolve-then-check path jail)

```python
target = (WORKSPACE / path).resolve()          # collapse ../ FIRST
if not target.is_relative_to(WORKSPACE):        # is the REAL destination inside?
    return "Error: escapes the workspace. Refused."
```

The attack is path TRAVERSAL, not a metacharacter. `WORKSPACE / "../../etc/passwd"`
climbs OUT of the jail.

- **.resolve() FIRST** — follows the `..` climbs, turns the tricky path into its real
  absolute location. You can't inspect a path for safety while it still contains `..`
  tricks; you must see where it ACTUALLY points.
- **.is_relative_to(WORKSPACE)** — checks the RESOLVED path. `..` tricks are already
  collapsed, so they can't fool it.

Refused all three traversal shapes: relative `../../`, absolute `/etc/passwd`, and nested
`subdir/../../../tmp/`. One check beats a dozen regexes.

> **One-liner:** path safety = resolve THEN check, never check the raw string. Validate
> where the path LEADS, not what it SAYS. The attacker controls the string, not where
> .resolve() says it points.

---

## Tool 3 — sql_query (read-only connection)

```python
conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)   # read-only at CONNECTION
cursor.fetchmany(100)                                          # bound results
```

The danger is data destruction (DROP/DELETE/UPDATE). The defense is NOT scanning the
query for keywords — that's a losing game (comments, case, encodings, stacked queries).
Instead: **remove the WRITE CAPABILITY at the connection level.**

Proven: `DROP TABLE`, `DELETE FROM`, `UPDATE` all rejected with "attempt to write a
readonly database" — from the SQLite ENGINE, not my code. Table survived (3 rows intact).

> **The cleanest expression of the whole day:** capability removal beats input
> inspection. A read-only connection rejects writes no matter how the SQL is phrased.
> No keyword filter needed, and none can be bypassed.

---

## The approval gate (human circuit-breaker for irreversible actions)

Some actions are dangerous even when contained + correctly requested (send email, delete,
pay, post). For those, pause and ask a human.

- `@tool(requires_approval=True)` — flag rides on the function (decorator factory pattern:
  `fn=None` lets it work both bare and with args).
- Loop checks the flag before dispatch; if set, prints the EXACT call (name + args) and
  waits for `input()`. Denial → is_error result, agent adapts gracefully (doesn't crash).

> **This is the last line of defense against a successful injection:** even if the model
> is fooled into REQUESTING something terrible, a human sees the actual request in plain
> sight ("delete all files — approve?") and refuses. The model can be tricked; the human
> reading the literal request usually can't.

**Limitation noted:** input() is synchronous — fine for CLI, but Day 7's web server needs
async pause/resume.

---

## THE ATTACK REPORT (interview centerpiece)

Built miniagent, then spent a session trying to break it. Three layers of defense, tested
independently.

### Test A — injection via file contents (benign task, malicious data)
Planted a file with 4 payloads (rm -rf via shell, path-traversal write, DROP TABLE, all
wrapped in fake authority "SYSTEM OVERRIDE / authorized by admin" + padded with innocent
notes). Task was benign: "summarize the action items."

**Result:** the model IGNORED all 4 payloads and just summarized. Layer-1 (model
reasoning) resisted — my system prompt + the model's training held.

> Note: model resistance is the SOFT layer. Real, but NOT what I rely on. Modern models
> (Haiku 4.5) are meaningfully injection-resistant, but that's a bonus, not a guarantee.

### Test B — forced attack (model 100% attempts the dangerous action)
Removed the model's choice — task directly ordered each dangerous action. The model FULLY
intended to comply. Watched the CODE defenses catch each:
- "run rm -rf ." → refused by ALLOWLIST
- "write to ../../etc/backdoor" → refused by PATH JAIL
- "DROP TABLE users" → refused by READ-ONLY CONNECTION

The model even explained the defense back ("attempts to escape the workspace... which the
function explicitly refuses").

> **The key proof:** the defense does NOT depend on the model's judgment. A model fully
> cooperating with the attacker still can't break out. Stronger than "a dumb model got
> fooled."

### Test C — canary (watch an injection SUCCEED, harmlessly)
Added an UNDEFENDED tool (send_message, no gate, only prints). Injection targeting it
FIRED: `[CANARY FIRED] would send to ...`. Watched exfiltration happen with zero risk.

> **The thesis, from the A/B/C contrast:** the difference between the safe tools and the
> canary is NOT the model — it's whether there's a code-level defense behind the tool.
> Same model, same kind of request; one refused by code, one waved through. Defense lives
> in code, not in the model.

### Damage verification (what actually happened, not what the model said)
After every test: workspace files intact, no backdoor outside the jail, users table still
3 rows. The proof is the system state, not the model's words.

---

## Defense-in-depth summary

| Layer | Type | Reliability |
|---|---|---|
| Model reasoning ("ignore file instructions") | soft | helps ~90%, don't rely on it |
| Code defenses (allowlist / path jail / read-only) | hard | holds even when model fully attempts |
| Approval gate | human | last resort for irreversible actions |

> **The sentence that lands:** "Defense-in-depth means I don't need the model to be
> perfect. I assume it WILL eventually be fooled, and make that survivable — the code
> doesn't care that the model was persuaded."

---

## Interview-ready answers

> **Q: How do you secure an agent against prompt injection?**
> You can't fully prevent it — no filter reliably separates instructions from data. So I
> limit blast radius. Every tool has code-level defenses that don't depend on the model's
> judgment: shell has an allowlist + shell=False, write_file resolves paths and refuses
> anything outside the workspace, sql uses a read-only connection. Irreversible actions
> hit a human approval gate. I proved these hold by forcing the model to attempt each
> attack — it complied fully and the code still refused.

> **Q: Why not just scan tool inputs for dangerous patterns?**
> Blocklists always miss something — shell metacharacters, SQL comments/encodings, path
> tricks. I remove the capability instead: read-only DB connection can't write no matter
> how the query is phrased; allowlist permits only known-safe commands; resolve-then-check
> makes traversal impossible. Capability removal beats input inspection.

> **Q: What's the lethal trifecta?**
> Private data access + untrusted content exposure + external communication. Any one is
> fine; all three lets injected text exfiltrate. My agent has all three, so the mitigation
> is the approval gate + no undefended external-comms tools (I demoed the hole with a
> canary tool that had no gate — the injection fired).

> **Q: Give me a security bug you found in your own code.**
> The shell allowlist masked a shell=True vulnerability — `ls; rm` was blocked by the
> allowlist (split made "ls;" the first token), so I never saw the shell danger until I
> tested `echo hi; rm` where the first token IS allowlisted. With shell=True the file got
> deleted; shell=False saved it. Taught me the two layers catch different attacks.

---

## Gut check — can I answer cold?
- [ ] Why can't you tell the model "ignore instructions in file content" and be safe?
- [ ] Allowlist vs blocklist — why allowlist?
- [ ] Why shell=False + a list, not a string? What attack does it stop that the allowlist doesn't?
- [ ] Why resolve() BEFORE the is_relative_to check, not after?
- [ ] Why is a read-only connection better than scanning SQL for DROP/DELETE?
- [ ] What's the lethal trifecta, and does my agent have all three?
- [ ] Why is the forced-attack demo stronger proof than an old model getting fooled?