"""Strict CI gate: 0 within+useful, 1 observed breach/failure, 2 inconclusive/rejected."""
from pathlib import Path
from runpy import run_path
import argparse,sys
app=run_path(str(Path(__file__).resolve().with_name('workbench.py')))
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',required=True);a=p.parse_args()
    try:
        with open(a.bundle,'rb') as f:raw=f.read(app['MAX_BODY']+1)
        if len(raw)>app['MAX_BODY']:raise ValueError
        out=app['assess_bundle'](app['decode'](raw))
        code=app['gate'](out['report']);out['gate']={'exitCode':code,'meaning':{0:'within-declared-scope-and-required-output-passed',1:'observed-breach-or-required-output-failed',2:'inconclusive-or-rejected'}[code]}
        sys.stdout.buffer.write(app['compact'](out)+b'\n');return code
    except (OSError,ValueError,KeyError,AttributeError,TypeError,RecursionError):
        print('{"gate": {"exitCode": 2, "meaning": "invalid-or-unreadable-bundle"}}');return 2
if __name__=='__main__':raise SystemExit(main())
