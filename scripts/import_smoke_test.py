import importlib
import sys

modules = [
    'core.llm_router',
    'agents.researcher',
    'agents.writer',
    'agents.coder',
    'main',
]
errs = False
for m in modules:
    try:
        importlib.import_module(m)
        print('OK', m)
    except Exception as e:
        print('ERROR', m, e)
        errs = True

if errs:
    sys.exit(1)

print('Import smoke-test completed successfully')
