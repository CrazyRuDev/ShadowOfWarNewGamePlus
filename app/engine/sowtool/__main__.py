"""Command line of the Shadow of War save tool.

    sowtool info <save> [--data DIR] [--format text|json|tsv]
    sowtool ngplus --base <new game save> --source <finished game save> --out <save> [--towers] [--ithildin] [--gondor] [--shelob] [--start-level] [--clean-gear] [--keep-army] [--twenty] [--twenty-count N] [--weak MODE] [--data DIR]
    sowtool world --base <save> --source <finished game save> --out <save> [--towers] [--ithildin] [--gondor] [--shelob]
                                    (only the towers / collectibles, Talion untouched)
    sowtool orcs <save> [--format text|tsv]  (the Nemesis army: every orc, recommended ones for the new game+)
    sowtool plan --base <save> --source <save>  (what each ngplus option would do, tsv lines)
    sowtool chronicle --out <folder> [--save <file>] [--source <finished game save>]  (the debug log of a play)
    sowtool setup --game <game folder> [--data DIR]
    sowtool locate                  (Steam: game folder and newest save, as 'game<TAB>path', 'save<TAB>path')

--data is the folder with game.gamedb and string_ruru.strdb (made by setup); by default 'data' next to the tool.
"""
import argparse
import json
import os
import sys

from . import archive, chronicle, crypto, ngplus, orcs as orcs_mod, returned, save as sv, steam
from .gamedata import GameData


def default_data_dir():
    base = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__))
    if not getattr(sys, 'frozen', False):
        base = os.path.dirname(base)
    return os.path.join(base, 'data')


def game_data(data_dir):
    db, txt = os.path.join(data_dir, 'game.gamedb'), os.path.join(data_dir, 'string_ruru.strdb')
    if not (os.path.exists(db) and os.path.exists(txt)):
        sys.exit('Нет данных игры в %s - сначала выполните setup' % data_dir)
    return GameData(db, txt)


def tsv(rep):
    """Line-based form for the AutoHotkey GUI: kind<TAB>fields..., tabs and newlines removed from values."""
    def f(*vals):
        return '\t'.join('' if v is None else str(v).replace('\t', ' ').replace('\n', ' ') for v in vals)
    lines = [f('talion', rep['level'], rep['xp'], rep['xp_next'], rep['mirians'], rep['skill_points'])]
    for r in rep['rows']:
        lines.append(f('row', r['title'], r['learned'], r['total']))
        for n in r['nodes']:
            for s in n['skills']:
                lines.append(f('skill', r['title'], n['node'], int(s['child']), int(s['learned']), s['rank'],
                               s['name'], s['key'], s['text']))
    eq = set(rep['equipped'])
    for it in rep['items']:
        lines.append(f('item', it['uid'], it['level'], it['slot'], it['rarity'], int(it['uid'] in eq), it['name'],
                       it['owner'], it['rarity_line'], it['description'],
                       ' | '.join('%s:%s' % (k, t.replace('|', '/')) for k, t in it['effects'])))
    for g in rep['gems']:
        lines.append(f('gem', g['count'], g['name'], g['key']))
    for s in rep['sockets']:
        lines.append(f('socket', s['socket'], s['gem']))
    world = rep.get('world')
    if world:
        lines.append(f('world_act1', int(world['act1'])))
        for r in world['regions']:
            lines.append(f('world_region', r['region'], r['towers'], r['ithildin'], r['ithildin_total'],
                           r['door_known'], r['door_placed'], r['door_slots'], r['towers_counter'],
                           r['ithildin_counter'], r['gondor'], r['shelob']))
        for c in world['collections']:
            lines.append(f('world_collection', c['title'], c['have'], c['total'], c['note']))
    for w in rep.get('warnings', ()):
        lines.append(f('warning', w))
    return '\n'.join(lines)


def orcs_report(buf, gd, fmt):
    army = orcs_mod.read(buf, gd)
    orcs_mod.recommend(army)

    def f(*vals):
        return '\t'.join('' if v is None else str(v).replace('\t', ' ').replace('\n', ' ') for v in vals)
    names = orcs_mod.Names(gd)
    weights = sorted(orcs_mod.recommend.weights.items(), key=lambda x: -x[1])
    lines = [f('orc_weights', orcs_mod.recommend.how, ', '.join(
        '%s +%g' % ((names.trait(p) or (p,))[0], w) for p, w in weights))]
    for o in army:
        if fmt == 'tsv':
            lines.append(f('orc', orcs_mod.group(o), o['number'], o['name'], o['title'], o['level'],
                           'мёртв' if o['dead'] else 'жив', o['region'], o['place'], o['class'], o['tribe'],
                           o['rarity'], o['score'], o['kill'], o['last'], o['fled'], o['back'], o['death'],
                           o['pick'], o.get('target', ''), o['why'], ' ¶ '.join(orcs_mod.details(o))))
        else:
            lines.append('%-26s №%-4d %-34s ур.%-3d %-5s %-12s счёт %-3d %s' % (
                orcs_mod.group(o), o['number'], (o['name'] + ' ' + o['title'])[:34], o['level'],
                'мёртв' if o['dead'] else 'жив', o['region'], o['score'], o['pick']))
    return '\n'.join(lines)


def text(rep):
    out = ['Предупреждение: ' + w for w in rep.get('warnings', ())]
    out += ['Уровень %s, опыт %s / %s, мирианы %s, очки навыков %s' % (rep['level'], rep['xp'], rep['xp_next'],
                                                                  rep['mirians'], rep['skill_points']), '']
    for r in rep['rows']:
        out.append('%s %d/%d' % (r['title'], r['learned'], r['total']))
        for n in r['nodes']:
            out.append('   ' + ', '.join(('+' if s['learned'] else '-') + s['name'] for s in n['skills']))
    eq = set(rep['equipped'])
    out += ['', 'Предметы (%d):' % len(rep['items'])]
    for it in rep['items']:
        out.append('  %s№%-5d %s, ур. %d (%s, %s)%s' % ('*' if it['uid'] in eq else ' ', it['uid'], it['name'],
                                                    it['level'], it['slot'], it['rarity'],
                                                    ', владелец: ' + it['owner'] if it['owner'] else ''))
    out += ['', 'Самоцветы:'] + ['  %s: %d' % (g['name'], g['count']) for g in rep['gems']]
    out += ['', 'Слоты:'] + ['  %s: %s' % (s['socket'], s['gem'] or '-') for s in rep['sockets']]
    world = rep.get('world')
    if world:
        out += ['', 'Мир (первый акт %s):' % ('пройден' if world['act1'] else 'не пройден')]
        out += ['  %-13s хэдиры %d/3 (счётчик игры %d), итильдин %d/%d (счётчик игры %d), дверь: известно слов %d, '
                'вставлено %d/%d; счётчики игры: артефакты %d, воспоминания %d'
                % (r['region'], r['towers'], r['towers_counter'], r['ithildin'], r['ithildin_total'],
                   r['ithildin_counter'], r['door_known'], r['door_placed'], r['door_slots'], r['gondor'], r['shelob'])
                for r in world['regions']]
        out += ['  %s: %d/%d%s' % (c['title'], c['have'], c['total'], ' (%s)' % c['note'] if c['note'] else '')
                for c in world['collections']]
    return '\n'.join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(prog='sowtool')
    ap.add_argument('--data', default=None)
    ap.add_argument('--history', choices=tuple(orcs_mod.HISTORY_MODES), default=orcs_mod.HISTORY,
                    help='how the events of past games (new game+) count in the orc score: decay (at half), last '
                         '(not at all), all')
    sub = ap.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('info')
    a.add_argument('save')
    a.add_argument('--format', choices=('text', 'json', 'tsv'), default='text')
    a.add_argument('--out')
    a = sub.add_parser('ngplus')
    a.add_argument('--base', required=True)
    a.add_argument('--source', required=True)
    a.add_argument('--out', required=True)
    a.add_argument('--towers', action='store_true', help='also take over the towers (all regions but Minas Morgul)')
    a.add_argument('--keep-army', action='store_true',
                   help="keep the base's army (by default its random orcs are replaced with orcs of the finished game "
                        "that never met Talion, see army)")
    a.add_argument('--twenty', action='store_true',
                   help='the orcs that troubled Talion most into Nurn (and Cirith Ungol after the prologue), those he '
                        'killed back from the dead (see returned)')
    a.add_argument('--twenty-count', type=int, choices=returned.COUNTS, default=returned.DEFAULT_COUNT,
                   help='how many of them (by importance: nemeses of Nurn, bosses, captains)')
    a.add_argument('--weak', choices=tuple(returned.WEAK), default='none',
                   help='weaknesses taken off them: ' + '; '.join('%s = %s' % (k, v[0])
                                                                  for k, v in returned.WEAK.items()))
    a.add_argument('--clean-gear', action='store_true', help='remove the common and rare gear that is not equipped')
    a.add_argument('--start-level', action='store_true',
                   help="Talion and his gear at the new game's level (act 2: median captain of Nurn - 2)")
    for kind, _, title in ngplus.COLLECTIBLES:
        a.add_argument('--' + kind, action='store_true', help='picked-up ' + kind + ' (all but one of each set)')
    a = sub.add_parser('plan', help='what each build option would do (tsv lines for the GUI cards)')
    a.add_argument('--base', required=True)
    a.add_argument('--source', required=True)
    a = sub.add_parser('world', help='only the towers / collectibles into a save, Talion untouched')
    a.add_argument('--base', required=True)
    a.add_argument('--source', required=True)
    a.add_argument('--out', required=True)
    a.add_argument('--towers', action='store_true')
    a.add_argument('--marks', action='store_true', help='only the map markers of the towers already taken')
    for kind, _, _ in ngplus.COLLECTIBLES:
        a.add_argument('--' + kind, action='store_true')
    a = sub.add_parser('orcs')
    a.add_argument('save')
    a.add_argument('--format', choices=('text', 'tsv'), default='text')
    a.add_argument('--out')
    a = sub.add_parser('chronicle', help='watch the save while playing, a short log of what matters (see chronicle)')
    a.add_argument('--out', required=True)
    a.add_argument('--save', help='the save to watch (default: the newest Steam save)')
    a.add_argument('--source', help='the finished game: its orcs are marked in the log')
    a.add_argument('--parent', type=int, help='stop when this process (the window) is gone')
    a = sub.add_parser('setup')
    a.add_argument('--game', required=True)
    sub.add_parser('locate')
    args = ap.parse_args(argv)
    orcs_mod.HISTORY = args.history
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):
            pass
    data_dir = args.data or default_data_dir()

    if args.cmd == 'locate':
        print('game\t%s' % (steam.find_game() or ''))
        print('save\t%s' % (steam.find_save() or ''))
        return
    if args.cmd == 'setup':
        archive.extract(args.game, data_dir)
        return
    gd = game_data(data_dir)
    if args.cmd == 'info':
        buf, _ = sv.load(args.save)
        rep = sv.report(buf, gd)
        rep['warnings'] = sv.warnings(buf, os.path.basename(args.save))
        rep['world'] = ngplus.world_report(buf, gd)
        out = json.dumps(rep, ensure_ascii=False, indent=1) if args.format == 'json' else \
            tsv(rep) if args.format == 'tsv' else text(rep)
        if args.out:
            with open(args.out, 'w', encoding='utf-8') as f:
                f.write(out)
        else:
            print(out)
    elif args.cmd == 'chronicle':
        path = args.save or steam.find_save()
        if not path or not os.path.exists(path):
            raise sv.SaveError('Сохранение не найдено — укажите его вверху окна или через --save.')
        chronicle.watch(path, args.out, gd, args.source, parent=args.parent)
    elif args.cmd == 'orcs':
        buf, _ = sv.load(args.save)
        out = orcs_report(buf, gd, args.format)
        if args.out:
            with open(args.out, 'w', encoding='utf-8') as f:
                f.write(out)
        else:
            print(out)
    elif args.cmd == 'plan':
        base, _ = sv.load(args.base)
        source, _ = sv.load(args.source)
        p = ngplus.plan(base, source, gd)
        print('plan_base	%d	%s' % (int(p['act1']), p['base_level']))
        print('plan_level	%s	%s' % (p['source_level'], p['start_level']))
        print('plan_towers	%d' % p['towers'])
        for kind, n in p['collect'].items():
            print('plan_collect	%s	%s' % (kind, '' if n is None else n))
        print('plan_clean	%d	%d' % (p['clutter'], p['items']))
        print('plan_blocked	%d	%s' % (len(p['blocked']), ', '.join(p['blocked'])))
        print('plan_army	%d	%s' % (sum(p['army'].values()), ', '.join('%s %d' % kv for kv in p['army'].items())))
        for n, where in p['twenty'].items():
            print('plan_twenty	%d	%d	%d	%s' % (n, p['picked'], sum(v for k, v in where.items() if k != 'предатель'),
                                                ', '.join('%s %d' % kv for kv in where.items())))
    elif args.cmd == 'world':
        base, user = sv.load(args.base)
        source, _ = sv.load(args.source)
        user = user if user is not None else 0
        out_user = crypto.user_id_from_name(args.out) if '_ShadowOfWar' in os.path.basename(args.out) else user
        new = ngplus.add_towers(base, source, gd) if args.towers else base
        collect = [k for k, _, _ in ngplus.COLLECTIBLES if getattr(args, k)]
        if collect:
            new = ngplus.add_collectibles(new, source, gd, collect)
        if args.towers or args.marks:
            new = ngplus.add_marks(new, gd)
        sv.validate(new, 'результат')
        sv.write(args.out, new, out_user)
        print('Записано: %s' % args.out)
    elif args.cmd == 'ngplus':
        # the finished game itself as the target, outside Steam (its kept copy — 2026-10-23 an empty «куда» got the
        # source's path and the new game went over it): refuse. In the Steam slot it is the usual way and goes on.
        if os.path.isfile(args.out) and 'userdata' not in os.path.abspath(args.out).lower() \
                and open(args.out, 'rb').read() == open(args.source, 'rb').read():
            raise sv.SaveError('«Куда записать» — это сама пройденная игра (%s), не сохранение Steam. Ничего не '
                               'записано: выберите сохранение в папке Steam (кнопка рядом с полем).' % args.out)
        base, _ = sv.load(args.base)
        source, user = sv.load(args.source)
        user = user if user is not None else 0
        out_user = crypto.user_id_from_name(args.out) if '_ShadowOfWar' in os.path.basename(args.out) else user
        for w in ngplus.check_pair(base, source):
            print('Предупреждение: ' + w)
        new = ngplus.build(base, source, gd, towers=args.towers,
                           collect=[k for k, _, _ in ngplus.COLLECTIBLES if getattr(args, k)],
                           start=args.start_level, clean=args.clean_gear,
                           new_army=not args.keep_army, twenty=args.twenty, twenty_count=args.twenty_count,
                           weak=args.weak)
        sv.validate(new, 'результат')
        try:
            sv.write(args.out, new, out_user)
        except OSError as e:
            raise sv.SaveError('Не удалось записать %s (%s). Закройте игру, если она запущена, и проверьте, '
                               'что папка доступна для записи.' % (args.out, e.strerror or e))
        print('Записано: %s' % args.out)


def run():
    """main() with errors as messages: 2 - a problem with the saves, 3 - a bug of the tool."""
    try:
        main()
    except sv.SaveError as e:
        print('Ошибка: %s' % e)
        sys.exit(2)
    except Exception as e:                                    # noqa: BLE001
        import traceback
        print('Внутренняя ошибка программы: %s: %s\nЕсли повторяется — сообщите автору и приложите сохранение.'
              '\n\n%s' % (type(e).__name__, e, traceback.format_exc()))
        sys.exit(3)


if __name__ == '__main__':
    run()
