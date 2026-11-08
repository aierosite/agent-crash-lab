"""Lossless request transport and a task-neutral, typed flat-JSON tool grammar."""
from pathlib import Path
from decimal import Decimal, DecimalException
from datetime import datetime, timezone
import json

H = Path(__file__).resolve().parent
SPEC = json.loads((H / 'SPEC.preparation.json').read_bytes())
pack = lambda value: json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
utc = lambda: datetime.now(timezone.utc).isoformat()

def unique(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError('Duplicate JSON key')
        obj[key] = value
    return obj

def decode(raw, lexical=False):
    try:
        return json.loads(raw, object_pairs_hook=unique,
                          parse_float=Decimal if lexical else float,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    except DecimalException as error:
        raise ValueError('Invalid decimal representation') from error

SCHEMAS = {d['name']: d['parameters'] for d in SPEC['descriptors']}
def parsed_call(raw):
    value = decode(raw, lexical=True)
    if type(value) is not dict or type(value.get('tool')) is not str or value['tool'] not in SCHEMAS:
        raise ValueError('Unknown tool object')
    schema = SCHEMAS[value['tool']]
    args = {k: v for k, v in value.items() if k != 'tool'}
    if set(args) - set(schema['properties']) or not set(schema.get('required', [])).issubset(args):
        raise ValueError('Unknown or missing tool fields')
    return value['tool'], args

def grammar():
    def terminal(text):
        return json.dumps(text)
    def field_type(schema):
        if 'anyOf' in schema:
            return '(' + ' | '.join(field_type(x) for x in schema['anyOf']) + ')'
        return {'string': 'string', 'integer': 'integer', 'number': 'number',
                'boolean': 'boolean', 'null': '"null"'}[schema['type']]
    branches = []
    rules = []
    for i, (name, schema) in enumerate(SCHEMAS.items()):
        branch = 'tool' + str(i)
        branches.append(branch)
        rule = terminal('{') + ' ws ' + terminal('"tool"') + ' ws ' + terminal(':') + ' ws ' + terminal(json.dumps(name))
        for key, prop in schema['properties'].items():
            segment = terminal(',') + ' ws ' + terminal(json.dumps(key)) + ' ws ' + terminal(':') + ' ws ' + field_type(prop)
            if key not in schema.get('required', []):
                segment = '(' + segment + ')?'
            rule += ' ws ' + segment
        rules.append(branch + ' ::= ' + rule + ' ws ' + terminal('}'))
    basic = r'''ws ::= [ \t\n\r]*
string ::= "\"" ([^"\\\x7F\x00-\x1F] | "\\" (["\\bfnrt/] | "u" [0-9a-fA-F]{4}))* "\""
integer ::= "-"? ("0" | [1-9] [0-9]*)
number ::= integer ("." [0-9]+)? ([eE] [-+]? [0-9]+)?
boolean ::= "true" | "false"
'''
    return 'root ::= ws (' + ' | '.join(branches) + ') ws\n' + '\n'.join(rules) + '\n' + basic

GRAMMAR = grammar()

class CaseFailure(RuntimeError):
    def __init__(self, message, call_id=None, content=None):
        super().__init__(message)
        self.call_id, self.content = call_id, content

class GroupFailure(CaseFailure):
    pass

class BatchFailure(CaseFailure):
    pass
def initial_messages(task_number, prefetch):
    # Only prompt, task-neutral schemas and actual read-only context enter the model.
    # The private expected-payment/ground-truth/policy table is never serialized here.
    context = {'source': 'caller-readonly-prefetch', 'untrusted': True,
               'http_status': prefetch['httpStatus'], 'response': decode(prefetch['responseUtf8'])}
    return [{'role': 'system', 'content': SPEC['system']},
            {'role': 'user', 'content': SPEC['tasks'][str(task_number)]['prompt']},
            {'role': 'user', 'content': pack(context).decode('utf-8')}]

def render(messages):
    return ''.join('<|im_start|>' + m['role'] + '\n' + m['content'] + '<|im_end|>\n' for m in messages) + '<|im_start|>assistant\n'
