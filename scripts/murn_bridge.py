"""Optional local bridge for murn. APIs accepting one prompt string instead of messages.

Run with env MURN_URL, MURN_INPUT_FIELD and MURN_OUTPUT_PATH matching YOUR API.
This is a protocol adapter, not a replacement model or a guess of murn.'s internals.
"""
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx
import uvicorn
from fastapi import FastAPI,HTTPException
from pydantic import BaseModel,Field
from rp_creator.models import AISettings

app=FastAPI(title='RP creator · murn. bridge')


class Message(BaseModel):
    role: str
    content: str = Field(max_length=100000)


class Completion(BaseModel):
    model: str
    messages: list[Message] = Field(max_length=60)
    stream: bool = False
    temperature: float = .7


@app.post('/v1/chat/completions')
async def completion(data:Completion):
    if data.stream:raise HTTPException(400,'Este adaptador usa respostas completas, sem streaming.')
    url=os.environ.get('MURN_URL','http://127.0.0.1:7331/api/chat')
    from urllib.parse import urlsplit
    split=urlsplit(url)
    AISettings(base_url=f'{split.scheme}://{split.netloc}')
    field=os.environ.get('MURN_INPUT_FIELD','message')
    output=os.environ.get('MURN_OUTPUT_PATH','response')
    # Preserve ALL system instructions and history, not just the last user message.
    prompt='\n\n'.join(f'<{m.role}>\n{m.content}\n</{m.role}>' for m in data.messages)
    payload={field:prompt,'model':data.model,'stream':False}
    headers={}
    if os.environ.get('MURN_API_KEY'):headers['Authorization']='Bearer '+os.environ['MURN_API_KEY']
    try:
        async with httpx.AsyncClient(timeout=180,trust_env=False) as client:
            r=await client.post(url,json=payload,headers=headers);r.raise_for_status();result=r.json()
        for key in output.split('.'):
            result=result[int(key)] if isinstance(result,list) else result[key]
        if not isinstance(result,str) or not result.strip():raise ValueError('Resposta inválida')
        return {'choices':[{'message':{'role':'assistant','content':result}}]}
    except (httpx.HTTPError,KeyError,ValueError,TypeError,IndexError) as exc:
        raise HTTPException(502,'Confira o contrato do murn. e as variáveis MURN_*.') from exc


if __name__=='__main__':
    uvicorn.run(app,host='127.0.0.1',port=int(os.environ.get('RP_BRIDGE_PORT','7333')))
