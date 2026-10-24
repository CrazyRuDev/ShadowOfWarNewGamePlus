import sys,struct,re,collections
sys.path.insert(0,'/home/user/claude/ShadowOfWar-NGPlus'); import sowsave
sys.path.insert(1,'/tmp/claude-0/-home-user-claude/736d1654-7f66-5b6b-ac74-5dab6060c2ec/scratchpad/tools'); import secs,tok2,ivmg,h397
H=lambda s: struct.pack('<I',h397.h(s))
src=open('ngp/src.bin','rb').read(); pro=open('sav2/pro.bin','rb').read()

STORY_FAM={'Glaive','CBGameChanger','CBGameChanger_DarkTalion','CBMeter_DEFAULT','CBMeter_DarkTalion','DeathThreat',
 'DeathThreat_CalledShot','DeathThreat_SuperShame','SummonFollowers','Brand','DominateCaptains','SummonBodyguard',
 'SummonToughGrunts','ShadowStrike_Kill','ShadowStrike_KD','ShadowStrike_Chain','ShadowBrand','Raise','RhythmMovement_Jump',
 'RhythmMovement_DoubleJumping','ChargeMeterGrant','Counter_SC','HC_Crit_Threshold','Rhythm_Mov','RhythmMovement_ElvenClimbing',
 'Struggle_Crit','Wraith_Punch_2','WrathMeterGrant'}
def family(k):
    m=re.match(r'PS_(.+?)_(Parent|Child\d|UNLOCK|SKILL|DUMMY|NEWSKILL|Jump|Skill)',k)
    f=m.group(1) if m else k[3:]
    if k.startswith('PS_RhythmMovement_Jump'): f='RhythmMovement_Jump'
    if k.startswith('PS_RhythmMovement_DoubleJumping'): f='RhythmMovement_DoubleJumping'
    return f
def skill_ok(k): return k.startswith('PS_') and family(k) not in STORY_FAM

def blk(b,tag):
    return [(p,s) for t,v,p,s in secs.blocks(b,secs.sections(b)[0]) if t==tag][0]

# ---------- IVMG ----------
def stock_raw(b):
    p,s,T=ivmg.get(b); cap,ent,i=ivmg.stock(T)
    # raw bytes of each entry
    offs=[o for o,_ in T]
    out=[]
    for sl,ti,k,c,a,ids in ent:
        n=5+len(ids); out.append((k,c,a,ids,b[offs[ti]:offs[ti+n]]))
    return p,T,offs,ent,out,i
sp,sT,soffs,sent,sraw,send=stock_raw(src)
pp,pT,poffs,pent,praw,pend=stock_raw(pro)
srcmap={k:r for k,c,a,ids,r in sraw}
SWAP={'Talion_Isildur_Ring':'Talion_Celebrimbor_Ring','AD_Talion_Isildur_Ring':'AD_Talion_Celebrimbor_Ring'}
def swap(raw):
    for a,b in SWAP.items(): raw=raw.replace(H(a),H(b))
    return raw
ITEMKEEP=('Primary_','PrimSnipe_','PrimHam_','Runegem_','Has_')
new=[];kept=collections.Counter();seen=set()
# 1) pro entries: keep unless they hold item instance ids (pro items are dropped)
for k,c,a,ids,r in praw:
    if ids: continue
    if k in srcmap and (skill_ok(k) or k.startswith(ITEMKEEP) or k=='PC_Mirian'): r=srcmap[k]
    new.append(r); seen.add(k); kept['pro']+=1
# 2) src entries
for k,c,a,ids,r in sraw:
    if k in seen: continue
    if ids or skill_ok(k) or k.startswith(ITEMKEEP) or k=='PC_Mirian' or k in ('1Sword_Prestige','3Bow_Prestige','5Cape_Prestige','6Ring_Prestige'):
        new.append(swap(r)); seen.add(k); kept['src:'+(k.split('_')[0])]+=1
print('stock entries',len(new),dict(kept))
sS=[x for _,x in sT]
# blob: find 0x10 token
bt=next(i for i,x in enumerate(sS) if x.startswith('BLOB')); blob_start=soffs[bt]; blen=struct.unpack_from('<I',src,blob_start+1)[0]
blob_data_start=blob_start+5; blob_end=blob_data_start+blen
cap_tok=7
head=src[blob_data_start:soffs[cap_tok]]               # 05 pair + skin + nextid
captok=b'\x04'+struct.pack('<i',len(new))
rest=src[soffs[send]:blob_end]
rest=swap(rest)
newblob=head+captok+b''.join(new)+rest
# new IVMG content: pro prefix up to its blob, new blob, pro suffix after its blob
pS=[x for _,x in pT]; pbt=next(i for i,x in enumerate(pS) if x.startswith('BLOB')); pbs=poffs[pbt]
pblen=struct.unpack_from('<I',pro,pbs+1)[0]; pbe=pbs+5+pblen
P_ivmg,S_ivmg=blk(pro,'IVMG')
ivmg_content=pro[P_ivmg+20:pbs]+b'\x10'+struct.pack('<I',len(newblob))+newblob+pro[pbe:P_ivmg+16+S_ivmg]

# ---------- IVPD ----------
def ivpd_parse(b):
    p,s=blk(b,'IVPD'); T=tok2.tok(b,p+20,p+16+s); S=[x for _,x in T]; offs=[o for o,_ in T]+[p+16+s]
    n=int(S[2][1:]); pairs=[(S[3+2*i],b[offs[3+2*i]:offs[5+2*i]]) for i in range(n)]
    return p,s,b[p+20:offs[3]],pairs,b[offs[3+2*n]:p+16+s]
_,_,pre_head,ppairs,ptail=ivpd_parse(pro); _,_,_,spairs,_=ivpd_parse(src)
smap=dict(spairs); pk={k for k,_ in ppairs}
outp=[(k,smap[k] if (k in smap and skill_ok(k)) else r) for k,r in ppairs]
for k,r in spairs:
    if k not in pk and (skill_ok(k) or k.endswith('_Prestige_UNLOCK') or k.endswith('_Prestige_SKILL')): outp.append((k,r))
print('IVPD entries',len(ppairs),'->',len(outp))
hd=bytearray(pre_head); assert hd[-5]==4; struct.pack_into('<i',hd,len(hd)-4,len(outp))
ivpd_content=bytes(hd)+b''.join(r for _,r in outp)+ptail

# ---------- PPDC ----------
P_pp,S_pp=blk(src,'PPDC'); ppdc_src=src[P_pp+20:P_pp+16+S_pp]
pp_p,pp_s=blk(pro,'PPDC'); ppdc=bytearray(pro[pp_p+20:pp_p+16+pp_s])
# tokens: i3 SinglePlayer i<lvl-1> i<xp> ...
assert ppdc[:5]==b'\x04\x03\x00\x00\x00'
ppdc[10:20]=ppdc_src[10:20]
print('PPDC level/xp',struct.unpack_from('<i',ppdc,11)[0]+1,struct.unpack_from('<i',ppdc,16)[0])

# ---------- assemble ----------
def replace_block(b,tag,content):
    p,s=blk(b,tag); ver=struct.unpack_from('<I',b,p+4)[0]; sz=len(content)+4
    nb=bytearray(b[:p]+b[p:p+4]+struct.pack('<IIII',ver,sz,0,sz-4)+content+b[p+16+s:]); d=len(nb)-len(b)
    L=struct.unpack_from('<I',nb,0x15be)[0]+d; struct.pack_into('<I',nb,0x15be,L); struct.pack_into('<I',nb,0x1609,L-0x47)
    return bytes(nb),d
b=pro;tot=0
for tag,c in (('IVMG',ivmg_content),('IVPD',ivpd_content),('PPDC',bytes(ppdc))):
    b,d=replace_block(b,tag,c); tot+=d
b=bytearray(b)
struct.pack_into('<I',b,12,len(b)-0x14); struct.pack_into('<I',b,16,len(b)-0x14)
b=bytes(b)
# verify: walk all sections/blocks, tokenize IVMG/IVPD fully
for sec in secs.sections(b): secs.blocks(b,sec)
for tag in ('IVMG','IVPD','PPDC'):
    p,s=blk(b,tag); T=tok2.tok(b,p+20,p+16+s); bad=[x for _,x in T if x.startswith('?')]; assert not bad,(tag,bad[:5])
p2,s2,T2=ivmg.get(b); cap2,ent2,i2=ivmg.stock(T2); print('verify stock',cap2,len(ent2))
# слоты самоцветов пустые, как в прологе: иначе обучение вставке самоцвета в меч не завершается
sys.path.insert(0,'ngp'); import sockets
b,n=sockets.empty_sockets(b); print('sockets emptied',n)
open('ngp/ngplus.bin','wb').write(b)
print('size',hex(len(pro)),'->',hex(len(b)))
