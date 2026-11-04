"""Verify release bytes; --judge also runs all three offline acceptance suites."""
from pathlib import Path
import hashlib,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
def main():
    try:
        if sys.argv[1:] not in [[],['--judge']]:raise ValueError('Use --judge or no arguments')
        m=json.loads((ROOT/'RELEASE_MANIFEST.json').read_text(encoding='utf-8'));bad=[];runs=[]
        if m['format']!='agent-crash-lab/release-v1' or type(m['files']) is not dict or not m['files']:raise ValueError('Invalid manifest')
        for name,expected in m['files'].items():
            path=ROOT/name
            if not path.resolve().is_relative_to(ROOT) or path.is_symlink():raise ValueError('Unsafe release path')
            if not path.is_file():bad.append({'file':name,'error':'missing'});continue
            raw=path.read_bytes()
            if len(raw)!=expected['bytes'] or hashlib.sha256(raw).hexdigest()!=expected['sha256']:bad.append({'file':name,'error':'hash-or-size'})
        if '--judge' in sys.argv and not bad:
            for script in ['test_agent_crash_lab.py','test_workbench.py','verify_reserved.py']:
                r=subprocess.run([sys.executable,'-I','-S',str(ROOT/script)],cwd=ROOT,capture_output=True,timeout=60)
                runs.append({'suite':script,'exitCode':r.returncode,'error':r.stderr.decode(errors='replace')[-1200:] if r.returncode else ''})
        ok=not bad and all(r['exitCode']==0 for r in runs)
        print(json.dumps({'verified':ok,'checkedFiles':len(m['files']),'errors':bad,'judgeSuites':runs,'meaning':'Release consistency and requested offline checks; not signed authenticity or a production audit'}));return 0 if ok else 1
    except (OSError,ValueError,KeyError,TypeError,subprocess.TimeoutExpired):print(json.dumps({'verified':False,'error':'Invalid manifest, arguments or incomplete checks'}));return 2
if __name__=='__main__':raise SystemExit(main())
