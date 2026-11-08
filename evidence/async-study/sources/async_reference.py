"""Original plan-level reference for partial native-effect evidence, no assessor imports."""
import json,sys
from pathlib import Path

def reference(plan):
    seen=set();conflict=plan['family']=='conflicting-leaf'
    for view in plan['views']:
        if view['wholeFinal']:seen.update(view['leaves'])
        else:seen.update(leaf for leaf in view['leaves'] if leaf in plan['anchoredLeaves'])
    amount=0 if conflict else sum(plan['amounts'][leaf] for leaf in seen)
    complete=plan['closedHorizon'] and not conflict and any(view['wholeFinal'] for view in plan['views'])
    status='conflict' if conflict else 'breached' if amount>plan['cap'] else 'within' if complete else 'unknown'
    count=int(amount>0)
    return {'A-merchant':{'known_subtotal':str(amount),'exact_total':str(amount) if complete else None,'status':status},
            'A-count':{'known_subtotal':str(count),'exact_total':str(count) if complete else None,
                       'status':'conflict' if conflict else 'within' if complete else 'unknown'},
            'B-merchant':{'known_subtotal':'3','exact_total':'3' if plan['closedHorizon'] else None,
                          'status':'within' if plan['closedHorizon'] else 'unknown'},
            'B-count':{'known_subtotal':'1','exact_total':'1' if plan['closedHorizon'] else None,
                       'status':'within' if plan['closedHorizon'] else 'unknown'}}

if __name__=='__main__':
    plan=json.loads(Path(sys.argv[1]).read_bytes());print(json.dumps(reference(plan)))
