"""Decrypted save layout.

Top header: 'SAVE', 2, 0, plain length - 0x14 (twice, at 0x0C and 0x10). Then three sections; each starts
with a u32 length (8 bytes before its inner 'SAVE' header), and the first section also keeps the length of its
blocks at SAVE + 0x43 (= section length - 0x47). Blocks: tag, version, size, 0, size - 4, content.

Values are typed tokens; the game checks the type byte when reading:
00 id (4), 04 int32, 0a float, 07/08 u32, 05/09/0b/0d 8 bytes, 0c/02/01 byte, 03 int16, 06 4 bytes,
0e vec3 (12), 0f u8 length + string, 10 u32 length + nested data.
"""
import os
import re
import struct

from . import crypto
from .gamedata import RARITY, RARITY_LINE, SLOT, clean, name_hash

SIZES = {0x00: 4, 0x04: 4, 0x0A: 4, 0x07: 4, 0x08: 4, 0x05: 8, 0x09: 8, 0x0B: 8, 0x0D: 8,
         0x0C: 1, 0x02: 1, 0x01: 1, 0x03: 2, 0x06: 4, 0x0E: 12}


class Token:
    __slots__ = ('pos', 'end', 'type', 'value')

    def __init__(self, pos, end, typ, value):
        self.pos, self.end, self.type, self.value = pos, end, typ, value

    def __repr__(self):
        return '%02x:%r' % (self.type, self.value)


def tokens(buf, pos, end):
    """Flat token list; a 10 (nested data) token is followed by the tokens of its contents."""
    out = []
    while pos < end:
        t = buf[pos]
        if t == 0x0F:
            n = buf[pos + 1]
            out.append(Token(pos, pos + 2 + n, t, buf[pos + 2:pos + 2 + n].decode('latin1')))
            pos += 2 + n
        elif t == 0x10:
            out.append(Token(pos, pos + 5, t, struct.unpack_from('<I', buf, pos + 1)[0]))
            pos += 5
        elif t in SIZES:
            n = SIZES[t]
            raw = buf[pos + 1:pos + 1 + n]
            if t == 0x04:
                v = struct.unpack('<i', raw)[0]
            elif t == 0x0A:
                v = struct.unpack('<f', raw)[0]
            elif t in (0x00, 0x07, 0x08, 0x06):
                v = struct.unpack('<I', raw)[0]
            elif n == 1:
                v = raw[0]
            elif t == 0x03:
                v = struct.unpack('<h', raw)[0]
            else:
                v = raw
            out.append(Token(pos, pos + 1 + n, t, v))
            pos += 1 + n
        else:
            raise ValueError('неизвестный тип значения %02x по смещению 0x%x' % (t, pos))
    return out


KNOWN_BUILD = 8874                     # the game build the formats were worked out on (1.0.8874.0)
REQUIRED = ('PPDC', 'IVMG', 'IVPD')


class SaveError(Exception):
    """A problem with a save that the user can understand and fix; the message is shown as is."""


def load(path):
    """(decrypted bytes, user id) of a .sav file, or of an already decrypted file."""
    name = os.path.basename(path)
    try:
        data = open(path, 'rb').read()
    except OSError as e:
        raise SaveError('%s: не удалось открыть файл (%s)' % (name, e.strerror or e))
    user = None
    if data[:4] in (b'SOM3', b'SOM2'):
        named = crypto.user_id_from_name(path)
        for user in dict.fromkeys((named, 0)):        # the id from the name, then 0 (non-Steam versions)
            try:
                data = crypto.decrypt(data, user)
                break
            except ValueError:
                continue
        else:
            raise SaveError(
                '%s: не удалось расшифровать.\n'
                'Ключ шифрования зависит от первых 8 знаков имени файла (<8 знаков>_ShadowOfWar.sav). Если файл '
                'переименовывали — верните ему исходное имя, с которым он был скачан или записан игрой. '
                'Иначе файл повреждён (например, скачан не полностью).' % name)
    elif data[:4] != b'SAVE':
        raise SaveError('%s: это не сохранение Shadow of War (файл начинается не с SOM3/SOM2).' % name)
    validate(data, name)
    return data, user


def build_number(buf):
    return struct.unpack_from('<I', buf, 0x14)[0]


def validate(buf, name='сохранение'):
    """Raises SaveError if the decrypted save has a layout the tool does not know."""
    if buf[:4] != b'SAVE' or len(buf) < 0x100:
        raise SaveError('%s: это не сохранение Shadow of War.' % name)
    unknown = '%s: незнакомое устройство сохранения (%%s). Программа проверена на версии игры 1.0.%d; ' \
              'возможно, сохранение от другой версии или повреждено.' % (name, KNOWN_BUILD)
    try:
        secs = sections(buf)
        if not secs:
            raise ValueError('нет разделов')
        for k in range(len(secs)):
            blocks(buf, k)
        tags = {t for t, *_ in blocks(buf, 0)}
        missing = [t for t in REQUIRED if t not in tags]
        if missing:
            raise ValueError('нет блоков %s' % ', '.join(missing))
        for t in REQUIRED:
            block_tokens(buf, t)
    except (ValueError, struct.error, IndexError, KeyError) as e:
        raise SaveError(unknown % e)
    if talion(buf)[0] is None:
        raise SaveError('%s: в сохранении нет данных Талиона.' % name)
    try:
        Inventory(buf)
    except (ValueError, struct.error, IndexError, StopIteration) as e:
        raise SaveError(unknown % ('инвентарь: %s' % (e or type(e).__name__)))


def warnings(buf, name='сохранение'):
    """Things worth telling the user that do not stop the tool."""
    out = []
    b = build_number(buf)
    if b != KNOWN_BUILD:
        out.append('%s: сохранение от версии игры 1.0.%d, программа проверена на 1.0.%d — '
                   'данные могут читаться неточно.' % (name, b, KNOWN_BUILD))
    return out


def write(path, plain, user_id):
    with open(path, 'wb') as f:
        f.write(crypto.encrypt(plain, user_id))


def sections(buf):
    """[(offset of the inner 'SAVE', length)] of the three sections."""
    out, i = [], buf.find(b'SAVE', 4)
    while i >= 0:
        length = struct.unpack_from('<I', buf, i - 8)[0]
        if length < 0x47 or i + length > len(buf):
            raise ValueError('раздел %d: неверная длина %d' % (len(out), length))
        out.append((i, length))
        i = buf.find(b'SAVE', i + length)
    return out


def blocks(buf, section=0):
    """[(tag, version, offset, size)] of a section's blocks."""
    s, _ = sections(buf)[section]
    p = s + 0x47
    end = p + struct.unpack_from('<I', buf, s + 0x43)[0]
    out = []
    while p < end:
        ver, size = struct.unpack_from('<II', buf, p + 4)
        out.append((buf[p:p + 4].decode('latin1'), ver, p, size))
        p += size + 16
    if p != end:
        raise ValueError('раздел %d: блоки кончаются на 0x%x, ожидалось 0x%x' % (section, p, end))
    return out


def block(buf, tag, section=0):
    for t, _, p, size in blocks(buf, section):
        if t == tag:
            return p, size
    raise KeyError(tag)


def replace_block(buf, tag, content):
    """New save bytes with the block's content replaced and all lengths fixed (first section only)."""
    p, size = block(buf, tag)
    ver = struct.unpack_from('<I', buf, p + 4)[0]
    new = len(content) + 4
    out = bytearray(buf[:p + 4] + struct.pack('<IIII', ver, new, 0, new - 4) + content + buf[p + 16 + size:])
    return fix_lengths(out, len(out) - len(buf))


def fix_lengths(out, delta):
    s, length = sections(bytes(out))[0]
    length += delta
    struct.pack_into('<I', out, s - 8, length)
    struct.pack_into('<I', out, s + 0x43, length - 0x47)
    struct.pack_into('<I', out, 12, len(out) - 0x14)
    struct.pack_into('<I', out, 16, len(out) - 0x14)
    out = bytes(out)
    for k in range(len(sections(out))):
        blocks(out, k)
    return out


def block_tokens(buf, tag):
    p, size = block(buf, tag)
    return tokens(buf, p + 20, p + 16 + size)


# ---- what Talion has -----------------------------------------------------------------------------------
TALION = name_hash('SinglePlayer')


def talion(buf):
    """(level, xp in level) from PPDC: 04 owners, then 00 SinglePlayer 04 level-1 04 xp ..."""
    t = block_tokens(buf, 'PPDC')
    for i, tok in enumerate(t):
        if tok.type == 0 and tok.value == TALION:
            return t[i + 1].value + 1, t[i + 2].value
    return None, None


def unlocks(buf):
    """IVPD of Talion: {record id: value}. Layout: 04 owners, 00 owner, 04 count, (00 id, 04 value)*count, ..."""
    t = block_tokens(buf, 'IVPD')
    out = {}
    i = 1
    while i < len(t):
        owner, count = t[i].value, t[i + 1].value
        pairs = t[i + 2:i + 2 + 2 * count]
        if owner == TALION:
            out = {pairs[k].value: pairs[k + 1].value for k in range(0, len(pairs), 2)}
        i += 2 + 2 * count
    return out


class Inventory:
    """Talion's IVMG data (nested data of the SinglePlayer owner).

    Start: 05 <two u32>, 00 skin, 04 next item number, 04 slots in the stock table, then per slot
    0c 00 (empty) or 0c 01 00 record 04 count 04 ? 04 n (04 item number)*n. Then 04 slots of the item table
    and per slot 0c 00 or 0c 01 04 number 04 level 02 ? 00 template ... (variable). Near the end: the
    equipped list (0c 01 04 number | 0c 00) and the gem sockets 0c 01 04 8 (00 Socket_X (0c 00 | 0c 01 00 Socket_X
    00 gem))*8."""

    def __init__(self, buf):
        self.buf = buf
        t = block_tokens(buf, 'IVMG')
        self.blob_tok = next(i for i, x in enumerate(t) if x.type == 0x10)
        b = t[self.blob_tok]
        self.blob_start, self.blob_end = b.end, b.end + b.value
        self.t = t = tokens(buf, self.blob_start, self.blob_end)
        self.skin, self.next_id, cap = t[1].value, t[2].value, t[3].value
        self.stock = []                    # (record id, count, field, [item numbers], start, end)
        i = 4
        for _ in range(cap):
            if t[i].value == 0:
                i += 1
                continue
            rid, count, field, n = t[i + 1].value, t[i + 2].value, t[i + 3].value, t[i + 4].value
            ids = [x.value for x in t[i + 5:i + 5 + n]]
            self.stock.append((rid, count, field, ids, t[i].pos, t[i + 5 + n - 1].end if n else t[i + 4].end))
            i += 5 + n
        self.stock_end_tok = i
        self.items = self._items(i)
        self.equipped = self._equipped()
        self.sockets = self._sockets()

    def _items(self, i):
        t = self.t
        starts = [k for k in range(i + 1, len(t) - 4)
                  if t[k].type == 0x0C and t[k].value == 1 and t[k + 1].type == 4 and t[k + 2].type == 4
                  and t[k + 3].type == 2 and t[k + 4].type == 0 and 0 < t[k + 1].value < 1000000
                  and 0 < t[k + 2].value < 100]
        items = []
        for n, s in enumerate(starts):
            end = starts[n + 1] if n + 1 < len(starts) else len(t)
            items.append(dict(uid=t[s + 1].value, level=t[s + 2].value, template=t[s + 4].value,
                              ids=[x.value for x in t[s + 5:end] if x.type == 0 and x.value],
                              owner_name=self._owner_name(t[s + 5:end])))
        return items

    @staticmethod
    def _owner_name(toks):
        """Previous owner: 00 NG_record 00 ? 00 Role_X 04 <first name text key>."""
        for k in range(len(toks) - 1):
            if toks[k].type == 0 and toks[k + 1].type == 4 and toks[k + 1].value > 0x10000 \
                    and k >= 2 and toks[k - 2].type == 0:
                return toks[k].value, toks[k + 1].value & 0xFFFFFFFF
        return None

    def _equipped(self):
        """The equipped list: 04 <slots> then that many slot entries '0c 01 04 <number>' / '0c 00' (the longest such
        list; a run of entries not preceded by its own count is not it — the last item record may end in 0c 01)."""
        blob = self.buf[self.blob_start:self.blob_end]
        best = []
        for m in re.finditer(rb'(?=\x04(.{4})((?:\x0c\x01\x04.{4}|\x0c\x00){10,}))', blob, re.S):    # overlapping
            n = struct.unpack('<i', m.group(1))[0]
            run, p = [], m.start(2)
            while p < m.end(2) and len(run) < n:
                if blob[p + 1] == 1:
                    run.append(struct.unpack_from('<I', blob, p + 3)[0])
                    p += 7
                else:
                    run.append(None)
                    p += 2
            if len(run) == n and n > len(best):
                best = run
        return best

    def _socket_start(self):
        t = self.t
        first = name_hash('Socket_4Armor')
        for k in range(len(t) - 1, 2, -1):
            if t[k].type == 0 and t[k].value == first and t[k - 1].type == 4 and t[k - 1].value == 8 \
                    and t[k - 2].type == 0x0C:
                return k
        return None

    def _sockets(self):
        """[(socket record id, gem record id or None)]"""
        k = self._socket_start()
        out = []
        if k is None:
            return out
        t = self.t
        for _ in range(8):
            if t[k + 1].value:
                out.append((t[k].value, t[k + 3].value))
                k += 4
            else:
                out.append((t[k].value, None))
                k += 2
        return out

    def stock_count(self, rid):
        for r, count, *_ in self.stock:
            if r == rid:
                return count
        return 0


def describe_item(it, gd):
    """Display fields of an item record."""
    rec = gd.record
    template = rec(it['template']) or '#%08x' % it['template']
    names = [rec(v) for v in it['ids']]
    names = [n for n in names if n]
    nemesis = next((n for n in names if n.startswith('NG_')), None)
    role = next((n for n in names if n.startswith('Role_')), None)
    affixes = [n for n in names if re.match(r'\d[A-Za-z]+_', n)]
    parts = template.split('_')
    slot = next((SLOT[p] for p in parts if p in SLOT), '')
    rarity = next((RARITY[p] for p in parts if p in RARITY), '')
    owner = None
    if role and it['owner_name']:
        title = gd.role_title(role)
        first = gd.text.get(it['owner_name'][1])
        owner = ' '.join(x for x in (first, title) if x) or None
    effects = []                    # (kind, text): kind 'legendary' (purple in the game) or 'normal'
    for a in affixes:
        text = gd.affix(a)
        if text:
            effects.append(('legendary' if '_SetProp_' in a else 'normal', clean(text)))
    effects.sort(key=lambda e: e[0] != 'legendary')
    tribe = parts[3] if rarity == 'легендарный' and len(parts) > 3 else ''
    set_name = gd.set_name(tribe) if tribe else None
    line = ' '.join(x for x in (RARITY_LINE.get(rarity, ''), set_name) if x)
    return dict(uid=it['uid'], level=it['level'], template=template,
                name=gd.item_name(template, nemesis, affixes, names[0] if names else '') or template, slot=slot, rarity=rarity,
                rarity_line=line, description=gd.item_description(template), owner=owner, effects=effects,
                set=tribe if set_name else '')


def report(buf, gd):
    """Everything the GUI shows, as plain data."""
    level, xp = talion(buf)
    inv = Inventory(buf)
    learned = unlocks(buf)
    for rid, count, *_ in inv.stock:          # some skills are marked only in the stock table
        if count > 0 and (gd.record(rid) or '').startswith('PS_'):
            learned.setdefault(rid, count)
    rows = []
    for title, nodes in gd.skill_tree:
        out_nodes, have, total = [], 0, 0
        for node, parent, kids in nodes:
            prestige = 'Prestige' in node
            # shown only once opened (the Dark Talion meter, raising the dead)
            hidden = node in ('SkillRow7_Node_Parent_Raise', 'SkillRow6_Node_Parent_CBMeter_DarkTalion') and \
                not any(learned.get(name_hash(k), 0) for k in [parent] + kids if k)
            if hidden:
                continue
            entries = []
            for k, key in enumerate([parent] + kids):
                if not key:
                    continue
                v = learned.get(name_hash(key), 0)
                on = v > 0
                entries.append(dict(key=key, name=(gd.skill(key) or key).replace('{1!.0f}', str(v or 1)),
                                    learned=on, rank=v, child=k > 0, text=gd.skill_description(key)))
                if not prestige:
                    total += 1
                    have += on
            out_nodes.append(dict(node=node, prestige=prestige, skills=entries))
        rows.append(dict(title=title, learned=have, total=total, nodes=out_nodes))
    by_uid = {it['uid']: it for it in inv.items}
    equipped = []
    for uid in inv.equipped:
        if uid in by_uid:
            d = describe_item(by_uid[uid], gd)
            if d['slot']:
                equipped.append(uid)
    items = [describe_item(it, gd) for it in inv.items]
    worn_sets = {}
    for d in items:
        if d['uid'] in equipped and d['set']:
            worn_sets[d['set']] = worn_sets.get(d['set'], 0) + 1
    for d in items:                           # set bonuses with the equipped count, as in the game
        if d['set']:
            for need, text in gd.set_bonuses(d['set']):
                d['effects'].append(('set', 'Комплект: снаряжено %d/%d' % (min(worn_sets.get(d['set'], 0), need), need)
                                     + ' — ' + text))
    gems = []
    for rid, count, *_ in inv.stock:
        n = gd.record(rid) or ''
        if n.startswith('Runegem_'):
            gems.append(dict(key=n, name=gd.gem(n), count=count))
    sockets = [dict(socket=gd.record(s) or '', gem=gd.gem(gd.record(g)) if g else None) for s, g in inv.sockets]
    cost = gd.level_cost
    return dict(level=level, xp=xp, xp_next=int(cost[level - 1]) if level and level <= len(cost) else None,
                mirians=inv.stock_count(name_hash('PC_Mirian')),
                skill_points=inv.stock_count(name_hash('SkillPoint')), rows=rows, items=items, equipped=equipped,
                gems=gems, sockets=sockets)
