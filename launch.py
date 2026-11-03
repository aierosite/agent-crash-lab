"""Start the local workbench on a free port. Ctrl+C stops only this child server."""
from pathlib import Path
import argparse,json,subprocess,sys,urllib.request,webbrowser
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--no-browser',action='store_true');p.add_argument('--check',action='store_true',help='Start, check loopback health, then stop own server');a=p.parse_args()
    root=Path(__file__).resolve().parent
    child=subprocess.Popen([sys.executable,'-I','-S',str(root/'workbench.py'),'--port','0'],cwd=root,stdout=subprocess.PIPE,text=True)
    try:
        line=child.stdout.readline().strip()
        if not line.startswith('Agent Crash Lab http://127.0.0.1:'):raise RuntimeError('Local workbench did not start')
        url=line.split(' ',3)[3];print(line,flush=True);print('Ctrl+C closes this local server. No wallet, API or network transaction is used.',flush=True)
        if a.check:
            with urllib.request.urlopen(url+'api/health',timeout=5) as response:
                if not json.load(response)['ok']:raise RuntimeError('Health check failed')
            return 0
        if not a.no_browser:webbrowser.open(url)
        return child.wait()
    except KeyboardInterrupt:return 0
    finally:
        if child.poll() is None:
            child.terminate()
            try:child.wait(timeout=5)
            except subprocess.TimeoutExpired:child.kill();child.wait(timeout=3)
if __name__=='__main__':raise SystemExit(main())
