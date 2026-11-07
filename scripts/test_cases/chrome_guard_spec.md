# Spec: which job-Chrome extensions block a runner

Input: Chrome's `Secure Preferences` → `extensions.settings`, a map extension id → {manifest: {name}, location: int,
disable_reasons: list, path: str, state?, blacklist_state?}. Output: the list of (id, name) that are ENABLED and NOT allowed.

- Enabled = the entry has a non-empty manifest AND disable_reasons is missing, null or an empty list AND it is not
  blocklisted (blacklist_state truthy) AND state is not 0. An entry with no manifest is a stub → ignored.
- Allowed (never listed): the Claude extension id fcoeoabgfenejglbffodgkkbkcdhcgfn; Chrome defaults
  ghbmnnjooekpmoecnnnilnnbdlolhkhi (Docs Offline) and nmmhkkegccagdldgiimedpiccmgmieda (Web Store Payments); any entry
  with location 5 or 10 (Chrome component); an UNPACKED entry (location 4) whose path contains "lever_fill".
- Everything else enabled is listed: password managers (iCloud Passwords pejdijmoenmkgeppbflobdenhhabjlaj), autofill
  (Simplify pbanhockgagggenencehbnadejlgchfc), AI sidebars, userscript managers, any other unpacked folder.
