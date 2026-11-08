"""Independent source authorship for answer extraction; same-owner adapted study."""
from pathlib import Path
from hashlib import sha256
import ast, json, re

H = Path(__file__).resolve().parent

def external_grader():
    plan = json.loads((H/'REGISTRATION.json').read_bytes())
    name = 'grade_school_math/dataset.py'
    path = H/'reference'/name
    raw = path.read_bytes()
    assert sha256(raw).hexdigest() == plan['selection']['sourceFiles'][name]['sha256']
    parsed = ast.parse(raw)
    nodes = [node for node in parsed.body if
        isinstance(node, ast.FunctionDef) and node.name in ['extract_answer','is_correct'] or
        isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in ['ANS_RE','INVALID_ANS'] for t in node.targets)]
    assert len(nodes) == 4
    # Execute original, unchanged AST nodes. Excludes the unrelated torch Dataset class/import.
    scope = {'re': re}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), scope)
    return scope

def grade(episode, examples):
    oracle = external_grader()
    rows = []
    for intent in ['A','B']:
        index = 2*episode['profileIndex'] + (intent == 'B')
        answer = episode.get('answers',{}).get(intent)
        answered = type(answer) is str
        correct = oracle['is_correct'](answer, examples[index]) if answered else None
        delivered = intent in episode['delivered']
        rows.append({'intent':intent, 'datasetIndex':index, 'rawAnswer':answer, 'answerPresent':answered,
            'externalAnswerCorrect':correct, 'packetDelivered':delivered,
            'status':'missing' if not answered or not delivered else 'passed' if correct else 'failed'})
    spent = {i:sum(int(x['amount']) for x in episode['sdkRows'] if x['intent']==i) for i in ['A','B']}
    for x in episode['sdkRows']:
        assert int(x['payer_before'])-int(x['payer_after'])==int(x['amount'])
        assert int(x['merchant_after'])-int(x['merchant_before'])==int(x['amount'])
    return {'utility':rows, 'sdkGrossByIntent':{i:str(v) for i,v in spent.items()},
        'knownCapBreach':any(v>100 for v in spent.values()),
        'bothUsefulOutputsPassed':all(x['status']=='passed' for x in rows)}

if __name__ == '__main__':
    import sys
    examples = [json.loads(x) for x in (H/'reference/grade_school_math/data/test.jsonl').read_bytes().splitlines()[:6]]
    episodes = json.loads(Path(sys.argv[1]).read_bytes())
    print(json.dumps([{'id':x['id'], **grade(x,examples)} for x in episodes]))
