import sys
sys.path.insert(0,'/tmp/claude-0/-home-user-claude/736d1654-7f66-5b6b-ac74-5dab6060c2ec/scratchpad/tools')
import sowpe
_t=sowpe.d[sowpe.va2off(0x141db50d0):][:256]
T=[x-256 if x>127 else x for x in _t]
def h(s,v=0):
    if isinstance(s,str): s=s.encode('latin1')
    for c in s: v=(v*0x397+T[c])&0xffffffff
    return v
