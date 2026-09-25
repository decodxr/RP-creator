"""Readable Obsidian projection with explicit, conflict-checked memory import."""
import hashlib
import json
from pathlib import Path
from .db import dumps
from .memory import save_memory,invalidate_dependents
from .models import MemoryInput


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def note(meta,text):
    # JSON is a valid YAML flow mapping; also avoids requiring a YAML parser.
    return '---\n'+json.dumps(meta,ensure_ascii=False,indent=2)+'\n---\n\n'+text.rstrip()+'\n'


def parse_note(text):
    if not text.startswith('---\n'):
        raise ValueError('Nota precisa do cabeçalho JSON entre --- conforme o modelo exportado.')
    head,body=text[4:].split('\n---\n',1)
    return json.loads(head),body.strip()


class Vault:
    def __init__(self,database):
        self.db=database
        self.root=database.root/'vault'
        self.root.mkdir(exist_ok=True)

    def _safe(self,path):
        p=self.root/path
        if not p.resolve().is_relative_to(self.root.resolve()) or any(part.is_symlink() for part in [p,*p.parents] if part!=self.root.parent):
            raise ValueError('Caminho ou link simbólico não permitido no vault.')
        return p

    def export(self,cid):
        c=self.db.one('SELECT * FROM campaigns WHERE id=?',(cid,))
        if not c: raise ValueError('Campanha não encontrada.')
        written=0; conflicts=[]
        def write(relative,content,mid=None,revision=None):
            nonlocal written
            path=f'{cid}/{relative}'; p=self._safe(path)
            old=self.db.one('SELECT * FROM vault_files WHERE path=?',(path,))
            if p.exists():
                current=p.read_text(encoding='utf-8')
                if digest(current)==digest(content): return
                if not old or digest(current)!=old['hash']:
                    conflicts.append(path); return
            p.parent.mkdir(parents=True,exist_ok=True)
            tmp=p.with_suffix('.tmp'); tmp.write_text(content,encoding='utf-8'); tmp.replace(p)
            with self.db.connect() as db:
                db.execute('INSERT OR REPLACE INTO vault_files VALUES (?,?,?,?)',(path,digest(content),mid,revision))
            written+=1
        npcs=self.db.rows('SELECT * FROM npcs WHERE campaign=?',(cid,))
        locations=self.db.rows('SELECT * FROM locations WHERE campaign=?',(cid,))
        links={n['id']:f"[[{n['id']}|{n['name']}]]" for n in npcs+locations}
        write('World.md',f"# {c['name']}\n\n{c['premise']}\n\nData: {c['time']}\n\n"+'\n'.join(links.values())+'\n\n[[Profile|Jogador]]\n\nMemórias em Memories/. Edite o corpo da nota e importe pela interface.\n')
        write('Player/Profile.md',f"# {c['player_name']}\n\n{c['player_profile']}\n\nLocal: {links.get(c['location'],'')}\n")
        relations=self.db.rows('SELECT * FROM relationships WHERE campaign=?',(cid,))
        write('Player/Relationships.md','# Relações (visão do criador)\n\n'+'\n'.join(f"{links.get(r['source'],r['source'])} → {links.get(r['target'],r['target'])}: {r['values_json']}" for r in relations))
        for n in npcs:
            body=f"# {n['name']}\n\n{n['profile']}\n\nHumor: {n['mood']}\n\nLocal: {links.get(n['location'],'')}\n\n## Objetivos\n"+'\n'.join('- '+g for g in json.loads(n['goals']))
            body+='\n\n## Rotina\n'+'\n'.join(f"- {s['hour']:02}:00 — {links.get(s['location'],'')}: {s['activity']}" for s in json.loads(n['routine']))
            write(f"Characters/{n['id']}.md",body)
        for l in locations:
            write(f"Locations/{l['id']}.md",f"# {l['name']}\n\n{l['description']}\n")
        for m in self.db.rows('SELECT * FROM memories WHERE campaign=?',(cid,)):
            meta={k:m[k] for k in ('id','campaign','kind','importance','created','valid','fact_key','source','revision')}
            for k in ('known_by','entities','parents'): meta[k]=json.loads(m[k])
            body=m['text']+'\n\n<!-- rp-links -->\n'+' '.join(links[x] for x in meta['entities'] if x in links)
            write(f"Memories/{m['id']}.md",note(meta,body),m['id'],m['revision'])
        for e in self.db.rows('SELECT * FROM events WHERE campaign=?',(cid,)):
            write(f"Events/{e['id']}.md",note({'time':e['time'],'known_by':json.loads(e['known_by'])},e['text']+'\n\n'+' '.join(links.get(x,x) for x in json.loads(e['entities']))))
        return {'written':written,'conflicts':conflicts,'path':str(self.root/cid)}

    def import_memories(self,cid):
        folder=self._safe(f'{cid}/Memories')
        c=self.db.one('SELECT time FROM campaigns WHERE id=?',(cid,))
        if not c: raise ValueError('Campanha não encontrada.')
        actors={'player','*'}|{r['id'] for r in self.db.rows('SELECT id FROM npcs WHERE campaign=?',(cid,))}
        imported=[]; errors=[]
        if not folder.exists(): return {'imported':[],'errors':[]}
        for file in sorted(folder.glob('*.md')):
            try:
                p=self._safe(file.relative_to(self.root)); path=str(p.relative_to(self.root))
                if p.stat().st_size>64000: raise ValueError('Nota excede 64 KB.')
                content=p.read_text(encoding='utf-8')
                tracked=self.db.one('SELECT * FROM vault_files WHERE path=?',(path,))
                if tracked and digest(content)==tracked['hash']: continue
                meta,body=parse_note(content)
                body=body.split('<!-- rp-links -->')[0].strip()
                m=MemoryInput.model_validate({k:meta[k] for k in ('kind','known_by','entities','importance','fact_key') if k in meta}|{'text':body})
                if not set(m.known_by)<=actors: raise ValueError('Conhecedor inexistente nesta campanha.')
                if m.kind=='secret' and '*' in m.known_by: raise ValueError('Segredo não pode ter audiência pública.')
                if meta.get('campaign',cid)!=cid: raise ValueError('Nota pertence a outra campanha.')
                valid=meta.get('valid',1)
                if valid not in (0,1): raise ValueError('valid deve ser 0 ou 1.')
                with self.db.connect() as db:
                    if tracked and tracked['memory_id']:
                        old=db.execute('SELECT * FROM memories WHERE id=? AND campaign=?',(tracked['memory_id'],cid)).fetchone()
                        if not old or old['revision']!=tracked['revision'] or meta.get('revision')!=tracked['revision']:
                            raise ValueError('Conflito: memória também mudou no banco. Preserve sua edição e compare com a interface.')
                        if meta.get('id')!=old['id']: raise ValueError('Não altere o ID da nota.')
                        mid=old['id']
                        invalidate_dependents(db,mid)
                        db.execute('''UPDATE memories SET text=?,kind=?,known_by=?,entities=?,importance=?,fact_key=?,valid=?,
                                   embedding=NULL,embedding_model=NULL,revision=revision+1 WHERE id=?''',
                                   (m.text,m.kind,dumps(sorted(set(m.known_by))),dumps(m.entities),m.importance,m.fact_key,valid,mid))
                        revision=old['revision']+1
                    else:
                        if meta.get('id'): raise ValueError('Para criar nova memória, remova id e revision do cabeçalho.')
                        mid=save_memory(db,cid,m.kind,m.text,m.known_by,c['time'],'obsidian',m.importance,m.entities,m.fact_key)
                        revision=1
                    # Keep tracking current bytes; next export writes new revision header.
                    db.execute('INSERT OR REPLACE INTO vault_files VALUES (?,?,?,?)',(path,digest(content),mid,revision))
                    db.execute('UPDATE campaigns SET version=version+1 WHERE id=?',(cid,))
                imported.append(mid)
                # New files adopt canonical identity; avoid importing twice under arbitrary name.
                if p.name!=mid+'.md':
                    canonical=p.with_name(mid+'.md')
                    if canonical.exists(): raise ValueError('Nome canônico já existe; revise a nota duplicada.')
                    p.rename(canonical)
                    with self.db.connect() as db:
                        db.execute('UPDATE vault_files SET path=? WHERE path=?',(str(canonical.relative_to(self.root)),path))
            except (ValueError,KeyError,TypeError,OSError) as exc:
                errors.append({'file':file.name,'error':str(exc)})
        self.export(cid)
        return {'imported':imported,'errors':errors}
