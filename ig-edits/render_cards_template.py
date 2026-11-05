"""Render HTML card states to full-frame (1080x1920) transparent PNGs for Edits overlays.

TEMPLATE: copy it, then set SRC (an HTML file whose cards are hidden `.clip` divs with ids),
OUT, and `states` (output name -> (card element id, extra CSS for that state)).
Needs Playwright (`pip install playwright`) and Google Chrome.

Why the SVG inlining: Chrome often draws logo SVGs blank or as broken icons when used as <img>.
Always look at every PNG (an ffmpeg crop grid is fastest) before placing it in Edits.
"""
import os, re, sys, time
from playwright.sync_api import sync_playwright

SRC = 'cards.html'          # your card sheet
OUT = 'cards_png/'          # output folder
states = {                  # name -> (element id, extra css)
    '01_intro': ('intro', ''),
    '02_logo': ('logo', ''),
    '03_logo_struck': ('logo', '#logo .strike{opacity:1}'),
}

base = os.path.dirname(os.path.abspath(SRC)) + '/'
src = open(SRC).read()
style = re.search(r'<style>(.*?)</style>', src, re.S).group(1)
body = re.search(r'<body[^>]*>(.*?)</body>', src, re.S).group(1)
body = re.sub(r'<script.*?</script>', '', body, flags=re.S)


def _inline(m):
    cls, f = m.group(1), m.group(2)
    svg = open(base + f).read()
    svg = re.sub(r'<\?xml[^>]*>', '', svg)
    svg = re.sub(r'<svg\b', f'<svg class="{cls}"', svg, count=1)
    for _ in range(2):
        svg = re.sub(r'(<svg[^>]*?)\s(width|height)="[^"]*"', r'\1', svg)
    return svg


body = re.sub(r'<img class="([^"]+)" src="([^"]+\.svg)">', _inline, body)
extra = ('html,body{margin:0;background:transparent;width:1080px;height:1920px;overflow:hidden}'
         ' .clip{display:none} .clip.show{display:block}')
os.makedirs(OUT, exist_ok=True)
t = time.time()
with sync_playwright() as p:
    b = p.chromium.launch(channel='chrome')
    pg = b.new_page(viewport={'width': 1080, 'height': 1920})
    for name, (cid, css) in states.items():
        html = (f'<html><head><base href="file://{base}"><style>{style}{extra}{css}</style></head>'
                f'<body>{body}<script>document.getElementById("{cid}").classList.add("show")</script></body></html>')
        pg.set_content(html, wait_until='networkidle')
        pg.evaluate('Promise.all([document.fonts.ready,...[...document.images].map(i=>i.decode().catch(()=>0))])')
        pg.wait_for_timeout(300)
        pg.screenshot(path=os.path.join(OUT, name + '.png'), omit_background=True)
    b.close()
print('rendered', len(states), 'in', round(time.time() - t, 1), 's')
