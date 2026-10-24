"""The chronicle: a short log of a long play for finding what went wrong, instead of a copy of every save.

    sowtool chronicle --out <folder> [--save <file>] [--source <finished game save>]

Watches the save while the game writes it (only reads it). Into <folder>/летопись.txt goes only what matters:
- the orcs of the finished game (--source: the worthy ones and the dead followers — the enemies the build brings) — every change: died, killed Talion, came
  back, promoted, betrayed. Names repeat, so an orc is ours when in the first save it has a name of the twenty and
  its old title, the role of its return or the mark of a return (IsResurrected); then it is followed by number. Other orcs that
  met Talion — deaths, returns, promotions to warchief or overlord, kills of Talion;
- the Nemesis queue: ambushes and betrayals appearing and leaving (with the orc), not the short combat events;
- the story (QSTD records changing), Talion's level;
- crash dumps of the game (%LOCALAPPDATA%\\CrashDumps) and saves that cannot be read.
Copies of the save: the last KEEP in <folder>/копии, and for good the ones of the moments above (a crash, a story
step, an orc of ours dying or coming back) in <folder>/важные. A copy keeps <id>_ShadowOfWar in its name — the key
of the save depends on it.
"""
import datetime
import glob
import os
import shutil
import time

from . import orcs, save as sv

KEEP = 30
QUIET = ('PC_', 'AI_Low', 'General_Cooldown')         # combat context events: they come and go every few seconds
WATCH_FLAGS = ('IsResurrected', 'PlayerFollower', 'Dominated')
REGIONS = {'Faction_MinasIthil': 'Минас-Моргул', 'Faction_MtnPass': 'Кирит-Унгол', 'Faction_snowMtn': 'Серегост',
           'Faction_volcano': 'Горгорот', 'Faction_island': 'Нурн', 'Faction_desert_Real': 'Литлад'}


class Snapshot:
    def __init__(self, buf, gd):
        rec = gd.record
        self.level = sv.talion(buf)[0]
        self.orcs = {o['number']: o for o in orcs.read(buf, gd)}
        p, size = sv.block(buf, 'WHDC')
        t = sv.tokens(buf, p + 20, p + 16 + size)
        self.queue = []
        for i in range(len(t) - 7):
            if t[i].type == 0x0C and t[i].value == 1 and t[i + 1].type == 0 and t[i + 2].type == 0 \
                    and t[i + 3].type == 0 and t[i + 4].type == 4 and t[i + 5].type == 8 and t[i + 6].type == 4 \
                    and (rec(t[i + 1].value) or '').startswith('Faction_'):
                ev = rec(t[i + 2].value) or '#%08x' % t[i + 2].value
                self.queue.append((ev, REGIONS.get(rec(t[i + 1].value), rec(t[i + 1].value)), t[i + 4].value,
                                   t[i + 6].value))
        q = sv.block_tokens(buf, 'QSTD')
        self.story = {rec(x.value): q[k + 1].value for k, x in enumerate(q[:-1])
                      if x.type == 0 and rec(x.value) and q[k + 1].type in (2, 4, 8)}


def _who(o):
    return '%s %s (№%d, ур. %d, %s%s)' % (o['name'], o['title'], o['number'], o['level'], o['region'] or 'без региона',
                                          ', ' + o['place'] if o['place'] else '')


def _same(a, b):
    return a is not None and b is not None and a['name'] == b['name']


def mine(snap, source_orcs):
    """The numbers of our orcs in the first save of the play (see the module doc)."""
    from .returned import SCARS, comes_back
    known = {}                                    # name -> titles and roles it can have
    for o in source_orcs:
        s = comes_back(o)
        known.setdefault(o['name'], set()).update({o['title'], o['role_key'], SCARS[s or 'Slashface'][0]})  # as place()
    for v in known.values():
        v.discard('')                             # no title / role: many a namesake of the base has none too
    return {n for n, o in snap.orcs.items() if o['name'] in known
            and ({o['title'], o['role_key']} & known[o['name']] or 'IsResurrected' in o['flags'])}


def diff(a, b, ours):
    """The lines of what changed from a to b; important: one of them is a moment to keep a copy of."""
    out, important = [], False
    if a.level != b.level:
        out.append('Талион: уровень %s → %s' % (a.level, b.level))
    for k in sorted(set(a.story) | set(b.story)):
        if a.story.get(k) != b.story.get(k):
            out.append('Сюжет: %s %s → %s' % (k, a.story.get(k, '—'), b.story.get(k, '—')))
            important = True
    for n, o in sorted(b.orcs.items()):
        p = a.orcs.get(n)
        if not _same(p, o):                      # a number taken by another orc: ours no more
            ours.discard(n)
            continue
        mine = n in ours
        if not (mine or o['met']):
            continue
        what = []
        if p['dead'] != o['dead']:
            what.append('погиб' + (' (%s)' % orcs.CAUSES.get(o['death_cause'], o['death_cause'])
                                   if o['death_cause'] else '') if o['dead'] else 'вернулся из мёртвых')
        if o['kill'] > p['kill']:
            what.append('убил Талиона (%d-й раз)' % o['kill'])
        if p['place'] != o['place'] and (mine or o['place'] in ('вождь', 'правитель')):
            what.append('место: %s → %s' % (p['place'] or '—', o['place'] or '—'))
        if p['title'] != o['title'] and mine:
            what.append('титул: %s → %s' % (p['title'], o['title']))
        if mine and p['level'] != o['level']:
            what.append('уровень %d → %d' % (p['level'], o['level']))
        for f in WATCH_FLAGS:
            if (f in p['flags']) != (f in o['flags']) and (mine or f != 'Dominated'):
                what.append('%s %s' % ('+' if f in o['flags'] else '−', f))
        if what:
            out.append('%s%s %s: %s' % ('★ ' if mine else '', o['name'], o['title'], ', '.join(what)))
            important = important or (mine and (p['dead'] != o['dead'] or o['kill'] > p['kill']))

    def keyed(s):
        return {(ev, reg, num) for ev, reg, num, _ in s.queue if not ev.startswith(QUIET)}

    def name(s, num):
        o = s.orcs.get(num)
        return '' if num < 0 else ' №%d %s %s' % (num, o['name'], o['title']) if o else ' №%d' % num
    for ev, reg, num in sorted(keyed(b) - keyed(a)):
        out.append('Очередь: + %s (%s)%s' % (ev, reg, name(b, num)))
    for ev, reg, num in sorted(keyed(a) - keyed(b)):
        out.append('Очередь: − %s (%s)%s — сработало или снято' % (ev, reg, name(a, num)))
    return out, important


def _dumps(since):
    root = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'CrashDumps')
    return {f for f in glob.glob(os.path.join(root, '*.dmp'))
            if 'shadowofwar' in os.path.basename(f).lower() and os.path.getmtime(f) >= since}


def _stable_read(path):
    while True:
        st = os.stat(path)
        time.sleep(0.4)
        st2 = os.stat(path)
        if (st.st_size, st.st_mtime) == (st2.st_size, st2.st_mtime):
            with open(path, 'rb') as f:
                return f.read(), st2.st_mtime


def _alive(pid):
    """Is the process still running (Windows; elsewhere — assumed so)."""
    try:
        import ctypes
        k = ctypes.windll.kernel32
    except (ImportError, AttributeError):
        return True
    h = k.OpenProcess(0x1000, False, pid)                # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return False
    code = ctypes.c_ulong()
    ok = k.GetExitCodeProcess(h, ctypes.byref(code))
    k.CloseHandle(h)
    return bool(ok) and code.value == 259                 # STILL_ACTIVE


def watch(path, out, gd, source=None, log=print, parent=None):
    """Runs until stopped (Ctrl+C, the process killed, or the parent process — the window — gone: then it stops
    itself, so that it never stays behind when the window was closed some other way or fell)."""
    copies, keep = os.path.join(out, 'копии'), os.path.join(out, 'важные')
    for d in (out, copies, keep):
        os.makedirs(d, exist_ok=True)
    army = orcs.read(sv.load(source)[0], gd) if source else []
    picked = orcs.recommend(army) + [o for o in army if o['follower'] and o['dead'] and o['met'] and not o['story']]
    ours = set()
    journal = os.path.join(out, 'летопись.txt')
    stem = os.path.basename(path)[:-len('.sav')]

    def write(lines):
        stamp = datetime.datetime.now().strftime('%H:%M:%S')
        with open(journal, 'a', encoding='utf-8') as f:
            for line in lines:
                f.write('%s  %s\n' % (stamp, line))
                log(line)

    start = time.time()
    write(['', '=== %s: летопись, сохранение %s%s' % (
        datetime.datetime.now().strftime('%Y-%m-%d'), path,
        '; орки пройденной игры (★): ' + ', '.join(o['name'] for o in picked) if picked else '')])
    prev, last, last_mtime, seen_dumps = None, None, None, _dumps(start)
    while True:
        if parent and not _alive(parent):
            write(['=== летопись остановлена: окно программы закрыто'])
            break
        try:
            for d in sorted(_dumps(start) - seen_dumps):
                write(['ВЫЛЕТ ИГРЫ: дамп %s' % d])
                seen_dumps.add(d)
                if last:                                 # the last save before the crash
                    shutil.copy2(last, keep)
            if os.path.getmtime(path) != last_mtime:
                raw, last_mtime = _stable_read(path)
                copy = os.path.join(copies, '%s_%s.sav' % (stem, datetime.datetime.fromtimestamp(last_mtime)
                                                           .strftime('%Y%m%d-%H%M%S')))
                if not os.path.exists(copy):
                    with open(copy, 'wb') as f:
                        f.write(raw)
                last = copy
                try:
                    snap = Snapshot(sv.load(copy)[0], gd)
                except Exception as e:                   # noqa: BLE001 - a save the tools cannot read is news
                    write(['НЕ ЧИТАЕТСЯ: %s (%s: %s)' % (os.path.basename(copy), type(e).__name__, e)])
                    shutil.copy2(copy, keep)
                    snap = None
                if snap:
                    if prev is None:
                        ours = mine(snap, picked)
                        mine_now = [snap.orcs[n] for n in sorted(ours)]
                        write(['Начало: Талион ур. %s; наших орков в сохранении: %d; засад и предательств в очереди: %d'
                               % (snap.level, len(mine_now), sum(1 for e in snap.queue if not e[0].startswith(QUIET)))]
                              + ['★ ' + _who(o) + (', мёртв' if o['dead'] else '') for o in mine_now])
                        shutil.copy2(copy, keep)
                    else:
                        lines, important = diff(prev, snap, ours)
                        if lines:
                            write(['— сохранение %s' % os.path.basename(copy)] + ['  ' + x for x in lines])
                        if important:
                            shutil.copy2(copy, keep)
                    prev = snap
                old = sorted(glob.glob(os.path.join(copies, '*.sav')))
                for f in old[:-KEEP]:
                    os.remove(f)
            time.sleep(1)
        except KeyboardInterrupt:
            write(['=== летопись остановлена'])
            break
        except OSError:                                   # the game is replacing the file right now
            time.sleep(1)
