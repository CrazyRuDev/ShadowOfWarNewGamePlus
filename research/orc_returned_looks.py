"""Experiment 51: "came back beforehand" with the looks of the return — as experiment 50 (orc_returned.py), plus the
scar looks and the voice the game gives on a real return (research/scar_looks.py), for several orcs at once.

    python research/orc_returned_looks.py <base> <source> <out> <num>:<Defaced|IronSkull|Slashface|Burned>:<level> ...

Each orc takes the cell of the next Nurn captain the game has not put into the world yet. Looks, in every copy the
record keeps:
  - item slots (17 tokens: 04 -1 | 04 1 | 02 0 | 00 item | 00 | 00 AD_ | 0c | 0c | 04 | 04 | 05 guid | 05 guid | 0f |
    02 | 0c | 0c | 02 kind) — the slot is replaced by a slot of the same AD_ taken from any orc of the source, with new
    guids (uuid4); Body_Scar is a new slot after IT_Orc_Body_LOD (the list count before the first slot + 1);
  - model sets (head, body, head, hair, 4 extras, 7 meshes, 00, 00, the 7 AD_ of the meshes) — the meshes of the
    replaced slots (an empty part is Smp_Empty_Set), the body Orc_<build>_Body001* → Orc_<build>_Body_Scar;
  - the voice Orc_<Personality>N and PersonalityMarker_* → the voice of the role's origin line.
"""
import os
import struct
import sys
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app', 'engine'))
from sowtool import army, crypto, ngplus, orcs, save as sv   # noqa: E402
from sowtool.gamedata import GameData, name_hash               # noqa: E402

ON, OFF = ('IsResurrected', 'HasEverSpawned'), ('IsDead', 'CanResurrect', 'KilledByPlayer', 'IsDeadMockMember',
                                                'SeveredHead')
# reward → (role, voice, {AD list index: (item, AD_, mesh: None = empty, 'NoHair' = empty without hair, else part)},
#           body mesh → Body_Scar, added slots [(item, AD_, before IT_Orc_Body_LOD, mesh index from the AD list, part)])
# An added slot whose AD_ the orc already has replaces that slot instead.
BODY_SCAR = ('Body_Scar_BodyReplacement', 'AD_Body_Scar', False, None, None)
SCARS = {
    # the real return of Mozu: the poisoned face in the helmet slot (no helmet)
    'Defaced': ('Role_Defaced', 'Whiner2', {0: ('orc_poison_head_02', 'AD_empty_head', None),
                                             1: ('IT_empty_shoulders', 'AD_empty_shoulders', None),
                                             2: ('Tumor_Chest', 'AD_Tumor_Chest', 'Tumor_Chest')}, False, []),
    'IronSkull': ('Role_IronSkull', 'Clever1', {0: (None, 'AD_MetalBandage_Helmet', 'MetalBandage_Helmet_Head01')},
                  True, [BODY_SCAR]),
    # Tkhrak's real return: the face scar item in the body scar slot, the body mesh with scars — both at once
    'Slashface': ('Role_SlashFace', 'Wise1', {}, True, [('orc_Bloody_Face', 'AD_Body_Scar', False, None, None)]),
    # the burns of Ogbur «Пламя Войны» (a real burned orc of the source): face and chest burns, no armour above
    'Burned': ('Role_Burned', 'Twisted2', {0: ('orc_burns_head_leftFace_02', 'AD_empty_head', None),
                                           1: ('IT_empty_shoulders', 'AD_empty_shoulders', None),
                                           2: ('orc_burns_body_leftChest', 'AD_empty_chest', None),
                                           3: ('IT_empty_arms', 'AD_empty_arms', None)}, True, [BODY_SCAR]),
    # Bolg «Железная Челюсть» (history 2026-10-20): no helmet, the jaw is the 2nd extra mesh after Body_LOD
    'RazorJaw': ('Role_RazorJaw', 'Brute2', {0: ('IT_empty_head_NoHair', 'AD_empty_head_NoHair', 'NoHair')}, False,
                 [('MetalJaw_Helmet', 'AD_MetalJaw_Helmet', False, -1, 'MetalJaw_Helmet')]),
    # the left arm claw of Norukh: a slot before IT_Orc_Body_LOD, the 2nd of the 4 extra meshes after the hair
    'Claw': ('Role_Claw', 'Professional3', {}, False, [('L_Arm_Claw', 'AD_L_Arm_Claw', True, -12, 'L_Arm_Claw')]),
    # transformations (samples: the finished save and the saves of other players); a mesh '!Name' is taken as is
    # FlameOfWar: the burns as Burned + the fire kit of traits (TRAITS)
    'FlameOfWar': ('Role_FlameOfWar', 'Brute2', {0: ('orc_burns_head_leftFace_02', 'AD_empty_head', None),
                                                 1: ('IT_empty_shoulders', 'AD_empty_shoulders', None),
                                                 2: ('orc_burns_body_leftChest', 'AD_empty_chest', None),
                                                 3: ('IT_empty_arms', 'AD_empty_arms', None)}, True, [BODY_SCAR]),
    # Machine (Kruk, Kuga, Khrosh, Golm): no armour at all, the machine body and head — Buff meshes for every build
    'Machine': ('Role_Machine', 'Professional2', {0: ('IT_empty_head_HighWeight', 'AD_empty_head_NoHair', 'NoHair'),
                                                  1: ('IT_empty_shoulders', 'AD_empty_shoulders', None),
                                                  2: ('IT_empty_chest', 'AD_empty_chest', None),
                                                  3: ('IT_empty_arms', 'AD_empty_arms', None),
                                                  4: ('IT_empty_pants', 'AD_empty_pants', None),
                                                  5: ('IT_empty_legs', 'AD_empty_legs', None),
                                                  6: ('Machine_BodyLOD', 'AD_Machine_BodyLOD',
                                                      '!Orc_Buff_Machine_BodyLOD')}, False,
                [('Machine_Head', 'AD_Machine_Head', False, -15, '!Orc_Buff_Machine_Head'),   # inserted in reverse
                 ('Machine_Body', 'AD_Machine_Body', False, -16, '!Orc_Buff_Machine_Body')]),
    # Blight (Maku «Развалина», Pashsh «Очаровашка»): the rotten head instead of the 2nd head, tumours, no helmet
    # BagHead (Grisha «Взломщик», a save of another player): no hair, the sack instead of the 2nd head
    # no samples of these looks: the role, the voice of its line and an overlay (OVERLAY) only
    'Unkillable': ('Role_Unkillable', 'Clever1', {0: ('IT_empty_head_LowWeight', 'AD_empty_head', None)}, True,
                   [BODY_SCAR]),
    'Specter': ('Role_Specter', 'Brute1', {}, False, []),
    'Beast': ('Role_Beast', 'BlackSpeech1', {}, True, [BODY_SCAR]),
    'Survivor': ('Role_Survivor', None, {}, False, []),
    'Stormbringer': ('Role_StormBringer', 'Professional1', {}, False, []),
    # Infested: the maggot head of the finished save (orc_maggot_head_01 in place of the helmet)
    'Infested': ('Role_Infested', 'Twisted1', {0: ('orc_maggot_head_01', 'AD_empty_head_NoHair', 'NoHair')}, False,
                 []),
    'BagHead': ('Role_BagHead', 'Twisted3', {0: ('IT_empty_head_HighWeight', 'AD_empty_head_NoHair', 'NoHair')}, False,
                [('Sack_Head', 'AD_Sack_Head', False, -15, 'Sack_Head')]),
    'Blight': ('Role_Blight', 'Brute1', {0: ('IT_empty_head_NoHair', 'AD_empty_head_NoHair', 'NoHair'),
                                         1: ('IT_empty_shoulders', 'AD_empty_shoulders', None),
                                         2: ('Tumor_Chest', 'AD_Tumor_Chest', 'Tumor_Chest')}, False,
               [('Blight_Head', 'AD_Blight_Head', False, -15, 'Blight_Head')]),
}
# Ologs: their own metal plate (Ar-Baruk «Безмозглый», history 2026-10-22 17:16)
OLOG_PARTS = {'IronSkull': {0: ('olog_Exposed_Brain_02', 'AD_MetalCap_Helmet', 'MetalCap_Helmet_Head01')}}
# the wound drawn on the skin in the scar slot (AD_Body_Scar), over the armour — experiment 58
OVERLAY = {'Slashface': 'orc_cuts_head_01', 'Defaced': 'orc_Left_Eye_Gouge', 'IronSkull': 'orc_metalHead_head',
           'FlameOfWar': 'orc_tornFace_head', 'Burned': 'orc_tornFace_head', 'Blight': 'orc_sores_head',
           'RazorJaw': 'orc_mauled_head_01', 'Unkillable': 'orc_cuts_head_03', 'Specter': 'orc_undead',
           'Beast': 'orc_mauled_head_01', 'Infested': 'orc_maggot_body_01', 'Survivor': 'orc_stitched_cut_body_LElbow',
           'Stormbringer': 'orc_Stormbringer_OldScar'}
# a second overlay in the head slot when the orc wears no helmet (the item of an empty head swapped, its AD_ kept —
# as orc_poison_head_02 / orc_maggot_head_01 sit there): experiment 59 — the head of Prak was clean under his line
HEAD_OVERLAY = {'Slashface': 'orc_cuts_head_02', 'Blight': 'orc_Left_Eye_Gouge', 'Unkillable': 'orc_eyewound_head_LEye',
                'Survivor': 'orc_cuts_head_02', 'Stormbringer': 'orc_cuts_head_02', 'Specter': 'orc_curse_head_face',
                'Beast': 'orc_mauled_head_03'}
REWARDS = {'Unkillable': 'ResReward_PinnicleScar_Unkillable', 'Specter': 'ResReward_PinnicleScar_Specter',
           'Beast': 'ResReward_TransformRole_Beast', 'Infested': 'ResReward_TransformRole_Infested',
           'Survivor': 'ResReward_ChangeRole_Survivor', 'Stormbringer': 'ResReward_ChangeRole_Stormbringer',
           'Claw': 'ResReward_ChangeRole_Claw', 'FlameOfWar': 'ResReward_TransformRole_FlameOfWar',
           'Machine': 'ResReward_TransformRole_Machine', 'Blight': 'ResReward_TransformRole_Blight'}
# the others: ResReward_PinnicleScar_<scar>
# traits a transformation brings (common to all its samples): (pickers, markers)
LEGEND = ['Marker_OrcRarity_Legendary', 'Marker_MoreLucky_to_CheatDeath']
TRAITS = {'FlameOfWar': (['Picker_Fire_Weapon', 'Picker_Grenade_Fire', 'Picker_ExplodesOnDeath_Fire',
                          'Picker_PlantsMines_Fire', 'Picker_ThrowGrenadesAtFeet_Fire', 'Picker_OrcRarity_Legendary'],
                         ['Marker_StatusEffect_Fire'] + LEGEND),
          'Machine': (['Picker_OrcRarity_Legendary'], LEGEND),
          'Blight': (['Picker_OrcRarity_Legendary'], LEGEND)}
OLOG_VOICES = ('Wise1', 'Zealot1', 'BlackSpeech1')  # these personalities speak with an Olog_ voice record
VOICES = ('Brute', 'Clever', 'Professional', 'Twisted', 'Whiner', 'Wise', 'Zealot', 'BlackSpeech')
BUILDS = {'Marker_AppearanceTag_Slim': 'Slim', 'Marker_AppearanceTag_Buff': 'Buff', 'Marker_AppearanceTag_Stocky': 'Stk'}


def name(x, rec):
    return rec(x.value) if x.type == 0 and x.value is not None else None


def slots(t, rec):
    """Item slots: index of the item token for each slot (the AD_ is 2 tokens later, the kind 13 later)."""
    return [i for i in range(3, len(t) - 13)
            if t[i].type == 0 and t[i + 2].type == 0 and (name(t[i + 2], rec) or '').startswith('AD_')
            and t[i + 7].type == 5 and t[i + 8].type == 5 and t[i - 3].type == 4 and t[i - 3].value == -1]


def donors(bufs, gd):
    """AD_ (and item) → bytes of a whole slot (17 tokens) of some orc of these saves."""
    rec, out = gd.record, {}
    for buf in bufs:
        t, s, e = army._table(buf, rec)
        for o in orcs.read(buf, gd):
            try:
                a, b = army._record(buf, t, s, e, o['number'])
            except Exception:
                continue
            tt = sv.tokens(buf[a:b], 0, b - a)
            for i in slots(tt, rec):
                raw = bytes(buf[a + tt[i - 3].pos:a + tt[i + 14].pos])
                out.setdefault((name(tt[i], rec), name(tt[i + 2], rec)), raw)
                out.setdefault((None, name(tt[i + 2], rec)), raw)
    return out


def new_guids(raw):
    """A donor slot with fresh guids (tokens 05 at slot positions 10 and 11)."""
    raw = bytearray(raw)
    t = sv.tokens(bytes(raw), 0, len(raw))
    g = uuid.uuid4().bytes
    for k, x in enumerate((t[10], t[11])):
        assert x.type == 5
        raw[x.pos + 1:x.pos + 9] = g[8 * k:8 * k + 8]
    return bytes(raw)


def looks(raw, scar, donor, rec):
    role, voice, parts, body_scar, added = SCARS[scar]
    t = sv.tokens(bytes(raw), 0, len(raw))
    build = next(BUILDS[n] for n in map(lambda x: name(x, rec), t) if n in BUILDS)
    olog = any((name(x, rec) or '').startswith('OlogHai_') for x in t)
    pre = 'Olog_' if olog else 'Orc_'
    if olog:                                       # Ologs have their own scar items and only Olog voices
        parts = OLOG_PARTS.get(scar, parts)
        voice = None
    elif voice is None:                            # a role without its own line keeps the orc's voice
        pass
        added = [(('olog_' + it[4:]) if it and it.startswith('orc_') else it, ad, before, m, part)
                 for it, ad, before, m, part in added]
        added = [a for a in added if (a[0], a[1]) in donor]   # no Olog variant at hand: the orc keeps its own
    edits, counts = [], {}                         # (start, end, bytes) applied from the end; count token → + n

    def put(x, n):
        edits.append((x.pos + 1, x.pos + 5, struct.pack('<I', name_hash(n))))
    # model sets: head, body, head, hair, 4 extras, 7 meshes, 2 extras, 7 AD_
    ad_list = None
    for j in range(16, len(t) - 7):
        if all((name(t[j + k], rec) or '').startswith('AD_') for k in range(7)) and \
                not (name(t[j - 1], rec) or '').startswith('AD_') and name(t[j - 9], rec) is not None:
            ad_list = [name(t[j + k], rec) for k in range(7)]
            for k, (item, new_ad, mesh) in parts.items():
                put(t[j - 9 + k], 'Smp_Empty_Set' if mesh is None else 'Smp_Empty_Set_NoHair' if mesh == 'NoHair'
                    else mesh[1:] if mesh.startswith('!') else pre + '%s_%s' % (build, mesh))
                put(t[j + k], new_ad)
            if body_scar and (name(t[j - 16], rec) or '').startswith(pre + '%s_Body0' % build):
                put(t[j - 16], pre + '%s_Body_Scar' % build)
            for item, ad, before, m, part in added:
                if m is not None:
                    put(t[j + m], part[1:] if part.startswith('!') else pre + '%s_%s' % (build, part))
    # item slots of every item list
    sl = slots(t, rec)
    heads = {i for i in sl if i - 17 not in sl}
    for i in sl:
        ad = name(t[i + 2], rec)
        for k, (item, new_ad, mesh) in parts.items():
            if ad == ad_list[k]:
                edits.append((t[i - 3].pos, t[i + 14].pos, new_guids(donor[(item, new_ad)])))
        if not (name(t[i + 2], rec) or '').startswith('AD_Orc_Body_LOD'):   # IT_Orc_Body_LOD, _Rogue_LOD…
            continue
        first = max(h for h in heads if h <= i)
        while t[first - 20].type == 4 and t[first - 20].value == -1 and t[first - 19].type == 4:
            first -= 17                            # weapon slots before it have no AD_
        group = [x for x in sl if first <= x <= i + 17 * 4]
        for item, ad, before, m, part in added:
            same = [x for x in group if name(t[x + 2], rec) == ad]
            if same:
                edits.append((t[same[0] - 3].pos, t[same[0] + 14].pos, new_guids(donor[(item, ad)])))
                continue
            at = t[i - 3].pos if before else t[i + 14].pos
            edits.append((at, at, new_guids(donor[(item, ad)])))
            assert t[first - 4].type == 4, t[first - 4]
            counts[first - 4] = counts.get(first - 4, 0) + 1
    for c, n in counts.items():
        edits.append((t[c].pos + 1, t[c].pos + 5, struct.pack('<i', t[c].value + n)))
    # voice and personality marker
    for x in t:
        n = name(x, rec) or ''
        if voice is None:
            break
        if n.startswith('PersonalityMarker_'):
            put(x, 'PersonalityMarker_' + voice)
        elif n.startswith(('Orc_', 'Olog_')) and n.split('_', 1)[1][:-1] in VOICES and n[-1].isdigit():
            put(x, ('Olog_' if voice in OLOG_VOICES else 'Orc_') + voice)
    raw = bytearray(raw)
    for a, b, new in sorted(edits, key=lambda e: e[0], reverse=True):
        raw[a:b] = new
    pickers, markers = TRAITS.get(scar, ([], []))
    return add_traits(bytes(raw), pickers, markers, rec), role


def set_face(raw, scar, rec):
    """The face scar (Combat/Scar/Type): after TraitLevelOffset_* come the role bookmark, 04 n, the n lasting scars
    (prostheses) and then this one — the game draws it (Khura «Одноглазый»: EyeGouge)."""
    t = sv.tokens(raw, 0, len(raw))
    k = next(i for i, x in enumerate(t) if (name(x, rec) or '').startswith('TraitLevelOffset_'))
    assert t[k + 2].type == 4, t[k + 2]
    x = t[k + 3 + t[k + 2].value]
    assert x.type == 0, x
    raw = bytearray(raw)
    raw[x.pos + 1:x.pos + 5] = struct.pack('<I', name_hash(scar))
    return bytes(raw)


def head_overlay(raw, item, rec):
    """The overlay in place of an empty head (IT_empty_head*), in every item list; a helmet stays as it is."""
    t = sv.tokens(raw, 0, len(raw))
    raw = bytearray(raw)
    for i in slots(t, rec):
        if (name(t[i], rec) or '').startswith('IT_empty_head'):
            raw[t[i].pos + 1:t[i].pos + 5] = struct.pack('<I', name_hash(item))
    return bytes(raw)


def overlay(raw, item, donor, rec):
    """Put an overlay item (orc_cuts_head_01, orc_Left_Eye_Gouge…) into the scar slot (AD_Body_Scar) — it shows over
    the armour (Tkhrak's orc_Bloody_Face under a helmet). The slot is a body scar slot of the source with the item
    swapped; an orc without one gets it after IT_Orc_Body_LOD in every item list."""
    t = sv.tokens(raw, 0, len(raw))
    sl = slots(t, rec)
    h = struct.pack('<I', name_hash(item))
    edits, counts = [], {}
    scar = [i for i in sl if name(t[i + 2], rec) == 'AD_Body_Scar']
    for i in scar:
        edits.append((t[i].pos + 1, t[i].pos + 5, h))
    if not scar:
        base = bytearray(donor[BODY_SCAR[:2]])
        dt = sv.tokens(bytes(base), 0, len(base))
        base[dt[3].pos + 1:dt[3].pos + 5] = h
        heads = {i for i in sl if i - 17 not in sl}
        for i in sl:
            if not (name(t[i + 2], rec) or '').startswith('AD_Orc_Body_LOD'):
                continue
            first = max(x for x in heads if x <= i)
            while t[first - 20].type == 4 and t[first - 20].value == -1 and t[first - 19].type == 4:
                first -= 17
            edits.append((t[i + 14].pos, t[i + 14].pos, new_guids(bytes(base))))
            counts[first - 4] = counts.get(first - 4, 0) + 1
    for c, n in counts.items():
        edits.append((t[c].pos + 1, t[c].pos + 5, struct.pack('<i', t[c].value + n)))
    raw = bytearray(raw)
    for a, b, new in sorted(edits, key=lambda e: e[0], reverse=True):
        raw[a:b] = new
    return bytes(raw)


def add_traits(raw, pickers, markers, rec):
    """Add the traits the record does not have yet: the pickers to the trait list (04 n | (00 Picker_* | 00)*n), the
    markers to the marker list (04 n | 00 marker*n)."""
    t = sv.tokens(raw, 0, len(raw))
    have = {name(x, rec) for x in t}
    edits = []
    for c in range(len(t) - 1):
        if t[c].type != 4 or not t[c].value or t[c].value < 0:
            continue
        n = t[c].value
        if c + 2 * n < len(t) and all((name(t[c + 1 + 2 * k], rec) or '').startswith('Picker_') for k in range(n)):
            new = [p for p in pickers if p not in have]
            if new:
                at = t[c + 2 * n].end
                edits.append((at, at, b''.join(b'\x00' + struct.pack('<I', name_hash(p)) + b'\x00' + b'\x00' * 4
                                                for p in new)))
                edits.append((t[c].pos + 1, t[c].pos + 5, struct.pack('<i', n + len(new))))
                pickers = []
        elif c + n < len(t) and all(t[c + 1 + k].type == 0 and name(t[c + 1 + k], rec)
                                    and not name(t[c + 1 + k], rec).startswith('Picker_') for k in range(n)) and                 any('Marker' in name(t[c + 1 + k], rec) for k in range(n)):
            new = [m for m in markers if m not in have]
            if new:
                at = t[c + n].end
                edits.append((at, at, b''.join(b'\x00' + struct.pack('<I', name_hash(m)) for m in new)))
                edits.append((t[c].pos + 1, t[c].pos + 5, struct.pack('<i', n + len(new))))
                markers = []
    raw = bytearray(raw)
    for a, b, new in sorted(edits, key=lambda e: e[0], reverse=True):
        raw[a:b] = new
    return bytes(raw)


def returned(raw, role, reward, rec):
    """As orc_returned.py: alive, resurrected, the role and the reward list = that reward."""
    raw = bytearray(raw)
    t = sv.tokens(bytes(raw), 0, len(raw))
    d = orcs._desc_start(t, 0, len(t))
    f = next(x for x in t[d:] if x.type == 0x05)
    bits = int.from_bytes(raw[f.pos + 1:f.pos + 9], 'little')
    for n in OFF:
        bits &= ~(1 << orcs.FLAGS.index(n))
    for n in ON:
        bits |= 1 << orcs.FLAGS.index(n)
    raw[f.pos + 1:f.pos + 9] = bits.to_bytes(8, 'little')
    for r in t[d:]:                      # the record may keep a second copy at its end — the map shows that one
        if r.type == 0 and (rec(r.value) or '').startswith('Role_'):
            raw[r.pos + 1:r.pos + 5] = struct.pack('<I', name_hash(role))
    tail = t[-5:]
    assert [x.type for x in tail] == [4, 4, 0, 2, 0], [x.type for x in tail]
    k = len(t) - 5
    assert t[k].value == 0, 'награды уже есть'
    return bytes(raw[:t[k].pos] + b'\x04' + struct.pack('<i', 1) + b'\x00' + struct.pack('<I', name_hash(reward)) +
                 raw[t[len(t) - 4].pos:])


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    base_p, src_p, out_p = sys.argv[1:4]
    gd = GameData(os.path.join(ROOT, 'app', 'gui', 'data', 'game.gamedb'),
                  os.path.join(ROOT, 'app', 'gui', 'data', 'string_ruru.strdb'))
    rec = gd.record
    base, source = sv.load(base_p)[0], sv.load(src_p)[0]
    donor = donors([source], gd)
    targets, _ = army._targets(base, gd)
    cells = [(r, o) for r, o in targets['island'] if r.startswith('island_Row_Captain')]
    st = army._table(source, rec)
    put = []
    for spec, (row, old) in zip(sys.argv[4:], cells):
        num, scar, level = spec.split(':')
        sa, sb = army._record(source, *st, int(num))
        raw = army._prepare(source[sa:sb], old['number'], 'Faction_island', row, int(level),
                            max(0, ngplus.base_day(base) - 5), rec)
        raw, role = looks(raw, scar, donor, rec)
        raw = returned(raw, role, REWARDS.get(scar, 'ResReward_PinnicleScar_' + scar), rec)
        put.append((old['number'], raw, num, row, old['name']))
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
    army_ = {o['number']: o for o in orcs.read(out, gd)}
    for n, raw, num, row, oldname in put:
        x = army_[n]
        print('%s %s (источник №%s) — %s вместо №%d %s, ур. %d, %s, роль %s, награды %s, гибель: %s от %s'
              % (x['name'], x['title'], num, row, n, oldname, x['level'], x['personality'], x['role_key'],
                 x['rewards'], x['death_cause'], x['killer_name']))
    print('Записано:', out_p)


if __name__ == '__main__':
    main()
