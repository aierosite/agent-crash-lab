"""Bounded owned Linux process; no inference is issued by the supervisor."""
from pathlib import Path
from hashlib import file_digest
import json, os, selectors, signal, socket, subprocess, sys, time

H = Path(__file__).resolve().parent
resources = json.loads((H / 'RESOURCES.json').read_bytes())
model_id, run_name, seconds = sys.argv[1], sys.argv[2], float(sys.argv[3])
assert model_id in {m['id'] for m in resources['models']} and run_name.replace('-', '').isalnum() and 0 < seconds <= 3700
assert str(H) == '/tmp/agent-crash-lab-multitask-v0171'
model = next(m for m in resources['models'] if m['id'] == model_id)
binary = H / 'runtime/llama-b12110/llama-server'
def digest(path):
    with path.open('rb') as source:
        return file_digest(source, 'sha256').hexdigest()
assert digest(H / model['file']) == model['sha256'] and digest(binary) == resources['runtime']['binarySha256']
out = H / run_name
out.mkdir(exist_ok=False)
with socket.socket() as s:
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
command = [str(binary), '-m', str(H / model['file']), '--no-context-shift',
           '--host', '127.0.0.1', '--port', str(port), '-c', '12288',
           '-t', '2', '-tb', '2', '-ngl', '0', '--parallel', '1']
log = (out / 'runtime.log').open('wb')
proc = subprocess.Popen(command, stdout=log, stderr=log, start_new_session=True,
                        env={'PATH': os.defpath, 'LANG': 'C.UTF-8', 'LD_LIBRARY_PATH': str(binary.parent)})
metadata = {'modelId': model_id, 'pid': proc.pid, 'supervisorPid': os.getpid(), 'port': port,
            'command': command, 'peakSampledVmHwmBytes': 0, 'inferenceIssuedBySupervisor': False}
(out / 'process.json').write_text(json.dumps(metadata), encoding='utf-8')
print(json.dumps(metadata), flush=True)
start, stopping = time.monotonic(), False
selector = selectors.DefaultSelector()
selector.register(sys.stdin, selectors.EVENT_READ)
try:
    while proc.poll() is None and time.monotonic() - start < seconds:
        try:
            line = next(x for x in Path('/proc/' + str(proc.pid) + '/status').read_text().splitlines() if x.startswith('VmHWM:'))
            metadata['peakSampledVmHwmBytes'] = max(metadata['peakSampledVmHwmBytes'], int(line.split()[1]) * 1024)
        except (OSError, StopIteration):
            pass
        if selector.select(.2):
            sys.stdin.readline()
            stopping = True
            break
finally:
    if proc.poll() is None:
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(3)
    log.close()
    selector.close()
    metadata.update(stopped=True, returncode=proc.returncode, stopRequested=stopping,
                    elapsedSeconds=round(time.monotonic() - start, 3))
    (out / 'stopped.json').write_text(json.dumps(metadata), encoding='utf-8')
    print(json.dumps(metadata), flush=True)
