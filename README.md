# Claude + Instagram Edits (Mac)

A Claude Code skill for building videos inside the **Instagram Edits** desktop app on macOS.

Edits for Mac ships a local automation server (Settings > Automation) that speaks MCP. Once Claude Code is connected to it, Claude can drive the editor directly: place footage, overlays and logo cards at exact times, add SFX, build titles, generate captions, get word-level transcripts, render preview frames to check its own work, and export. A full reel rebuild (12 cards, 13 SFX, titles, export) took about 40 seconds of machine time.

This repo is the field manual: setup, the sandbox and timing rules that break things, the fastest tool for each job, a Python client, a 274-tool reference, and the click fallback for when the server is off.

## What's inside

| File | What |
|---|---|
| [`ig-edits/SKILL.md`](ig-edits/SKILL.md) | The skill: setup, rules, building blocks, text recipe, limits, workflow |
| [`ig-edits/TOOLS.md`](ig-edits/TOOLS.md) | Every editor tool with its args, grouped by category (there are no public docs) |
| [`ig-edits/edits_client.py`](ig-edits/edits_client.py) | Plain-HTTP client with helpers (`place_overlay`, `place_sfx`, `add_text`, `frames`, `wait_export`) |
| [`ig-edits/render_cards_template.py`](ig-edits/render_cards_template.py) | Render HTML cards to transparent 1080x1920 PNGs for overlays |

## Install

```bash
git clone https://github.com/iamjeeth/claude-edits-skill.git
cp -r claude-edits-skill/ig-edits ~/.claude/skills/
```

Then in Edits: **Settings > Automation > Enable Automation Server**, copy the Claude Code command shown there, run it in Terminal, and start a new Claude Code session. Ask Claude to "build this in Edits".

## Quick test (Python client)

```bash
cd ~/.claude/skills/ig-edits && python3 -c "import edits_client as e; e.init(); print(e.call('appState'))"
```

## Limits worth knowing

- Edits can only read files inside its sandbox (`~/Library/Containers/com.burbn.basel.mac/Data/tmp/`). The client's `stage()` copies them there.
- No posting, trial reel or scheduling through the server.
- No opacity/blur keyframes, no text line height.

Unofficial. Not affiliated with Meta or Instagram. Tested on Edits for Mac, November 2026; the tool list can change with app updates (re-dump it, see `TOOLS.md`).

## License

MIT
