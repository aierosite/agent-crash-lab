from pathlib import Path
from hashlib import sha256
from datetime import datetime,timezone
import json
H=Path(__file__).resolve().parent;old=H.parent/'native-required-study-v015/actor.py';source=old.read_text(encoding='utf-8');edits=[
 ('from native_loop import Sdk,Merchant,serve,pack,decode,drive,TOOLS','from bank_loop import Sdk,Merchant,serve,pack,decode,drive,TOOLS'),
 ("'maxEvaluationCalls'", "'maxEvaluationCalls'"),
 ("crash-lab-agent-loop-sdk","crash-lab-banking-sdk"),
 ("digest(sdk_binary)==plan['sdk']['binarySha256']", "digest(sdk_binary)==decode((H/'BUILD.json').read_bytes())['sdkBinarySha256']"),
 ("sdk=Sdk(sdk_binary,sdk_log);questions=decode((H/'questions.json').read_bytes());assert all(set(x)=={'question'} for x in questions) and len(questions)==6\n  merchant=Merchant(sdk,questions)","sdk=Sdk(sdk_binary,sdk_log)\n  merchant=Merchant(sdk)")]
changes=[]
for before,after in edits:
 if before==after:continue
 n=source.count(before);assert n==1,(before,n);source=source.replace(before,after);changes.append({'before':before,'after':after})
assert not (H/'actor.py').exists();(H/'actor.py').write_text(source,encoding='utf-8',newline='\n')
(H/'ACTOR-ADAPTATION.json').write_text(json.dumps({'atUtc':datetime.now(timezone.utc).isoformat(),'baseSource':'native-required-study-v015/actor.py','baseSha256':sha256(old.read_bytes()).hexdigest(),'edits':changes,'requestMode':'required','fullPromptPreserved':True,'modelResponsesRepaired':False},indent=2)+'\n',encoding='utf-8')
print(json.dumps({'actorPrepared':True,'changes':len(changes),'inferenceCalls':0}))
