"""Hide secrets (API keys, tokens, emails) in a screen you filmed with a phone: the screen moves, so a fixed box
won't do. For each span you give a reference time + boxes drawn on that reference frame; every frame in the span is
matched to the reference (ORB features + RANSAC homography, optionally only inside a feature mask) so the boxes follow
the screen, then they are pixelated + blurred. The output keeps the source timing, so it can replace the clip 1:1.

  python blur_track.py spans.json in.mov out.mov
  spans.json: [{"start": 25.9, "end": 30.9, "ref": 29.5, "boxes": [[420, 848, 795, 888]], "mask": null}, ...]
  Boxes / mask are pixels on a 1080x1920 frame (portrait). Needs: pip install opencv-python-headless numpy; ffmpeg.

Then VERIFY every frame (verify_blur.py): cut the readable secret out of the ORIGINAL as a template and make sure it
never matches in the output. Sampling a few frames is not enough: a camera move can make the tracker lose the screen
for a fraction of a second, and that is exactly when the secret shows.
Tip: when the secret sits in a part of the screen that moves on its own (a chat box that grows), give that span a
"mask" around that part so the tracker follows it instead of the rest of the screen.
"""
import cv2, numpy as np, subprocess, sys, json
W, H, FPS, S = 1080, 1920, 30, 0.5
spans_path, SRC, OUT = sys.argv[1:4]
SPANS = json.load(open(spans_path))
orb = cv2.ORB_create(3000); bf = cv2.BFMatcher(cv2.NORM_HAMMING)
def grab(t):
    b = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(t), '-i', SRC, '-frames:v', '1', '-vf', f'scale={W}:{H}',
                        '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'], capture_output=True).stdout
    return np.frombuffer(b, np.uint8).reshape(H, W, 3)
refs = {}
for i, sp in enumerate(SPANS):
    g = cv2.resize(cv2.cvtColor(grab(sp['ref']), cv2.COLOR_BGR2GRAY), None, fx=S, fy=S); mk = None
    if sp.get('mask'):
        x0, y0, x1, y1 = sp['mask']; mk = np.zeros_like(g); mk[int(y0 * S):int(y1 * S), int(x0 * S):int(x1 * S)] = 255
    refs[i] = orb.detectAndCompute(g, mk)
def hide(fr, poly):
    x, y, w, h = cv2.boundingRect(poly.astype(np.int32)); x, y = max(x, 0), max(y, 0); w, h = min(w, W - x), min(h, H - y)
    if w < 4 or h < 4: return
    roi = fr[y:y + h, x:x + w]
    small = cv2.resize(roi, (max(1, w // 14), max(1, h // 14)), interpolation=cv2.INTER_AREA)
    pix = cv2.GaussianBlur(cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST), (0, 0), 6)
    m = np.zeros((h, w), np.uint8); cv2.fillConvexPoly(m, (poly - [x, y]).astype(np.int32), 255); roi[m > 0] = pix[m > 0]
dec = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', SRC, '-vf', f'scale={W}:{H}', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'], stdout=subprocess.PIPE)
enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                        '-i', SRC, '-map', '0:v', '-map', '1:a?', '-c:v', 'libx264', '-crf', '16', '-pix_fmt', 'yuv420p',
                        '-c:a', 'aac', '-b:a', '192k', '-shortest', OUT], stdin=subprocess.PIPE)
i, lastH, low = 0, {}, 0
while True:
    buf = dec.stdout.read(W * H * 3)
    if len(buf) < W * H * 3: break
    t = i / FPS; i += 1
    hit = [k for k, sp in enumerate(SPANS) if sp['start'] <= t <= sp['end']]
    if hit:
        k = hit[0]; fr = np.frombuffer(buf, np.uint8).reshape(H, W, 3).copy()
        g = cv2.resize(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY), None, fx=S, fy=S); kp, de = orb.detectAndCompute(g, None)
        rk, rd = refs[k]; Hm = lastH.get(k)
        if de is not None and len(kp) > 20:
            ms = [m for m, n in (p for p in bf.knnMatch(rd, de, k=2) if len(p) == 2) if m.distance < 0.75 * n.distance]
            if len(ms) > 25:
                M, mask = cv2.findHomography(np.float32([rk[m.queryIdx].pt for m in ms]) / S, np.float32([kp[m.trainIdx].pt for m in ms]) / S, cv2.RANSAC, 4.0)
                if M is not None and mask.sum() > 15: Hm = M; lastH[k] = M
                else: low += 1
        if Hm is None: Hm = np.eye(3)
        for x0, y0, x1, y1 in SPANS[k]['boxes']:
            hide(fr, cv2.perspectiveTransform(np.float32([[[x0, y0]], [[x1, y0]], [[x1, y1]], [[x0, y1]]]), Hm).reshape(4, 2))
        buf = fr.tobytes()
    enc.stdin.write(buf)
enc.stdin.close(); enc.wait(); dec.wait(); print('done; frames with weak tracking:', low)
