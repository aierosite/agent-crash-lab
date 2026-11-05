"""Export an exact-byte input bundle without starting the web workbench."""
from pathlib import Path
import argparse,hashlib,importlib.util,json
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('export_bench',ROOT/'workbench.py');app=importlib.util.module_from_spec(spec);spec.loader.exec_module(app)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('scenario',choices=[*app.CATALOG,'browser-catalog']);p.add_argument('output',type=Path);a=p.parse_args()
    if a.scenario=='browser-catalog':
        names={'agent_crash_lab.py','workbench.py','BASELINES.json','verification/native-crash-comparison.json'}
        for row in app.BASELINES.values():names.update([row['task'],*row['sources'].values()])
        b={'format':'agent-crash-lab/browser-v1','scenarios':app.CURATED,'baselines':list(app.BASELINES.values()),'files':{n:{'bytes':(ROOT/n).stat().st_size,'sha256':hashlib.sha256((ROOT/n).read_bytes()).hexdigest()} for n in sorted(names)}}
        a.output.write_text(json.dumps(b,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(str(a.output));return
    task,sources=app.data_for(app.CATALOG[a.scenario])
    b={'format':'agent-crash-lab/bundle-v1','task_utf8':task.decode(),'sources_utf8':{k:v.decode() for k,v in sources.items()},'classification':app.CATALOG[a.scenario]['kind']}
    a.output.write_text(json.dumps(b,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(str(a.output))
if __name__=='__main__':main()
