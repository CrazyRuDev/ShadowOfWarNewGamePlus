"""Orcs of a save (research): state part (number, name, faction, region, AI class, hierarchy slot), the _NPC_ id
and the description (flags, level, role, tribe, traits).

    python research/orcs2.py <save> [--all]
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app', 'engine'))
from sowtool import save as sv                        # noqa: E402
from sowtool.gamedata import GameData                 # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLAGS = ['IsResurrected', 'IsSpawned', 'IsDead', 'KilledByPlayer', 'CanResurrect', 'PresentedToPlayer',
         'CameraPresented', 'IdentityPresented', 'Dominated', 'HasEverSpawned', 'IgnorePlayerLevelRestriction',
         'SimEventActive', 'Vow', 'HasTraitLootBonus', 'HasTraitBypassIntel', 'UNUSED1', 'ResurrectedThisSpawn',
         'SeveredHead', 'Squealer', 'HasTraitNPCSummon', 'HasAddedInitialThreatThisSpawn', 'IsDeadMockMember',
         'CanInterrogateAbout', 'PreventLocationChangeUntilSpawn', 'RevengeTarget', 'WasEverPresetFactionMember',
         'SpawnedAsNemesis', 'PlayerFollower', 'Spy', 'PlayerBodyguard', 'CanDisplayRoleName', 'CanHaveTribe',
         'Builder_CanNotSave', 'Builder_DisableSimEvents', 'TraitPickersDirty', 'IsNew', 'Prisoner',
         'Builder_RemoveAfterQuest', 'DisableTraitChanges', 'DisableRelationships', 'CanNotDropLoot',
         'CanNotChangeXPLevel', 'CanNotApplyContract', 'CanNotHaveSimEventIfHenchman', 'CalcXPLevelOnAssignToRow',
         'Builder_NeverRemove', 'PreventDeathThisSpawn', 'IsGuestOverlord', 'PlayerBodyguard_Slot0',
         'PlayerBodyguard_Slot1', 'PlayerBodyguard_Slot2', 'Mercenary']


def orcs(buf, gd):
    rec = gd.record
    p, size = sv.block(buf, 'WHDC')
    t = sv.tokens(buf, p + 20, p + 16 + size)
    ids = [k for k, x in enumerate(t) if x.type == 0x0F and '_NPC_' in x.value]
    out = []
    for n, k in enumerate(ids):
        # state part: 04 number | 09 8b | 08 name | 00 Faction_*/InvasionFaction_* | 00 Faction_* | 00 AI_* |
        # 00 hierarchy slot (0 = none) | ... then the worn gear, then the _NPC_ id
        lo = ids[n - 1] if n else max(0, k - 2000)
        st = None
        for j in range(k - 1, lo, -1):
            if t[j].type == 0x08 and t[j + 1].type == 0 and \
                    re.match(r'(Invasion)?Faction_', rec(t[j + 1].value) or '') and t[j - 1].type == 0x09:
                st = j
                break
        o = dict(npc=t[k].value, tok=k)
        if st is not None:
            o['number'] = t[st - 2].value if t[st - 2].type == 4 else None
            o['name'] = gd.text.get(t[st].value) or '#%08x' % t[st].value
            names = [rec(t[st + i].value) or ('#%08x' % t[st + i].value if t[st + i].value else '') for i in (1, 2, 3, 4)]
            o['invasion'], o['faction'], o['ai'], o['slot'] = names
        hi = ids[n + 1] if n + 1 < len(ids) else len(t)
        d = t[k + 1:hi]
        f = next((x for x in d if x.type == 0x05), None)
        flags = int.from_bytes(f.value, 'little') if f else 0
        o['flags'] = [FLAGS[b] for b in range(len(FLAGS)) if flags >> b & 1]
        names = [rec(x.value) or '' for x in d if x.type == 0]
        o['role'] = next((x for x in names if x.startswith('Role_')), '')
        o['tribe'] = next((x for x in names if x.startswith('TribeDef_')), '')
        o['rarity'] = next((x for x in names if x.startswith('Marker_Rarity') or 'Rarity' in x), '')
        o['traits'] = [x for x in names if x.startswith('Picker_')]
        ints = [x.value for x in d[:40] if x.type == 4]
        o['ints'] = ints[:12]
        out.append(o)
    return out


def story_reasons(o):
    """Why an orc belongs to the story (empty = an ordinary Nemesis orc), from the save's own data only."""
    r = []
    if 'WasEverPresetFactionMember' in o['flags']:
        r.append('заранее заданный персонаж (WasEverPresetFactionMember)')
    if 'DisableTraitChanges' in o['flags']:
        r.append('особенности не меняются (DisableTraitChanges)')
    if 'DisableRelationships' in o['flags']:
        r.append('без отношений с орками (DisableRelationships)')
    if any(f.startswith('Builder_') for f in o['flags']):
        r.append('создан заданием (Builder_*)')
    if o.get('ai', '').startswith('GP_'):
        r.append('сюжетный класс %s' % o['ai'])
    if o['tribe'] == 'TribeDef_Sauron':
        r.append('племя Саурона (назгулы)')
    if not o['tribe']:
        r.append('без племени')
    return r


def title(gd, role):
    t = gd.role_title(role) if role else None
    return t or ''


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    path = sys.argv[1]
    gd = GameData(os.path.join(ROOT, 'app', 'gui', 'data', 'game.gamedb'),
                  os.path.join(ROOT, 'app', 'gui', 'data', 'string_ruru.strdb'))
    buf, _ = sv.load(path)
    all_ = orcs(buf, gd)
    alive = [o for o in all_ if 'IsDead' not in o['flags']]
    print('орков %d, живых %d, последователей %d' % (len(all_), len(alive),
                                                     sum('PlayerFollower' in o['flags'] for o in alive)))
    pool = [o for o in alive if 'PlayerFollower' not in o['flags'] and not o.get('slot')]
    story = [o for o in all_ if story_reasons(o)]
    print('сюжетных (по данным): %d — %s' % (len(story), ', '.join(sorted({o.get('name', '?') for o in story}))))
    if '--story' in sys.argv:
        for o in story:
            print('  %-5s %-30s %s' % (o.get('number'), o.get('name', '?') + ' ' + title(gd, o['role']),
                                       '; '.join(story_reasons(o))))
    pool = [o for o in pool if not story_reasons(o)]
    print('живых врагов без места в иерархии, не сюжетных: %d' % len(pool))
    for o in (all_ if '--all' in sys.argv else pool):
        print('%-5s %-28s %-24s %-18s %-14s %s | %s | %s' % (
            o.get('number'), (o.get('name') or '?') + ' ' + title(gd, o['role']), o.get('faction', ''),
            o.get('ai', ''), o['tribe'].replace('TribeDef_', ''), o.get('slot', '') or '-',
            ','.join(f for f in o['flags'] if f in ('IsSpawned', 'PresentedToPlayer', 'IdentityPresented', 'Prisoner',
                                                     'Spy', 'Mercenary', 'Builder_NeverRemove', 'IsNew')),
            o['ints'][:6]))
