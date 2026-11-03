# Optional: generate fresh native crash/restart evidence

The default UI and all tests replay existing recordings. This optional command **creates two new owned local chains and sends five local native transactions**. It does not connect to any wallet, mainnet/testnet or existing account. It must run on Linux (WSL is supported).

Prerequisites: Python3, `cryptography`, and the official **near-sandbox 2.14.0 Linux x86_64** executable. Use a separate virtual environment for the optional dependency:

```sh
python3 -m venv .venv-native
.venv-native/bin/python -m pip install -r requirements-native.txt
```

Official binary archive used in this research:

https://s3-us-west-1.amazonaws.com/build.nearprotocol.com/nearcore/Linux-x86_64/2.14.0/near-sandbox.tar.gz

The runner requires the **executable** SHA256, not the archive hash:

```
797b9d7a9a23907048d68a427e86a55c94f1de232dbfb8b8a1eec09ecef3bf13
```

Verify the downloaded/extracted binary before running. The matching nearcore source pin is `bc4e9e8cfb03d9e82f027883055624e18576993e`. The runner rejects a different executable; do not disable that check to accommodate an unreviewed release.

From the repository directory in Linux, with the pinned binary at an explicit path:

```sh
.venv-native/bin/python tools/native_crash.py --binary /absolute/path/near-sandbox --output evidence
.venv-native/bin/python tools/bind_native.py
python3 -I -S test_agent_crash_lab.py
python3 -I -S test_workbench.py
```

This replaces only `evidence/native-*.json`, the two `tasks/native-*.json`, native verification files and their baseline/expected entries. Preserve earlier outputs before rerunning if comparing experiments. New run hashes will differ. Rebuild the release manifest after intentional changes.

On this developer machine, a Windows convenience wrapper was actually executed:

```sh
python -I -S tools/run_native_wsl.py --distro Gamero-Unified-QA-20261028 --binary /tmp/agent-crash-lab-20261102/near-sandbox
python -I -S tools/bind_native.py
```

The distro name/path above are observed machine-specific settings, not prerequisites for another machine. The wrapper streams code/config through stdin and copies only observation/precommit JSON back. No ephemeral signing seed is returned or written into product evidence.

Fault and measurements: actual process `os._exit(77)` after FINAL, actual restart, separate intent B, signed action/receipt observation, merchant balance corroboration, four actual controlled local HTTP deliveries and the separately predeclared expected task answer. Node cleanup is in `finally`; both owned processes were observed stopped. Temporary genesis homes contain default local node keys and remain private under `/tmp`; they are not included in this repository or release. No existing node is searched for or stopped.

This is a same-operator, known-family integration exercise. It does not establish an independent holdout score, a live LLM's competence, production exactly-once delivery or universal NEAR behavior.
