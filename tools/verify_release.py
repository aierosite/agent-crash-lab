"""Check every release-manifest file. Consistency only, not an author signature."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1]
def main():
    try:
        m=json.loads((ROOT/'RELEASE_MANIFEST.json').read_text(encoding='utf-8'));bad=[]
        for name,expected in m['files'].items():
            path=ROOT/name
            if not path.is_file():bad.append({'file':name,'error':'missing'});continue
            raw=path.read_bytes()
            if len(raw)!=expected['bytes'] or hashlib.sha256(raw).hexdigest()!=expected['sha256']:bad.append({'file':name,'error':'hash-or-size'})
        print(json.dumps({'verified':not bad,'checkedFiles':len(m['files']),'errors':bad,'meaning':'Exact local release-file consistency, not an authenticated signature'}));return 1 if bad else 0
    except (OSError,ValueError,KeyError):print(json.dumps({'verified':False,'error':'Manifest unreadable or invalid'}));return 2
if __name__=='__main__':raise SystemExit(main())
