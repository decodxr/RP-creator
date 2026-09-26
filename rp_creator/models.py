from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator
from urllib.parse import urlsplit


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class CampaignInput(Strict):
    name: str = Field(min_length=1, max_length=100)
    premise: str = Field(default='Uma cidade contemporânea, cheia de histórias por descobrir.', max_length=6000)
    player_name: str = Field(default='Lucas', min_length=1, max_length=80)
    player_profile: str = Field(default='', max_length=4000)
    seed: bool = True


class LocationInput(Strict):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default='', max_length=2000)


class Routine(Strict):
    hour: int = Field(ge=0, le=23)
    location: str = Field(min_length=1, max_length=100)
    activity: str = Field(default='segue sua rotina', max_length=200)


class NPCInput(Strict):
    name: str = Field(min_length=1, max_length=80)
    profile: str = Field(min_length=1, max_length=4000)
    location: str = Field(min_length=1, max_length=100)
    mood: str = Field(default='neutro', max_length=100)
    routine: list[Routine] = Field(default_factory=list, max_length=24)
    goals: list[str] = Field(default_factory=list, max_length=8)

    @field_validator('goals')
    @classmethod
    def check_goals(cls, goals):
        if any(len(g) > 300 for g in goals):
            raise ValueError('Objetivos devem ter até 300 caracteres.')
        return goals


MemoryKind = Literal['episodic','semantic','social','emotional','promise','secret','temporal','summary','derived']
DraftMemoryKind = Literal['episodic','semantic','social','emotional','promise','secret','temporal']


class CharacterPromptInput(Strict):
    prompt: str = Field(min_length=3, max_length=12000)


class CharacterDraftMemory(Strict):
    kind: DraftMemoryKind = 'semantic'
    text: str = Field(min_length=1, max_length=2000)
    importance: int = Field(default=7, ge=1, le=10)
    # During generation, "self" means the character being created.
    # Other values are player, *, an existing NPC id, or an existing NPC name
    # that the engine resolves before returning/saving the draft.
    known_by: list[str] = Field(default_factory=lambda: ['self'], min_length=1, max_length=50)


class CharacterDraft(Strict):
    name: str = Field(min_length=1, max_length=80)
    profile: str = Field(min_length=1, max_length=4000)
    location: str = Field(min_length=1, max_length=100)
    mood: str = Field(default='neutro', max_length=100)
    routine: list[Routine] = Field(default_factory=list, max_length=24)
    goals: list[str] = Field(default_factory=list, max_length=8)
    memories: list[CharacterDraftMemory] = Field(default_factory=list, max_length=20)

    @field_validator('goals')
    @classmethod
    def check_draft_goals(cls, goals):
        if any(len(g) > 300 for g in goals):
            raise ValueError('Objetivos devem ter até 300 caracteres.')
        return goals


class NPCWithMemoriesInput(Strict):
    npc: NPCInput
    memories: list[CharacterDraftMemory] = Field(default_factory=list, max_length=20)


class MemoryInput(Strict):
    kind: MemoryKind = 'semantic'
    text: str = Field(min_length=1, max_length=2000)
    known_by: list[str] = Field(min_length=1, max_length=50)
    entities: list[str] = Field(default_factory=list, max_length=20)
    importance: int = Field(default=5, ge=1, le=10)
    fact_key: str | None = Field(default=None, max_length=100)


class ExtractedMemory(Strict):
    kind: MemoryKind = 'semantic'
    text: str = Field(min_length=1, max_length=1000)
    importance: int = Field(default=5, ge=1, le=10)
    evidence: str = Field(min_length=3, max_length=1000)
    # Extractor cannot choose who knows a fact; server grants current participants only.
    fact_key: str | None = Field(default=None, max_length=100)


class Effect(Strict):
    metric: Literal['trust','friendship','respect','fear','anger','affection','attraction','loyalty','suspicion']
    delta: int = Field(ge=-10, le=10)
    evidence: str = Field(min_length=3, max_length=1000)


class PromiseProposal(Strict):
    text: str = Field(min_length=1, max_length=500)
    due: str = Field(max_length=40)
    location: str = Field(max_length=100)
    evidence: str = Field(min_length=3, max_length=1000)


class Analysis(Strict):
    memories: list[ExtractedMemory] = Field(default_factory=list, max_length=8)
    effects: list[Effect] = Field(default_factory=list, max_length=5)
    promises: list[PromiseProposal] = Field(default_factory=list, max_length=3)


class ChatInput(Strict):
    npc: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=6000)
    request_id: str = Field(min_length=8, max_length=100)
    # Server-generated shared-scene context for group conversations. The normal
    # UI never needs to fill this field directly.
    scene_context: str = Field(default='', max_length=8000)


class GroupChatInput(Strict):
    message: str = Field(min_length=1, max_length=6000)
    request_id: str = Field(min_length=8, max_length=80, pattern=r'^[A-Za-z0-9-]+    provider: Literal['murn','openai','ollama','custom','demo'] = 'murn'
    base_url: str = 'http://127.0.0.1:7331'
    model: str = Field(default='llama3.1:8b', min_length=1, max_length=200)
    chat_path: str = Field(default='/v1/chat', max_length=200)
    messages_field: str = Field(default='messages', pattern=r'^[A-Za-z_][A-Za-z0-9_]*$')
    response_path: str = Field(default='response', pattern=r'^[A-Za-z0-9_.]+$')
    api_key: str = Field(default='', max_length=2000)
    temperature: float = Field(default=0.7, ge=0, le=2)
    timeout: int = Field(default=120, ge=5, le=600)
    json_mode: bool = False
    embeddings: bool = False
    embedding_url: str = 'http://127.0.0.1:11434'
    embedding_model: str = Field(default='embeddinggemma', min_length=1, max_length=200)
    embedding_provider: Literal['ollama','openai'] = 'ollama'
    context_chars: int = Field(default=18000, ge=4000, le=60000)
    retrieval_limit: int = Field(default=12, ge=1, le=30)

    @field_validator('base_url','embedding_url')
    @classmethod
    def local_endpoint(cls, value):
        p = urlsplit(value)
        # Local desktop tool: prevent configuring arbitrary public HTTP fetches.
        if p.scheme not in ('http','https') or p.hostname not in ('localhost','127.0.0.1','::1','host.docker.internal') or p.username or p.password or p.query or p.fragment:
            raise ValueError('Use uma URL local: localhost, 127.0.0.1 ou host.docker.internal.')
        return value.rstrip('/')

    @field_validator('chat_path')
    @classmethod
    def relative_path(cls, value):
        if not value.startswith('/') or value.startswith('//') or '..' in value or '?' in value or '#' in value:
            raise ValueError('Informe somente um caminho absoluto local, como /api/chat.')
        return value
)


class AISettings(Strict):
    provider: Literal['murn','openai','ollama','custom','demo'] = 'murn'
    base_url: str = 'http://127.0.0.1:7331'
    model: str = Field(default='llama3.1:8b', min_length=1, max_length=200)
    chat_path: str = Field(default='/v1/chat', max_length=200)
    messages_field: str = Field(default='messages', pattern=r'^[A-Za-z_][A-Za-z0-9_]*$')
    response_path: str = Field(default='response', pattern=r'^[A-Za-z0-9_.]+$')
    api_key: str = Field(default='', max_length=2000)
    temperature: float = Field(default=0.7, ge=0, le=2)
    timeout: int = Field(default=120, ge=5, le=600)
    json_mode: bool = False
    embeddings: bool = False
    embedding_url: str = 'http://127.0.0.1:11434'
    embedding_model: str = Field(default='embeddinggemma', min_length=1, max_length=200)
    embedding_provider: Literal['ollama','openai'] = 'ollama'
    context_chars: int = Field(default=18000, ge=4000, le=60000)
    retrieval_limit: int = Field(default=12, ge=1, le=30)

    @field_validator('base_url','embedding_url')
    @classmethod
    def local_endpoint(cls, value):
        p = urlsplit(value)
        # Local desktop tool: prevent configuring arbitrary public HTTP fetches.
        if p.scheme not in ('http','https') or p.hostname not in ('localhost','127.0.0.1','::1','host.docker.internal') or p.username or p.password or p.query or p.fragment:
            raise ValueError('Use uma URL local: localhost, 127.0.0.1 ou host.docker.internal.')
        return value.rstrip('/')

    @field_validator('chat_path')
    @classmethod
    def relative_path(cls, value):
        if not value.startswith('/') or value.startswith('//') or '..' in value or '?' in value or '#' in value:
            raise ValueError('Informe somente um caminho absoluto local, como /api/chat.')
        return value
