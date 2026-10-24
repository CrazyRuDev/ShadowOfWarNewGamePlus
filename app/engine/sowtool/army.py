"""A new army: the random orcs of the base's hierarchies replaced with orcs of the finished game that never met
Talion. Researched in research/orc_replace.py, experiments 29-36 (CLAUDE.md).

Who is replaced: an orc on a captain's or warchief's place (never the overlord) that the game generates anew in
every new game. Two fresh new games showed every fixed character carries WasEverPresetFactionMember (Bruz, the
Ranger, the nazgul, the Gondorians, Krimp the prologue's first captain...); so an occupant is kept when it has that
flag, IgnorePlayerLevelRestriction or PlayerFollower, a story AI (not AI_*), a story reason, met Talion or is dead.
Also kept: an orc the game already put into the world (its _NPC_ id is set) — replacing those in Cirith Ungol, the
region of act 1, crashed the game on loading (experiments 31-35); on the prologue base none is, on the act 2 base
Cirith Ungol, Minas Morgul and half of Gorgoroth are.
Who comes first (decided with the user 2026-10-24, "the same orcs on the same places"): the living enemies of the
source that stand in a region's hierarchy (captain or warchief; not followers, not story, not the ones returned.place
already took) go to the fresh places of their own region — a warchief to a warchief's place (else a captain's), a
captain to a captain's; level = the replaced orc's (the region's band), the history of past games thinned as for
the returned orcs (orcs.HISTORY); one its region has no place for does not come at all. The places left:
a living orc of the source that never met Talion (no Talion event, not even an indirect '*Player*' one),
not preset, not a follower, AI_* class, a generated name; about a third of a region from its overlord's tribe.
What is done to it: it takes the replaced orc's number and cell in MainGame (the Nemesis missions on the map and the
hierarchy table point at that number), its region becomes the base's, its place = the row, its level = the
replaced orc's (both copies), history days = the base's day (see build: current day - 5), its relation list
emptied, the flags of having been seen cleared. Title, traits, personality, looks stay — the lines depend on them.
"""
import random
import re
import struct

from . import orcs, save as sv
from .gamedata import name_hash

# region key -> (faction of the hierarchy table and the orcs, prefix of its rows)
REGIONS = {'MinasIthil': ('Faction_MinasIthil', 'MinasIthil'), 'island': ('Faction_island', 'island'),
           'MtnPass': ('Faction_MtnPass', 'MtnPass'), 'snowMtn': ('Faction_snowMtn', 'snowMtn'),
           'volcano': ('Faction_volcano', 'volcano'), 'desert': ('Faction_desert_Real', 'desert')}
ROWS = ('Captain', 'Outer_Warchief', 'Inner_Warchief')
KEEP_FLAGS = {'WasEverPresetFactionMember', 'IgnorePlayerLevelRestriction', 'PlayerFollower'}
CLEAR_FLAGS = ('PresentedToPlayer', 'CameraPresented', 'IdentityPresented', 'SimEventActive', 'Vow', 'RevengeTarget',
               'ResurrectedThisSpawn')
TRIBE_SHARE = 1 / 3
SEED = 1                                 # the same pair of saves always gives the same army


# what an event of the past becomes when the transfer thins the history: «ушёл» (in many histories, not in the score)
NEUTRAL = 'ActiveDespawn_AllCases'

def _table(buf, rec):
    """(tokens, record start token indexes, end token index of the table) of MainGame."""
    t, ranges = orcs.table(buf, rec)
    return t, [s for s, _ in ranges], ranges[-1][1]


def _record(buf, t, starts, end, number):
    k = next(k for k, s in enumerate(starts) if t[s + 1].value == number)
    a = t[starts[k]].pos
    b = t[starts[k + 1]].pos if k + 1 < len(starts) else t[end].pos
    return a, b


def _hierarchy(t, rec, faction, prefix):
    """{row name: [token index of each place]} of a region's hierarchy table: 00 Faction | 04 | 04 | 04 <rows> |
    (00 <prefix>_Row_<row> | 04 <places> | 04 <orc or -1> * places) * rows."""
    for i in range(len(t) - 4):
        if t[i].type == 0 and rec(t[i].value) == faction and t[i + 1].type == 4 and t[i + 2].type == 4 \
                and t[i + 3].type == 4 and t[i + 4].type == 0 and (rec(t[i + 4].value) or '').startswith(prefix + '_Row_'):
            out, j = {}, i + 4
            for _ in range(t[i + 3].value):
                row, places = rec(t[j].value), t[j + 1].value
                out[row] = list(range(j + 2, j + 2 + places))
                j += 2 + places
            return out
    return {}


def _name_keys(buf, rec):
    t, ranges = orcs.table(buf, rec)
    return {t[s + 1].value: rec(t[s + 3].value) or '' for s, _ in ranges}


def _random_orc(o, name_key):
    """An orc the game generates anew in every new game (see the module doc)."""
    return (not o['met'] and not o['dead'] and not set(o['flags']) & KEEP_FLAGS and o['ai'].startswith('AI_')
            and 'NameGen' in name_key and not o['story'])


def _candidate(o, name_key):
    return _random_orc(o, name_key) and not o['follower'] and not any('Player' in ev for ev, _ in o['history'])


def _prepare(raw, number, faction, row, level, day, rec, thin=False):
    """The source record made the base's orc number `number` on `row`. Its history gets day `day` (orcs.PAST_DAY: the
    past of the new game). thin: of the events of past games (already day PAST_DAY) the score counts, half of each
    kind become a neutral one (NEUTRAL, same size) — the past fades by half with every transfer (orcs.HISTORY
    'decay'); the events of the game just finished stay whole."""
    raw = bytearray(raw)
    struct.pack_into('<i', raw, 3, number)
    t = sv.tokens(bytes(raw), 0, len(raw))
    src = next(x.value for x in t if x.type == 0 and (rec(x.value) or '').startswith('Faction_'))
    for x in t:
        if x.type == 0 and x.value == src:
            raw[x.pos + 1:x.pos + 5] = struct.pack('<I', name_hash(faction))
    assert t[7].type == 0                     # 0c 01 | 04 n | 09 | 08 name | 00 | 00 | 00 AI | 00 place
    raw[t[7].pos + 1:t[7].pos + 5] = struct.pack('<I', name_hash(row))
    d = orcs._desc_start(t, 0, len(t))
    struct.pack_into('<I', raw, t[d + 8].pos + 1, level - 1)          # 08 <level-1> | 04 <level-1>
    struct.pack_into('<i', raw, t[d + 9].pos + 1, level - 1)
    # the history: the longest unbroken run of 00 <event> 03 <day> (the death record further on is left)
    pair = [t[k].type == 0 and t[k].value and rec(t[k].value) and t[k + 1].type == 3 for k in range(len(t) - 1)]
    best, k = (0, 0), 0
    while k < len(pair):
        j = k
        while j < len(pair) and pair[j]:
            j += 2
        if (j - k) // 2 > best[1]:
            best = (k, (j - k) // 2)
        k = j + 1 if j == k else j
    seen = dict.fromkeys(orcs.SCORED, 0)
    for n in range(best[1]):
        ev, dt = t[best[0] + 2 * n], t[best[0] + 2 * n + 1]
        k = orcs.event_kind(rec(ev.value) or '')
        if thin and k in seen and dt.value == orcs.PAST_DAY:
            seen[k] += 1
            if (seen[k] + number) % 2 == 0:         # an odd count rounds down or up by the orc's new number:
                                                    # half on average, a single past event fades too
                raw[ev.pos + 1:ev.pos + 5] = struct.pack('<I', name_hash(NEUTRAL))
        struct.pack_into('<h', raw, dt.pos + 1, day)
    f = next(x for x in t[d:] if x.type == 0x05)
    bits = int.from_bytes(raw[f.pos + 1:f.pos + 9], 'little')
    for name in CLEAR_FLAGS:
        bits &= ~(1 << orcs.FLAGS.index(name))
    raw[f.pos + 1:f.pos + 9] = bits.to_bytes(8, 'little')
    # relations: 04 <count> at TraitLevelOffset_* + 15, then (0c 01 | 00 | 00 | 04 | 00 | 04) * count
    tlo = next((k for k, x in enumerate(t) if x.type == 0 and (rec(x.value) or '').startswith('TraitLevelOffset_')),
               None)
    if tlo is None:                       # preset characters (a Nazgul) have no such list
        return bytes(raw)
    c = t[tlo + 15]
    assert c.type == 4
    if c.value:
        raw = raw[:c.pos] + b'\x04' + struct.pack('<i', 0) + raw[t[tlo + 15 + 6 * c.value].end:]
    return bytes(raw)


def _targets(base, gd):
    """{region key: [(row, old orc)]} of the places to fill, and the base's orcs by number."""
    rec = gd.record
    army = {o['number']: o for o in orcs.read(base, gd)}
    names = _name_keys(base, rec)
    t, _, _ = _table(base, rec)
    out = {}
    for key, (faction, prefix) in REGIONS.items():
        for row, cells in _hierarchy(t, rec, faction, prefix).items():
            if re.sub(r'_\d+$', '', row.split('_Row_')[1]) not in ROWS:
                continue
            for c in cells:
                o = army.get(t[c].value)
                if o and _random_orc(o, names[o['number']]) and not o['npc']:
                    out.setdefault(key, []).append((row, o))
    return out, army


def count(base, gd):
    """{region name: places to fill} — for the plan in the GUI."""
    targets, _ = _targets(base, gd)
    return {orcs.REGIONS[REGIONS[k][0]]: len(v) for k, v in targets.items() if v}


def _enemy(o, key_of):
    """A living enemy of the source on a captain's or warchief's place of a region of REGIONS."""
    return (not o['dead'] and not o['follower'] and not o['story'] and not set(o['flags']) & KEEP_FLAGS
            and o['faction'] in key_of and o['place'] in ('капитан', 'вождь'))


def replace(base, source, gd, day, log=print, exclude=()):
    """exclude: numbers of source orcs already brought by returned.place."""
    rec = gd.record
    rng = random.Random(SEED)
    targets, army = _targets(base, gd)
    s_orcs = orcs.read(source, gd)
    s_names = _name_keys(source, rec)
    ids = {o['npc'] for o in army.values() if o['npc']}           # never two orcs with one _NPC_ id
    s_orcs = [o for o in s_orcs if o['number'] not in exclude and not (o['npc'] and o['npc'] in ids)]
    key_of = {f: k for k, (f, _) in REGIONS.items()}
    key_of['Faction_desert'] = 'desert'                             # Lithlad's orcs of some saves
    # an enemy on a place shows only in its own region: one its region had no place for stays out
    pool = [o for o in s_orcs if _candidate(o, s_names[o['number']]) and not _enemy(o, key_of)]
    t, starts, end = _table(base, rec)
    st = _table(source, rec)
    used, edits, counts, own = set(), [], {}, {}
    thin = orcs.HISTORY == 'decay'
    for o in sorted((o for o in s_orcs if _enemy(o, key_of)), key=lambda o: (o['place'] != 'вождь', -o['level'])):
        places = targets.get(key_of[o['faction']], [])
        fit = [p for p in places if ('Warchief' in p[0]) == (o['place'] == 'вождь')] or             [p for p in places if 'Warchief' not in p[0]]
        if not fit:
            continue
        row, old = fit[0]
        places.remove(fit[0])
        used.add(o['number'])
        sa, sb = _record(source, *st, o['number'])
        raw = _prepare(source[sa:sb], old['number'], REGIONS[key_of[o['faction']]][0], row, old['level'], day, rec,
                       thin)
        edits.append((*_record(base, t, starts, end, old['number']), raw))
        own[o['region']] = own.get(o['region'], 0) + 1
    for key, places in targets.items():
        faction = REGIONS[key][0]
        over = next((army[t[c].value] for row, cells in _hierarchy(t, rec, *REGIONS[key]).items()
                     if row.endswith('_Row_Overlord') for c in cells if t[c].value in army), None)
        tribe = over['tribe_key'] if over else ''
        free = [o for o in pool if o['number'] not in used]
        same = [o for o in free if o['tribe_key'] == tribe]
        other = [o for o in free if o['tribe_key'] != tribe]
        rng.shuffle(same)
        rng.shuffle(other)
        k_same = min(len(same), round(len(places) * TRIBE_SHARE))
        chosen = same[:k_same] + other[:len(places) - k_same]
        rng.shuffle(chosen)
        for (row, old), new in zip(places, chosen):
            used.add(new['number'])
            sa, sb = _record(source, *st, new['number'])
            raw = _prepare(source[sa:sb], old['number'], faction, row, old['level'], day, rec)
            edits.append((*_record(base, t, starts, end, old['number']), raw))
        counts[orcs.REGIONS[faction]] = len(chosen)
    bp, size = sv.block(base, 'WHDC')
    out, d = base, 0
    for a, b, raw in sorted(edits, reverse=True):                    # from the end, so the offsets hold
        out = out[:a] + raw + out[b:]
        d += len(raw) - (b - a)
    out = bytearray(out)
    struct.pack_into('<I', out, bp + 8, size + d)
    struct.pack_into('<I', out, bp + 16, size + d - 4)
    out = bytes(sv.fix_lengths(out, d))
    log('Армия: враги пройденной игры на своих местах (капитаны и вожди своего региона) — %d (%s)'
        % (sum(own.values()), ', '.join('%s %d' % kv for kv in own.items()) or 'нет'))
    log('Армия: орков пройденной игры, не встречавших Талиона, на оставшиеся места — %d (%s); кандидатов было %d'
        % (sum(counts.values()), ', '.join('%s %d' % kv for kv in counts.items() if kv[1]) or 'некуда', len(pool)))
    return out
