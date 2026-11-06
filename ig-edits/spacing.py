"""Measured vertical spacing for stacked text/stickers in Edits (keeps stacked text evenly spaced by measuring rendered ink, not guessing).

    import sys; sys.path.insert(0, '<path to this ig-edits folder>')
    import edits_client as e, spacing
    e.init()
    spacing.even_stack([lead_id, big_id, tag_id], t=1.0, gap=0.012)   # top-to-bottom order, gap = fraction of frame height

How: render the frame, hide one element at a time (opacity 0) and diff, so each element's REAL ink box is measured
(fonts have different ascenders/descenders; pills add padding). Then the first element stays put and every next one is
moved so the gap between ink boxes equals `gap`. Re-measures and returns the final gaps (fraction of height) to verify.
Needs PIL + numpy: run with any python that has them (e.g. a venv with pillow + numpy).
"""
import base64, io, json
import edits_client as e

W = 540  # render width for measuring

def _frame(t):
    d = e.rpc('tools/call', {'name': 'previewVideo', 'arguments': dict(startSeconds=t, durationSeconds=0.1, frameCount=1, maxWidth=W, includeClip=False)})
    from PIL import Image
    import numpy as np
    for x in d['result']['content']:
        if x['type'] == 'image':
            return np.asarray(Image.open(io.BytesIO(base64.b64decode(x['data']))).convert('RGB')).astype(int)

def _hide(eid, on):
    r = e.call('setTextVisibility', id=eid, visible=not on)
    if isinstance(r, dict) and r.get('_error'):
        e.call('setOpacity', id=eid, opacity=0.0 if on else 1.0)

def ink_boxes(ids, t):
    """{id: (top, bottom, left, right)} as fractions of the frame, measured by hide-and-diff."""
    import numpy as np
    base = _frame(t); H = base.shape[0]; out = {}
    for eid in ids:
        _hide(eid, True); f = _frame(t); _hide(eid, False)
        diff = np.abs(base - f).sum(axis=2) > 40
        ys, xs = np.nonzero(diff)
        if len(ys): out[eid] = (ys.min() / H, ys.max() / H, xs.min() / base.shape[1], xs.max() / base.shape[1])
    return out

def shift_y(eid, delta, x=0.5):
    """Move an element down by delta (fraction of height). Keyframed elements (pops) keep their position IN the
    keyframes, so every keyframe's y is shifted; otherwise the base text position is moved."""
    kfs = e.call('getTransformKeyframes', id=eid).get('keyframes', [])
    if kfs:
        for k in kfs:
            e.call('setTransformKeyframe', id=eid, time=k['time'], scale=k['scale'], x=k['x'], y=round(k['y'] + delta, 4))
    else:
        el = e.call('getElement', id=eid); y = el.get('positionY', el.get('y', 0.5))
        e.call('setTextPosition', id=eid, x=x, y=round(y + delta, 4))

def even_stack(ids, t, gap=0.012, x=0.5):
    """Move ids[1:] so the ink gap between consecutive elements equals `gap` (fraction of frame height)."""
    for _ in range(2):
        b = ink_boxes(ids, t)
        for prev, cur in zip(ids, ids[1:]):
            want_top = b[prev][1] + gap
            delta = want_top - b[cur][0]
            if abs(delta) > 0.001:
                shift_y(cur, delta, x)
                b = ink_boxes(ids, t)
    b = ink_boxes(ids, t)
    return [round(b[c][0] - b[p][1], 4) for p, c in zip(ids, ids[1:])]
