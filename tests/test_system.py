import asyncio
import io
import json
import sqlite3
import zipfile
import pytest
import httpx
from fastapi.testclient import TestClient
from rp_creator.api import create_app
from rp_creator.ai import AIClient,AIError
from rp_creator.db import Database,uid,dumps
from rp_creator.models import AISettings,CampaignInput,ChatInput,Analysis,ExtractedMemory,Effect,PromiseProposal
from rp_creator.engine import Engine
from rp_creator.memory import save_memory
from rp_creator.vault import parse_note,note


@pytest.fixture
def env(tmp_path):
    e=Engine(Database(tmp_path)); c=e.world.create(CampaignInput(name='Teste'))
    e.db.set_setting('ai',AISettings(provider='demo').model_dump())
    cid=c['id']; ns=e.db.rows('SELECT * FROM npcs WHERE campaign=? ORDER BY name',(cid,))
    return e,cid,{n['name']:n for n in ns}


def run(coro): return asyncio.run(coro)


def chat(e,cid,nid,message,request_id=None):
    return run(e.chat(cid,ChatInput(npc=nid,message=message,request_id=request_id or uid())))


def test_persistent_chat_and_recall(env):
    e,cid,ns=env
    t=chat(e,cid,ns['Sara']['id'],'Eu odeio café e gosto de chá de hibisco.')
    assert t['new_memories']
    fresh=Engine(Database(e.db.root))
    result=chat(fresh,cid,ns['Sara']['id'],'Você lembra do que eu gosto?')
    assert 'hibisco' in result['response'] and '[mem:' in result['response']


def test_idempotency_no_double_effect(env):
    e,cid,ns=env; rid=uid()
    a=chat(e,cid,ns['Sara']['id'],'Eu gosto de fotografar.',rid)
    b=chat(e,cid,ns['Sara']['id'],'Eu gosto de fotografar.',rid)
    assert a['id']==b['id'] and b['replayed']
    assert len(e.history(cid,ns['Sara']['id']))==1
    with pytest.raises(ValueError): chat(e,cid,ns['Sara']['id'],'Texto diferente',rid)


def test_secrets_isolated_across_characters_campaigns_and_player(env):
    e,cid,ns=env
    secret=e.memory.search(cid,ns['Sara']['id'],'festa surpresa',50)
    assert any(m['kind']=='secret' for m in secret)
    for actor in ('player',ns['Alex']['id']):
        assert not any(m['kind']=='secret' for m in e.memory.search(cid,actor,'festa surpresa',50))
    other=e.world.create(CampaignInput(name='Outro'))
    assert not any(m['campaign']==cid for m in e.memory.search(other['id'],'gm','festa',50))


def test_old_memory_found_after_1500_new_records(env):
    e,cid,ns=env
    with e.db.connect() as db:
        mid=save_memory(db,cid,'episodic','Encontrou o medalhão azul no farol.',[ns['Sara']['id']],'2020-01-01T00:00:00','test',1)
        for i in range(1500): save_memory(db,cid,'episodic',f'Conversa rotineira número {i}',[ns['Sara']['id']],'2026-09-25T09:00:00','test',3)
    found=e.memory.search(cid,ns['Sara']['id'],'medalhão farol',12)
    assert found[0]['id']==mid


def test_facts_supersede_only_same_audience(env):
    e,cid,ns=env
    with e.db.connect() as db:
        old=save_memory(db,cid,'semantic','Gosta de café',['player',ns['Sara']['id']],'2026','t',fact_key='coffee')
        other=save_memory(db,cid,'semantic','Gosta de café',[ns['Alex']['id']],'2026','t',fact_key='coffee')
        new=save_memory(db,cid,'semantic','Não gosta de café',['player',ns['Sara']['id']],'2026','t',fact_key='coffee')
    assert e.db.one('SELECT valid FROM memories WHERE id=?',(old,))['valid']==0
    assert e.db.one('SELECT valid FROM memories WHERE id=?',(other,))['valid']==1
    assert new!=old


def test_summary_preserves_sources_and_private_audience(env):
    e,cid,ns=env
    with e.db.connect() as db:
        for i in range(12):save_memory(db,cid,'semantic',f'Segredo {i}',[ns['Sara']['id']],'2026-01-01','test')
    result=e.memory.consolidate(cid,'2026-09-25')
    assert result['created']==2
    assert e.memory.consolidate(cid,'2026-09-25')['created']==0
    assert not any('Segredo' in m['text'] for m in e.memory.search(cid,ns['Alex']['id'],'Segredo',100))
    summary=e.db.one("SELECT parents FROM memories WHERE kind='summary'")
    assert len(json.loads(summary['parents']))==6


def test_routine_moves_npc_and_blocks_remote_chat(env):
    e,cid,ns=env;e.world.advance(cid,60)
    sara=e.db.one('SELECT location FROM npcs WHERE id=?',(ns['Sara']['id'],))
    assert sara['location']!=e.world.require(cid)['location']
    with pytest.raises(ValueError,match='outro local'):chat(e,cid,ns['Sara']['id'],'Oi!')
    e.world.move(cid,sara['location'])
    assert chat(e,cid,ns['Sara']['id'],'Oi!')['response']


def add_promise(e,cid,nid,due,lid):
    pid=uid()
    with e.db.connect() as db:db.execute('INSERT INTO promises VALUES (?,?,?,?,?,?,?,?,?)',(pid,cid,nid,'Encontrar Sara',due,lid,'pending','2026-09-25T09:00:00','test'))
    return pid


def test_promise_fulfilled_and_applied_once(env):
    e,cid,ns=env;pid=add_promise(e,cid,ns['Sara']['id'],'2026-09-25T09:30:00',ns['Sara']['location'])
    e.world.advance(cid,30);e.world.advance(cid,20)
    assert e.db.one('SELECT status FROM promises WHERE id=?',(pid,))['status']=='fulfilled'
    values=e.db.one('SELECT values_json FROM relationships WHERE source=? AND target=?',(ns['Sara']['id'],'player'))
    assert json.loads(values['values_json'])['trust']==5


def test_missed_promise_during_large_time_skip(env):
    e,cid,ns=env;park=ns['Alex']['location']
    pid=add_promise(e,cid,ns['Sara']['id'],'2026-09-25T11:30:00',park)
    e.world.advance(cid,1440)
    assert e.db.one('SELECT status FROM promises WHERE id=?',(pid,))['status']=='missed'
    assert e.db.one("SELECT count(*) n FROM events WHERE kind='goal'")['n']==2


def test_npc_encounters_do_not_leak(env):
    e,cid,ns=env;e.world.move(cid,ns['Alex']['location']);e.world.advance(cid,180)
    # At noon Alex is in square, Sara in library; later 19h Sara is home, Alex arrives at 20.
    e.world.advance(cid,480)
    hidden=[x for x in e.world.snapshot(cid,True)['events'] if 'se encontraram' in x['text']]
    assert hidden and not any(x['id'] in {h['id'] for h in hidden} for x in e.world.snapshot(cid)['events'])


def test_vault_round_trip_conflict_and_path_guard(env,tmp_path):
    e,cid,ns=env;e.vault.export(cid)
    m=e.memory.search(cid,'gm','biblioteca',1)[0];p=e.vault.root/cid/'Memories'/f"{m['id']}.md"
    original=p.read_text();meta,body=parse_note(original)
    p.write_text(note(meta,'Uma memória editada manualmente.'))
    exported=e.vault.export(cid);assert str(p.relative_to(e.vault.root)) in exported['conflicts']
    result=e.vault.import_memories(cid);assert result['imported']==[m['id']] and not result['errors']
    assert e.db.one('SELECT text FROM memories WHERE id=?',(m['id'],))['text']=='Uma memória editada manualmente.'
    meta,body=parse_note(p.read_text());p.write_text(note(meta,'Outro ajuste'))
    with e.db.connect() as db:db.execute('UPDATE memories SET revision=revision+1 WHERE id=?',(m['id'],))
    assert e.vault.import_memories(cid)['errors']
    with pytest.raises(ValueError):e.vault._safe('../../outside')


def test_invalid_extractor_never_applies_unquoted_evidence(env,monkeypatch):
    e,cid,ns=env;e.db.set_setting('ai',AISettings().model_dump())
    async def complete(*args,**kwargs):return 'Uma resposta.'
    async def analyze(*args,**kwargs):return Analysis(memories=[ExtractedMemory(text='Fake',evidence='inventado')],effects=[Effect(metric='trust',delta=10,evidence='inventado')])
    monkeypatch.setattr(AIClient,'complete',complete);monkeypatch.setattr(AIClient,'analyze',analyze)
    result=chat(e,cid,ns['Sara']['id'],'Oi Sara!')
    assert not result['new_memories']
    assert not e.db.one("SELECT * FROM relationships WHERE target='player'")


def test_failed_ai_preserves_world_and_turns(env,monkeypatch):
    e,cid,ns=env;e.db.set_setting('ai',AISettings().model_dump())
    async def fail(*args,**kwargs):raise AIError('offline')
    monkeypatch.setattr(AIClient,'complete',fail)
    before=e.world.require(cid)
    with pytest.raises(AIError):chat(e,cid,ns['Sara']['id'],'Oi!')
    assert e.history(cid,ns['Sara']['id'])==[] and e.world.require(cid)==before


def test_analyzer_failure_saves_response_with_warning(env,monkeypatch):
    e,cid,ns=env;e.db.set_setting('ai',AISettings().model_dump())
    async def complete(*args,**kwargs):return 'Oi!'
    async def fail(*args,**kwargs):raise AIError('extração inválida')
    monkeypatch.setattr(AIClient,'complete',complete);monkeypatch.setattr(AIClient,'analyze',fail)
    result=chat(e,cid,ns['Sara']['id'],'Oi Sara!')
    assert result['response']=='Oi!' and 'inválida' in result['warning']


@pytest.mark.parametrize('provider,path,response',[('openai','/v1/chat/completions',{'choices':[{'message':{'content':'OK'}}]}),('ollama','/api/chat',{'message':{'content':'OK'}}),('custom','/v1/chat/completions',{'response':'OK'})])
def test_provider_contracts(monkeypatch,provider,path,response):
    real=httpx.AsyncClient
    def handler(req):
        assert req.url.path==path
        body=json.loads(req.content);assert body['stream'] is False and body['messages'][0]['content']=='oi'
        return httpx.Response(200,json=response)
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(handler),**kw))
    assert run(AIClient(AISettings(provider=provider,chat_path=path)).complete([{'role':'user','content':'oi'}]))=='OK'


def test_embedding_privacy_and_semantic_recall(env):
    e,cid,ns=env
    with e.db.connect() as db:
        mid=save_memory(db,cid,'semantic','Encontro no litoral',[ns['Sara']['id']],'2020','test')
        db.execute('UPDATE memories SET embedding=?,embedding_model=? WHERE id=?',(dumps([1.,0.]),'x',mid))
    assert e.memory.search(cid,ns['Sara']['id'],'praia',10,[1.,0.],'x')[0]['id']==mid
    assert mid not in [m['id'] for m in e.memory.search(cid,ns['Alex']['id'],'praia',10,[1.,0.],'x')]


def test_api_end_to_end_security_and_backup(tmp_path):
    app=create_app(tmp_path,testing=True)
    with TestClient(app) as c:
        assert c.post('/api/campaigns',json={'name':'A'}).status_code==403
        c.headers['X-RP-Token']=c.get('/api/session').json()['token']
        assert c.post('/api/campaigns',json={'name':'A'},headers={'Origin':'https://evil.example'}).status_code==403
        assert c.put('/api/settings',json={'base_url':'https://example.com'}).status_code==422
        assert c.put('/api/settings',json={'provider':'demo','api_key':'sensitive-test-key'}).status_code==200
        assert 'sensitive-test-key' not in c.get('/api/settings').text
        campaign=c.post('/api/campaigns',json={'name':'A'}).json();cid=campaign['id']
        w=c.get(f'/api/campaigns/{cid}').json();sara=next(n for n in w['npcs'] if n['name']=='Sara')
        turn=c.post(f'/api/campaigns/{cid}/chat',json={'npc':sara['id'],'message':'Eu odeio café.','request_id':uid()})
        assert turn.status_code==200,turn.text
        assert 'café' in c.get(f'/api/campaigns/{cid}/memories?q=café').text
        secret=app.state.engine.db.one("SELECT id FROM memories WHERE kind='secret'")['id']
        assert c.get(f'/api/campaigns/{cid}/memories/{secret}').status_code==404
        assert c.get('/').status_code==200
        assert "script-src 'self'" in c.get('/').headers['content-security-policy']
        archive=zipfile.ZipFile(io.BytesIO(c.get('/api/backup').content))
        snapshot=archive.read('world.sqlite3')
        assert b'sensitive-test-key' not in snapshot
        restored=sqlite3.connect(':memory:');restored.deserialize(snapshot)
        assert 'sensitive-test-key' not in restored.execute('SELECT value FROM settings').fetchone()[0]
        assert restored.execute('SELECT count(*) FROM turns').fetchone()[0]==1


def test_summary_invalidated_when_source_superseded(env):
    e,cid,ns=env
    with e.db.connect() as db:
        for i in range(6):save_memory(db,cid,'semantic',f'Fato {i}',['player'],'2026','test',fact_key=f'f{i}')
    summary=e.memory.consolidate(cid,'2026')['ids'][0]
    with e.db.connect() as db:save_memory(db,cid,'semantic','Fato corrigido',['player'],'2026','test',fact_key='f0')
    assert e.db.one('SELECT valid FROM memories WHERE id=?',(summary,))['valid']==0


def test_scheduled_npc_attends_meeting_outside_routine(env):
    e,cid,ns=env;park=ns['Alex']['location']
    pid=add_promise(e,cid,ns['Sara']['id'],'2026-09-25T10:30:00',park)
    e.world.move(cid,park);e.world.advance(cid,90)
    assert e.db.one('SELECT status FROM promises WHERE id=?',(pid,))['status']=='fulfilled'
    assert e.db.one('SELECT location FROM npcs WHERE id=?',(ns['Sara']['id'],))['location']==park


def test_context_excludes_other_npc_secret_and_private_player_profile(env,monkeypatch):
    e,cid,ns=env;seen=[];e.db.set_setting('ai',AISettings().model_dump())
    with e.db.connect() as db:
        db.execute('UPDATE campaigns SET player_profile=? WHERE id=?',('PRIVATE_PROFILE_SENTINEL',cid))
        save_memory(db,cid,'secret','ALEX_SECRET_SENTINEL',[ns['Alex']['id']],'2026','test',10)
    async def complete(self,messages,**kwargs):seen.extend(messages);return 'Olá'
    async def analyze(*args,**kwargs):return Analysis()
    monkeypatch.setattr(AIClient,'complete',complete);monkeypatch.setattr(AIClient,'analyze',analyze)
    chat(e,cid,ns['Sara']['id'],'O que você sabe sobre Alex?')
    assert 'ALEX_SECRET_SENTINEL' not in str(seen)
    assert 'PRIVATE_PROFILE_SENTINEL' not in str(seen)
    assert 'festa surpresa' in str(seen)


def test_restore_backup_script(tmp_path):
    import importlib.util
    from pathlib import Path
    spec=importlib.util.spec_from_file_location('restore',Path(__file__).parents[1]/'scripts/restore_backup.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    app=create_app(tmp_path/'source',testing=True)
    with TestClient(app) as client:
        client.headers['X-RP-Token']=client.get('/api/session').json()['token']
        campaign=client.post('/api/campaigns',json={'name':'Meu mundo'}).json()
        backup=tmp_path/'backup.zip';backup.write_bytes(client.get('/api/backup').content)
    dest=module.restore(backup,tmp_path/'restored')
    db=Database(dest)
    assert db.one('SELECT name FROM campaigns WHERE id=?',(campaign['id'],))['name']=='Meu mundo'
    assert (dest/'vault'/campaign['id']/'World.md').exists()
    with pytest.raises(ValueError):module.restore(backup,dest)


def test_real_murn_contract_and_ollama_extraction(env,monkeypatch):
    e,cid,ns=env
    e.db.set_setting('ai',AISettings(provider='murn').model_dump())
    calls=[]
    original=httpx.AsyncClient
    def handler(request):
        body=json.loads(request.content)
        calls.append((request.url.path,body))
        if request.url.path=='/v1/rp/chat':
            assert body['source']=='rp-creator'
            assert body['messages'][0]['role']=='system'
            assert 'Sara' in body['messages'][0]['content']
            assert body['messages'][-1]['content']=='Eu gosto de chá.'
            return httpx.Response(200,json={'message':'*Sara sorri.* Vou me lembrar disso.','model':'llama3.1:8b'})
        assert request.url.path=='/api/chat'
        assert body['format']=='json'
        assert body['messages'][0]['role']=='system'
        return httpx.Response(200,json={'message':{'content':json.dumps({
            'memories':[{'kind':'semantic','text':'O jogador gosta de chá.','importance':7,'evidence':'Eu gosto de chá.'}],
            'effects':[],'promises':[]
        })}})
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    turn=chat(e,cid,ns['Sara']['id'],'Eu gosto de chá.')
    assert turn['new_memories']
    assert [path for path,_ in calls]==['/v1/rp/chat','/api/chat']


def test_murn_rp_endpoint_falls_back_to_ollama_on_old_server(monkeypatch):
    calls=[]
    original=httpx.AsyncClient
    def handler(request):
        body=json.loads(request.content);calls.append(request.url.path)
        if request.url.path=='/v1/rp/chat':
            return httpx.Response(404,json={'detail':'Not Found'})
        assert request.url.path=='/api/chat'
        assert body['messages'][-1]['content']=='oi'
        return httpx.Response(200,json={'message':{'content':'RP OK'}})
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    ai=AIClient(AISettings(provider='murn'))
    assert run(ai.complete([{'role':'system','content':'Interprete Tanjiro.'},{'role':'user','content':'oi'}]))=='RP OK'
    assert calls==['/v1/rp/chat','/api/chat']


def test_delete_turn_removes_transcript_and_direct_memories(env):
    e,cid,ns=env
    turn=chat(e,cid,ns['Sara']['id'],'Eu odeio café.')
    tid=turn['id']
    assert e.db.one('SELECT id FROM turns WHERE id=?',(tid,))
    assert e.db.one('SELECT id FROM memories WHERE source=?',(tid,))
    result=e.delete_turn(cid,tid)
    assert result['deleted'] and result['user']=='Eu odeio café.'
    assert not e.db.one('SELECT id FROM turns WHERE id=?',(tid,))
    assert not e.db.one('SELECT id FROM memories WHERE source=?',(tid,))


def test_role_confusion_triggers_clean_retry(env,monkeypatch):
    e,cid,ns=env
    e.db.set_setting('ai',AISettings().model_dump())
    with e.db.connect() as db:
        db.execute('UPDATE campaigns SET player_name=? WHERE id=?',('Kuren Matsumi',cid))
        db.execute('UPDATE npcs SET name=?,profile=? WHERE id=?',
                   ('Tanjiro Kamado','Tanjiro é um Caçador de Demônios da Corporação.',ns['Sara']['id']))
    replies=iter([
        'Eu sou Kuren Matsumi. Você é?',
        '*Tanjiro inclina a cabeça.* Sim, sou Tanjiro Kamado. Quem é você?'
    ])
    seen=[]
    async def complete(self,messages,**kwargs):
        seen.append(messages)
        return next(replies)
    async def analyze(*args,**kwargs): return Analysis()
    monkeypatch.setattr(AIClient,'complete',complete)
    monkeypatch.setattr(AIClient,'analyze',analyze)
    result=chat(e,cid,ns['Sara']['id'],'Você é Tanjiro Kamado?')
    assert result['response'].startswith('*Tanjiro')
    assert len(seen)==2
    assert 'CORREÇÃO DE PAPÉIS' in seen[1][1]['content']


def test_analysis_normalizes_portuguese_json(monkeypatch):
    ai=AIClient(AISettings(provider='ollama',json_mode=True))
    async def complete(self,messages,**kwargs):
        return json.dumps({
            'memórias':[{'tipo':'Fato','texto':'O jogador gosta de chá.',
                         'importância':'7/10','evidência':'gosto de chá'}],
            'efeitos':[{'métrica':'confiança','mudança':3,'evidência':'gosto de chá'}],
            'promessas':[]
        },ensure_ascii=False)
    monkeypatch.setattr(AIClient,'complete',complete)
    result=run(ai.analyze('gosto de chá',{'npc':{'name':'Sara'}}))
    assert result.memories[0].kind=='semantic'
    assert result.memories[0].importance==7
    assert result.effects[0].metric=='trust'


def test_continuity_detects_reasking_explicit_identity_fact():
    reason=Engine._continuity_confusion(
        'Você é... meio oni?',
        'Sou meio oni. Mas nunca comi humanos.',
        'Tanjiro é um Caçador de Demônios.',
        '',
        []
    )
    assert 'acabou de afirmar' in reason


def test_continuity_detects_definition_of_known_concept():
    reason=Engine._continuity_confusion(
        'E o que você quer dizer com "Respiração"?',
        'Ainda consigo usar técnicas de Respiração.',
        'Tanjiro domina a Respiração da Água e conhece técnicas de Respiração.',
        '',
        []
    )
    assert 'conceito que o personagem já conhece' in reason


def test_continuity_retry_rewrites_bad_reply(env,monkeypatch):
    e,cid,ns=env
    e.db.set_setting('ai',AISettings().model_dump())
    with e.db.connect() as db:
        db.execute('UPDATE campaigns SET player_name=? WHERE id=?',('Kuren Matsumi',cid))
        db.execute('UPDATE npcs SET name=?,profile=? WHERE id=?',
                   ('Tanjiro Kamado','Tanjiro é Caçador de Demônios e domina a Respiração da Água.',ns['Sara']['id']))
    replies=iter([
        'Você é... meio oni? E o que você quer dizer com Respiração?',
        '*Tanjiro observa Kuren com atenção.* Então você consegue usar Respiração apesar do sangue de oni?'
    ])
    seen=[]
    async def complete(self,messages,**kwargs):
        seen.append(messages)
        return next(replies)
    async def analyze(*args,**kwargs): return Analysis()
    monkeypatch.setattr(AIClient,'complete',complete)
    monkeypatch.setattr(AIClient,'analyze',analyze)
    result=chat(e,cid,ns['Sara']['id'],'Sou meio oni. Ainda consigo usar técnicas de Respiração.')
    assert result['response'].startswith('*Tanjiro')
    assert len(seen)==2
    assert 'CORREÇÃO OBRIGATÓRIA DE CONTINUIDADE' in seen[1][1]['content']


def test_role_confusion_detects_player_as_narrative_subject():
    assert Engine._role_confusion(
        'Kuren olha para você com um olhar sereno. Ele parece ansioso.',
        'Tanjiro Kamado',
        'Kuren Matsumi',
        'Tanjiro é Caçador de Demônios.'
    )


def test_role_confusion_detects_switch_to_other_npc():
    assert Engine._role_confusion(
        '*Giyo Tomioka olha para você com uma expressão serena.*',
        'Tanjiro Kamado',
        'Kuren Matsumi',
        'Tanjiro é Caçador de Demônios.',
        ['Tanjiro Kamado','Giyu Tomioka','Shinobu Kocho']
    )


def test_player_narration_is_retried_before_save(env,monkeypatch):
    e,cid,ns=env
    e.db.set_setting('ai',AISettings().model_dump())
    with e.db.connect() as db:
        db.execute('UPDATE campaigns SET player_name=? WHERE id=?',('Kuren Matsumi',cid))
        db.execute('UPDATE npcs SET name=?,profile=? WHERE id=?',
                   ('Tanjiro Kamado','Tanjiro é Caçador de Demônios e usa Respiração da Água.',ns['Sara']['id']))
    replies=iter([
        'Kuren olha para você com um olhar sereno e parece ansioso. — É melhor assim.',
        '*Tanjiro mantém os olhos em Kuren, surpreso.* — Você nunca comeu um humano... e ainda consegue usar Respiração? Isso é diferente de tudo que eu já vi.'
    ])
    async def complete(self,messages,**kwargs): return next(replies)
    async def analyze(*args,**kwargs): return Analysis()
    monkeypatch.setattr(AIClient,'complete',complete)
    monkeypatch.setattr(AIClient,'analyze',analyze)
    result=chat(
        e,cid,ns['Sara']['id'],
        'Sim. Sou meio oni. Ainda consigo usar Respiração e nunca comi um humano.'
    )
    assert result['response'].startswith('*Tanjiro')
    assert 'Kuren olha para você' not in result['response']
