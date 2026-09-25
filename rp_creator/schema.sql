PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS campaigns (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, premise TEXT NOT NULL,
 player_name TEXT NOT NULL, player_profile TEXT NOT NULL DEFAULT '',
 time TEXT NOT NULL, location TEXT NOT NULL, realtime INTEGER NOT NULL DEFAULT 0,
 rate REAL NOT NULL DEFAULT 1, last_wall REAL NOT NULL, version INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS locations (
 id TEXT PRIMARY KEY, campaign TEXT NOT NULL REFERENCES campaigns(id), name TEXT NOT NULL,
 description TEXT NOT NULL, UNIQUE(campaign,name)
);
CREATE TABLE IF NOT EXISTS npcs (
 id TEXT PRIMARY KEY, campaign TEXT NOT NULL REFERENCES campaigns(id), name TEXT NOT NULL,
 profile TEXT NOT NULL, mood TEXT NOT NULL DEFAULT 'neutro', location TEXT NOT NULL,
 routine TEXT NOT NULL DEFAULT '[]', goals TEXT NOT NULL DEFAULT '[]', UNIQUE(campaign,name)
);
CREATE TABLE IF NOT EXISTS relationships (
 campaign TEXT NOT NULL REFERENCES campaigns(id), source TEXT NOT NULL, target TEXT NOT NULL,
 values_json TEXT NOT NULL, PRIMARY KEY(campaign,source,target)
);
CREATE TABLE IF NOT EXISTS memories (
 id TEXT PRIMARY KEY, campaign TEXT NOT NULL REFERENCES campaigns(id), kind TEXT NOT NULL,
 text TEXT NOT NULL, known_by TEXT NOT NULL, entities TEXT NOT NULL DEFAULT '[]',
 importance INTEGER NOT NULL DEFAULT 5, created TEXT NOT NULL, valid INTEGER NOT NULL DEFAULT 1,
 fact_key TEXT, source TEXT NOT NULL, evidence TEXT NOT NULL DEFAULT '',
 parents TEXT NOT NULL DEFAULT '[]', embedding TEXT, embedding_model TEXT,
 revision INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS memory_campaign ON memories(campaign,valid,created);
CREATE INDEX IF NOT EXISTS memory_fact ON memories(campaign,fact_key);
CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(text, content='memories', content_rowid='rowid', tokenize='unicode61 remove_diacritics 2');
CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
 INSERT INTO memory_fts(rowid,text) VALUES(new.rowid,new.text);
END;
CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
 INSERT INTO memory_fts(memory_fts,rowid,text) VALUES('delete',old.rowid,old.text);
END;
CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE OF text ON memories BEGIN
 INSERT INTO memory_fts(memory_fts,rowid,text) VALUES('delete',old.rowid,old.text);
 INSERT INTO memory_fts(rowid,text) VALUES(new.rowid,new.text);
END;
CREATE TABLE IF NOT EXISTS turns (
 id TEXT PRIMARY KEY, campaign TEXT NOT NULL REFERENCES campaigns(id), npc TEXT NOT NULL,
 request_id TEXT NOT NULL, user TEXT NOT NULL, response TEXT NOT NULL, created TEXT NOT NULL,
 recalled TEXT NOT NULL DEFAULT '[]', warning TEXT NOT NULL DEFAULT '', UNIQUE(campaign,request_id)
);
CREATE INDEX IF NOT EXISTS turn_history ON turns(campaign,npc,created);
CREATE TABLE IF NOT EXISTS events (
 id TEXT PRIMARY KEY, campaign TEXT NOT NULL REFERENCES campaigns(id), time TEXT NOT NULL,
 kind TEXT NOT NULL, text TEXT NOT NULL, known_by TEXT NOT NULL, entities TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS event_time ON events(campaign,time);
CREATE TABLE IF NOT EXISTS promises (
 id TEXT PRIMARY KEY, campaign TEXT NOT NULL REFERENCES campaigns(id), npc TEXT NOT NULL,
 text TEXT NOT NULL, due TEXT NOT NULL, location TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending', created TEXT NOT NULL, source TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS vault_files (
 path TEXT PRIMARY KEY, hash TEXT NOT NULL, memory_id TEXT, revision INTEGER
);
PRAGMA user_version=1;
