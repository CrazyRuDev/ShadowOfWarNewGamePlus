"""Orcs of a save (the Nemesis army): who they are, what they did to Talion, and which of them are worth bringing
into the new game+.

MainGame orc table (WHDC block): 00 MainGame | 0c 1 | 04 <cells> | records. A record: 0c 01 | 04 <number> |
09 | 08 <name> | 00 Faction | 00 Faction | 00 AI_<class> | 00 <hierarchy place or 0> | ...gear... |
0f <id>_NPC_<n> | 09 | 04 | 04 | 04 | 0c | 0f | 0f | 08 <level-1> | ... | 05 <flags> | 00 Role_* | ...
The history: pairs 00 <event> 03 <day>. The death record: 00 TraitLevelOffset_* | 00 | 04 | 00 <status> |
00 Resurrection_<cause> | 03 | 03 | 04 <killer: orc number, -1 = Talion> | 00 <killer model> | ...
"""
import math
import re

from . import save as sv
from .gamedata import clean, name_hash

FLAGS = ['IsResurrected', 'IsSpawned', 'IsDead', 'KilledByPlayer', 'CanResurrect', 'PresentedToPlayer',
         'CameraPresented', 'IdentityPresented', 'Dominated', 'HasEverSpawned', 'IgnorePlayerLevelRestriction',
         'SimEventActive', 'Vow', 'HasTraitLootBonus', 'HasTraitBypassIntel', 'UNUSED1', 'ResurrectedThisSpawn',
         'SeveredHead', 'Squealer', 'HasTraitNPCSummon', 'HasAddedInitialThreatThisSpawn', 'IsDeadMockMember',
         'CanInterrogateAbout', 'PreventLocationChangeUntilSpawn', 'RevengeTarget', 'WasEverPresetFactionMember',
         'SpawnedAsNemesis', 'PlayerFollower', 'Spy', 'PlayerBodyguard', 'CanDisplayRoleName', 'CanHaveTribe']

REGIONS = {'Faction_MinasIthil': 'Минас-Моргул', 'Faction_MtnPass': 'Кирит-Унгол', 'Faction_snowMtn': 'Серегост',
           'Faction_volcano': 'Горгорот', 'Faction_island': 'Нурн', 'Faction_desert_Real': 'Литлад',
           'Faction_desert': 'Литлад'}

CLASSES = {'Infantry': 'воин', 'Berserker': 'берсерк', 'Archer': 'лучник', 'Defender': 'защитник',
           'Spearman': 'охотник', 'Hunter': 'охотник', 'Olog_Infantry': 'олог', 'Olog_Berserker': 'олог-берсерк',
           'Olog_Defender': 'олог-защитник', 'Olog_Archer': 'олог-лучник', 'Savage': 'дикарь'}

RARITY = {'Common': 'обычный', 'Epic': 'эпический', 'Legendary': 'легендарный', 'Unique': 'уникальный'}

PLACES = {'Captain': 'капитан', 'Outer_Warchief': 'вождь', 'Inner_Warchief': 'вождь', 'Warchief': 'вождь',
          'Overlord': 'правитель', 'Bodyguard': 'охранник'}

# events of the history about Talion: (prefix, text, kind); kind feeds the counters and the score
EVENTS = [('ActiveKillPlayer', 'убил Талиона', 'kill'),
          ('ActiveGotPlayerInLastChance', 'довёл Талиона до последнего шанса', 'last'),
          ('ArcherPutsPlayerInLastChance', 'довёл Талиона до последнего шанса (лучник)', 'last'),
          ('ActiveReverseLastChance', 'Талион вырвался из последнего шанса', ''),
          ('ActiveKilledByPlayer', 'убит Талионом', 'killed'),
          ('ActiveSurvivedVsPlayer', 'выжил в бою с Талионом', 'fled'),
          ('ActiveFlee', 'сбежал от Талиона', 'fled'),
          ('ActiveDespawnWhileFleeing', 'сбежал от Талиона', 'fled'),
          ('FleeRunStart', 'бросился бежать', ''),
          ('Resurrected_', 'вернулся из мёртвых', 'back'),
          ('WillResurrect_', 'выживет после гибели', ''),
          ('Resurrection_', 'погиб', 'death'),
          ('ActiveInitialPlayerThreat', 'встретил Талиона', 'met'),
          ('ActiveShowdownGiven', 'вызвал Талиона на бой', 'met'),
          ('ActiveIdentify', 'раскрыт Талионом', ''),
          ('ActiveGainInterrogationIntel', 'Талион узнал о нём сведения', ''),
          ('ActiveSetInterrogationSubject', 'Талион допросил о нём', ''),
          ('ActiveDominationStarted', 'Талион начал подчинение', ''),
          ('Domination_Recruit', 'подчинён Талионом', ''),
          ('Domination_Shame', 'опозорен Талионом', ''),
          ('Domination_Defend', 'защищался от подчинения', ''),
          ('Domination_Retreat', 'отступил при подчинении', ''),
          ('IsPlayerFollowerApply', 'стал последователем Талиона', ''),
          ('IsPlayerFollowerRemove', 'перестал быть последователем', ''),
          ('BecomeBodyguardToPlayer', 'стал телохранителем Талиона', ''),
          ('ActiveRevivedByPlayer', 'спасён Талионом', ''),
          ('BrotherKilledByPlayer', 'Талион убил его кровного брата', ''),
          ('ActiveBecame_Shame', 'обезумел от позора', ''),
          ('ActiveKillNamedAI', 'убил капитана', ''),
          ('ActiveKilledOnSimEvent', 'погиб в событии Немезиды', ''),
          ('ActiveLevelUpPlayerLimitLevel', 'поднялся в уровне', ''),
          ('Promote', 'повышен', ''),
          ('HierarchyPresented', 'занял место в иерархии', ''),
          ('ActiveHateTriggered', 'пришёл в ярость', ''),
          ('ActiveFearTriggered', 'испугался', ''),
          ('ActiveTerrorTriggered', 'пришёл в ужас', ''),
          ('Duel', 'дуэль', ''),
          ('Feast', 'пир', ''),
          ('Trial', 'испытание', ''),
          ('Execution', 'казнь', ''),
          ('Raid', 'набег', ''),
          ('Chase', 'погоня', ''),
          ('Ambush_Presented', 'устроил засаду', ''),
          ('ActiveVowApplied', 'дал клятву', ''),
          ('ActiveKillTroll', 'убил тролля', ''),
          ('ActiveKillWarg', 'убил варга', ''),
          ('ActiveRecruitedSuccess', 'завербован', ''),
          ('ActiveBleedout', 'истекал кровью', ''),
          ('ActiveInterrogated', 'допрошен', ''),
          ('ActiveUnkPresentation', 'показался Талиону', ''),
          ('ActiveDespawn', 'ушёл', ''),
          ('FactionMember_RoleSelected', 'получил титул', ''),
          ('PromoteDead', 'занял место погибшего', ''),
          ('PromoteEmpty', 'занял пустое место', ''),
          ('EjectWarchief', 'изгнан из вождей', ''),
          ('WarchiefBrandedEjection', 'изгнан из вождей', ''),
          ('BecomeBodyguardToWarchief', 'стал охранником вождя', ''),
          ('Contract_', 'наёмник: контракт', ''),
          ('FortDefense', 'оборона крепости', ''),
          ('Gauntlet', 'испытание бойцов', ''),
          ('BossKilled', 'убит в бою', ''),
          ('HenchmenKilled', 'охранники убиты', '')]

PERSONALITY = {'Brute': 'грубиян', 'Twisted': 'безумец', 'Professional': 'профессионал', 'Whiner': 'нытик',
               'Wise': 'мудрец', 'Clever': 'хитрец', 'Bully': 'задира', 'Zealot': 'фанатик', 'Gentleman': 'джентльмен'}
LOOKS = {'Slim': 'худой', 'BigNose': 'большой нос', 'Buff': 'мускулистый', 'Stocky': 'коренастый'}

CAUSES = {'PlayerSlash': 'зарублен Талионом', 'Bleedout': 'истёк кровью', 'HeadRemoved': 'обезглавлен',
          'LeftArmLower_Removed': 'отрублена рука', 'RightArmLower_Removed': 'отрублена рука', 'Poisoned': 'отравлен',
          'OrcSlash': 'зарублен орком', 'Burned': 'сожжён', 'Fire': 'сожжён', 'Frost': 'заморожен',
          'Cursed': 'проклят', 'Drained': 'осушён', 'Beast': 'убит зверем', 'Ranged': 'застрелен',
          'Explosion': 'взорван', 'Fall': 'разбился', 'Stealth': 'убит скрытно', 'Execution': 'казнён'}

# the enemies brought back: at most PICK_TOTAL, only those with a score of MIN_SCORE or more (about "killed Talion
# once" or "brought him to his last chance and fled") — in two of four players' saves the 12th-20th had 1-3, orcs met
# on the way and remembered by nobody (decided with the user 2026-10-22)
PICK_TOTAL, MIN_SCORE = 15, 5
# The memory of new game+ (decided with the user 2026-10-23). The history brought into a new game gets day PAST_DAY
# (army._prepare); the game writes its own events with the current day and keeps the last 32 of them (the oldest go,
# checked on 100 orcs). So in a finished new game+ the events of day 0 are the past games (or the very first day of a
# game: the prologue in Minas Morgul, where none of our enemies stand) — the score counts them by HISTORY:
#   decay — at half (and the transfer thins them by half, see army._prepare: a past cycle fades with every new one),
#   last  — not at all (only what the orc did in the game just finished), all — like the events of the game itself.
PAST_DAY = 0
HISTORY_MODES = {'decay': 0.5, 'last': 0, 'all': 1}
HISTORY = 'decay'
SCORED = ('kill', 'last', 'fled', 'back')                # the kinds the score counts (and the transfer thins)
# Traits that make an orc hard to beat: a bonus to its danger. The weights are counted from the player's own save
# (trait_weights): how much more often a trait is found among the orcs that killed this Talion than among the other
# orcs he met — so they follow each player's style. «Без шансов» (no last chance) is always the strongest.
NO_LAST_CHANCE, NO_LAST_CHANCE_WEIGHT = 'Picker_NoLastChance', 3
# at least this much whatever the statistics say: the Tank gets back up once with new strength ("Презирает
# смерть" on screen), checked in a fight by the user — the counted weight was only 0.5
MIN_WEIGHTS = {'Picker_BaseStrength_Tank': 1.5}
TRAIT_CAP = 5            # the traits together add at most this: what the orc did to Talion stays the main thing
MIN_KILLERS, MIN_WITH_TRAIT, MAX_WEIGHT = 8, 3, 2
# strengths only: weaknesses (vulnerable, afraid, enraged by...) and markers are not counted
NOT_STRENGTH = re.compile(r'Resistant|Vulnerable|WeakBy|Fear_|Hate_|Terror_|OrcRarity|InHierarchy|BodyguardCount|'
                          r'Betray|NamedEnemy|Follower_|SlowAdapt|GiveUpOnPlayer')
# When the save has too few killers to count: weights from the user's experience on the highest difficulty
# (calibrated on his 37 killers and another player's 10).
FALLBACK_WEIGHTS = {'Picker_NoLastChance': 3,              # «Без шансов»: x2.7 / x2.0
                 'Picker_BaseStrength_Tank': 2,            # танк, «Презирает смерть» в бою: восполняет здоровье
                 'Picker_Resist_Combat_Immune': 2,         # «Неуязвим к казни»: ломает натиск на 2–3 капитанов
                 'Picker_QuickMovement': 2,                # «Проворный»: уворачивается от всего
                 'Picker_QuickThrow': 1.5,                 # «Метание кинжалов»: x3.1 у пользователя
                 'Picker_BaseStrength_Assassin': 1,        # «Наёмный убийца»: x2.5 у пользователя
                 'Picker_Resist_Ranged_Immune': 1,         # «Неуязвим к обстрелу»: x1.5 / x1.6
                 'Picker_BaseStrength_CombatMaster': 1,    # «Истребитель»: x2.0 / x1.8
                 'Picker_TribeAttack_Outlaw': 1,           # бола Преступников: x4.3 / x2.0
                 'Picker_Tracker': 1,                      # «Умелый охотник»: x2.1 / x1.8
                 'Picker_Resist_Stealth_Immune': 0.5}      # «Бдительный»: наименее опасный


def _clean(name):
    return re.sub(r'_\d+$', '', name)


def event_text(ev):
    for prefix, text, _ in EVENTS:
        if ev.startswith(prefix):
            return text
    return None


def event_kind(ev):
    for prefix, _, kind in EVENTS:
        if ev.startswith(prefix):
            return kind
    return ''


def story_reasons(o):
    """Why an orc belongs to the story (empty = an ordinary Nemesis orc), from the save's own data only."""
    r = []
    if 'WasEverPresetFactionMember' in o['flags']:
        r.append('заранее заданный персонаж')
    if o['ai'].startswith('GP_'):
        r.append('сюжетный класс')
    if o['tribe_key'] == 'TribeDef_Sauron':
        r.append('назгул')
    if not o['tribe_key']:
        r.append('без племени')
    if not o['role_key']:
        r.append('без титула')          # every Nemesis orc has a role; the story ones (Бруз, Зог, ...) have none
    return r


class Names:
    """Russian names of the game's records, cached."""

    def __init__(self, gd):
        self.gd = gd
        self.traits = {}
        defs = gd.category('Faction/Traits/Definitions')
        self._defs = {n: k for k, (_, n) in enumerate(defs)}
        self._defrecs = defs

    def role(self, role):
        return (self.gd.role_title(role) or '') if role else ''

    def tribe(self, tribe):
        core = tribe.replace('TribeDef_', '')
        core = {'Sorcerous': 'Mystic'}.get(core, core)       # the Mystics' record and their text differ
        return self.gd.say('App_Name_%sTribe' % core) or core

    def ai_class(self, ai):
        core = re.sub(r'^AI_', '', ai)
        if core in CLASSES:
            return CLASSES[core]
        t = self.gd.say('UI_MembersSummary_Class_' + core) or self.gd.say('App_Name_' + core)
        return t.lower() if t else core

    def trait(self, picker):
        """(name, description) of a Picker_ trait, or None for hidden mechanics."""
        if picker in self.traits:
            return self.traits[picker]
        s = picker[len('Picker_'):]
        cands = [s, 'Quirk_' + s, 'Trait_' + s]
        m = re.match(r'Resist_(\w+?)_(Immune|Vulnerable|Resistant|MortalVulnerable)$', s)
        if m:
            cands = [m.group(2) + '_' + m.group(1)] + cands
        out = None
        for c in cands:
            if c not in self._defs:
                continue
            f = self.gd.fields(self._defrecs, self._defs[c])
            keys = [self.gd._pstr(v) for v in f if self.gd._is_name(v)]
            name = next((self.gd.say(k) for k in keys if k.startswith(('IntRes_', 'Orc_Ability_'))
                         and not k.endswith('_Desc') and self.gd.say(k)), None)
            desc = next((self.gd.say(k) for k in keys if k.endswith('_Desc') and self.gd.say(k)), None)
            hint = next((self.gd.say(k) for k in keys if k.startswith('Trait_Hint_') and self.gd.say(k)), None)
            if name or hint:
                out = (clean(name or hint), clean(desc or ''))
                break
        self.traits[picker] = out
        return out


def table(buf, rec):
    """(tokens, [(start, end) token ranges of the MainGame records])."""
    p, size = sv.block(buf, 'WHDC')
    t = sv.tokens(buf, p + 20, p + 16 + size)
    main = name_hash('MainGame')
    mg = next(i for i in range(len(t)) if t[i].type == 0 and t[i].value == main and t[i + 1].type == 0x0C)
    starts = [j - 1 for j in range(mg + 3, len(t) - 3) if t[j - 1].type == 0x0C and t[j - 1].value == 1
              and t[j].type == 4 and t[j + 1].type == 9 and t[j + 2].type == 8 and t[j + 3].type == 0
              and re.match(r'(Invasion)?Faction_', rec(t[j + 3].value) or '')]
    bg = name_hash('BG')
    end = next(i for i in range(starts[-1], len(t)) if t[i].type == 0 and t[i].value == bg)
    while t[end - 1].type == 4:
        end -= 1
    return t, [(s, starts[k + 1] if k + 1 < len(starts) else end) for k, s in enumerate(starts)]


def read(buf, gd):
    """All orcs of the MainGame table as dicts."""
    rec = gd.record
    names = Names(gd)
    t, ranges = table(buf, rec)
    by_num = {}
    out = []
    for s, e in ranges:
        # the description starts at the id string (empty in a fresh game): 0f id | 09 | 04 | 04 | 04 | 0c | 0f | 0f | 08
        npc = _desc_start(t, s, e)
        if npc is None:
            continue
        num = t[s + 1].value
        o = dict(number=num, name=gd.text.get(t[s + 3].value) or '?', faction=rec(t[s + 4].value) or '',
                 ai=rec(t[s + 6].value) or '', place_key=rec(t[s + 7].value) or '', npc=t[npc].value)
        lv = next((t[i + 1].value for i in range(npc, min(npc + 12, e)) if t[i].type == 8 and t[i + 1].type == 4), 0)
        o['level'] = lv + 1
        f = next((t[i] for i in range(npc, e) if t[i].type == 0x05), None)
        bits = int.from_bytes(f.value, 'little') if f else 0
        o['flags'] = [FLAGS[b] for b in range(len(FLAGS)) if bits >> b & 1]
        keys = [rec(t[i].value) or '' for i in range(npc, e) if t[i].type == 0]
        o['markers'] = [k for k in keys if 'Marker' in k]
        o['role_key'] = next((k for k in keys if k.startswith('Role_')), '')
        o['tribe_key'] = next((k for k in keys if k.startswith('TribeDef_')), '')
        rar = next((k for k in keys if k.startswith('Marker_OrcRarity_') and not k.endswith('_Forced')), '')
        o['rarity'] = RARITY.get(rar.replace('Marker_OrcRarity_', ''), '')
        pers = re.sub(r'^PersonalityMarker_', '', next((k for k in keys if k.startswith('PersonalityMarker_')), ''))
        o['personality'] = PERSONALITY.get(pers.rstrip('0123456789'), pers)
        o['looks'] = [LOOKS.get(x, x) for x in (k.replace('Marker_AppearanceTag_', '') for k in keys
                                                if k.startswith('Marker_AppearanceTag_'))]
        o['rewards'] = [k for k in keys if k.startswith('ResReward_')]
        o['traits'] = [k for k in keys if k.startswith('Picker_')]
        # history and the death record
        tlo = next((i for i in range(npc, e) if t[i].type == 0 and (rec(t[i].value) or '').startswith('TraitLevelOffset_')), None)
        o['history'] = [(rec(t[i].value), t[i + 1].value) for i in range(s, e - 1)
                        if t[i].type == 0 and t[i].value and t[i + 1].type == 3 and rec(t[i].value)
                        and (tlo is None or i != tlo + 4)]
        o['death_cause'], o['killer'], o['killer_model'], o['status'] = '', None, '', ''
        if tlo is not None and tlo + 8 < e:
            o['status'] = rec(t[tlo + 3].value) or ''
            o['death_cause'] = (rec(t[tlo + 4].value) or '').replace('Resurrection_', '')
            if t[tlo + 7].type == 4 and o['death_cause']:
                o['killer'] = t[tlo + 7].value
                o['killer_model'] = rec(t[tlo + 8].value) or ''
        cnt = {'kill': 0, 'last': 0, 'fled': 0, 'back': 0, 'death': 0, 'killed': 0, 'met': 0}
        past = dict.fromkeys(SCORED, 0)               # of them: events of past games (day PAST_DAY)
        for ev, day in o['history']:
            k = event_kind(ev)
            if k:
                cnt[k] += 1
                if k in past and day == PAST_DAY:
                    past[k] += 1
        if 'IsDead' in o['flags'] and not cnt['death']:
            cnt['death'] = 1
        o.update(cnt)
        o['past'] = past
        w = HISTORY_MODES[HISTORY]
        sc = {k: cnt[k] - past[k] + w * past[k] for k in SCORED}
        o['kill_score'] = sc['kill']
        o['score'] = 3 * sc['kill'] + 3 * sc['last'] + sc['fled'] + 2 * sc['back']
        o['danger'], o['danger_traits'], o['danger_trait_names'] = o['score'], [], []
        talion = [ev for ev, _ in o['history'] if event_kind(ev) in ('kill', 'last', 'killed', 'fled', 'met')
                  or ev.startswith(('ActiveDomination', 'Domination_', 'ActiveIdentify', 'ActiveRevivedByPlayer',
                                    'ActiveReverseLastChance', 'IsPlayerFollower', 'BecomeBodyguardToPlayer',
                                    'ActiveGainInterrogationIntel', 'ActiveSetInterrogationSubject'))]
        o['met'] = bool(talion) or 'PresentedToPlayer' in o['flags']
        o['dead'] = 'IsDead' in o['flags']
        o['follower'] = 'PlayerFollower' in o['flags']
        o['story'] = story_reasons(o)
        o['region'] = REGIONS.get(o['faction'], o['faction'])
        m = re.match(r'\w+?_Row_(\w+?)(?:_\d+)?$', o['place_key'])
        o['place'] = PLACES.get(m.group(1), m.group(1)) if m else ''
        o['title'] = names.role(o['role_key'])
        o['tribe'] = names.tribe(o['tribe_key']) if o['tribe_key'] else ''
        o['class'] = names.ai_class(o['ai'])
        o['trait_names'] = [x for x in (names.trait(p) for p in o['traits']) if x]
        o['trait_map'] = {p: names.trait(p)[0] for p in o['traits'] if names.trait(p)}
        by_num[num] = o
        out.append(o)
    for o in out:
        k = o['killer']
        o['killer_name'] = '' if k is None else 'Талион' if k == -1 else \
            ('%s %s' % (by_num[k]['name'], by_num[k]['title'])).strip() if k in by_num else 'орк №%d' % k
    return out


def trait_weights(orcs):
    """({trait: weight}, how they were counted). Among the non-story enemies Talion met: the share of a trait among
    those who killed him against its share among the others (smoothed); weight = log2 of that, 0..MAX_WEIGHT, for
    strengths found at least at MIN_WITH_TRAIT killers. «Без шансов» — always NO_LAST_CHANCE_WEIGHT. Too few
    killers — FALLBACK_WEIGHTS."""
    pool = [o for o in orcs if o['met'] and not o['story'] and not o['follower']]
    killers = [o for o in pool if o['kill'] > 0]
    others = [o for o in pool if o['kill'] == 0]
    if len(killers) < MIN_KILLERS or not others:
        return dict(FALLBACK_WEIGHTS), 'убийц Талиона %d — мало для подсчёта, веса по опыту' % len(killers)
    count_k, count_o = {}, {}
    for group, count in ((killers, count_k), (others, count_o)):
        for o in group:
            for p in set(o['trait_map']):
                count[p] = count.get(p, 0) + 1
    weights = {NO_LAST_CHANCE: NO_LAST_CHANCE_WEIGHT}
    for p, n in count_k.items():
        if p == NO_LAST_CHANCE or n < MIN_WITH_TRAIT or NOT_STRENGTH.search(p):
            continue
        lift = (n / len(killers)) / ((count_o.get(p, 0) + 0.5) / (len(others) + 1))
        w = min(MAX_WEIGHT, round(2 * math.log2(lift)) / 2) if lift > 1 else 0
        if w > 0:
            weights[p] = w
    for p, w in MIN_WEIGHTS.items():
        weights[p] = max(weights.get(p, 0), w)
    return weights, 'посчитаны по %d убийцам Талиона из %d встречавшихся орков' % (len(killers), len(pool))


def apply_weights(orcs, weights):
    for o in orcs:
        o['danger_traits'] = [p for p in o['trait_map'] if p in weights]
        o['danger_trait_names'] = ['%s (+%g)' % (o['trait_map'][p], weights[p]) for p in o['danger_traits']]
        o['danger'] = o['score'] + min(TRAIT_CAP, sum(weights[p] for p in o['danger_traits']))


def past_note(o):
    p = o['past']
    how = {'decay': 'считается вполовину', 'last': 'не считается', 'all': 'считается полностью'}[HISTORY]
    return ('из прошлых игр (убил Талиона %d, последний шанс %d, сбегал %d, возвращался %d) %s'
            % (p['kill'], p['last'], p['fled'], p['back'], how))


def recommend(orcs, total=PICK_TOTAL):
    """Mark the orcs worth bringing back: o['pick'] = way of return, o['target'] = region, o['why'] = reason.
    Rules agreed with the user: non-story orcs who met Talion and did something against him (score >= MIN_SCORE), the
    most dangerous first (what they did + their dangerous traits). The level does not count (decided 2026-10-22):
    the returning orcs get their level from the new game anyway, and killing Talion on level 30 is as much as on
    80. Former followers go too: an ally of the finished game comes back an enemy; on the transfer their flags of
    being Talion's (PlayerFollower, Dominated, Spy, PlayerBodyguard) are cleared — the only thing that sets them
    apart (they stand in the regions' hierarchies like any orc). Killed by another orc: comes back alive.
    The way back is what the build does (returned.place): killed by Talion — "came back beforehand" with the reward of
    returned.comes_back, the others alive; into Nurn (and Cirith Ungol on the prologue base)."""
    weights, how = trait_weights(orcs)
    apply_weights(orcs, weights)
    recommend.weights, recommend.how = weights, how
    main = []
    for o in orcs:
        o['pick'], o['why'], o['target'] = '', '', ''
        if o['story'] or not o['met'] or o['score'] < MIN_SCORE:
            continue
        main.append(o)
    main.sort(key=lambda o: (o['danger'], o['score'], o['level']), reverse=True)
    picked = main[:total]
    from .returned import TITLES, comes_back            # returned reads orcs: imported here
    for o in picked:
        why = []
        if o['follower']:
            why.append('бывший последователь Талиона — вернётся врагом')
        why.append('опасность %g: счёт %g (убил Талиона %d, последний шанс %d, сбегал %d, возвращался %d)'
                   % (o['danger'], o['score'], o['kill'], o['last'], o['fled'], o['back']))
        if any(o['past'].values()):
            why.append(past_note(o))
        if o['danger_trait_names']:
            why.append('опасные особенности: ' + ', '.join(o['danger_trait_names']))
        s = comes_back(o)
        if s:
            o['pick'] = 'вернётся: ' + TITLES[s]
            why.append('убит Талионом (%s) — «обманул смерть» заранее: облик, раны и реплика о гибели'
                       % (CAUSES.get(o['death_cause'], o['death_cause']) or 'причина неизвестна'))
        else:
            o['pick'] = 'живым'
            if o['dead']:
                why.append('убит орком (%s) — вернётся живым' % (o['killer_name'] or '?'))
        o['target'] = 'Нурн (на прологе — и Кирит-Унгол)'
        o['why'] = '; '.join(why)
    return picked


def _desc_start(t, s, e):
    """Token index of the description start (the _NPC_ id string, empty in a fresh game), or None."""
    return next((i for i in range(s, e - 9) if t[i].type == 0x0F and t[i + 1].type == 9 and t[i + 5].type == 0x0C
                 and t[i + 6].type == 0x0F and t[i + 7].type == 0x0F and t[i + 8].type == 8), None)


def group(o):
    if o['pick']:
        return 'Рекомендованы к переносу'
    if o['story']:
        return 'Сюжетные'
    if o['follower']:
        return 'Последователи Талиона'
    if not o['met']:
        return 'Не встречались с Талионом'
    return 'Мёртвые враги' if o['dead'] else 'Живые враги'


def details(o):
    """Everything about one orc as text lines."""
    L = ['%s %s' % (o['name'], o['title']), '№%d, уровень %d, %s' % (o['number'], o['level'], o['region'])]
    state = 'мёртв' if o['dead'] else 'жив'
    if o['follower']:
        state += ', последователь Талиона'
    L.append('Состояние: %s%s' % (state, ', место: ' + o['place'] if o['place'] else ', без места в иерархии'))
    L.append('Класс: %s;  племя: %s;  редкость: %s;  характер: %s' % (o['class'], o['tribe'] or '—',
                                                                    o['rarity'] or '—', o['personality'] or '—'))
    if o['looks']:
        L.append('Облик: ' + ', '.join(o['looks']))
    if o['story']:
        L.append('Сюжетный: ' + '; '.join(o['story']))
    if o['pick']:
        L += ['', 'РЕКОМЕНДАЦИЯ: %s → %s' % (o['pick'], o['target']), 'Почему: ' + o['why']]
    L += ['', 'Счёт «насколько докучал»: %g' % o['score'] + ('' if not any(o['past'].values())
                                                             else ' — ' + past_note(o)),
          '  убил Талиона: %d, до последнего шанса: %d, сбегал/выживал: %d, возвращался из мёртвых: %d'
          % (o['kill'], o['last'], o['fled'], o['back']),
          '  убит Талионом: %d, гибелей всего: %d' % (o['killed'], o['death'])]
    if o['death_cause']:
        L.append('Последняя гибель: %s%s' % (CAUSES.get(o['death_cause'], o['death_cause']),
                                            ', убийца: ' + o['killer_name'] if o['killer_name'] else ''))
    if o['rewards']:
        L.append('Награды за возвращение: ' + ', '.join(r.replace('ResReward_', '') for r in o['rewards']))
    if o['trait_names']:
        L += ['', 'Особенности:'] + ['  • %s%s' % (n, ' — ' + d if d else '') for n, d in o['trait_names']]
    if o['history']:
        L += ['', 'История (день — событие):']
        for ev, day in sorted(o['history'], key=lambda x: x[1]):
            txt = event_text(ev)
            L.append('  %3d  %s' % (day, txt + '  (' + _clean(ev) + ')' if txt else _clean(ev)))
    return L
