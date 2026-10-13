import json, sys
sys.path.insert(0, r"C:\개인\wooahouse\wooagongsi\scripts")
sys.stdout.reconfigure(encoding="utf-8")
import fetch_gongsi as F
rows = F.history()
uddi, sn, name, reg = rows[1]
r = F.S.post("https://www.data.go.kr/tcs/dss/selectFileDataDownload.do", data={"publicDataDetailPk": uddi, "publicDataPk": F.PK, "atchFileId": "", "fileDetailSn": sn, "publicDataTyCode": "PR0051"}, headers=F.HDR, timeout=60)
j = r.json()
print({k: v for k, v in j.items() if k != "dataSetFileDetailInfo"})
info = j["dataSetFileDetailInfo"]
for k, v in info.items():
    if v not in (None, "", 0, [], {}) and ("atch" in k.lower() or "file" in k.lower() or "FILE_" in str(v) or k in ("dataNm", "publicDataDetailPk", "updtDt")):
        print(k, "=", str(v)[:120])
print([ (k, str(v)[:80]) for k, v in info.items() if "FILE_" in str(v)])
vo = j.get("fileDataRegistVO") or {}
print({k: str(v)[:80] for k, v in vo.items() if v not in (None, "", 0, [], {}) and ("atch" in k.lower() or "file" in k.lower() or "FILE_" in str(v))})
