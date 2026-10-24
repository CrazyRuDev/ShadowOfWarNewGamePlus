"""Experiment 52: the whole twenty of the finished game straight onto the map of Nurn, no ambushes.

    python research/orc_twenty.py <base> <source> <out> [seed]

The twenty is orcs.recommend of the source; they take the Nurn cells the game has not put into the world yet,
warchief cells first (the most dangerous), then the captain cells. Each gets a random level 40–50.
  - killed by Talion: "came back beforehand" (orc_returned_looks): a scar role by the cause of death (poison →
    Defaced, fire → Burned, an arm cut off → Claw, an arrow → RazorJaw, the head/troll/lower body → IronSkull, the
    rest and Ologs → Slashface), its reward, the looks and the voice of the return;
  - killed by orcs or alive: alive as they were (death flags and the follower flags off).
Traits: fatal weaknesses (*MortalVulnerable) and fears (Picker_Fear_*, Picker_Terror_*) are removed, the plain
weaknesses stay. The trait list is 04 n | (00 Picker_* | 00)*n.
"""
import os
import random
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app', 'engine'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sowtool import army, crypto, ngplus, orcs, save as sv   # noqa: E402
from sowtool.gamedata import GameData                         # noqa: E402
from orc_returned_looks import (HEAD_OVERLAY, OVERLAY, REWARDS, donors, head_overlay, looks, name, overlay,  # noqa
                                returned)

COMPARE = {27: 'Defaced',   # experiment 56: Khoshgrish stays Defaced to compare with Mozu's Blight (both poisoned)
           486: 'BagHead',   # experiment 57: an arrow of Talion — the game's list has BagHead, not RazorJaw
           # experiment 59, from the game's lists: a troll → Beast, a blade → Unkillable / Survivor, an arm → Stormbringer
           218: 'Beast', 208: 'Unkillable', 280: 'Survivor', 377: 'Stormbringer',
           403: 'Specter', 381: 'Infested'}   # not in the lists for their deaths — to see the looks only
# experiment 58, a catalogue of overlay items in the scar slot (no samples in any save), by source number
OVERLAYS = {471: 'orc_Left_Eye_Gouge', 498: 'orc_cuts_head_01', 257: 'orc_mauled_head_01', 27: 'orc_facepeel_head_01',
            218: 'orc_tornFace_head', 486: 'orc_curse_head_face', 318: 'orc_Shame', 286: 'orc_undead',
            17: 'orc_maggot_body_01', 381: 'orc_Stormbringer_OldScar', 62: 'orc_Slayer_Face_Scar',
            280: 'orc_bullet_healed_head_01', 130: 'orc_eyewound_head_LEye', 73: 'orc_eyes_Metal_Leye',
            403: 'orc_metalHead_head', 238: 'orc_sores_head', 377: 'orc_stitched_cut_body_LElbow',
            207: 'orc_eyes_cataracts', 208: 'orc_trickster_head_face'}
# experiment 57 (the face scar field draws nothing — kept for the record, not used)
FACES_57 = {471: 'Poison', 498: 'Slashface_CutsFace', 257: 'AxeHead', 27: 'Poison', 218: 'ExposedBrain',
         318: 'EyeGouge', 286: 'Branded_Slave', 17: 'Facepeele', 381: 'Curse', 62: 'Mauled', 280: 'Slashface_CutsFace',
         130: 'BruisedEyes', 73: 'CutsHead', 403: 'DaggerHead', 238: 'Burns', 377: 'Shamed', 207: 'Metal_Head',
         208: 'Resurrected_PlayerAbility_RaiseDead'}
DEAD_FLAGS = ('IsDead', 'CanResurrect', 'KilledByPlayer', 'IsDeadMockMember', 'SeveredHead')
FOLLOWER_FLAGS = (8, 27, 28, 29)   # Dominated, PlayerFollower, Spy, PlayerBodyguard


def scar(cause, olog=False, berserker=False):
    """The scar by the cause of death. Ologs: only the metal plate and body scars are known for their model.
    Berserkers hold two axes — an arm prosthetic never shows on them."""
    if cause.startswith('HeadRemoved') or cause == 'Troll':
        return 'IronSkull'
    if olog:
        return 'Slashface'
    if cause.startswith('Poison'):        # the game: Blight; Defaced also speaks of poison
        return 'Blight'
    if cause.startswith('Fire'):          # the game turns those burned to death into FlameOfWar
        return 'FlameOfWar'
    if cause == 'LowerBody':              # «Ты рассек меня пополам…» — the line of Machine
        return 'Machine'
    if 'ArmLower_Removed' in cause and not berserker:   # all of ours lost the left arm: the left claw
        return 'Claw'
    if cause == 'PlayerArrow':
        return 'RazorJaw'
    return 'Slashface'                   # a blade, cut in half, an arm of a berserker…


def removed(n):
    return 'MortalVulnerable' in n or n.startswith(('Picker_Fear_', 'Picker_Terror_'))


def traits(raw, rec):
    """Drop the removed traits from every trait list of the record; returns (raw, names dropped)."""
    t = sv.tokens(bytes(raw), 0, len(raw))
    edits, gone = [], []
    for c in range(len(t) - 2):
        if t[c].type != 4 or not (name(t[c + 1], rec) or '').startswith('Picker_'):
            continue
        n = t[c].value
        if not all((name(t[c + 1 + 2 * k], rec) or '').startswith('Picker_') for k in range(n)):
            continue
        drop = [k for k in range(n) if removed(name(t[c + 1 + 2 * k], rec))]
        for k in drop:
            a = t[c + 1 + 2 * k]
            edits.append((a.pos, t[c + 3 + 2 * k].pos, b''))
            gone.append(name(a, rec))
        if drop:
            edits.append((t[c].pos + 1, t[c].pos + 5, struct.pack('<i', n - len(drop))))
    raw = bytearray(raw)
    for a, b, new in sorted(edits, key=lambda e: e[0], reverse=True):
        raw[a:b] = new
    return bytes(raw), gone


def alive(raw):
    raw = bytearray(raw)
    t = sv.tokens(bytes(raw), 0, len(raw))
    d = orcs._desc_start(t, 0, len(t))
    f = next(x for x in t[d:] if x.type == 0x05)
    bits = int.from_bytes(raw[f.pos + 1:f.pos + 9], 'little')
    for k in [orcs.FLAGS.index(n) for n in DEAD_FLAGS] + list(FOLLOWER_FLAGS):
        bits &= ~(1 << k)
    raw[f.pos + 1:f.pos + 9] = bits.to_bytes(8, 'little')
    return bytes(raw)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    base_p, src_p, out_p = sys.argv[1:4]
    seed = int(sys.argv[4]) if len(sys.argv) > 4 else random.randrange(1 << 30)
    rnd = random.Random(seed)
    gd = GameData(os.path.join(ROOT, 'app', 'gui', 'data', 'game.gamedb'),
                  os.path.join(ROOT, 'app', 'gui', 'data', 'string_ruru.strdb'))
    rec = gd.record
    base, source = sv.load(base_p)[0], sv.load(src_p)[0]
    # the jaw slot: Bolg «Железная Челюсть» of the history (the finished save has no such slot)
    jaw = os.path.join(ROOT, 'game files', 'история', '096c2a9f_ShadowOfWar_20261020-085254.sav')
    olog = os.path.join(ROOT, 'game files', 'история', '096c2a9f_ShadowOfWar_20261022-171608.sav')   # Olog plate
    donor = donors([source, sv.load(jaw)[0], sv.load(olog)[0]], gd)
    targets, _ = army._targets(base, gd)
    cells = sorted(targets['island'], key=lambda c: 'Warchief' not in c[0])
    twenty = orcs.recommend(orcs.read(source, gd))
    assert len(cells) >= len(twenty), (len(cells), len(twenty))
    st = army._table(source, rec)
    day = max(0, ngplus.base_day(base) - 5)
    put = []
    for o, (row, old) in zip(twenty, cells):
        level = rnd.randint(40, 50)
        sa, sb = army._record(source, *st, o['number'])
        raw = army._prepare(source[sa:sb], old['number'], 'Faction_island', row, level, day, rec)
        if o['dead'] and o['killer_name'] == 'Талион':
            names = {rec(x.value) for x in sv.tokens(raw, 0, len(raw)) if x.type == 0 and x.value is not None}
            s = scar(o['death_cause'], any((n or '').startswith('OlogHai_') for n in names), 'Orc_Berserker' in names)
            s = COMPARE.get(o['number'], s)
            raw, role = looks(raw, s, donor, rec)
            raw = returned(raw, role, REWARDS.get(s, 'ResReward_PinnicleScar_' + s), rec)
            how = 'вернулся заранее, ' + s
            if s in OVERLAY and not any((n or '').startswith('OlogHai_') for n in names):
                raw = overlay(raw, OVERLAY[s], donor, rec)
                how += ' + ' + OVERLAY[s]
            if s in HEAD_OVERLAY:
                raw2 = head_overlay(raw, HEAD_OVERLAY[s], rec)
                if raw2 != raw:
                    raw, how = raw2, how + ' + голова ' + HEAD_OVERLAY[s]
        else:
            raw = alive(raw)
            how = 'живой' if not o['dead'] else 'живой (был убит: %s)' % o['killer_name']
        raw, gone = traits(raw, rec)
        put.append((old['number'], raw, o, row, old['name'], how, gone))
    out = bytearray(base)
    t2, starts, end = army._table(base, rec)
    spans = [(army._record(base, t2, starts, end, n), raw) for n, raw, *_ in put]
    dd = 0
    for (a, b), raw in sorted(spans, key=lambda s: s[0][0], reverse=True):
        out[a:b] = raw
        dd += len(raw) - (b - a)
    bp, size = sv.block(base, 'WHDC')
    struct.pack_into('<I', out, bp + 8, size + dd)
    struct.pack_into('<I', out, bp + 16, size + dd - 4)
    out = bytes(sv.fix_lengths(out, dd))
    sv.validate(out, 'результат')
    os.makedirs(os.path.dirname(os.path.abspath(out_p)), exist_ok=True)
    sv.write(out_p, out, crypto.user_id_from_name(out_p))
    assert sv.load(out_p)[1] == 0x096c2a9f
    now = {o['number']: o for o in orcs.read(out, gd)}
    print('seed', seed)
    for n, raw, o, row, oldname, how, gone in put:
        x = now[n]
        print('%-9s %-22s №%-3d → %-26s №%-3d ур. %d, %s, %s, %s; убрано: %s'
              % (x['name'], x['title'], o['number'], row, n, x['level'], x['personality'], x['role_key'], how,
                 ', '.join(g[7:] for g in gone) or '—'))
    print('Записано:', out_p)


if __name__ == '__main__':
    main()
