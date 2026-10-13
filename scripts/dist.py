import gzip, pickle, sys, collections
sys.stdout.reconfigure(encoding="utf-8")
d = pickle.load(gzip.open("data/agg/agg_2026.pkl.gz", "rb"))
ns = sorted((v["n"] for v in d.values()), reverse=True)
print("단지", len(ns), "호", sum(ns))
for t in (1, 3, 5, 10, 20, 30, 50, 100, 300, 1000):
    c = sum(1 for n in ns if n >= t)
    print(f"호수≥{t}: 단지 {c:,} / 호 {sum(n for n in ns if n >= t):,}")
print("상위 5:", [(k[1], v['n']) for k, v in sorted(d.items(), key=lambda x: -x[1]['n'])[:5]])
