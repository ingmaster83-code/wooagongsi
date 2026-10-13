import sys
sys.path.insert(0, r"C:\개인\wooahouse\wooagongsi\scripts")
sys.stdout.reconfigure(encoding="utf-8")
import fetch_gongsi as F
rows = F.history()
uddi = rows[1][0]
for sn in range(1, 8):
    r = F.S.post("https://www.data.go.kr/tcs/dss/selectFileDataDownload.do", data={"publicDataDetailPk": uddi, "publicDataPk": F.PK, "atchFileId": "", "fileDetailSn": sn, "publicDataTyCode": "PR0051"}, headers=F.HDR, timeout=60)
    j = r.json()
    print(sn, j.get("status"), j.get("atchFileId"), j.get("fileDetailSn"), (j.get("dataSetFileDetailInfo") or {}).get("atchFileCo"))
# 다른 연도도 한번에 확인
for uddi, sn, name, reg in rows:
    r = F.S.post("https://www.data.go.kr/tcs/dss/selectFileDataDownload.do", data={"publicDataDetailPk": uddi, "publicDataPk": F.PK, "atchFileId": "", "fileDetailSn": sn, "publicDataTyCode": "PR0051"}, headers=F.HDR, timeout=60)
    j = r.json()
    print(name[-12:], sn, j.get("atchFileId"))
