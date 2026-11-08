"""Separate declared-ledger diagnostic over the unchanged v2 custody primitive."""
from pathlib import Path
from hashlib import sha256
import argparse,runpy

ROOT=Path(__file__).resolve().parent
BASE=runpy.run_path(str(ROOT/'token_review.py'))
pack=BASE['pack']
ReviewError=BASE['ReviewError']

def review(raw):
    result=BASE['review'](raw)
    result['format']='agent-crash-lab/token-review-v3'
    result['base_assessor_sha256']=result['assessor_sha256']
    result['assessor_sha256']=sha256(Path(__file__).read_bytes()).hexdigest()
    declared=BASE['decode'](raw)['scope']['single_owner_whole_vault']
    for step in result['steps']:
        differences=[sum(int(s[k]) for k in ['credit','pending','reserved'])-int(s['liabilities']) for s in [step['before'],step['after']]]
        step['reported_ledger']={'status':'not-declared' if not declared else 'conflict' if any(differences) else 'matches','before_difference':str(differences[0]),'after_difference':str(differences[1])}
        if not declared:
            step['reasons']=[r for r in step['reasons'] if r!='The reported total liability does not equal this single-owner ledger.']
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('recording',type=Path);args=parser.parse_args()
    try:print(pack(review(args.recording.read_bytes())).decode('utf8'));return 0
    except (ReviewError,OSError) as e:parser.exit(2,str(e)+'\n')

if __name__=='__main__':raise SystemExit(main())
