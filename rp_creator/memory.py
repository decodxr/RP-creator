import json
import math
import re
from .db import uid, dumps


def visible(known_by, actor):
    known = json.loads(known_by) if isinstance(known_by,str) else known_by
    return actor == 'gm' or '*' in known or actor in known


def decode(row):
    result = dict(row)
    for key in ('known_by','entities','parents'):
        if key in result:
            result[key] = json.loads(result[key])
    result.pop('embedding',None)
    return result


def invalidate_dependents(db, mid):
    """Invalidate summaries when any original source changes."""
    db.execute('''WITH RECURSIVE descendants(id) AS (
        SELECT id FROM memories WHERE EXISTS(SELECT 1 FROM json_each(parents) WHERE value=?)
        UNION
        SELECT m.id FROM memories m JOIN descendants d
        ON EXISTS(SELECT 1 FROM json_each(m.parents) WHERE value=d.id)
    ) UPDATE memories SET valid=0,revision=revision+1 WHERE valid=1 AND id IN (SELECT id FROM descendants)''',(mid,))


def save_memory(db, campaign, kind, text, known_by, created, source, importance=5,
                entities=None, fact_key=None, evidence='', parents=None):
    known_by = sorted(set(known_by))
    existing = db.execute('SELECT id FROM memories WHERE campaign=? AND text=? AND known_by=? AND valid=1',
                          (campaign,text,dumps(known_by))).fetchone()
    if existing:
        return existing['id']
    # Different witnesses may retain contradictory beliefs; supersede only same audience.
    if fact_key:
        for row in db.execute('SELECT id FROM memories WHERE campaign=? AND fact_key=? AND known_by=? AND valid=1',
                              (campaign,fact_key,dumps(known_by))).fetchall():
            invalidate_dependents(db,row['id'])
        db.execute('UPDATE memories SET valid=0,revision=revision+1 WHERE campaign=? AND fact_key=? AND known_by=? AND valid=1',
                   (campaign,fact_key,dumps(known_by)))
    mid = uid()
    db.execute('''INSERT INTO memories(id,campaign,kind,text,known_by,entities,importance,created,
               fact_key,source,evidence,parents) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
               (mid,campaign,kind,text,dumps(known_by),dumps(entities or []),importance,created,fact_key,source,evidence,dumps(parents or [])))
    return mid


class MemoryEngine:
    def __init__(self, database):
        self.db = database

    def search(self, campaign, actor, query='', limit=12, query_vector=None, embedding_model=None, include_invalid=False):
        # SQL audience filter occurs before ranking or prompt construction.
        privacy = "(?='gm' OR EXISTS (SELECT 1 FROM json_each(m.known_by) WHERE value IN ('*',?)))"
        valid = '' if include_invalid else ' AND m.valid=1'
        base = f'SELECT m.* FROM memories m WHERE m.campaign=? AND {privacy}{valid}'
        params = (campaign,actor,actor)
        tokens = re.findall(r'\w+',query,flags=re.UNICODE)[:24]
        candidates = {}
        lexical = {}
        if tokens:
            match = ' OR '.join('"'+t+'"' for t in tokens)
            rows = self.db.rows(f"""SELECT m.*,bm25(memory_fts) AS lexical_rank FROM memory_fts
                JOIN memories m ON m.rowid=memory_fts.rowid WHERE m.campaign=? AND {privacy}{valid}
                AND memory_fts MATCH ? ORDER BY lexical_rank LIMIT 400""",params+(match,))
            for rank,row in enumerate(rows):
                lexical[row['id']] = 2 / (1+rank/25)
            candidates.update({r['id']:r for r in rows})
        recent = self.db.rows(base+' ORDER BY m.created DESC,m.rowid DESC LIMIT 80',params)
        important = self.db.rows(base+' ORDER BY m.importance DESC,m.created DESC LIMIT 40',params)
        candidates.update({r['id']:r for r in recent+important})
        semantic = {}
        if query_vector:
            # Exact cosine scan in batches: bounded RAM; disk storage grows with campaign.
            norm = math.sqrt(sum(x*x for x in query_vector)) or 1
            with self.db.connect() as conn:
                cursor = conn.execute(base+' AND m.embedding_model=? AND m.embedding IS NOT NULL',params+(embedding_model,))
                best = []
                while rows := cursor.fetchmany(256):
                    for raw in rows:
                        r = dict(raw)
                        v = json.loads(r['embedding'])
                        if len(v) != len(query_vector):
                            continue
                        sim = sum(a*b for a,b in zip(v,query_vector))/(norm*(math.sqrt(sum(x*x for x in v)) or 1))
                        best.append((sim,r))
                    best.sort(key=lambda x:x[0], reverse=True)
                    best = best[:60]
                for sim,r in best:
                    semantic[r['id']] = max(0,sim)*3
                    candidates[r['id']] = r
        ranked=[]
        for r in candidates.values():
            score = lexical.get(r['id'],0)+semantic.get(r['id'],0)+r['importance']/20
            if actor in json.loads(r['entities']):
                score += .15
            ranked.append((score,r))
        ranked.sort(key=lambda x:(x[0],x[1]['created']),reverse=True)
        return [dict(decode(r),score=round(score,3)) for score,r in ranked[:limit]]

    async def reindex(self, campaign, ai, batch=32):
        if not ai.s.embeddings:
            return {'indexed':0,'remaining':0,'message':'Ative embeddings nas configurações.'}
        rows = self.db.rows('SELECT id,text FROM memories WHERE campaign=? AND valid=1 AND (embedding_model IS NULL OR embedding_model!=?) LIMIT ?',
                            (campaign,ai.embedding_key,batch))
        vectors = await ai.embed([r['text'] for r in rows])
        with self.db.connect() as db:
            for row,vector in zip(rows,vectors):
                db.execute('UPDATE memories SET embedding=?,embedding_model=? WHERE id=? AND text=?',
                           (dumps(vector),ai.embedding_key,row['id'],row['text']))
        remaining = self.db.one('SELECT count(*) n FROM memories WHERE campaign=? AND valid=1 AND (embedding_model IS NULL OR embedding_model!=?)',(campaign,ai.embedding_key))['n']
        return {'indexed':len(vectors),'remaining':remaining}

    def consolidate(self,campaign,now):
        # Extractive summaries, grouped by identical audience: no secret laundering.
        rows = self.db.rows("SELECT * FROM memories WHERE campaign=? AND valid=1 AND kind NOT IN ('summary','derived') ORDER BY created,rowid",(campaign,))
        used=set()
        for r in self.db.rows("SELECT parents FROM memories WHERE campaign=? AND kind='summary' AND valid=1",(campaign,)):
            used.update(json.loads(r['parents']))
        groups={}
        for row in rows:
            if row['id'] not in used:
                groups.setdefault(row['known_by'],[]).append(row)
        made=[]
        with self.db.connect() as db:
            for known,items in groups.items():
                for start in range(0,len(items)-5,6):
                    batch=items[start:start+6]
                    text='Resumo extrativo (fontes preservadas):\n'+'\n'.join(f"• {r['text'][:220]}" for r in batch)
                    made.append(save_memory(db,campaign,'summary',text,json.loads(known),now,'consolidation',6,
                               parents=[r['id'] for r in batch]))
        return {'created':len(made),'ids':made}
