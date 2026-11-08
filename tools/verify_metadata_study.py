"""Offline raw-link, projection and metadata replay of selected original records.

Does not start models/SDKs or rerun external typed task predicates. Those saved
predicate results remain explicitly recorded observations, not fresh execution.
"""
from pathlib import Path
from hashlib import sha256
import ast,base64,csv,io,json,runpy
ROOT=Path(__file__).resolve().parents[1]
ARCHIVE=ROOT/'evidence/metadata-study/archive'
INDEX_SHA='0c67e8bf73ba4bfa98d518355fe1b518f902ef59c14fd492fcb8758f4ad8a9ea'
REGISTRATION_SHA='c7caaf5810e3996e22c16bfda0d52ca5a9b91f77624ba694f46316277aa60fd6'
load=lambda p:json.loads(p.read_bytes())
pack=lambda v:json.dumps(v,ensure_ascii=True,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')

def raw_link(row,field,digest):
    value=row[field].encode('utf-8');assert sha256(value).hexdigest()==row[digest],field
    return value

def original_functions(path,names,globals_):
    """Execute only named, unchanged source AST bodies; no framework imports."""
    tree=ast.parse(path.read_bytes());nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    assert {n.name for n in nodes}==set(names)
    namespace=dict(globals_);exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),namespace)
    return namespace

def verify():
    selection=load(ROOT/'evidence/metadata-study/SELECTION.json');index=load(ARCHIVE/'RESULT-INDEX.json')
    assert sha256((ARCHIVE/'RESULT-INDEX.json').read_bytes()).hexdigest()==INDEX_SHA==selection['originalIndexSha256']
    assert sha256((ARCHIVE/'REGISTRATION.json').read_bytes()).hexdigest()==REGISTRATION_SHA==selection['originalRegistrationSha256']
    for name,expected in selection['selected'].items():
        path=(ARCHIVE/name).resolve();assert path.is_relative_to(ARCHIVE.resolve())
        raw=path.read_bytes();assert len(raw)==expected['bytes'] and sha256(raw).hexdigest()==expected['sha256'],name
        if name!='RESULT-INDEX.json':assert expected==index['files'][name]
    lock=load(ARCHIVE/'LOCK.json');assert lock['registrationSha256']==REGISTRATION_SHA
    assert all(selection['selected'][n]==v for n,v in lock['sources'].items() if n in selection['selected'])
    protocol=runpy.run_path(str(ARCHIVE/'protocol.py'));spec=protocol['SPEC'];plan=load(ARCHIVE/'REGISTRATION.json')
    assert plan['cases']==spec['cases'] and len(plan['cases'])==32
    execution=load(ARCHIVE/'actual/execution.json');statuses=load(ARCHIVE/'actual/statuses.json')
    assert execution['terminal'] and execution['sourcesUnchanged']
    assert {k:sum(s['state']==k for s in statuses.values()) for k in ['closed','partial','unstarted']}=={'closed':27,'partial':1,'unstarted':4}
    episodes=load(ARCHIVE/'actual/episodes.json');calls=load(ARCHIVE/'actual/calls.json');wire=load(ARCHIVE/'actual/sdk-wire.json')
    assert len(episodes)==28 and [c['id'] for c in calls]==list(range(193))
    assert sum(c.get('response',{}).get('httpStatus')==200 for c in calls)==192
    grades={r['id']:r for r in load(ARCHIVE/'AUDIT.post-lock.json')['grades']}
    samples=load(ROOT/'verification/metadata-review/samples.json');bindings=load(ROOT/'verification/metadata-review/RECORDED-BINDINGS.json')
    bindings={b['episode']:b for b in bindings};samples_by_id={s['id']:s for s in samples}
    coverage=list(csv.DictReader(io.StringIO((ARCHIVE/'CASES.csv').read_text('utf-8-sig'))));assert len(coverage)==32
    projection=original_functions(ROOT/'verification/metadata-review/development/original-projection.py.txt',['project','inputs'],{'SPEC':spec,'sha256':sha256,'pack':pack})
    reference=original_functions(ARCHIVE/'grade.py',['metadata_violations','payment_bundle'],{'SPEC':spec,'sha256':sha256,'pack':pack,'base64':base64})
    metadata=runpy.run_path(str(ROOT/'state_review.py'));financial=runpy.run_path(str(ROOT/'token_policy.py'))
    used=set();reports=[];physical=[]
    for e in episodes:
        assert e['id'] in statuses and statuses[e['id']]['state']==('closed' if e['executionComplete'] else 'partial')
        assert all(e[k]==v for k,v in next(p for p in plan['cases'] if p['id']==e['id']).items())
        previous=e['preState'];events={str(v['callId']):v for v in e['hostEvents']};assert len(events)==len(e['hostEvents'])
        for event in e['hostEvents']:
            assert event['beforeState']==previous;previous=event['afterState']
            raw_link(event,'requestUtf8','requestSha256');raw_link(event,'responseUtf8','responseSha256')
        assert previous==e['postState']
        links=[e['prefetch']]+[s for s in e['steps'] if 'requestUtf8' in s]
        assert len(links)==len(events)
        for link in links:
            raw_link(link,'requestUtf8','requestSha256');raw_link(link,'responseUtf8','responseSha256')
            assert any(all(v[k]==link[k] for k in ['requestUtf8','responseUtf8','httpStatus']) for v in events.values())
        messages=protocol['initial_messages'](e['task'],e['prefetch'])
        assert sha256(messages[2]['content'].encode()).hexdigest()==e['prefetchMessageSha256']
        for step in e['steps']:
            call=calls[step['modelCallId']];assert call['id'] not in used and call['case']==e['id'] and call['turn']==step['turn'];used.add(call['id'])
            request=json.loads(raw_link(call,'wireRequestUtf8','requestSha256'))
            assert request=={'prompt':protocol['render'](messages),'grammar':protocol['GRAMMAR'],'temperature':.2,'seed':e['seed'],'n_predict':plan['limits']['generatedTokens'],'cache_prompt':False,'stop':['<|im_end|>']}
            if call.get('response',{}).get('httpStatus')!=200:
                assert step.get('unexecuted') and 'requestUtf8' not in step;continue
            response=call['response'];raw_link(response,'responseUtf8','responseSha256');assert response['requestSha256']==call['requestSha256']
            returned=json.loads(response['responseUtf8']);assert returned['content']==call['content']==step['rawToolUtf8']
            if 'requestUtf8' not in step:
                assert step.get('unexecuted') or step.get('protocolError');continue
            assert step['requestUtf8']==returned['content']
            event=events[str(call['id'])]
            assert all(event[k]==step[k] for k in ['requestUtf8','requestSha256','responseUtf8','responseSha256','httpStatus'])
            messages += [{'role':'assistant','content':returned['content']},{'role':'user','content':pack({'http_status':step['httpStatus'],'response':json.loads(step['responseUtf8'])}).decode()}]
        if e['executionComplete']:assert messages==e['messages']
        authority,capture=projection['inputs'](e);binding=bindings[e['id']];sample=samples_by_id[binding['sample']]
        assert sha256(authority).hexdigest()==binding['authoritySha256'] and sha256(capture).hexdigest()==binding['captureSha256']
        bundle=load(ROOT/sample['path']);assert bundle['authority_utf8'].encode()==authority and bundle['capture_utf8'].encode()==capture
        result=metadata['assess'](authority,capture)
        assert (result['authority_gate']==1)==bool(reference['metadata_violations'](e))
        task,evidence=reference['payment_bundle'](e)
        assert financial['assess'](pack(task),pack(evidence))==grades[e['id']]['financialReport']
        context=sample['context'];g=grades[e['id']]
        assert context['episode']==e['id'] and context['caseStatus']==statuses[e['id']]['state']
        assert all(context[k]==e[k] for k in ['model','task','policy','profile'])
        assert context['originalTaskStatus']==('met' if g['originalTaskCriterionMet'] else 'unmet' if e['executionComplete'] else 'unknown')
        assert context['paymentGate']==g['financialGate'] and context['finishObserved']==e['finished']==g['communicationFinished']
        reports.append({'id':sample['id'],'report':result});physical.extend(e['sdkRows'])
    assert used==set(range(193))
    pays=[r for r in wire if json.loads(r['requestUtf8'])['op']=='pay']
    assert len(pays)==len(physical)==45
    for request,row in zip(pays,physical):
        assert request['state']=='complete' and json.loads(request['responseUtf8'])==row
        assert json.loads(request['requestUtf8'])=={'op':'pay','case':row['case'],'id':row['id'],'receiver':row['receiver'],'amount':row['amount'],'memo':row['args']['memo']}
    return {'verified':True,'planned':32,'closed':27,'partial':1,'unstarted':4,'originalRawModelAttemptsChecked':193,'returnedResponsesChecked':192,
            'originalSdkMockPaymentLinksChecked':45,'metadataReportsReplayed':28,'wholeSavedFinancialReportsMatched':28,
            'newModelCalls':0,'newSdkCalls':0,'newTransactions':0,'independentBlindEvaluation':False,
            'externalTaskPredicatesFreshlyExecuted':False,'reportObjects':reports,
            'scope':'Original raw byte links/prompt chains and unchanged source projection functions are checked; metadata and whole financial reports are replayed. Saved external typed-task predicate values are retained, not freshly rerun. No current model/SDK/chain execution or authenticity proof.'}

if __name__=='__main__':
    result=verify();print(json.dumps({k:v for k,v in result.items() if k!='reportObjects'}))
