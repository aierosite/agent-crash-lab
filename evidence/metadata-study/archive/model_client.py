"""Windows lifecycle and exact-byte requests to the single owned Linux model."""
from pathlib import Path
import json, queue, subprocess, threading, time
from protocol import pack, decode, utc
from sdk_bridge import DIST

ROOT = '/tmp/agent-crash-lab-multitask-v0171'
def proxy(port, method, path, body=b'', timeout=15):
    start = time.monotonic()
    proc = subprocess.run(['wsl', '-d', DIST, '-e', 'python3', '-I', '-S', ROOT + '/model_http.py',
                           str(port), method, path, str(timeout)], input=body, capture_output=True,
                          timeout=timeout + 8, creationflags=subprocess.CREATE_NO_WINDOW)
    if proc.returncode:
        raise RuntimeError('Owned HTTP proxy failed: ' + proc.stderr.decode('utf-8', errors='replace'))
    value = decode(proc.stdout)
    value['windowsRoundTripElapsedMs'] = round((time.monotonic() - start) * 1000, 3)
    return value

class Model:
    def __init__(self, model_id, name, log, seconds):
        self.process = subprocess.Popen(['wsl', '-d', DIST, '-e', 'python3', '-I', '-S', ROOT + '/model_supervisor.py',
            model_id, name, str(seconds)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW)
        self.queue = queue.Queue()
        def read():
            for line in iter(self.process.stdout.readline, b''):
                self.queue.put(line)
            self.queue.put(None)
        self.reader = threading.Thread(target=read, daemon=True)
        self.reader.start()
        try:
            line = self.queue.get(timeout=20)
            if line is None:
                raise RuntimeError('Model supervisor stopped before returning a process handle')
            self.metadata = decode(line)
        except BaseException:
            self.process.stdin.close()  # supervisor EOF terminates only its owned process group
            self.process.wait(timeout=12)
            self.reader.join(2)
            self.process.stdout.close()
            raise
        self.port = self.metadata['port']
        self.ready = []
        self.stopped = None

    def wait_ready(self, seconds=90):
        start = time.monotonic()
        while time.monotonic() - start < seconds:
            if self.process.poll() is not None:
                raise RuntimeError('Owned model stopped during startup')
            response = proxy(self.port, 'GET', '/health', timeout=2)
            self.ready.append(response)
            if response.get('httpStatus') == 200 and decode(response['responseUtf8']).get('status') == 'ok':
                props = proxy(self.port, 'GET', '/props', timeout=8)
                assert props['httpStatus'] == 200 and decode(props['responseUtf8'])['build_info'] == 'b12110-cd959bae9'
                return props
            time.sleep(.2)
        raise RuntimeError('Owned model did not become ready within the fixed startup budget')

    def close(self):
        if self.process.poll() is None:
            self.process.stdin.write(b'stop\n')
            self.process.stdin.flush()
            self.process.stdin.close()
        self.process.wait(timeout=12)
        self.reader.join(2)
        while not self.queue.empty():
            line = self.queue.get_nowait()
            if line:
                self.stopped = decode(line)
        if self.process.stdout:
            self.process.stdout.close()
        if not self.stopped or not self.stopped.get('stopped'):
            raise RuntimeError('Missing authoritative owned-model shutdown receipt')
        return self.stopped
