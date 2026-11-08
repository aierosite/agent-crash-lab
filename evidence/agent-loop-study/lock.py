from pathlib import Path
from hashlib import sha256
from datetime import datetime,timezone
import json

H=Path(__file__).resolve().parent
names=['actor.py','agent_tools.py','grader.py','assess_episode.py','test_controls.py','REGISTRATION.initial.json',
 'PRE-INFERENCE-AMENDMENT.json','SDK-SOURCE-CHECK.json','worker/Cargo.toml','worker/Cargo.lock','worker/src/main.rs',
 'inspector/token_policy.py','inspector/token_review.py','reference/LICENSE','reference/grade_school_math/dataset.py','reference/grade_school_math/data/test.jsonl']
record={'format':'agent-crash-lab/agent-loop-source-lock-v1','lockedAtUtc':datetime.now(timezone.utc).isoformat(),
 'beforeFirstModelCall':True,'registrationSha256':sha256((H/'REGISTRATION.json').read_bytes()).hexdigest(),
 'sources':{n:{'bytes':(H/n).stat().st_size,'sha256':sha256((H/n).read_bytes()).hexdigest()} for n in names},
 'preInferenceControls':'controls3.stderr.txt; seven tests passed. Scripted model doubles are not actual inference.',
 'controlHistory':'Original descriptor warnings fixed; second run had a test Unicode-escape expectation error, preserved before correction. Generic calculator example changed to7+5 before inference to avoid matching the first dataset problem.'}
(H/'LOCK.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({'lockedAtUtc':record['lockedAtUtc'],'sources':len(names),'firstModelCallMade':False}))
