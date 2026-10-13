#!/usr/bin/env python3
"""
build_data.py - data/agg/agg_{2019..2026}.pkl.gz(연도별 단지 집계)를 합쳐 사이트용 데이터를 만든다.

출력
  _rawdata/gongsi_{시도}.json  : 단지 레코드(호수 MIN_UNITS 이상) — 플러그인이 읽는다
  _rawdata/gongsi_dong.json    : 동 단위 전체 통계(소규모 건물 포함) — 동 허브 요약용
  _rawdata/gongsi_meta.json    : 기준연도·집계 메타
  ../wooaapt/_data/gongsi_slugs.json : 우아공시가 페이지가 있는 우아아파트 단지 목록(우아아파트 → 공시가격 링크용)

단지 레코드 필드(짧은 키)
  id, name, do, sg, dong, road, lot, n(2026 호수), nd(동 수), avg(2026 평균 공시가격 원), mx(최고), mn(최저), yoy(전년 대비 %, 같은 면적대 호수 가중), h[≥6/9/12/15/30억 호수],
  ar: 면적별 [[a, n, min, avg, max, 전년 평균, yoy]] (호수 많은 순 8개), ta: 대표 면적, tr: 대표 면적 연도별 [[년, avg, n]], ck: 단지 평균 연도별 [[년, avg, n]],
  kc/ap: 우아아파트 연결(kc=K-apt 코드, ap='apt:slug'|'trade:slug'), tx: 대표 면적 최근 12개월 실거래 평균(만원)·건수, rr: 현실화율(%)
"""
import gzip, hashlib, json, pickle, re, sys
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parent.parent
AGG = ROOT / "data" / "agg"
RAW = ROOT / "_rawdata"
WAAPT = ROOT.parent / "wooaapt"
YEARS = list(range(2019, 2027))
LATEST, PREV = YEARS[-1], YEARS[-2]
MIN_UNITS = int(sys.argv[1]) if len(sys.argv) > 1 else 20      # 이 호수 이상인 단지만 개별 레코드로 보관(미만은 동 통계에만 반영)

DO_MAP = {"서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천", "광주광역시": "광주", "대전광역시": "대전", "울산광역시": "울산",
          "세종특별자치시": "세종", "경기도": "경기", "강원특별자치도": "강원", "강원도": "강원", "충청북도": "충북", "충청남도": "충남", "전북특별자치도": "전북",
          "전라북도": "전북", "전라남도": "전남", "경상북도": "경북", "경상남도": "경남", "제주특별자치도": "제주"}


def norm_name(s):
    s = re.sub(r"\([^)]*\)", "", s or "")
    return re.sub(r"아파트|APT|apt|\s+|[-·.,]", "", s)


def ruby_slug_of(name, seq):
    """wooaapt/_plugins/trade_generator.rb TradeGenerator.slug_of 와 같은 규칙."""
    base = "".join(c if c.isalnum() else "-" for c in (name or ""))
    base = re.sub(r"-+", "-", base).strip("-")[:22]
    return re.sub(r"-+", "-", f"{base}-{seq}")


def load_year(y, keys):
    """연도별 집계에서 keys 에 있는 단지만 가볍게 추린다: key -> (n, s, {a: (n, sum, mn, mx)}, h, meta, nd)."""
    with gzip.open(AGG / f"agg_{y}.pkl.gz", "rb") as f:
        d = pickle.load(f)
    out = {}
    for k, v in d.items():
        if keys is None or k in keys:
            out[k] = v
    return out


def yoy_of(cur_areas, prev_areas):
    """같은 면적대(정수 ㎡)끼리만 비교한 호수 가중 변동률. 비교 가능한 호수가 전체의 50% 미만이면 None."""
    num = den = cov = tot = 0
    for a, c in cur_areas.items():
        tot += c[0]
        p = prev_areas.get(a) if prev_areas else None
        if p and p[0] > 0:
            cav, pav = c[1] / c[0], p[1] / p[0]
            num += c[0] * cav
            den += c[0] * pav
            cov += c[0]
    if den <= 0 or tot <= 0 or cov < 0.5 * tot:
        return None
    return round((num / den - 1) * 100, 1)


def load_wooaapt():
    """우아아파트 단지(K-apt)와 실거래 요약을 불러온다."""
    detail = json.loads((WAAPT / "_rawdata" / "apt_detail.json").read_text(encoding="utf-8"))
    apts = {}
    for f in (WAAPT / "_rawdata").glob("apts_*.json"):
        for a in json.loads(f.read_text(encoding="utf-8")):
            apts[a["code"]] = a
    trades_by_code, trade_only = {}, []
    for f in (WAAPT / "_rawdata").glob("trades_*.json"):
        for t in json.loads(f.read_text(encoding="utf-8")):
            if t["code"]:
                trades_by_code[t["code"]] = t
            else:
                trade_only.append(t)
    idx_k = defaultdict(list)       # (bjd10, norm name) -> [code]
    idx_kd = defaultdict(list)      # bjd10 -> [code]
    for code, d in detail.items():
        a = apts.get(code)
        if a and d.get("bjdCode"):
            idx_k[(d["bjdCode"], norm_name(a["aptName"]))].append(code)
            idx_kd[d["bjdCode"]].append(code)
    idx_t = defaultdict(list)       # (sgg5, norm dong, norm name) -> [trade rec]
    for t in trade_only:
        idx_t[(t["seq"].split("-")[0], norm_name(t["dong"]), norm_name(t["name"]))].append(t)
    return apts, trades_by_code, idx_k, idx_kd, idx_t


def main():
    print("2026 집계 불러오는 중...", flush=True)
    latest = load_year(LATEST, None)
    keys = {k for k, v in latest.items() if v["n"] >= MIN_UNITS}
    print(f"2026 단지 {len(latest):,} / 보관 대상(호수 {MIN_UNITS}↑) {len(keys):,}", flush=True)

    hist = {LATEST: {k: latest[k] for k in keys}}
    for y in YEARS[:-1]:
        hist[y] = load_year(y, keys)
        print(f"  {y}: 대상 단지 {len(hist[y]):,}", flush=True)

    # 동 단위 통계(소규모 건물 포함, 2026·2025)
    prev_all = load_year(PREV, None)
    dong_stat = defaultdict(lambda: {"cx": 0, "n": 0, "s": 0, "n9": 0, "ys": 0, "yp": 0})
    for k, v in latest.items():
        m = v["meta"]
        do = DO_MAP.get(m[0], m[0])
        dong = (m[2] + " " + m[3]).strip()
        ds = dong_stat[(do, m[1] or do, dong)]          # 세종처럼 시군구가 비어 있으면 시도명을 시군구로 쓴다
        ds["cx"] += 1
        ds["n"] += v["n"]
        ds["s"] += v["s"]
        ds["n9"] += v["h"][1]
        p = prev_all.get(k)
        if p:                       # 전년 비교(같은 면적대만)
            for a, c in v["a"].items():
                pa = p["a"].get(a)
                if pa and pa[0] > 0:
                    ds["ys"] += c[0] * (c[1] / c[0])
                    ds["yp"] += c[0] * (pa[1] / pa[0])
    del prev_all

    apts, trades_by_code, idx_k, idx_kd, idx_t = load_wooaapt()
    print(f"우아아파트 K-apt {len(apts):,}단지 / 실거래 요약 {len(trades_by_code):,}", flush=True)

    recs_by_do = defaultdict(list)
    link = {}                      # 우아아파트 쪽 링크용: "apt:slug" / "trade:slug" -> 우아공시가 slug
    used_codes = set()
    stat = {"kapt": 0, "trade": 0}
    for k in sorted(keys, key=lambda k: -latest[k]["n"]):
        bjd, name = k
        if "�" in name or not name.strip():       # 원본에서 깨진 이름(디코딩 실패)은 페이지·링크에서 제외
            continue
        v = latest[k]
        m = v["meta"]
        do = DO_MAP.get(m[0], m[0])
        dong = (m[2] + " " + m[3]).strip()
        areas = v["a"]
        top = sorted(areas.items(), key=lambda x: -x[1][0])[:8]
        ta = top[0][0]
        prev = hist[PREV].get(k)
        pareas = prev["a"] if prev else {}
        ar = []
        for a, c in top:
            pa = pareas.get(a)
            pavg = int(pa[1] / pa[0]) if pa and pa[0] else 0
            cavg = int(c[1] / c[0])
            ar.append([a, c[0], c[2], cavg, c[3], pavg, round((cavg / pavg - 1) * 100, 1) if pavg else None])
        tr = []
        ck = []
        for y in YEARS:
            hv = hist[y].get(k)
            if not hv:
                continue
            ck.append([y, int(hv["s"] / hv["n"]), hv["n"]])
            c = hv["a"].get(ta)
            if c and c[0]:
                tr.append([y, int(c[1] / c[0]), c[0]])
        # 우아아파트 연결
        kc = ap = ""
        nn = norm_name(name)
        cands = idx_k.get((bjd, nn), [])
        if not cands and len(nn) >= 3:
            cands = [c for c in idx_kd.get(bjd, []) if nn in norm_name(apts[c]["aptName"]) or norm_name(apts[c]["aptName"]) in nn]
            if len(cands) > 1:
                cands = [max(cands, key=lambda c: SequenceMatcher(None, nn, norm_name(apts[c]["aptName"])).ratio())]
        cands = [c for c in cands if c not in used_codes]
        tx = None
        if cands:
            kc = cands[0]
            used_codes.add(kc)
            ap = "apt:" + apts[kc]["slug"]
            stat["kapt"] += 1
            tr_rec = trades_by_code.get(kc)
        else:
            ts = idx_t.get((bjd[:5], norm_name(m[3]), nn), [])
            tr_rec = ts[0] if ts else None
            if tr_rec:
                ap = "trade:" + ruby_slug_of(tr_rec["name"], tr_rec["seq"])
                stat["trade"] += 1
        rr = 0
        if tr_rec:
            for g in tr_rec.get("tg", []):
                if g["a"] == ta and g.get("n12", 0) >= 2 and g.get("avg12", 0) > 0:
                    tx = [g["avg12"], g["n12"]]
                    cavg_main = areas[ta][1] / areas[ta][0]
                    rr = round(cavg_main / (g["avg12"] * 10000) * 100)
                    break
        gid = "g" + hashlib.md5(f"{bjd}|{name}".encode()).hexdigest()[:8]
        rec = {
            "id": gid, "name": name, "do": do, "sg": m[1] or do, "dong": dong, "road": m[4], "lot": f"{m[5]}-{m[6]}" if m[6] not in ("", "0") else m[5], "bjd": bjd,
            "n": v["n"], "nd": v["nd"], "avg": int(v["s"] / v["n"]), "mx": max(c[3] for c in areas.values()), "mn": min(c[2] for c in areas.values()),
            "yoy": yoy_of(areas, pareas), "h": v["h"], "ar": ar, "ta": ta, "tr": tr, "ck": ck, "kc": kc, "ap": ap, "tx": tx, "rr": rr,
        }
        recs_by_do[do].append(rec)
        if ap:
            link[ap] = ruby_slug_of(name, gid)       # 우아공시가 페이지 /g/{slug}/ (Ruby GText.slug_of 와 같은 규칙)

    RAW.mkdir(exist_ok=True)
    for old in RAW.glob("gongsi_*.json"):
        old.unlink()
    total = 0
    for do, lst in recs_by_do.items():
        lst.sort(key=lambda r: (r["sg"], r["dong"], r["name"]))
        (RAW / f"gongsi_{do}.json").write_text(json.dumps(lst, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        total += len(lst)
    dong_out = [{"do": k[0], "sg": k[1], "dong": k[2], **{x: v[x] for x in ("cx", "n", "s", "n9")}, "yoy": round((v["ys"] / v["yp"] - 1) * 100, 1) if v["yp"] > 0 else None}
                for k, v in dong_stat.items()]
    (RAW / "gongsi_dong.json").write_text(json.dumps(dong_out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (RAW / "gongsi_meta.json").write_text(json.dumps({"year": LATEST, "prev": PREV, "years": YEARS, "min_units": MIN_UNITS, "units": sum(v["n"] for v in latest.values()), "complexes": len(latest)}), encoding="utf-8")
    out = WAAPT / "_data" / "gongsi_slugs.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(link, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    sz = sum(f.stat().st_size for f in RAW.glob("gongsi_*.json")) / 1e6
    print(f"단지 레코드 {total:,} ({sz:.1f}MB) / 동 {len(dong_out):,} / 우아아파트 연결 K-apt {stat['kapt']:,} 실거래전용 {stat['trade']:,} → {out}", flush=True)


if __name__ == "__main__":
    main()
