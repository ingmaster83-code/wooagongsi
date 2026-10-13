#!/usr/bin/env python3
"""
fetch_gongsi.py - 공공데이터포털 '국토교통부_주택 공시가격 정보'(id 3073746) 연도별 버전을 내려받는다.

- 현재 버전(2026-01-01 기준) + 과거 데이터 목록(selectHistAndCsvData.do)의 각 연도 버전 → data/raw/gongsi_{연도}.zip
- 각 zip 안의 큰 CSV(호별 공시가격 약 1,500만 건, 해제 시 약 3.5GB)는 process_gongsi.py 가 zip 에서 바로 스트리밍으로 읽는다.
- 이미 받은 연도는 건너뛴다. 사용: python scripts/fetch_gongsi.py [--years 2019-2026]
"""
import argparse, json, re, sys
from pathlib import Path

import requests

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parent.parent
RAW = ROOT / "data" / "raw"
PK = "3073746"
CUR_UDDI = "uddi:5f82ff99-7d19-4392-9497-b34767842922"
HDR = {"X-Requested-With": "XMLHttpRequest", "Referer": f"https://www.data.go.kr/data/{PK}/fileData.do", "User-Agent": "Mozilla/5.0"}
S = requests.Session()


def file_id(uddi, sn):
    r = S.post("https://www.data.go.kr/tcs/dss/selectFileDataDownload.do",
               data={"publicDataDetailPk": uddi, "publicDataPk": PK, "atchFileId": "", "fileDetailSn": sn, "publicDataTyCode": "PR0051"}, headers=HDR, timeout=60)
    j = r.json()
    if not j.get("status") or not j.get("atchFileId"):
        raise RuntimeError(j.get("error") or "download info failed")
    return j["atchFileId"], j["fileDetailSn"], j["dataSetFileDetailInfo"].get("dataNm", "")


def history():
    r = S.post("https://www.data.go.kr/tcs/dss/selectHistAndCsvData.do", data={"publicDataPk": PK, "publicDataDetailPk": CUR_UDDI}, headers=HDR, timeout=60)
    html = r.text
    rows = re.findall(r'data-public-pk="(uddi:[^"]+)"\s+data-public-detail-sn="(\d+)"\s*>\s*([^<]+?)\s*</a>\s*</td>\s*<td>(\d{4}-\d{2}-\d{2})</td>', html)
    return rows


def year_of(name):
    m = re.search(r"_(\d{4})\d{4}$", name.strip()) or re.search(r"_(\d{2})/\d{2}/(\d{4})$", name.strip())
    if m:
        return int(m.group(2) if m.lastindex == 2 else m.group(1))
    m = re.match(r"(\d{4})년", name.strip())
    return int(m.group(1)) if m else None


def download(fid, sn, out):
    tmp = out.with_suffix(".part")
    with S.get("https://www.data.go.kr/cmm/cmm/fileDownload.do", params={"atchFileId": fid, "fileDetailSn": sn}, headers={"User-Agent": "Mozilla/5.0"}, stream=True, timeout=(30, 300)) as r:
        r.raise_for_status()
        n = 0
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
                n += len(chunk)
    tmp.rename(out)
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", default="2019-2026")
    a, b = [int(x) for x in ap.parse_args().years.split("-")]
    RAW.mkdir(parents=True, exist_ok=True)
    targets = {2026: (CUR_UDDI, "1", "국토교통부_주택 공시가격 정보_20260101")}
    for uddi, sn, name, reg in history():
        y = year_of(name)
        if y and y not in targets:
            targets[y] = (uddi, sn, name)
    print("확인된 연도:", sorted(targets), flush=True)
    for y in sorted(targets, reverse=True):
        if not (a <= y <= b):
            continue
        out = RAW / f"gongsi_{y}.zip"
        if out.exists():
            print(y, "이미 있음", out.stat().st_size // 1_000_000, "MB", flush=True)
            continue
        uddi, sn, name = targets[y]
        # 과거 데이터 목록의 data-public-detail-sn 은 파일 번호가 아니라 이력 번호라서, 항상 1번 파일부터 요청하고 안 나오면 다른 번호를 시도한다
        for try_sn in ("1", sn, "2", "3", "4", "5"):
            try:
                fid, fsn, nm = file_id(uddi, try_sn)
                break
            except RuntimeError:
                continue
        else:
            print(y, "식별자를 찾지 못함", flush=True)
            continue
        n = download(fid, fsn, out)
        print(y, nm, "→", out.name, n // 1_000_000, "MB", flush=True)
    (RAW / "years.json").write_text(json.dumps({str(y): v[2] for y, v in sorted(targets.items())}, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
