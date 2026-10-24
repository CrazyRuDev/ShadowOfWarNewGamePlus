"""Which roles (titles) have an origin line ("history" an orc tells when presented / back from the dead) and in
which voice (research).

Role -> number: AudioHooks/Conditions record RoleCategory_<NNN>_<Name>; the line is dx_pr_sh_OriginRole<NNN>_<voice>_01
or dx_pr_sh_TransOriginRole<NNN>_<voice>_01 (a transformation). Voice = personality: PersonalityMarker_Whiner2 ->
wh2, Wise1 -> ws1, Clever1 -> cv1, Brute1 -> br1, Twisted2 -> tw2, Professional1 -> pr1, ...

    python research/role_voice.py [Role_X ...]
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app', 'engine'))
from sowtool.gamedata import GameData, name_hash      # noqa: E402

VOICE = {'Whiner': 'wh', 'Wise': 'ws', 'Clever': 'cv', 'Brute': 'br', 'Twisted': 'tw', 'Professional': 'pr',
         'Bully': 'bs', 'Zealot': 'ze', 'Gentleman': 'gn'}


def voice(personality):
    """'PersonalityMarker_Whiner2' -> 'wh2'"""
    m = re.match(r'PersonalityMarker_([A-Za-z]+?)(\d)$', personality or '')
    return (VOICE.get(m.group(1), m.group(1)[:2].lower()) + m.group(2)) if m else None


def role_lines(gd):
    """{role name: (number, [(kind, voice, text)])} for every RoleCategory condition."""
    cats = [n for _, n in gd.category('AudioHooks/Conditions') if n.startswith('RoleCategory_')]
    names = {name_hash(n): n for n in gd.records.values()}
    lines = {}
    for k, v in gd.text.items():
        n = names.get(k, '')
        m = re.match(r'dx_pr_sh_(Trans)?OriginRole(\d+)_([a-z]+\d)_\d+$', n)
        if m:
            lines.setdefault(m.group(2), []).append(('превращение' if m.group(1) else 'происхождение', m.group(3), v))
    out = {}
    for c in cats:
        m = re.match(r'RoleCategory_(\d+)_(.+)$', c)
        if m:
            out['Role_' + m.group(2)] = (m.group(1), lines.get(m.group(1), []))
        else:
            out['Role_' + c[len('RoleCategory_'):]] = (None, [])
    return out


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    gd = GameData(os.path.join(ROOT, 'app', 'gui', 'data', 'game.gamedb'),
                  os.path.join(ROOT, 'app', 'gui', 'data', 'string_ruru.strdb'))
    rl = role_lines(gd)
    with_line = sum(1 for n, l in rl.values() if l)
    print('ролей в условиях: %d, с номером: %d, с репликой: %d' % (len(rl), sum(1 for n, _ in rl.values() if n), with_line))
    for r in sys.argv[1:] or sorted(rl):
        # the role names in conditions are not always the Role_ record names: try a loose match
        key = r if r in rl else next((k for k in rl if k.lower().replace('_', '') == r.lower().replace('_', '')), None)
        if key is None:
            key = next((k for k in rl if r.replace('Role_', '').lower() in k.lower()), None)
        n, l = rl.get(key, (None, []))
        title = gd.text.get(name_hash('Orc_Title_' + r.replace('Role_', '')))
        print('%-22s (%s) %-6s %s' % (r, title or key, n or '—', '; '.join('%s %s: %s' % (k, v, t[:60]) for k, v, t in l) or 'реплики нет'))
