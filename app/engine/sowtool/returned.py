"""The enemies of the finished game: the orcs that troubled Talion most (orcs.recommend) come back into the new
game — "hello from the past". Researched in experiments 50-63 (CLAUDE.md, research/orc_twenty.py, orc_ambush*.py).

Where (PLACES, by importance; the player's preset takes the first 3, 5, 10 or 15): two nemeses of Nurn by the
ambush "cheated death" (one meets the player on coming to Nurn, one a few hours later), a boss of Seregost and a
boss of Gorgoroth by the same ambush (it waits until the player comes into the region), then captains on the map —
Cirith Ungol, Nurn — on the places the game has not put into the world yet (as the new army, army.py). Bosses are
those who killed Talion most; they keep the profile of the finished game without any weakness, fear or «Нет
последнего шанса». Level: the top of the region's band + 10…15. Up to two dead former followers come back traitors
(CheatDeath_Betrayal, the game sets their level itself), Nurn or Cirith Ungol, after 2.5–4 hours.

How: an orc killed by Talion "came back beforehand" — alive, IsResurrected, its death record kept, the reward of
its return and its role (the origin line at the first meeting speaks of that death), the looks and the voice of the
return, as the game makes them. The reward follows the game's lists MaybeNewRole_CheatDeath_<cause> (gamedb
Faction/Rewards/Lists): a special cause gives a transformation (fire → «Пламя Войны», poison → «Гибельный», cut in
half → «Мясорубка», flies → «Заражённый», a beast → «Зверюга»), a blade one of the scars by the game's weights; an
arm cut off — a claw (a berserker holds two axes, a prosthesis never shows: «Буревестник»); a cut off head, which the
game never brings back, — «Железный Череп». Orcs killed by other orcs and the living come alive as they were.

Looks: item slots of the record (17 tokens: 04 -1 | 04 1 | 02 0 | 00 item | 00 | 00 AD_ | 0c | 0c | 04 | 04 |
05 guid | 05 guid | 0f | 02 | 0c | 0c | 02 kind) replaced or added, in every copy the record keeps, from the samples
in looks_data.py; the model sets (head, body, head, hair, 4 extras, 7 meshes, 2 extras, the 7 AD_ of the meshes)
follow. An overlay (orc_cuts_head_01, orc_Left_Eye_Gouge…) in the body scar slot draws a wound over the armour; a
second one goes in place of an empty head. The voice is the one of the role's line (Orc_<Personality>N or Olog_…).
"""
import random
import struct
import uuid

from . import army, orcs, save as sv
from .gamedata import name_hash

SEED = 3
# what to take off: key -> (title, test of a trait name)
WEAK = {'none': ('Ничего не убирать', lambda n: False),
        'fatal': ('Убрать фатальные слабости', lambda n: 'MortalVulnerable' in n),
        'fears': ('Убрать страхи', lambda n: n.startswith(('Picker_Fear_', 'Picker_Terror_'))),
        'plain': ('Убрать простые слабости', lambda n: n.startswith('Picker_WeakBy_') or
                  (n.startswith('Picker_Resist_') and n.endswith('_Vulnerable'))),
        'all': ('Убрать все слабости и страхи', lambda n: n.startswith(('Picker_Fear_', 'Picker_Terror_', 'Picker_WeakBy_')) or
                (n.startswith('Picker_Resist_') and 'Vulnerable' in n))}

ON, OFF = ('IsResurrected', 'HasEverSpawned'), ('IsDead', 'CanResurrect', 'KilledByPlayer', 'IsDeadMockMember',
                                                'SeveredHead')
FOLLOWER_FLAGS = ('Dominated', 'PlayerFollower', 'Spy', 'PlayerBodyguard')
# reward -> (role, voice of its line or None, {AD list index: (item, AD_, mesh)}, body mesh -> Body_Scar,
#            added slots [(item, AD_, before the body LOD slot, mesh index from the AD list, part)]);
# a mesh None = empty, 'NoHair' = empty without hair, '!Name' as is, else Orc_<build>_<part>.
# An added slot whose AD_ the orc already has replaces that slot instead.
BODY_SCAR = ('Body_Scar_BodyReplacement', 'AD_Body_Scar', False, None, None)
_BURNS = {0: ('orc_burns_head_leftFace_02', 'AD_empty_head', None), 1: ('IT_empty_shoulders', 'AD_empty_shoulders', None),
          2: ('orc_burns_body_leftChest', 'AD_empty_chest', None), 3: ('IT_empty_arms', 'AD_empty_arms', None)}
SCARS = {
    # the real return of Mozu (experiment 6): the poisoned face instead of a helmet, tumours
    'Defaced': ('Role_Defaced', 'Whiner2', {0: ('orc_poison_head_02', 'AD_empty_head', None),
                                             1: ('IT_empty_shoulders', 'AD_empty_shoulders', None),
                                             2: ('Tumor_Chest', 'AD_Tumor_Chest', 'Tumor_Chest')}, False, []),
    'IronSkull': ('Role_IronSkull', 'Clever1', {0: ('orc_Exposed_Brain_01', 'AD_MetalBandage_Helmet',
                                                    'MetalBandage_Helmet_Head01')}, True, [BODY_SCAR]),
    # Tkhrak's real return: blood on the face in the body scar slot (the overlay replaces it) and the scarred body
    'Slashface': ('Role_SlashFace', 'Wise1', {}, True, [('orc_Bloody_Face', 'AD_Body_Scar', False, None, None)]),
    'Burned': ('Role_Burned', 'Twisted2', _BURNS, True, [BODY_SCAR]),
    'RazorJaw': ('Role_RazorJaw', 'Brute2', {0: ('IT_empty_head_NoHair', 'AD_empty_head_NoHair', 'NoHair')}, False,
                 [('MetalJaw_Helmet', 'AD_MetalJaw_Helmet', False, -1, 'MetalJaw_Helmet')]),
    'Claw': ('Role_Claw', 'Professional3', {}, False, [('L_Arm_Claw', 'AD_L_Arm_Claw', True, -12, 'L_Arm_Claw')]),
    # a right leg cut off: the same claw on the leg (Ogbur after ScarBookmark_Role_Claw, Dudz «Хромоногий»)
    'ClawLeg': ('Role_Claw', 'Professional3', {}, False, [('R_Leg_Claw', 'AD_R_Leg_Claw', True, -12, 'R_Leg_Claw')]),
    'BagHead': ('Role_BagHead', 'Twisted3', {0: ('IT_empty_head_HighWeight', 'AD_empty_head_NoHair', 'NoHair')}, False,
                [('Sack_Head', 'AD_Sack_Head', False, -15, 'Sack_Head')]),
    'Unkillable': ('Role_Unkillable', 'Clever1', {0: ('IT_empty_head_LowWeight', 'AD_empty_head', None)}, True,
                   [BODY_SCAR]),
    'Specter': ('Role_Specter', 'Brute1', {}, False, []),
    'Survivor': ('Role_Survivor', None, {}, False, []),
    'Stormbringer': ('Role_StormBringer', 'Professional1', {}, False, []),
    'FlameOfWar': ('Role_FlameOfWar', 'Brute2', _BURNS, True, [BODY_SCAR]),
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
    'Blight': ('Role_Blight', 'Brute1', {0: ('IT_empty_head_NoHair', 'AD_empty_head_NoHair', 'NoHair'),
                                         1: ('IT_empty_shoulders', 'AD_empty_shoulders', None),
                                         2: ('Tumor_Chest', 'AD_Tumor_Chest', 'Tumor_Chest')}, False,
               [('Blight_Head', 'AD_Blight_Head', False, -15, 'Blight_Head')]),
    'Infested': ('Role_Infested', 'Twisted1', {0: ('orc_maggot_head_01', 'AD_empty_head_NoHair', 'NoHair')}, False,
                 []),
    'Beast': ('Role_Beast', 'BlackSpeech1', {}, True, [BODY_SCAR]),
}
OLOG_PARTS = {'IronSkull': {0: ('olog_Exposed_Brain_02', 'AD_MetalCap_Helmet', 'MetalCap_Helmet_Head01')}}
OVERLAY = {'Slashface': 'orc_cuts_head_01', 'Defaced': 'orc_Left_Eye_Gouge', 'IronSkull': 'orc_metalHead_head',
           'FlameOfWar': 'orc_tornFace_head', 'Burned': 'orc_tornFace_head', 'Blight': 'orc_sores_head',
           'RazorJaw': 'orc_mauled_head_01', 'Unkillable': 'orc_cuts_head_03', 'Specter': 'orc_undead',
           'Beast': 'orc_mauled_head_01', 'Infested': 'orc_maggot_body_01', 'Survivor': 'orc_stitched_cut_body_LElbow',
           'Stormbringer': 'orc_Stormbringer_OldScar'}
HEAD_OVERLAY = {'Slashface': 'orc_cuts_head_02', 'Blight': 'orc_Left_Eye_Gouge', 'Unkillable': 'orc_eyewound_head_LEye',
                'Survivor': 'orc_cuts_head_02', 'Stormbringer': 'orc_cuts_head_02', 'Specter': 'orc_curse_head_face',
                'Beast': 'orc_mauled_head_03'}
REWARDS = {'Claw': 'ResReward_ChangeRole_Claw', 'ClawLeg': 'ResReward_ChangeRole_Claw', 'Survivor': 'ResReward_ChangeRole_Survivor',
           'Stormbringer': 'ResReward_ChangeRole_Stormbringer', 'FlameOfWar': 'ResReward_TransformRole_FlameOfWar',
           'Machine': 'ResReward_TransformRole_Machine', 'Blight': 'ResReward_TransformRole_Blight',
           'Infested': 'ResReward_TransformRole_Infested', 'Beast': 'ResReward_TransformRole_Beast'}
LEGEND = ['Marker_OrcRarity_Legendary', 'Marker_MoreLucky_to_CheatDeath']
# traits a transformation brings (common to all its samples): (pickers, markers)
TRAITS = {'FlameOfWar': (['Picker_Fire_Weapon', 'Picker_Grenade_Fire', 'Picker_ExplodesOnDeath_Fire',
                          'Picker_PlantsMines_Fire', 'Picker_ThrowGrenadesAtFeet_Fire', 'Picker_OrcRarity_Legendary'],
                         ['Marker_StatusEffect_Fire'] + LEGEND),
          'Machine': (['Picker_OrcRarity_Legendary'], LEGEND), 'Blight': (['Picker_OrcRarity_Legendary'], LEGEND),
          'Infested': (['Picker_OrcRarity_Legendary'], LEGEND), 'Beast': (['Picker_OrcRarity_Legendary'], LEGEND)}
# a blade: the game's list of MaybeNewRole_CheatDeath_PlayerSlash with its weights (without the shield role)
BLADE = [('IronSkull', 10), ('RazorJaw', 20), ('Slashface', 10), ('Unkillable', 20), ('BagHead', 10), ('Survivor', 1)]
ARROW = [('Unkillable', 20), ('Slashface', 10), ('BagHead', 10), ('Survivor', 1)]
OLOG_VOICES = ('Wise1', 'Zealot1', 'BlackSpeech1')    # these personalities speak with an Olog_ voice record
VOICES = ('Brute', 'Clever', 'Professional', 'Twisted', 'Whiner', 'Wise', 'Zealot', 'BlackSpeech')
BUILDS = {'Marker_AppearanceTag_Slim': 'Slim', 'Marker_AppearanceTag_Buff': 'Buff', 'Marker_AppearanceTag_Stocky': 'Stk'}
TITLES = {'Defaced': 'Обезображенный', 'IronSkull': 'Железный Череп', 'Slashface': 'Со Шрамом', 'Burned': 'Обожжённый',
          'RazorJaw': 'Острозуб', 'Claw': 'Клешня', 'ClawLeg': 'Клешня (нога)', 'BagHead': 'Мешок на голове', 'Unkillable': 'Неубиваемый',
          'Specter': 'Привидение', 'Survivor': 'Выживший', 'Stormbringer': 'Буревестник', 'FlameOfWar': 'Пламя Войны',
          'Machine': 'Мясорубка', 'Blight': 'Гибельный', 'Infested': 'Заражённый', 'Beast': 'Зверюга'}


def scar(cause, rng, olog=False, berserker=False):
    """The reward of a return by the cause of death (see the module doc)."""
    def pick(table):
        return rng.choices([k for k, _ in table], [w for _, w in table])[0]
    if cause.startswith('HeadRemoved') or cause in ('Fall', 'FellBeast', 'CrushingRocks'):
        return 'IronSkull'
    if olog:                                      # no other looks are known for the Olog model
        return 'Slashface'
    if cause.startswith('Poison'):
        return 'Blight'
    if cause.startswith(('Fire', 'Balefire')):
        return 'FlameOfWar'
    if cause == 'LowerBody':
        return 'Machine'
    if 'ArmLower_Removed' in cause or 'ArmSever' in cause:
        return 'Stormbringer' if berserker else 'Claw'
    if 'Leg' in cause:                            # RightLeg: a right leg cut off
        return 'ClawLeg'
    if cause in ('Troll', 'Caragor', 'Ghul'):
        return 'Beast'
    if cause == 'Flies':
        return 'Infested'
    if cause in ('Curse', 'Torment'):
        return 'Specter'
    if cause == 'Bleedout' or cause.startswith('Executed'):
        return 'Unkillable'
    if 'Arrow' in cause:
        return pick(ARROW)
    return pick(BLADE)


def comes_back(o):
    """The return of an orc of the finished game (orcs.read): the SCARS key for one killed by Talion, None for the
    others (they come alive). The draw is seeded by the orc, so the Orcs tab shows what the build will do."""
    if not (o['dead'] and o['killer_name'] == 'Талион'):
        return None
    return scar(o['death_cause'] or '', random.Random(SEED * 100003 + o['number']), o['class'] == 'олог',
                o['class'] == 'берсерк')


# ---- records -------------------------------------------------------------------------------------------------
def _name(x, rec):
    return rec(x.value) if x.type == 0 and x.value is not None else None


def _hash(n):
    return struct.pack('<I', name_hash(n))


def slots(t, rec):
    """Item slots of a record: the index of the item token of each (its AD_ 2 tokens later)."""
    return [i for i in range(3, len(t) - 13)
            if t[i].type == 0 and t[i + 2].type == 0 and (_name(t[i + 2], rec) or '').startswith('AD_')
            and t[i + 7].type == 5 and t[i + 8].type == 5 and t[i - 3].type == 4 and t[i - 3].value == -1]


def samples(bufs, gd):
    """(item, AD_) -> the bytes of a whole slot of some orc of these saves (research/make_looks_data.py)."""
    rec, out = gd.record, {}
    for buf in bufs:
        t, s, e = army._table(buf, rec)
        for o in orcs.read(buf, gd):
            try:
                a, b = army._record(buf, t, s, e, o['number'])
            except StopIteration:
                continue
            tt = sv.tokens(buf[a:b], 0, b - a)
            for i in slots(tt, rec):
                out.setdefault((_name(tt[i], rec), _name(tt[i + 2], rec)), bytes(buf[a + tt[i - 3].pos:a + tt[i + 14].pos]))
    return out


def needed():
    """The slots the looks put in."""
    keys = {BODY_SCAR[:2]}
    for parts, added in [(s[2], s[4]) for s in SCARS.values()] + [(p, []) for p in OLOG_PARTS.values()]:
        keys |= {(item, ad) for item, ad, _ in parts.values()} | {(item, ad) for item, ad, *_ in added}
    return keys


def _slot(key):
    from .looks_data import SLOTS
    return bytes.fromhex(SLOTS[key])


def _fresh(raw):
    """A sample slot with new guids (the 05 tokens at slot positions 10 and 11)."""
    raw = bytearray(raw)
    t = sv.tokens(bytes(raw), 0, len(raw))
    g = uuid.uuid4().bytes
    for k, x in enumerate((t[10], t[11])):
        raw[x.pos + 1:x.pos + 9] = g[8 * k:8 * k + 8]
    return bytes(raw)


def _apply(raw, edits):
    raw = bytearray(raw)
    for a, b, new in sorted(edits, key=lambda e: e[0], reverse=True):
        raw[a:b] = new
    return bytes(raw)


def _list_count(t, sl, i, rec):
    """The token index of the item count of the item list the slot i belongs to."""
    heads = {x for x in sl if x - 17 not in sl}
    first = max(h for h in heads if h <= i)
    while t[first - 20].type == 4 and t[first - 20].value == -1 and t[first - 19].type == 4:
        first -= 17                              # weapon slots before it have no AD_
    assert t[first - 4].type == 4, t[first - 4]
    return first - 4


def looks(raw, key, rec):
    """The looks and the voice of the return `key` (SCARS) in every copy the record keeps."""
    role, voice, parts, body_scar, added = SCARS[key]
    t = sv.tokens(raw, 0, len(raw))
    names = [_name(x, rec) for x in t]
    build = next((BUILDS[n] for n in names if n in BUILDS), 'Buff')
    olog = any((n or '').startswith('OlogHai_') for n in names)
    pre = 'Olog_' if olog else 'Orc_'
    if olog:                                     # Ologs: their own scar items, their own voices
        parts, voice = OLOG_PARTS.get(key, parts), None
        added = [(('olog_' + it[4:]) if it.startswith('orc_') else it, ad, *rest) for it, ad, *rest in added]
        from .looks_data import SLOTS
        added = [a for a in added if a[:2] in SLOTS]
    edits, counts = [], {}

    def put(x, n):
        edits.append((x.pos + 1, x.pos + 5, _hash(n)))

    def mesh(m):
        return 'Smp_Empty_Set' if m is None else 'Smp_Empty_Set_NoHair' if m == 'NoHair' else \
            m[1:] if m.startswith('!') else pre + '%s_%s' % (build, m)
    ad_list = None
    for j in range(16, len(t) - 7):              # model sets: … 7 meshes, 2 extras, 7 AD_
        if all((names[j + k] or '').startswith('AD_') for k in range(7)) and \
                not (names[j - 1] or '').startswith('AD_') and names[j - 9] is not None:
            ad_list = names[j:j + 7]
            for k, (item, ad, m) in parts.items():
                put(t[j - 9 + k], mesh(m))
                put(t[j + k], ad)
            if body_scar and (names[j - 16] or '').startswith(pre + '%s_Body0' % build):
                put(t[j - 16], pre + '%s_Body_Scar' % build)
            for item, ad, before, m, part in added:
                if m is not None:
                    put(t[j + m], mesh(part))
    sl = slots(t, rec)
    for i in sl:
        for k, (item, ad, m) in parts.items():
            if ad_list and names[i + 2] == ad_list[k]:
                edits.append((t[i - 3].pos, t[i + 14].pos, _fresh(_slot((item, ad)))))
        if not (names[i + 2] or '').startswith('AD_Orc_Body_LOD'):
            continue
        c = _list_count(t, sl, i, rec)
        group = [x for x in sl if c < x <= i + 17 * 4]
        for item, ad, before, m, part in added:
            same = [x for x in group if names[x + 2] == ad]
            if same:
                edits.append((t[same[0] - 3].pos, t[same[0] + 14].pos, _fresh(_slot((item, ad)))))
                continue
            at = t[i - 3].pos if before else t[i + 14].pos
            edits.append((at, at, _fresh(_slot((item, ad)))))
            counts[c] = counts.get(c, 0) + 1
    for c, n in counts.items():
        edits.append((t[c].pos + 1, t[c].pos + 5, struct.pack('<i', t[c].value + n)))
    for x, n in zip(t, names):                   # the voice and the personality marker
        n = n or ''
        if voice is None:
            break
        if n.startswith('PersonalityMarker_'):
            put(x, 'PersonalityMarker_' + voice)
        elif n.startswith(('Orc_', 'Olog_')) and n.split('_', 1)[1][:-1] in VOICES and n[-1].isdigit():
            put(x, ('Olog_' if voice in OLOG_VOICES else 'Orc_') + voice)
    raw = _apply(raw, edits)
    pickers, markers = TRAITS.get(key, ([], []))
    raw = add_traits(raw, pickers, markers, rec)
    if not olog:
        if key in OVERLAY:
            raw = overlay(raw, OVERLAY[key], rec)
        if key in HEAD_OVERLAY:
            raw = head_overlay(raw, HEAD_OVERLAY[key], rec)
    return raw, role


def overlay(raw, item, rec):
    """A wound in the body scar slot (AD_Body_Scar) — drawn over the armour; an orc without that slot gets one after
    its body LOD slot in every item list."""
    t = sv.tokens(raw, 0, len(raw))
    sl = slots(t, rec)
    scar = [i for i in sl if _name(t[i + 2], rec) == 'AD_Body_Scar']
    edits, counts = [(t[i].pos + 1, t[i].pos + 5, _hash(item)) for i in scar], {}
    if not scar:
        base = bytearray(_slot(BODY_SCAR[:2]))
        bt = sv.tokens(bytes(base), 0, len(base))
        base[bt[3].pos + 1:bt[3].pos + 5] = _hash(item)
        for i in sl:
            if (_name(t[i + 2], rec) or '').startswith('AD_Orc_Body_LOD'):
                edits.append((t[i + 14].pos, t[i + 14].pos, _fresh(bytes(base))))
                c = _list_count(t, sl, i, rec)
                counts[c] = counts.get(c, 0) + 1
    for c, n in counts.items():
        edits.append((t[c].pos + 1, t[c].pos + 5, struct.pack('<i', t[c].value + n)))
    return _apply(raw, edits)


def head_overlay(raw, item, rec):
    """A second wound in place of an empty head (IT_empty_head*), its AD_ kept; a helmet stays."""
    t = sv.tokens(raw, 0, len(raw))
    return _apply(raw, [(t[i].pos + 1, t[i].pos + 5, _hash(item)) for i in slots(t, rec)
                        if (_name(t[i], rec) or '').startswith('IT_empty_head')])


def add_traits(raw, pickers, markers, rec):
    """The traits the record lacks: pickers to the trait list (04 n | (00 Picker_* | 00)*n), markers to the marker
    list (04 n | 00 marker*n)."""
    t = sv.tokens(raw, 0, len(raw))
    have = {_name(x, rec) for x in t}
    edits = []
    for c in range(len(t) - 1):
        if t[c].type != 4 or not t[c].value or t[c].value < 0:
            continue
        n = t[c].value
        ns = [_name(t[c + 1 + k], rec) for k in range(min(n, len(t) - c - 1))]
        if pickers and c + 2 * n < len(t) and all((_name(t[c + 1 + 2 * k], rec) or '').startswith('Picker_')
                                                  for k in range(n)):
            new = [p for p in pickers if p not in have]
            if new:
                at = t[c + 2 * n].end
                edits.append((at, at, b''.join(b'\x00' + _hash(p) + b'\x00' * 5 for p in new)))
                edits.append((t[c].pos + 1, t[c].pos + 5, struct.pack('<i', n + len(new))))
            pickers = []
        elif markers and len(ns) == n and all(x and not x.startswith('Picker_') for x in ns) and \
                any('Marker' in x for x in ns):
            new = [m for m in markers if m not in have]
            if new:
                at = t[c + n].end
                edits.append((at, at, b''.join(b'\x00' + _hash(m) for m in new)))
                edits.append((t[c].pos + 1, t[c].pos + 5, struct.pack('<i', n + len(new))))
            markers = []
    return _apply(raw, edits)


def remove_traits(raw, test, rec):
    """Drop the traits that pass `test` from every trait list; returns (raw, names dropped)."""
    t = sv.tokens(raw, 0, len(raw))
    edits, gone = [], []
    for c in range(len(t) - 2):
        if t[c].type != 4 or not t[c].value or t[c].value < 0 or \
                not (_name(t[c + 1], rec) or '').startswith('Picker_'):
            continue
        n = t[c].value
        if c + 2 * n >= len(t) or not all((_name(t[c + 1 + 2 * k], rec) or '').startswith('Picker_')
                                          for k in range(n)):
            continue
        drop = [k for k in range(n) if test(_name(t[c + 1 + 2 * k], rec))]
        for k in drop:
            edits.append((t[c + 1 + 2 * k].pos, t[c + 3 + 2 * k].pos, b''))
            gone.append(_name(t[c + 1 + 2 * k], rec))
        if drop:
            edits.append((t[c].pos + 1, t[c].pos + 5, struct.pack('<i', n - len(drop))))
    return _apply(raw, edits), gone


def _flags(raw, on=(), off=()):
    raw = bytearray(raw)
    t = sv.tokens(bytes(raw), 0, len(raw))
    d = orcs._desc_start(t, 0, len(t))
    f = next(x for x in t[d:] if x.type == 0x05)
    bits = int.from_bytes(raw[f.pos + 1:f.pos + 9], 'little')
    for n in off:
        bits &= ~(1 << orcs.FLAGS.index(n))
    for n in on:
        bits |= 1 << orcs.FLAGS.index(n)
    raw[f.pos + 1:f.pos + 9] = bits.to_bytes(8, 'little')
    return bytes(raw)


def _reward(raw, reward):
    """The reward list at the record's end (04 <n> (00 ResReward)*n, then 04, 00, 02, 00) = that one reward. Usually
    empty in a finished game's dead orc; one the game already chose (an orc it was about to bring back) is replaced."""
    t = sv.tokens(raw, 0, len(raw))
    end = len(t) - 4
    assert [x.type for x in t[end:]] == [4, 0, 2, 0], [x.type for x in t[-8:]]
    k = next(k for k in range(end - 1, -1, -1) if t[k].type == 4 and t[k].value == end - 1 - k)
    assert all(x.type == 0 for x in t[k + 1:end]), [x.type for x in t[k:]]
    return raw[:t[k].pos] + b'\x04' + struct.pack('<i', 1) + b'\x00' + _hash(reward) + raw[t[end].pos:]


def came_back(raw, role, reward, rec):
    """Alive and resurrected, the role in every copy (the map shows the one at the record's end), the reward list =
    that reward (04 <n> (00 ResReward)*n at the record's end, empty in a finished game's dead orc)."""
    raw = bytearray(_flags(raw, ON, OFF))
    t = sv.tokens(bytes(raw), 0, len(raw))
    d = orcs._desc_start(t, 0, len(t))
    for r in t[d:]:
        if r.type == 0 and (rec(r.value) or '').startswith('Role_'):
            raw[r.pos + 1:r.pos + 5] = _hash(role)
    return _reward(bytes(raw), reward)


# ---- the enemies into the base ------------------------------------------------------------------------------
# The places by importance; a preset of N takes the first N (decided with the user 2026-10-23). An ambush returns a
# dead orc killed by Talion ("cheated death"): it waits until the player comes to its region and never leaves the
# queue (experiments 61-63; a far one does not hold the others back). The rest stand on the map as captains — never
# warchiefs (the Nurn siege). Cirith Ungol: captains only (its warchief is the target of the act 1 mission «Ворота
# предателя»), no ambushes there (they would come in the short visit of act 1).
#   (kind, region key of army.REGIONS, ambush timer in seconds of game time (low, high))
# The top three of the finished game are met first, in Nurn (decided 2026-10-23): the timer of an ambush counts from
# the start of the game, not from coming to Nurn (the prologue and act 1 take 1.5-2 hours), so only one of them comes
# by an ambush — it waits in Nurn and meets the player on arrival — and the two others stand there as captains: the
# game sends captains who know Talion against him itself (Gund in experiment 51). All three get
# Marker_MoreLucky_to_CheatDeath: killed in Nurn, they are likely to come back later, as the game decides.
PLACES = ([('nemesis', 'island', (480, 720)), ('top', 'island', None), ('top', 'island', None),
           ('boss', 'volcano', (300, 600)), ('boss', 'snowMtn', (300, 600))]
          + [('captain', 'MtnPass', None)] * 6 + [('captain', 'island', None)] * 4)
LUCKY = 'Marker_MoreLucky_to_CheatDeath'
COUNTS = (3, 5, 10, 15)
DEFAULT_COUNT = 5
LEVEL_UP = (10, 15)                           # above the top of the region's band (its captains and warchiefs)
TRAITOR_TIMER = (9000, 14400)                 # 2.5-4 h: not ripe in the short visit to Cirith Ungol in act 1
DEAD_ON = ('IsDead', 'CanResurrect', 'PresentedToPlayer', 'IdentityPresented', 'HasEverSpawned')
KIND = {'boss': 'БОСС, засада', 'nemesis': 'ТОП, засада «обманул смерть»', 'changed': 'ТОП, засада «орк изменился»', 'top': 'ТОП, капитан',
        'traitor': 'ПРЕДАТЕЛЬСТВО', 'captain': 'капитан'}


# the traitors: always two, those who served Talion best (decided with the user 2026-10-24) — a betrayal hurts more
TRAITORS = 2
RECRUIT = ('IsPlayerFollowerApply', 'Domination_Recruit', 'ActiveRecruitedSuccess', 'RecruitedDuringDefense')
WORK = ('RewSub_SubSuc', 'PS_Single_Reward_SubSuc', 'ActiveKillNamedAI', 'Contract_', 'FortDefense_', 'FortMission_',
        'Duel_SubSuccess', 'Gauntlet_', 'Promote')     # missions, captains killed, contracts, fort defence, promotions
PLACE_BONUS = {'правитель': 6, 'вождь': 4, 'охранник': 2, 'капитан': 1}
UNSEEN = 10                  # days of service a full history (32 events) hides: its recruitment fell out of it


def service(o):
    """How well a dead follower served Talion: days from the recruitment to the last event of the history (no
    recruitment left in a full history — from its first event + UNSEEN), the work (2 each), the times Talion revived
    it (3 each), its place."""
    h = o['history']
    if not h:
        return 0
    last = max(d for _, d in h)
    rec_days = [d for ev, d in h if ev.startswith(RECRUIT)]
    days = last - min(rec_days) if rec_days else last - min(d for _, d in h) + (UNSEEN if len(h) >= 32 else 0)
    work = sum(1 for ev, _ in h if ev.startswith(WORK))
    revived = sum(1 for ev, _ in h if ev == 'ActiveRevivedByPlayer')
    return days + 2 * work + 3 * revived + PLACE_BONUS.get(o['place'], 0)


def regions(act1):
    """Regions of the captains: the act 2 base has no fresh places in Cirith Ungol (one at most)."""
    return ('island',) if act1 else ('island', 'MtnPass')


def band_tops(base, gd):
    """{region key: the highest level of its living non-story captains and warchiefs} in the base."""
    by_faction = {f: k for k, (f, _) in army.REGIONS.items()}
    tops = {}
    for o in orcs.read(base, gd):
        k = by_faction.get(o['faction'])
        if k and not o['dead'] and not o['story'] and o['place'] in ('капитан', 'вождь'):
            tops[k] = max(tops.get(k, 0), o['level'])
    return tops


def _ambush_ok(o):
    """Can come back by an ambush: killed by Talion, not beheaded (the game never brings a head back), no double, no
    Olog (no Olog looks known but the plate)."""
    return (o['dead'] and o['killer_name'] == 'Талион' and 'HeadRemoved' not in (o['death_cause'] or '')
            and 'Dopple' not in o['role_key'] and o['class'] != 'олог')


def cells(base, gd, keys):
    """Fresh captain places of these regions, region by region in turn — [(region key, row, old orc)]."""
    targets, _ = army._targets(base, gd)
    caps = [[(k, r, o) for r, o in targets.get(k, []) if 'Warchief' not in r] for k in keys]
    out = []
    while any(caps):
        for c in caps:
            if c:
                out.append(c.pop(0))
    return out


def plan(source, gd, act1, count=DEFAULT_COUNT, base=None):
    """([(orc, kind, region key, timer)], traitors). The top three by danger go to Nurn: the first of them an ambush
    can bring by the ambush, the others captains (none fits the ambush — all three captains). Bosses: of the rest,
    those who killed Talion most among the ones an ambush can bring (Gorgoroth's, the main one, first); captains: the
    rest by danger, Cirith Ungol first (no more than its fresh places), then Nurn."""
    army_ = orcs.read(source, gd)
    picked = orcs.recommend(army_)                 # every worthy one: a place takes the best one fitting it
    places = list(PLACES[:min(count, len(picked))])
    ku = len(cells(base, gd, ('MtnPass',))) if base is not None and not act1 else 0
    for i, p in enumerate(places):
        if p[1] == 'MtnPass':
            if ku:
                ku -= 1
            else:
                places[i] = ('captain', 'island', None)
    out, used = [], set()
    top = picked[:sum(1 for p in places if p[0] in ('nemesis', 'top'))]
    for p in places:                              # the nemesis — the first of the top, alive or dead (see place)
        if p[0] in ('nemesis', 'top'):
            o = next((x for x in top if x['number'] not in used), None)
            if o is not None:
                used.add(o['number'])
                out.append((o, p[0], p[1], p[2]))
    able = [o for o in picked if _ambush_ok(o) and o['number'] not in used]
    able.sort(key=lambda o: (o['kill_score'], o['danger']), reverse=True)
    for p in places:                              # Gorgoroth's boss, the main one, comes first in PLACES
        if p[0] == 'boss' and able:
            o = able.pop(0)
            used.add(o['number'])
            out.append((o, 'boss', p[1], p[2]))
    rest = [o for o in picked if o['number'] not in used]
    caps = [p[1] for p in places if p[0] == 'captain']
    caps += ['island'] * (len(places) - len(out) - len(caps))       # ambush places nobody fitted
    for o, key in zip(rest, caps):
        out.append((o, 'captain', key, None))
    traitors = [o for o in army_ if o['follower'] and o['dead'] and not o['story'] and o['met']
                and o['number'] not in {x[0]['number'] for x in out}]
    traitors.sort(key=lambda o: (service(o), o['level']), reverse=True)
    return out, traitors[:TRAITORS]


def count(base, gd, act1, source=None, how_many=DEFAULT_COUNT):
    """For the plan line of the GUI: {what: n}."""
    if source is None:
        return {}
    out = {}
    placed, traitors = plan(source, gd, act1, how_many, base)
    for o, kind, key, _ in placed:
        name = orcs.REGIONS[army.REGIONS[key][0]] + (' засадой' if kind in ('nemesis', 'boss') else '')
        out[name] = out.get(name, 0) + 1
    if traitors:
        out['предатель'] = len(traitors)
    return out


def _make(raw, o, level, rec, kind, weak):
    """The looks of the return, the level (both copies), the weaknesses off (a boss: all, and «Нет последнего
    шанса» even its own)."""
    s = comes_back(o)
    if s:
        raw, _ = looks(raw, s, rec)
    t = sv.tokens(raw, 0, len(raw))
    d = orcs._desc_start(t, 0, len(t))
    raw = bytearray(raw)
    struct.pack_into('<I', raw, t[d + 8].pos + 1, level - 1)
    struct.pack_into('<i', raw, t[d + 9].pos + 1, level - 1)
    test = WEAK['all'][1] if kind == 'boss' else WEAK[weak][1]
    raw, gone = remove_traits(bytes(raw), (lambda n: test(n) or n == 'Picker_NoLastChance') if kind == 'boss'
                              else test, rec)
    return raw, s


def _waiting(raw, role, reward, rec, follower):
    """A record at the end of MainGame waiting for its ambush: no place (the game seats the comer itself), dead and
    seen, the role in every copy, the follower flag only for a traitor (only a follower can betray, experiment 41),
    the reward (see _reward)."""
    raw = bytearray(raw)
    t = sv.tokens(bytes(raw), 0, len(raw))
    raw[t[7].pos + 1:t[7].pos + 5] = b'\0\0\0\0'
    d = orcs._desc_start(t, 0, len(t))
    for r in t[d:]:
        if r.type == 0 and (rec(r.value) or '').startswith('Role_'):
            raw[r.pos + 1:r.pos + 5] = _hash(role)
    raw = _flags(bytes(raw), DEAD_ON + (('PlayerFollower',) if follower else ()),
                 ('Dominated', 'Spy', 'PlayerBodyguard') + (() if follower else ('PlayerFollower',)))
    return _reward(raw, reward)


def _changed(raw, s, rec):
    """A record at the end of MainGame waiting for «орк изменился»: no place, alive and once spawned (else the game
    deletes it on loading, experiment 10), not a follower; one killed by Talion but no fit for «обманул смерть»
    (beheaded, a double, an Olog) has already come back — role and reward of `s`."""
    raw = bytearray(raw)
    t = sv.tokens(bytes(raw), 0, len(raw))
    raw[t[7].pos + 1:t[7].pos + 5] = b'\0\0\0\0'
    raw = bytes(raw)
    if s:
        raw = came_back(raw, SCARS[s][0], REWARDS.get(s, 'ResReward_PinnicleScar_' + s), rec)
    return _flags(raw, ('HasEverSpawned',), OFF + FOLLOWER_FLAGS)


def _event(region, event, number, ms):
    """A Nemesis queue entry: 0c 01 | 00 Faction | 00 event | 00 Faction | 04 orc | 08 tag | 04 timer ms."""
    return (b'\x0c\x01\x00' + _hash(region) + b'\x00' + _hash(event) + b'\x00' + _hash(region) + b'\x04'
            + struct.pack('<i', number) + b'\x08' + struct.pack('<I', 0) + b'\x04' + struct.pack('<i', ms))


def place(base, source, gd, act1, how_many=DEFAULT_COUNT, weak='none', day=0, log=print):
    """The enemies of `source` into the base: captains on fresh places, ambushes as records at the end of MainGame
    with their queue events. Returns (the new base, {its number in the new base: (source orc, kind, region key)})."""
    rec = gd.record
    placed, traitors = plan(source, gd, act1, how_many, base)
    tops = band_tops(base, gd)
    st = army._table(source, rec)
    where = {k: cells(base, gd, (k,)) for k in regions(act1)}
    t, starts, end = army._table(base, rec)
    mg = next(i for i in range(len(t)) if t[i].type == 0 and t[i].value == name_hash('MainGame')
              and t[i + 1].type == 0x0C)
    n = t[mg + 2].value
    jobs = placed + [(o, 'traitor', 'island' if act1 or random.Random(SEED + o['number']).random() < 0.5
                      else 'MtnPass', TRAITOR_TIMER) for o in traitors]
    edits, added, events, lines, numbers = [], [], [], [], {}
    for o, kind, key, timer in jobs:
        rng = random.Random(SEED * 100003 + o['number'] + 1)
        level = min(85, tops.get(key, 20) + rng.randint(*LEVEL_UP))
        faction = army.REGIONS[key][0]
        sa, sb = army._record(source, *st, o['number'])
        if kind in ('captain', 'top'):
            if not where.get(key):
                continue
            _, row, old = where[key].pop(0)
            raw = army._prepare(source[sa:sb], old['number'], faction, row, level, day, rec,
                                orcs.HISTORY == 'decay')
            raw, s = _make(raw, o, level, rec, kind, weak)
            raw = came_back(raw, SCARS[s][0], REWARDS.get(s, 'ResReward_PinnicleScar_' + s), rec) if s else \
                _flags(raw, off=OFF + FOLLOWER_FLAGS)
            if kind == 'top':
                raw = add_traits(raw, [], [LUCKY], rec)
            edits.append((*army._record(base, t, starts, end, old['number']), raw))
            numbers[old['number']] = (o, kind, key)
            what = 'вернулся: ' + TITLES[s] if s else 'жив'
        else:
            number = n + len(added)
            numbers[number] = (o, kind, key)
            raw = army._prepare(source[sa:sb], number, faction, 'Row', level, day, rec, orcs.HISTORY == 'decay')
            raw, s = _make(raw, o, level, rec, kind, weak)
            alive = kind == 'nemesis' and not _ambush_ok(o)    # «орк изменился» waits for its region too (exp. 66)
            if alive:
                raw = _changed(raw, s, rec)
            else:
                s = s or 'Slashface'
                raw = _waiting(raw, SCARS[s][0], REWARDS.get(s, 'ResReward_PinnicleScar_' + s), rec, kind == 'traitor')
            if kind == 'nemesis':
                raw = add_traits(raw, [], [LUCKY], rec)
            added.append(raw)
            ms = rng.randint(*timer) * 1000
            events.append(_event(faction, 'CheatDeath_Betrayal' if kind == 'traitor' else
                                 'RoleTransformation_Ambush' if alive else 'CheatDeath_Ambush', number, ms))
            what = '%s через %d мин игры' % (TITLES[s] if s else 'жив', ms // 60000)
            kind = 'changed' if alive else kind
        lines.append('%s %s, ур. %d — %s, %s: %s' % (o['name'], o['title'], level, orcs.REGIONS[faction], KIND[kind],
                                                    what))
    out = base
    for a, b, raw in sorted(edits, reverse=True):
        out = out[:a] + raw + out[b:]
    d = len(out) - len(base)
    if d:
        out = bytearray(out)
        bp, size = sv.block(base, 'WHDC')
        struct.pack_into('<I', out, bp + 8, size + d)
        struct.pack_into('<I', out, bp + 16, size + d - 4)
        out = bytes(sv.fix_lengths(out, d))
    out = _append(out, added, events, rec)
    log('Враги из пройденной игры: %d (предателей %d); уровень — верх полосы региона +%d…+%d'
        % (len(lines), len(traitors), *LEVEL_UP))
    for s in lines:
        log('  ' + s)
    return out, numbers


def _queue(t, rec):
    """Token indexes of the Nemesis queue entries: the run of 7-token entries right after a count equal to its
    length (an entry's region may be empty — the first one of a prologue save is)."""
    def entry(i):
        return (t[i].type == 0x0C and t[i].value == 1 and t[i + 1].type == 0 and t[i + 2].type == 0
                and t[i + 3].type == 0 and t[i + 4].type == 4 and t[i + 5].type == 8 and t[i + 6].type == 4
                and (not t[i + 1].value or (rec(t[i + 1].value) or '').startswith('Faction_')))
    for i in range(1, len(t) - 7):
        if t[i - 1].type == 4 and t[i - 1].value > 0 and entry(i):
            run = [i + 7 * k for k in range(t[i - 1].value)]
            if all(j + 7 <= len(t) and entry(j) for j in run):
                return run
    raise sv.SaveError('Не найдена очередь Немезиды в сохранении.')


def _append(buf, records, events, rec):
    """Records at the end of MainGame (its count grows) and their events into the Nemesis queue (its count too)."""
    if not records:
        return buf
    p, size = sv.block(buf, 'WHDC')
    t = sv.tokens(buf, p + 20, p + 16 + size)
    mg = next(i for i in range(len(t)) if t[i].type == 0 and t[i].value == name_hash('MainGame')
              and t[i + 1].type == 0x0C)
    _, _, end = army._table(buf, rec)
    q = _queue(t, rec)
    cnt = t[q[0] - 1]
    add_r, add_e = b''.join(records), b''.join(events)
    at_r, at_e = t[end].pos, t[q[0]].pos
    assert at_r < at_e
    out = bytearray(buf[:at_r] + add_r + buf[at_r:at_e] + add_e + buf[at_e:])
    struct.pack_into('<i', out, t[mg + 2].pos + 1, t[mg + 2].value + len(records))
    struct.pack_into('<i', out, cnt.pos + len(add_r) + 1, cnt.value + len(events))
    d = len(add_r) + len(add_e)
    struct.pack_into('<I', out, p + 8, size + d)
    struct.pack_into('<I', out, p + 16, size + d - 4)
    return bytes(sv.fix_lengths(out, d))
