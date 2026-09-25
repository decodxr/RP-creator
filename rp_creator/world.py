import json
import time
from datetime import datetime,timedelta
from .db import uid,dumps
from .memory import save_memory,visible
from .models import CampaignInput,NPCInput

METRICS = ['trust','friendship','respect','fear','anger','affection','attraction','loyalty','suspicion']


def event(db,cid,now,kind,text,known,entities=None):
    eid=uid()
    db.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?)',(eid,cid,now,kind,text,dumps(sorted(set(known))),dumps(entities or [])))
    return eid


def relationship(db,cid,source,target,metric,delta):
    row=db.execute('SELECT values_json FROM relationships WHERE campaign=? AND source=? AND target=?',(cid,source,target)).fetchone()
    values=json.loads(row['values_json']) if row else {k:0 for k in METRICS}
    values[metric]=max(-100,min(100,values.get(metric,0)+delta))
    db.execute('INSERT OR REPLACE INTO relationships VALUES (?,?,?,?)',(cid,source,target,dumps(values)))
    return values


class World:
    def __init__(self,database):
        self.db=database

    def require(self,cid):
        row=self.db.one('SELECT * FROM campaigns WHERE id=?',(cid,))
        if not row:
            raise ValueError('Campanha não encontrada.')
        return row

    def create(self,data:CampaignInput):
        cid=uid()
        locs=[(uid(),'Praça','O coração de Vila Aurora. Bancos à sombra, um café e caminhos que se cruzam.'),
              (uid(),'Biblioteca','Livros antigos, mesas de estudo e histórias à meia-voz.'),
              (uid(),'Parque','Uma trilha entre árvores, um lago e um pequeno mirante.'),
              (uid(),'Casa','Um lugar tranquilo para descansar e planejar o dia.')]
        now='2026-09-25T09:00:00'
        with self.db.connect() as db:
            db.execute('INSERT INTO campaigns(id,name,premise,player_name,player_profile,time,location,last_wall) VALUES (?,?,?,?,?,?,?,?)',
                (cid,data.name,data.premise,data.player_name,data.player_profile,now,locs[0][0],time.time()))
            for lid,name,desc in locs:
                db.execute('INSERT INTO locations VALUES (?,?,?,?)',(lid,cid,name,desc))
            event(db,cid,now,'begin','Um novo capítulo começa em Vila Aurora.',['*'])
        if data.seed:
            sara=self.add_npc(cid,NPCInput(name='Sara',profile='24 anos. Curiosa, extrovertida e brincalhona. Valoriza honestidade e amizade. Gosta de música e jogos. Trabalha na biblioteca.',location=locs[0][0],
                routine=[{'hour':8,'location':locs[0][0],'activity':'toma café na praça'},
                         {'hour':10,'location':locs[1][0],'activity':'organiza os livros'},
                         {'hour':15,'location':locs[2][0],'activity':'caminha no parque'},
                         {'hour':19,'location':locs[3][0],'activity':'descansa em casa'}],goals=['Organizar um clube de leitura']))
            alex=self.add_npc(cid,NPCInput(name='Alex',profile='26 anos. Reservado, leal e observador. Fotógrafo, gosta de trilhas. Não confia facilmente em desconhecidos.',location=locs[2][0],
                routine=[{'hour':7,'location':locs[2][0],'activity':'fotografa a natureza'},{'hour':12,'location':locs[0][0],'activity':'almoça na praça'},{'hour':20,'location':locs[3][0],'activity':'revisa suas fotos'}],goals=['Preparar uma exposição de fotografias']))
            with self.db.connect() as db:
                relationship(db,cid,sara,alex,'trust',25)
                relationship(db,cid,alex,sara,'friendship',20)
                save_memory(db,cid,'secret','Sara está preparando uma festa surpresa para Alex.',[sara],now,'seed',8,[sara,alex])
                save_memory(db,cid,'semantic','Sara trabalha na biblioteca e gosta de jogos.',['*'],now,'seed',5,[sara])
        return self.require(cid)

    def add_npc(self,cid,data:NPCInput,nid=None):
        self.require(cid)
        ids={r['id'] for r in self.db.rows('SELECT id FROM locations WHERE campaign=?',(cid,))}
        if data.location not in ids or any(r.location not in ids for r in data.routine):
            raise ValueError('Local da rotina não pertence a esta campanha.')
        if len({r.hour for r in data.routine})!=len(data.routine):
            raise ValueError('Use apenas uma atividade por horário.')
        nid=nid or uid()
        values=(data.name,data.profile,data.mood,data.location,dumps([r.model_dump() for r in sorted(data.routine,key=lambda x:x.hour)]),dumps(data.goals))
        with self.db.connect() as db:
            if db.execute('SELECT id FROM npcs WHERE id=? AND campaign=?',(nid,cid)).fetchone():
                db.execute('UPDATE npcs SET name=?,profile=?,mood=?,location=?,routine=?,goals=? WHERE id=?',values+(nid,))
            else:
                db.execute('INSERT INTO npcs(id,campaign,name,profile,mood,location,routine,goals) VALUES (?,?,?,?,?,?,?,?)',(nid,cid)+values)
            db.execute('UPDATE campaigns SET version=version+1 WHERE id=?',(cid,))
        return nid

    def snapshot(self,cid,gm=False):
        c=self.require(cid)
        npcs=self.db.rows('SELECT * FROM npcs WHERE campaign=? ORDER BY name',(cid,))
        for n in npcs:
            n['routine']=json.loads(n['routine']); n['goals']=json.loads(n['goals'])
        events=self.db.rows('SELECT * FROM events WHERE campaign=? ORDER BY time DESC,rowid DESC LIMIT 200',(cid,))
        events=[dict(e,known_by=json.loads(e['known_by']),entities=json.loads(e['entities'])) for e in events if visible(e['known_by'],'gm' if gm else 'player')]
        relations=self.db.rows('SELECT * FROM relationships WHERE campaign=?',(cid,))
        for r in relations:
            r['values']=json.loads(r.pop('values_json'))
        return {'campaign':c,'locations':self.db.rows('SELECT * FROM locations WHERE campaign=?',(cid,)),
                'npcs':npcs,'events':events,'relationships':relations if gm else [],
                'promises':self.db.rows('SELECT * FROM promises WHERE campaign=? ORDER BY due DESC LIMIT 100',(cid,)),
                'memory_count':self.db.one("SELECT count(*) n FROM memories WHERE campaign=? AND valid=1 AND (?=1 OR EXISTS(SELECT 1 FROM json_each(known_by) WHERE value IN ('*','player')))",(cid,int(gm)))['n']}

    def move(self,cid,lid):
        c=self.require(cid)
        loc=self.db.one('SELECT * FROM locations WHERE id=? AND campaign=?',(lid,cid))
        if not loc:
            raise ValueError('Local não encontrado.')
        with self.db.connect() as db:
            db.execute('UPDATE campaigns SET location=?,version=version+1 WHERE id=?',(lid,cid))
            witnesses=[r['id'] for r in db.execute('SELECT id FROM npcs WHERE campaign=? AND location=?',(cid,lid))]
            eid=event(db,cid,c['time'],'travel',f"{c['player_name']} chegou a {loc['name']}.",['player']+witnesses,[lid])
            save_memory(db,cid,'episodic',f"{c['player_name']} chegou a {loc['name']}.",['player']+witnesses,c['time'],eid,3,[lid]+witnesses)
            self._promises(db,cid,c['time'])
        return loc

    def advance(self,cid,minutes):
        c=self.require(cid)
        start=datetime.fromisoformat(c['time'])
        end=start+timedelta(minutes=minutes)
        cursor=start
        with self.db.connect() as db:
            # Visit each hourly boundary and each promise deadline, even in large skips.
            boundaries=set()
            hour=start.replace(minute=0,second=0,microsecond=0)+timedelta(hours=1)
            while hour<=end:
                boundaries.add(hour); hour+=timedelta(hours=1)
            for row in db.execute("SELECT due FROM promises WHERE campaign=? AND status='pending'",(cid,)):
                due=datetime.fromisoformat(row['due'])
                if start<due<=end: boundaries.add(due)
                late=due+timedelta(minutes=61)
                if start<late<=end: boundaries.add(late)
            boundaries.add(end)
            for cursor in sorted(boundaries):
                now=cursor.isoformat(timespec='seconds')
                db.execute('UPDATE campaigns SET time=? WHERE id=?',(now,cid))
                if cursor.minute==0:
                    self._routines(db,cid,cursor)
                self._promises(db,cid,now)
            db.execute('UPDATE campaigns SET version=version+1,last_wall=? WHERE id=?',(time.time(),cid))
        return self.require(cid)

    def _routines(self,db,cid,clock):
        now=clock.isoformat(timespec='seconds')
        npcs=list(db.execute('SELECT * FROM npcs WHERE campaign=?',(cid,)))
        c=dict(db.execute('SELECT * FROM campaigns WHERE id=?',(cid,)).fetchone())
        for n in npcs:
            for step in json.loads(n['routine']):
                if step['hour']!=clock.hour: continue
                db.execute('UPDATE npcs SET location=? WHERE id=?',(step['location'],n['id']))
                loc=db.execute('SELECT name FROM locations WHERE id=?',(step['location'],)).fetchone()['name']
                known=[n['id']]+(['player'] if c['location']==step['location'] else [])
                text=f"{n['name']} {step['activity']} em {loc}."
                eid=event(db,cid,now,'routine',text,known,[n['id'],step['location']])
                save_memory(db,cid,'temporal',text,known,now,eid,3,[n['id'],step['location']])
        # Co-location produces shared encounters once per pair per day.
        current=list(db.execute('SELECT * FROM npcs WHERE campaign=? ORDER BY id',(cid,)))
        for i,a in enumerate(current):
            for b in current[i+1:]:
                if a['location']!=b['location']: continue
                key=f"{a['id']}:{b['id']}:{clock.date()}"
                if db.execute("SELECT 1 FROM events WHERE campaign=? AND kind=?",(cid,key)).fetchone(): continue
                known=[a['id'],b['id']]+(['player'] if c['location']==a['location'] else [])
                text=f"{a['name']} e {b['name']} se encontraram e conversaram."
                eid=event(db,cid,now,key,text,known,[a['id'],b['id']])
                save_memory(db,cid,'social',text,known,now,eid,5,[a['id'],b['id']])
                relationship(db,cid,a['id'],b['id'],'friendship',1)
                relationship(db,cid,b['id'],a['id'],'friendship',1)
        if clock.hour==18:
            for n in current:
                goals=json.loads(n['goals'])
                if not goals: continue
                goal=goals[clock.toordinal()%len(goals)]
                known=[n['id']]+(['player'] if c['location']==n['location'] else [])
                text=f"{n['name']} dedicou tempo ao objetivo: {goal}."
                eid=event(db,cid,now,'goal',text,known,[n['id']])
                save_memory(db,cid,'episodic',text,known,now,eid,5,[n['id']])

    def _promises(self,db,cid,now):
        c=db.execute('SELECT * FROM campaigns WHERE id=?',(cid,)).fetchone()
        for p in list(db.execute("SELECT * FROM promises WHERE campaign=? AND status='pending'",(cid,))):
            due=datetime.fromisoformat(p['due']); clock=datetime.fromisoformat(now)
            n=db.execute('SELECT * FROM npcs WHERE id=?',(p['npc'],)).fetchone()
            within=due<=clock<=due+timedelta(minutes=60)
            # The scheduled meeting temporarily takes precedence over the NPC routine.
            if within and n['location']!=p['location']:
                db.execute('UPDATE npcs SET location=? WHERE id=?',(p['location'],p['npc']))
                known=[p['npc']]+(['player'] if c['location']==p['location'] else [])
                event(db,cid,now,'appointment',f"{n['name']} chegou ao local do encontro combinado.",known,[p['npc'],p['location']])
                n=dict(n);n['location']=p['location']
            fulfilled=within and c['location']==p['location'] and n['location']==p['location']
            missed=clock>due+timedelta(minutes=60)
            if not fulfilled and not missed: continue
            status='fulfilled' if fulfilled else 'missed'
            db.execute('UPDATE promises SET status=? WHERE id=?',(status,p['id']))
            text=f"Encontro {'cumprido' if fulfilled else 'perdido'}: {p['text']}"
            eid=event(db,cid,now,'promise',text,['player',p['npc']],[p['npc'],p['location']])
            save_memory(db,cid,'promise',text,['player',p['npc']],now,eid,9,[p['npc']],fact_key='promise:'+p['id'])
            values=relationship(db,cid,p['npc'],'player','trust',5 if fulfilled else -8)
            db.execute('UPDATE npcs SET mood=? WHERE id=?',('contente' if fulfilled else 'decepcionado',p['npc']))
            save_memory(db,cid,'derived',f"Após o encontro, {n['name']} {'ganhou' if fulfilled else 'perdeu'} confiança no jogador (índice {values['trust']}).",[p['npc'],'player'],now,eid,7,[p['npc']])
