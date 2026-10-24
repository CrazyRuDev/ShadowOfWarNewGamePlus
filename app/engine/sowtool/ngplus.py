"""New Game Plus: a base save (the start of a new game) plus Talion's progress from a finished game.

Taken from the source save: level and XP (PPDC), skills (IVPD and the PS_ records of the IVMG stock table)
but three (see BLOCKED), all items, gems and mirians (IVMG), the game's options and unlocked looks (GOXC); by the
options of build: towers, collectibles, the start level, the gear cleanup. The base's army gets new orcs from the
source (army.py), and the orcs that troubled Talion most come on the map (returned.py). The story stays as in the
base save. Gem sockets are left empty: the story tutorial asks to put
the first gem in.
"""
import re
import struct

from . import army, orcs, returned, save as sv
from .gamedata import name_hash

# Skills: everything learned goes but three (decided with the user 2026-10-24 after a whole prologue and act 1 with the
# story skills transferred — when the story grants a skill already learned it only marks the grant, experiments
# 25/25b): «Подчинение капитанов» itself (recruiting captains in the prologue and act 1, where the game has no war for
# fortresses; its upgrades go — they are other records), «Подчинение» (Brand, an upgrade of «Истощение») and «Хуже
# смерти» (an upgrade of «Угроза смертью»). No skill points are returned for them: Talion of level 1 earns them fast.
BLOCKED = ('PS_DominateCaptains_', 'PS_Brand_', 'PS_DeathThreat_SuperShame_')
PRESTIGE = ('1Sword_Prestige', '2Dagger_Prestige', '3Bow_Prestige', '4Armor_Prestige', '5Cape_Prestige',
            '6Ring_Prestige')
KEEP_PREFIXES = ('Primary_', 'PrimSnipe_', 'PrimHam_', 'Runegem_', 'Has_')
SKILL_POINT = name_hash('SkillPoint')     # stock entry: unspent skill points (absent when 0)
SWAP = {'Talion_Isildur_Ring': 'Talion_Celebrimbor_Ring', 'AD_Talion_Isildur_Ring': 'AD_Talion_Celebrimbor_Ring'}
# Minas Morgul is left alone while the base has not finished act 1: its story has the player take a tower there
# (with a cutscene). Act 1 is done when the QSTD record Blade10Part25 is 1 (it turns 1 once, at the end of act 1).
ACT1_DONE = name_hash('Blade10Part25')
MINAS = 'MinasIthil'


# the current day of the bundled bases: the day the game writes into new orc history events right after loading
# (orc experiment 29: 8 on the act 2 base; the latest day in its orcs' histories, 16, is not it); the prologue: 0
BASE_DAY = {False: 0, True: 8}


def base_day(base):
    return BASE_DAY[act1_done(base)]


def act1_done(buf):
    t = sv.block_tokens(buf, 'QSTD')
    return any(x.type == 0 and x.value == ACT1_DONE and t[i + 1].value == 1 for i, x in enumerate(t[:-1]))


# towers taken over with the "towers" option: all three in every region (Minas Morgul only after act 1). A tower
# is the stock/IVPD record <region>_Tower_0N, the PDCC counter TowerPurify_<region> (twice) and the IIUC flag
# SeeingStone_<region>_0(N+1).
TOWER_REGIONS = ('MtnPass', 'SnowMtn', 'Volcano', 'Island')
TOWER_NAMES = {'MtnPass': 'Кирит-Унгол', 'SnowMtn': 'Серегост', 'Volcano': 'Горгорот', 'Island': 'Нурн',
               MINAS: 'Минас-Моргул'}


# the tower of Minas Morgul the story itself has the player take in the prologue (with a cutscene; seen in the 2026-10-21
# run): before act 1 is done it stays as in the base, the other two go (the user's wish, 2026-10-24)
STORY_TOWER = 'MinasIthil_Tower_01'


def tower_regions(base):
    return TOWER_REGIONS + (MINAS,)


def tower_skip(base):
    """towers left to the story in this base"""
    return () if act1_done(base) else (STORY_TOWER,)


def tower_re(regions, skip=()):
    return re.compile(r'%s(%s)_Tower_\d+$' % ('(?!(?:%s)$)' % '|'.join(skip) if skip else '', '|'.join(regions)))


def tower_state(regions):
    return (('PDCC', re.compile(r'TowerPurify_(%s)$' % '|'.join(regions))),
            ('IIUC', re.compile(r'SeeingStone_(%s)_\d+$' % '|'.join(regions))))


class Rules:
    """Which skill records go to the new game: every learned skill but BLOCKED."""

    @staticmethod
    def skill(key):
        return key.startswith('PS_') and not key.startswith(BLOCKED)


def _ivpd_pairs(buf):
    """(bytes before Talion's pairs incl. the count token, [(name, raw pair)], bytes after)"""
    p, size = sv.block(buf, 'IVPD')
    t = sv.tokens(buf, p + 20, p + 16 + size)
    i = 1
    while i < len(t):
        owner, count = t[i].value, t[i + 1].value
        if owner == sv.TALION:
            pairs = [(t[i + 2 + 2 * k].value, buf[t[i + 2 + 2 * k].pos:t[i + 3 + 2 * k].end]) for k in range(count)]
            after = t[i + 2 + 2 * count].pos if i + 2 + 2 * count < len(t) else p + 16 + size
            return buf[p + 20:t[i + 1].end], pairs, buf[after:p + 16 + size]
        i += 2 + 2 * count
    raise ValueError('no Talion in IVPD')


def _value(pair):
    """Value of an IVPD pair '00 id 04 value'."""
    return struct.unpack_from('<i', pair, 6)[0]


def _learned(buf, inv):
    """{record id: value} of Talion's skills: IVPD plus the stock table (some are marked only there)."""
    out = sv.unlocks(buf)
    for rid, count, *_ in inv.stock:
        if count > 0:
            out.setdefault(rid, count)
    return out


def _swap(raw):
    for a, b in SWAP.items():
        raw = raw.replace(struct.pack('<I', name_hash(a)), struct.pack('<I', name_hash(b)))
    return raw


def empty_sockets(buf):
    inv = sv.Inventory(buf)
    k = inv._socket_start()
    if k is None:
        return buf, 0
    t = inv.t
    out, n, start = bytearray(), 0, t[k].pos
    for _ in range(8):
        if t[k + 1].value:
            out += buf[t[k].pos:t[k].end] + b'\x0c\x00'
            k += 4
            n += 1
        else:
            out += buf[t[k].pos:t[k + 1].end]
            k += 2
    return _replace_in_blob(buf, start, t[k - 1].end, bytes(out)), n


# tower records the game database has no name string for (SeeingStone_Island_02 is stored only as its hash)
_TOWER_NAMES = {name_hash(n): n for r in TOWER_REGIONS + (MINAS,)
                for n in ['TowerPurify_' + r] + ['SeeingStone_%s_%02d' % (r, k) for k in (1, 2, 3)]}


def _named_values(buf, tag, rec, pattern):
    """[(name, value token)] for every '00 <record> <value>' in a block whose record name matches."""
    t = sv.block_tokens(buf, tag)
    name = lambda v: rec(v) or _TOWER_NAMES.get(v, '')          # noqa: E731
    return [(name(x.value), t[i + 1]) for i, x in enumerate(t[:-1])
            if x.type == 0 and pattern.match(name(x.value)) and t[i + 1].type in (0x04, 0x0C)]


def _set_named(buf, tag, values, rec):
    """Every '00 <record> <value>' of these records in a block set to the given numbers, in place (04 int32 or
    0c byte, same size). Returns (bytes, number of values changed)."""
    out = bytearray(buf)
    n = 0
    pattern = re.compile('(%s)$' % '|'.join(re.escape(k) for k in values)) if values else None
    for name, tok in (_named_values(buf, tag, rec, pattern) if pattern else ()):
        new = _i32(values[name]) if tok.type == 4 else bytes([0x0C, 1 if values[name] else 0])
        if out[tok.pos:tok.end] != new:
            out[tok.pos:tok.end] = new
            n += 1
    return bytes(out), n


def _region_count(picked, pattern):
    return sum(1 for n in picked if re.match(pattern, n))


def copy_tower_state(out, source, rec, regions):
    """Tower counters and flags of these regions from the result's captured towers: TowerPurify_<region> (PDCC, twice)
    = towers taken, SeeingStone_<region>_0(N+1) (IIUC) = 1 for a taken tower _Tower_0N; flags of towers not taken
    stay as in the base. (The source's values are not copied: they may be behind the base's.)"""
    picked = _picked(out, rec)
    counts, flags = {}, {}
    for r in regions:
        taken = [int(m.group(1)) for m in (re.match(r'%s_Tower_(\d+)$' % r, n) for n in picked) if m]
        counts['TowerPurify_' + r] = len(taken)
        flags.update({'SeeingStone_%s_%02d' % (r, k + 1): 1 for k in taken})
    out, a = _set_named(out, 'PDCC', counts, rec)
    out, b = _set_named(out, 'IIUC', flags, rec)
    return out, a + b


# PDCC counters of picked-up collectibles per region (the game shows them as "x of N" for the region)
REGION_COUNTERS = {'ithildin': 'DoorPuzzle_', 'gondor': 'GondorCollectible_', 'shelob': 'ShelobCollectible_'}


def _region_counters(buf, rec, prefix):
    return {name[len(prefix):]: tok.value for name, tok in
            _named_values(buf, 'PDCC', rec, re.compile(re.escape(prefix) + r'[A-Za-z]+$'))}


def sync_region_counters(out, source, gd, kinds, log=print):
    """The PDCC per-region counters after taking collectibles. Ithildin: the words picked up in the region.
    Artifacts and memories: the game data does not say which one lies where, so each region gets the larger of the
    base's and the source's count, and the counts are then evened out to the total picked up."""
    rec = gd.record
    picked = _picked(out, rec)
    regions = (MINAS,) + TOWER_REGIONS
    notes = []
    for kind in kinds:
        prefix = REGION_COUNTERS[kind]
        if kind == 'ithildin':
            want = {prefix + r: _region_count(picked, r'Col_Lore_DoorClue_%s_\d+$' % r) for r in regions}
        else:
            item = 'Col_GondorPickup_' if kind == 'gondor' else 'Col_SpiderPickup_'
            total = sum(1 for n in picked if n.startswith(item) and COLLECTIBLE_RE.match(n))
            have, src = _region_counters(out, rec, prefix), _region_counters(source, rec, prefix)
            v = {r: max(have.get(r, 0), src.get(r, 0)) for r in regions}
            spread = regions
            order = sorted(spread, key=lambda r: src.get(r, 0) - have.get(r, 0), reverse=True)
            while sum(v.values()) < total:             # the source's extra picks: to the regions it has more in
                v[order[0]] += 1
                order = order[1:] + order[:1]
            while sum(v.values()) > total:             # overlap of base and source: back to the base's counts
                r = next((r for r in order if v[r] > have.get(r, 0)), None) or max(spread, key=v.get)
                v[r] -= 1
            want = {prefix + r: v[r] for r in regions}
            notes.append('%s %s' % (prefix.rstrip('_'), ', '.join('%s %d' % (TOWER_NAMES[r], v[r]) for r in regions)))
        out, _ = _set_named(out, 'PDCC', want, rec)
    if notes:
        log('Счётчики регионов (приблизительно — игра не хранит, где лежит каждая вещь): ' + '; '.join(notes))
    return out


# collectibles: (option, record prefix, display name). Picked-up ones go, but never the whole set: one always stays
# in the world (the full set may trigger something - all of Shelob's memories open an ability). Ithildin goes in full
# (it was one word per region left before experiment 28, then by the user's decision none). Story records (GP_*) and barrows are never touched.
COLLECTIBLES = (('ithildin', 'Col_Lore_DoorClue_', 'итильдин'), ('gondor', 'Col_GondorPickup_', 'гондорские артефакты'),
                ('shelob', 'Col_SpiderPickup_', 'воспоминания Шелоб'))
COLLECTIBLE_RE = re.compile(r'Col_(Lore_DoorClue_[A-Za-z]+_\d+|GondorPickup_\d+|SpiderPickup_\d+)$')


def _picked(buf, rec):
    return {rec(r) or '' for r, v in _learned(buf, sv.Inventory(buf)).items() if v > 0}


def _pick_collectibles(base, source, gd, kinds):
    """Names of the source's picked-up collectibles of the chosen kinds that the base does not have yet, so that
    together with the base's own no set is full (one stays in the world)."""
    rec = gd.record
    taken, own = _picked(source, rec), _picked(base, rec)
    out, kept = [], []
    for kind, prefix, _ in COLLECTIBLES:
        if kind not in kinds:
            continue
        every = [n for n in gd.records.values() if n.startswith(prefix) and COLLECTIBLE_RE.match(n)]
        # Was: ithildin per region, one word of every region's door left in the world (5 in all), out of caution.
        # Experiment 28 (2026-10-22): all 6 words of Minas Morgul given before its barrow mission, on the prologue
        # base - the mission, the trial and the verse on the door went fine. So ithildin is now one set for the
        # whole world, and by the user's decision none is left in the world: ithildin goes in full.
        # group = (lambda n: n.rsplit('_', 1)[0]) if kind == 'ithildin' else (lambda n: prefix)
        group = lambda n: prefix
        for g in sorted({group(n) for n in every}):
            total = sum(group(n) == g for n in every)
            have = sum(group(n) == g for n in own if n in every)
            new = sorted(n for n in taken if n in every and group(n) == g and n not in own)
            while kind != 'ithildin' and new and have + len(new) >= total:
                kept.append(new.pop())                   # the last one stays in the world
            out += new
    return out, kept


GONDOR_COUNTER = name_hash('GondorCollectableReward_CombinedItem')   # = number of picked-up Gondor artifacts


def _set_count(buf, rid, count):
    """Stock entry '0c 01 00 rid 04 count 04 1 04 0' and IVPD pair '00 rid 04 count' (replaced or added)."""
    stock = b'\x0c\x01\x00' + struct.pack('<I', rid) + _i32(count) + _i32(1) + _i32(0)
    pair = b'\x00' + struct.pack('<I', rid) + _i32(count)
    return _take_records(buf, None, None, (), extra={rid: (stock, pair)})


def _take_records(base, source, rec, names, extra=None):
    """The source's stock and IVPD entries of these records written into the base (replaced or added).
    extra: {record id: (stock entry bytes, IVPD pair bytes)} to write as well."""
    names = set(names)
    base_inv = sv.Inventory(base)
    take = [(rid, source[s:e]) for rid, count, _, ids, s, e in sv.Inventory(source).stock
            if (rec(rid) or '') in names] if names else []
    take += [(rid, st) for rid, (st, _) in (extra or {}).items()]
    src_raw = dict(take)
    entries = [src_raw.get(rid, base[s:e]) for rid, _, _, _, s, e in base_inv.stock]
    have = {rid for rid, *_ in base_inv.stock}
    entries += [raw for rid, raw in take if rid not in have]
    t = base_inv.t
    head = base[t[0].pos:t[3].pos]
    rest = base[t[base_inv.stock_end_tok].pos:base_inv.blob_end]
    blob = head + b'\x04' + struct.pack('<i', len(entries)) + b''.join(entries) + rest
    p, size = sv.block(base, 'IVMG')
    bt = base_inv.t[0].pos - 5
    ivmg = base[p + 20:bt] + b'\x10' + struct.pack('<I', len(blob)) + blob + base[base_inv.blob_end:p + 16 + size]

    before, base_pairs, after = _ivpd_pairs(base)
    src_pairs = _ivpd_pairs(source)[1] if names else []
    src_map = {rid: raw for rid, raw in src_pairs if (rec(rid) or '') in names}
    src_map.update({rid: pair for rid, (_, pair) in (extra or {}).items()})
    pairs = [(rid, src_map.get(rid, raw)) for rid, raw in base_pairs]
    have = {rid for rid, _ in base_pairs}
    pairs += [(rid, raw) for rid, raw in src_map.items() if rid not in have]
    before = bytearray(before)
    struct.pack_into('<i', before, len(before) - 4, len(pairs))
    ivpd = bytes(before) + b''.join(raw for _, raw in pairs) + after
    return sv.replace_block(sv.replace_block(base, 'IVMG', ivmg), 'IVPD', ivpd)


def _i32(v):
    return b'\x04' + struct.pack('<i', v)


def _shown_at(t):
    """Index of the "shown on the map" list in IIUC tokens. IIUC: 04 16 | (00 SeeingStone_* 0c v) * 16 | 04 5 |
    (00 DoorPuzzle_<region> 04 6 <6 placed> 04 M <M known>) * 5 | 04 N | (04 record 0c 1) * N | 04 counter | ..."""
    i = 1 + 2 * t[0].value
    m = t[i].value
    i += 1
    for _ in range(m):
        k = t[i + 1].value
        i += 2 + k
        i += 1 + t[i].value
    return i


def shown_on_map(buf):
    """Record ids of the IIUC "shown on the map, not picked up" list."""
    t = sv.block_tokens(buf, 'IIUC')
    i = _shown_at(t)
    return [t[i + 1 + 2 * j].value & 0xFFFFFFFF for j in range(t[i].value)]


def _fix_iiuc(buf, rec, taken, show=()):
    """IIUC after taking these collectibles: they leave the "shown on the map" list, and every taken ithildin word
    joins the known words of its region's door puzzle (00 DoorPuzzle_<region> 04 6 <6 placed> 04 M <M known>, the
    known list starts with -1; a word's number is its record number - 1). Placed words stay as they are.
    show: records to add to the "shown on the map" list (map markers)."""
    p, size = sv.block(buf, 'IIUC')
    t = sv.tokens(buf, p + 20, p + 16 + size)
    ids = {name_hash(n) for n in taken}
    add = [name_hash(n) for n in show]
    words = {}
    for n in taken:
        m = re.match(r'Col_Lore_DoorClue_([A-Za-z]+)_(\d+)$', n)
        if m:
            words.setdefault(m.group(1), []).append(int(m.group(2)) - 1)
    list_at = _shown_at(t)
    parts, pos, i = [], p + 20, 0
    while i < len(t):
        x = t[i]
        name = rec(x.value) if x.type == 0 else None
        if name and name.startswith('DoorPuzzle_') and name[11:] in words:
            k = t[i + 1].value
            m_tok = t[i + 2 + k]
            known = [y.value for y in t[i + 3 + k:i + 3 + k + m_tok.value]]
            known += [w for w in sorted(words[name[11:]]) if w not in known]
            end = t[i + 2 + k + m_tok.value].end
            parts.append(buf[pos:m_tok.pos] + _i32(len(known)) + b''.join(_i32(w) for w in known))
            pos, i = end, i + 3 + k + m_tok.value
            continue
        if i == list_at:
            n = x.value
            entries = [(t[i + 1 + 2 * j].value & 0xFFFFFFFF, t[i + 2 + 2 * j]) for j in range(n)]
            keep = [(v, buf[f.pos:f.end]) for v, f in entries if v not in ids]
            have = {v for v, _ in keep}
            keep += [(v, b'\x0c\x01') for v in dict.fromkeys(add) if v not in have and v not in ids]
            parts.append(buf[pos:x.pos] + _i32(len(keep))
                         + b''.join(_i32(v - (1 << 32) if v >= 1 << 31 else v) + flag for v, flag in keep))
            pos, i = t[i + 2 * n].end, i + 1 + 2 * n          # the counter after the list stays as it is
            continue
        i += 1
    parts.append(buf[pos:p + 16 + size])
    return sv.replace_block(buf, 'IIUC', b''.join(parts))


def add_collectibles(out, source, gd, kinds, log=print):
    """Picked-up ithildin / Gondor artifacts / Shelob's memories of the source (kinds: 'ithildin', 'gondor',
    'shelob'), all but one of each set in the whole world; see COLLECTIBLES. Minas Morgul too on a base before act 1
    (experiments 27-28: the story there and its barrow door work with everything picked up); only its towers stay."""
    taken, kept = _pick_collectibles(out, source, gd, kinds)
    # Was: before act 1 no Minas Morgul ithildin (its towers are a story mission there). Experiments 27-28 showed
    # the story takes all the collectibles of Minas Morgul fine, so only its towers stay as in the base now.
    # if not act1:
    #     taken = [n for n in taken if not n.startswith('Col_Lore_DoorClue_%s_' % MINAS)]
    #     kept = [n for n in kept if not n.startswith('Col_Lore_DoorClue_%s_' % MINAS)]
    if taken:
        out = _take_records(out, source, gd.record, taken)
        out = _fix_iiuc(out, gd.record, taken)
    counter = ''
    if 'gondor' in kinds:              # the game counts picked-up artifacts separately (it adds 1 on every pick-up)
        n = sum(1 for x in _picked(out, gd.record) if x.startswith('Col_GondorPickup_') and COLLECTIBLE_RE.match(x))
        if n and sv.Inventory(out).stock_count(GONDOR_COUNTER) != n:
            out = _set_count(out, GONDOR_COUNTER, n)
        counter = '; счётчик подобранных артефактов: %d' % n
    out = sync_region_counters(out, source, gd, kinds, log)
    for kind, prefix, title in COLLECTIBLES:
        if kind in kinds:
            k = [n for n in kept if n.startswith(prefix)]
            log('Коллекции, %s: перенесено %d%s%s' % (title, sum(n.startswith(prefix) for n in taken),
                                                       ' (оставлены в мире, чтобы набор не был полным: %s)'
                                                       % ', '.join(k) if k else '', counter if kind == 'gondor' else ''))
    return out


def _tower_log(out, rec, regions, changed, log, title, skip=()):
    rx = tower_re(regions, skip)
    got = {}
    for rid, count, *_ in sv.Inventory(out).stock:
        m = rx.match(rec(rid) or '')
        if m and count > 0:
            got[m.group(1)] = got.get(m.group(1), 0) + 1
    log('%s: %s%s; значений счётчиков и признаков: %d'
        % (title, ', '.join('%s %d/3' % (TOWER_NAMES[r], got.get(r, 0)) for r in regions),
           ' (Минас-Моргул — кроме сюжетной башни: её захватят в задании пролога)' if skip else '', changed))


def add_marks(out, gd, log=print):
    """Map markers for what the captured towers show: every not picked-up collectible gets one. A region counts as
    open when all its 3 towers are taken (Minas Morgul only after act 1). Ithildin: per open region. Gondor artifacts
    and Shelob's memories have no region in the game data, so they get markers only when every region is open.
    Barrows and story records (GP_*) are not touched; Shelob's final memory gets no marker."""
    rec = gd.record
    picked = _picked(out, rec)
    regions = (MINAS,) + TOWER_REGIONS
    open_ = {r for r in regions if sum(1 for n in picked if re.match(r'%s_Tower_\d+$' % r, n)) >= 3}
    if not act1_done(out):
        open_.discard(MINAS)
    every = [n for n in gd.records.values() if COLLECTIBLE_RE.match(n) and n not in picked]
    marks = []
    for n in sorted(every):
        m = re.match(r'Col_Lore_DoorClue_([A-Za-z]+)_\d+$', n)
        if (m and m.group(1) in open_) or (not m and open_ == set(regions)):
            marks.append(n)
    if marks:
        out = _fix_iiuc(out, rec, (), marks)
    counts = {title: sum(n.startswith(prefix) for n in marks) for _, prefix, title in COLLECTIBLES}
    log('Метки на карте (хэдиры захвачены полностью: %s): %s%s'
        % (', '.join(TOWER_NAMES[r] for r in regions if r in open_) or 'нигде',
           ', '.join('%s %d' % kv for kv in counts.items()),
           '' if open_ == set(regions) else '; артефакты и воспоминания — только когда захвачены все хэдиры мира'))
    return out


def door_puzzles(buf, rec):
    """{region: (placed words, known words)} of the barrow door puzzles in IIUC (-1 = empty)."""
    t = sv.block_tokens(buf, 'IIUC')
    out = {}
    for i, x in enumerate(t):
        n = rec(x.value) if x.type == 0 else None
        if n and n.startswith('DoorPuzzle_'):
            k = t[i + 1].value
            m = t[i + 2 + k].value
            out[n[11:]] = ([y.value for y in t[i + 2:i + 2 + k]], [y.value for y in t[i + 3 + k:i + 3 + k + m]])
    return out


def world_report(buf, gd):
    """Towers and collectibles of a save, for the GUI: regions (towers, ithildin, door words) and collections."""
    rec = gd.record
    picked = _picked(buf, rec)
    doors = door_puzzles(buf, rec)
    every = [n for n in gd.records.values() if COLLECTIBLE_RE.match(n)]
    pd = {n: t.value for n, t in _named_values(buf, 'PDCC', rec, re.compile(
        r'(TowerPurify|DoorPuzzle|GondorCollectible|ShelobCollectible)_[A-Za-z]+$'))}
    regions = []
    for r in (MINAS,) + TOWER_REGIONS:
        towers = sum(1 for n in picked if re.match(r'%s_Tower_\d+$' % r, n))
        ith = [n for n in every if n.startswith('Col_Lore_DoorClue_%s_' % r)]
        placed, known = doors.get(r, ([], []))
        regions.append(dict(region=TOWER_NAMES[r], towers=towers, ithildin=sum(n in picked for n in ith),
                            ithildin_total=len(ith), door_known=sum(1 for w in known if w >= 0),
                            door_placed=sum(1 for w in placed if w >= 0), door_slots=len(placed),
                            # what the game itself counts for the region (PDCC)
                            towers_counter=pd.get('TowerPurify_' + r, 0), ithildin_counter=pd.get('DoorPuzzle_' + r, 0),
                            gondor=pd.get('GondorCollectible_' + r, 0), shelob=pd.get('ShelobCollectible_' + r, 0)))
    inv = sv.Inventory(buf)
    collections = []
    for kind, prefix, title in COLLECTIBLES:
        allk = [n for n in every if n.startswith(prefix)]
        note = ''
        if kind == 'gondor':
            note = 'счётчик игры: %d' % inv.stock_count(GONDOR_COUNTER)
        if kind == 'shelob':
            note = 'последнее воспоминание (способность): %s' % ('да' if 'Col_SpiderPickup_Final' in picked else 'нет')
        collections.append(dict(kind=kind, title=title, have=sum(n in picked for n in allk), total=len(allk), note=note))
    return dict(act1=act1_done(buf), regions=regions, collections=collections)


def add_towers(base, source, gd, log=print):
    """Only the towers of the source written into the base (Minas Morgul only if the base finished act 1); Talion
    and everything else stay as in the base. For a save that already is a New Game Plus."""
    rec = gd.record
    regions, skip = tower_regions(base), tower_skip(base)
    rx = tower_re(regions, skip)
    names = [rec(rid) or '' for rid, *_ in sv.Inventory(source).stock if rx.match(rec(rid) or '')]
    out = _take_records(base, source, rec, names)
    out, changed = copy_tower_state(out, source, rec, regions)
    _tower_log(out, rec, regions, changed, log, 'Только башни', skip)
    return out


def _replace_in_blob(buf, start, end, new):
    """Replaces bytes inside Talion's IVMG nested data and fixes the nested, block and section lengths."""
    inv = sv.Inventory(buf)
    p, size = sv.block(buf, 'IVMG')
    blob_tok = inv.t[0].pos - 5
    d = len(new) - (end - start)
    out = bytearray(buf[:start] + new + buf[end:])
    struct.pack_into('<I', out, blob_tok + 1, inv.blob_end - inv.blob_start + d)
    struct.pack_into('<I', out, p + 8, size + d)
    struct.pack_into('<I', out, p + 16, size + d - 4)
    return sv.fix_lengths(out, d)


def check_pair(base, source, base_name='опорное сохранение', source_name='пройденная игра'):
    """Raises SaveError when the two saves cannot be combined; returns warnings otherwise."""
    if base == source:
        raise sv.SaveError('Опорное сохранение и пройденная игра — одно и то же сохранение. Опорным нужно взять '
                           'начало новой игры (например, сразу после пролога).')
    vb = {t: v for t, v, _, _ in sv.blocks(base, 0)}
    vs = {t: v for t, v, _, _ in sv.blocks(source, 0)}
    diff = ['%s %d/%d' % (t, vb[t], vs[t]) for t in sv.REQUIRED if vb[t] != vs[t]]
    if diff:
        raise sv.SaveError('Сохранения записаны разными версиями игры (версии блоков %s: %s). Возьмите оба '
                           'сохранения из одной версии игры.' % (', '.join(diff), base_name + ' / ' + source_name))
    lb, ls = sv.talion(base)[0], sv.talion(source)[0]
    out = sv.warnings(base, base_name) + sv.warnings(source, source_name)
    if sv.build_number(base) != sv.build_number(source):
        out.append('Сохранения от разных версий игры (1.0.%d и 1.0.%d), но устройство нужных блоков совпадает.'
                   % (sv.build_number(base), sv.build_number(source)))
    if lb > ls:
        out.append('У опорного сохранения уровень %d, у пройденной игры — %d: уровень станет %d. Если сохранения '
                   'перепутаны — вверху окна нужна пройденная игра, опорным — начало новой игры.' % (lb, ls, ls))
    elif ls == lb:
        out.append('Уровень пройденной игры (%d) не выше опорного — переносить почти нечего.' % ls)
    return out


START_BELOW = 2          # start mode: Talion this many levels below the average captain of Nurn


def start_level(base, gd):
    """Talion's level for the start mode: the base after the prologue — the base's own (1, the tutorial); the base
    at the start of act 2 — the median captain of Nurn (where act 2 begins; 13–20 there, median 15) minus
    START_BELOW: a fight with a captain is a challenge from the first minute. The army of a region has its own band
    of levels by the story, whatever Talion's level, so the start is equally hard for every base."""
    if not act1_done(base):
        return sv.talion(base)[0]
    levels = sorted(o['level'] for o in orcs.read(base, gd) if o['faction'] == 'Faction_island'
                    and o['place'] == 'капитан' and not o['dead'] and not o['story'])
    return max(1, levels[len(levels) // 2] - START_BELOW) if levels else sv.talion(base)[0]


def set_item_levels(buf, level):
    """Every item of Talion of a level above 1 (looks and story items are level 1) to this level. Item record in
    Talion's IVMG data: 0c 01 | 04 <number> | 04 <level> | 02 | 00 <template>. Damage and the numbers of the item's
    properties the game derives from the level; in the game an item can be upgraded up to Talion's level."""
    inv = sv.Inventory(buf)
    t = inv.t
    out = bytearray(buf)
    for k in range(inv.stock_end_tok + 1, len(t) - 4):
        if t[k].type == 0x0C and t[k].value == 1 and t[k + 1].type == 4 and t[k + 2].type == 4                 and t[k + 3].type == 2 and t[k + 4].type == 0 and 0 < t[k + 1].value < 1000000                 and 1 < t[k + 2].value < 100:
            struct.pack_into('<i', out, t[k + 2].pos + 1, level)
    return bytes(out)


def _equipped_list(t, i):
    """Token index of the equipped list (04 <slots> then that many slot entries 0c 01 04 <number> | 0c 00) after
    token i, or None."""
    for j in range(i, len(t) - 1):
        n = t[j].value if t[j].type == 4 else 0
        if not 10 <= n <= 64:
            continue
        k, ok = j + 1, True
        for _ in range(n):
            if k < len(t) and t[k].type == 0x0C and t[k].value == 1 and k + 1 < len(t) and t[k + 1].type == 4:
                k += 2
            elif k < len(t) and t[k].type == 0x0C and t[k].value == 0:
                k += 1
            else:
                ok = False
                break
        if ok:
            return j
    return None


# gear that clutters the inventory: common (default, standard) and rare items of the ordinary kinds; the story items
# (PC_Glaive*, PC_Bow_Celebrimbor — the bow Azkâr, Talion_*_Ring, RangerT2_Scabbard) have other templates
CLUTTER = re.compile(r'(Primary|PrimHam|PrimSnipe)_.+_(1Default|2Standard|3Rare)$')


def clean_gear(buf, rec, log=print):
    """Talion's common and rare items that are not equipped removed, as the game removes a sold item (checked on the
    user's save: 52 items sold): the item record goes (it ends where the next one starts, the last one where the
    equipped list starts: 04 <slots> | (0c 01 04 <number> | 0c 00)*slots; the cell count before the item table
    drops by one), its number leaves its stock entry (count - 1), a stock entry left without items goes."""
    inv = sv.Inventory(buf)
    t = inv.t
    starts = [k for k in range(inv.stock_end_tok + 1, len(t) - 4) if t[k].type == 0x0C and t[k].value == 1
              and t[k + 1].type == 4 and t[k + 2].type == 4 and t[k + 3].type == 2 and t[k + 4].type == 0]
    ends = starts[1:] + [_equipped_list(t, starts[-1] + 5) if starts else None]
    equipped = set(inv.equipped)
    cut, gone = [], set()
    for k, e in zip(starts, ends):
        uid = t[k + 1].value
        if e is not None and uid not in equipped and CLUTTER.match(rec(t[k + 4].value) or ''):
            cut.append((t[k].pos, t[e].pos))
            gone.add(uid)
    if not gone:
        return buf
    entries = []
    for rid, count, field, ids, s, e in inv.stock:
        left = [x for x in ids if x not in gone]
        if len(left) == len(ids):
            entries.append(buf[s:e])
        elif left and count - (len(ids) - len(left)) > 0:
            entries.append(b'\x0c\x01\x00' + struct.pack('<I', rid) + b'\x04' + struct.pack('<i', count - (len(ids) - len(left)))
                           + b'\x04' + struct.pack('<i', field) + b'\x04' + struct.pack('<i', len(left))
                           + b''.join(b'\x04' + struct.pack('<i', x) for x in left))
    cells = t[inv.stock_end_tok]
    items, at = [b'\x04' + struct.pack('<i', cells.value - len(gone))], cells.end
    for a, b in cut:
        items.append(buf[at:a])
        at = b
    items.append(buf[at:inv.blob_end])
    blob = buf[t[0].pos:t[3].pos] + b'\x04' + struct.pack('<i', len(entries)) + b''.join(entries) + b''.join(items)
    p, size = sv.block(buf, 'IVMG')
    ivmg = buf[p + 20:inv.t[0].pos - 5] + b'\x10' + struct.pack('<I', len(blob)) + blob + buf[inv.blob_end:p + 16 + size]
    log('Убрано обычное и редкое снаряжение (не надетое): %d шт.' % len(gone))
    return sv.replace_block(buf, 'IVMG', ivmg)


def plan(base, source, gd):
    """What each option of the build would do with this pair, without building — for the cards of the GUI."""
    rec = gd.record
    act1 = act1_done(base)
    regions = tower_regions(base)
    rx = tower_re(regions, tower_skip(base))
    towers = sum(1 for rid, *_ in sv.Inventory(source).stock if re.match(r'.+_Tower_\d+$', rec(rid) or '')
                 and rx.match(rec(rid) or ''))
    collect = {}
    for kind, _, _ in COLLECTIBLES:
        taken, kept = _pick_collectibles(base, source, gd, [kind])
        collect[kind] = len(taken)
    inv = sv.Inventory(source)
    equipped = set(inv.equipped)
    clutter = sum(1 for it in inv.items if it['uid'] not in equipped and CLUTTER.match(rec(it['template']) or ''))
    learned = {rec(r) or '' for r, v in _learned(source, inv).items() if v > 0}
    blocked = sorted({gd.skill(k) or k for k in learned if k.endswith('_UNLOCK') and k.startswith(BLOCKED)})
    return dict(act1=act1, base_level=sv.talion(base)[0], source_level=sv.talion(source)[0],
                start_level=start_level(base, gd), towers=towers, collect=collect, clutter=clutter,
                items=len(inv.items), blocked=blocked, army=army.count(base, gd),
                twenty={n: returned.count(base, gd, act1, source, n) for n in returned.COUNTS},
                picked=len(orcs.recommend(orcs.read(source, gd))))


# the game's options (the menus: field of view, HUD, sound, controls, language) and the unlocked looks (Skin_*)
# live in the save too: block GOXC before the sections, entries 00 <name> | 02 <0/1/2> | 0c <flag> / 0a <float> /
# 08 <u32>. They always go from the finished game (decided with the user) but the save slot numbers.
SETTINGS_KEEP = ('SS_',)
_SETTING_SIZE = {0x0C: 1, 0x0A: 4, 0x08: 4}


def settings(buf, rec):
    """{name: (offset of the value, type)} of the GOXC block."""
    i = buf.find(b'GOXC')
    if i < 0:
        return {}
    size = struct.unpack_from('<I', buf, i + 8)[0]
    out, j, end = {}, i + 16, i + 16 + size
    while j < end - 8:
        if buf[j] == 0 and buf[j + 5] == 2 and buf[j + 6] in (0, 1, 2) and buf[j + 7] in _SETTING_SIZE:
            name = rec(struct.unpack_from('<I', buf, j + 1)[0])
            if name:
                out[name] = (j + 8, buf[j + 7])
                j += 8 + _SETTING_SIZE[buf[j + 7]]
                continue
        j += 1
    return out


def copy_settings(out, source, gd, log=print):
    """The finished game's options and looks into the new game (same sizes, values only)."""
    rec = gd.record
    mine, theirs = settings(out, rec), settings(source, rec)
    out, changed = bytearray(out), []
    for name, (pos, ty) in mine.items():
        if name.startswith(SETTINGS_KEEP) or name not in theirs or theirs[name][1] != ty:
            continue
        sp = theirs[name][0]
        n = _SETTING_SIZE[ty]
        if out[pos:pos + n] != source[sp:sp + n]:
            out[pos:pos + n] = source[sp:sp + n]
            changed.append(name)
    log('Настройки игры и облики из пройденной игры: изменено %d из %d (%s)'
        % (len(changed), len(mine), ', '.join(changed[:12]) + ('…' if len(changed) > 12 else '') or 'всё уже так'))
    return bytes(out)


def build(base, source, gd, log=print, towers=False, collect=(), start=False, clean=False,
          new_army=False, twenty=False, twenty_count=returned.DEFAULT_COUNT, weak='none'):
    """New Game Plus save bytes. towers: also take over the towers (Minas Morgul only after act 1); collect:
    picked-up collectibles of these kinds ('ithildin', 'gondor', 'shelob'), see add_collectibles; start: Talion and
    his gear at the level of the new
    game (see start_level) instead of the finished game's — the skills stay, the levels are earned again; clean:
    the common and rare gear that is not equipped removed (see clean_gear); the skills: all learned but BLOCKED;
    new_army: the random orcs of the base's army that the game has not put into the world
    yet replaced with orcs of the finished game that never met Talion (see army); twenty: the orcs that troubled
    Talion most come back — the top three in Nurn, bosses of Gorgoroth and Seregost by ambush, captains of Cirith
    Ungol (after the prologue) and Nurn (see returned.PLACES), twenty_count of them (returned.COUNTS), with
    the weaknesses `weak` taken off (returned.WEAK). The game's options always go."""
    rec = gd.record
    src_inv, base_inv = sv.Inventory(source), sv.Inventory(base)
    rules = Rules()
    src_raw = {rid: (count, source[s:e]) for rid, count, _, _, s, e in src_inv.stock}

    regions = tower_regions(base)
    rx = tower_re(regions, tower_skip(base))

    def tower(name):
        return towers and bool(rx.match(name))

    def keep(name):
        return rules.skill(name) or name.startswith(KEEP_PREFIXES) or name == 'PC_Mirian' or name in PRESTIGE \
            or tower(name)

    # stock table: base entries without items (taking the source value for transferred records; for skills
    # the larger one, so a skill the base already has stays), then every source entry that holds items or
    # is a skill, gem, mirians, "has acquired" flag or prestige
    entries, seen = [], set()
    for rid, count, _, ids, s, e in base_inv.stock:
        if ids:
            continue
        name = rec(rid) or ''
        raw = base[s:e]
        if rid in src_raw and keep(name) and not (name.startswith('PS_') and src_raw[rid][0] < count):
            raw = src_raw[rid][1]
        entries.append(raw)
        seen.add(rid)
    blocked = []
    for rid, _, _, ids, s, e in src_inv.stock:
        if rid in seen:
            continue
        name = rec(rid) or ''
        if ids or keep(name):
            entries.append(_swap(source[s:e]))
            seen.add(rid)
        elif name.startswith('PS_'):
            blocked.append(name)
    # skill points: none — the source's unspent ones are not carried (after a few runs of new game+ they would only pile
    # up) and none are returned for the BLOCKED skills (decided with the user 2026-10-24)
    points = 0
    entries = [e for e in entries if e[3:7] != struct.pack('<I', SKILL_POINT)]
    if points:
        entries.append(b'\x0c\x01\x00' + struct.pack('<I', SKILL_POINT) + b'\x04' + struct.pack('<i', points)
                       + b'\x04\x00\x00\x00\x00\x04\x00\x00\x00\x00')
    t = src_inv.t
    head = source[t[0].pos:t[3].pos]                 # 05 pair, skin, next item number
    rest = _swap(source[t[src_inv.stock_end_tok].pos:src_inv.blob_end])
    blob = head + b'\x04' + struct.pack('<i', len(entries)) + b''.join(entries) + rest

    # IVMG: the base block with Talion's nested data replaced
    p, size = sv.block(base, 'IVMG')
    bt = base_inv.t[0].pos - 5
    ivmg = base[p + 20:bt] + b'\x10' + struct.pack('<I', len(blob)) + blob + base[base_inv.blob_end:p + 16 + size]

    # IVPD: base pairs (with source values for transferred skills) plus the source's other skills
    before, base_pairs, after = _ivpd_pairs(base)
    _, src_pairs, _ = _ivpd_pairs(source)
    src_map = dict(src_pairs)
    pairs = [(rid, src_map[rid] if rid in src_map and keep(rec(rid) or '') and _value(src_map[rid]) >= _value(raw)
              else raw) for rid, raw in base_pairs]
    have = {rid for rid, _ in base_pairs}
    for rid, raw in src_pairs:
        name = rec(rid) or ''
        if rid not in have and (rules.skill(name) or tower(name)):
            pairs.append((rid, raw))
    # the unspent points are kept twice: the stock entry and an IVPD pair; on loading the game sets the stock entry
    # to the IVPD value (the act 2 base had 0 there — the points vanished on the first save), so both get them
    pairs = [(rid, raw) for rid, raw in pairs if rid != SKILL_POINT]
    if points or any(rid == SKILL_POINT for rid, _ in base_pairs):
        pairs.append((SKILL_POINT, b'\x00' + struct.pack('<I', SKILL_POINT) + b'\x04' + struct.pack('<i', points)))
    before = bytearray(before)
    struct.pack_into('<i', before, len(before) - 4, len(pairs))
    ivpd = bytes(before) + b''.join(raw for _, raw in pairs) + after

    # PPDC: level - 1 and XP of Talion
    level, xp = sv.talion(source)
    if start:
        level, xp = start_level(base, gd), 0
    pt = sv.block_tokens(base, 'PPDC')
    pp, psize = sv.block(base, 'PPDC')
    ppdc = bytearray(base[pp + 20:pp + 16 + psize])
    for i, tok in enumerate(pt):
        if tok.type == 0 and tok.value == sv.TALION:
            struct.pack_into('<i', ppdc, pt[i + 1].pos + 1 - (pp + 20), level - 1)
            struct.pack_into('<i', ppdc, pt[i + 2].pos + 1 - (pp + 20), xp)

    out = base
    for tag, content in (('IVMG', ivmg), ('IVPD', ivpd), ('PPDC', bytes(ppdc))):
        out = sv.replace_block(out, tag, content)
    out, n = empty_sockets(out)
    if clean:
        out = clean_gear(out, rec, log)
    if start:
        out = set_item_levels(out, level)
        log('Начало с уровня новой игры: Талион и снаряжение — уровень %d (пройденная игра: %d)'
            % (level, sv.talion(source)[0]))
    if towers:
        out, changed = copy_tower_state(out, source, rec, regions)
        _tower_log(out, rec, regions, changed, log, 'Башни', tower_skip(base))

    if collect:
        out = add_collectibles(out, source, gd, collect, log)
    if towers:                                    # what the captured towers show on the map
        out = add_marks(out, gd, log)
    brought = ()
    if twenty:                                   # before the army: it fills the places left
        out, numbers = returned.place(out, source, gd, act1_done(base), twenty_count, weak, orcs.PAST_DAY, log)
        brought = {o['number'] for o, _, _ in numbers.values()}
    if new_army:
        out = army.replace(out, source, gd, orcs.PAST_DAY, log, brought)
    out = copy_settings(out, source, gd, log)

    blocked_names = sorted({gd.skill(k) or k for k in blocked if k.endswith('_UNLOCK')})
    log('Уровень %d, опыт %d; записей запасов %d, навыков %d; освобождено слотов самоцветов: %d'
        % (level, xp, len(entries), len(pairs), n))
    log('Навыки перенесены все, кроме закрытых: %s (их выдаст сюжет); очки навыков не переносятся'
        % (', '.join(blocked_names) or 'в пройденной игре их не было'))
    return out
