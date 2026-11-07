"""Export an exact-byte input bundle without starting the web workbench."""
from pathlib import Path
from runpy import run_path
from types import SimpleNamespace
import argparse,hashlib,json
ROOT=Path(__file__).resolve().parents[1]
app=SimpleNamespace(**run_path(str(ROOT/'workbench.py')))
def browser_catalog():
    names={'agent_crash_lab.py','workbench.py','BASELINES.json','verification/native-crash-comparison.json','tools/scenario_lab.py','episode_oracle.py'}
    for row in app.BASELINES.values():names.update([row['task'],*row['sources'].values()])
    return {'format':'agent-crash-lab/browser-v1','scenarios':app.CURATED,'baselines':list(app.BASELINES.values()),'files':{n:{'bytes':(ROOT/n).stat().st_size,'sha256':hashlib.sha256((ROOT/n).read_bytes()).hexdigest()} for n in sorted(names)}}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('scenario',choices=[*app.CATALOG,'browser-catalog']);p.add_argument('output',type=Path);a=p.parse_args()
    if a.scenario=='browser-catalog':b=browser_catalog()
    else:
        scenario=app.CATALOG[a.scenario]
        b=app.bundle(*app.data_for(scenario),scenario)
    a.output.write_text(json.dumps(b,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\r\n')
    print(a.output)
if __name__=='__main__':main()
