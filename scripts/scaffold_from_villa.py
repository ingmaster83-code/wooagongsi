#!/usr/bin/env python3
"""scaffold_from_villa.py - 우아빌라 사이트의 공용 뼈대(CSS·JS·include·개인정보·robots·deploy·기본 레이아웃)를 복사해 우아공시가용으로 치환한다(1회성)."""
import re, shutil, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
SRC = Path(r"C:\개인\wooahouse\wooavilla")
DST = Path(r"C:\개인\wooahouse\wooagongsi")

COLORS = {            # 틸 → 스카이블루
    "#0D9488": "#0369A1", "#0d9488": "#0369A1",
    "#14B8A6": "#0EA5E9", "#14b8a6": "#0EA5E9",
    "#0F766E": "#075985", "#0f766e": "#075985",
    "#115E59": "#0C4A6E", "#115e59": "#0C4A6E",
    "#F0FDFA": "#F0F9FF", "#f0fdfa": "#F0F9FF",
    "#CCFBF1": "#E0F2FE", "#ccfbf1": "#E0F2FE",
    "#99F6E4": "#BAE6FD", "#99f6e4": "#BAE6FD",
    "#5EEAD4": "#7DD3FC", "#5eead4": "#7DD3FC",
}
TEXT = [("wooavilla", "wooagongsi"), ("우아빌라", "우아공시가")]


def conv(text):
    for a, b in COLORS.items():
        text = text.replace(a, b)
    for a, b in TEXT:
        text = text.replace(a, b)
    return text


def copy(rel, convert=True):
    s, d = SRC / rel, DST / rel
    d.parent.mkdir(parents=True, exist_ok=True)
    if convert:
        d.write_text(conv(s.read_text(encoding="utf-8")), encoding="utf-8")
    else:
        shutil.copyfile(s, d)
    print("복사:", rel)


for rel in ["assets/css/main.css", "assets/js/ad-dev-placeholder.js", "assets/js/wooa-sidebar.js", "assets/js/wooa-sites-bar.js",
            "_includes/ad.html", "_includes/faq.html", "privacy/index.html", "robots.txt", "CNAME", "Gemfile", "_layouts/default.html"]:
    copy(rel, convert=not rel.startswith("assets/js"))

# 기본 레이아웃: 네이버 메타(우아빌라 값) 제거, 내비·푸터 문구 교체
p = DST / "_layouts" / "default.html"
s = p.read_text(encoding="utf-8")
s = re.sub(r'\s*<meta name="naver-site-verification"[^>]*/>\n', "\n", s)
s = s.replace("우아공시가 - 빌라·오피스텔 실거래가·전세가율", "우아공시가 - 아파트·빌라 공시가격 조회와 추이")
s = s.replace("{{ '/jeonse/' | relative_url }}\">전세가율</a>", "{{ '/rank/' | relative_url }}\">랭킹</a>")
s = s.replace("page.layout == 'building' or page.layout == 'dong' or page.layout == 'sigungu' or page.layout == 'do' or page.layout == 'jeonse'",
              "page.layout == 'complex' or page.layout == 'dong' or page.layout == 'sigungu' or page.layout == 'do' or page.layout == 'rank'")
s = s.replace("page.layout == 'building'", "page.layout == 'complex'")
i = s.find('<p class="footer-disclaimer">')
j = s.find("</p>", i) + 4
disc = '''<p class="footer-disclaimer">
      공시가격은 국토교통부 '주택 공시가격 정보'(공공데이터포털, 매년 1월 1일 기준 공동주택 공시가격)를 단지(법정동+단지명) 단위로 집계한 것입니다. 호별 가격·동호수는 표시하지 않으며, 단지 평균과 면적별 최저·평균·최고를 보여줍니다.<br>
      세금·건강보험료 등 산정에 쓰이는 공식 공시가격은 부동산공시가격알리미(realtyprice.kr)에서 확인하세요. 현실화율·변동률은 참고용 계산값이며 법적 효력이 없습니다.
    </p>'''
s = s[:i] + disc + s[j:]
s = s.replace('<a href="https://wooaapt.wooahouse.com">우아아파트</a> ·\n      <a href="https://wooahakgun.wooahouse.com">우아학군</a> ·', '<a href="https://wooaapt.wooahouse.com">우아아파트</a> ·\n      <a href="https://wooahakgun.wooahouse.com">우아학군</a> ·\n      <a href="https://wooavilla.wooahouse.com">우아빌라</a> ·')
p.write_text(s, encoding="utf-8")
print("기본 레이아웃 정리 완료")
