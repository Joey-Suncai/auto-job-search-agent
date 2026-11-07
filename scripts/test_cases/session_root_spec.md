# Which folder decides the session's system? (2026-11-05)

pick_root(hook_input, cwd, script_root) returns the folder whose git checkout decides whether a session is the using or the
developing system. The session start hook passes its JSON input text (Claude Code writes an object such as
{"session_id": "…", "cwd": "/Users/x/agent/.claude/worktrees/w1", "hook_event_name": "SessionStart", "source": "startup"}),
the process's working directory, and the folder of the checkout that holds the script.

Order:
1. If hook_input is a string that parses as a JSON object, and that object has a key "cwd" whose value is a string that is
   not empty after trimming surrounding spaces → return that value, trimmed.
2. Otherwise, if cwd is a string that is not empty after trimming → return cwd, trimmed.
3. Otherwise → return script_root, trimmed when it is a non-blank string; returned as given otherwise.

Anything else in hook_input is ignored, never an error: null, an empty or blank string, text that is not JSON, valid JSON
that is not an object (a list, a number, a quoted string), an object without "cwd", or a "cwd" that is null, a number, a
list, an object, or a blank string. The other keys of the object do not matter. Paths are returned as text; they are not
checked to exist and not normalised (no case change, no removing of trailing "/").
