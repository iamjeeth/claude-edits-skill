"""Tiny client for the Edits (IG Edits for Mac) automation server.

Usage:
    import sys; sys.path.insert(0, '<path to this folder>')
    import edits_client as e
    e.init()                      # token from $EDITS_TOKEN, else the MCP entry in ~/.claude.json
    e.call('appState')            # -> dict
    e.frames(2.8, 'out.jpg')      # save one preview frame at 2.8s
    e.wait_export()               # poll exportStatus until done

The token is never printed. If calls return HTTP 403, the token was regenerated in Edits:
re-add the server (see SKILL.md) and run again.
"""
import base64, json, os, time, urllib.request

URL = 'http://127.0.0.1:19501/mcp'
SANDBOX = os.path.expanduser('~/Library/Containers/com.burbn.basel.mac/Data/tmp/')
_sid = None
_n = [0]
_tok = None


def _token():
    """$EDITS_TOKEN, else the first MCP server in ~/.claude.json pointing at port 19501."""
    if os.environ.get('EDITS_TOKEN'):
        return os.environ['EDITS_TOKEN']
    cfg = json.load(open(os.path.expanduser('~/.claude.json')))
    pools = [cfg.get('mcpServers', {})] + [p.get('mcpServers', {}) for p in cfg.get('projects', {}).values()]
    for pool in pools:
        for srv in pool.values():
            if ':19501' in str(srv.get('url', '')):
                return srv['headers']['Authorization'].split(' ', 1)[1]
    raise SystemExit('No Edits token: set EDITS_TOKEN or add the server with claude mcp add (see SKILL.md)')


def rpc(method, params=None, notify=False):
    global _sid
    body = {'jsonrpc': '2.0', 'method': method}
    if params is not None:
        body['params'] = params
    if not notify:
        _n[0] += 1
        body['id'] = _n[0]
    h = {'Authorization': 'Bearer ' + _tok, 'Content-Type': 'application/json',
         'Accept': 'application/json, text/event-stream'}
    if _sid:
        h['Mcp-Session-Id'] = _sid
    r = urllib.request.urlopen(urllib.request.Request(URL, json.dumps(body).encode(), h), timeout=300)
    _sid = r.headers.get('Mcp-Session-Id') or _sid
    txt = r.read().decode()
    if notify:
        return None
    lines = [l[6:] if l.startswith('data: ') else l for l in txt.strip().split('\n') if l.strip()]
    return json.loads(lines[-1])


def init():
    global _tok
    _tok = _token()
    rpc('initialize', {'protocolVersion': '2025-06-18', 'capabilities': {},
                       'clientInfo': {'name': 'claude', 'version': '1'}})
    rpc('notifications/initialized', notify=True)


def call(_tool, **args):
    """Call a tool. Returns the parsed JSON result, or {'_error': ...}."""
    d = rpc('tools/call', {'name': _tool, 'arguments': args})
    if 'error' in d:
        return {'_error': d['error']}
    c = d['result'].get('content', [])
    texts = [x['text'] for x in c if x.get('type') == 'text']
    t = texts[-1] if texts else ''
    try:
        out = json.loads(t)
    except Exception:
        out = t
    if d['result'].get('isError'):
        return {'_error': out}
    return out


def ok(r):
    return isinstance(r, dict) and not r.get('_error') and r.get('ok', True)


def tools():
    return {t['name']: t for t in rpc('tools/list')['result']['tools']}


def stage(*paths, folder='claude'):
    """Copy files into the Edits sandbox (Edits can't read anywhere else). Returns new paths."""
    import shutil
    d = os.path.join(SANDBOX, folder)
    os.makedirs(d, exist_ok=True)
    out = []
    for p in paths:
        q = os.path.join(d, os.path.basename(p))
        shutil.copy2(p, q)
        out.append(q)
    return out


def frames(start, path_prefix, count=1, duration=0.1, width=540):
    """Render preview frames from the timeline and save them as JPGs. Returns file paths."""
    d = rpc('tools/call', {'name': 'previewVideo', 'arguments': dict(
        startSeconds=start, durationSeconds=duration, frameCount=count, maxWidth=width, includeClip=False)})
    files = []
    for x in d['result']['content']:
        if x['type'] == 'image':
            f = path_prefix if count == 1 else f'{path_prefix}_{len(files)}.jpg'
            open(f, 'wb').write(base64.b64decode(x['data']))
            files.append(f)
    return files


def element_start(eid):
    for x in call('elements', fields=['id', 'startTime', 'endTime'], limit=5000)['elements']:
        if x['id'] == eid:
            return x['startTime'], x['endTime']


def place_overlay(path, start, end, pop=True):
    """Full-frame transparent PNG at exact times, optional 1.08->1 scale pop. Returns element id."""
    r = call('addOverlay', path=path, startSeconds=start, x=0.5, y=0.5, scale=1)
    eid = r['id']
    st, et = element_start(eid)
    if abs(st - start) > 0.02:
        call('move', id=eid, toSeconds=start)
        st, et = element_start(eid)
    extra = (et - st) - (end - st)
    if abs(extra) > 0.01:
        call('trim', id=eid, side='right', deltaSeconds=round(extra, 3))
    if pop:
        call('setTransformKeyframe', id=eid, time=round(st + 0.001, 4), scale=1.08, x=0.5, y=0.5)
        call('setTransformKeyframe', id=eid, time=round(st + 0.3, 4), scale=1.0, x=0.5, y=0.5)
    return eid


def place_sfx(path, start, volume=1.0):
    r = call('addMedia', path=path, audioKind='soundEffect')
    eid = r['id']
    call('move', id=eid, toSeconds=start)
    call('setVolume', id=eid, volume=volume)
    return eid


def add_text(text, start, duration, x, y, size, color='#111111', font='Oswald-Regular',
             emphasis='none', emphasis_color=None, align='center'):
    """One text line, fully styled in one helper. size ~ target px / 2.8."""
    eid = call('addText', text=text, atSeconds=start, duration=duration)['id']
    call('setTextFont', id=eid, family=font)
    call('setTextStyle', id=eid, size=size, color=color, alignment=align)
    call('setTextPosition', id=eid, x=x, y=y)
    if emphasis != 'none':
        a = dict(style=emphasis)
        if emphasis_color:
            a['color'] = emphasis_color
        call('setEmphasis', id=eid, **a)
    return eid


def add_box_under(x, y, w, h, color, start, duration, radius=0.012, opacity=1.0, layer=None):
    """Rounded box (addShape). It lands on a new TOP layer; pass layer= to move it under text."""
    eid = call('addShape', x=x, y=y, width=w, height=h, color=color, cornerRadius=radius,
               opacity=opacity, startSeconds=start, duration=duration)['id']
    if layer is not None:
        call('moveToLayer', id=eid, toLayer=layer)
    return eid


def wait_export(timeout=300):
    t = time.time()
    time.sleep(2)
    while time.time() - t < timeout:
        s = call('exportStatus')
        if isinstance(s, dict) and s.get('state') in ('complete', 'failed', 'error', 'cancelled'):
            return s
        time.sleep(1)
    return {'state': 'timeout'}
