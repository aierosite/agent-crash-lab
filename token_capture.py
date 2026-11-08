"""Preserve caller-supplied RPC bytes and build an offline token-policy input. No network I/O."""
from pathlib import Path
from hashlib import sha256
import argparse,json,runpy,sys

ROOT=Path(__file__).resolve().parent
POLICY=runpy.run_path(str(ROOT/'token_policy.py'));decode=POLICY['decode'];pack=POLICY['pack']
MAX_FILE=2*1024*1024;MAX_TOTAL=8*1024*1024;MAX_RECORDS=128
TEMPLATE_KEYS={'format','profile','authority','network','token_contract','payer','closed_horizon','horizon_note','intents','bindings'}

class CaptureError(ValueError):pass
def need(ok,message):
 if not ok:raise CaptureError(message)
def exact(value,keys,message):need(type(value) is dict and set(value)==set(keys),message)
def read(path,limit=MAX_FILE):
 with Path(path).open('rb') as stream:raw=stream.read(limit+1)
 need(len(raw)<=limit,'A capture input exceeds the byte limit.');return raw
def descriptor(name,raw):return {'file':name,'bytes':len(raw),'sha256':sha256(raw).hexdigest()}
def validate_source(source):
 exact(source,['kind','note'],'Declare source kind and note explicitly.')
 need(source['kind'] in ['synthetic','owner-recording','public-archival-rpc'] and type(source['note']) is str and 0<len(source['note'])<=2048,'Use a supported source claim and a note within 2048 characters.')
def validate_records(records):
 need(type(records) is list and len(records)<=MAX_RECORDS,'Supply at most 128 observation pairs.')
 seen=set();total=0
 for row in records:
  need(type(row) is tuple and len(row)==3,'Each observation needs an ID and exact request/response bytes.')
  key,request,response=row;need(type(key) is str and 0<len(key)<=96 and key not in seen,'Observation IDs must be unique and within 96 characters.');seen.add(key)
  for raw in [request,response]:need(type(raw) is bytes and len(raw)<=MAX_FILE,'Each raw input must be bytes within 2 MiB.');total+=len(raw)
 need(total<=MAX_TOTAL,'Combined raw observations exceed 8 MiB.');return total

def assemble(template_raw,source,records):
 """Interpret a declared subset without discarding its unparsed raw members."""
 template=decode(template_raw);exact(template,TEMPLATE_KEYS,'Policy template has missing or extra fields.')
 need(template['format']=='agent-crash-lab/token-policy-template-v1','Use token-policy-template-v1; do not rebind an existing sealed task implicitly.')
 need(type(template['closed_horizon']) is bool and type(template['horizon_note']) is str,'Declare a finite horizon and note explicitly.')
 observations=[];supported=[];uninterpreted=[]
 for index,(key,request_raw,response_raw) in enumerate(records):
  try:
   request=decode(request_raw);response=decode(response_raw)
   need(type(request) is dict and type(request.get('params')) is dict and type(response) is dict,'An observation requires request/response objects with named parameters.')
   tx=request['params'].get('tx_hash');need(type(tx) is str and 0<len(tx)<=96,'Transaction identity is missing or unbounded.')
  except (ValueError,KeyError,TypeError) as error:
   uninterpreted.append({'capture_index':index,'id':key,'reason':str(error)[:512]});continue
  supported.append({'capture_index':index,'observation_index':len(observations),'id':key})
  observations.append({'id':key,'request':request,'response':response})
 mapped_source=dict(source);horizon=template['closed_horizon'];note=template['horizon_note']
 if uninterpreted:
  horizon=False;suffix=' Capture adapter forced an open horizon: '+str(len(uninterpreted))+' raw observation pair(s) could not be interpreted.'
  note=note+suffix if len(note+suffix)<=2048 else 'Original horizon note retained in policy-template.json.'+suffix
  suffix=' Capture adapter supplied only '+str(len(supported))+' of '+str(len(records))+' parsed pairs; all original raw pairs remain in the capture directory.'
  mapped_source['note']=source['note']+suffix if len(source['note']+suffix)<=2048 else 'Original source note retained in capture.json.'+suffix
 evidence={'format':'agent-crash-lab/token-execution-v1','network':template['network'],'source':mapped_source,'observations':observations};evidence_raw=pack(evidence)
 task={**template,'format':'agent-crash-lab/token-task-v1','evidence_sha256':sha256(evidence_raw).hexdigest(),'closed_horizon':horizon,'horizon_note':note};task_raw=pack(task)
 report=POLICY['assess'](task_raw,evidence_raw)
 need(not uninterpreted or report['gate'] in [1,2],'Incomplete raw capture must not produce a clean gate.')
 need(len(pack(report))<=MAX_FILE,'The assessment report exceeds 2 MiB; raw capture remains available.')
 bundle=pack({'format':'agent-crash-lab/token-policy-bundle-v1','task_utf8':task_raw.decode('utf-8'),'evidence_utf8':evidence_raw.decode('utf-8')})
 need(len(bundle)<=MAX_FILE,'The generated policy bundle exceeds 2 MiB; raw capture remains available.')
 return report,bundle,supported,uninterpreted,horizon

def review(directory):
 root=Path(directory);need(root.is_dir() and not root.is_symlink(),'Choose a real capture directory, not a symlink.');root=root.resolve()
 index_path=root/'capture.json';need(index_path.resolve()==index_path and not index_path.is_symlink(),'Capture index must not be a symlink.')
 header_raw=read(index_path);header=decode(header_raw);exact(header,['format','source','policy','records'],'Capture index has missing or extra fields.')
 need(header['format']=='agent-crash-lab/token-capture-v1','Unsupported capture format.');validate_source(header['source'])
 need(type(header['records']) is list and len(header['records'])<=MAX_RECORDS,'Capture observation quota exceeded.')
 consumed=0
 def original(meta,expected):
  nonlocal consumed
  exact(meta,['file','bytes','sha256'],'A raw file descriptor is malformed.');need(meta['file']==expected,'Capture file path is not the expected generated path.')
  need(type(meta['bytes']) is int and 0<=meta['bytes']<=MAX_FILE and type(meta['sha256']) is str and len(meta['sha256'])==64,'A raw file size or fingerprint is malformed.')
  path=root/expected;need(path.resolve()==path and path.is_file() and not path.is_symlink(),'A declared raw file is absent or passes through a symlink.')
  need(consumed+meta['bytes']<=MAX_TOTAL,'Combined capture exceeds 8 MiB.')
  raw=read(path);need(len(raw)==meta['bytes'] and sha256(raw).hexdigest()==meta['sha256'],'Original raw bytes changed: '+expected);consumed+=len(raw);return raw
 template=original(header['policy'],'policy-template.json');records=[]
 for index,row in enumerate(header['records']):
  exact(row,['id','request','response'],'An observation descriptor is malformed.')
  records.append((row['id'],original(row['request'],f'raw/{index:03d}-request.json'),original(row['response'],f'raw/{index:03d}-response.json')))
 total=validate_records(records);need(total+len(template)<=MAX_TOTAL,'Combined capture exceeds 8 MiB.')
 report=bundle=None;supported=[];uninterpreted=[];effective_horizon=None;error=None
 try:report,bundle,supported,uninterpreted,effective_horizon=assemble(template,header['source'],records)
 except (ValueError,KeyError,TypeError) as failure:error=str(failure)[:512]
 exported=root/'payment-bundle.json'
 if exported.exists() or exported.is_symlink():
  need(exported.resolve()==exported and not exported.is_symlink() and bundle is not None and read(exported)==bundle,'Stored export differs from rebuilt raw capture or is not supported.')
 result={'format':'agent-crash-lab/token-capture-review-v1','capture_sha256':sha256(header_raw).hexdigest(),'reader_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
  'source_integrity':{'raw_files_checked':1+2*len(records),'raw_bytes_checked':total+len(template),'matched':True,'authenticity':'not assessed; fingerprints bind supplied files, not their origin or consensus'},
  'source':header['source'],'supported_records':supported,'uninterpreted_records':uninterpreted,
  'effective_closed_horizon':effective_horizon,'assessment_accepted':report is not None,'assessment_error':error,'gate':report['gate'] if report is not None else 2,'assessment':report,
  'new_transactions':0,'network_requests':0,'meaning':'Passive supplied-byte capture and conditional existing-profile assessment. Raw unsupported replies are retained; an incomplete capture cannot establish a clean gate. Useful work remains separate.'}
 return result,bundle

def create(directory,template_raw,source,records):
 validate_source(source);total=validate_records(records);need(type(template_raw) is bytes and len(template_raw)<=MAX_FILE and total+len(template_raw)<=MAX_TOTAL,'The policy or combined raw capture exceeds its byte limit.')
 root=Path(directory);need(not root.exists() and not root.is_symlink(),'Output directory already exists; choose a new path. Existing data was not changed.')
 root.mkdir(parents=False,exist_ok=False);(root/'raw').mkdir();(root/'policy-template.json').write_bytes(template_raw);rows=[]
 for index,(key,request,response) in enumerate(records):
  names=[f'raw/{index:03d}-request.json',f'raw/{index:03d}-response.json']
  for name,raw in zip(names,[request,response]):(root/name).write_bytes(raw)
  rows.append({'id':key,'request':descriptor(names[0],request),'response':descriptor(names[1],response)})
 header={'format':'agent-crash-lab/token-capture-v1','source':source,'policy':descriptor('policy-template.json',template_raw),'records':rows};(root/'capture.json').write_bytes(pack(header))
 result,bundle=review(root)
 if bundle is not None:
  with (root/'payment-bundle.json').open('xb') as stream:stream.write(bundle)
 return result

def main(argv=None):
 parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
 make=sub.add_parser('create',help='Preserve supplied raw files in a new directory; print its current 0/1/2 assessment.')
 make.add_argument('--policy',type=Path,required=True);make.add_argument('--source-kind',choices=['synthetic','owner-recording','public-archival-rpc'],required=True);make.add_argument('--source-note',required=True)
 make.add_argument('--observation',nargs=3,action='append',default=[],metavar=('ID','REQUEST_FILE','RESPONSE_FILE'));make.add_argument('--output',type=Path,required=True)
 check=sub.add_parser('check',help='Rebuild from original bytes; detect changed raw files and exports.');check.add_argument('directory',type=Path)
 args=parser.parse_args(argv)
 try:
  if args.command=='create':
   template=read(args.policy);records=[];remaining=MAX_TOTAL-len(template)
   need(len(args.observation)<=MAX_RECORDS,'Supply at most 128 observation pairs.')
   for key,request,response in args.observation:
    request_raw=read(request,min(MAX_FILE,remaining));remaining-=len(request_raw)
    response_raw=read(response,min(MAX_FILE,remaining));remaining-=len(response_raw)
    records.append((key,request_raw,response_raw))
   result=create(args.output,template,{'kind':args.source_kind,'note':args.source_note},records)
  else:result,_=review(args.directory)
  print(json.dumps(result));return result['gate']
 except (OSError,ValueError,KeyError,TypeError) as error:
  print(json.dumps({'format':'agent-crash-lab/token-capture-error-v1','source_integrity':{'matched':False},'assessment_accepted':False,'assessment':None,'gate':2,'error':str(error)[:512]}));return 2

if __name__=='__main__':raise SystemExit(main())
