import json

def run(s):
    frames=[]
    def check(screen,cur=None,count=None):
        value=s.state()
        assert value['screen']==screen,('screen',value,screen)
        assert value['rows']==8 and len(value['labels'])==8
        assert 0<=value['cur']<value['count']
        assert value['physical']==value['cur']-value['top'] and 0<=value['physical']<8
        if cur is not None:assert value['cur']==cur,('cur',value,cur)
        if count is not None:assert value['count']==count,('count',value,count)
        for text in value['labels']:
            assert len(text.encode('ascii'))<=8
        first=value['count']-value['top']
        if first<8:
            assert value['labels'][first]=='--------'
            assert all(not text.strip() for text in value['labels'][first+1:])
        frames.append({key:value[key] for key in ['screen','cur','top','physical','count','slot','levels','armed','labels']})
        return value

    s.goto(0,0);before=check(0,0,10)
    s.press('UP');value=check(0,9,10)
    assert value['slot']==before['slot'] and value['levels']==before['levels']
    assert s.events[-1]['W']==0
    s.press('DOWN');value=check(0,0,10);assert value['slot']==1
    s.match(1,value['levels'])

    s.goto(0,2);s.press('DISP');s.goto(1,0);check(1,0,5)
    s.press('UP');check(1,4,5)
    s.press('DOWN');check(1,0,5)
    s.goto(1,1);s.press('DISP');s.goto(2,0);check(2,0,6)
    s.press('UP');check(2,5,6)
    s.press('DOWN');check(2,0,6)

    s.goto(2,1);s.press('DISP');check(3,None,19)
    s.goto(3,0);upper=check(3,0,19);assert upper['levels'][1]==9
    s.press('UP');value=check(3,0,19)
    assert value['levels']==upper['levels'] and s.events[-1]['W']==0
    assert '!' in value['labels'][value['physical']]
    s.goto(3,18);lower=check(3,18,19);assert lower['levels'][1]==-9
    s.press('DOWN');value=check(3,18,19)
    assert value['levels']==lower['levels'] and s.events[-1]['W']==0
    assert '!' in value['labels'][value['physical']]
    s.match(3,value['levels'])

    s.press('DISP');s.goto(2,0);s.press('DISP');s.goto(1,0);s.press('DISP')
    s.goto(0,9);s.press('DISP');s.goto(4,0);check(4,0,9)
    s.press('UP');check(4,8,9)
    s.press('DOWN');check(4,0,9)
    s.goto(4,1);s.press('DISP');s.goto(5,0);check(5,0,2)
    s.press('UP');check(5,1,2)
    s.press('DOWN');check(5,0,2)
    s.press('DISP');s.goto(4,0);s.press('DISP')
    s.goto(0,2);s.press('DISP');s.goto(1,4);s.press('DISP')
    value=check(1,4,5);assert value['armed']==1
    s.press('DOWN');value=check(1,0,5);assert value['armed']==0
    print(json.dumps({'menu_probe':'PASS','frames':frames,'events':len(s.events)}),flush=True)
