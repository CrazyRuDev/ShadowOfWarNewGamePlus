"""Shows what a Shadow of War save holds: Talion's level, learned skills and gear, with names from the game texts.

    python3 sowinfo.py <save.sav | decrypted.bin> <game.gamedb> <string.strdb>

game.gamedb and string.strdb are unpacked from the game archives (extract_arch.ps1 + ltar.py),
the Russian texts are database\\string\\ruru\\string.strdb from hotchunk.arch06.
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import sowsave  # noqa: E402
import strdb  # noqa: E402

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


RARITY = {'2Standard': 'обычный', '3Rare': 'редкий', '4Epic': 'эпический', '5Lgnd': 'легендарный'}
SLOT = {'1Sword': 'меч', '2Dagger': 'кинжал', '3Bow': 'лук', '4Armor': 'доспехи', '5Cape': 'плащ', '6Ring': 'руна'}


class Names:
    def __init__(self, gamedb_path, strdb_path):
        db = open(gamedb_path, 'rb').read()
        pool_size = struct.unpack_from('<I', db, 8)[0]
        pool = db[0x47:0x47 + pool_size]
        self.records = {}
        for m in re.finditer(rb'[\x20-\x7e]+', pool):
            s = m.group().decode('latin1')
            self.records.setdefault(name_hash(s), s)
        self.text = strdb.load(strdb_path)
        self.text_names = sorted(self.records[k] for k in self.text if k in self.records)
        self.skill_names = self._skill_names(db, pool)

    @staticmethod
    def _category(db, pool, path):
        """Records of one database category as [(offset, name)], in file order.

        Category header: name, type, path ('\\...\\gdb.category06'), 0, record count, hash - each a
        string-pool offset or u32. A record starts with its name, a type word and a 0x08xxxxxx word."""
        po = pool.find(b'\x00' + path.encode() + b'\x00') + 1
        data_start = 0x47 + len(pool)
        head = db.find(struct.pack('<I', po) + b'\x00\x00\x00\x00', data_start) - 8
        count = struct.unpack_from('<I', db, head + 16)[0]
        recs, p = [], head + 24
        while len(recs) < count and p < len(db) - 12:
            name, _, flags = struct.unpack_from('<III', db, p)
            if flags >> 24 == 8 and not flags & 0xFF0000 and 0 < name < len(pool) and pool[name - 1] == 0 \
                    and 0x20 < pool[name] < 0x7F:
                recs.append((p, pool[name:pool.index(b'\x00', name)].decode('latin1')))
            p += 4
        return recs

    @staticmethod
    def _skill_names(db, pool):
        """PS_<skill>_UNLOCK (Inventory/Items) -> PSN_ text key of its Inventory/UIItemData record.

        A record refers to another record as (category << 20) | index; strings are string-pool offsets."""
        items = Names._category(db, pool, '\\Inventory\\Items\\gdb.category06')
        ui = Names._category(db, pool, '\\Inventory\\UIItemData\\gdb.category06')

        def fields(recs, k):
            p, end = recs[k][0], recs[k + 1][0] if k + 1 < len(recs) else recs[k][0] + 0x400
            return struct.unpack_from('<%dI' % ((end - p) // 4), db, p)

        def psn(k):
            for v in fields(ui, k)[3:]:
                if 0 < v < len(pool) and pool[v - 1] == 0 and pool.startswith(b'PSN_', v):
                    return pool[v:pool.index(b'\x00', v)].decode('latin1')

        unlocks = [k for k, (_, n) in enumerate(items) if n.startswith('PS_') and n.endswith('_UNLOCK')]
        votes = {}
        for k in unlocks:
            for v in fields(items, k)[3:]:
                if v != 0xFFFFFFFF and v >> 20 and (v & 0xFFFFF) < len(ui) and ui[v & 0xFFFFF][1].startswith('PSUID_'):
                    votes[v >> 20] = votes.get(v >> 20, 0) + 1
        ui_cat = max(votes, key=votes.get)
        out = {}
        for k in unlocks:
            for v in fields(items, k)[3:]:
                if v >> 20 == ui_cat and (v & 0xFFFFF) < len(ui):
                    key = psn(v & 0xFFFFF)
                    if key:
                        out[items[k][1]] = key
                        break
        return out

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

    def item_name(self, template, nemesis, affixes):
        core = template.split('_', 1)[1] if '_' in template else template
        name = self.say('UI_%s_N' % core)
        # Nazgul set items are named by their set property, Nemesis gear by its NG_ record
        for a in affixes:
            if not name and '_SetProp_' in a:
                name = self.say('UI_%s_N' % a)
        if not name and nemesis:
            name = self.say('UI_Nem_Name_' + re.sub(r'_\d[A-Z]$', '', nemesis[3:]))
        return name

    def affix(self, rec):
        if '_SetProp_' in rec or '_Base_Prop_' in rec:
            return self.say('UI_%s_D' % rec) if '_SetProp_' in rec else None
        slot, _, rest = rec.partition('_')
        return self.say('UI_%s_N_%s' % (slot, rest))

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


def tokens(buf, pos, end):
    """Save values: 00 id, 04 int, 0a float, 05 8 bytes, 0c/02/0f byte."""
    while pos < end:
        t = buf[pos]
        if t in (0x00, 0x04, 0x0A):
            yield pos, t, struct.unpack_from('<I', buf, pos + 1)[0]
            pos += 5
        elif t == 0x05:
            yield pos, t, buf[pos + 1:pos + 9]
            pos += 9
        elif t in (0x0C, 0x02, 0x0F):
            yield pos, t, buf[pos + 1]
            pos += 2
        else:
            return


def block(buf, tag):
    i = buf.find(tag)
    size = struct.unpack_from('<I', buf, i + 8)[0]
    return buf[i:i + 16 + size]


def read_items(ivmg, names):
    starts = [m.start() for m in re.finditer(rb'\x04(.{4})\x04(.{4})\x02\x00\x00(.{4})', ivmg, re.S)
              if struct.unpack_from('<I', ivmg, m.start() + 1)[0] < 100000
              and 0 < struct.unpack_from('<I', ivmg, m.start() + 6)[0] < 100]
    items = []
    for n, s in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(ivmg)
        vals = list(tokens(ivmg, s, end))
        uid, level, template = vals[0][2], vals[1][2], names.record(vals[3][2]) or '#%08x' % vals[3][2]
        ids = [names.record(v) for _, t, v in vals if t == 0 and v]
        ids = [i for i in ids if i]
        nemesis = next((i for i in ids if i.startswith('NG_')), None)
        role = next((i for i in ids if i.startswith('Role_')), None)
        affixes = [i for i in ids[2:] if re.match(r'\d[A-Za-z]+_', i)]
        items.append(dict(uid=uid, level=level, template=template, nemesis=nemesis, role=role, affixes=affixes))
    return items


def equipped(ivmg):
    """Longest run of slot entries '0c 01 04 <uid>' / '0c 00' - the equipment slots."""
    best = []
    for m in re.finditer(rb'(?:\x0c\x01\x04.{4}|\x0c\x00){10,}', ivmg, re.S):
        run, p = [], m.start()
        while p < m.end():
            if ivmg[p + 1] == 1:
                run.append(struct.unpack_from('<I', ivmg, p + 3)[0])
                p += 7
            else:
                run.append(None)
                p += 2
        if len(run) > len(best):
            best = run
    return best


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    save_path, gamedb_path, strdb_path = sys.argv[1:]
    data = open(save_path, 'rb').read()
    if data[:4] in (b'SOM3', b'SOM2'):
        data = sowsave.decrypt(data, sowsave.user_id_from_name(save_path))
    names = Names(gamedb_path, strdb_path)
    out = []

    talion = struct.pack('<I', name_hash('SinglePlayer'))
    i = block(data, b'PPDC').find(b'\x00' + talion + b'\x04')
    if i >= 0:
        ppdc = block(data, b'PPDC')
        level, xp = struct.unpack_from('<I', ppdc, i + 6)[0], struct.unpack_from('<I', ppdc, i + 11)[0]
        out.append('Уровень: %d, опыт в уровне: %d' % (level + 1, xp))
    m = re.search(rb'\x0c\x01\x00' + struct.pack('<I', name_hash('PC_Mirian')) + rb'\x04(.{4})', block(data, b'IVMG'), re.S)
    if m:
        out.append('Мирианы: %d' % struct.unpack('<I', m.group(1))[0])

    ivpd = block(data, b'IVPD')
    learned = []
    for m in re.finditer(rb'\x00(.{4})\x04(.{4})', ivpd, re.S):
        rid, value = struct.unpack('<Ii', m.group(1) + m.group(2))
        rec = names.record(rid)
        if rec and rec.startswith('PS_') and rec.endswith('_UNLOCK') and value > 0:
            learned.append((names.skill(rec) or rec, value))
    out.append('')
    out.append('Изученные навыки (%d):' % len(learned))
    for name, value in learned:
        out.append('  %s%s' % (name.replace('{1!.0f}', str(value)), '' if value == 1 or '{1' in name else ' (ранг %d)' % value))

    ivmg = block(data, b'IVMG')
    items = read_items(ivmg, names)
    by_uid = {it['uid']: it for it in items}
    slots = equipped(ivmg)

    def describe(it):
        parts = it['template'].split('_')
        slot = next((SLOT[p] for p in parts if p in SLOT), '')
        rarity = next((RARITY[p] for p in parts if p in RARITY), '')
        name = names.item_name(it['template'], it['nemesis'], it['affixes']) or slot or it['template']
        line = '%s, ур. %d' % (name, it['level'])
        if rarity:
            line += ' (%s, %s)' % (slot, rarity)
        if it['role']:
            title = names.say('Orc_Title_' + it['role'][5:])
            if title:
                line += ', прежний владелец: …%s' % title
        return line

    out.append('')
    out.append('Надето:')
    for uid in slots:
        if uid in by_uid and any(p in SLOT for p in by_uid[uid]['template'].split('_')):
            out.append('  ' + describe(by_uid[uid]))
    out.append('')
    out.append('Снаряжение (%d):' % len(items))
    for it in items:
        out.append('  №%-5d %s' % (it['uid'], describe(it)))
        for a in it['affixes']:
            text = names.affix(a)
            if text:
                out.append('           • ' + re.sub(r'\{\d![^}]*\}', 'X', text))
    print('\n'.join(out))


if __name__ == '__main__':
    main()
