"""WSL-only bounded HTTP proxy: exact bytes to one owned loopback model listener."""
from hashlib import sha256
from urllib.request import Request, build_opener, ProxyHandler
from urllib.error import HTTPError
import json, sys, time

port, method, path, timeout = int(sys.argv[1]), sys.argv[2], sys.argv[3], float(sys.argv[4])
assert 1024 <= port <= 65535 and 0 < timeout <= 95
assert (method, path) in [('GET', '/health'), ('GET', '/props'), ('POST', '/tokenize'), ('POST', '/completion')]
raw = sys.stdin.buffer.read(262145)
assert len(raw) <= 262144 and (method != 'GET' or not raw)
request = Request('http://127.0.0.1:' + str(port) + path,
                  data=raw if method == 'POST' else None, method=method,
                  headers={'Content-Type': 'application/json'})
start = time.monotonic()
status, response = None, b''
try:
    try:
        with build_opener(ProxyHandler({})).open(request, timeout=timeout) as reply:
            status, response = reply.status, reply.read(1048577)
    except HTTPError as error:
        status, response = error.code, error.read(1048577)
        error.close()
    assert len(response) <= 1048576
    result = {'httpStatus': status, 'responseUtf8': response.decode('utf-8'),
              'requestSha256': sha256(raw).hexdigest(), 'responseSha256': sha256(response).hexdigest(),
              'loopbackHttpElapsedMs': round((time.monotonic() - start) * 1000, 3)}
except BaseException as error:
    result = {'transportError': type(error).__name__ + ': ' + str(error), 'httpStatus': status,
              'requestSha256': sha256(raw).hexdigest(), 'responseHex': response.hex(),
              'loopbackHttpElapsedMs': round((time.monotonic() - start) * 1000, 3)}
sys.stdout.write(json.dumps(result, ensure_ascii=True, separators=(',', ':')) + '\n')
