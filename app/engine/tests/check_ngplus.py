"""Checks of the save tool on real saves, without the game.

    python tests/check_ngplus.py [--data DIR] [--saves DIR] [--source SAVE]

--saves: folder with .sav files (by default '../../game files' of the project). The source (finished game) is the
save with the highest level unless --source is given; every other save is used as a base for a New Game Plus.
"""
import argparse
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sowtool import army, crypto, ngplus, orcs, save as sv    # noqa: E402
from sowtool.gamedata import GameData, name_hash       # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
CHANGED = ('IVMG', 'IVPD', 'PPDC')
PATHS = {}                     # save name -> path
failures = []


def check(cond, what):
    if not cond:
        failures.append(what)
        print('   ОШИБКА: ' + what)
    return cond


def stock_names(inv, gd):
    return {gd.record(rid) or '#%08x' % rid: count for rid, count, *_ in inv.stock}


def learned(buf, inv):
    out = dict(sv.unlocks(buf))
    for rid, count, *_ in inv.stock:
        if count > 0:
            out.setdefault(rid, count)
    return {rid for rid, v in out.items() if v > 0}


def check_file(path, raw):
    """Decrypt / encrypt round trip and the structure of every section."""
    buf, user = sv.load(path)
    check(crypto.encrypt(buf, user) == raw, '%s: шифрование после расшифровки дало другой файл' % path)
    for k in range(len(sv.sections(buf))):
        sv.blocks(buf, k)
    for tag in CHANGED:
        sv.block_tokens(buf, tag)
    return buf, user


def check_build(name, base, source, gd, towers=False):
    t0 = time.time()
    new = ngplus.build(base, source, gd, log=lambda s: print('   ' + s), towers=towers)
    changed = CHANGED + (('PDCC', 'IIUC') if towers else ())
    print('   сборка: %.1f с, %d байт' % (time.time() - t0, len(new)))

    # structure and lengths
    check(struct.unpack_from('<I', new, 12)[0] == len(new) - 0x14, 'длина в заголовке (0x0C)')
    check(struct.unpack_from('<I', new, 16)[0] == len(new) - 0x14, 'длина в заголовке (0x10)')
    for k in range(len(sv.sections(new))):
        sv.blocks(new, k)
    s0, len0 = sv.sections(new)[0]
    check(struct.unpack_from('<I', new, s0 + 0x43)[0] == len0 - 0x47, 'длина блоков первого раздела (0x1609)')
    for tag in CHANGED:
        sv.block_tokens(new, tag)
    check(crypto.decrypt(crypto.encrypt(new, 0x1234), 0x1234) == new, 'шифрование результата')

    # everything except the three changed blocks is the base, byte for byte
    bb, nb = sv.blocks(base, 0), sv.blocks(new, 0)
    check([(t, v) for t, v, _, _ in bb] == [(t, v) for t, v, _, _ in nb], 'список блоков первого раздела')
    for (t, _, p, size), (_, _, q, nsize) in zip(bb, nb):
        if t not in changed:
            check(base[p:p + 16 + size] == new[q:q + 16 + nsize], 'блок %s не совпадает с опорным' % t)
    sb, sn = sv.sections(base), sv.sections(new)
    for k in range(1, len(sb)):
        check(base[sb[k][0] - 8:sb[k][0] + sb[k][1]] == new[sn[k][0] - 8:sn[k][0] + sn[k][1]],
              'раздел %d не совпадает с опорным' % k)
    # before the first section: only the values of the game's options (GOXC) differ — see check_settings
    head = bytearray(new[:sn[0][0] - 8])
    for name, (pos, ty) in ngplus.settings(base, gd.record).items():
        n = ngplus._SETTING_SIZE[ty]
        head[pos:pos + n] = base[pos:pos + n]
    check(base[:s0 - 8][0x14:] == bytes(head)[0x14:], 'начало файла до первого раздела')

    # Talion
    check(sv.talion(new) == sv.talion(source), 'уровень и опыт: %s, ждали %s' % (sv.talion(new), sv.talion(source)))
    si, ni, bi = sv.Inventory(source), sv.Inventory(new), sv.Inventory(base)
    mir = name_hash('PC_Mirian')
    check(ni.stock_count(mir) == si.stock_count(mir), 'мирианы')
    swap = {name_hash(a): name_hash(b) for a, b in ngplus.SWAP.items()}
    items = sorted((it['uid'], it['level'], swap.get(it['template'], it['template'])) for it in si.items)
    check(sorted((it['uid'], it['level'], it['template']) for it in ni.items) == items,
          'предметы: %d, ждали %d' % (len(ni.items), len(items)))
    check(ni.equipped == si.equipped, 'надетое снаряжение')
    ivpd_points = {rid: ngplus._value(raw) for rid, raw in ngplus._ivpd_pairs(new)[1]}.get(ngplus.SKILL_POINT, 0)
    check(ivpd_points == ni.stock_count(ngplus.SKILL_POINT), 'очки навыков: в запасах %d, в IVPD %d'
          % (ni.stock_count(ngplus.SKILL_POINT), ivpd_points))
    check(ni.next_id == si.next_id, 'номер следующего предмета')
    check(all(g is None for _, g in ni.sockets) and len(ni.sockets) == 8, 'слоты самоцветов не пусты')
    sn_, nn = stock_names(si, gd), stock_names(ni, gd)
    for k, v in sn_.items():
        if k.startswith('Runegem_'):
            check(nn.get(k) == v, 'самоцветы %s: %s, ждали %s' % (k, nn.get(k), v))
    rids = [rid for rid, *_ in ni.stock]
    check(len(rids) == len(set(rids)), 'повторы в таблице запасов: %s'
          % sorted({gd.record(r) for r in rids if rids.count(r) > 1}))
    # the stock table also lists numbers with no item record (already so in the game's own saves): they must be
    # the source's ones, and every item must be listed
    def dangling(inv):
        owned = {u for _, _, _, ids, _, _ in inv.stock for u in ids}
        uids = {it['uid'] for it in inv.items}
        return owned - uids, uids - owned
    check(dangling(ni) == dangling(si), 'таблица запасов и список предметов расходятся иначе, чем в исходном')

    # skills
    src_l, new_l, base_l = learned(source, si), learned(new, ni), learned(base, bi)
    # every learned skill goes but the three BLOCKED ones, whose records stay exactly as in the base
    rules = ngplus.Rules()
    lost = [gd.record(r) for r in src_l - new_l if rules.skill(gd.record(r) or '')]
    check(not lost, 'не перенесены навыки: %s' % lost)
    for tag, read in (('IVMG', lambda b: {rid: c for rid, c, *_ in sv.Inventory(b).stock}),
                      ('IVPD', lambda b: {rid: ngplus._value(raw) for rid, raw in ngplus._ivpd_pairs(b)[1]})):
        bv, nv = read(base), read(new)
        changed = [gd.record(r) for r in set(bv) | set(nv)
                   if (gd.record(r) or '').startswith(ngplus.BLOCKED) and bv.get(r) != nv.get(r)]
        check(not changed, '%s: закрытые навыки не как в опоре: %s' % (tag, changed))
    check(sv.Inventory(new).stock_count(ngplus.SKILL_POINT) == 0, 'очки навыков перенеслись или вернулись')
    gone = [gd.record(r) for r in base_l - new_l if (gd.record(r) or '').startswith('PS_')]
    check(not gone, 'пропали навыки опорного сохранения: %s' % gone)

    # towers: the source state for the transferred regions (Minas Morgul only after act 1), the base state else
    regions, skip = ngplus.tower_regions(base), ngplus.tower_skip(base)
    others = ()
    check(bool(skip) != ngplus.act1_done(base), 'сюжетная башня Минас-Моргула и первый акт')
    if towers and skip:                      # the story tower stays as in the base, the counters follow the result
        check(stock_names(ni, gd).get(ngplus.STORY_TOWER) == stock_names(bi, gd).get(ngplus.STORY_TOWER),
              'сюжетная башня Минас-Моргула перенесена')
        regions = ngplus.TOWER_REGIONS       # Minas Morgul is not the source's state: checked by check_marks
    for tag, pattern in ngplus.tower_state(regions) + (('IVMG', ngplus.tower_re(regions, skip)),):
        rest = ngplus.tower_re(others) if tag == 'IVMG' else dict(ngplus.tower_state(others))[tag] if others else None
        if tag == 'IVMG':
            got = {k: v for k, v in nn.items() if pattern.match(k)}
            want = {k: v for k, v in sn_.items() if pattern.match(k)} if towers else \
                {k: v for k, v in stock_names(bi, gd).items() if pattern.match(k)}
            check(got == want, 'башни в таблице запасов: %s, ждали %s' % (got, want))
            if others:
                base_rest = {k: v for k, v in stock_names(bi, gd).items() if rest.match(k)}
                check({k: v for k, v in nn.items() if rest.match(k)} == base_rest, 'башни Минас-Моргула изменились')
            continue
        vals = lambda buf, pat: [(n, buf[t.pos:t.end]) for n, t in ngplus._named_values(buf, tag, gd.record, pat)]
        check(vals(new, pattern) == vals(source if towers else base, pattern), '%s: состояние башен' % tag)
        if tag == 'IIUC':                    # 3 seeing stones per region (Nurn's _02 has no name in the db)
            check(len(vals(source, pattern)) == 3 * len(regions),
                  'IIUC: найдено признаков башен %d, ждали %d' % (len(vals(source, pattern)), 3 * len(regions)))
        if others:
            check(vals(new, rest) == vals(base, rest), '%s: Минас-Моргул изменился' % tag)

    # a run over the result changes only the skill points (unspent ones are not carried), a further run nothing
    again = ngplus.build(base, new, gd, log=lambda s: None, towers=towers)
    check(sv.Inventory(again).stock_count(ngplus.SKILL_POINT) == 0, 'повторная сборка: очки навыков перенеслись')
    check(ngplus.build(base, again, gd, log=lambda s: None, towers=towers) == again,
          'повторная сборка из результата дала другой файл')
    return new


def check_settings(base, source, gd):
    """The game's options and looks (GOXC) are the finished game's in every build, the save slot numbers the base's."""
    rec = gd.record
    new = ngplus.build(base, source, gd, log=lambda *a: None)
    mine, theirs, was = ngplus.settings(new, rec), ngplus.settings(source, rec), ngplus.settings(base, rec)
    check(len(mine) > 100, 'настройки: не найден блок GOXC (%d записей)' % len(mine))
    val = lambda buf, d, k: buf[d[k][0]:d[k][0] + ngplus._SETTING_SIZE[d[k][1]]]
    bad = [k for k in mine if k in theirs and val(new, mine, k) != (val(base, was, k) if k.startswith(ngplus.SETTINGS_KEEP)
                                                                   else val(source, theirs, k))]
    check(not bad, 'настройки: не те значения %s' % bad[:5])
    print('   настроек %d, поле зрения %.2f' % (len(mine), struct.unpack('<f', val(new, mine, 'GP_FOVUserScale'))[0]))


def check_army(base, source, gd):
    """New army: only random never-spawned captains/warchiefs replaced, on the same numbers, places and levels."""
    from sowtool import army
    rec = gd.record
    plain = ngplus.build(base, source, gd, log=lambda *a: None)
    new = ngplus.build(base, source, gd, log=lambda *a: None, new_army=True)
    sv.validate(new, 'новая армия')
    a = {o['number']: o for o in orcs.read(plain, gd)}
    b = {o['number']: o for o in orcs.read(new, gd)}
    check(set(a) == set(b), 'армия: изменились номера орков')
    rep = [k for k in a if (a[k]['name'], a[k]['title']) != (b[k]['name'], b[k]['title'])]
    want = sum(ngplus.plan(base, source, gd)['army'].values())
    check(len(rep) == want, 'армия: заменено %d, план %d' % (len(rep), want))
    check(all(not a[k]['npc'] and not a[k]['story'] and a[k]['place'] in ('капитан', 'вождь') for k in rep),
          'армия: заменён сюжетный, правитель или уже бывший в мире орк')
    check(all((b[k]['place_key'], b[k]['level']) == (a[k]['place_key'], a[k]['level']) for k in rep),
          'армия: у заменённых изменились место или уровень')
    key_of = {f: k for k, (f, _) in army.REGIONS.items()}
    key_of['Faction_desert'] = 'desert'
    src = {(o['name'], o['title'], o['npc']): o for o in orcs.read(source, gd)}     # names repeat; the id is kept
    own = [k for k in rep if army._enemy(src[(b[k]['name'], b[k]['title'], b[k]['npc'])], key_of)]
    check(all(not src[(b[k]['name'], b[k]['title'], b[k]['npc'])]['met'] for k in rep if k not in own),
          'армия: на свободное место пришёл орк, встречавший Талиона')
    check(all(b[k]['region'] == src[(b[k]['name'], b[k]['title'], b[k]['npc'])]['region'] for k in own),
          'армия: враг пройденной игры стоит не в своём регионе')
    check(all((a[k]['place'] == 'вождь') <= (src[(b[k]['name'], b[k]['title'], b[k]['npc'])]['place'] == 'вождь')
              for k in own),
          'армия: капитан пройденной игры поставлен вождём')
    check(len({(b[k]['name'], b[k]['title'], b[k]['npc']) for k in rep}) == len(rep), 'армия: один орк пришёл дважды')
    other = [k for k in a if k not in rep and (a[k]['flags'], a[k]['history'], a[k]['place_key']) !=
             (b[k]['flags'], b[k]['history'], b[k]['place_key'])]
    check(not other, 'армия: изменились другие орки %s' % other[:5])
    t, ranges = orcs.table(new, rec)
    for key, (faction, prefix) in army.REGIONS.items():
        for row, cells in army._hierarchy(t, rec, faction, prefix).items():
            for c in cells:
                if t[c].value >= 0:
                    check(b[t[c].value]['place_key'] == row, 'армия: иерархия %s не сходится' % row)
    for blk in ('IVMG', 'IVPD', 'PDCC', 'IIUC', 'QSTD', 'PPDC'):
        pa, sa = sv.block(plain, blk)
        pb, sb = sv.block(new, blk)
        check(plain[pa + 16:pa + 16 + sa] == new[pb + 16:pb + 16 + sb], 'армия: изменился блок %s' % blk)
    print('   заменено орков: %d, из них врагов на своих местах: %d' % (len(rep), len(own)))


def check_twenty(base, source, gd):
    """The enemies of the finished game: every one of the plan comes where planned — a captain alive on its place,
    an ambush as a dead record without a place with its CheatDeath event; the level is the region's band top +10…15
    (traitors: any, the game resets it); bosses without weaknesses, fears and «Нет последнего шанса»."""
    from sowtool import returned
    rec = gd.record
    act1 = ngplus.act1_done(base)
    tops = returned.band_tops(base, gd)
    ready = ngplus.build(base, source, gd, log=lambda *a: None)
    for n in returned.COUNTS:
        new = ngplus.build(base, source, gd, log=lambda *a: None, twenty=True, twenty_count=n, new_army=True)
        sv.validate(new, 'враги %d' % n)
        out, placed = returned.place(ready, source, gd, act1, n, 'none', 0, log=lambda *a: None)
        sv.validate(out, 'враги %d отдельно' % n)
        plan, traitors = returned.plan(source, gd, act1, n, ready)
        check(len(placed) == len(plan) + len(traitors), 'враги %d: поставлено %d из %d' % (n, len(placed),
                                                                                         len(plan) + len(traitors)))
        fit = [o for o in orcs.read(source, gd) if o['follower'] and o['dead'] and not o['story'] and o['met']]
        check(len(traitors) == min(returned.TRAITORS, len(fit)), 'враги %d: предателей %d' % (n, len(traitors)))
        check(plan[0][1] == 'nemesis' and plan[0][0]['number'] == orcs.recommend(orcs.read(source, gd))[0]['number'],
              'враги %d: засадой в Нурн идёт не самый докучливый' % n)
        now = {o['number']: o for o in orcs.read(out, gd)}
        t = sv.block_tokens(out, 'WHDC')
        queue = {(rec(t[i + 2].value), t[i + 4].value) for i in returned._queue(t, rec)}
        for num, (src, kind, key) in placed.items():
            x = now.get(num)
            check(x is not None and x['name'] == src['name'], 'враги %d: №%d не %s' % (n, num, src['name']))
            if x is None:
                continue
            if kind in ('nemesis', 'top'):
                check('Marker_MoreLucky_to_CheatDeath' in x['markers'], 'враги %d: у топа %s нет удачи обмануть смерть'
                      % (n, x['name']))
            if kind in ('captain', 'top'):
                check(not x['dead'] and x['place'] == 'капитан', 'враги %d: капитан %s мёртв или не на месте'
                      % (n, x['name']))
            elif kind == 'nemesis' and not returned._ambush_ok(src):
                check(not x['dead'] and not x['follower'] and 'HasEverSpawned' in x['flags'] and not x['place']
                      and ('RoleTransformation_Ambush', num) in queue,
                      'враги %d: живой топ %s не ждёт засады «орк изменился»' % (n, x['name']))
            else:
                ev = 'CheatDeath_Betrayal' if kind == 'traitor' else 'CheatDeath_Ambush'
                check(x['dead'] and not x['place'] and (ev, num) in queue,
                      'враги %d: %s (%s) не ждёт своей засады' % (n, x['name'], kind))
            if kind != 'traitor':
                top = tops.get(key, 20)
                check(top + returned.LEVEL_UP[0] <= x['level'] <= min(85, top + returned.LEVEL_UP[1]),
                      'враги %d: %s ур. %d, полоса до %d' % (n, x['name'], x['level'], top))
            if kind == 'boss':
                bad = [k for k in x['trait_map'] if returned.WEAK['all'][1](k) or k == 'Picker_NoLastChance']
                check(not bad, 'враги %d: у босса %s остались %s' % (n, x['name'], bad))
    # the top one alive (here: made so) comes by «орк изменился»: alive, once spawned, no place, its event queued
    ok = returned._ambush_ok
    returned._ambush_ok = lambda o: False
    try:
        out, placed = returned.place(ready, source, gd, act1, 3, 'none', 0, log=lambda *a: None)
    finally:
        returned._ambush_ok = ok
    sv.validate(out, 'живой топ')
    t = sv.block_tokens(out, 'WHDC')
    queue = {(rec(t[i + 2].value), t[i + 4].value) for i in returned._queue(t, rec)}
    now = {o['number']: o for o in orcs.read(out, gd)}
    nem = [num for num, (_, kind, _) in placed.items() if kind == 'nemesis']
    check(len(nem) == 1 and not now[nem[0]]['dead'] and 'HasEverSpawned' in now[nem[0]]['flags']
          and not now[nem[0]]['place'] and ('RoleTransformation_Ambush', nem[0]) in queue,
          'живой топ не ждёт засады «орк изменился»')
    # a dead orc the game was already bringing back has a reward chosen (2026-10-23): it is replaced, not added to
    t, starts, end = army._table(source, rec)
    raw = source[t[starts[0]].pos:t[starts[1]].pos]
    twice = returned._reward(returned._reward(raw, 'ResReward_PinnicleScar_Burned'), returned.REWARDS['Claw'])
    tt = sv.tokens(twice, 0, len(twice))
    check([x.type for x in tt[-6:]] == [4, 0, 4, 0, 2, 0] and tt[-6].value == 1
          and rec(tt[-5].value) == returned.REWARDS['Claw'], 'награда возвращения не заменилась')
    print('   враги (15): %s' % ', '.join('%s %d' % kv for kv in returned.count(base, gd, act1, source, 15).items()))
    # the memory of new game+: the history brought over has day PAST_DAY; read back as a finished game, «only the last
    # cycle» finds nothing worthy (nothing was played), decay counts it at half, and the next transfer thins it
    out, placed = returned.place(ready, source, gd, act1, 5, 'none', 0, log=lambda *a: None)
    mine = [o for o in orcs.read(out, gd) if o['number'] in placed]
    check(all(d == orcs.PAST_DAY for o in mine for _, d in o['history']), 'память: принесённая история не с днём 0')
    scores = {}
    for mode in orcs.HISTORY_MODES:
        orcs.HISTORY = mode
        scores[mode] = {o['number']: o['score'] for o in orcs.read(out, gd) if o['number'] in placed}
    orcs.HISTORY = 'decay'
    check(all(scores['last'][n] == 0 and scores['decay'][n] == scores['all'][n] / 2 for n in placed),
          'память: режимы счёта не сходятся %s' % scores)
    again, placed2 = returned.place(ready, out, gd, act1, 5, 'none', 0, log=lambda *a: None)
    before = sum(o['kill'] for o in mine)
    after = sum(o['kill'] for o in orcs.read(again, gd) if o['number'] in placed2)
    check(after < before or before == 0, 'память: перенос не проредил прошлое (%d → %d)' % (before, after))


def check_clean_gear(base, source, gd):
    new = ngplus.build(base, source, gd, log=lambda *a: None, clean=True)
    sv.validate(new, 'чистка снаряжения')
    si, ni = sv.Inventory(source), sv.Inventory(new)
    rec = gd.record
    gone = {it['uid'] for it in si.items} - {it['uid'] for it in ni.items}
    kinds = {rec(it['template']) or '' for it in si.items if it['uid'] in gone}
    check(all(ngplus.CLUTTER.match(k) for k in kinds), 'чистка: убрано не то: %s' % sorted(kinds))
    check(not gone & set(si.equipped), 'чистка: убрано надетое')
    left = [rec(it['template']) for it in ni.items if ngplus.CLUTTER.match(rec(it['template']) or '')
            and it['uid'] not in ni.equipped]
    check(not left, 'чистка: осталось %s' % left)
    check(ni.equipped == si.equipped, 'чистка: изменилось надетое')
    ids = {x for _, _, _, xs, _, _ in ni.stock for x in xs}
    check(not ids & gone, 'чистка: в запасах остались номера убранных')
    check(sv.Inventory(new).t[ni.stock_end_tok].value == si.t[si.stock_end_tok].value - len(gone),
          'чистка: число ячеек таблицы предметов')
    print('   убрано предметов: %d, осталось %d' % (len(gone), len(ni.items)))


def check_start_level(base, source, gd):
    new = ngplus.build(base, source, gd, log=lambda *a: None, start=True)
    sv.validate(new, 'начало с уровня новой игры')
    level = ngplus.start_level(base, gd)
    check(sv.talion(new) == (level, 0), 'начало с уровня: Талион %s, ждали (%d, 0)' % (sv.talion(new), level))
    check(1 <= level <= 30, 'начало с уровня: странный уровень %d' % level)
    items = sv.Inventory(new).items
    check(all(it['level'] in (1, level) for it in items), 'начало с уровня: предметы не того уровня: %s'
          % sorted({it['level'] for it in items}))
    plain = ngplus.build(base, source, gd, log=lambda *a: None)
    check(len(new) == len(plain), 'начало с уровня: изменилась длина')
    again = ngplus.build(base, new, gd, log=lambda *a: None, start=True)
    check(ngplus.build(base, again, gd, log=lambda *a: None, start=True) == again,
          'начало с уровня: повторная сборка дала другой файл')
    print('   Талион и снаряжение: уровень %d' % level)


def check_orcs(name, buf, gd):
    army = orcs.read(buf, gd)
    nums = [o['number'] for o in army]
    check(army and len(nums) == len(set(nums)), '%s: орки без номеров или с повторами' % name)
    check(all(1 <= o['level'] <= 200 for o in army), '%s: странный уровень орка' % name)
    picked = orcs.recommend(army)
    check(len(picked) <= orcs.PICK_TOTAL, '%s: рекомендовано больше %d' % (name, orcs.PICK_TOTAL))
    check(not any(o['story'] or not o['met'] or o['score'] < orcs.MIN_SCORE for o in picked),
          '%s: рекомендован сюжетный, незнакомый или ничего не сделавший Талиону орк' % name)
    check(all(o['pick'] == 'живым' or o['pick'].startswith('вернётся: ') for o in picked),
          '%s: у рекомендованного нет способа возвращения' % name)
    check(all(orcs.details(o) for o in army), '%s: пустая карточка орка' % name)
    print('   %s: орков %d, рекомендовано %d' % (name, len(army), len(picked)))


def check_towers_only(base, source, gd):
    """add_towers: towers as in the source (but Minas Morgul), everything else as in the base."""
    new = ngplus.add_towers(base, source, gd, log=lambda s: print('   ' + s))
    bb, nb = sv.blocks(base, 0), sv.blocks(new, 0)
    for (t, _, p, size), (_, _, q, nsize) in zip(bb, nb):
        if t not in ('IVMG', 'IVPD', 'PDCC', 'IIUC'):
            check(base[p:p + 16 + size] == new[q:q + 16 + nsize], 'только башни: блок %s изменился' % t)
    bi, ni, si = sv.Inventory(base), sv.Inventory(new), sv.Inventory(source)
    check(sv.talion(new) == sv.talion(base), 'только башни: уровень изменился')
    check([(i['uid'], i['level'], i['template']) for i in ni.items] ==
          [(i['uid'], i['level'], i['template']) for i in bi.items], 'только башни: предметы изменились')
    check(ni.equipped == bi.equipped and ni.sockets == bi.sockets, 'только башни: экипировка или слоты')
    sb, sn, ss = stock_names(bi, gd), stock_names(ni, gd), stock_names(si, gd)
    for k in set(sb) | set(sn) | set(ss):
        want = ss.get(k) if ngplus.tower_re(ngplus.tower_regions(base), ngplus.tower_skip(base)).match(k) else sb.get(k)
        check(sn.get(k) == want, 'только башни: %s = %s, ждали %s' % (k, sn.get(k), want))
    for tag, pattern in ngplus.tower_state(ngplus.TOWER_REGIONS if ngplus.tower_skip(base) else ngplus.tower_regions(base)):
        vals = lambda buf: [(n, buf[t.pos:t.end]) for n, t in ngplus._named_values(buf, tag, gd.record, pattern)]
        check(vals(new) == vals(source), 'только башни: %s' % tag)
    check(ngplus.add_towers(new, source, gd, log=lambda s: None) == new, 'только башни: повтор дал другой файл')


def iiuc_state(buf, gd):
    """(shown-on-map record ids, {region: (placed words, known words)})"""
    return ngplus.shown_on_map(buf), ngplus.door_puzzles(buf, gd.record)


def check_collectibles(base, source, gd):
    kinds = [k for k, _, _ in ngplus.COLLECTIBLES]
    new = ngplus.build(base, source, gd, log=lambda s: print('   ' + s), collect=kinds)
    plain = ngplus.build(base, source, gd, log=lambda s: None)
    bb, nb = sv.blocks(plain, 0), sv.blocks(new, 0)
    for (t, _, p, size), (_, _, q, nsize) in zip(bb, nb):
        if t not in ('IVMG', 'IVPD', 'IIUC', 'PDCC'):
            check(plain[p:p + 16 + size] == new[q:q + 16 + nsize], 'коллекции: блок %s изменился' % t)
    rec = gd.record
    have = {rec(r) or '' for r, v in ngplus._learned(new, sv.Inventory(new)).items() if v > 0}
    src = {rec(r) or '' for r, v in ngplus._learned(source, sv.Inventory(source)).items() if v > 0}
    col = sorted(n for n in have if ngplus.COLLECTIBLE_RE.match(n) or n.startswith('Col_SpiderPickup_Final'))
    check('Col_SpiderPickup_Final' not in have, 'коллекции: перенесено Col_SpiderPickup_Final')
    own = {rec(r) or '' for r, v in ngplus._learned(plain, sv.Inventory(plain)).items() if v > 0}
    check(all(n in src or n in own for n in col), 'коллекции: появилось то, чего нет ни в пройденной игре, ни в опоре')
    for kind, prefix, title in ngplus.COLLECTIBLES:
        every = [n for n in gd.records.values() if n.startswith(prefix) and ngplus.COLLECTIBLE_RE.match(n)]
        mine = [n for n in col if n.startswith(prefix)]
        check(kind == 'ithildin' or len(mine) < len(every) or sum(n in own for n in every) == len(every),
              '%s: перенесён полный набор' % title)
        want = [n for n in src if n.startswith(prefix) and ngplus.COLLECTIBLE_RE.match(n)]
        check(len(mine) >= min(len(want), len(every) - (kind != 'ithildin')),
              '%s: перенесено %d из %d' % (title, len(mine), len(want)))
    gondor = sum(n.startswith('Col_GondorPickup_') for n in col)
    if gondor:
        check(sv.Inventory(new).stock_count(ngplus.GONDOR_COUNTER) == gondor and
              sv.unlocks(new).get(ngplus.GONDOR_COUNTER) == gondor,
              'счётчик гондорских артефактов %s, ждали %d' % (sv.Inventory(new).stock_count(ngplus.GONDOR_COUNTER), gondor))
    shown, doors = iiuc_state(new, gd)
    _, base_doors = iiuc_state(plain, gd)
    ids = {name_hash(n) for n in col}
    check(not ids & set(shown), 'коллекции: подобранное осталось на карте')
    for region, (placed, known) in doors.items():
        check(placed == base_doors[region][0], 'дверь %s: вставленные слова изменились' % region)
        words = sorted(int(n.rsplit('_', 1)[1]) - 1 for n in col if n.startswith('Col_Lore_DoorClue_%s_' % region))
        check(sorted(w for w in known if w >= 0) == sorted(set(words) | {w for w in base_doors[region][1] if w >= 0}),
              'дверь %s: известные слова %s, ждали %s' % (region, known, words))
    again = ngplus.build(base, new, gd, log=lambda s: None, collect=kinds)
    check(ngplus.build(base, again, gd, log=lambda s: None, collect=kinds) == again,
          'коллекции: повторная сборка дала другой файл')


def check_marks(base, source, gd):
    """Towers + all collectibles: every not picked-up collectible of an open region is shown on the map."""
    kinds = [k for k, _, _ in ngplus.COLLECTIBLES]
    new = ngplus.build(base, source, gd, log=lambda s: print('   ' + s), towers=True, collect=kinds)
    rec = gd.record
    picked = ngplus._picked(new, rec)
    shown = {rec(v) or '#%08x' % v for v in iiuc_state(new, gd)[0]}
    act1 = ngplus.act1_done(base)
    every = [n for n in gd.records.values() if ngplus.COLLECTIBLE_RE.match(n)]
    check(not shown & picked, 'метки: подобранное отмечено на карте: %s' % sorted(shown & picked)[:5])
    for n in every:
        m = __import__('re').match(r'Col_Lore_DoorClue_([A-Za-z]+)_\d+$', n)
        minas = m and m.group(1) == ngplus.MINAS
        want = n not in picked and (act1 or (m and not minas))
        if want:
            check(n in shown, 'метки: нет метки у %s' % n)
        elif not act1 and (minas or not m):
            base_shown = {rec(v) for v in iiuc_state(base, gd)[0]}
            check(n not in shown or n in base_shown, 'метки: первый акт не пройден, а отмечено %s' % n)
    check('Col_SpiderPickup_Final' not in shown or 'Col_SpiderPickup_Final' in {rec(v) for v in iiuc_state(base, gd)[0]},
          'метки: отмечено последнее воспоминание Шелоб')
    # counters agree with the records
    import re as _re
    regions = (ngplus.MINAS,) + ngplus.TOWER_REGIONS
    pd = {n: t.value for n, t in ngplus._named_values(new, 'PDCC', rec, _re.compile(r'.*'))}
    stones = {n: t.value for n, t in ngplus._named_values(new, 'IIUC', rec, _re.compile(r'SeeingStone_'))}
    for r in regions:
        taken = [int(m.group(1)) for m in (_re.match(r'%s_Tower_(\d+)$' % r, n) for n in picked) if m]
        check(pd.get('TowerPurify_' + r) == len(taken), 'счётчик хэдиров %s = %s, захвачено %d' % (r, pd.get('TowerPurify_' + r), len(taken)))
        for k in taken:
            check(stones.get('SeeingStone_%s_%02d' % (r, k + 1)) == 1, 'признак хэдира %s_%02d не стоит' % (r, k + 1))
        words = sum(1 for n in picked if _re.match(r'Col_Lore_DoorClue_%s_\d+$' % r, n))
        check(pd.get('DoorPuzzle_' + r) == words, 'счётчик итильдина %s = %s, подобрано %d' % (r, pd.get('DoorPuzzle_' + r), words))
    if act1:
        for prefix, item in (('GondorCollectible_', 'Col_GondorPickup_'), ('ShelobCollectible_', 'Col_SpiderPickup_')):
            total = sum(1 for n in picked if n.startswith(item) and ngplus.COLLECTIBLE_RE.match(n))
            got = sum(pd.get(prefix + r, 0) for r in regions)
            check(got == total, 'счётчики %s по регионам: сумма %d, подобрано %d' % (prefix, got, total))
    again = ngplus.build(base, new, gd, log=lambda s: None, towers=True, collect=kinds)
    check(ngplus.build(base, again, gd, log=lambda s: None, towers=True, collect=kinds) == again,
          'метки: повторная сборка дала другой файл')


def expect_error(what, fn, *words):
    """fn() must raise SaveError whose message has all the words."""
    try:
        fn()
    except sv.SaveError as e:
        msg = str(e)
        return check(all(w in msg for w in words), '%s: в сообщении нет %s: %s' % (what, words, msg))
    except Exception as e:                               # noqa: BLE001
        return check(False, '%s: вместо понятной ошибки %s: %s' % (what, type(e).__name__, e))
    return check(False, '%s: ошибки нет' % what)


def check_errors(saves, src, data_dir, gd):
    """Broken, renamed and mixed-up saves give a message, not a crash."""
    import shutil
    import subprocess
    import tempfile
    tmp = tempfile.mkdtemp(prefix='sowcheck_')
    try:
        raw = open(PATHS[src], 'rb').read()
        user = crypto.user_id_from_name(src)

        def put(name, data):
            p = os.path.join(tmp, name)
            open(p, 'wb').write(data)
            return p
        expect_error('мусор', lambda: sv.load(put('a_ShadowOfWar.sav', os.urandom(5000))), 'не сохранение')
        expect_error('переименованный', lambda: sv.load(put('12345678_ShadowOfWar.sav', raw)), 'имя')
        expect_error('обрезанный', lambda: sv.load(put('%08x_ShadowOfWar.sav' % user, raw[:len(raw) // 2])),
                     'расшифровать')
        expect_error('нет файла', lambda: sv.load(os.path.join(tmp, 'nope_ShadowOfWar.sav')), 'открыть')
        buf = saves[src]
        s0, _ = sv.sections(buf)[0]
        for what, pos, val in (('длина раздела 0', s0 - 8, 0), ('длина блоков', s0 + 0x43, 12345),
                               ('размер блока', sv.block(buf, 'IVPD')[0] + 8, 0x7FFFFFF)):
            bad = bytearray(buf)
            struct.pack_into('<I', bad, pos, val)
            p = put('%08x_ShadowOfWar.sav' % user, crypto.encrypt(bytes(bad), user))
            expect_error(what, lambda: sv.load(p), 'незнакомое устройство')

        base = next(b for f, b in saves.items() if f != src)
        expect_error('одно и то же', lambda: ngplus.check_pair(buf, buf), 'одно и то же')
        check(any('перепутаны' in w for w in ngplus.check_pair(buf, base)), 'нет предупреждения: опора выше уровнем')
        swapped = ngplus.build(buf, base, gd, log=lambda s: None)       # allowed: the user may want it
        check(sv.talion(swapped) == sv.talion(base), 'перенос на опору с большим уровнем')
        old = bytearray(base)
        struct.pack_into('<I', old, sv.block(base, 'IVMG')[0] + 4, 42)
        expect_error('версии блоков', lambda: ngplus.check_pair(bytes(old), buf), 'разными версиями')
        other = bytearray(base)
        struct.pack_into('<I', other, 0x14, 8000)
        check(any('1.0.8000' in w for w in sv.warnings(bytes(other))), 'нет предупреждения о версии игры')

        # the command line: message and code 2, nothing written
        out = os.path.join(tmp, '%08x_ShadowOfWar.sav' % user)
        if os.path.exists(out):
            os.remove(out)
        r = subprocess.run([sys.executable, '-m', 'sowtool', '--data', data_dir, 'ngplus', '--base',
                            PATHS[src], '--source', PATHS[src], '--out', out],
                           cwd=os.path.dirname(HERE), capture_output=True, encoding='utf-8')
        check(r.returncode == 2 and r.stdout.startswith('Ошибка:') and 'Traceback' not in r.stdout + r.stderr,
              'командная строка: код %d, вывод %r' % (r.returncode, (r.stdout + r.stderr)[:300]))
        check(not os.path.exists(out), 'командная строка: файл записан несмотря на ошибку')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default=os.path.join(PROJECT, 'app', 'gui', 'data'))
    ap.add_argument('--saves', default=os.path.join(PROJECT, 'game files'))
    ap.add_argument('--source')
    ap.add_argument('--keep', help='folder to write the built saves into (decrypted, .bin)')
    args = ap.parse_args()
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):
            pass
    gd = GameData(os.path.join(args.data, 'game.gamedb'), os.path.join(args.data, 'string_ruru.strdb'))

    saves = {}
    folders = [args.saves, os.path.join(PROJECT, 'app', 'gui', 'bases')]      # + the bases shipped with the tool
    for f, path in sorted((f, os.path.join(d, f)) for d in folders if os.path.isdir(d) for f in os.listdir(d)):
        if f.lower().endswith('.sav'):
            PATHS[f] = path
            raw = open(path, 'rb').read()
            print('%s' % f)
            try:
                buf, user = check_file(path, raw)
            except Exception as e:                       # noqa: BLE001
                check(False, '%s: %s: %s' % (f, type(e).__name__, e))
                continue
            print('   уровень %s, разделов %d, пользователь %s, данных %d байт'
                  % (sv.talion(buf)[0], len(sv.sections(buf)), '%08x' % user if user else 0, len(buf)))
            saves[f] = buf
    if not saves:
        sys.exit('нет сохранений в %s' % args.saves)
    src = os.path.basename(args.source) if args.source else max(saves, key=lambda f: sv.talion(saves[f])[0] or 0)
    print('\nПройденная игра: %s' % src)
    for f, buf in saves.items():
        if f == src:
            continue
        print('\nНовая игра+ на основе %s' % f)
        try:
            new = check_build(f, buf, saves[src], gd)
            print('   — с башнями:')
            check_build(f, buf, saves[src], gd, towers=True)
            check_towers_only(buf, saves[src], gd)
            print('   — с коллекциями:')
            check_collectibles(buf, saves[src], gd)
            print('   — башни, коллекции и метки:')
            check_marks(buf, saves[src], gd)
            print('   — настройки игры:')
            check_settings(buf, saves[src], gd)
            print('   — новая армия:')
            check_army(buf, saves[src], gd)
            check_twenty(buf, saves[src], gd)
            print('   — с чисткой снаряжения:')
            check_clean_gear(buf, saves[src], gd)
            print('   — с началом с уровня новой игры:')
            check_start_level(buf, saves[src], gd)
            if args.keep:
                open(os.path.join(args.keep, f + '.ngplus.bin'), 'wb').write(new)
        except Exception as e:                           # noqa: BLE001
            import traceback
            traceback.print_exc()
            check(False, '%s: %s: %s' % (f, type(e).__name__, e))
    print('\nАрмия Немезиды')
    for f, buf in saves.items():
        try:
            check_orcs(f, buf, gd)
        except Exception as e:                           # noqa: BLE001
            check(False, '%s: орки: %s: %s' % (f, type(e).__name__, e))
    print('\nИспорченные и перепутанные сохранения')
    check_errors(saves, src, args.data, gd)
    print('\n' + ('Все проверки пройдены' if not failures else 'Ошибок: %d' % len(failures)))
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
