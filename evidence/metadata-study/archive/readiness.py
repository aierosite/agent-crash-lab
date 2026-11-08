"""Cold-start/props/tokenizer checks only. No completion endpoint or warmup."""
from pathlib import Path
import json, sys, traceback
H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
from protocol import SPEC, pack, render, initial_messages, utc
from model_client import Model, proxy

def main():
    attempt = len(list(H.glob('readiness-attempt-*'))) + 1
    out = H / ('readiness-attempt-' + str(attempt))
    out.mkdir(exist_ok=False)
    episodes = json.loads((H / 'preflight-attempt-2/episodes.json').read_bytes())
    contexts = [x['episode'] for x in episodes if '/context-construction/' in x['episode']['id']]
    assert len(contexts) == 8
    rows, errors = [], []
    for model_id in ['qwen-1.5b', 'qwen-0.5b']:
        model = None
        row = {'model': model_id, 'startedAtUtc': utc(), 'tokenizations': []}
        with (out / (model_id + '-supervisor.log')).open('wb') as log:
            try:
                model = Model(model_id, f'readiness-{attempt}-' + model_id.replace('.', '-'), log, 130)
                row['process'] = model.metadata
                row['properties'] = model.wait_ready()
                for episode in contexts:
                    prompt = render(initial_messages(episode['task'], episode['prefetch']))
                    response = proxy(model.port, 'POST', '/tokenize', pack({'content': prompt, 'add_special': False, 'parse_special': True}), 15)
                    assert response['httpStatus'] == 200
                    tokens = json.loads(response['responseUtf8'])['tokens']
                    assert 0 < len(tokens) <= 11800
                    row['tokenizations'].append({'task': episode['task'], 'profile': episode['profile'],
                                                 'promptTokens': len(tokens), 'raw': response})
            except BaseException as error:
                errors.append({'model': model_id, 'error': type(error).__name__ + ': ' + str(error), 'traceback': traceback.format_exc()})
            finally:
                if model:
                    row.update(healthPolls=model.ready, shutdown=model.close())
                row['finishedAtUtc'] = utc()
                rows.append(row)
                (out / 'results.json').write_bytes(pack(rows) + b'\n')
    (out / 'errors.json').write_bytes(pack(errors) + b'\n')
    summary = {'atUtc': utc(), 'passed': not errors, 'models': len(rows),
               'tokenizedInitialContexts': sum(len(r['tokenizations']) for r in rows),
               'completionRequests': 0, 'errors': len(errors), 'warmupRequests': 0,
               'allModelShutdownReceipts': all(r.get('shutdown', {}).get('stopped') for r in rows)}
    (out / 'SUMMARY.json').write_bytes(pack(summary) + b'\n')
    print(json.dumps(summary))
    return int(bool(errors))

if __name__ == '__main__':
    raise SystemExit(main())
