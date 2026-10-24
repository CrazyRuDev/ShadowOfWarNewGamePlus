import sys; sys.path.insert(0,'/tmp/claude-0/-home-user-claude/736d1654-7f66-5b6b-ac74-5dab6060c2ec/scratchpad/tools'); import secs,tok2
def get(b):
    p,s=[(p,s) for t,v,p,s in secs.blocks(b,secs.sections(b)[0]) if t=='IVMG'][0]
    return p,s,tok2.tok(b,p+20,p+16+s)
def stock(T):
    S=[x for _,x in T]; cap=int(S[7][1:]); i=8; ent=[]; slot=0
    while slot<cap:
        if S[i]=='bc0': i+=1; slot+=1; continue
        assert S[i]=='bc1',(i,S[i:i+6])
        n=int(S[i+4][1:]); ids=[int(x[1:]) for x in S[i+5:i+5+n]]
        ent.append((slot,i,S[i+1],int(S[i+2][1:]),int(S[i+3][1:]),ids)); i+=5+n
        slot+=1
    return cap,ent,i
