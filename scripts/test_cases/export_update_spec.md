# Public export — update mode (release 2+) helper functions

A tool publishes new versions of an open-source tree into an existing git clone of the public repository. Four pure helpers decide what it may do.

## parse_version(v) → [major, minor, patch] or null
- Valid versions are exactly "v" followed by MAJOR.MINOR or MAJOR.MINOR.PATCH, each part a non-negative decimal integer written without leading zeros ("0" itself is fine, "01" is not).
- The result is the three integers; a missing PATCH counts as 0 ("v0.2" → [0, 2, 0], "v1.4.3" → [1, 4, 3]).
- Anything else gives null: no leading lowercase "v" (also "V0.2"), only one part ("v1"), four or more parts, empty parts, signs, letters or suffixes ("v0.2-beta", "v0.2rc1"), surrounding whitespace, the empty string, a non-string value.

## release_message(version) → string
Exactly "auto-job-search-agent " + version + " (public export)", e.g. "auto-job-search-agent v0.2 (public export)".

## preflight(version, tags, dirty, behind, branch, has_commits) → list of problem codes
Inputs: the version to release (string), the tags already in the clone (list of strings, may include tags that are not versions), dirty (true when the clone has uncommitted or untracked files), behind (integer: commits on the remote that the clone does not have), branch (current branch name), has_commits (false when the clone has no commits at all).
Codes, always in this order when several apply:
1. "bad_version" — version is not valid for parse_version.
2. "no_history" — has_commits is false. When this applies, "not_main" is NOT reported.
3. "not_main" — has_commits is true and branch is not exactly "main".
4. "dirty" — dirty is true.
5. "behind" — behind is greater than 0.
6. "tag_exists" — the version is valid and the exact same string is already in tags.
7. "not_newer" — the version is valid, not already a tag, and some tag that is a valid version is greater than or equal to it (compare [major, minor, patch] numerically, so v0.10 > v0.9, and v0.2 equals v0.2.0). Tags that are not valid versions are ignored. "tag_exists" and "not_newer" are never both reported.
An empty list means the release may go ahead. With no version tags at all, any valid version is newer.

## stale_paths(clone_tracked, exported) → sorted list
clone_tracked: paths tracked in the clone; exported: paths in the new export (both repo-relative, "/" separated; a "\" in a path counts as "/").
Returns, sorted ascending and without duplicates, every clone path that is not in exported — the files to delete before copying the export in.
Never returns ".git" or anything starting with ".git/" (but ".github/…" and ".gitignore" are ordinary files). Empty strings in clone_tracked are ignored.
