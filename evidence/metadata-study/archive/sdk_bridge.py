"""Windows-to-owned-WSL stdio bridge to the unchanged canonical SDK mock worker."""
from pathlib import Path
import json, os, queue, subprocess, threading
from protocol import pack, utc

DIST = 'Gamero-Unified-QA-20261028'
BINARY = '/tmp/agent-crash-lab-sdk-v013-tools/target/debug/crash-lab-banking-sdk'
SHA = 'b340696521d9eda1fca93eb931bcd9ad24e3da6190b7daea8cd5fbedb86fa729'

class Sdk:
    def __init__(self, log):
        code = "from pathlib import Path;from hashlib import file_digest;import os,json,sys;p=Path(" + repr(BINARY) + ");f=p.open('rb');d=file_digest(f,'sha256').hexdigest();f.close();assert d==" + repr(SHA) + ";print(json.dumps({'sdkPid':os.getpid(),'binarySha256':d}),file=sys.stderr,flush=True);os.execv(str(p),[str(p)])"
        self.process = subprocess.Popen(['wsl', '-d', DIST, '-e', 'python3', '-I', '-S', '-c', code],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW)
        self.requests, self.lock, self.replies = [], threading.Lock(), queue.Queue()
        def read():
            while True:
                raw = self.process.stdout.readline(262145)
                self.replies.put(raw)
                if not raw:
                    return
        self.reader = threading.Thread(target=read, daemon=True)
        self.reader.start()

    def call(self, value):
        with self.lock:
            raw = pack(value) + b'\n'
            event = {'requestUtf8': raw.decode('utf-8'), 'startedAtUtc': utc(), 'state': 'started'}
            self.requests.append(event)
            try:
                self.process.stdin.write(raw)
                self.process.stdin.flush()
                reply = self.replies.get(timeout=15)
                if len(reply) > 262144 or not reply.endswith(b'\n'):
                    raise RuntimeError('Missing or invalid SDK worker reply')
                event.update(responseUtf8=reply.decode('utf-8'), finishedAtUtc=utc(), state='returned')
                result = json.loads(reply)
                if type(result) is not dict or result.get('op') != value['op'] or result.get('case') != value['case']:
                    raise RuntimeError('SDK worker response does not match its request')
                event.update(responseUtf8=reply.decode('utf-8'), finishedAtUtc=utc(), state='complete')
                return result
            except BaseException as error:
                event.update(state='error', error=type(error).__name__ + ': ' + str(error), finishedAtUtc=utc())
                raise RuntimeError('Owned SDK transport failed') from error

    def close(self):
        if self.process.stdin and not self.process.stdin.closed:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        if self.process.stdout:
            self.process.stdout.close()
        self.reader.join(2)
