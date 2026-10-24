import sys,struct,re
sys.path.insert(0,'/home/user/claude/ShadowOfWar-NGPlus'); import sowsave
sys.path.insert(1,'/tmp/claude-0/-home-user-claude/736d1654-7f66-5b6b-ac74-5dab6060c2ec/scratchpad/tools'); import ivmg,secs,tok2,h397
SOCK=['Socket_4Armor','Socket_2Dagger','Socket_3Bow','Socket_6Ring','Socket_5Cape','Socket_Hammer','Socket_1Sword','Socket_Weapon']
def empty_sockets(b):
    p,s,T=ivmg.get(b); S=[x for _,x in T]; O=[o for o,_ in T]
    bt=next(i for i,x in enumerate(S) if x.startswith('BLOB')); bs=O[bt]
    i=max(k for k,x in enumerate(S) if x=='Socket_4Armor' and S[k-2:k]==['bc1','i8'])
    assert S[i-2:i]==['bc1','i8'],S[i-3:i]
    out=bytearray(); k=i; n=0
    for _ in range(8):
        name=S[k]; assert name in SOCK,(name)
        if S[k+1]=='bc1':
            assert S[k+2]==name and S[k+3].startswith('Runegem'); out+=b[O[k]:O[k+1]]+b'\x0c\x00'; k+=4; n+=1
        else: out+=b[O[k]:O[k+2]]; k+=2
    start,end=O[i],O[k]
    d=len(out)-(end-start)
    nb=bytearray(b[:start]+out+b[end:])
    struct.pack_into('<I',nb,bs+1,struct.unpack_from('<I',nb,bs+1)[0]+d)
    struct.pack_into('<I',nb,p+8,s+d); struct.pack_into('<I',nb,p+16,s+d-4)
    L=struct.unpack_from('<I',nb,0x15be)[0]+d; struct.pack_into('<I',nb,0x15be,L); struct.pack_into('<I',nb,0x1609,L-0x47)
    struct.pack_into('<I',nb,12,len(nb)-0x14); struct.pack_into('<I',nb,16,len(nb)-0x14)
    nb=bytes(nb)
    for sec in secs.sections(nb): secs.blocks(nb,sec)
    p2,s2,T2=ivmg.get(nb); assert not [x for _,x in T2 if x.startswith('?')]
    return nb,n
if __name__=='__main__':
    b=open(sys.argv[1],'rb').read(); nb,n=empty_sockets(b); open(sys.argv[2],'wb').write(nb); print('emptied',n)
