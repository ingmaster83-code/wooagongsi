"""peek_gongsi.py <zip> [행수] - zip 안 CSV 앞부분을 읽어 컬럼·값 분포를 본다."""
import collections, csv, io, sys, zipfile

sys.stdout.reconfigure(encoding="utf-8")
path = sys.argv[1]
N = int(sys.argv[2]) if len(sys.argv) > 2 else 200000
z = zipfile.ZipFile(path)
name = max(z.infolist(), key=lambda i: i.file_size)
print("CSV:", name.filename.encode("cp437", "ignore").decode("cp949", "ignore"), name.file_size)
with z.open(name) as f:
    rd = csv.reader(io.TextIOWrapper(f, encoding="utf-8", newline=""))
    head = next(rd)
    print("컬럼:", head)
    rows = []
    for i, r in enumerate(rd):
        rows.append(r)
        if i + 1 >= N:
            break
print("행", len(rows))
for r in rows[:3]:
    print(r)
idx = {h: i for i, h in enumerate(head)}
for col in ("특수지명", "단지명", "동명", "호명", "시도"):
    if col in idx:
        c = collections.Counter(r[idx[col]] for r in rows)
        print(col, "빈값", c.get("", 0), "고유", len(c), c.most_common(5))
