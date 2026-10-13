#!/usr/bin/env python3
"""
aggregate_year.py <연도> - data/raw/gongsi_{연도}.zip 안의 호별 공시가격 CSV(약 1,500만 행)를 스트리밍으로 읽어
(법정동코드, 단지명) 단위로 집계해 data/agg/agg_{연도}.pkl.gz 로 저장한다.

집계 레코드: key=(법정동코드10, 단지명) → {
  n: 호수, s: 공시가격 합(원), a: {전용면적 정수㎡: [호수, 합, 최저, 최고]},
  h: 공시가격 구간별 호수 [≥6억, ≥9억, ≥12억, ≥15억, ≥30억],
  meta(마지막 행 기준): 시도, 시군구, 읍면, 동리, 도로명주소, 본번, 부번, nd: 동(棟) 수 추정(고유 동명 수, 최대 50까지만 셈)
}
사용: python scripts/aggregate_year.py 2026
"""
import codecs, csv, gzip, io, pickle, sys, time, zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parent.parent
RAW = ROOT / "data" / "raw"
AGG = ROOT / "data" / "agg"
csv.field_size_limit(1 << 20)

COLS = {"법정동코드": ("법정동코드",), "시도": ("시도",), "시군구": ("시군구",), "읍면": ("읍면",), "동리": ("동리",), "도로명주소": ("도로명주소",),
        "본번": ("본번",), "부번": ("부번",), "단지명": ("단지명",), "동명": ("동명",), "전용면적": ("전용면적",), "공시가격": ("공시가격",)}


def open_csv(zpath):
    z = zipfile.ZipFile(zpath)
    big = max(z.infolist(), key=lambda i: i.file_size)
    raw = z.open(big)
    head = raw.read(8192)
    raw.close()
    enc = "utf-8"
    try:
        codecs.getincrementaldecoder("utf-8")().decode(head, final=False)    # 끝이 멀티바이트 중간에서 잘려도 오류로 보지 않는다
    except UnicodeDecodeError:
        enc = "cp949"
    return io.TextIOWrapper(z.open(big), encoding=enc, newline="", errors="replace"), big.file_size, enc


def main(year):
    t0 = time.time()
    f, size, enc = open_csv(RAW / f"gongsi_{year}.zip")
    rd = csv.reader(f)
    head = next(rd)
    idx = {}
    for k, alts in COLS.items():
        for a in alts:
            if a in head:
                idx[k] = head.index(a)
                break
        else:
            raise SystemExit(f"컬럼 없음: {k} / 헤더 {head}")
    i_bjd, i_nm, i_ar, i_pr, i_dg = idx["법정동코드"], idx["단지명"], idx["전용면적"], idx["공시가격"], idx["동명"]
    out = {}
    n = bad = 0
    for r in rd:
        n += 1
        try:
            price = int(r[i_pr])
            area = float(r[i_ar])
        except (ValueError, IndexError):
            bad += 1
            continue
        if price <= 0:
            bad += 1
            continue
        key = (r[i_bjd], r[i_nm])
        rec = out.get(key)
        a = int(area)                    # 전용면적 정수㎡(버림): 84.97 → 84, 우아아파트 실거래 면적대와 같은 규칙
        if rec is None:
            rec = out[key] = {"n": 0, "s": 0, "a": {}, "dg": set(), "h": [0, 0, 0, 0, 0],
                              "meta": [r[idx["시도"]], r[idx["시군구"]], r[idx["읍면"]], r[idx["동리"]], r[idx["도로명주소"]], r[idx["본번"]], r[idx["부번"]]]}
        rec["n"] += 1
        rec["s"] += price
        if price >= 600_000_000:
            h = rec["h"]
            h[0] += 1
            if price >= 900_000_000:
                h[1] += 1
                if price >= 1_200_000_000:
                    h[2] += 1
                    if price >= 1_500_000_000:
                        h[3] += 1
                        if price >= 3_000_000_000:
                            h[4] += 1
        ag = rec["a"].get(a)
        if ag is None:
            rec["a"][a] = [1, price, price, price]
        else:
            ag[0] += 1
            ag[1] += price
            if price < ag[2]:
                ag[2] = price
            if price > ag[3]:
                ag[3] = price
        if len(rec["dg"]) < 50:
            rec["dg"].add(r[i_dg])
        if n % 2_000_000 == 0:
            print(f"  {year}: {n:,}행 / 단지 {len(out):,} / {time.time() - t0:.0f}s", flush=True)
    for rec in out.values():
        rec["nd"] = len(rec.pop("dg"))
    AGG.mkdir(parents=True, exist_ok=True)
    with gzip.open(AGG / f"agg_{year}.pkl.gz", "wb") as g:
        pickle.dump(out, g, protocol=4)
    print(f"{year}: 행 {n:,} (제외 {bad:,}) / 단지 {len(out):,} / 인코딩 {enc} / {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]))
