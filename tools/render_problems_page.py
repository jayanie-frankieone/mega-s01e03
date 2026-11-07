# Renders src/routes/kb/incidents/4471/problems/+page.svx the way the runbook layout and
# ProblemTable/RenderStamp would, from the kb data. Written for this repo; runs none of the kb's code.
import json, glob, re, sys, html, datetime
kb = sys.argv[1]
rows = json.load(open(kb + '/src/lib/data/reports-4471.json'))
notes = json.load(open(kb + '/src/lib/data/desk-notes.json'))
T = {json.load(open(f))['handle']: json.load(open(f)) for f in glob.glob(kb + '/src/lib/data/tenants/*.json')}
u = {}
for r in rows: u[r['id']] = r
merged = [r for r in u.values() if r['mergedInto'] == 4471]
DAY_FIRST = {'de-DE','es-ES','en-GB','nl-NL','cs-CZ','it-IT','fr-FR','pl-PL','pt-PT','da-DK','en-IE'}  # checked with Intl
def problem(r):
    if r['id'] in notes['oneDayMove']: return 'one-day'
    t = T.get(r['tenant'])
    if not t or t['locale'] not in DAY_FIRST: return 'unplaced'
    return 'hint' if r['channel'] == 'form' and t['form'] == 'booking-v3' else 'parser'
TEXT = {'parser': 'Shared parser reads day-first dates month first', 'hint': 'booking-v3 form hint says MM/DD, the form reads day first',
        'one-day': 'Date moves by one day across time zones', 'unplaced': 'No tenant on file'}
ISSUE = {'parser': 1, 'hint': 2, 'one-day': 3}
STATE = {'parser': 'fixed', 'hint': "won't fix"}  # engineering update on #4471, closed 5 October
groups = {}
for r in merged: groups.setdefault(problem(r), []).append(r)
def desk_cause(r):  # the desk's CauseTable view: one-day moves stay under their tenant's cause
    t = T.get(r['tenant'])
    if not t or t['locale'] not in DAY_FIRST: return 'unplaced'
    return 'hint' if r['channel'] == 'form' and t['form'] == 'booking-v3' else 'parser'
def desk_count(p, rs):
    if p == 'one-day': return len(rs), 0
    here = [r for r in merged if desk_cause(r) == p]
    return len(here), sum(1 for r in here if r['id'] in notes['oneDayMove'])
trs = []
for p, rs in sorted(groups.items(), key=lambda x: -desk_count(x[0], x[1])[0]):
    dc, also = desk_count(p, rs)
    rs = rs if p == 'one-day' else [r for r in merged if desk_cause(r) == p]  # every column counts the same reports
    count = f'{dc}<br><span class="what">incl. {also} one-day</span>' if also else f'{dc}'
    d = sorted(r['receivedAt'][:10] for r in rs)
    tags = {}
    for r in rs: tags[r['meta']['intakeTag']] = tags.get(r['meta']['intakeTag'], 0) + 1
    tg = ' · '.join(f'{k} ×{v}' for k, v in sorted(tags.items(), key=lambda x: -x[1]))
    n = ISSUE.get(p)
    link = f'<a href="https://github.com/jayanie-frankieone/mega-s01e03/issues/{n}">#{n}</a>' if n else '<span class="none">no ticket</span>'
    trs.append(f'<tr><td><code>{p}</code><br><span class="what">{html.escape(TEXT[p])}</span></td><td>{count}</td><td>{len({r["tenant"] for r in rs})}</td><td>{d[0]} → {d[-1]}</td><td class="tags">{tg}</td><td>{html.escape(STATE[p]) if p in STATE else '<span class="none">open</span>'}</td><td>{link}</td></tr>')
def fnv(t, seed):
    h = seed
    for ch in t.encode('utf-16-le')[::2] if t.isascii() else [ord(c) for c in t]:
        h ^= ch; h = (h * 0x01000193) & 0xffffffff
    return h
def desk_ref(sig):
    t = sig.strip(); a = fnv(t, 0x811c9dc5); b = fnv(t, 0x9e3779b9)
    bits = (a << 8) | (b & 0xff); A = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'; out = ''
    for _ in range(8): out = A[bits & 31] + out; bits >>= 5
    return f'DR-{out[:4]}-{out[4:]}'
SIG = re.search(r'^signature: (.+)$', open(kb + '/src/routes/kb/incidents/4471/problems/+page.svx').read(), re.M).group(1).strip()  # the page's own frontmatter
ref = desk_ref(SIG)
reviewed = '2026-11-07'
age = (datetime.date.fromisoformat(sys.argv[3]) - datetime.date.fromisoformat(reviewed)).days
css = re.search(r'<style>(.*)</style>', open(kb + '/src/lib/layouts/runbook.svelte').read(), re.S).group(1)
css = re.sub(r':global\(([^)]*)\)', r'\1', css)
page = open(kb + '/src/routes/kb/incidents/4471/problems/+page.svx').read().split('</script>', 1)[1]
def md(s):
    s = html.escape(s, quote=False)
    s = re.sub(r'\*\*`([^`]+)`(.*?)\*\*', r'<strong><code>\1</code>\2</strong>', s)
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    s = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', s)
    return s
body = []
for block in re.split(r'\n\s*\n', page.strip()):
    b = block.strip()
    if b.startswith('<ProblemTable'):
        body.append(f'<p class="sum"><strong>{len(merged)}</strong> reports merged into #4471 · <strong>{len(groups)}</strong> problems</p>\n<table><thead><tr><th>problem</th><th>reports</th><th>tenants</th><th>seen</th><th>intake tagged</th><th>state</th><th>tracked in</th></tr></thead><tbody>\n' + '\n'.join(trs) + '\n</tbody></table>')
    elif b.startswith('<Callout'):
        inner = re.sub(r'</?Callout[^>]*>', '', b).strip()
        body.append(f'<aside class="warn">{md(" ".join(inner.split()))}</aside>')
    elif b.startswith('<RenderStamp'):
        body.append(f'<p class="stamp">desk ref <b>{ref}</b></p>')
    elif b.startswith('## '):
        body.append(f'<h2>{md(b[3:])}</h2>')
    elif b.startswith('- '):
        items = re.split(r'\n- ', b[2:])
        body.append('<ul>' + ''.join(f'<li>{md(" ".join(i.split()))}</li>' for i in items) + '</ul>')
    else:
        body.append(f'<p>{md(" ".join(b.split()))}</p>')
title = '#4471 · three problems, not one'
out = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} · support kb</title>
<style>{css}
aside {{ border-left: 4px solid var(--accent); padding: 0.5rem 1rem; margin: 1rem 0; background: var(--note-bg); }}
aside.warn {{ border-color: var(--warn); background: var(--warn-bg); }}
.sum {{ font-size: 1.1rem; }} .what, .tags {{ color: var(--muted); font-size: 0.85em; }} .none {{ color: var(--warn); font-weight: 600; }}
.stamp {{ margin: 2rem 0 0; font: 0.85rem var(--mono); color: var(--muted); }} .stamp b {{ color: var(--accent); letter-spacing: 0.04em; }}
</style></head><body>
<div class="kb">
  <header>
    <a class="crumb" href="/kb">support desk · kb</a>
    <h1>{html.escape(title)}</h1>
    <p class="meta"><span>owner <b>Jayanie Bogahawatte</b></span> <span class="status open">open</span> <span>reviewed {reviewed} · {age} days ago</span></p>
  </header>
  <main>
{chr(10).join(body)}
  </main>
  <footer>Pages are written by people. Tables and charts are built from data at render time.</footer>
</div>
</body></html>
'''
import os
os.makedirs(sys.argv[2], exist_ok=True)
open(sys.argv[2] + '/index.html', 'w').write(out)
print(ref, len(merged), {k: len(v) for k, v in groups.items()})
