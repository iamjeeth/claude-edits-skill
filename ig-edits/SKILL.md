---
name: ig-edits
description: Use when building, rebuilding or tweaking a video inside the Instagram Edits desktop app on a Mac (bundle com.burbn.basel.mac), or when the user says "do it in Edits", "put it in Edits", "make the Edits project", "export from Edits", or asks what Edits can do. Drives Edits through its built-in local automation server (MCP, port 19501): footage, overlays/cards, text titles, SFX, captions, transcripts, preview frames, export. Covers the click fallback too. Not for posting: Edits has no post/trial/schedule tool.
---

# Instagram Edits (Mac) with Claude

Field notes from building real reels in Edits for Mac with Claude Code (Nov 2026). Edits has a hidden-in-plain-sight automation server that speaks MCP. With it, Claude can build a whole edit (cards, SFX, titles, captions, export) in about 40 seconds of machine time instead of clicking.

Files in this folder:
- `edits_client.py`: plain-HTTP Python client for the same server. Use it in the session where you just added the MCP (the `mcp__...` tools only load in a NEW session) and for batch builds. Helpers: `init()`, `call(tool, **args)`, `tools()`, `stage()`, `place_overlay()`, `place_sfx()`, `add_text()`, `add_box_under()`, `frames()`, `wait_export()`.
- `TOOLS.md`: all 274 editor tools with args, grouped by category. Read the rows you need before building.
- `render_cards_template.py`: renders HTML card states to transparent 1080x1920 PNGs for overlays (Playwright).

## 0. Setup (once)

1. Open Edits > **Settings > Automation > Enable Automation Server**. It listens on `http://127.0.0.1:19501/mcp` with a bearer token. Server off = connection refused.
2. Copy the Claude Code command from that Automation page and run it in Terminal yourself (keeps the token out of chat). It is shaped like:
   `claude mcp add --transport http --scope user <name> http://127.0.0.1:19501/mcp --header "Authorization: Bearer <token>"`
3. Start a new Claude Code session: the tools appear as `mcp__<name>__*`.
4. HTTP 403 later = the token was regenerated. `claude mcp remove <name> -s user`, re-add with the new command.
5. `edits_client.py` reads the token from `$EDITS_TOKEN`, else from the MCP entry in `~/.claude.json`. It never prints it.

## 1. How the server behaves

- **The tool list follows the screen.** About 30 tools on the home screen, 274 in the editor. `appState` says which screen. Open a project first (`projects`, `openProject`, `newProject`).
- **No public docs exist.** Tool descriptions are the manual (`TOOLS.md`). `getCapabilities` returns conventions, catalogs and recipes. MCP resources: app-state, clips, elements, overview.
- **The app can bounce to home mid-run** (tools then say "not in current manifest"). Check `appState`, `openProject`, continue. Element ids survive.

## 2. Rules that bite

- **Sandbox.** Edits only reads files inside `~/Library/Containers/com.burbn.basel.mac/Data/tmp/` (or files the user picked in its UI). Copy every asset there first (`stage()`), export there too, then copy the export out. Error "Sandbox bookmark unavailable" = you forgot.
- **Coordinates.** Canvas normalized 0-1, origin top-left, x/y = element CENTRE. Time in seconds on the timeline. Colours `#RRGGBB(AA)`.
- **Frame snapping.** Start times snap to frames (30fps). Keyframe times must be >= the element's real startTime: read it back with `elements` and use start + 0.001.
- **Python client gotcha.** Never name a client function param `name`; tool args like `name=` must pass through `**args`.
- **Check with frames, not screenshots.** `previewVideo` returns rendered frames as image blocks (`frames()` saves them as JPGs). Full-screen screenshots of the Edits preview go stale.

## 3. Building blocks (fastest path)

| Job | Tool(s) | Notes |
|---|---|---|
| Footage on main track | `addMedia(path)` | Becomes the magnetic video track. |
| Card / asset overlay | `addOverlay(path, startSeconds, x, y, scale)` | Default length 3s, then `trim(id, side='right', deltaSeconds)`. Full-frame transparent PNG + x=.5, y=.5, scale=1 = exactly the designed position. `place_overlay()` does all of it. |
| Swap an asset | `replaceElementMedia(id, path)` | Keeps timing and keyframes. |
| Entrance pop | `setTransformKeyframe(id, time, scale, x, y)` x2 | 1.08 to 1.0 over 0.3s. No opacity/blur keyframes via MCP (only static `setOpacity`). |
| Move / split / trim | `move`, `splitAt(id, times)`, `trim` | `split` uses the playhead. |
| SFX file | `addMedia(path, audioKind='soundEffect')` + `move` + `setVolume` | Volume is linear 0-10 (1 = 0 dB). `place_sfx()`. Library SFX: `searchSoundEffects` / `addSoundEffect`. |
| Text line | `addText` + `setTextFont` + `setTextStyle` + `setTextPosition` (+ `setEmphasis`) | `add_text()` does it in one go. |
| Box behind text | `addShape(x, y, width, height, color, cornerRadius, opacity, ...)` then `moveToLayer` under the text | Shapes land on a new TOP layer. `tracks` shows layer order. |
| Restyle many texts | `applyTextPreset(name, ids="a,b,c")` | One call. Save a house style in the Text panel first. |
| Brand font | `importAccountFont(path)` | Built-in catalog is thin (Oswald-Regular, no Medium). |
| Captions | `generateCaptions`, `setCaptionStyle`, `editCaption`, `setCaptionHighlights` | About 20s for a 22s clip. |
| Word timings | `transcribeClip(id)` | Word-level start/end, WhisperX-like. Spot-check once before relying on it. |
| Silence cuts | `transcriptJumpCut` | With the transcriptId from `transcribeClip`. |
| Export | `setExportSettings(dynamicRange='SDR', resolution='1080x1920', resolutionType='HD', aspectRatio='nineBySixteen', quality='High', frameRate=30)` then `export(path)` + `wait_export()` | resolutionType, aspectRatio AND quality are all required or export silently never starts. resolution is "WxH". Output is HEVC SDR; frameRate 30 was ignored (came out 60fps). About 10s for 22s. Default without settings = HEVC 1440x2560 60fps. |

## 4. Text: measure once, build once

- No line height and no single multi-line box via MCP. Emphasis styles: `none`, `outline`, `invertedOutline`, `backgroundPill` (one pill PER LINE), `invertedBackgroundPill`. Alpha in the pill colour is ignored.
- For a "two lines in one box" title: measure the target frame in px first, convert to normalized (px / 1080, px / 1920), then 1 `addShape` box (+ optional translucent bar) moved under the text, and one text element per line with emphasis `none`.
- Text size is about target px / 2.8 (55px -> size 20; 40px -> 13.5).
- Don't trial-and-error sizes. Measure, build, one preview to confirm.

## 5. Cards and logos

Edits can't draw logo cards. Render each card state as a transparent full-frame 1080x1920 PNG (`render_cards_template.py`), then `place_overlay()` each. Check EVERY card image before placing (make a crop grid with ffmpeg and look at it): logo SVGs often render blank or broken as `<img>`, so inline them as `<svg>`.

Alpha formats that keep transparency in Edits: PNG, ProRes 4444 MOV, HEVC-with-alpha MOV (incl. 50% soft edges). Library thumbnails of alpha MOVs show a solid colour: ignore that. Prefer ProRes 4444 (HEVC soft edges look slightly paler).

## 6. What Edits can't do (via MCP)

- No posting, trial reel or scheduling. The UI share sheet (Export > Share to Instagram) has a Trial reel toggle and "Trial settings: Manual", no schedule. Post with your own pipeline (Graph API etc.).
- No fade/blur animation on overlays, no text line height, no single box behind multi-line text.

## 7. Click fallback (computer use), only if the server is off

- Background `app_*` clicks work for panels, buttons, menus (`app_menu`), and the source-preview "+" button.
- The Import Media file picker (separate process) and anything on the timeline canvas need full-screen control. In the picker: cmd+shift+g, type the path, Import.
- Thumbnail "+" INSERTS into the main track (pushes video). For an overlay: slow drag (mouse down, 0.6s hold, about 8 small moves, 0.8s hold, release) from the main track up to the empty row above. Fast drags are ignored.
- Audio "+" lands on its own track at 0:00, not at the playhead.
- Split = click the ruler to set the playhead, then Timeline > Split (the toolbar split icon is a mode). Precise playhead moves: Timeline > Forward/Back 10 frames.
- Edits can drop out of `app_list_windows` when Stage Manager moves it. Use `app_screenshot` / `app_zoom` of the window, not full-screen shots.

## 8. Workflow that works

1. Human cuts the takes.
2. Claude plans and renders assets (cards, PNGs, SFX picks), stages them in the sandbox.
3. Claude builds the whole edit in an Edits project with this skill, then checks it with `previewVideo` frames.
4. Human opens the project and tweaks live in Edits (no re-render loop), approves.
5. Claude exports SDR 1080x1920, runs upload checks, posts via the usual pipeline.

Timing from one real rebuild: 12 cards 11s, 13 SFX 9s, text 4s, export about 10s.
