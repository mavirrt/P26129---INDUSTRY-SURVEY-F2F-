"""QC checks for P26129 Industry Survey F2F.
Input: SurveyToGo XML export (Raw_Data sheet chunks joined) -> data/raw.xml
Output: data/interviews.json (1 row / interview) and data/flags.json (1 row / issue).
Personal data (respondent name, phone, address) is NOT written out: only derived flags.
"""
import xml.etree.ElementTree as ET, json, re, sys, unicodedata, collections, datetime as dt, hashlib

SRC = sys.argv[1] if len(sys.argv) > 1 else 'data/raw.xml'
CODE = open(__file__, encoding='utf-8').read()
root = ET.parse(SRC).getroot()

def ts(t):
    t = t.rstrip('Z')
    if '.' in t:
        a, b = t.split('.'); t = a + '.' + b[:6]
    return dt.datetime.fromisoformat(t)

def parse_subject(s):
    m = {c.attrib.get('Field', c.tag): (c.text or '') for c in s if c.tag != 'Chapter'}
    a, times = {}, []
    for q in s.iter('Question'):
        v, qt = q.findtext('Variable'), q.findtext('QType')
        if q.findtext('AnsweredTimeStamp'): times.append(ts(q.findtext('AnsweredTimeStamp')))
        if qt == 'eqtAmerican':
            an = q.find('Answers/Answer')
            a[v] = {'code': an.findtext('Code') if an is not None else None, 'text': q.findtext('QuestionAnswer'),
                    'oth': an.findtext('OtherSpec') if an is not None else None}
        elif qt == 'eqtMultiSelect':
            a[v] = [{'code': x.findtext('Code'), 'text': x.findtext('Text'), 'oth': x.findtext('OtherSpec')} for x in q.findall('Answers/Answer')]
        else:
            d = {}
            for t in q.findall('Topics/Topic'):
                k = t.findtext('Text')
                if qt in ('eqtMultiNumeric', 'eqtMultiText'): d[k] = t.findtext('TopicAnswer')
                else: d[k] = [{'code': x.findtext('Code'), 'oth': x.findtext('OtherSpec'), 'text': x.findtext('Text')} for x in t.findall('Answers/Answer')]
            a[v] = d
    return m, a, sorted(times)

def code(a, q):
    v = a.get(q); return int(v['code']) if isinstance(v, dict) and v.get('code') not in (None, '') else None
def codes(a, q): return [int(x['code']) for x in a.get(q) or [] if x.get('code')]
def card1(a, q):  # card -> single code
    return {k: int(v[0]['code']) for k, v in (a.get(q) or {}).items() if v and v[0].get('code')}
def cardm(a, q): return {k: [int(x['code']) for x in v if x.get('code')] for k, v in (a.get(q) or {}).items()}
def short(card): return card.split('_')[0] if card.startswith('RF') else card.rstrip(':')
def norm(s):
    s = unicodedata.normalize('NFD', (s or '').lower()); s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return re.sub(r'\s+', ' ', s.replace('đ', 'd')).strip()

B4_LOW, B4_TOP = {1: 1, 2: 5, 3: 20, 4: 50, 5: 200}, {1: 4, 2: 19, 3: 49, 4: 199, 5: None}
A10_LOW, A10_TOP = {1: 1, 2: 20, 3: 50, 4: 200, 5: 500, 6: 2000}, {1: 19, 2: 49, 3: 199, 4: 499, 5: 1999, 6: None}
C5_MID = {1: 0, 2: 1.5, 3: 4, 4: 8, 5: 15, 6: 35, 7: 50}
JUNK = {'', 'khong', 'ko', 'k', 'x', 'xx', '.', '-', 'na', 'n/a', 'khong biet', 'kb', 'abc', 'không'}

subs = [parse_subject(s) for s in root.findall('.//SurveyResults/Subject')]
interviews, flags = [], []
phones = collections.defaultdict(list); companies = collections.defaultdict(list)
streets = collections.defaultdict(list); oe_texts = collections.defaultdict(list)

for m, a, times in subs:
    sid = m['SbjNum']; nam = m.get('SbjNam', '')
    test = nam == 'STGTester' or m.get('Test') == 'True'
    pvv = 'TEST' if test else (nam[:-1] if len(nam) >= 3 and nam.isdigit() else (nam or '?'))
    city = m.get('CustomData1') or '?'
    start_local = ts(m['VStart']) + dt.timedelta(hours=7)
    active_min = round((times[-1] - times[0]).total_seconds() / 60, 1) if len(times) > 1 else None
    info = a.get('Q_6') or {}
    phone = re.sub(r'\D', '', next((v for k, v in info.items() if 'điện thoại' in k.lower()), '') or '')
    comp = next((v for k, v in info.items() if 'công ty' in k.lower()), '') or ''
    addr = next((v for k, v in info.items() if 'địa chỉ' in k.lower()), '') or ''
    row = dict(id=sid, pvv=pvv, city=city, date=start_local.strftime('%Y-%m-%d'), start=start_local.strftime('%H:%M'),
               minutes=active_min, sessions=int(m.get('NumberOfSessions') or 1), status=m.get('Status'), test=test,
               a1=(a.get('A1') or {}).get('text'), a4=code(a, 'A4'), a7=code(a, 'A7'), a8=code(a, 'A8'), a10=code(a, 'A10'), a11=code(a, 'A11'),
               a2=code(a, 'A2'), s0=(a.get('S0') or {}).get('text'), company=comp.strip())
    F = []
    def flag(group, chk, sev, detail): F.append(dict(id=sid, pvv=pvv, city=city, group=group, check=chk, severity=sev, detail=detail))

    A1, A2, A3, A4, A5, A6, A10 = (code(a, q) for q in ('A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'A10'))
    A7, A8 = code(a, 'A7'), code(a, 'A8'); A9 = codes(a, 'A9')
    B1 = a.get('B1') or []; B5 = a.get('B5') or []
    B4, C1 = card1(a, 'B4'), {k: (int(v) if str(v).strip().lstrip('-').isdigit() else None) for k, v in (a.get('C1') or {}).items()}
    C2, C3, C4, C5 = card1(a, 'C2'), card1(a, 'C3'), card1(a, 'C4'), card1(a, 'C5')
    C6, D2, D3 = cardm(a, 'C6'), cardm(a, 'D2'), a.get('D3') or {}
    D4, D5, D6 = card1(a, 'D4'), card1(a, 'D5'), code(a, 'D6')
    E1, E2, F1, F2 = card1(a, 'E1'), cardm(a, 'E2'), card1(a, 'F1'), card1(a, 'F2')

    # ---------- 1. LOGIC GIỮA CÁC CÂU ----------
    LG = 'Logic giữa câu'
    so = []
    if A1 == 4: so.append('A1=4 (tỉnh khác)')
    if A2 is not None and A2 not in (4, 5, 6, 7): so.append(f'A2={A2}')
    if A3 is not None and A3 <= 2: so.append(f'A3={A3}')
    if A5 == 2: so.append('A5=Không')
    if A6 == 2: so.append('A6=Không')
    if 98 in A9: so.append('A9=98')
    if A10 == 99: so.append('A10=Không rõ')
    if 99 in B4.values(): so.append('B4=Không rõ')
    if so: flag(LG, 'Lẽ ra bị screen out', 'Cao', ', '.join(so) + ' nhưng bài vẫn hoàn thành')
    if A4 in (1, 2) and A5 is None: flag(LG, 'Sai nhánh A4 → A5/A6', 'Cao', f'A4={A4} nhưng không có A5')
    if A4 in (3, 4, 5) and A6 is None: flag(LG, 'Sai nhánh A4 → A5/A6', 'Cao', f'A4={A4} nhưng không có A6')
    oth = [x for x in B1 if not (x['text'] or '').startswith('RF')]
    if len(B1) < 3: flag(LG, 'B1 chọn dưới 3 vị trí', 'Cao', f'B1 có {len(B1)} vị trí')
    if len(oth) >= 2: flag(LG, 'B1 dùng 2–3 ô Khác (quota max 50)', 'Theo dõi', f'{len(oth)} ô Khác: ' + '; '.join((x["oth"] or '')[:40] for x in oth))
    b1t = {x['text'] for x in B1}
    if len(B5) != 3: flag(LG, 'B5 không đúng 3 vị trí', 'Cao', f'B5 có {len(B5)} vị trí')
    if any(x['text'] not in b1t for x in B5): flag(LG, 'B5 ngoài danh sách B1', 'Cao', 'Có vị trí ở B5 không chọn ở B1')
    for k, v in C1.items():
        if v is not None and v not in range(0, 99) and v != 99: flag(LG, 'C1 ngoài khoảng 0–98/99', 'Cao', f'{short(k)}: C1={v}')
    for q, cardmap, cond in (('C2', C2, lambda c: c != 0), ('C3', C3, lambda c: c not in (0, 99))):
        for k in cardmap:
            if k in C1 and C1[k] is not None and not cond(C1[k]): flag(LG, f'{q} hỏi sai thẻ (theo C1)', 'Cao', f'{short(k)}: C1={C1[k]} vẫn có {q}')
    for k, v in C1.items():
        if v is not None and 1 <= v <= 98 and k not in C3: flag(LG, 'Thiếu C3 cho thẻ C1 1–98', 'Cao', f'{short(k)}: C1={v}')
        top = B4_TOP.get(B4.get(k))
        if v is not None and v != 99 and top is not None and v > top:
            flag(LG, 'C1 lớn hơn quy mô B4', 'Trung bình', f'{short(k)}: C1={v} người nhưng B4 tối đa {top}')
    for k, c4 in C4.items():
        if c4 == 3 and C6.get(k): flag(LG, 'C6 hỏi thẻ có C4 = Giữ nguyên', 'Cao', short(k))
        if c4 in (1, 2, 4, 5) and k not in C6: flag(LG, 'Thiếu C6 cho thẻ có thay đổi', 'Cao', f'{short(k)}: C4={c4}')
    if A6 == 1 and C5 and all(v == 1 for v in C5.values()):
        flag(LG, 'Quản lý có kế hoạch tuyển nhưng C5 = Không tuyển hết', 'Trung bình', 'A6=Có, C5=Không tuyển ở cả 3 vị trí')
    for k in D3:
        if 96 in D2.get(k, []): flag(LG, 'D3 hỏi thẻ D2 = Ngành nào cũng được', 'Cao', short(k))
    for k, v in D5.items():
        if D4.get(k) not in (1, 2): flag(LG, 'D5 có chương trình không chấm 1–2 ở D4', 'Cao', f'{short(k)[:40]} (D4={D4.get(k, "không có thẻ")})')
    for k, v in D4.items():
        if v in (1, 2) and k not in D5: flag(LG, 'Thiếu D5 cho chương trình D4 1–2', 'Cao', short(k)[:30])
    if (a.get('D7') or a.get('D8')) and D6 not in (3, 4, 5): flag(LG, 'D7/D8 hỏi sai base D6', 'Cao', f'D6={D6}')
    if D6 in (3, 4, 5) and not a.get('D8'): flag(LG, 'Thiếu D8 khi D6 = 3–5', 'Cao', f'D6={D6}')
    for k, v in (a.get('D7') or {}).items():
        n = {x['text']: norm(x['oth']) for x in v if x.get('oth')}
        if len(n) == 1 and not any(x['code'] == '98' for x in v): flag(LG, 'D7 chỉ nhập 1 ngành', 'Trung bình', short(k))
        if len(n) == 2 and len(set(n.values())) == 1: flag(LG, 'D7 hai ngành trùng nhau', 'Trung bình', f'{short(k)}: {list(n.values())[0]}')
    for k, v in E2.items():
        if v and E1.get(k) not in (1, 2): flag(LG, 'E2 không khớp E1', 'Cao', short(k))
    for k, v in E1.items():
        if v in (1, 2) and not E2.get(k): flag(LG, 'Thiếu E2 khi E1 khó', 'Cao', short(k))
    mod1 = A8 == 11 or A7 in (16, 17)
    if bool(a.get('H1')) != mod1: flag(LG, 'Module H1–H3 sai base', 'Cao', f'A8={A8}, A7={A7}, có H1={bool(a.get("H1"))}')
    H4 = codes(a, 'H4')
    if bool(a.get('H5')) != (A8 == 13 or 1 in H4): flag(LG, 'H5 sai base', 'Cao', f'A8={A8}, H4={H4}')
    if A4 in (1, 2) and 1 in A9: flag(LG, 'Nhân viên nhưng “quyết định tuyển ai”', 'Thấp', f'A4={A4}, A9 có code 1')
    if A2 == 4 and A4 in (4, 5): flag(LG, 'Kinh nghiệm 3–5 năm nhưng cấp GĐ/CEO', 'Thấp', f'A2=4, A4={A4}')
    if A10 in A10_TOP and A10_TOP[A10]:
        big = [short(k) for k, b in B4.items() if b in B4_LOW and B4_LOW[b] > A10_TOP[A10]]
        if big: flag(LG, 'Phòng ban (B4) lớn hơn cả công ty (A10)', 'Cao', f'A10 tối đa {A10_TOP[A10]} người; B4 vượt: {", ".join(big)}')
    for k, f2 in F2.items():
        if f2 == 6 and C2.get(k) == 3: flag(LG, 'F2 “không tuyển thạc sĩ” nhưng C2 = thạc sĩ', 'Thấp', short(k))

    # ---------- 2. CHECK VỚI THỰC TẾ ----------
    RG = 'So với thực tế'
    if active_min is not None and active_min < 25: flag(RG, 'Phỏng vấn quá nhanh (< 25 phút)', 'Cao', f'{active_min} phút')
    if active_min is not None and active_min > 120: flag(RG, 'Phỏng vấn quá dài (> 120 phút)', 'Thấp', f'{active_min} phút, {row["sessions"]} phiên')
    if row['sessions'] >= 3: flag(RG, 'Mở bài nhiều lần (≥ 3 phiên)', 'Trung bình', f'{row["sessions"]} phiên')
    if start_local.hour < 7 or start_local.hour >= 21: flag(RG, 'Phỏng vấn ngoài giờ (trước 7h / sau 21h)', 'Trung bình', row['start'])
    for k, v in F1.items():
        if v in (7, 8): flag(RG, 'Lương khởi điểm ≥ 30 triệu', 'Trung bình', f'{short(k)}: F1 code {v}')
    for k, v in C1.items():
        if v is not None and 30 <= v <= 98 and (A10 or 0) <= 3: flag(RG, 'Tuyển ≥ 30 người mới/12 tháng ở công ty < 200 người', 'Trung bình', f'{short(k)}: C1={v}, A10={A10}')
    tot_c5 = sum(C5_MID.get(v, 0) for v in C5.values())
    if A10 in (1, 2) and tot_c5 > 20: flag(RG, 'Dự kiến tuyển > 20 người mới/năm ở công ty < 50 người', 'Trung bình', f'≈{tot_c5:.0f} người/năm')
    c3a = [v[0]['code'] for v in (a.get('Q_28') or {}).values() if v]
    if len(c3a) >= 5 and len(set(c3a)) == 1: flag(RG, 'C3a trả lời 1 mức cho mọi kỹ năng', 'Trung bình', f'Tất cả = {c3a[0]}')
    for q in ('D1', 'D2', 'D3'):
        vals = {k: tuple(sorted(norm(x['oth']) for x in v if x.get('oth'))) for k, v in (a.get(q) or {}).items()}
        vals = {k: v for k, v in vals.items() if v}
        bad = [short(k) for k, v in vals.items() if any(t in JUNK or len(t) < 3 for t in v)]
        if bad: flag(RG, f'{q} câu mở quá ngắn / vô nghĩa', 'Trung bình', ', '.join(bad))
        if len(vals) >= 2 and len(set(vals.values())) == 1: flag(RG, f'{q} chép y hệt cho mọi vị trí', 'Trung bình', ' | '.join(vals[next(iter(vals))])[:80])
    dk = sum(1 for q in ('C1',) for v in C1.values() if v == 99) + sum(1 for q in ('C2', 'E1', 'F1', 'F2') for v in card1(a, q).values() if v == 99)
    row['dont_know'] = dk
    if dk >= 6: flag(RG, 'Nhiều câu trả lời “Không rõ” (≥ 6)', 'Thấp', f'{dk} lần')
    if not test:
        if phone and len(phone) != 10: flag(RG, 'SĐT đáp viên không đủ 10 số', 'Trung bình', f'{len(phone)} số')
        if phone: phones[hashlib.sha1(phone.encode()).hexdigest()].append(sid)
        if comp.strip(): companies[norm(comp)].append(sid)
        st = re.sub(r'^[\w/\-\.]*\d[\w/\-\.]*\s*', '', norm(addr))  # bỏ số nhà
        st = re.split(r',|\bp\b|\bphuong\b|\bquan\b|\bq\.', st)[0].strip()
        if len(st) >= 4: streets[(pvv, st)].append(sid)
        if city != '?' and row['a1'] and norm(city)[:6] != norm(row['a1'])[:6]: flag(RG, 'Link thành phố khác A1', 'Trung bình', f'Link {city}, A1 {row["a1"]}')
    row.update(b1_n=len(B1), b1_other=len(oth), n_flags=0)
    interviews.append(row); flags.extend(F)

byid = {r['id']: r for r in interviews}
def addf(ids, group, chk, sev, detail):
    for i in ids: flags.append(dict(id=i, pvv=byid[i]['pvv'], city=byid[i]['city'], group=group, check=chk, severity=sev, detail=detail(i)))
for h, ids in phones.items():
    if len(ids) > 1: addf(ids, 'So với thực tế', 'Trùng SĐT đáp viên với bài khác', 'Cao', lambda i: 'Trùng với ' + ', '.join(x for x in ids if x != i))
for c, ids in companies.items():
    if len(ids) > 1 and len({byid[i]['pvv'] for i in ids}) == 1:
        addf(ids, 'So với thực tế', 'Cùng PVV phỏng vấn nhiều người cùng công ty', 'Thấp', lambda i: f'{len(ids)} bài cùng một công ty: ' + ', '.join(x for x in ids if x != i))
for (p, st), ids in streets.items():
    if len(ids) > 1: addf(ids, 'So với thực tế', 'Cùng PVV, nhiều đáp viên ở cùng tên đường', 'Trung bình', lambda i: f'{len(ids)} bài cùng tên đường: ' + ', '.join(x for x in ids if x != i))
cnt = collections.Counter(f['id'] for f in flags)
SEVW = {'Cao': 3, 'Trung bình': 2, 'Thấp': 1, 'Theo dõi': 0}
for r in interviews:
    fs = [f for f in flags if f['id'] == r['id']]
    r['n_flags'] = len(fs); r['n_high'] = sum(f['severity'] == 'Cao' for f in fs)
    r['score'] = sum(SEVW[f['severity']] for f in fs)
    r.pop('company', None)

meta = [{'label': 'qc.py', 'value': CODE, 'type': 'code', 'lang': 'python'},
        {'label': 'Input', 'value': 'Google Sheet “RMIT_Industry Survey”, tab Raw_Data (XML SurveyToGo, 185 chunk)'},
        {'label': 'Snapshot', 'value': (dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) + dt.timedelta(hours=7)).strftime('%d/%m/%Y %H:%M') + ' (giờ VN)'}]
json.dump({'rows': interviews, 'meta': meta}, open('data/interviews.json', 'w'), ensure_ascii=False)
json.dump({'rows': flags, 'meta': meta}, open('data/flags.json', 'w'), ensure_ascii=False)
print(len(interviews), 'interviews', len(flags), 'flags')
print(collections.Counter((f['group'], f['check']) for f in flags).most_common())
