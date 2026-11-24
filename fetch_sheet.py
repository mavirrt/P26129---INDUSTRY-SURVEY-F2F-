"""Tải raw data XML (SurveyToGo) từ Google Sheet "RMIT_Industry Survey", tab Raw_Data, ghép các chunk thành data/raw.xml.

Cần một service account có quyền xem Sheet:
    pip install google-auth requests
    export GOOGLE_APPLICATION_CREDENTIALS=/duong/dan/service-account.json
    python fetch_sheet.py            # rồi: python qc.py data/raw.xml

Raw_Data có các cột: Sync Time | Batch | Chunk | XML Data. Script lấy batch mới nhất và nối các chunk theo thứ tự.
"""
import os, sys, json, requests
from google.oauth2 import service_account
from google.auth.transport.requests import Request

SHEET_ID = os.environ.get('SHEET_ID', '1xRJJGpcCm1iLtUxUi7VZaDa6J9480jUEb7fS0DdzLPU')
OUT = sys.argv[1] if len(sys.argv) > 1 else 'data/raw.xml'
STEP = 40  # số dòng mỗi lần gọi (mỗi chunk ~50k ký tự)

cred = service_account.Credentials.from_service_account_file(
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'], scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
cred.refresh(Request())
H = {'Authorization': f'Bearer {cred.token}'}
URL = f'https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/'

def get(rng):
    r = requests.get(URL + requests.utils.quote(rng), headers=H, timeout=120); r.raise_for_status()
    return r.json().get('values', [])

idx = get('Raw_Data!B2:C')
last = max(int(b) for b, _ in idx if b)
rows = [i + 2 for i, (b, _) in enumerate(idx) if b and int(b) == last]
parts = {}
for start in range(min(rows), max(rows) + 1, STEP):
    end = min(start + STEP - 1, max(rows))
    for b, c, x in get(f'Raw_Data!B{start}:D{end}'):
        if int(b) == last: parts[int(c)] = x
missing = [k for k in range(1, max(parts) + 1) if k not in parts]
if missing: sys.exit(f'Thiếu chunk {missing} của batch {last}')
os.makedirs(os.path.dirname(OUT) or '.', exist_ok=True)
open(OUT, 'w', encoding='utf-8').write(''.join(parts[k] for k in sorted(parts)))
print(f'Batch {last}: {len(parts)} chunk -> {OUT}')
