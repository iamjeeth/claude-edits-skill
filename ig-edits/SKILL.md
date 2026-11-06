---
name: ig-edits
description: Use when building, rebuilding or tweaking a video inside the Instagram Edits desktop app on a Mac (bundle com.burbn.basel.mac), or when the user says "do it in Edits", "put it in Edits", "make the Edits project", "export from Edits", or asks what Edits can do. Drives Edits through its built-in local automation server (MCP, port 19501): footage, overlays/cards, text titles, SFX, captions, transcripts, preview frames, export. Covers the click fallback, hiding secrets in screen recordings, and posting through the UI share sheet (trial reel, location, cover). No MCP posting or scheduling.
---

# Instagram Edits (Mac) with Claude

Field notes from building real reels in Edits for Mac with Claude Code (Nov 2026). Edits has a hidden-in-plain-sight automation server that speaks MCP. With it, Claude can build a whole edit (cards, SFX, titles, captions, export) in about 40 seconds of machine time instead of clicking.

Files in this folder:
- `edits_client.py`: plain-HTTP Python client for the same server. Use it in the session where you just added the MCP (the `mcp__...` tools only load in a NEW session) and for batch builds. Helpers: `init()`, `call(tool, **args)`, `tools()`, `stage()`, `place_overlay()`, `place_sfx()`, `add_text()`, `add_box_under()`, `frames()`, `wait_export()`.
- `TOOLS.md`: all 274 editor tools with args, grouped by category. Read the rows you need before building.
- `render_cards_template.py`: renders HTML card states to transparent 1080x1920 PNGs for overlays (Playwright).
- `spacing.py`: `even_stack(ids, t, gap)` measures the real ink box of each stacked text element (hide-and-diff render) and moves them so every vertical gap is identical. Needs pillow + numpy.
- `blur_track.py` + `verify_blur.py`: hide API keys / tokens in a hand-filmed screen recording (tracked pixelation) and prove every frame is clean (section 12).

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
| Swap an asset | `replaceElementMedia(id, path)` | Keeps the timeline length, BUT: on a video clip it resets the in-point to 0 (re-slip with `slipClip`) and scrambles transform keyframe times (remove them all, re-apply); on a still PNG overlay it loses its length (shows ~1 frame): delete and `addOverlay` again instead. |
| Entrance pop | `setTransformKeyframe(id, time, scale, x, y)` x2 | 1.08 to 1.0 over 0.3s. No opacity/blur keyframes via MCP (only static `setOpacity`). |
| Move / split / trim | `move`, `splitAt(id, times)`, `trim` | `split` uses the playhead. |
| SFX file | `addMedia(path, audioKind='soundEffect')` + `move` + `setVolume` | Volume is linear 0-10 (1 = 0 dB). `place_sfx()`. Library SFX: `searchSoundEffects` / `addSoundEffect`. |
| Text / title | ONE `addText` (use `\n` for line breaks) + `setTextFont` + `setTextStyle` + `setTextPosition` + `setEmphasis` | Don't build titles as a shape box + one text per line; style one element (section 4). |
| Background behind text | `setEmphasis(style='backgroundPill', color=...)` on the text itself | `addShape` is for non-text shapes (rules, bars); shapes land on a new TOP layer, `moveToLayer` to reorder. |
| Restyle many texts | `applyTextPreset(name, ids="a,b,c")` | One call. Save a house style in the Text panel first. |
| Brand font | `importAccountFont(path)` | Built-in catalog is thin (Oswald-Regular, no Medium). |
| Captions (default) | `generateCaptions(language='en')` then ONE `setCaptionStyle(style=...)` for all; `captions()` lists them; `editCaption(id, text)` fixes misheard words | About 20s for a 70s reel. 73 presets (`listCaptionStyles`). One caption track beats hundreds of per-word text elements: restyling is one call. Check every phrase for misheard brand names (e.g. 'Claude' -> 'cloud'/'clot'). |
| Word timings | `transcribeClip(id)` | Word-level start/end, WhisperX-like. Spot-check once before relying on it. |
| Silence cuts | `transcriptJumpCut` | With the transcriptId from `transcribeClip`. |
| Punch-in / zoom on a clip | `setTransformKeyframe(id, time, scale=s, x=cx, y=cy)` x2 | cx = 0.5 - s*(Px-0.5) (P = focus point in the source frame, 0-1), clamped to 0.5 +/- (s-1)/2. Start + end keyframe with s -> s*1.04 = slow push. Angled screen shots need a smaller scale or the text gets cut. |
| Export | `setExportSettings(dynamicRange='SDR', resolution='1080x1920', resolutionType='HD', aspectRatio='nineBySixteen', quality='High', frameRate=30)` then `export(path)` + `wait_export()` | resolutionType, aspectRatio AND quality are all required or export silently never starts. resolution is "WxH". Output is HEVC SDR; frameRate 30 was ignored (came out 60fps). About 10s for 22s. Default without settings = HEVC 1440x2560 60fps. Exports through the automation server do NOT carry licensed music (and the audio can come out identical to an earlier export), so you can't verify the music mix from them: check it by playing in Edits, or export from the UI. |

## 4. Text: one element, styled through the Text panel

- Make ONE text element per title (`addText` with `\n`), then style it. Stacking a shape box + one text per line is the slow route and drifts out of alignment.
- **Fonts:** `setTextFont(family=<PostScript id>)`. Search ids with `listCatalog(kind='font', query=...)`; `listFonts` only returns the first 50. Display names mislead: 'Classic' = `IGUIBetav9-Heavy` (sans), 'Editor' = a typewriter face. Instagram's serif is `InstagramSerif-Regular-Test`; `InstrumentSerif-Regular` / `-Italic` are also available.
- **Background:** `setEmphasis` styles are none, outline, invertedOutline, backgroundPill, invertedBackgroundPill. backgroundPill draws one rounded pill PER LINE (two lines = a stepped block, never one square box). Padding a line with spaces/NBSP to equalise pill widths breaks emoji and alignment: don't.
- **Text panel fields over MCP:** `selectById(text_id)` -> `selectTool('textStyle')` -> `valueFields()`. With a background accent the order is: font size, line height, letter spacing, background padding, background opacity, scale %, X, Y, rotate, opacity. `editValueField(match=<field's current text>, text=<new>)` works for INTEGER fields (size, opacity, X, Y). It fails for decimal fields (line height 1.0, letter spacing 0.0, padding 1.0): "1.0" is parsed as "1" and matches nothing. Drag those sliders with background computer use instead and read `valueFields` back.
- **Pop-in keyframes pin position:** after a `setTransformKeyframe` pop, the element's y lives in the keyframes; `setTextPosition` / `getTransform` no longer reflect it. Move it by re-setting every keyframe's y (`spacing.shift_y` does this).
- **Vertical spacing between stacked text:** measure, never eyeball. `spacing.even_stack([ids top->bottom], t, gap=0.012)` renders, measures each element's real ink box and equalises the gaps. Re-run after any size, text or emoji change (ascenders, descenders, emoji and pill padding all change the ink box).
- **Big words wrap:** a text box has a max width; above it Edits wraps mid-word ("claud/e"). Size down until one line.
- Text size is about target px / 2.8. Measure once, build, one preview frame to confirm.
- **Captions on screen recordings:** move them lower (y ~0.78, still inside the safe zone) while a screen is shown so they don't cover the UI being explained.

## 5. Cards and logos

Edits can't draw logo cards. Render each card state as a transparent full-frame 1080x1920 PNG (`render_cards_template.py`), then `place_overlay()` each. Check EVERY card image before placing (make a crop grid with ffmpeg and look at it): logo SVGs often render blank or broken as `<img>`, so inline them as `<svg>`.

Alpha formats that keep transparency in Edits: PNG, ProRes 4444 MOV, HEVC-with-alpha MOV (incl. 50% soft edges). Library thumbnails of alpha MOVs show a solid colour: ignore that. Prefer ProRes 4444 (HEVC soft edges look slightly paler).

## 6. What Edits can't do (via MCP)

- No posting, trial reel or scheduling via MCP. The UI share sheet does post (section 13), without scheduling.
- No fade/blur animation on overlays. Decimal Text-panel fields (line height, letter spacing, background padding) need a slider drag. backgroundPill is per line, so no single square box behind multi-line text.

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

## 9. Timeline gotchas

- **`elements` returns 200 rows per page by default.** Projects with many captions/stickers go past that silently: pass `limit=5000` (the client's `element_start` does).
- **Deleting a main-track clip ripples everything after it** (overlays, captions, SFX, the music end). Don't shift them again by hand; read positions back.
- **`setSpeed` on a main clip ripples later items and re-times items that start inside it** (captions scale, spanning overlays and music stretch).
- **Lengthening a main clip with `trim` ripples later items, but items that start inside it keep their end time** (extend titles/stickers yourself).
- **Variants of one edit:** `duplicateProject(id)` (home screen), rename, open, then swap only the part that differs. Swapping a hook clip: `replaceElementMedia` -> `slipClip` to the new in-point -> `setSpeed` -> `trim` to the new out-point -> clear and re-add its keyframes.
- **De-duplicating by (text, start)** can hit a caption and a title line that share a word and a start time. Track ids instead.
- `trim` on a TEXT element can stretch instead of shorten: read `elements` back after trimming.

## 10. Audio and music

- **Licensed music is capped at 60 seconds for export/share.** Over that, Edits asks "Save without music?" and drops it. Trim the song to <= 59.5s (+ a 2s fade-out) before exporting a longer video.
- `addSongToComposition(audioAssetId=...)` (not `track=`). Tracks carry `highlights` (seconds): start on one with trim(right, -N) -> trim(left, +N) -> move to 0. `licensedMusicStatus` shows availability. The library has no mood/genre metadata: pick by artist + title, not by searching mood words.
- Bed under a talking video: `setSound(volumeDb=-23 to -31)`, `setFade`, `setDucking(behavior='video', level=0.5)`. Library SFX (`searchSoundEffects`, `addSoundEffect`) come in loud: start them around volume 0.3-0.5.
- Per-clip loudness: measure each kept span (ffmpeg ebur128 on the source audio) and set `setSound(volumeDb=target-measured)` so takes match; measure very short spans (< 1s) over a wider window. `setSound(reduceNoise=60)` on every speech clip.
- `sampleOutputLevel` while playing is too noisy to verify small level changes.

## 11. Check the cut with a transcript

1. Export a low-res check file (`setExportSettings(... resolution='720x1280', resolutionType='720p', quality='Low' ...)`).
2. Transcribe it with word timings (WhisperX or `transcribeClip`).
3. List gaps between words > 0.35s and repeated words ("different, different").
4. Map each back to the source clip and split/trim it out. Repeat once to confirm.
WhisperX word lists are also the best source for one-word or chunked captions, but prefer the native caption track (section 3).

## 12. Hiding secrets in screen recordings

Hand-filmed screens move, so a static blur box leaks. Use `blur_track.py`: per span, a reference frame + boxes; each frame is matched to the reference with ORB features + a RANSAC homography so the boxes follow the screen, then pixelated. When the secret sits in a part that moves on its own (a chat input that grows when you paste), give that span a feature `mask` around it. Then run `verify_blur.py` on EVERY frame (template = the readable secret cut from the original): it must match the original and never exceed ~0.6 on the blurred file. Spot checks miss the 0.3s where tracking slips. Swap the result in with `replaceElementMedia` and remember section 3's keyframe/in-point caveats.

## 13. Posting from the share sheet (UI)

- Export (toolbar resolution button: check SDR, FHD, 30) -> "Ready to share" -> Share to Instagram opens a separate "Share to Instagram" window. Exports also land in `~/Movies/Edits/Exports/`.
- In that window: caption text area (compare the character counter with your text length), Add location (search, pick an entry), Trial reel toggle ("Trial settings: Manual" appears when on; Audience greys out), Share. "Back" from the location panel can error but the panel still returns; scroll to reach the Trial toggle.
- Cover: "Edit cover" -> drag the strip handle (handle centre maps linearly to time along the strip; check the preview and nudge a few px), or "Import" an image. The Import file picker needs full-screen control; background double-clicks there are unreliable. Floating overlay windows from other apps can block screen clicks.
- Upload + "Waiting for processing" takes about 1-1.5 min for a 70s reel. Trials posted this way may not appear in the Graph API media list.

## 14. Covers made programmatically

Edits caches its remote fonts on disk (`~/Library/Containers/com.burbn.basel.mac/Data/Library/Caches/com.burbn.basel.mac.ig_remote_assets_disk_cache/`, hashed file names; identify them with PIL `ImageFont.truetype(f).getname()`). Copy the one your title uses so a Pillow/HTML cover matches the video's title type exactly. Cut the subject out of an HD photo (`npx hyperframes remove-background in.png -o out.png`), keep the title and face inside the 3:4 profile-grid crop (y 240-1680 of 1920), and measure stacked-text gaps the same way as section 4. Colour emoji in Pillow: Apple Color Emoji at size 160 with `embedded_color=True`, then scale.

## 15. Defaults that work for talking-head reels

- **Captions: one preset for the whole video.** `generateCaptions` + one `setCaptionStyle`, one text colour, fix misheard words with `editCaption`. Don't build captions as per-word text elements or colour individual keywords: hundreds of elements, slow to restyle, and the extra colours rarely help.
- **Title only for the first 10-15 seconds.** Show the title through the hook, then end it (at a sentence break, or where a card or cutaway takes the top of the frame). A title left on for the whole reel is distracting.
- **Pick music by vibe, not by keyword.** Turn the description ("new beginnings, exciting", "news-y") into a sound brief: feeling, energy/tempo, how it builds, texture, instrumental or not. Then pick well-known tracks that sound like that and search the library by artist + title. Searching the description words returns songs with that TITLE, not that feel. Under a voice, prefer instrumental or mostly-instrumental tracks.
- **Volume levels that sit under a voice:**
  | Layer | Setting |
  |---|---|
  | Music bed | `setSound(volumeDb=-23)` as a start, down to about -31 dB if it still competes; `setDucking(behavior='video', level=0.5)`; fade in 0.3s, out 1-2s |
  | Whoosh / riser | `setVolume` about 0.3 (full volume is too loud) |
  | Click / pop | about 0.5 |
  | Shimmer / sparkle | about 0.35 |
  | Speech clips | `setSound(reduceNoise=60)`, each take levelled to the same loudness (section 10) |
