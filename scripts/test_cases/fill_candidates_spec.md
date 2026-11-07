# Spec: page top-up candidates for a tailored resume (fill_candidates)

A tailored resume is built from a BASE resume (one per track). The base lists, for every entry (a job or a project, identified by
a key such as "HP", "FS", "JSA", "ML"), an ordered list of bullet IDs, and an ordered list of skill-line IDs. A selection step has
already chosen, per entry, an ordered list of bullet IDs (it may drop, swap or add bank bullets) and an ordered list of skill lines.
When the printed page comes out too short, the program adds back items one at a time. This function returns the ordered list of
items that MAY be added back, best first. It never invents text: only items of the base resume can be returned.

Inputs:
- selection: {"exp": {key: [bullet ids]}, "projects": {key: [bullet ids]}, "skill_lines": [skill ids]}
- base: {"experience": [{"key", "base_bullets": [ids]}], "projects": [{"key", "base_bullets": [ids]}], "base_skill_lines": [ids]}
- bank: {bullet id: {"text", "tags"}}  (tags is a single string such as "data cleaning, Excel modeling")
- pool: {skill id: {"label", "text"}}
- jd: job description text

Rules:
1. Bullet candidates: for each entry, every base bullet of that entry that is not in the selection for that entry.
   - Skip it if its ID is not in the bank.
   - Skip it if a selected bullet of the SAME entry that is NOT one of that entry's base bullets has exactly the same tags string
     (that selected bullet is a reworded variant of the same fact).
   - Skip every bullet of an entry whose selection already has (number of base bullets of that entry + 1) bullets or more.
   - Return no bullet candidates at all when the total number of selected bullets over all entries is already ≥ (total base bullets + 1).
2. Skill-line candidates: every base skill line not in the selected skill lines, skipping one whose ID is not in the pool and one
   whose label equals the label of any selected skill line. Return none when the selection already has ≥ (base skill lines + 1).
3. Order: all bullet candidates first, then all skill-line candidates. Within bullets, sort by JD relevance descending; ties keep
   the base order (entries in the order experience then projects, bullets in base order). Same for skill lines (ties = base order).
   JD relevance = the number of distinct words shared between the item's text and the JD, where a word is a lowercase run of
   letters (plus '+' and '#') of length ≥ 4 that starts with a letter, and these stop words do not count: with that this from have
   will your their about which they them were been into more than also such other work experience team teams role skills ability
   strong using used build building years year ours our you are and the for can able including related required preferred plus must.
4. Output: a list of triples: ["bullet", entry key, bullet id] or ["skill", null, skill id].
5. An entry key appears either under "exp" or "projects" in the selection, as in the base; a missing key means no bullets selected.
