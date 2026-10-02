"""Local operator maintenance; stop Streamlit before changing or snapshotting stores."""
import argparse
import json
from pathlib import Path
import sqlite3

from health import runtime_health
import settings as cfg
from storage import Store,DATABASES,connection,tables


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['status','maintain','backup','restore'])
    parser.add_argument('--data',type=Path,default=cfg.DATA_ROOT)
    parser.add_argument('--backup',type=Path)
    parser.add_argument('--destination',type=Path)
    args=parser.parse_args()
    if args.command=='status':
        result=runtime_health();result['storage']={}
        for name in DATABASES:
            path=args.data/name
            if path.exists():
                with connection(path) as conn:
                    result['storage'][name]=dict(bytes=path.stat().st_size,
                        integrity=conn.execute('PRAGMA quick_check').fetchone()[0],
                        rows={table:conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                              for table in tables(conn) if not table.startswith('sqlite_')})
    else:
        store=Store(args.data)
        with store.acquire_runtime():
            if args.command=='maintain':result=store.maintain()
            elif args.command=='backup':result={'backup':str(store.backup())}
            else:
                if not args.backup or not args.destination:parser.error('restore requires --backup and --destination')
                result={'restored_to':str(store.restore_into(args.backup,args.destination).root)}
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
