import json, sys
sys.path.insert(0, r"C:\개인\wooahouse\wooagongsi\scripts")
sys.stdout.reconfigure(encoding="utf-8")
import fetch_gongsi as F

rows = F.history()
print(len(rows), "history rows")
for uddi, sn, name, reg in rows[:4]:
    r = F.S.post("https://www.data.go.kr/tcs/dss/selectFileDataDownload.do",
                 data={"publicDataDetailPk": uddi, "publicDataPk": F.PK, "atchFileId": "", "fileDetailSn": sn, "publicDataTyCode": "PR0051"}, headers=F.HDR, timeout=60)
    j = r.json()
    info = j.get("dataSetFileDetailInfo", {})
    print(name.encode("utf-8", "ignore").decode("utf-8"), "| status", j.get("status"), "| atch", j.get("atchFileId"), "| sn", j.get("fileDetailSn"), "| error", j.get("error"),
          "| info.atch", info.get("atchFileId"), info.get("publicDataPk"), info.get("fileDetailSn"))
    if j.get("atchFileId"):
        rr = F.S.get("https://www.data.go.kr/cmm/cmm/fileDownload.do", params={"atchFileId": j["atchFileId"], "fileDetailSn": j["fileDetailSn"]}, headers={"User-Agent": "Mozilla/5.0"}, stream=True, timeout=60)
        print("   fileDownload", rr.status_code, rr.headers.get("Content-Length"), rr.headers.get("Content-Disposition", "")[:80])
        rr.close()
