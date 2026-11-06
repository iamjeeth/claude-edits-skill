# Instagram Edits + Claude Code: automate video editing on Mac with MCP

**Edit Instagram Reels with AI.** This is a Claude Code skill that lets Claude edit videos inside the **Instagram Edits** desktop app for Mac: add overlays, logo cards, sound effects, text titles and captions, get word-level transcripts, preview frames and export, all through the app's built-in MCP automation server.

A full reel rebuild (12 overlay cards, 13 sound effects, a two-line title, export) took about **40 seconds** of machine time instead of an hour of clicking.

## Contents

- [What this skill does](#what-this-skill-does)
- [How to connect Claude to Instagram Edits](#how-to-connect-claude-to-instagram-edits)
- [Install the skill](#install-the-skill)
- [What's in the repo](#whats-in-the-repo)
- [Limits of the Edits automation server](#limits-of-the-edits-automation-server)
- [FAQ](#faq)

## What this skill does

Instagram Edits for Mac (bundle `com.burbn.basel.mac`) ships a local automation server under **Settings > Automation**. It speaks the Model Context Protocol (MCP) and exposes 274 editor tools, but Meta publishes no docs for it. This repo is the field manual, written from real reel builds:

- **Overlays and cards** at exact timestamps, with scale-pop entrances
- **Sound effects** placed on the beat, volume set per clip
- **Text titles** as one element styled through the Text panel, with measured, even spacing between stacked lines
- **Auto captions** with one style preset for the whole video
- **Word-level transcripts** (like WhisperX) and silence jump cuts
- **Preview frames** so Claude checks its own edit before you look
- **Export** settings that actually work (SDR, 1080x1920, HEVC)
- **Hide API keys and tokens** in hand-filmed screen recordings (tracked blur) and verify every frame
- **Post** through the Edits share sheet: trial reel, location and cover
- A **click fallback** with computer use for when the server is off

## How to connect Claude to Instagram Edits

1. Open Edits on your Mac and go to **Settings > Automation > Enable Automation Server**. It runs on `http://127.0.0.1:19501/mcp`.
2. Copy the Claude Code command shown on that page and run it in Terminal. It looks like:
   ```bash
   claude mcp add --transport http --scope user edits http://127.0.0.1:19501/mcp --header "Authorization: Bearer <token>"
   ```
3. Start a new Claude Code session. The Edits tools load as `mcp__edits__*`.

## Install the skill

```bash
git clone https://github.com/iamjeeth/claude-edits-skill.git
```

```bash
cp -r claude-edits-skill/ig-edits ~/.claude/skills/
```

Then ask Claude: "build this reel in Edits". Quick connection test with the Python client:

```bash
cd ~/.claude/skills/ig-edits && python3 -c "import edits_client as e; e.init(); print(e.call('appState'))"
```

## What's in the repo

| File | What it is |
|---|---|
| [`ig-edits/SKILL.md`](ig-edits/SKILL.md) | The skill: setup, sandbox and timing rules, fastest tool per job, text recipe, limits, workflow |
| [`ig-edits/TOOLS.md`](ig-edits/TOOLS.md) | All 274 Instagram Edits automation tools with arguments, grouped by category |
| [`ig-edits/edits_client.py`](ig-edits/edits_client.py) | Python MCP client with helpers: `place_overlay`, `place_sfx`, `add_text`, `frames`, `wait_export` |
| [`ig-edits/render_cards_template.py`](ig-edits/render_cards_template.py) | Render HTML cards to transparent 1080x1920 PNGs for video overlays |
| [`ig-edits/spacing.py`](ig-edits/spacing.py) | Measure stacked text in a rendered frame and equalise the vertical gaps |
| [`ig-edits/blur_track.py`](ig-edits/blur_track.py) | Pixelate secrets that move with a hand-filmed screen (ORB + homography tracking) |
| [`ig-edits/verify_blur.py`](ig-edits/verify_blur.py) | Check every frame of the blurred clip for the secret with template matching |

## Limits of the Edits automation server

- Edits only reads files inside its sandbox (`~/Library/Containers/com.burbn.basel.mac/Data/tmp/`). The client's `stage()` copies assets there.
- No posting, trial reels or scheduling to Instagram through the server (the UI share sheet can post, see SKILL.md).
- Licensed music is capped at 60 seconds on export/share; longer videos lose it unless the song is trimmed.
- No opacity or blur keyframes, no text line height, no single box behind multi-line text.
- Export needs `resolutionType`, `aspectRatio` and `quality` set together, or it silently never starts.

## FAQ

**Does Instagram Edits have an API?**
Not a public one. The Mac app has a local MCP automation server (Settings > Automation) with 274 tools. This repo documents it.

**Can Claude edit Instagram Reels?**
Yes. With this skill, Claude Code drives Instagram Edits on your Mac: footage, overlays, sound effects, text, captions and export.

**Can Claude post or schedule reels from Edits?**
Not through the automation server. The Edits share sheet (Export > Share to Instagram) can post, including as a trial reel with a location and a custom cover; there is no scheduling. SKILL.md has the steps.

**Does it work with other AI agents?**
Any MCP client can connect to the server. The skill format is written for Claude Code; `edits_client.py` works from any Python script.

**Does it work on iPhone?**
No. The automation server is in Edits for Mac only.

---

Unofficial. Not affiliated with Meta or Instagram. Tested on Instagram Edits for Mac, November 2026. The tool list can change with app updates; see `TOOLS.md` to re-dump it.

## License

MIT
