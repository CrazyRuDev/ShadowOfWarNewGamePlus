"""The Nemesis event queue of a save: event, region, orc, game-time left (debug tool).

    python research/queue.py [<save>]          (default: the newest Steam save)

Queue entry: 0c 01 | 00 Faction_<region> | 00 <event> | 00 Faction_<region> or 0 | 04 <orc or -1> | 08 <tag> |
04 <time left, ms of game time>. The timer only runs while playing (not in menus) and is written on every save.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app', 'engine'))
sys.path.insert(0, os.path.join(ROOT, 'research'))
from sowtool import save as sv, steam                 # noqa: E402
from sowtool.gamedata import GameData                 # noqa: E402

DESCR = {'CheatDeath_Ambush': 'обманул смерть — засада', 'General_Ambush_Zog': 'засада Зога (сюжет)',
         'PC_LowHealth_GeneralUse': 'засада, когда мало здоровья', 'PC_LowHealth_ContextAmb': 'засада, когда мало здоровья',
         'PC_Collect_Gear_ContextAmb': 'засада при сборе добычи', 'PC_MountedCaragor_Ambush': 'засада на всаднике',
         'PC_Showdown_Ambush': 'засада после стычки', 'PC_Fleeing_Ambush': 'засада при бегстве',
         'PC_Respawn_Ambush': 'засада после воскрешения Талиона', 'Periodic_Ambush': 'периодическая засада',
         'GiftGiver_Follower_Ambush': 'засада с подарком последователя',
         'BruzBrothers_Daz_Ambush': 'засада Даза, брата Бруза (сюжет; ждёт условий, перевыставляется)'}


def describe(event):
    if event in DESCR:
        return DESCR[event]
    if 'Ambush' in event:
        return 'засада'
    if 'Betray' in event:
        return 'предательство'
    return ''


REGIONS = {'Faction_MinasIthil': 'Минас-Моргул', 'Faction_MtnPass': 'Кирит-Унгол', 'Faction_snowMtn': 'Серегост',
           'Faction_volcano': 'Горгорот', 'Faction_island': 'Нурн', 'Faction_desert_Real': 'Пустошь'}


def queue(buf, gd):
    """[(event, region, orc number, orc name, tag, ms left)] in queue order."""
    rec = gd.record
    p, size = sv.block(buf, 'WHDC')
    t = sv.tokens(buf, p + 20, p + 16 + size)
    q = [i for i in range(len(t) - 7) if t[i].type == 0x0C and t[i].value == 1 and t[i + 1].type == 0
         and (rec(t[i + 1].value) or '').startswith('Faction_') and t[i + 2].type == 0 and t[i + 3].type == 0
         and t[i + 4].type == 4 and t[i + 5].type == 8 and t[i + 6].type == 4]
    names = {}
    try:
        import orcs2
        names = {o['number']: '%s %s' % (o.get('name', '?'), orcs2.title(gd, o['role'])) for o in orcs2.orcs(buf, gd)
                 if o.get('number') is not None}
    except Exception:                                  # noqa: BLE001 - names are only a convenience
        pass
    out = []
    for i in q:
        num = t[i + 4].value
        out.append((rec(t[i + 2].value) or '#%08x' % t[i + 2].value, REGIONS.get(rec(t[i + 1].value), rec(t[i + 1].value)),
                    num, names.get(num, '') if num >= 0 else '', t[i + 5].value, t[i + 6].value))
    return out


def fmt(ms):
    s = max(ms, 0) // 1000
    return '%d:%02d:%02d' % (s // 3600, s // 60 % 60, s % 60) if s >= 3600 else '%d:%02d' % (s // 60, s % 60)


def lines(buf, gd):
    q = queue(buf, gd)
    out = ['Очередь Немезиды: %d событий (время — игровое, на момент записи сохранения)' % len(q)]
    for ev, reg, num, name, tag, ms in sorted(q, key=lambda e: e[5]):
        out.append('  через %-8s %-34s %-13s %s' % (fmt(ms), ev, reg, ('№%d %s' % (num, name)) if num >= 0 else ''))
    return out


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    path = sys.argv[1] if len(sys.argv) > 1 else steam.find_save()
    gd = GameData(os.path.join(ROOT, 'app', 'gui', 'data', 'game.gamedb'),
                  os.path.join(ROOT, 'app', 'gui', 'data', 'string_ruru.strdb'))
    buf, _ = sv.load(path)
    print('\n'.join(lines(buf, gd)))
