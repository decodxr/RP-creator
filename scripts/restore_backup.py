"""Restore a trusted RP creator backup into a NEW directory, never overwrite a world."""
import argparse
import sqlite3
import zipfile
from pathlib import Path


def restore(archive_path,destination):
    dest=Path(destination).resolve()
    if dest.exists() and any(dest.iterdir()):
        raise ValueError('A pasta de destino precisa estar vazia. Seu mundo atual não será sobrescrito.')
    with zipfile.ZipFile(archive_path) as archive:
        infos=archive.infolist()
        if sum(i.file_size for i in infos)>2*1024**3:
            raise ValueError('Backup excede 2 GiB descompactado.')
        for item in infos:
            p=Path(item.filename)
            if p.is_absolute() or '..' in p.parts or '\\' in item.filename:
                raise ValueError('Caminho inválido no backup.')
            if item.filename not in ('world.sqlite3','RESTORE.txt') and not (p.parts[0]=='vault' and p.suffix=='.md'):
                raise ValueError('Arquivo inesperado no backup.')
        payload=archive.read('world.sqlite3')
        db=sqlite3.connect(':memory:')
        try:
            db.deserialize(payload)
            db.execute('PRAGMA trusted_schema=OFF')
            if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise ValueError('Banco corrompido.')
            if db.execute('PRAGMA user_version').fetchone()[0]!=1: raise ValueError('Versão de banco não suportada.')
        finally: db.close()
        dest.mkdir(parents=True,exist_ok=True)
        (dest/'world.sqlite3').write_bytes(payload)
        for item in infos:
            if not item.filename.startswith('vault/'):continue
            p=dest/item.filename;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(archive.read(item))
    return dest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('backup');parser.add_argument('--data',required=True)
    args=parser.parse_args()
    try:print('Restaurado em:',restore(args.backup,args.data))
    except (ValueError,KeyError,sqlite3.Error,zipfile.BadZipFile) as exc:parser.exit(1,str(exc)+'\n')
