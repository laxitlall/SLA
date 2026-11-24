"""Create a local admin-only upload password without printing or committing it."""
from pathlib import Path
import getpass
import sys

ROOT = Path(__file__).resolve().parents[2]
p = ROOT / '.env'
existing = p.read_text(encoding='utf-8-sig') if p.exists() else ''
if any(line.strip().startswith('CV_UPLOAD_PASSWORD=') for line in existing.splitlines()):
    sys.exit('CV_UPLOAD_PASSWORD is already configured; no changes made.')
first = getpass.getpass('Choose CV upload admin password (16+ characters): ')
second = getpass.getpass('Repeat CV upload admin password: ')
if first != second or len(first) < 16 or any(c in first for c in '\r\n#\"'):
    sys.exit('Passwords must match, be 16+ characters, and contain no # or quotation marks. No changes made.')
with p.open('a', encoding='utf-8') as f:
    f.write('\nCV_UPLOAD_PASSWORD=' + first + '\n')
print('Private CV upload password configured in root .env. Restart the CV server.')
