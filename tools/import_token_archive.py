"""Extract protocol facts from two pinned public Workcell archives; no network or execution."""
from pathlib import Path
from hashlib import sha256
import argparse,json

PIN='b80bcecc1d30263662b985fc025b83233e07a173'
SOURCES={
 'df812867dc62a343019d99480dcc60ed0f8639a8e6c77b66dc8d8c7449421a86':'wc_mw0eydrg_0c8f2c.json',
 'f94a88ea55191172168add2c2e940fe2520ee7677b008b85dbfbf7dadd7d416c':'wc_mw0hwd2k_6d93f3.json',
}
def pack(value):return json.dumps(value,ensure_ascii=True,sort_keys=True,separators=(',',':')).encode()
def extract(raw):
 digest=sha256(raw).hexdigest()
 if digest not in SOURCES:raise ValueError('This importer accepts only the two documented immutable archives. It does not interpret arbitrary Workcell versions.')
 doc=json.loads(raw);out=[]
 for ci,case in enumerate(doc['cases']):
  token=next(a for a in case['artifacts'] if a['role']=='token')
  def snapshot(s):
   return {'block_hash':s['blockHash'],'block_height':s['blockHeight'],'held':s['targetTokens'],
    'credit':s['credit'],'pending':s['pending'],'reserved':s.get('reserved','0'),'liabilities':s['liabilities']}
  steps=[]
  for si,step in enumerate(case['steps']):
   transactions=[]
   for tid in step['txIds']:
    ti,t=next((i,t) for i,t in enumerate(case['transactions']) if t['id']==tid)
    transactions.append({'source_pointer':f'/cases/{ci}/transactions/{ti}/result','result':t['result']})
   steps.append({'id':f'step-{si}','operation':step['action']['kind'],'source_pointer':f'/cases/{ci}/steps/{si}',
    'before':snapshot(step['before']),'after':snapshot(step['after']),'transactions':transactions})
  out.append({'format':'agent-crash-lab/token-recording-v1','id':case['id'],'network':doc['network'],
   'source':{'kind':'third-party-public-archive','url':f'https://github.com/dotmantissa/workcell/blob/{PIN}/evidence/{SOURCES[digest]}',
    'sha256':digest,'case_pointer':f'/cases/{ci}','created_at':doc['createdAt']},
   'scope':{'single_owner_whole_vault':True,'closed_intervals':True,'meaning':'Review assumptions, not independently verified facts'},
   'asset':{'standard':'nep141','contract':token['accountId'],'sha256':token['sha256'],'code_hash':token['codeHash'],
    'deployed_before':token['deployedBefore'],'deployed_after':token['deployedAfter']},
   'vault':case['accounts']['target'],'steps':steps})
 return out
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('archive',type=Path);p.add_argument('--case',required=True);a=p.parse_args()
 try:
  if a.archive.stat().st_size>2*1024*1024:raise ValueError('Archive exceeds 2 MiB')
  found=next((x for x in extract(a.archive.read_bytes()) if x['id']==a.case),None)
  if found is None:raise ValueError('Case is not present in this pinned archive')
  print(pack(found).decode());return 0
 except (OSError,ValueError,KeyError,StopIteration) as e:print(json.dumps({'error':str(e)}));return 2
if __name__=='__main__':raise SystemExit(main())
