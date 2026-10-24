"""Experiment: the random orcs of a region's hierarchy replaced with orcs of the finished game (research).

    python research/orc_replace.py <base> <source> <out> [--region island] [--seed N] [--rows Captain,Outer_Warchief]

Who is replaced: an orc on a place of the region's hierarchy table (rows Captain_*, Outer_Warchief, Inner_Warchief;
never the overlord) that is random — two fresh new games (research/fresh_diff.py) showed the fixed characters carry
WasEverPresetFactionMember (Bruz, the Ranger, the nazgul, the Gondorians...). So an occupant is kept when it has that
flag, IgnorePlayerLevelRestriction, PlayerFollower, a story AI (not AI_*), a fixed name (not *NameGen*), met Talion
or is dead.
Who comes: a living orc of the source that never met Talion (no Talion event in its history, not even an indirect
'*Player*' one), not preset, not a follower, AI_* class, generated name; about a third from the overlord's tribe.
What is done to it: its record takes the replaced orc's number and cell in MainGame (that orc is gone, everything
of the game pointing at the number now means the new orc), its region becomes the base's, its place token = the
row (the hierarchy table already has the number), its level = the replaced orc's level (both
copies), history days = the base's current day - 5, not below 0 (BASE_DAY), its relation list emptied, flags
PresentedToPlayer, CameraPresented, IdentityPresented, SimEventActive, Vow, RevengeTarget, ResurrectedThisSpawn
cleared (it was never seen in this game). Title, traits, personality, looks stay.
History: experiment 29 appended the new ones and left the old ones place-less (the game kept them), 30 deleted the
old ones (empty cells; loaded fine, Nurn only), 31 the same in all regions crashed on loading — the old numbers are
also used by the Nemesis missions on the map. Hence the same number since experiment 32.
"""
import collections
import os
import random
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app', 'engine'))
sys.path.insert(0, os.path.join(ROOT, 'research'))
from sowtool import crypto, ngplus, orcs, save as sv  # noqa: E402
from sowtool.gamedata import GameData, name_hash      # noqa: E402
import orc_ghosts                                     # noqa: E402
import orc_insert                                     # noqa: E402
import orc_slot                                       # noqa: E402

KEEP_FLAGS = {'WasEverPresetFactionMember', 'IgnorePlayerLevelRestriction', 'PlayerFollower'}
CLEAR_FLAGS = ('PresentedToPlayer', 'CameraPresented', 'IdentityPresented', 'SimEventActive', 'Vow', 'RevengeTarget',
               'ResurrectedThisSpawn')
ROWS = ('Captain', 'Outer_Warchief', 'Inner_Warchief')
TRIBE_SHARE = 1 / 3
EMPTY_CELL = bytes((0x0C, 0))                # a deleted orc's cell in MainGame
# region key -> (faction of the hierarchy table and the orcs, prefix of its rows). Minas Morgul too (the user, after
# experiment 34: its only story fights are the nazgul; the siege is a cutscene) - its nazgul / Gondorians are preset
REGIONS = {'MinasIthil': ('Faction_MinasIthil', 'MinasIthil'), 'island': ('Faction_island', 'island'), 'MtnPass': ('Faction_MtnPass', 'MtnPass'),
           'snowMtn': ('Faction_snowMtn', 'snowMtn'), 'volcano': ('Faction_volcano', 'volcano'),
           'desert': ('Faction_desert_Real', 'desert')}


def hierarchy(t, rec, faction, prefix):
    """{row name: [token index of each place]} of a region's hierarchy table (see orc_slot.hierarchy)."""
    for i in range(len(t) - 4):
        if t[i].type == 0 and rec(t[i].value) == faction and t[i + 1].type == 4 and t[i + 2].type == 4                 and t[i + 3].type == 4 and t[i + 4].type == 0 and (rec(t[i + 4].value) or '').startswith(prefix + '_Row_'):
            out, j = {}, i + 4
            for _ in range(t[i + 3].value):
                row, places = rec(t[j].value), t[j + 1].value
                out[row] = list(range(j + 2, j + 2 + places))
                j += 2 + places
            return out
    raise SystemExit('нет таблицы иерархии для %s' % faction)
# the current day of the bundled bases: the day the game writes into new history events right after loading
# (experiment 29: 8 on the act 2 base; the latest day in its orcs' histories, 16, is not it); the prologue: 0
BASE_DAY = {False: 0, True: 8}          # by ngplus.act1_done(base)


def name_keys(buf, rec):
    t, rg = orcs.table(buf, rec)
    return {t[s + 1].value: rec(t[s + 3].value) or '' for s, e in rg}


def random_orc(o, name_key):
    """True when the orc is one the game generates anew (see the module doc)."""
    return (not o['met'] and not o['dead'] and not set(o['flags']) & KEEP_FLAGS and o['ai'].startswith('AI_')
            and 'NameGen' in name_key and not o['story'])


def candidate(o, name_key):
    return random_orc(o, name_key) and not o['follower'] and not any('Player' in ev for ev, _ in o['history'])


def prepare(raw, number, region, level, day, rec):
    raw = bytearray(raw)
    struct.pack_into('<i', raw, 3, number)
    t = sv.tokens(bytes(raw), 0, len(raw))
    src_region = next(rec(x.value) for x in t if x.type == 0 and (rec(x.value) or '').startswith('Faction_'))
    for x in t:
        if x.type == 0 and x.value == name_hash(src_region):
            raw[x.pos + 1:x.pos + 5] = struct.pack('<I', name_hash(region))
    # level: 0f id | 09 | 04 | 04 | 04 | 0c | 0f | 0f | 08 <lvl-1> | 04 <lvl-1>
    npc = orcs._desc_start(t, 0, len(t))
    i = next(i for i in range(npc, npc + 12) if t[i].type == 8 and t[i + 1].type == 4)
    assert t[i].value == t[i + 1].value
    struct.pack_into('<I', raw, t[i].pos + 1, level - 1)
    struct.pack_into('<i', raw, t[i + 1].pos + 1, level - 1)
    # history days (the longest run of 00 <event> 03 <day>, as orc_ghosts.prepare)
    pair = [t[k].type == 0 and t[k].value and rec(t[k].value) and t[k + 1].type == 3 for k in range(len(t) - 1)]
    best, k = (0, 0), 0
    while k < len(pair):
        j = k
        while j < len(pair) and pair[j]:
            j += 2
        if (j - k) // 2 > best[1]:
            best = (k, (j - k) // 2)
        k = j + 1 if j == k else j
    for n in range(best[1]):
        struct.pack_into('<h', raw, t[best[0] + 2 * n + 1].pos + 1, day)
    # flags
    f = next(x for x in t[npc:] if x.type == 0x05)
    bits = int.from_bytes(raw[f.pos + 1:f.pos + 9], 'little')
    for name in CLEAR_FLAGS:
        bits &= ~(1 << orcs.FLAGS.index(name))
    raw[f.pos + 1:f.pos + 9] = bits.to_bytes(8, 'little')
    # relations: 04 <count> at TraitLevelOffset_* + 15, then (0c 01 | 00 | 00 | 04 | 00 | 04) * count
    tlo = next(k for k, x in enumerate(t) if x.type == 0 and (rec(x.value) or '').startswith('TraitLevelOffset_'))
    c = t[tlo + 15]
    assert c.type == 4
    dropped = c.value
    if dropped:
        last = t[tlo + 15 + 6 * dropped]
        assert t[tlo + 16].type == 0x0C and last.type == 4
        raw = raw[:c.pos] + b'\x04' + struct.pack('<i', 0) + raw[last.end:]
    return bytes(raw), dropped


def build(base, source, gd, region='island', rows=ROWS, seed=None, log=print, used=None, fresh_only=False,
          keep_id=False):
    """used: source orc numbers already taken (several regions in a row); the chosen ones are added to it.
    fresh_only: replace only orcs the game never put into the world (empty _NPC_ id) - experiment 34; keep_id: the new
    orc keeps the replaced one's _NPC_ id string - experiment 35 (Cirith Ungol, where act 1 was played, crashed on
    loading when its orcs were replaced - experiment 33a; Gorgoroth with 14 spawned orcs replaced loaded fine)."""
    rec = gd.record
    faction, prefix = REGIONS[region]
    used = set() if used is None else used
    rng = random.Random(seed)
    b_orcs = {o['number']: o for o in orcs.read(base, gd)}
    b_names = name_keys(base, rec)
    p, t, mg, n, starts, end = orc_insert.table(base, rec)
    table = hierarchy(t, rec, faction, prefix)
    overlord = next((b_orcs[t[c].value] for row, cells in table.items() if row.endswith('_Row_Overlord')
                     for c in cells if t[c].value >= 0), None)
    targets, kept = [], []
    for row, cells in table.items():
        kind = re.sub(r'_\d+$', '', row.split('_Row_')[1])
        for c in cells:
            num = t[c].value
            if num < 0:
                continue
            o = b_orcs[num]
            # only an orc the game never put into the world (empty _NPC_ id): experiment 33 — Cirith Ungol, the
            # region of act 1, has its orcs spawned (id set, duels, interrogations, the warchief's guard...);
            # replacing them crashed the game on loading, the other regions (all ids empty) loaded fine
            if kind in rows and random_orc(o, b_names[num]) and not (fresh_only and o['npc']):
                targets.append((row, c, o))
            else:
                kept.append((row, o))
    for row, o in kept:
        log('остаётся: %-26s №%-4d %s %s %s' % (row, o['number'], o['name'], o['title'],
                                               ', '.join(sorted(set(o['flags']) & KEEP_FLAGS))
                                               or ('уже был в мире' if o['npc'] else o['ai'])))
    s_orcs = orcs.read(source, gd)
    s_names = name_keys(source, rec)
    pool = [o for o in s_orcs if candidate(o, s_names[o['number']]) and o['number'] not in used]
    tribe = overlord['tribe_key'] if overlord else ''
    same = [o for o in pool if o['tribe_key'] == tribe]
    other = [o for o in pool if o['tribe_key'] != tribe]
    rng.shuffle(same)
    rng.shuffle(other)
    k_same = min(len(same), round(len(targets) * TRIBE_SHARE))
    chosen = same[:k_same] + other[:len(targets) - k_same]
    rng.shuffle(chosen)
    assert len(chosen) == len(targets), 'кандидатов мало'
    used.update(o['number'] for o in chosen)
    day = max(0, BASE_DAY[ngplus.act1_done(base)] - 5)
    log('правитель: %s (%s); из его племени %d из %d; кандидатов %d; дни истории %d'
        % (overlord['name'] if overlord else '-', overlord['tribe'] if overlord else '-', k_same, len(targets),
           len(pool), day))
    # every new orc takes the replaced one's number and cell (experiment 32): the game's own references to that
    # number — Nemesis missions on the map (raids, executions, chases, outpost commanders, trials...), the
    # hierarchy table — then point at the new orc of the same place instead of a deleted one. Experiments 29-31
    # appended the new orcs and deleted the old ones; 31 (all regions) crashed on loading, most likely on such a
    # mission of Cirith Ungol pointing at a deleted orc (in 30 only Nurn's missions did, and it loaded).
    edits = []
    for (row, cell, old), new in zip(targets, chosen):
        raw, rels = prepare(orc_insert.record(source, rec, new['number']), old['number'], faction, old['level'], day,
                            rec)
        rt = sv.tokens(raw, 0, len(raw))
        assert rt[7].type == 0                         # 0c 01 | 04 n | 09 | 08 name | 00 | 00 | 00 AI | 00 place
        raw = raw[:rt[7].pos + 1] + struct.pack('<I', name_hash(row)) + raw[rt[7].pos + 5:]
        if keep_id:
            orec = orc_insert.record(base, rec, old['number'])
            otk = sv.tokens(orec, 0, len(orec))
            oid = otk[orcs._desc_start(otk, 0, len(otk))]
            rt = sv.tokens(raw, 0, len(raw))
            nid = rt[orcs._desc_start(rt, 0, len(rt))]
            raw = raw[:nid.pos] + orec[oid.pos:oid.end] + raw[nid.end:]
        k = next(k for k, s in enumerate(starts) if t[s + 1].value == old['number'])
        a = t[starts[k]].pos
        b = t[starts[k + 1]].pos if k + 1 < len(starts) else t[end].pos
        edits.append((a, b, raw))
        log('%-26s №%-4d %-28s ур%-3d -> %-28s (источник №%d, ур%d, %s, %s%s)'
            % (row, old['number'], old['name'] + ' ' + old['title'], old['level'],
               new['name'] + ' ' + new['title'], new['number'], new['level'], new['class'], new['tribe'],
               ', связей снято %d' % rels if rels else ''))
    bp, size = sv.block(base, 'WHDC')
    out, d = base, 0
    for a, b, raw in sorted(edits, reverse=True):     # from the end, so the offsets hold
        out = out[:a] + raw + out[b:]
        d += len(raw) - (b - a)
    out = bytearray(out)
    struct.pack_into('<I', out, bp + 8, size + d)
    struct.pack_into('<I', out, bp + 16, size + d - 4)
    out = bytes(sv.fix_lengths(out, d))
    log('заменено %d на тех же номерах; MainGame %d (не изменился), %+d байт' % (len(edits), n, d))
    return out

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    args = sys.argv[1:]
    opt = lambda k, d: args[args.index(k) + 1] if k in args else d
    regions = [r for r in REGIONS] if opt('--region', 'island') == 'all' else opt('--region', 'island').split(',')
    seed = int(opt('--seed', '1'))
    rows = tuple(opt('--rows', ','.join(ROWS)).split(','))
    pos = [a for i, a in enumerate(args) if not a.startswith('--') and (i == 0 or not args[i - 1].startswith('--'))]
    base_p, src_p, out_p = pos[:3]
    gd = GameData(os.path.join(ROOT, 'app', 'gui', 'data', 'game.gamedb'),
                  os.path.join(ROOT, 'app', 'gui', 'data', 'string_ruru.strdb'))
    base, _ = sv.load(base_p)
    source, _ = sv.load(src_p)
    new, used = base, set()
    for region in regions:
        print('== %s' % REGIONS[region][0])
        new = build(new, source, gd, region, rows, seed, used=used, fresh_only='--fresh-only' in args,
                    keep_id='--keep-id' in args)
    sv.validate(new, 'результат')
    os.makedirs(os.path.dirname(os.path.abspath(out_p)), exist_ok=True)
    sv.write(out_p, new, crypto.user_id_from_name(out_p))
    assert sv.load(out_p)[1] == 0x096c2a9f
    print('Записано:', out_p)
