"""Verify release bytes. --judge also runs the offline acceptance suites."""
from pathlib import Path
from hashlib import sha256
import json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
def unique(pairs):
    value=dict(pairs)
    if len(value)!=len(pairs):
        raise ValueError('Duplicate manifest key')
    return value

def main():
    try:
        if sys.argv[1:] not in [[],['--judge']]:raise ValueError('Use --judge or no arguments')
        m=json.loads((ROOT/'RELEASE_MANIFEST.json').read_text('utf-8'),object_pairs_hook=unique)
        files=m['files'];bad=[];runs=[]
        if m['format']!='agent-crash-lab/release-v1' or type(files) is not dict:raise ValueError('Invalid manifest')
        names=json.dumps(sorted(files),separators=(',',':')).encode()
        if sha256(names).hexdigest()!='d7256a380286eca2a7b25cef8fb4b40b52c4f6bbe1a6b45ccba7d69b209d9806':
            raise ValueError('Release inventory mismatch')
        for name,expected in files.items():
            path=ROOT/name
            if path.resolve()!=path:raise ValueError('Unsafe release path')
            if not path.is_file():bad.append({'file':name,'error':'missing'});continue
            raw=path.read_bytes()
            if len(raw)!=expected['bytes'] or sha256(raw).hexdigest()!=expected['sha256']:bad.append({'file':name,'error':'hash-or-size'})
        if sys.argv[1:] and not bad:
            for script, *args in (('test_agent_crash_lab.py',),('test_workbench.py',),('verify_reserved.py',),('tools/verify_live_agent.py','--replay'),('test_scenario_lab.py',),('test_proposal_study.py',),('test_async_evidence.py',)):
                r=subprocess.run([sys.executable,'-I','-S',script,*args],cwd=ROOT,capture_output=True,timeout=60)
                runs.append({'suite':script,'exitCode':r.returncode,'error':r.stderr.decode(errors='replace')[-1200:] if r.returncode else ''})
        ok=not bad and all(r['exitCode']==0 for r in runs)
        print(json.dumps({'verified':ok,'checkedFiles':len(files),'errors':bad,'judgeSuites':runs,'meaning':'Release integrity and offline checks within declared scope'}));return int(not ok)
    except (OSError,ValueError,KeyError,TypeError,subprocess.TimeoutExpired) as e:
        print(json.dumps(dict(verified=False,error=str(e))))
        return 2
if __name__=='__main__':raise SystemExit(main())
