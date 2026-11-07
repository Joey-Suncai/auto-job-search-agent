---
name: gemini-visuals
description: Makes banners, diagrams and agent/skills maps with Google Gemini through Claude in Chrome, then captures them at full resolution without downloading — prompt recipes, retry handling, canvas capture and tile stitching.
---

# Gemini Visuals (via Claude in Chrome)

The user wants every image (banners, agent maps, skills maps) made **in Gemini**, not hand-coded. Gemini: `https://gemini.google.com/app` (he's signed in; model "Flash" default worked).

## 1. Prompt
1. `navigate` → wait 3 s. If "Students, claim your Gemini plan free for 1 year" shows, click **Not now**.
2. `find "prompt input text box"` → ref "Enter a prompt for Gemini" → click → `type` prompt → `key Return`.
3. Recipe (prompts that worked are verbatim in `skills/_shared/prompts.md`):
   - Start with `Create an image:`; give aspect ratio (16:5 banner; 16:9 diagrams); palette with hex (dark navy + UChicago maroon #800000, white cards).
   - "flat vector style, crisp readable sans-serif labels spelled exactly as given".
   - List every label verbatim, semicolons between, ≤5 words each, ≤ ~25 labels; describe layout (columns, hub, bottom band, arrows).
   - End: "No logos, no crests, no people."
4. Wait ~25 s (`wait` 10 + 10 + 5) then screenshot. Read every label; if any is wrong, reply in the same chat: "Regenerate with the exact same design but fix the text: …".

## 2. Errors
"Sorry, something went wrong. Please try your request again." → click the redo icon under the reply (≈ (224,316)) → **Try again** (≈ (278,440)). Worked on the second attempt for the agent map.

## 3. Capture at full resolution without downloading
Gemini shows the result as a `blob:` `<img>`, naturalWidth 1024 (banner 1024×318; 16:9 = 1024×572). Viewport is 960×820 at DPR 1, so capture two tiles (close any Gemini image viewer first):
```js
// tile A
const ims=[...document.querySelectorAll('img')].filter(i=>i.getBoundingClientRect().width>300);
window.__m=ims[ims.length-1];
const H=window.__m.naturalHeight, cv=document.createElement('canvas');
cv.id='__bn'; cv.width=960; cv.height=H;
Object.assign(cv.style,{position:'fixed',left:'0px',top:'0px',width:'960px',height:H+'px',zIndex:2147483647});
cv.getContext('2d').drawImage(window.__m,0,0); document.body.appendChild(cv); window.__m.naturalWidth+'x'+H
```
→ `computer zoom region [0,0,960,H] save_to_disk:true`
```js
// tile B
const cv=document.getElementById('__bn'), c=cv.getContext('2d');
c.clearRect(0,0,960,cv.height); c.drawImage(window.__m,-64,0); 'ok'
```
→ `zoom` again (save_to_disk) → `document.getElementById('__bn').remove()`.
Tiles land in the container at `/tmp/claude-chrome-screenshots-*/screenshot-*.png`. Stitch:
`python3 skills/gemini-visuals/scripts/stitch.py out.png 1024 64 tileA.png tileB.png` → prints "overlap diff 0.0" when perfect.
Use `browser_batch` for the whole sequence (one round trip).
Higher resolution: Gemini's **Download** button (top-right of the image) saves the original to ~/Downloads — needs his OK to download + folder access to Downloads.

### Capture when the viewport is wider (2026-10-26: CSS viewport 1920, screenshot frame 1568)
One tile is enough: draw the image on a fixed 1024×572 canvas at (0,0), then `zoom` region `[0,0,1024*f,572*f]` with f = frameWidth/innerWidth (0.8167 → `[0,0,836,467]`), `save_to_disk:true` → the PNG comes out at the full 1024×572.
Refusals ("I'm having a hard time fulfilling your request") → start a **new chat** with a shorter prompt (no product/school names).

## 4. Deliver
Save to the folder via `/mnt/user-data/outputs/job-search-agent/<dir>/` + `device_commit_files`: diagrams → `maps/`, banners → `github-profile/`. Show it with `SendUserFile`. To upload into a website: `device_stage_files` then `file_upload` from `/mnt/user-data/uploads/job search agent/...`.

## 5. Made on 2026-10-22
| File | Size | Content |
| --- | --- | --- |
| `github-profile/banner.png` | 1024×318 | Profile banner in steviebuchicago style |
| `maps/_archive_2026-10-22/agent-map.png` | 1024×572 | (archived) INPUTS (Resume .docx, LinkedIn, GitHub, Reference profile steviebuchicago) → TOOLS (Claude in Chrome, Gemini, GitHub web editor, Desktop folder) → ORCHESTRATOR (Claude) → OUTPUTS (GitHub avatar, bio & links, banner, README, updated resume); bottom band AI JOB-INTELLIGENCE PIPELINE (Sources → Role scoring → Fit reports → Human review → Apply) |
| `maps/_archive_2026-10-22/skills-map.png` | 1024×572 | old 3-skill version (archived) |

## 6. Regenerated on 2026-10-26 (prompts in `_shared/prompts.md`)
| File | Size | Content |
| --- | --- | --- |
| `maps/agent-map.png` | 1024×572 | INPUTS (candidate profile, 20 job sources, Gmail read-only, Joey's approvals) → ORCHESTRATOR (main chat) with SCHEDULED TASKS (daily new roles, eligibility check, weekly refresh, follow-ups) and SUBAGENTS (materials agent, form-fill agent) → OUTPUTS (dashboard, applications folder); bottom APPLICATION PIPELINE: Sources → Scoring → Eligibility gate → Joey picks → Resume + form → Joey approves → Submit + track |
| `maps/skills-map.png` | 1024×572 | job-search-agent → FIND JOBS (job-hunt-pipeline, daily-job-refresh, add-target-role) · APPLY (auto-apply, resume-updater, cover-letter-writer) · PROFILE (linkedin-updater, github-profile-builder, gemini-visuals); SHARED REFERENCES band |
