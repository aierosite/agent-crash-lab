"""Banking-only loader for canonical AgentDojo modules; no model/provider imports."""
from pathlib import Path
from hashlib import sha256
import ast, importlib, json, sys, types, site

H = Path(__file__).resolve().parent
sys.dont_write_bytecode = True

def load_originals():
    index = json.loads((H / 'SOURCE-INDEX.json').read_bytes())
    source = H / 'upstream'
    for name, meta in index['files'].items():
        raw = (source / name).read_bytes()
        assert len(raw) == meta['bytes'] and sha256(raw).hexdigest() == meta['sha256'], name
    dependency = index['dependency']
    if 'files' in dependency:
        for name, meta in dependency['files'].items():
            assert sha256((H / 'vendor' / name).read_bytes()).hexdigest() == meta['sha256'], name
    sys.path.insert(0, str(H / 'vendor'))
    sys.path.insert(0, str(source / 'src'))
    # Existing Pydantic/PyYAML live in the user's installed package directory.
    # Explicit access under -I does not execute user site startup/.pth hooks.
    existing_packages = site.getusersitepackages()
    if existing_packages not in sys.path:
        sys.path.append(existing_packages)
    runtime = importlib.import_module('agentdojo.functions_runtime')
    import pydantic, yaml
    from collections.abc import Callable

    # GroundTruthPipeline needs only this pure formatter from a module which
    # otherwise imports unrelated Google model providers. Its AST is unchanged.
    path = source / 'src/agentdojo/agent_pipeline/tool_execution.py'
    node = next(n for n in ast.parse(path.read_bytes()).body
                if isinstance(n, ast.FunctionDef) and n.name == 'tool_result_to_str')
    formatter = types.ModuleType('agentdojo.agent_pipeline.tool_execution')
    formatter.__file__ = str(path)
    formatter.__dict__.update(BaseModel=pydantic.BaseModel, yaml=yaml,
                              FunctionReturnType=runtime.FunctionReturnType, Callable=Callable)
    sys.modules[formatter.__name__] = formatter
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), formatter.__dict__)

    bank = importlib.import_module('agentdojo.default_suites.v1.banking.task_suite')
    importlib.import_module('agentdojo.default_suites.v1.banking.user_tasks')
    importlib.import_module('agentdojo.default_suites.v1.banking.injection_tasks')
    importlib.import_module('agentdojo.default_suites.v1_1_1.banking.user_tasks')
    importlib.import_module('agentdojo.default_suites.v1_2.banking.injection_tasks')
    importlib.import_module('agentdojo.default_suites.v1_2_2.banking.user_tasks')
    suite = bank.task_suite
    suite.data_path = source / 'src/agentdojo/data/suites/banking'
    gt = importlib.import_module('agentdojo.agent_pipeline.ground_truth_pipeline')
    base = importlib.import_module('agentdojo.agent_pipeline.base_pipeline_element')
    message_types = importlib.import_module('agentdojo.types')
    loaded = {n: str(m.__file__) for n, m in sys.modules.items()
              if n.startswith('agentdojo.') and getattr(m, '__file__', None)}
    record = {'revision': index['revision'], 'modules': loaded,
              'fullOriginalModulesExceptFormatter': True,
              'formatterUnchangedAstSha256': sha256(ast.dump(node).encode()).hexdigest(),
              'namespaceParents': 'Standard Python namespace packages; unrelated package initializers/suites/CLI/provider imports are not executed.',
              'bankingVersionSelection': 'Actual TaskSuite registration and get_new_version; v1.2.2 tuple matches the original load_suites mapping. No marker substitution.',
              'python': sys.version, 'pydantic': pydantic.__version__, 'PyYAML': yaml.__version__,
              'existingUserPackagesExplicitlyAddedUnderIsolation': existing_packages,
              'docstringParser': dependency,
              'modelProvidersImported': [n for n in sys.modules if n.startswith(('openai', 'anthropic', 'google.generativeai'))]}
    assert not record['modelProvidersImported']
    return suite, runtime, gt.GroundTruthPipeline, base.BasePipelineElement, message_types, record

if __name__ == '__main__':
    from datetime import datetime, timezone
    from unittest.mock import patch
    with patch('socket.socket.connect', side_effect=AssertionError('Network is forbidden during original runtime execution')) as connect:
        suite, runtime, ground_truth, pipeline, messages, record = load_originals()
        env = suite.load_and_inject_default_environment({})
        assert len(suite.user_tasks) == 16 and len(suite.tools) == 11
        latest = suite.get_new_version((1, 2, 2))
        record.update(atUtc=datetime.now(timezone.utc).isoformat(), userTasks=len(suite.user_tasks),
                      tools=len(suite.tools), defaultHistoryRows=len(env.bank_account.transactions),
                      defaultScheduledRows=len(env.bank_account.scheduled_transactions),
                      task6V1=suite.user_tasks['user_task_6'].__class__.__module__,
                      task6Latest=latest.user_tasks['user_task_6'].__class__.__module__,
                      task15Latest=latest.user_tasks['user_task_15'].__class__.__module__,
                      networkConnectionsAttempted=connect.call_count, utilityEvaluations=0)
        assert connect.call_count == 0
    (H / 'PROBE.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: record[k] for k in ['userTasks', 'tools', 'defaultHistoryRows', 'task6Latest', 'task15Latest', 'networkConnectionsAttempted', 'utilityEvaluations']}))
