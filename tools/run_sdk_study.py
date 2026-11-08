"""Opt-in Linux execution of the pinned upstream SDK study, without a NEAR node."""
from pathlib import Path
from hashlib import sha256
from datetime import datetime, timezone
import argparse, json, os, runpy, shutil, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parents[1]
E = ROOT / 'verification/sdk-study'
PIN = 'bacd081a0bd648d840b814dab7677e1f3330afbb'

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true', help='Fetch source/crates and execute actual Rust mock-host methods')
    parser.add_argument('--workspace', type=Path, help='New directory for source, compiler output and complete logs')
    parser.add_argument('--output', type=Path, required=True, help='New JSON summary file; existing files are not overwritten')
    args = parser.parse_args()
    if not args.execute:
        parser.error('Use tools/verify_sdk_study.py for offline replay, or explicitly pass --execute')
    if sys.platform != 'linux' or not shutil.which('cargo') or not shutil.which('git'):
        parser.error('Fresh SDK execution requires Linux, Git and Rust 1.95.0; offline replay supports Python on Windows too')
    if args.output.exists():
        parser.error('Output already exists; select a new file')
    workspace = args.workspace.resolve() if args.workspace else Path(tempfile.mkdtemp(prefix='crash-lab-sdk-'))
    if args.workspace:
        workspace.mkdir(parents=True, exist_ok=False)
    upstream = workspace / 'upstream'
    environment = dict(os.environ, RUSTUP_TOOLCHAIN='1.95.0', CARGO_BUILD_JOBS='2', CARGO_TARGET_DIR=str(workspace / 'target'), GIT_TERMINAL_PROMPT='0')
    commands = []
    def call(label, command, data=None):
        with (workspace / (label + '.stdout.txt')).open('xb') as out, (workspace / (label + '.stderr.txt')).open('xb') as err:
            process = subprocess.run(command, input=data, stdout=out, stderr=err, env=environment)
        commands.append({'label': label, 'command': [str(x) for x in command], 'exitCode': process.returncode})
        if process.returncode:
            raise RuntimeError(label + ' failed; complete logs retained at ' + str(workspace))
        return (workspace / (label + '.stdout.txt')).read_bytes()
    started = datetime.now(timezone.utc).isoformat()
    call('clone', ['git', 'clone', '-c', 'core.autocrlf=false', '--no-checkout', '--filter=blob:none', 'https://github.com/near/near-sdk-rs.git', str(upstream)])
    call('checkout', ['git', '-C', str(upstream), 'checkout', '--detach', PIN])
    assert call('revision', ['git', '-C', str(upstream), 'rev-parse', 'HEAD']).decode().strip() == PIN
    expected_source = json.loads((E / 'canonical-source-integrity.json').read_bytes())['files']
    def source_check():
        for name, meta in expected_source.items():
            raw = (upstream / name).read_bytes()
            assert len(raw) == meta['bytes'] and sha256(raw).hexdigest() == meta['sha256'], name
    source_check()
    shutil.copyfile(E / 'upstream.Cargo.lock', upstream / 'Cargo.lock')
    shutil.copytree(E / 'harness', workspace / 'harness')
    compiler = call('compiler', ['rustc', '--version', '--verbose']).decode().strip()
    call('upstream-tests', ['cargo', 'test', '--locked', '--manifest-path', str(upstream / 'Cargo.toml'), '-p', 'near-contract-standards', '--lib', 'fungible_token', '--', '--nocapture'])
    call('build', ['cargo', 'build', '--locked', '--manifest-path', str(workspace / 'harness/Cargo.toml')])
    actual_raw = call('sdk-execution', [str(workspace / 'target/debug/crash-lab-sdk-resolver-study')], (E / 'cases.json').read_bytes())
    actual = json.loads(actual_raw)
    expected = json.loads((E / 'sdk-original.json').read_bytes())
    assert actual == expected, 'Fresh SDK result differs from the original saved SDK observations'
    adapter = runpy.run_path(str(E / 'replay.py'))
    assess = runpy.run_path(str(ROOT / 'token_policy.py'))['assess']
    for row in actual:
        task, evidence, reference = adapter['fixture'](row)
        report = assess(adapter['pack'](task), adapter['pack'](evidence))
        assert report['gate'] == 0 and {k: report['payments'][0][k] for k in reference} == reference, row['case']['id']
    source_check()
    result = {'format': 'agent-crash-lab/sdk-fresh-result-v1', 'startedAtUtc': started, 'endedAtUtc': datetime.now(timezone.utc).isoformat(),
        'sdkRevision': PIN, 'compiler': compiler, 'sourceFilesChecked': len(expected_source),
        'freshSdkExecutions': len(actual), 'currentProjectionMatches': len(actual), 'originalSdkObjectsMatched': True,
        'sdkOutputSha256': sha256(actual_raw).hexdigest(), 'newTransactions': 0, 'newModelCalls': 0,
        'workspace': str(workspace), 'commands': commands,
        'meaning': 'Fresh unmodified upstream SDK mock-host execution and own receipt projection. Not deployed WASM, an agent run, external blind evaluation or authenticated consensus.'}
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))

if __name__ == '__main__':
    main()
