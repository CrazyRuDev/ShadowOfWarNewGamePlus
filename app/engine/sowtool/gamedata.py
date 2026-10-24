"""Names and texts from the game database (game.gamedb, 'GADB' v17) and the text table (string.strdb, 'SKDB' v9).

A save stores records and text keys as name_hash(name). Database records are grouped into categories;
a record refers to another one as (list << 20) | index, where list numbers a global list of categories.
"""
import re
import struct

# Character weights of the game's name hash (ShadowOfWar.exe 1.0.8874, function 0x140423E70):
# letters ignore case, digits and punctuation have their own codes, everything else counts as 0.
_W = [0] * 256
_PUNCT = {32: 37, 33: 58, 34: 51, 35: 60, 36: 61, 37: 62, 38: 64, 39: 50, 40: 66, 41: 67, 42: 65, 43: 40,
          44: 54, 45: 39, 46: 55, 47: 52, 58: 49, 59: 48, 60: 56, 61: 41, 62: 57, 63: 53, 64: 59,
          91: 44, 92: 42, 93: 45, 94: 63, 95: 38, 96: 68, 123: 46, 124: 43, 125: 47, 126: 69}
for _c, _v in _PUNCT.items():
    _W[_c] = _v
for _d in range(10):
    _W[48 + _d] = 27 + _d
for _l in range(26):
    _W[65 + _l] = _W[97 + _l] = 1 + _l


def name_hash(name):
    """Id the game uses for a database record or a text key: h = h * 0x397 + weight(char)."""
    h = 0
    for c in name.encode('latin1'):
        h = (h * 0x397 + _W[c]) & 0xFFFFFFFF
    return h


def load_strdb(path):
    """Text key hash -> text. Header 'SKDB', version, header size, count; (key, offset in chars) pairs; UTF-16."""
    d = open(path, 'rb').read()
    _, _, hdr, cnt = struct.unpack_from('<4sIII', d, 0)
    base = hdr + cnt * 8
    out = {}
    for k in range(cnt):
        h, off = struct.unpack_from('<II', d, hdr + 8 * k)
        s = base + off * 2
        e = s
        while d[e:e + 2] != b'\0\0':
            e += 2
        out[h] = d[s:e].decode('utf-16-le')
    return out


# Lists of the skill menu: rows (MenuTreeBase) -> nodes (MenuTreeNode/Skills) -> PSS_ records
# (Inventory/Skill/Skills) and child nodes (MenuTreeNode/SkillChild). Found by resolving the references.
LIST_NODES, LIST_PSS, LIST_CHILD = 1428, 947, 320
SKILL_ROWS = [('SkillRow1_Sword', 'Бой'), ('SkillRow2_Dagger', 'Разбой'), ('SkillRow3_Bow', 'Дальний бой'),
              ('SkillRow4_Armor', 'Призрак'), ('SkillRow5_Cape', 'Наездник'), ('SkillRow6_RingWraith', 'История')]
# PSS_ records whose PS_..._UNLOCK item is not named after them
PSS_TO_PS = {
    'PSS_ShadowStrike_Grab_Child3': 'PS_ShadowGrab_Child3_UNLOCK',
    'PSS_ShadowStrike_Child3_ShadowBrand': 'PS_ShadowStrike_Kill_Child3_ShadowBrand_UNLOCK',
    'PSS_RhythmMovent_NoDbleJump_Parent': 'PS_StealthSprint_Parent_UNLOCK',
    'PSS_Execution_Child1': 'PS_Execution_Child1_WraithExecution_UNLOCK',
    'PSS_BrutalStrike_Child2_ChunkMeter': 'PS_BrutalStrike_C2_ChunkMeter_UNLOCK',
    'PSS_SStoFirePit_Parent': 'PS_SStoFirePits_Parent_UNLOCK',
    'PSS_SStoFirePit_Child1': 'PS_SStoFirePits_Child1_Ghuls_UNLOCK',
    'PSS_SStoFirePit_Child2': 'PS_SStoFirePits_Child2_Spiders_UNLOCK',
    'PSS_SStoFirePit_Child3': 'PS_SStoFirePits_Child3_Poison_UNLOCK',
    'PSS_Brand_Parent_Drain_C1': 'PS_Brand_UNLOCK',
    'PSS_CBMeter_Parent': 'PS_CBGameChanger_UNLOCK',
    'PSS_CBMeter_DarkTalion_Parent': 'PS_CBGameChanger_DarkTalion_UNLOCK',
}

RARITY_LINE = {'легендарный': 'Легендарное', 'эпический': 'Эпическое', 'редкий': 'Редкое', 'обычный': 'Обычное'}
SET_BONUS_KEY = {'Vendetta': 'Bounty'}        # set bonus texts of the Vendetta set are named Bounty
RARITY = {'1Default': 'обычный', '2Standard': 'обычный', '3Rare': 'редкий', '4Epic': 'эпический', '5Lgnd': 'легендарный'}
SLOT = {'1Sword': 'меч', '2Dagger': 'кинжал', '3Bow': 'лук', '4Armor': 'доспехи', '5Cape': 'плащ', '6Ring': 'руна'}


def clean(text):
    """Game text without markup tags and value placeholders."""
    text = re.sub(r'<[^>]*>', '', text)
    text = re.sub(r'\{\d![^}]*\}', 'X', text)
    text = re.sub(r'\{(Blue|Color|Red|Green|Gold|White|Orange|Purple)_?[^}]*\}', '', text)
    text = re.sub(r'\{[A-Za-z][^}]*\}', '[кнопка]', text)
    return re.sub(r'\s+', ' ', text).strip()


# names of Talion's story things (no UI_*_N text): a text key or the name itself
STORY_ITEMS = {'PC_Bow_Celebrimbor': 'App_Name_Azkar', 'PC_Glaive': 'App_Name_Aeglos', 'PC_Glaive_Ground': 'App_Name_Aeglos',
               'RangerT2_Scabbard': 'Ножны Следопыта', 'Talion_Isildur_Ring': 'Кольцо Исилдура'}


class GameData:
    def __init__(self, gamedb_path, strdb_path):
        db = self.db = open(gamedb_path, 'rb').read()
        pool_size = struct.unpack_from('<I', db, 8)[0]
        self.pool = db[0x47:0x47 + pool_size]
        self.records = {}
        for m in re.finditer(rb'[\x20-\x7e]+', self.pool):
            s = m.group().decode('latin1')
            self.records.setdefault(name_hash(s), s)
            # a name right after bytes that look like text (a float before BruzBrothers_Daz_Ambush: '{\x14®={\x14®=')
            tail = re.split(r'[^A-Za-z0-9_]', s)[-1]
            if tail != s and len(tail) >= 3:
                self.records.setdefault(name_hash(tail), tail)
        self.text = load_strdb(strdb_path)
        self.text_names = sorted(self.records[k] for k in self.text if k in self.records)
        self._cats = {}
        self.skill_names = self._skill_names()
        self.skill_tree = self._skill_tree()
        self.level_cost = self._level_cost()
        self._titles = None

    # ---- database access -------------------------------------------------------------------------------
    def _pstr(self, v):
        return self.pool[v:self.pool.index(b'\0', v)].decode('latin1')

    def _is_name(self, v):
        p = self.pool
        return 0 < v < len(p) and p[v - 1] == 0 and 0x20 < p[v] < 0x7F

    def category(self, path):
        """Records of one category as [(offset, name)], in file order.

        Category header: name, type, path ('\\...\\gdb.category06'), 0, record count, hash. A record starts
        with its name, a type word and a 0x08xxxxxx word."""
        if path in self._cats:
            return self._cats[path]
        db, pool = self.db, self.pool
        po = pool.find(b'\x00\\' + path.replace('/', '\\').encode() + b'\\gdb.category06\x00') + 1
        head = db.find(struct.pack('<I', po) + b'\x00\x00\x00\x00', 0x47 + len(pool)) - 8
        count = struct.unpack_from('<I', db, head + 16)[0]
        recs, p = [], head + 24
        while len(recs) < count and p < len(db) - 12:
            name, _, flags = struct.unpack_from('<III', db, p)
            if flags >> 24 == 8 and not flags & 0xFF0000 and self._is_name(name):
                recs.append((p, self._pstr(name)))
            p += 4
        self._cats[path] = recs
        return recs

    def fields(self, recs, k, limit=0x400):
        p = recs[k][0]
        end = recs[k + 1][0] if k + 1 < len(recs) else p + limit
        if not p < end <= p + 0x2000:
            end = p + limit
        return struct.unpack_from('<%dI' % ((end - p) // 4), self.db, p)

    def refs(self, recs, k, lst, target):
        return [target[v & 0xFFFFF][1] for v in self.fields(recs, k)[3:]
                if v >> 20 == lst and (v & 0xFFFFF) < len(target)]

    # ---- skills ----------------------------------------------------------------------------------------
    def _skill_names(self):
        """PS_<skill>_UNLOCK (Inventory/Items) -> PSN_ text key of its Inventory/UIItemData record."""
        items = self.category('Inventory/Items')
        ui = self.category('Inventory/UIItemData')

        def psn(k):
            for v in self.fields(ui, k)[3:]:
                if self._is_name(v) and self.pool.startswith(b'PSN_', v):
                    return self._pstr(v)

        unlocks = [k for k, (_, n) in enumerate(items) if n.startswith('PS_') and n.endswith('_UNLOCK')]
        votes = {}
        for k in unlocks:
            for v in self.fields(items, k)[3:]:
                if v != 0xFFFFFFFF and v >> 20 and (v & 0xFFFFF) < len(ui) and ui[v & 0xFFFFF][1].startswith('PSUID_'):
                    votes[v >> 20] = votes.get(v >> 20, 0) + 1
        ui_list = max(votes, key=votes.get)
        out = {}
        for k in unlocks:
            for v in self.fields(items, k)[3:]:
                if v >> 20 == ui_list and (v & 0xFFFFF) < len(ui):
                    key = psn(v & 0xFFFFF)
                    if key:
                        out[items[k][1]] = key
                        break
        return out

    def _skill_tree(self):
        """[(row title, [(node name, parent PS key, [child PS keys])])] as laid out in the skill menu."""
        base = self.category('Interface/Menu/MenuTreeBase')
        nodes = self.category('Interface/Menu/MenuTreeNode/Skills')
        child = self.category('Interface/Menu/MenuTreeNode/SkillChild')
        pss = self.category('Inventory/Skill/Skills')
        unlocks = {n for _, n in self.category('Inventory/Items') if n.startswith('PS_') and n.endswith('_UNLOCK')}

        def ps_of(s):
            if s in PSS_TO_PS:
                return PSS_TO_PS[s]
            c = s[4:]
            c2 = re.sub(r'_C(\d)$', r'_Child\1', c.replace('RhythmMovent', 'RhythmMovement')
                        .replace('PoisonBarrel_', 'PoisonBarrels_'))
            for x in (c, c2, re.sub(r'_Parent$', '', c2)):
                if 'PS_%s_UNLOCK' % x in unlocks:
                    return 'PS_%s_UNLOCK' % x

        def index(recs):                      # first record of a name (later ones belong to other lists)
            out = {}
            for k, (_, n) in enumerate(recs):
                out.setdefault(n, k)
            return out
        bi, ni, ci = index(base), index(nodes), index(child)
        tree = []
        for row, title in SKILL_ROWS:
            out = []
            for nn in self.refs(base, bi[row], LIST_NODES, nodes):
                k = ni[nn]
                parent = self.refs(nodes, k, LIST_PSS, pss)[:1]
                kids = [ps_of(r) for cn in self.refs(nodes, k, LIST_CHILD, child)
                        for r in self.refs(child, ci[cn], LIST_PSS, pss)[:1]]
                out.append((nn, ps_of(parent[0]) if parent else None, [x for x in kids if x]))
            tree.append((title, out))
        return tree

    def _level_cost(self):
        """XP needed for each level: PlayerPowerLevelCost (Combat/Stat/Constant/FloatArray), index = level - 1."""
        for p, n in self.category('Combat/Stat/Constant/FloatArray'):
            if n == 'PlayerPowerLevelCost':
                out, q = [], p + 12
                while True:
                    v = struct.unpack_from('<f', self.db, q)[0]
                    if out and not v > out[-1]:
                        return out
                    out.append(v)
                    q += 4
        return []

    # ---- texts -----------------------------------------------------------------------------------------
    def record(self, rid):
        return self.records.get(rid)

    def say(self, key):
        """Text for a text key name, without the '({1!ls})' owner placeholder."""
        s = self.text.get(name_hash(key))
        return s.replace(' ({1!ls})', '').strip() if s else None

    def first_with_prefix(self, prefix):
        p = prefix.lower()
        for n in self.text_names:
            if n.lower().startswith(p):
                return self.text[name_hash(n)]

    def skill(self, rec):
        m = re.match(r'PS_(.+?)_(UNLOCK|SKILL)$', rec)
        if not m:
            return None
        base = m.group(1)
        key = self.skill_names.get('PS_%s_UNLOCK' % base)
        if key and self.say(key):
            return self.say(key)
        c = re.match(r'(.+)_Child(\d)(?:_.*)?$', base)
        if c:
            return self.first_with_prefix('PSN_Krak_%s_C%s_' % (c.group(1), c.group(2)))
        return self.say('PSN_Krak_' + base) or self.first_with_prefix('PSN_Krak_%s_' % base)

    def skill_description(self, rec):
        key = self.skill_names.get(rec)
        text = self.say(key.replace('PSN_', 'PSD_', 1)) if key else None
        if not text:
            m = re.match(r'PS_(.+?)_(Child(\d)|Parent)?_?.*UNLOCK$', rec)
            if m:
                base = rec[3:].split('_Child')[0].split('_Parent')[0]
                text = self.first_with_prefix('PSD_Krak_%s_%s' % (base, 'C' + m.group(3) if m.group(3) else 'Parent'))
        return clean(text) if text else None

    def item_name(self, template, nemesis, affixes, art=''):
        if template in STORY_ITEMS:                 # the story things have no item text
            key = STORY_ITEMS[template]
            return self.say(key) if key.startswith('App_') else key
        core = template.split('_', 1)[1] if '_' in template else template
        name = self.say('UI_%s_N' % core)
        # Nazgul set items are named by their set property, Nemesis gear by its NG_ record; the texts of hammers and
        # longbows drop Ham/Snipe, two Nazgul masks are spelled out in full there
        for a in affixes:
            if not name and '_SetProp_' in a:
                for k in (a, re.sub(r'^3Bow(Ham|Snipe)_', '3Bow_', a)):
                    k = k.replace('_Hmrhand', '_Hammerhand').replace('_ArPharzn', '_ArPharazon')
                    name = name or self.say('UI_%s_N' % k)
        if not name and nemesis:
            core = re.sub(r'_\d[A-Z]$', '', nemesis[3:])
            name = self.say('UI_Nem_Name_' + core) or self.say('UI_Nem_Name_' + re.sub(r'^3Bow(Ham|Snipe)_', '3Bow_', core))
        if not name and art:                       # common gear: by the culture of its model
            slot = re.search(r'_(\d[A-Z][a-z]+)_', '_' + core + '_')
            kind = ('3BowHam' if template.startswith('PrimHam') else '3BowSnipe' if template.startswith('PrimSnipe')
                    else slot.group(1) if slot else '')
            culture = re.search(r'(BlackNumenorean|BlackNum|Numenorean|Gondorian|Dwarven|Elven|Haradrim|Rhovanion|Rohan)',
                                art)
            if kind and culture:
                c = 'BlackNumenorean' if culture.group(1) == 'BlackNum' else culture.group(1)
                name = self.say('UI_%s_%s_2Common_N' % (kind, c)) or self.say('UI_%s_%s_N' % (kind, c))
            name = name or (self.say('UI_%s_01_N' % kind.replace('Ham', '').replace('Snipe', '')) if kind else None)
        return name

    def affix(self, rec):
        if '_Base_Prop_' in rec:
            return None
        if '_SetProp_' in rec:
            return self.say('UI_%s_D' % rec)
        slot, _, rest = rec.partition('_')
        return self.say('UI_%s_N_%s' % (slot, rest))

    def role_title(self, role):
        """Orc title of a Role_ record: its text key is the 10th field of Faction/Roles/Definitions."""
        if self._titles is None:
            self._titles = {}
            recs = self.category('Faction/Roles/Definitions')
            for k, (_, n) in enumerate(recs):
                f = self.fields(recs, k)
                if len(f) > 9 and self._is_name(f[9]):
                    self._titles.setdefault(n, self._pstr(f[9]))
        key = self._titles.get(role)
        return (self.say(key) if key else None) or self.say('Orc_Title_' + role[5:])

    def item_description(self, template):
        core = template.split('_', 1)[1] if '_' in template else template
        return self.say('UI_%s_D' % core)

    def set_name(self, tribe):
        return self.say('UI_LegendarySetName_' + tribe)

    def set_bonuses(self, tribe):
        """[(items needed, text)] of a legendary set."""
        key = SET_BONUS_KEY.get(tribe, tribe)
        out = []
        for k, need in ((1, 2), (2, 4)):
            text = self.say('UI_LegendarySet_%s_Affix%d_D' % (key, k))
            if text:
                out.append((need, clean(text)))
        return out

    def gem(self, rec):
        return self.say('UI_' + rec) or rec
