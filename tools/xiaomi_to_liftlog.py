"""Xiaomi Notes .md export -> canonical Liftlog workouts.json
canonical grammar per spec: RxW | SxRxW | R xWORD, '+' links parts, '|' ends warm-up, other words = note on previous spec"""
import re, glob, json, hashlib, unicodedata, datetime as dt, sys, collections

def norm(s):
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn').lower().replace('ς', 'σ')
    return re.sub(r'[^a-z0-9\u0370-\u03ff]', '', s)

MODS = {}
for label, ks in [("EZ", ["ez"]), ("Closed", ["κλειστες","κλειστα","κλειστη","κλειστο","closed"]),
                  ("Good machine", ["good machine","καλο μηχανημα","μηχανημα αλλα το καλο","καλο"]),
                  ("Medium machine", ["μετριο μηχανημα","medium machine"]), ("Machine", ["machine","μηχανημα","μηχανηματοσ"]), ("Dumbbell", ["db","dumbbell","αλτηρεσ","αλτηρα"]),
                  ("Cable", ["cable"]), ("Wide", ["wide","φαρδια","ανοιχτα","ανοιχτο"])]:
    for k in ks: MODS[norm(k)] = label
IGNORE = {norm(w) for w in ['πάμε','συνεχίζουμε','συνεχίζω']}   # filler lines, skipped
DROP_NAMES = {norm(w) for w in ['Tricep pulldown + Dips ενναλαξ','Tricep SkullcrushersEZ Side raises Dumbbell']}
DROP_WORKOUTS = {'Gym Jan 11'}
WARM = re.compile(r'^(ζεστ|ζεσα|warm)', re.I)

# ---------- dates ----------
MON = {}
for i, names in enumerate([["jan","γεν","ιαν"],["feb","fev","φεβ","φλεβ"],["mar","μαρ"],["apr","απρ"],["may","μαι","μαϊ"],
                           ["jun","jume","ιουν"],["jul","ιουλ"],["aug","αυγ"],["sep","σεπ"],["oct","οκτ"],["nov","νοε","νοεμ"],["dec","δεκ"]]):
    for n in names: MON[norm(n)] = i + 1
def title_date(title, created):
    t = title.lower()
    m = re.search(r'(\d{1,2})/(\d{1,2})', t)
    day = mon = None
    if m: day, mon = int(m.group(1)), int(m.group(2))
    else:
        toks = re.findall(r'[^\W\d_]+|\d+', t)
        for i, tok in enumerate(toks):
            k = norm(tok)
            mk = next((MON[p] for p in sorted(MON, key=len, reverse=True) if k.startswith(p)), None)
            if mk and not k.startswith(('gym','push','pull')):
                nums = [int(x) for x in toks[max(0,i-1):i+2] if x.isdigit() and 1 <= int(x) <= 31]
                if nums: mon, day = mk, nums[-1] if (i+1 < len(toks) and toks[i+1].isdigit()) else nums[0]; break
        if mon is None:
            nums = [int(x) for x in toks if x.isdigit() and 1 <= int(x) <= 31]
            if nums:
                day = nums[0]; mon = created.month if day <= created.day else (created.month - 1 or 12)
    if not mon: return created, 'created'
    for y in (created.year, created.year - 1):
        try:
            d = dt.date(y, mon, day)
        except ValueError:
            return created, 'created'
        if d <= created + dt.timedelta(days=1): return d, 'title'
    return created, 'created'

def title_type(title):
    t = norm(title)
    parts = []
    for keys, lab in [(["push","σπρωξε","sprokse"],"Push"),(["pull","τραβα","trava"],"Pull"),(["backchest","bc"],"Back/Chest"),
                      (["back"],"Back"),(["chest"],"Chest"),(["shoulder"],"Shoulders"),(["leg"],"Leg"),(["arm"],"Arm"),
                      (["bicep"],"Bicep"),(["fullbody","fb"],"Full body")]:
        for k in keys:
            if k in t and not (lab in ("Back","Chest") and "Back/Chest" in parts):
                parts.append(lab); t = t.replace(k, ''); break
    s = '/'.join(parts) or 'Workout'
    if 'home' in norm(title): s += ' (home)'
    return s

# ---------- set specs ----------
NUM = r'\d+(?:[.,]\d+)?'
def f(x): x = float(str(x).replace(',', '.')); return str(int(x)) if x == int(x) else str(x)

def orient(a, b):
    """returns 'RW', 'WR' or None (ambiguous) for an AxB pair"""
    a, b = float(a), float(b)
    if b == 0: return 'WR' if a > 30 else 'RW'
    if a == 0: return 'RW' if b > 30 else 'WR'
    if a <= 20 and b > 20: return 'RW'
    if b <= 20 and a > 20: return 'WR'
    if a > 20 and b > 20: return 'RW' if b > a else 'WR'
    return None

def lex(tok):
    """token -> list of parts [{'n':[nums...], 'word':str|None, 'cont':bool}] or None"""
    parts = []
    for p in tok.split('+'):
        if not p: return None
        m = re.fullmatch(rf'({NUM}(?:x{NUM}){{0,2}})(?:x([^\d\W][\w.,]*))?', p, re.I)
        if m:
            ns = re.split(r'x', m.group(1), flags=re.I)
            if len(ns) == 1 and not m.group(2): return None   # bare number
            parts.append({'n': ns, 'word': m.group(2), 'cont': False}); continue
        m = re.fullmatch(rf'x({NUM})', p, re.I)  # "x100" = previous reps at new weight
        if m: parts.append({'n': [m.group(1)], 'word': None, 'cont': True}); continue
        m = re.fullmatch(rf'({NUM}(?:x{NUM}){{1,2}})([^\d\W]\w*)', p, re.I)  # "6x5Κλειστα" -> spec + note
        if m: parts.append({'n': re.split(r'x', m.group(1), flags=re.I), 'word': None, 'suffix': m.group(2), 'cont': False}); continue
        return None
    return parts

def pre(line):
    line = re.sub(r'(\d)\s*[xX×χ]\s*(?=[\d+])', r'\1x', line)       # "15 x 32"
    line = re.sub(r'x\s*\+\s*(\d)', r'x\1', line, flags=re.I)         # "9x+7.5" added weight
    line = re.sub(r'(\d+)\s*x\s*\(([^)]*)\)', lambda m: ' '.join([m.group(2)] * min(int(m.group(1)), 10)), line)  # 2x(a+b)
    line = re.sub(r'(\S)\(([^)]*)\)', r'\1 (\2)', line)                 # "80x3(PR)"
    return line

def canon_line(line, file_votes):
    """returns (canonical_tokens, prefix_words, n_specs, ambiguous_count)"""
    toks = [t.strip(',;.') for t in pre(line).split()]
    lexed = [(t, lex(t) if t else None) for t in toks]
    votes = collections.Counter()
    for _, L in lexed:
        for p in L or []:
            if len(p['n']) >= 2: o = orient(*p['n'][-2:]); o and votes.update([o])
    line_o = votes.most_common(1)[0][0] if votes else None
    out, prefix, nspec, amb, seen_spec = [], [], 0, 0, False
    for t, L in lexed:
        if t == '|' and seen_spec: out.append('|'); continue
        if not L:
            if not t: continue
            if re.fullmatch(r'f(ail)?', t, re.I) and out: out.append('fail'); continue
            (out if seen_spec else prefix).append(t); continue
        seen_spec = True; nspec += 1
        parts, prev_r, suffixes = [], None, []
        for p in L:
            n = p['n']
            if p['cont']:
                r, w = prev_r, n[0]
                if r is None: parts = None; break
                parts.append(f"{f(r)}x{f(w)}"); continue
            sets = 1
            if len(n) == 3: sets, n = n[0], n[1:]
            if float(sets) > 10 or float(sets) != int(float(sets)): parts = None; break
            if p['word']:
                if len(n) == 2:  # "110x6xK": numbers + qualifier word
                    o = orient(*n) or line_o or file_votes or 'RW'
                    r, w = (n[0], n[1]) if o == 'RW' else (n[1], n[0])
                    suffixes.append(p['word']); prev_r = r
                    parts.append(f"{f(sets)+'x' if int(float(sets))>1 else ''}{f(r)}x{f(w)}"); continue
                if re.fullmatch(r'f(ail)?', p['word'], re.I):   # "92.5xFAIL"
                    parts.append(f"0x{f(n[0])}"); suffixes.append('fail'); continue
                prev_r = n[0]
                parts.append(f"{f(sets)+'x' if int(float(sets))>1 else ''}{f(n[0])}x{p['word']}"); continue
            if len(n) == 1: parts = None; break
            o = orient(*n)
            if o is None: amb += 1; o = line_o or file_votes or 'RW'
            r, w = (n[0], n[1]) if o == 'RW' else (n[1], n[0])
            if float(r) == 0 and float(w) > 0: suffixes.append('fail')
            prev_r = r
            parts.append(f"{f(sets)+'x' if int(float(sets))>1 else ''}{f(r)}x{f(w)}")
            if p.get('suffix'): suffixes.append(p['suffix'])
        if parts is None: out.append(t); nspec -= 1; continue
        out.append('+'.join(parts)); out.extend(suffixes)
    return out, prefix, nspec, amb

STOP = {norm(w) for w in ["στο","στη","στην","με","το","τα","αλλα","και","on","the","with"]}
def canon_name(name):
    """strip filler words; Greek modifier phrases -> English modifier labels the app understands"""
    ws = [w for w in re.split(r'\s+', name.strip(' :,.')) if w]
    mods, keep, i = [], [], 0
    while i < len(ws):
        two = norm(' '.join(ws[i:i+2])) if i + 1 < len(ws) else None
        if two and two in MODS and len(ws) > 2: mods.append(MODS[two]); i += 2; continue
        k = norm(ws[i])
        if k in STOP and len(ws) > 1: i += 1; continue
        if k in MODS and len(ws) > 1 and k not in ('καλο',): mods.append(MODS[k]); i += 1; continue
        keep.append(ws[i]); i += 1
    return ' '.join(keep + [m for m in dict.fromkeys(mods)])

def blocks(raw):
    out = []
    for l in raw.split('\n'):
        if not re.search(r'\dx', l): out.append([l])
        elif out: out[-1].append(l)
    return out

# ---------- file ----------
def parse_file(path):
    txt = open(path, encoding='utf-8').read()
    title = re.search(r'## Title:\s*(.*)', txt).group(1).strip()
    cm = re.search(r'Created at:\s*(\d{2})/(\d{2})/(\d{4})\s*(\d{1,2}:\d{2})?', txt)
    bw = re.search(r'(?im)^\s*βάρος:?\s*(\d+(?:[.,]\d+)?)', txt)
    created = dt.date(int(cm.group(3)), int(cm.group(2)), int(cm.group(1)))
    body = txt.split(title, 1)[1]
    body = re.sub(r'\*Created at:.*?\*', '', body)
    lines = [l.rstrip() for l in body.split('\n')]
    # file-level orientation fallback
    fv = collections.Counter()
    for l in lines:
        for t in pre(l).split():
            for p in lex(t.strip(',;.')) or []:
                if len(p['n']) >= 2: o = orient(*p['n'][-2:]); o and fv.update([o])
    file_o = fv.most_common(1)[0][0] if fv else 'RW'
    info = [(l.strip(),) + canon_line(l, file_o) if l.strip() else None for l in lines]
    out, notes, cur, stats = [], [], None, collections.Counter()
    def nxt(i):
        for j in range(i + 1, len(info)):
            if info[j]: return j
        return None
    i = -1
    while i + 1 < len(info):
        i += 1
        if not info[i]: continue
        raw, toks, prefix, nspec, amb = info[i]
        if norm(raw) in IGNORE: continue
        stats['ambiguous'] += amb
        words = [norm(w) for w in raw.split() if norm(w)]
        modkey = next((MODS[k] for k in sorted(MODS, key=len, reverse=True) if norm(raw).startswith(k)), None)
        if nspec == 0:
            j = nxt(i)
            is_mod = modkey and cur and len(words) <= 6
            is_aux = lambda k: info[k][3] == 0 and (WARM.match(info[k][0]) or any(norm(info[k][0]).startswith(m) for m in MODS))
            hops = 0
            while j is not None and hops < 3 and is_aux(j): j = nxt(j); hops += 1
            nxt_spec = j is not None and info[j][3] > 0
            nxt_mod_spec = False
            if is_mod and not WARM.match(raw):
                base = cur; cur = canon_name(f"{cur} {raw}")
                if out and out[-1] == base: out[-1] = cur
                else: out.append(cur)
                stats['modifier lines'] += 1; continue
            if len(words) <= 4 and not WARM.match(raw) and (nxt_spec or nxt_mod_spec):
                cur = canon_name(raw); out.append(cur); stats['exercises'] += 1; continue
            notes.append(f"unparsable: {(cur + ': ') if cur else ''}{raw}"); stats['unparsable lines'] += 1; continue
        # spec line
        if prefix:
            pk = norm(' '.join(prefix))
            if any(WARM.match(w) for w in prefix):
                toks = toks + ['|']; stats['warm-up lines'] += 1
            elif pk in MODS and cur:
                cur = f"{cur} {MODS[pk]}"; out.append(cur)
            elif len(prefix) <= 3:
                cur = canon_name(' '.join(prefix)); out.append(cur); stats['exercises'] += 1
            else:
                notes.append(f"unparsable: {(cur + ': ') if cur else ''}{raw}"); stats['unparsable lines'] += 1; continue
        if not cur:
            notes.append(f"unparsable: {raw}"); stats['unparsable lines'] += 1; continue
        out.append(' '.join(toks)); stats['set lines'] += 1
        unp = [t for t in toks if re.fullmatch(rf'{NUM}', t)]
        if unp: stats['lines with stray numbers'] += 1
    # drop listed two-exercise lines with their sets
    keep, skipping = [], False
    for l in out:
        if not re.search(r'\dx', l): skipping = norm(l) in DROP_NAMES
        if not skipping: keep.append(l)
    out = keep
    # drop exercise headers with no following sets
    clean = []
    for k, l in enumerate(out):
        is_ex = not re.search(r'\dx', l)
        nxt_l = out[k + 1] if k + 1 < len(out) else None
        if is_ex and (nxt_l is None or not re.search(r'\dx', nxt_l)): notes.append(f"unparsable: {l} (no sets)"); stats['empty exercises'] += 1; continue
        clean.append(l)
    d, src = title_date(title, created)
    notes = [n for n in notes if not re.search(r'(?i)βάρος:?\s*\d', n)]   # bodyweight goes to the Weight tab
    return {'id': 'x' + hashlib.sha1(path.encode()).hexdigest()[:10], 'date': d.isoformat(), 'title': title_type(title),
            'raw': '\n'.join(clean), 'notes': '\n'.join(notes), 'original': title + '\n' + '\n'.join(l for l in lines if l.strip()),
            'source': title, '_bw': (float(bw.group(1).replace(',', '.')), cm.group(4) or '12:00') if bw else None}, stats, src

if __name__ == '__main__':
    files = sorted(glob.glob(sys.argv[1] + '/*.md'))
    ws, tot, skipped, dsrc = [], collections.Counter(), [], collections.Counter()
    for p in files:
        w, st, src = parse_file(p)
        if not re.search(r'\dx', w['raw']): skipped.append(w['source']); continue
        ws.append(w); tot.update(st); dsrc[src] += 1
    ws = [w for w in ws if w['source'] not in DROP_WORKOUTS]
    ws.sort(key=lambda w: w['date'])
    # pull-ups: until the first bodyweight (x0) pull-up set, weights were machine assistance -> negative
    PU = re.compile(r'^(ελξ|pullup|chinup)')
    first0 = next((w['date'] for w in ws for blk in blocks(w['raw']) if PU.match(norm(blk[0]))
                   and any(re.search(r'(^|[\s+])\d+(?:\.\d+)?x0(?=[\s+]|$)', l) for l in blk[1:])), None)
    neg = 0
    for w in ws:
        if first0 and w['date'] >= first0: break
        lines = w['raw'].split('\n'); cur = None
        for k, l in enumerate(lines):
            if not re.search(r'\dx', l): cur = l; continue
            if cur and PU.match(norm(cur)):
                lines[k] = re.sub(r'(\d+(?:\.\d+)?x)(\d+(?:\.\d+)?)(?=[\s+]|$)', lambda m: m.group(1) + ('-' + m.group(2) if float(m.group(2)) > 0 else m.group(2)), l); neg += 1
        w['raw'] = '\n'.join(lines)
    print('pull-ups assisted until', first0, '| lines negated:', neg)
    weights = []
    for w in ws:
        bw = w.pop('_bw')
        if bw: weights.append({'id': 'b' + w['id'][1:], 't': f"{w['date']}T{bw[1].zfill(5)}", 'kg': bw[0]})
    print('bodyweights:', len(weights))
    json.dump({'app': 'liftlog', 'version': 1, 'workouts': ws, 'weights': weights}, open(sys.argv[2], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(len(files), 'files ->', len(ws), 'workouts; skipped (no sets):', skipped)
    print('date source:', dict(dsrc)); print(dict(tot))
