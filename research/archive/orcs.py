import sys,re,struct
sys.path.insert(0,'/tmp/claude-0/-home-user-claude/736d1654-7f66-5b6b-ac74-5dab6060c2ec/scratchpad/tools')
import savetok,gdbrec,gdb,h397
D=gdb.D; C=gdbrec.load()
ru=savetok.ru; H=savetok.H
def say(k): return ru.get(h397.h(k))
cat=lambda n:[c for c in C if c['name']==n][0]['recs']
defs={}
for p,n in cat('Faction/Traits/Definitions'):
    v=struct.unpack_from('<I',D,p+0x3c)[0]; w=struct.unpack_from('<I',D,p+0x40)[0]
    defs[n]=(gdb.pstr(v),)
norm=lambda s:re.sub(r'[_\W]','',s.lower())
dnorm={norm(n):n for n in defs}
def trait(p):
    x=re.sub(r'^(Picker_|DLC4_)','',p)
    m=re.match(r'Resist_(\w+?)_(Immune|Resistant|Vulnerable|MortalVulnerable)(_Perm)?$',x)
    cands=[x]
    if m:
        e,k=m.group(1),m.group(2); cands=[{'Immune':'Immune_','Resistant':'Resistant_','Vulnerable':'Vulnerable_','MortalVulnerable':'MortalVulnerable_'}[k]+e]
    m=re.match(r'WeakBy_(\w+)',x)
    if m: cands=['Weakened_'+m.group(1)]
    cands+=['Quirk_'+x,x.replace('_Perm',''),'Quirk_'+x.replace('_Perm','')]
    for c in cands:
        d=dnorm.get(norm(c))
        if d and defs[d][0]:
            t=ru.get(h397.h(defs[d][0]))
            if t: return re.sub(r'\{[^}]*\}','',t)
    for k in ('IntRes_'+x,'IntRes_Trait_'+x):
        if say(k): return say(k)
    return None
def report(sv):
    ids=[(m.start(),m.end(),m.group().decode()) for m in re.finditer(rb'[0-9a-f]{32}_NPC_\d+',sv)]
    out=[]
    prev_end=None
    for k,(s,e,nid) in enumerate(ids):
        lo=ids[k-1][1] if k else s-0x1000
        hi=ids[k+1][0] if k+1<len(ids) else e+0x2000
        st=[x for _,x in savetok.tok(sv,lo,s)]
        # state: last name token before id
        ni=max((i for i,x in enumerate(st) if x.startswith('T"') and i+2<len(st) and st[i+2].startswith('Faction_')),default=None)
        name=st[ni][2:-1] if ni is not None else '?'
        faction=st[ni+2] if ni is not None else ''
        ai=st[ni+3] if ni is not None else ''
        slot=st[ni+4] if ni is not None else ''
        d=[x for _,x in savetok.tok(sv,e,hi)]
        # def ends where next state starts: cut at 'InvasionFaction'/'Faction_' after a T"
        role=next((x for x in d if x.startswith('Role_')),None)
        tribe=next((x for x in d if x.startswith('TribeDef_')),None)
        markers=[x for x in d[:120] if 'Marker' in x and not x.startswith('#')]
        pick=[]
        for x in d:
            if x.startswith('Picker_') or (x.startswith('DLC4_') and len(pick)>0): pick.append(x)
            elif x.startswith('Traits_'): break
        lvl=[x for x in d[:12] if x.startswith('i')]
        title=say('Orc_Title_'+role[5:]) if role else None
        out.append(dict(id=nid,name=name,title=title,role=role,tribe=tribe,faction=faction,ai=ai,slot=slot,markers=markers,pickers=pick,head=d[:12]))
    return out
