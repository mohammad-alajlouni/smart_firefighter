import subprocess, sys
from importlib.metadata import version, PackageNotFoundError

REQUIRED = [
    'paho-mqtt', 'python-dotenv', 'pandas', 'matplotlib',
    'fastapi', 'uvicorn', 'jinja2', 'websockets',
]

def _installed(pkg):
    try:
        version(pkg)
        return True
    except PackageNotFoundError:
        return False

# Bootstrap pip if missing
subprocess.run([sys.executable, '-m', 'ensurepip', '--upgrade'], capture_output=True)
subprocess.run([sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip', '-q',
                '--disable-pip-version-check'], capture_output=True)

missing = [p for p in REQUIRED if not _installed(p)]

if missing:
    print(f'Installing {len(missing)} missing package(s): {", ".join(missing)}')
    subprocess.run([sys.executable, '-m', 'pip', 'install', *missing, '-q',
                    '--disable-pip-version-check'])
else:
    print('All dependencies already installed.')

subprocess.run([sys.executable, '-m', 'uvicorn', 'web.main:app', '--reload', '--port', '8000'])
