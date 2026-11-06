"""Check EVERY frame of the blurred spans for the secret (multi-scale template matching). Run it on the original too:
it should match there (proves the template works) and never above ~0.6 on the blurred file.
  python verify_blur.py original.mov blurred.mov checks.json
  checks.json: [{"start": 104.5, "end": 106.2, "template_at": 105.75, "box": [470, 1280, 900, 1302]}, ...]
  box = x0, y0, x1, y1 of the READABLE secret on a 1080x1920 frame of the original at template_at."""
import cv2, numpy as np, subprocess, sys, json
W, H = 1080, 1920
ORIG, BLUR, CHK = sys.argv[1:4]
def frames(src, a, b):
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-ss', str(a), '-to', str(b), '-i', src, '-vf', f'scale={W}:{H}', '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], stdout=subprocess.PIPE)
    n = 0
    while True:
        buf = p.stdout.read(W * H)
        if len(buf) < W * H: break
        yield a + n / 30, np.frombuffer(buf, np.uint8).reshape(H, W); n += 1
    p.stdout.close(); p.wait()
def score(f, tpl):
    return max(float(cv2.matchTemplate(f, cv2.resize(tpl, None, fx=s, fy=s), cv2.TM_CCOEFF_NORMED).max()) for s in (0.85, 0.92, 1.0, 1.08, 1.16))
for c in json.load(open(CHK)):
    x0, y0, x1, y1 = c['box']; tpl = next(frames(ORIG, c['template_at'], c['template_at'] + 0.04))[1][y0:y1, x0:x1]
    for src in (ORIG, BLUR):
        sc = [(round(t, 2), score(f, tpl)) for t, f in frames(src, c['start'], c['end'])]
        bad = [x for x in sc if x[1] > 0.6]
        print(src, c['start'], c['end'], 'max', round(max(s for _, s in sc), 2), 'frames > 0.6:', len(bad), bad[:5])
