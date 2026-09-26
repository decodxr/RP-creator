import asyncio
import io
import json
import os
import secrets
import sqlite3
import time
import tempfile
import logging
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import FastAPI,HTTPException,Request,Query
from fastapi.responses import FileResponse,JSONResponse,Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel,Field
from .db import Database,uid,dumps
from .engine import Engine
from .ai import AIError
from .models import AISettings,CampaignInput,LocationInput,NPCInput,ChatInput,MemoryInput,CharacterPromptInput,NPCWithMemoriesInput
from .memory import visible,decode,save_memory,invalidate_dependents
from .world import event


class Advance(BaseModel):
    minutes: int = Field(ge=1,le=10080)


class Move(BaseModel):
    location: str


class Clock(BaseModel):
    enabled: bool
    rate: float = Field(default=1,ge=.1,le=60)


class Profile(BaseModel):
    name: str = Field(min_length=1,max_length=80)
    profile: str = Field(max_length=4000)


def create_app(root=None,testing=False):
    database=Database(root or os.environ.get('RP_DATA_DIR','data'))
    engine=Engine(database); token=secrets.token_urlsafe(32)

    async def ticker():
        while True:
            await asyncio.sleep(5)
            for c in database.rows('SELECT * FROM campaigns WHERE realtime=1'):
                try:
                    if engine.lock(c['id']).locked(): continue
                    async with engine.lock(c['id']):
                        # At most one week per iteration. Unprocessed elapsed time remains as backlog.
                        current=engine.world.require(c['id'])
                        minutes=min(10080,int((time.time()-current['last_wall'])*current['rate']/60))
                        if minutes>0:
                            engine.world.advance(c['id'],minutes)
                            with database.connect() as db:
                                db.execute('UPDATE campaigns SET last_wall=? WHERE id=?',(current['last_wall']+minutes*60/current['rate'],c['id']))
                            engine.vault.export(c['id'])
                except Exception:
                    logging.getLogger('rp_creator.clock').exception('Falha ao processar relógio da campanha %s',c['id'])

    @asynccontextmanager
    async def lifespan(app):
        task=asyncio.create_task(ticker())
        yield
        task.cancel()
        try: await task
        except asyncio.CancelledError: pass

    app=FastAPI(title='RP creator',version='1.0.0',lifespan=lifespan)
    app.state.engine=engine
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=['localhost','127.0.0.1','[::1]']+(['testserver'] if testing else []))

    @app.middleware('http')
    async def local_security(request:Request,call_next):
        origin=request.headers.get('origin')
        if origin and urlsplit(origin).netloc!=request.headers.get('host'):
            return JSONResponse({'detail':'Origem não autorizada.'},403)
        if request.method in ('POST','PUT','PATCH','DELETE'):
            if not secrets.compare_digest(request.headers.get('x-rp-token',''),token):
                return JSONResponse({'detail':'Sessão expirada. Atualize a página.'},403)
            try:
                if int(request.headers.get('content-length','0'))>131072:
                    return JSONResponse({'detail':'Requisição muito grande.'},413)
            except ValueError:
                return JSONResponse({'detail':'Tamanho inválido.'},400)
            body=await request.body()
            if len(body)>131072: return JSONResponse({'detail':'Requisição muito grande.'},413)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['Cache-Control']='no-store'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response

    @app.exception_handler(ValueError)
    async def value_error(request,exc): return JSONResponse({'detail':str(exc)},400)

    @app.exception_handler(sqlite3.IntegrityError)
    async def integrity_error(request,exc): return JSONResponse({'detail':'Já existe um registro com esse nome, ou a referência é inválida.'},409)

    @app.exception_handler(AIError)
    async def ai_error(request,exc): return JSONResponse({'detail':str(exc)},502)

    @app.get('/api/session')
    async def session(): return {'token':token,'version':'1.0.0'}

    @app.get('/api/health')
    async def health(): return {'ok':True,'app':'RP creator'}

    @app.get('/api/settings')
    async def settings():
        s=engine.client().s.model_dump(); s['has_api_key']=bool(s.pop('api_key'))
        return s

    @app.put('/api/settings')
    async def update_settings(data:AISettings):
        values=data.model_dump()
        if data.api_key=='__KEEP__': values['api_key']=database.setting('ai',{}).get('api_key','')
        database.set_setting('ai',values)
        return {'saved':True}

    @app.post('/api/settings/test')
    async def test_connection():
        ai=engine.client()
        if ai.s.provider=='demo': return {'ok':True,'message':'Modo demonstração ativo. Nenhum modelo foi chamado.'}
        result=await ai.complete([{'role':'user','content':'Responda apenas: conexão funcionando.'}])
        return {'ok':True,'message':result[:300]}

    @app.get('/api/campaigns')
    async def campaigns(): return database.rows('SELECT * FROM campaigns ORDER BY rowid DESC')

    @app.post('/api/campaigns')
    async def create_campaign(data:CampaignInput):
        c=engine.world.create(data); engine.vault.export(c['id']); return c

    @app.get('/api/campaigns/{cid}')
    async def snapshot(cid:str,gm:bool=False): return engine.world.snapshot(cid,gm)

    @app.put('/api/campaigns/{cid}/player')
    async def profile(cid:str,data:Profile):
        async with engine.lock(cid):
            engine.world.require(cid)
            with database.connect() as db:
                db.execute('UPDATE campaigns SET player_name=?,player_profile=?,version=version+1 WHERE id=?',(data.name,data.profile,cid))
            engine.vault.export(cid)
            return {'saved':True}

    @app.post('/api/campaigns/{cid}/locations')
    async def add_location(cid:str,data:LocationInput):
        async with engine.lock(cid):
            engine.world.require(cid); lid=uid()
            with database.connect() as db:
                db.execute('INSERT INTO locations VALUES (?,?,?,?)',(lid,cid,data.name,data.description))
                db.execute('UPDATE campaigns SET version=version+1 WHERE id=?',(cid,))
            engine.vault.export(cid); return {'id':lid}

    @app.post('/api/campaigns/{cid}/npcs/generate')
    async def generate_npc(cid:str,data:CharacterPromptInput):
        engine.world.require(cid)
        return await engine.generate_npc_draft(cid,data.prompt)

    @app.post('/api/campaigns/{cid}/npcs/with-memories')
    async def add_npc_with_memories(cid:str,data:NPCWithMemoriesInput):
        async with engine.lock(cid):
            nid=engine.add_npc_with_memories(cid,data)
            engine.vault.export(cid)
            return {'id':nid,'memories':len(data.memories)}

    @app.post('/api/campaigns/{cid}/npcs')
    async def add_npc(cid:str,data:NPCInput):
        async with engine.lock(cid):
            nid=engine.world.add_npc(cid,data); engine.vault.export(cid); return {'id':nid}

    @app.put('/api/campaigns/{cid}/npcs/{nid}')
    async def edit_npc(cid:str,nid:str,data:NPCInput):
        async with engine.lock(cid):
            if not database.one('SELECT id FROM npcs WHERE campaign=? AND id=?',(cid,nid)): raise HTTPException(404,'Personagem não encontrado.')
            engine.world.add_npc(cid,data,nid); engine.vault.export(cid); return {'id':nid}

    @app.post('/api/campaigns/{cid}/move')
    async def move(cid:str,data:Move):
        async with engine.lock(cid):
            result=engine.world.move(cid,data.location); engine.vault.export(cid); return result

    @app.post('/api/campaigns/{cid}/advance')
    async def advance(cid:str,data:Advance):
        async with engine.lock(cid):
            result=engine.world.advance(cid,data.minutes); engine.vault.export(cid); return result

    @app.put('/api/campaigns/{cid}/clock')
    async def clock(cid:str,data:Clock):
        async with engine.lock(cid):
            engine.world.require(cid)
            with database.connect() as db:
                db.execute('UPDATE campaigns SET realtime=?,rate=?,last_wall=?,version=version+1 WHERE id=?',(int(data.enabled),data.rate,time.time(),cid))
            return {'saved':True}

    @app.post('/api/campaigns/{cid}/chat')
    async def chat(cid:str,data:ChatInput): return await engine.chat(cid,data)

    @app.get('/api/campaigns/{cid}/history/{nid}')
    async def history(cid:str,nid:str,limit:int=Query(50,ge=1,le=200)):
        engine.world.require(cid)
        return engine.history(cid,nid,limit)

    @app.delete('/api/campaigns/{cid}/turns/{tid}')
    async def delete_turn(cid:str,tid:str):
        async with engine.lock(cid):
            engine.world.require(cid)
            return engine.delete_turn(cid,tid)

    @app.get('/api/campaigns/{cid}/memories')
    async def memories(cid:str,q:str=Query('',max_length=2000),actor:str='player',limit:int=Query(50,ge=1,le=200),invalid:bool=False):
        engine.world.require(cid)
        return engine.memory.search(cid,actor,q,limit,include_invalid=invalid)

    @app.get('/api/campaigns/{cid}/memories/{mid}')
    async def memory(cid:str,mid:str,gm:bool=False):
        row=database.one('SELECT * FROM memories WHERE campaign=? AND id=?',(cid,mid))
        if not row or not visible(row['known_by'],'gm' if gm else 'player'): raise HTTPException(404,'Memória não disponível para o jogador.')
        return decode(row)

    @app.post('/api/campaigns/{cid}/memories')
    async def create_memory(cid:str,data:MemoryInput):
        async with engine.lock(cid):
            c=engine.world.require(cid)
            known={'*','player'}|{n['id'] for n in database.rows('SELECT id FROM npcs WHERE campaign=?',(cid,))}
            if not set(data.known_by)<=known: raise ValueError('Conhecedor não pertence à campanha.')
            if data.kind=='secret' and '*' in data.known_by: raise ValueError('Um segredo não pode ser público.')
            with database.connect() as db:
                mid=save_memory(db,cid,data.kind,data.text,data.known_by,c['time'],'creator',data.importance,data.entities,data.fact_key)
                db.execute('UPDATE campaigns SET version=version+1 WHERE id=?',(cid,))
            engine.vault.export(cid); return {'id':mid}

    @app.post('/api/campaigns/{cid}/memories/{mid}/invalidate')
    async def invalidate(cid:str,mid:str):
        async with engine.lock(cid):
            with database.connect() as db:
                invalidate_dependents(db,mid)
                db.execute('UPDATE memories SET valid=0,revision=revision+1 WHERE campaign=? AND id=?',(cid,mid))
                db.execute('UPDATE campaigns SET version=version+1 WHERE id=?',(cid,))
            engine.vault.export(cid); return {'saved':True}

    @app.post('/api/campaigns/{cid}/consolidate')
    async def consolidate(cid:str):
        async with engine.lock(cid):
            c=engine.world.require(cid); result=engine.memory.consolidate(cid,c['time']); engine.vault.export(cid); return result

    @app.post('/api/campaigns/{cid}/reindex')
    async def reindex(cid:str):
        async with engine.lock(cid):
            engine.world.require(cid); return await engine.memory.reindex(cid,engine.client(),32)

    @app.post('/api/campaigns/{cid}/vault/{action}')
    async def vault(cid:str,action:str):
        async with engine.lock(cid):
            if action=='export': return engine.vault.export(cid)
            if action=='import': return engine.vault.import_memories(cid)
            raise HTTPException(404,'Ação não encontrada.')

    @app.get('/api/backup')
    async def backup():
        # SQLite backup API produces a consistent snapshot even with WAL active.
        out=io.BytesIO()
        with tempfile.TemporaryDirectory() as temp:
            snapshot_path=Path(temp)/'world.sqlite3'
            with database.connect() as source, sqlite3.connect(snapshot_path) as target:
                source.backup(target)
                target.execute('PRAGMA journal_mode=DELETE')
                target.execute("UPDATE settings SET value=json_set(value,'$.api_key','') WHERE key='ai'")
                target.commit()
                target.execute('VACUUM')
            snapshot=snapshot_path.read_bytes()
        with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('world.sqlite3',snapshot)
            archive.writestr('RESTORE.txt','Restaure com: python scripts/restore_backup.py backup.zip --data NOVA_PASTA\nA chave da IA foi omitida.\n')
            for p in engine.vault.root.rglob('*.md'):
                if not p.is_symlink() and p.resolve().is_relative_to(engine.vault.root.resolve()):
                    archive.write(p,'vault/'+str(p.relative_to(engine.vault.root)))
        return Response(out.getvalue(),media_type='application/zip',headers={'Content-Disposition':'attachment; filename="RP-creator-backup.zip"'})

    static=Path(__file__).with_name('static')
    app.mount('/static',StaticFiles(directory=static),name='static')

    @app.get('/')
    async def index(): return FileResponse(static/'index.html')

    return app


app=create_app()
