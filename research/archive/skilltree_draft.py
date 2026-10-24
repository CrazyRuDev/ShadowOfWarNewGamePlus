import sys,re,struct,collections; sys.path.insert(0,'/tmp/claude-0/-home-user-claude/736d1654-7f66-5b6b-ac74-5dab6060c2ec/scratchpad/tools'); import gdb,gdbrec
C=gdbrec.load(); D=gdb.D
cat={c['name']:c for c in C}
base=cat['Interface/Menu/MenuTreeBase']; nodes=cat['Interface/Menu/MenuTreeNode/Skills']; child=cat['Interface/Menu/MenuTreeNode/SkillChild']; pss=cat['Inventory/Skill/Skills']
def fields(c,k,maxn=0x400):
    recs=c['recs']; p=recs[k][0]; end=recs[k+1][0] if k+1<len(recs) else p+maxn
    if end<p or end-p>0x2000: end=p+maxn
    return struct.unpack_from('<%dI'%((end-p)//4),D,p)
def refs(c,k,G,dst): return [dst['recs'][x&0xfffff][1] for x in fields(c,k)[3:] if x>>20==G and (x&0xfffff)<len(dst['recs'])]
ROWS=[('SkillRow1_Sword','Бой'),('SkillRow2_Dagger','Разбой'),('SkillRow3_Bow','Дальний бой'),('SkillRow4_Armor','Призрак'),('SkillRow5_Cape','Наездник'),('SkillRow6_RingWraith','История')]
bi={n:k for k,(p,n) in enumerate(base['recs'])}; ni={n:k for k,(p,n) in enumerate(nodes['recs'])}; ci={n:k for k,(p,n) in enumerate(child['recs'])}
tree=[]
for rn,title in ROWS:
    row=[]
    for nn in refs(base,bi[rn],1428,nodes):
        k=ni[nn]; parent=refs(nodes,k,947,pss)[:1]; kids=[]
        for cn in refs(nodes,k,320,child):
            kids+=refs(child,ci[cn],947,pss)[:1]
        row.append((nn,parent,kids))
    tree.append((title,row))
if __name__=='__main__':
    for t,row in tree:
        print('==',t,sum(len(p)+len(k) for _,p,k in row))
        for nn,p,k in row: print('  ',nn,p,k)
OVR={'PSS_ShadowStrike_Grab_Child3':'PS_ShadowGrab_Child3_UNLOCK','PSS_ShadowStrike_Child3_ShadowBrand':'PS_ShadowStrike_Kill_Child3_ShadowBrand_UNLOCK',
 'PSS_RhythmMovent_NoDbleJump_Parent':'PS_StealthSprint_Parent_UNLOCK','PSS_Execution_Child1':'PS_Execution_Child1_WraithExecution_UNLOCK',
 'PSS_BrutalStrike_Child2_ChunkMeter':'PS_BrutalStrike_C2_ChunkMeter_UNLOCK','PSS_SStoFirePit_Parent':'PS_SStoFirePits_Parent_UNLOCK',
 'PSS_SStoFirePit_Child1':'PS_SStoFirePits_Child1_Ghuls_UNLOCK','PSS_SStoFirePit_Child2':'PS_SStoFirePits_Child2_Spiders_UNLOCK',
 'PSS_SStoFirePit_Child3':'PS_SStoFirePits_Child3_Poison_UNLOCK','PSS_Brand_Parent_Drain_C1':'PS_Brand_UNLOCK',
 'PSS_CBMeter_Parent':'PS_CBMeter_DEFAULT_UNLOCK','PSS_CBMeter_DarkTalion_Parent':'PS_CBMeter_DarkTalion_DEFAULT_UNLOCK'}
ITEMS=set(n for p,n in cat['Inventory/Items']['recs'] if n.startswith('PS_') and n.endswith('_UNLOCK'))
def ps_of(s):
    if s in OVR: return OVR[s]
    c=s[4:]; c2=re.sub(r'_C(\d)$',r'_Child\1',c.replace('RhythmMovent','RhythmMovement').replace('PoisonBarrel_','PoisonBarrels_'))
    for x in (c,c2,re.sub(r'_Parent$','',c2)):
        if 'PS_%s_UNLOCK'%x in ITEMS: return 'PS_%s_UNLOCK'%x
def layout():
    """[(row title, [(node, parent PS key, [child PS keys])])]"""
    return [(t,[(nn,ps_of(p[0]) if p else None,[ps_of(k) for k in kids]) for nn,p,kids in row]) for t,row in tree]
