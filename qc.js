/* QC checks for P26129 Industry Survey F2F — chạy trong trình duyệt.
   Input: QC.runList(danh sách bài từ tab QC_Data) hoặc QC.run(XML SurveyToGo ghép từ tab Raw_Data).
   Output: {interviews, flags}. Tên, SĐT, địa chỉ, công ty chỉ dùng để tìm trùng, không đưa ra ngoài. */
(function (global) {
  const B4_TOP = {1: 4, 2: 19, 3: 49, 4: 199, 5: null};
  const B4_LOW = {1: 1, 2: 5, 3: 20, 4: 50, 5: 200};
  const A10_TOP = {1: 19, 2: 49, 3: 199, 4: 499, 5: 1999, 6: null};
  const C5_MID = {1: 0, 2: 1.5, 3: 4, 4: 8, 5: 15, 6: 35, 7: 50};
  const JUNK = new Set(['', 'khong', 'ko', 'k', 'x', 'xx', '.', '-', 'na', 'n/a', 'khong biet', 'kb', 'abc']);
  // Chức danh chung theo cấp bậc (nhân viên, trưởng phòng…) dùng chung cho nhiều vị trí là hợp lý
  const GENERIC_TITLE = /^(nhan vien|chuyen vien|chuyen gia|thuc tap sinh|truong nhom|truong phong|pho phong|quan ly|giam doc|pho giam doc|team leader|leader|manager|staff|executive|specialist|intern|supervisor|giam sat)( .{0,15})?$/;
  const SEVW = {'Cao': 3, 'Trung bình': 2, 'Thấp': 1, 'Theo dõi': 0};
  // Trạng thái bài được tính; các trạng thái khác (Rejected, …) bỏ qua hoàn toàn
  const KEEP_STATUS = /^(approved|requires approval)$/i;
  const LG = 'Logic giữa câu', RG = 'So với thực tế';

  const kids = (el, tag) => el ? [...el.children].filter((c) => c.tagName === tag) : [];
  const kid = (el, tag) => kids(el, tag)[0];
  const kt = (el, tag) => { const k = kid(el, tag); return k ? k.textContent : null; };
  const norm = (s) => (s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/g, 'd').replace(/\s+/g, ' ').trim();
  const short = (card) => card.startsWith('RF') ? card.split('_')[0] : card.replace(/:$/, '');
  const int = (x) => x == null || x === '' ? null : parseInt(x, 10);
  const pad = (n) => String(n).padStart(2, '0');

  function answersOf(el) {
    return kids(kid(el, 'Answers'), 'Answer').map((x) => ({code: kt(x, 'Code'), text: kt(x, 'Text'), oth: kt(x, 'OtherSpec')}));
  }
  function parseSubject(s) {
    const m = {};
    for (const c of s.children) if (c.tagName !== 'Chapter') m[c.getAttribute('Field') || c.tagName] = c.textContent;
    const a = {}, times = [];
    for (const q of s.getElementsByTagName('Question')) {
      const v = kt(q, 'Variable'), qt = kt(q, 'QType'), t = kt(q, 'AnsweredTimeStamp');
      if (t) times.push(new Date(t));
      if (qt === 'eqtAmerican') { const an = answersOf(q)[0]; a[v] = {code: an ? an.code : null, text: kt(q, 'QuestionAnswer'), oth: an ? an.oth : null}; }
      else if (qt === 'eqtMultiSelect') a[v] = answersOf(q);
      else {
        const d = {};
        for (const tp of kids(kid(q, 'Topics'), 'Topic')) {
          const k = kt(tp, 'Text');
          d[k] = (qt === 'eqtMultiNumeric' || qt === 'eqtMultiText') ? kt(tp, 'TopicAnswer') : answersOf(tp);
        }
        a[v] = d;
      }
    }
    times.sort((x, y) => x - y);
    return {m, a, times};
  }
  const code = (a, q) => { const v = a[q]; return v && !Array.isArray(v) && v.code != null && v.code !== '' ? int(v.code) : null; };
  const codes = (a, q) => (a[q] || []).filter((x) => x.code).map((x) => int(x.code));
  const card1 = (a, q) => { const o = {}; for (const [k, v] of Object.entries(a[q] || {})) if (Array.isArray(v) && v[0] && v[0].code) o[k] = int(v[0].code); return o; };
  const cardm = (a, q) => { const o = {}; for (const [k, v] of Object.entries(a[q] || {})) o[k] = (v || []).filter((x) => x.code).map((x) => int(x.code)); return o; };
  const info = (obj, word) => { for (const [k, v] of Object.entries(obj || {})) if (k.toLowerCase().includes(word)) return v || ''; return ''; };

  // Đường cũ: XML thô (Raw_Data) -> danh sách bài {m, a, times}
  function run(xmlText) {
    const doc = new DOMParser().parseFromString(xmlText, 'text/xml');
    if (doc.getElementsByTagName('parsererror').length) throw new Error('XML chưa đầy đủ (có thể Sheet đang sync)');
    const subs = [];
    for (const s of doc.getElementsByTagName('Subject')) {
      if (!s.querySelector(':scope > [Field="SbjNum"]')) continue;
      const p = parseSubject(s);
      subs.push({m: p.m, a: p.a, times: p.times.length > 1 ? [+p.times[0], +p.times[p.times.length - 1]] : []});
    }
    return runList(subs);
  }

  // Đường mới: danh sách bài thu gọn (QC_Data). times = [mốc đầu, mốc cuối] (ms) hoặc [] nếu <2 mốc.
  function runList(subs) {
    const interviews = [], flags = [];
    const phones = new Map(), companies = new Map(), streets = new Map();
    const push = (map, k, v) => { if (!map.has(k)) map.set(k, []); map.get(k).push(v); };

    for (const {m, a, times} of subs) {
      if (m.Complete && m.Complete !== 'True') continue;
      if (!KEEP_STATUS.test((m.Status || '').trim())) continue;   // chỉ lấy bài Approved / Requires Approval
      const sid = m.SbjNum, nam = m.SbjNam || '';
      const test = /^(STGTester|RMIT)$/i.test(nam.trim()) || m.Test === 'True';   // bài test: tài khoản STGTester, RMIT hoặc cờ Test
      const pvv = test ? 'TEST' : (nam.length >= 3 && /^\d+$/.test(nam) ? nam.slice(0, -1) : (nam || '?'));
      const city = m.CustomData1 || '?';
      const st = new Date(new Date(m.VStart).getTime() + 7 * 3600e3);
      const minutes = times.length > 1 ? Math.round((times[times.length - 1] - times[0]) / 6000) / 10 : null;
      const Q6 = a.Q_6 || {};
      const phone = (info(Q6, 'điện thoại') || '').replace(/\D/g, ''), comp = (info(Q6, 'công ty') || '').trim(), addr = info(Q6, 'địa chỉ');
      const row = {id: sid, pvv, city, date: `${st.getUTCFullYear()}-${pad(st.getUTCMonth() + 1)}-${pad(st.getUTCDate())}`, start: `${pad(st.getUTCHours())}:${pad(st.getUTCMinutes())}`,
        minutes, sessions: int(m.NumberOfSessions) || 1, status: m.Status, test, a1: (a.A1 || {}).text || null,
        a4: code(a, 'A4'), a7: code(a, 'A7'), a8: code(a, 'A8'), a10: code(a, 'A10'), a11: code(a, 'A11'), a2: code(a, 'A2')};
      const F = [];
      const flag = (group, check, severity, detail) => F.push({id: sid, pvv, city, group, check, severity, detail});

      const [A1, A2, A3, A4, A5, A6, A10, A7, A8] = ['A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'A10', 'A7', 'A8'].map((q) => code(a, q));
      const A9 = codes(a, 'A9'), B1 = a.B1 || [], B5 = a.B5 || [];
      const B4 = card1(a, 'B4'), C1 = {};
      for (const [k, v] of Object.entries(a.C1 || {})) C1[k] = /^-?\d+$/.test(String(v || '').trim()) ? int(String(v).trim()) : null;
      const C2 = card1(a, 'C2'), C3 = card1(a, 'C3'), C4 = card1(a, 'C4'), C5 = card1(a, 'C5');
      const C6 = cardm(a, 'C6'), D2 = cardm(a, 'D2'), D3 = a.D3 || {};
      const D4 = card1(a, 'D4'), D5 = card1(a, 'D5'), D6 = code(a, 'D6');
      const E1 = card1(a, 'E1'), E2 = cardm(a, 'E2'), F1 = card1(a, 'F1'), F2 = card1(a, 'F2');

      // ---------- 1. LOGIC GIỮA CÁC CÂU ----------
      const so = [];
      if (A1 === 4) so.push('A1=4 (tỉnh khác)');
      if (A2 != null && ![4, 5, 6, 7].includes(A2)) so.push(`A2=${A2}`);
      if (A3 != null && A3 <= 2) so.push(`A3=${A3}`);
      if (A5 === 2) so.push('A5=Không');
      if (A6 === 2) so.push('A6=Không');
      if (A9.includes(98)) so.push('A9=98');
      if (A10 === 99) so.push('A10=Không rõ');
      if (Object.values(B4).includes(99)) so.push('B4=Không rõ');
      if (so.length) flag(LG, 'Lẽ ra bị screen out', 'Cao', so.join(', ') + ' nhưng bài vẫn hoàn thành');
      if ([1, 2].includes(A4) && A5 == null) flag(LG, 'Sai nhánh A4 → A5/A6', 'Cao', `A4=${A4} nhưng không có A5`);
      if ([3, 4, 5].includes(A4) && A6 == null) flag(LG, 'Sai nhánh A4 → A5/A6', 'Cao', `A4=${A4} nhưng không có A6`);
      const oth = B1.filter((x) => !(x.text || '').startsWith('RF'));
      if (B1.length < 3) flag(LG, 'B1 chọn dưới 3 vị trí', 'Cao', `B1 có ${B1.length} vị trí`);
      const b1t = new Set(B1.map((x) => x.text));
      if (B5.length !== 3) flag(LG, 'B5 không đúng 3 vị trí', 'Cao', `B5 có ${B5.length} vị trí`);
      if (B5.some((x) => !b1t.has(x.text))) flag(LG, 'B5 ngoài danh sách B1', 'Cao', 'Có vị trí ở B5 không chọn ở B1');
      for (const [k, v] of Object.entries(C1)) if (v != null && !(v >= 0 && v <= 99)) flag(LG, 'C1 ngoài khoảng 0–98/99', 'Cao', `${short(k)}: C1=${v}`);
      for (const [q, map, ok] of [['C2', C2, (c) => c !== 0], ['C3', C3, (c) => c !== 0 && c !== 99]])
        for (const k of Object.keys(map)) if (k in C1 && C1[k] != null && !ok(C1[k])) flag(LG, `${q} hỏi sai thẻ (theo C1)`, 'Cao', `${short(k)}: C1=${C1[k]} vẫn có ${q}`);
      for (const [k, v] of Object.entries(C1)) {
        if (v != null && v >= 1 && v <= 98 && !(k in C3)) flag(LG, 'Thiếu C3 cho thẻ C1 1–98', 'Cao', `${short(k)}: C1=${v}`);
        const top = B4_TOP[B4[k]];
        if (v != null && v !== 99 && top != null && v > top * 2 && v - top >= 5) flag(LG, 'C1 lớn hơn hẳn quy mô B4', 'Trung bình', `${short(k)}: C1=${v} người nhưng B4 tối đa ${top}`);
      }
      for (const [k, c4] of Object.entries(C4)) {
        if (c4 === 3 && (C6[k] || []).length) flag(LG, 'C6 hỏi thẻ có C4 = Giữ nguyên', 'Cao', short(k));
        if ([1, 2, 4, 5].includes(c4) && !(k in C6)) flag(LG, 'Thiếu C6 cho thẻ có thay đổi', 'Cao', `${short(k)}: C4=${c4}`);
      }
      const c5v = Object.values(C5);
      for (const k of Object.keys(D3)) if ((D2[k] || []).includes(96)) flag(LG, 'D3 hỏi thẻ D2 = Ngành nào cũng được', 'Cao', short(k));
      for (const k of Object.keys(D5)) if (![1, 2].includes(D4[k])) flag(LG, 'D5 có chương trình không chấm 1–2 ở D4', 'Cao', `${short(k).slice(0, 40)} (D4=${D4[k] != null ? D4[k] : 'không có thẻ'})`);
      for (const [k, v] of Object.entries(D4)) if ([1, 2].includes(v) && !(k in D5)) flag(LG, 'Thiếu D5 cho chương trình D4 1–2', 'Cao', short(k).slice(0, 30));
      if ((a.D7 || a.D8) && ![3, 4, 5].includes(D6)) flag(LG, 'D7/D8 hỏi sai base D6', 'Cao', `D6=${D6}`);
      if ([3, 4, 5].includes(D6) && !a.D8) flag(LG, 'Thiếu D8 khi D6 = 3–5', 'Cao', `D6=${D6}`);
      for (const [k, v] of Object.entries(a.D7 || {})) {
        const n = {}; for (const x of v || []) if (x.oth) n[x.text] = norm(x.oth);
        const vals = Object.values(n);
        const pairInOne = vals.length === 1 && /kết hợp|ket hop|\bvà\b|\bva\b|\+|&|,|\//.test(vals[0]);
        if (vals.length === 1 && !pairInOne && !(v || []).some((x) => x.code === '98')) flag(LG, 'D7 chỉ nhập 1 ngành', 'Thấp', `${short(k)}: ${vals[0]}`);
        if (vals.length === 2 && vals[0] === vals[1]) flag(LG, 'D7 hai ngành trùng nhau', 'Trung bình', `${short(k)}: ${vals[0]}`);
      }
      for (const [k, v] of Object.entries(E2)) if (v.length && ![1, 2].includes(E1[k])) flag(LG, 'E2 không khớp E1', 'Cao', short(k));
      for (const [k, v] of Object.entries(E1)) if ([1, 2].includes(v) && !(E2[k] || []).length) flag(LG, 'Thiếu E2 khi E1 khó', 'Cao', short(k));
      const mod1 = A8 === 11 || A7 === 16 || A7 === 17, hasH1 = !!(a.H1 && (a.H1.code || a.H1.text));
      if (hasH1 !== mod1) flag(LG, 'Module H1–H3 sai base', 'Cao', `A8=${A8}, A7=${A7}, có H1=${hasH1}`);
      const H4 = codes(a, 'H4'), hasH5 = !!(a.H5 && Object.keys(a.H5).length);
      if (hasH5 !== (A8 === 13 || H4.includes(1))) flag(LG, 'H5 sai base', 'Cao', `A8=${A8}, H4=[${H4}]`);
      if (A10_TOP[A10]) {
        const big = Object.entries(B4).filter(([, b]) => B4_LOW[b] > A10_TOP[A10]).map(([k]) => short(k));
        if (big.length) flag(LG, 'Phòng ban (B4) lớn hơn cả công ty (A10)', 'Cao', `A10 tối đa ${A10_TOP[A10]} người; B4 vượt: ${big.join(', ')}`);
      }
      for (const [k, f2] of Object.entries(F2)) if (f2 === 6 && C2[k] === 3) flag(LG, 'F2 “không tuyển thạc sĩ” nhưng C2 = thạc sĩ', 'Thấp', short(k));

      // ---------- 2. SO VỚI THỰC TẾ ----------
      if (minutes != null && minutes < 25) flag(RG, 'Phỏng vấn quá nhanh (< 25 phút)', 'Cao', `${minutes} phút`);
      if (st.getUTCHours() < 7 || st.getUTCHours() >= 22) flag(RG, 'Phỏng vấn ngoài giờ (trước 7h / sau 22h)', 'Trung bình', row.start);
      for (const [k, v] of Object.entries(F1)) if (v === 8) flag(RG, 'Lương khởi điểm ≥ 40 triệu', 'Trung bình', short(k));
      for (const [k, v] of Object.entries(C1)) if (v != null && v >= 30 && v <= 98 && (A10 || 0) <= 3) flag(RG, 'Tuyển ≥ 30 người mới/12 tháng ở công ty < 200 người', 'Trung bình', `${short(k)}: C1=${v}, A10=${A10}`);
      const totC5 = c5v.reduce((s, v) => s + (C5_MID[v] || 0), 0);
      if ((A10 === 1 || A10 === 2) && totC5 > 20) flag(RG, 'Dự kiến tuyển > 20 người mới/năm ở công ty < 50 người', 'Trung bình', `≈${Math.round(totC5)} người/năm`);
      const c3a = Object.values(a.Q_28 || {}).filter((v) => v && v[0]).map((v) => v[0].code);
      if (c3a.length >= 5 && new Set(c3a).size === 1 && ['1', '5'].includes(c3a[0])) flag(RG, 'C3a chấm cùng mức cực (toàn 1 hoặc toàn 5)', 'Thấp', `Tất cả = ${c3a[0]}`);
      for (const q of ['D1', 'D2', 'D3']) {
        const vals = {};
        for (const [k, v] of Object.entries(a[q] || {})) { const t = (v || []).filter((x) => x.oth).map((x) => norm(x.oth)).sort(); if (t.length) vals[k] = t; }
        const ks = Object.keys(vals);
        const bad = ks.filter((k) => vals[k].some((t) => JUNK.has(t) || t.length < 3)).map(short);
        if (bad.length) flag(RG, `${q} câu mở quá ngắn / vô nghĩa`, 'Trung bình', bad.join(', '));
        const generic = (t) => GENERIC_TITLE.test(t);
        if (q === 'D1' && ks.length >= 2 && new Set(ks.map((k) => JSON.stringify(vals[k]))).size === 1 && !vals[ks[0]].every(generic))
          flag(RG, 'D1 cùng một chức danh cụ thể cho mọi vị trí', 'Trung bình', vals[ks[0]].join(' | ').slice(0, 80));
      }
      const dk = Object.values(C1).filter((v) => v === 99).length + ['C2', 'E1', 'F1', 'F2'].reduce((s, q) => s + Object.values(card1(a, q)).filter((v) => v === 99).length, 0);
      row.dont_know = dk;
      if (dk >= 6) flag(RG, 'Nhiều câu trả lời “Không rõ” (≥ 6)', 'Thấp', `${dk} lần`);
      if (!test) {
        if (phone && phone.length !== 10) flag(RG, 'SĐT đáp viên không đủ 10 số', 'Trung bình', `${phone.length} số`);
        if (phone) push(phones, phone, sid);
        if (comp) push(companies, norm(comp), sid);
        let stn = norm(addr).replace(/^[\w\/\-\.]*\d[\w\/\-\.]*\s*/, '');
        stn = stn.split(/,|\bp\b|\bphuong\b|\bquan\b|\bq\./)[0].trim();
        if (stn.length >= 4) push(streets, pvv + '|' + stn, sid);
        if (city !== '?' && row.a1 && norm(city).slice(0, 6) !== norm(row.a1).slice(0, 6)) flag(RG, 'Link thành phố khác A1', 'Trung bình', `Link ${city}, A1 ${row.a1}`);
      }
      row.b1_n = B1.length; row.b1_other = oth.length;
      interviews.push(row); flags.push(...F);
    }

    const byid = Object.fromEntries(interviews.map((r) => [r.id, r]));
    const addf = (ids, check, sev, detail) => { for (const i of ids) flags.push({id: i, pvv: byid[i].pvv, city: byid[i].city, group: RG, check, severity: sev, detail: detail(i)}); };
    const others = (ids, i) => ids.filter((x) => x !== i).join(', ');
    for (const ids of phones.values()) if (ids.length > 1) addf(ids, 'Trùng SĐT đáp viên với bài khác', 'Cao', (i) => 'Trùng với ' + others(ids, i));
    for (const ids of companies.values()) if (ids.length > 1 && new Set(ids.map((i) => byid[i].pvv)).size === 1) addf(ids, 'Cùng PVV phỏng vấn nhiều người cùng công ty', 'Thấp', (i) => `${ids.length} bài cùng một công ty: ` + others(ids, i));
    for (const ids of streets.values()) if (ids.length > 1) addf(ids, 'Cùng PVV, nhiều đáp viên ở cùng tên đường', 'Trung bình', (i) => `${ids.length} bài cùng tên đường: ` + others(ids, i));
    for (const r of interviews) {
      const fs = flags.filter((f) => f.id === r.id);
      r.n_flags = fs.length; r.n_high = fs.filter((f) => f.severity === 'Cao').length; r.score = fs.reduce((s, f) => s + SEVW[f.severity], 0);
    }
    return {interviews, flags};
  }
  global.QC = {run, runList};
})(typeof window !== 'undefined' ? window : globalThis);
