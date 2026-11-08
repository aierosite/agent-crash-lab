"""Offline replay of recorded official SDK executions; does not execute Rust."""
from pathlib import Path
from hashlib import sha256
import json, runpy, tempfile

ROOT = Path(__file__).resolve().parents[1]
E = ROOT / 'verification/sdk-study'

def verify():
    manifest = json.loads((E / 'ARTIFACTS.json').read_bytes())
    for name, meta in manifest['files'].items():
        raw = (E / name).read_bytes()
        assert len(raw) == meta['bytes'] and sha256(raw).hexdigest() == meta['sha256'], name
    replay = runpy.run_path(str(E / 'replay.py'))['run']
    original = json.loads((E / 'first-comparison.json').read_bytes())
    with tempfile.TemporaryDirectory(prefix='crash-lab-sdk-frozen-') as directory:
        frozen = Path(directory)
        for name in ('token_policy.py', 'token_review.py'):
            (frozen / name).write_bytes((E / (name + '.txt')).read_bytes())
        assert replay(frozen) == original, 'Frozen original reports differ'
    current = replay(ROOT)
    assert all(r['matched'] for r in current['primary'] + current['controls']), 'Current SDK projection/policy disagreement'
    return {'format': 'agent-crash-lab/sdk-replay-result-v1', 'sdkRevision': 'bacd081a0bd648d840b814dab7677e1f3330afbb',
        'recordedSdkExecutions': len(current['primary']), 'currentProjectionMatches': sum(r['matched'] for r in current['primary']),
        'policyEvidenceControls': len(current['controls']), 'originalReportsReproduced': len(original['reports']),
        'upstreamTestResult': '12 event tests (6 FT and 6 NFT) recorded passing',
        'newSdkExecutions': 0, 'newTransactions': 0, 'newModelCalls': 0,
        'meaning': 'Offline replay of saved actual SDK host-mock observations. Not a fresh Rust run, external blind grading, full agent/WASM execution, consensus or comparative accuracy.'}

if __name__ == '__main__':
    print(json.dumps(verify()))
