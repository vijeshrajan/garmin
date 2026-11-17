"""Decision-first presentation for the private Garmin dashboard.

Only derived summaries are passed in; check-ins stay in this browser tab.
"""
import html
import json
import re
from pathlib import Path


def restructure(doc, context):
    esc = html.escape
    starts = list(re.finditer(r'<section class="(?:hero|section)"[^>]*>', doc))
    end = doc.index('<footer class="footer">', starts[-1].start())
    sections = {}
    for i, match in enumerate(starts):
        block = doc[match.start():starts[i+1].start() if i+1 < len(starts) else end]
        ident = re.search(r' id="([^"]+)"', match.group())
        sections[ident.group(1) if ident else ('reasoning' if i == 1 else 'records')] = block
    cfg = context
    stale = cfg['stale']
    headline = 'Check your data first' if stale else cfg['verdict']
    action = 'Recent recovery records are missing or dated. Refresh Garmin before using training guidance.' if stale else cfg['action']
    cards = [
        ('01 / TRAINING', 'Build a repeatable routine', f"{cfg['runs28']} runs in 28 days · {cfg['distance7']:.1f} km in the last 7 days.", 'Choose a manageable next session; do not make up missed mileage.'),
        ('02 / RECOVERY', 'Make room for sleep', cfg['sleep_detail'], 'Test an earlier wind-down for two weeks and review duration and how you feel.'),
        ('03 / GOAL', 'Build the base before race pace', f"Longest recent run: {cfg['long90']:.1f} km in 90 days.", 'The sub-4 goal needs a race date, recent benchmark and sustained endurance evidence.'),
    ]
    priorities = ''.join(f'<article class="priority"><small>{a}</small><h3>{b}</h3><p>{esc(c)}</p><footer>{esc(d)}</footer></article>' for a,b,c,d in cards)
    dates = ''.join(f'<span>{esc(k)} <b>{esc(v)}</b></span>' for k,v in cfg['dates'].items())
    today = f'''<section class="advisor-intro" id="today"><div><div class="eyebrow">YOUR DAILY BRIEF · {cfg['date']}</div><h1>Train with purpose.<br><em>Recover with intent.</em></h1><p>A clear next step, grounded in your own data.</p></div><div class="goal-note"><small>THE LONG-TERM DIRECTION</small><strong>SUB 4:00</strong><span>Marathon · 5:41/km</span><p>A goal, not a current fitness prediction.</p></div></section>
    <section class="decision"><div><small>TODAY’S GUIDANCE · DASHBOARD HEURISTIC</small><h2 id="advisorDecision">{esc(headline)}</h2><p id="advisorAction">{esc(action)}</p><div class="decision-meta"><span>{cfg['quality']} coverage of recent recovery data</span><span>Confidence limited until you check in</span></div></div><a class="primary-link" href="#checkin">Check in before training →</a></section>
    <section class="section"><div class="head"><div><div class="eyebrow">FOCUS ON WHAT MATTERS</div><h2>Your three priorities</h2></div><p>One decision at a time.</p></div><div class="priority-grid">{priorities}</div></section>
    <section class="checkin section" id="checkin"><div><div class="eyebrow">THE CONTEXT YOUR WATCH CANNOT KNOW</div><h2>How do you feel today?</h2><p>This check adjusts the guidance above. It stays in this tab and resets on reload.</p></div><form id="checkinForm"><label>How your body feels<select id="feeling"><option value="unknown">Choose before training</option><option value="well">Well, no unusual symptoms</option><option value="sore">Unusually sore or fatigued</option><option value="unwell">Ill or experiencing pain</option><option value="urgent">Chest pain, fainting or severe breathlessness</option></select></label><label>Time available<select id="available"><option value="15">15 minutes</option><option value="30" selected>30 minutes</option><option value="45">45 minutes</option></select></label><button type="submit">Update my guidance</button></form><p class="checkin-result" id="checkinResult" role="status">Check-in pending. A supportive watch score does not override symptoms.</p></section>
    <details class="evidence-drawer"><summary>Why this guidance? View the evidence</summary>{sections['reasoning']}</details>
    <section class="data-strip"><strong>Record dates</strong>{dates}<p>Refresh time describes the download. Each record date describes the measurement. Today’s activity and stress may be incomplete.</p></section>'''
    goal = f'''<section class="goal-review section"><div class="eyebrow">HONEST GOAL REVIEW</div><h2>What supports a sub-4 marathon?</h2><div class="priority-grid"><article class="priority"><small>RECENT CONSISTENCY</small><h3>{cfg['runs28']} runs / 28 days</h3><p>Session count describes participation, not training quality.</p></article><article class="priority"><small>RECENT ENDURANCE</small><h3>{cfg['long90']:.1f} km / 90 days</h3><p>Recent longest run. Historic best: {cfg['longall']:.1f} km. Neither is a prescribed next-run distance.</p></article><article class="priority"><small>PACE EVIDENCE</small><h3>{esc(cfg['pace_label'])}</h3><p>{esc(cfg['pace_detail'])}</p></article></div><p class="notice">No marathon readiness percentage: race date, a recent benchmark, endurance history and your health context are required for a useful assessment.</p></section>'''
    evidence_intro = '<section class="notice"><b>Patterns are hypotheses.</b> Sample count is not statistical confidence. Repeated days, changing routines and shared Garmin inputs can create associations. Compare similar sessions and test one change at a time.</section>'
    panels = [
        ('today', 'Today', today),
        ('week', 'This week', sections['week'] + sections['training']),
        ('recovery', 'Recovery', sections['morning'] + sections['health']),
        ('progress', 'Progress', goal + sections['running'] + sections['trends'] + sections['records']),
        ('evidence', 'Insights & evidence', evidence_intro + sections['insights'] + sections['relationships'] + sections['coverage']),
    ]
    nav = ''.join(f'<a href="#{key}" data-page="{key}"><span>0{i+1}</span>{label}</a>' for i,(key,label,_) in enumerate(panels))
    sidebar = f'<aside class="advisor-sidebar"><a class="brand" href="#today">MY <b>SUB-4</b><small>PERSONAL TRAINING ADVISOR</small></a><nav aria-label="Main navigation">{nav}</nav><div class="sidebar-note"><b>Consistency over perfection.</b><p>Use trends, your symptoms and your real-world context together.</p><small>PRIVATE · GARMIN CONNECTED</small></div></aside>'
    body = ''.join(f'<div class="advisor-page" data-panel="{key}">{markup}</div>' for key,_,markup in panels)
    doc = doc[:starts[0].start()] + body + doc[end:]
    doc = doc.replace('<body>', '<body>'+sidebar)
    doc = re.sub(r'<nav>.*?</nav>', '<span class="workspace-label">YOUR TRAINING WORKSPACE</span>', doc, count=1, flags=re.S)
    doc = doc.replace('MY <i>SUB-4</i> DASHBOARD', 'MY <i>SUB-4</i> ADVISOR')
    doc = doc.replace('</head>', '<style>'+Path(__file__).with_name('advisor.css').read_text(encoding='utf-8')+'</style></head>')
    script = Path(__file__).with_name('advisor.js').read_text(encoding='utf-8')
    doc = doc.replace('</body>', '<script>const ADVISOR='+json.dumps({'headline':headline,'action':action,'stale':stale,'cautious':cfg['cautious']})+';\n'+script+'</script></body>')
    return doc
