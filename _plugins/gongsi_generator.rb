require 'json'

module Jekyll
  module GText
    module_function

    def hangul_tail?(s)
      c = s.to_s.strip.sub(/[\s\)\]\}\>'"”’.,!?~·\-]+\z/, '')[-1]
      !c.nil? && c.ord >= 0xAC00 && c.ord <= 0xD7A3
    end

    def batchim?(s)
      c = s.to_s.strip.sub(/[\s\)\]\}\>'"”’.,!?~·\-]+\z/, '')[-1]
      return false if c.nil?
      o = c.ord
      (o >= 0xAC00 && o <= 0xD7A3) ? ((o - 0xAC00) % 28 != 0) : false
    end

    def josa(word, with_b, without_b)
      return "#{word}#{with_b}(#{without_b})" unless hangul_tail?(word)
      word.to_s + (batchim?(word) ? with_b : without_b)
    end

    def eun_neun(w); josa(w, '은', '는'); end

    def fmt(n)
      n.to_i.to_s.reverse.scan(/\d{1,3}/).join(',').reverse
    end

    # 원 단위 → "12억 3,500만원" (만원 미만 반올림)
    def won(n)
      m = (n.to_f / 10_000).round
      return '-' if m <= 0
      eok = m / 10_000
      rest = m % 10_000
      if eok.positive?
        rest.zero? ? "#{eok}억원" : "#{eok}억 #{fmt(rest)}만원"
      else
        "#{fmt(m)}만원"
      end
    end

    def pct(v)
      return '-' if v.nil?
      v >= 0 ? "+#{format('%.1f', v)}%" : "#{format('%.1f', v)}%"
    end

    def py(a)
      (a * 1.32 / 3.3058).round
    end

    def slug_of(name, id)
      base = name.to_s.gsub(/[^\p{Hangul}\p{Alnum}]+/, '-').gsub(/-+/, '-').gsub(/\A-|-\z/, '')[0, 22]
      "#{base}-#{id}".gsub(/-+/, '-')
    end
  end

  class GongsiGenerator < Generator
    safe true
    priority :normal

    MAX_COMPLEX_PAGES = 32_000      # 용량(Pages 1GB) 때문에 우아아파트 연결 단지 + 호수 많은 단지 순으로 상세 페이지를 만든다
    DONG_ROWS = 150
    SEARCH_MAX = 32_000
    RANK_MIN_UNITS = 100

    def generate(site)
      dir = File.join(site.source, '_rawdata')
      meta = JSON.parse(File.read(File.join(dir, 'gongsi_meta.json'), encoding: 'utf-8'))
      dong_stats = JSON.parse(File.read(File.join(dir, 'gongsi_dong.json'), encoding: 'utf-8'))
      recs = []
      Dir.glob(File.join(dir, 'gongsi_*.json')).sort.each do |f|
        next if f.end_with?('gongsi_meta.json') || f.end_with?('gongsi_dong.json')
        recs.concat(JSON.parse(File.read(f, encoding: 'utf-8')))
      end
      year = meta['year']
      hak = site.data['hak_slugs'] || {}

      ranked = recs.sort_by { |r| [-((r['ap'].to_s.empty? ? 0 : 100_000) + r['n']), r['id']] }
      page_set = ranked.first(MAX_COMPLEX_PAGES)
      page_set.each { |r| r['url'] = "/g/#{GText.slug_of(r['name'], r['id'])}/" }

      by_dong = recs.group_by { |r| [r['do'], r['sg'], r['dong']] }
      by_sg = recs.group_by { |r| [r['do'], r['sg']] }
      by_do = recs.group_by { |r| r['do'] }
      dstat = {}
      dong_stats.each { |d| dstat[[d['do'], d['sg'], d['dong']]] = d }

      counts = Hash.new(0)
      page_set.each do |r|
        nb = by_dong[[r['do'], r['sg'], r['dong']]].select { |x| x['url'] && x['id'] != r['id'] }.sort_by { |x| -x['n'] }.first(8)
        site.pages << ComplexPage.new(site, r, nb, year, hak)
        counts[:complex] += 1
      end

      # 시도/시군구/동 집계(소규모 건물까지 포함한 동 통계 사용)
      do_names = (by_do.keys | dong_stats.map { |d| d['do'] }).sort
      do_names.each do |do_short|
        dl = dong_stats.select { |d| d['do'] == do_short }
        sg_rows = dl.group_by { |d| d['sg'] }.map { |sg, ds| GongsiGenerator.agg_row(sg, ds) }.sort_by { |h| [-h['n'], h['name']] }
        site.pages << DoHubPage.new(site, do_short, sg_rows, GongsiGenerator.agg_row(do_short, dl), by_do[do_short] || [], year)
        counts[:do] += 1
        dl.group_by { |d| d['sg'] }.each do |sg, ds|
          dong_rows = ds.map { |d| GongsiGenerator.agg_row(d['dong'], [d]).merge('hub' => (by_dong[[do_short, sg, d['dong']]] || []).any?) }.sort_by { |h| [-h['n'], h['name']] }
          site.pages << SgHubPage.new(site, do_short, sg, GongsiGenerator.agg_row(sg, ds), dong_rows, by_sg[[do_short, sg]] || [], year)
          counts[:sg] += 1
          ds.each do |d|
            list = by_dong[[do_short, sg, d['dong']]]
            next if list.nil? || list.empty?
            site.pages << DongHubPage.new(site, do_short, sg, d['dong'], d, list, dong_rows, year)
            counts[:dong] += 1
          end
        end
      end

      # 랭킹
      pool = recs.select { |r| r['url'] && r['n'] >= RANK_MIN_UNITS }
      kinds = {
        'top' => ['평균 공시가격이 높은 단지', ->(l) { l.sort_by { |r| -r['avg'] } }],
        'rise' => ['공시가격 상승률이 높은 단지', ->(l) { l.select { |r| r['yoy'] }.sort_by { |r| -r['yoy'] } }],
        'h12' => ['공시가격 12억 원 이상 세대가 많은 단지', ->(l) { l.select { |r| r['h'][2].positive? }.sort_by { |r| -r['h'][2] } }],
        'h9' => ['공시가격 9억 원 이상 세대가 많은 단지', ->(l) { l.select { |r| r['h'][1].positive? }.sort_by { |r| -r['h'][1] } }]
      }
      kinds.each do |k, (title, fn)|
        site.pages << RankPage.new(site, k, title, nil, fn.call(pool).first(200), year)
        counts[:rank] += 1
        by_do.each_key do |d|
          rows = fn.call(pool.select { |r| r['do'] == d }).first(100)
          next if rows.empty?
          site.pages << RankPage.new(site, k, title, d, rows, year)
          counts[:rank] += 1
        end
      end
      site.pages << RankIndexPage.new(site, kinds.map { |k, (t, _)| [k, t] }, by_do.keys.sort, year)

      all_n = dong_stats.sum { |d| d['n'] }
      all_s = dong_stats.sum { |d| d['s'] }
      ys = dong_stats.select { |d| d['yoy'] }
      nat_yoy = ys.empty? ? nil : (ys.sum { |d| d['yoy'] * d['n'] } / ys.sum { |d| d['n'] }).round(1)
      site.data['gongsi_stats'] = {
        'year' => year, 'prev' => meta['prev'], 'years_first' => meta['years'].first, 'units' => GText.fmt(all_n), 'complexes' => GText.fmt(meta['complexes']),
        'avg' => GText.won(all_s.to_f / all_n), 'yoy' => GText.pct(nat_yoy), 'pages' => GText.fmt(page_set.size),
        'do_rows' => do_names.map { |d| r = GongsiGenerator.agg_row(d, dong_stats.select { |x| x['do'] == d }); { 'name' => d, 'n' => r['n_fmt'], 'avg' => r['avg_fmt'], 'yoy' => r['yoy_fmt'] } },
        'top' => pool.sort_by { |r| -r['avg'] }.first(12).map { |r| GongsiGenerator.row(r) },
        'rise' => pool.select { |r| r['yoy'] }.sort_by { |r| -r['yoy'] }.first(8).map { |r| GongsiGenerator.row(r) }
      }

      idx = []
      by_dong.each_key { |d, s, g| idx << { 'n' => g, 't' => '동네', 'l' => "#{d} #{s}", 'u' => "/region/#{d}/#{s}/#{g}/" } }
      by_sg.each_key { |d, s| idx << { 'n' => s, 't' => '시군구', 'l' => d, 'u' => "/region/#{d}/#{s}/" } }
      page_set.first(SEARCH_MAX).each { |r| idx << { 'n' => r['name'], 't' => '단지', 'l' => "#{r['do']} #{r['sg']} #{r['dong']}", 'u' => r['url'] } }
      pg = PageWithoutAFile.new(site, site.source, '', 'search_index.json')
      pg.content = JSON.generate(idx)
      pg.data['layout'] = nil
      pg.data['sitemap'] = false
      site.pages << pg
      Jekyll.logger.info 'GongsiGenerator:', "단지 #{counts[:complex]} / 동 #{counts[:dong]} / 시군구 #{counts[:sg]} / 시도 #{counts[:do]} / 랭킹 #{counts[:rank] + 1} (레코드 #{recs.size})"
    end

    # 동 통계 묶음 → 요약 한 줄
    def self.agg_row(name, ds)
      n = ds.sum { |d| d['n'] }
      s = ds.sum { |d| d['s'] }
      n9 = ds.sum { |d| d['n9'] }
      w = ds.select { |d| d['yoy'] }
      yoy = w.empty? ? nil : (w.sum { |d| d['yoy'] * d['n'] } / w.sum { |d| d['n'] }).round(1)
      {
        'name' => name, 'n' => n, 'cx' => ds.sum { |d| d['cx'] }, 'avg' => n.positive? ? (s.to_f / n) : 0, 'n9' => n9, 'yoy' => yoy,
        'n_fmt' => GText.fmt(n), 'cx_fmt' => GText.fmt(ds.sum { |d| d['cx'] }), 'avg_fmt' => n.positive? ? GText.won(s.to_f / n) : '-', 'yoy_fmt' => GText.pct(yoy),
        'r9' => n.positive? ? format('%.1f%%', n9.to_f / n * 100) : '-'
      }
    end

    # 목록용 한 줄
    def self.row(r)
      {
        'name' => r['name'], 'url' => r['url'], 'loc' => "#{r['do']} #{r['sg']} #{r['dong']}", 'n' => GText.fmt(r['n']), 'avg' => GText.won(r['avg']),
        'yoy' => GText.pct(r['yoy']), 'yoyN' => r['yoy'], 'n9' => GText.fmt(r['h'][1]), 'n12' => GText.fmt(r['h'][2]), 'mx' => GText.won(r['mx'])
      }
    end
  end

  class GBasePage < Page
    def setup(site, dir, layout)
      @site = site
      @base = site.source
      @dir = dir
      @name = 'index.html'
      process(@name)
      read_yaml(File.join(@base, '_layouts'), "#{layout}.html")
      data['layout'] = layout
    end

    def seo(title, desc)
      data['title'] = title
      data['description'] = desc[0, 155]
    end

    def faq(pairs)
      data['faq'] = pairs.map { |q, a| { 'q' => q, 'a' => a } }
    end

    def f(n)
      GText.fmt(n)
    end
  end

  # ── 단지 상세 ───────────────────────────────────────
  class ComplexPage < GBasePage
    def initialize(site, r, neighbors, year, hak)
      setup(site, "g/#{GText.slug_of(r['name'], r['id'])}", 'complex')
      name = r['name']
      loc = "#{r['do']} #{r['sg']} #{r['dong']}"
      ta = r['ta']
      main = r['ar'].find { |x| x[0] == ta }
      data['cName'] = name
      data['doShort'] = r['do']
      data['sigungu'] = r['sg']
      data['dong'] = r['dong']
      data['road'] = r['road']
      data['lot'] = r['lot']
      data['year'] = year
      data['n'] = r['n']
      data['nd'] = r['nd']
      data['avg'] = GText.won(r['avg'])
      data['propTax'] = TaxLinks.property_tax(r['avg'])
      data['mx'] = GText.won(r['mx'])
      data['mn'] = GText.won(r['mn'])
      data['yoy'] = GText.pct(r['yoy'])
      data['yoyUp'] = r['yoy'] && r['yoy'] >= 0
      data['hasYoy'] = !r['yoy'].nil?
      data['ta'] = ta
      data['taPy'] = GText.py(ta)
      data['arRows'] = r['ar'].map do |a, n, mn, avg, mx, pavg, yoy|
        { 'a' => a, 'py' => GText.py(a), 'n' => f(n), 'mn' => GText.won(mn), 'avg' => GText.won(avg), 'mx' => GText.won(mx), 'pavg' => pavg.to_i.positive? ? GText.won(pavg) : '-', 'yoy' => GText.pct(yoy), 'up' => yoy && yoy >= 0 }
      end
      mx_tr = (r['tr'].map { |x| x[1] }.max || 1).to_f
      prev = nil
      data['trRows'] = r['tr'].map do |y, avg, n|
        chg = prev && prev.positive? ? ((avg.to_f / prev - 1) * 100).round(1) : nil
        prev = avg
        { 'y' => y, 'avg' => GText.won(avg), 'n' => n, 'chg' => GText.pct(chg), 'up' => chg && chg >= 0, 'w' => (avg / mx_tr * 100).round }
      end
      mx_ck = (r['ck'].map { |x| x[1] }.max || 1).to_f
      prev = nil
      data['ckRows'] = r['ck'].map do |y, avg, n|
        chg = prev && prev.positive? ? ((avg.to_f / prev - 1) * 100).round(1) : nil
        prev = avg
        { 'y' => y, 'avg' => GText.won(avg), 'n' => f(n), 'chg' => GText.pct(chg), 'up' => chg && chg >= 0, 'w' => (avg / mx_ck * 100).round }
      end
      data['hRows'] = [['6억 원 이상', r['h'][0]], ['9억 원 이상', r['h'][1]], ['12억 원 이상', r['h'][2]], ['15억 원 이상', r['h'][3]], ['30억 원 이상', r['h'][4]]].map do |label, c|
        { 'label' => label, 'n' => f(c), 'r' => format('%.1f%%', c.to_f / r['n'] * 100) }
      end
      data['rr'] = r['rr']
      data['tx'] = r['tx'] ? { 'avg' => GText.won(r['tx'][0] * 10_000), 'n' => r['tx'][1] } : nil
      if r['ap'].to_s.start_with?('apt:')
        data['aaptUrl'] = "https://wooaapt.wooahouse.com/apt/#{r['ap'].sub('apt:', '')}/"
      elsif r['ap'].to_s.start_with?('trade:')
        data['aaptUrl'] = "https://wooaapt.wooahouse.com/trade/#{r['ap'].sub('trade:', '')}/"
      end
      hs = hak[r['ap']]
      data['hakUrl'] = "https://wooahakgun.wooahouse.com/apt/#{hs}/" if hs
      data['neighbors'] = neighbors.map { |x| GongsiGenerator.row(x) }

      s = +"#{GText.eun_neun(name)} #{loc}에 있는 공동주택으로 #{f(r['n'])}세대#{r['nd'].to_i > 1 ? "(#{r['nd']}개 동 이상)" : ''} 규모입니다. "
      s << "#{year}년 1월 1일 기준 공시가격은 평균 #{GText.won(r['avg'])}이고, 가장 많은 전용 #{ta}㎡(약 #{GText.py(ta)}평형) #{f(main[1])}세대는 평균 #{GText.won(main[3])}(최저 #{GText.won(main[2])}, 최고 #{GText.won(main[4])})입니다. " if main
      s << "전년 대비 같은 면적대 기준 #{format('%.1f', r['yoy'].abs)}% #{r['yoy'] >= 0 ? '올랐습니다' : '내렸습니다'}. " if r['yoy']
      s << "공시가격 9억 원 이상 #{f(r['h'][1])}세대, 12억 원 이상 #{f(r['h'][2])}세대입니다. " if r['h'][1].positive?
      s << "대표 평형의 최근 12개월 실거래가 평균 #{data['tx']['avg']}(#{data['tx']['n']}건) 대비 공시가격 비율(현실화율)은 약 #{r['rr']}%입니다." if data['tx'] && r['rr'].positive?
      data['summary'] = s

      seo("#{name} 공시가격 #{year}·연도별 추이 | #{loc}", "#{loc} #{name} #{year}년 공시가격 평균 #{GText.won(r['avg'])}#{r['yoy'] ? ", 전년 대비 #{GText.pct(r['yoy'])}" : ''}. 전용면적별 최저·평균·최고와 #{r['tr'].first ? r['tr'].first[0] : year}~#{year}년 추이.")
      pairs = []
      pairs << ["#{name} 공시가격은 얼마인가요?", "#{year}년 1월 1일 기준 단지 평균 공시가격은 #{GText.won(r['avg'])}입니다. 면적과 층, 동·호에 따라 #{GText.won(r['mn'])}에서 #{GText.won(r['mx'])}까지 차이가 나며, 내 집의 정확한 공시가격은 부동산공시가격알리미에서 동·호수로 조회할 수 있습니다."]
      pairs << ["#{name} 공시가격은 전년보다 얼마나 올랐나요?", r['yoy'] ? "같은 전용면적 구간끼리 비교한 단지 평균 변동률은 #{GText.pct(r['yoy'])}입니다. 호별 변동률은 층·향·동에 따라 다를 수 있습니다." : '전년 자료와 같은 면적대로 비교할 수 있는 호가 충분하지 않아 변동률을 계산하지 못했습니다.']
      pairs << ['공시가격 이의신청은 어떻게 하나요?', '공시가격은 매년 3월 중순 공시 후 약 한 달간 열람·의견 제출 기간이 있습니다. 부동산공시가격알리미에서 의견을 제출할 수 있고, 공시 확정 후에는 이의신청 절차로 조정을 요청할 수 있습니다.']
      faq(pairs)
    end
  end

  # ── 지역 허브 ───────────────────────────────────────
  class DoHubPage < GBasePage
    def initialize(site, do_short, sg_rows, total, list, year)
      setup(site, "region/#{do_short}", 'do')
      data['doShort'] = do_short
      data['year'] = year
      data['total'] = total
      data['sgRows'] = sg_rows
      data['top'] = list.select { |r| r['url'] && r['n'] >= 100 }.sort_by { |r| -r['avg'] }.first(15).map { |r| GongsiGenerator.row(r) }
      data['rise'] = list.select { |r| r['url'] && r['n'] >= 100 && r['yoy'] }.sort_by { |r| -r['yoy'] }.first(10).map { |r| GongsiGenerator.row(r) }
      data['summary'] = "#{do_short}의 공동주택(아파트·연립·다세대) #{total['n_fmt']}세대, #{total['cx_fmt']}개 단지·건물의 #{year}년 1월 1일 기준 공시가격을 정리했습니다. 평균 공시가격은 #{total['avg_fmt']}이고 전년 대비 약 #{total['yoy_fmt']}, 공시가격 9억 원 이상 주택은 전체의 #{total['r9']}입니다. 시군구를 선택해 동네별 단지 공시가격과 변동률을 확인하세요."
      seo("#{do_short} 공동주택 공시가격 #{year} - 시군구별 평균·변동률", "#{do_short} 공시가격 #{year}: 평균 #{total['avg_fmt']}, 전년 대비 #{total['yoy_fmt']}. 시군구별 평균 공시가격과 9억 원 이상 비율, 상승률 높은 단지.")
    end
  end

  class SgHubPage < GBasePage
    def initialize(site, do_short, sg, total, dong_rows, list, year)
      setup(site, "region/#{do_short}/#{sg}", 'sigungu')
      data['doShort'] = do_short
      data['sigungu'] = sg
      data['year'] = year
      data['total'] = total
      data['dongRows'] = dong_rows
      data['top'] = list.select { |r| r['url'] }.sort_by { |r| -r['avg'] }.first(15).map { |r| GongsiGenerator.row(r) }
      data['summary'] = "#{do_short} #{sg}의 공동주택 #{total['n_fmt']}세대(#{total['cx_fmt']}개 단지·건물)의 #{year}년 공시가격입니다. 평균 #{total['avg_fmt']}, 전년 대비 약 #{total['yoy_fmt']}이며 공시가격 9억 원 이상 주택 비율은 #{total['r9']}입니다."
      seo("#{do_short} #{sg} 공시가격 #{year} - 동네별 평균·변동률", "#{do_short} #{sg} 공시가격 #{year}: 평균 #{total['avg_fmt']}, 전년 대비 #{total['yoy_fmt']}. 동네별 평균 공시가격과 단지 목록.")
      faq([["#{sg} 공시가격 평균은 얼마인가요?", "#{year}년 1월 1일 기준 #{sg} 공동주택(아파트·연립·다세대) 평균 공시가격은 #{total['avg_fmt']}입니다. 동네와 단지에 따라 크게 달라 아래 표에서 동네별로 확인하세요."],
           ["#{sg} 공시가격 9억 원 이상 주택은 얼마나 되나요?", "#{sg}에서 공시가격 9억 원 이상인 주택은 #{f(total['n9'])}세대로 전체의 #{total['r9']}입니다. 9억 원은 다주택자 종합부동산세 과세 기준 등에 쓰이는 구간이니 세금 계산 시 공식 자료를 확인하세요."]])
    end
  end

  class DongHubPage < GBasePage
    def initialize(site, do_short, sg, dong, d, list, dong_rows, year)
      setup(site, "region/#{do_short}/#{sg}/#{dong}", 'dong')
      total = GongsiGenerator.agg_row(dong, [d])
      data['doShort'] = do_short
      data['sigungu'] = sg
      data['dong'] = dong
      data['year'] = year
      data['total'] = total
      sorted = list.sort_by { |r| [-r['n'], r['name']] }
      data['rows'] = sorted.first(GongsiGenerator::DONG_ROWS).map { |r| GongsiGenerator.row(r) }
      data['listed'] = list.size
      data['others'] = [d['cx'] - list.size, 0].max
      data['neighbors'] = dong_rows.reject { |h| h['name'] == dong || !h['hub'] }.first(12)
      data['summary'] = "#{do_short} #{sg} #{dong}의 공동주택 #{total['n_fmt']}세대(#{total['cx_fmt']}개 단지·건물)의 #{year}년 1월 1일 기준 공시가격입니다. 평균 공시가격은 #{total['avg_fmt']}이고 전년 대비 약 #{total['yoy_fmt']}, 공시가격 9억 원 이상 주택은 #{total['r9']}입니다."
      seo("#{do_short} #{sg} #{dong} 아파트 공시가격 #{year} - 단지별 평균·변동률", "#{do_short} #{sg} #{dong} 공시가격 #{year}: 평균 #{total['avg_fmt']}, 전년 대비 #{total['yoy_fmt']}. 단지별 평균 공시가격과 9억 원 이상 세대수.")
      faq([["#{dong} 아파트 공시가격은 어떻게 확인하나요?", "아래 표에서 단지별 평균 공시가격과 전년 대비 변동률을 볼 수 있고, 단지 상세 페이지에서 전용면적별 최저·평균·최고와 연도별 추이를 확인할 수 있습니다. 호별 공시가격은 부동산공시가격알리미에서 조회하세요."],
           ['표에 없는 건물은 왜 그런가요?', "호수가 20세대 미만인 소규모 건물은 단지 표에서 제외했고 동 전체 통계(평균·변동률)에는 포함했습니다. 이 동네의 소규모 건물은 #{data['others']}곳입니다."]])
    end
  end

  # ── 랭킹 ────────────────────────────────────────────
  class RankPage < GBasePage
    def initialize(site, kind, title, do_short, rows, year)
      if do_short
        setup(site, "rank/#{kind}/#{do_short}", 'rank')
        scope = do_short
      else
        setup(site, "rank/#{kind}", 'rank')
        scope = '전국'
      end
      data['kind'] = kind
      data['scope'] = scope
      data['doShort'] = do_short
      data['rankTitle'] = title
      data['year'] = year
      data['rows'] = rows.each_with_index.map { |r, i| GongsiGenerator.row(r).merge('rank' => i + 1) }
      data['count'] = rows.size
      data['minUnits'] = GongsiGenerator::RANK_MIN_UNITS
      what = { 'top' => '평균 공시가격이 높은', 'rise' => '전년 대비 공시가격 상승률이 높은', 'h12' => '공시가격 12억 원 이상 세대가 많은', 'h9' => '공시가격 9억 원 이상 세대가 많은' }[kind]
      data['summary'] = "#{scope}에서 #{GongsiGenerator::RANK_MIN_UNITS}세대 이상 단지 중 #{year}년 1월 1일 기준 #{what} 단지 #{rows.size}곳을 순서대로 정리했습니다. 단지 평균은 호별 가격의 평균이라 면적·층에 따라 개별 주택과 차이가 큽니다."
      seo("#{scope} #{title} TOP #{rows.size} (#{year} 공시가격)", "#{scope} #{year}년 공시가격 기준 #{title} 순위. #{GongsiGenerator::RANK_MIN_UNITS}세대 이상 단지 대상, 평균 공시가격·전년 대비·고가 세대 수 포함.")
    end
  end

  class RankIndexPage < GBasePage
    def initialize(site, kinds, dos, year)
      setup(site, 'rank', 'rankindex')
      data['kinds'] = kinds.map { |k, t| { 'k' => k, 't' => t } }
      data['dos'] = dos
      data['year'] = year
      seo("공시가격 랭킹 #{year} - 평균 상위·상승률·12억 이상 단지", "#{year}년 공동주택 공시가격 랭킹. 평균 공시가격이 높은 단지, 상승률이 높은 단지, 공시가격 12억·9억 원 이상 세대가 많은 단지를 전국·시도별로 확인하세요.")
    end
  end

  # 사이트맵: 5만 건 한도 때문에 40,000건씩 분할 + 인덱스
  class GongsiSitemapGenerator < Generator
    safe true
    priority :lowest
    CHUNK = 40_000

    def generate(site)
      urls = site.pages.reject { |p| p.url.to_s.end_with?('.json', '.xml', '.txt', '.js', '.css') || p.url.to_s == '/404.html' || p.data['sitemap'] == false }.map { |p| p.url }.uniq
      base = site.config['url'].to_s
      chunks = urls.each_slice(CHUNK).to_a
      chunks.each_with_index do |c, idx|
        body = +"<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n"
        c.each { |u| body << "  <url><loc>#{base}#{u}</loc></url>\n" }
        body << "</urlset>\n"
        site.pages << raw_page(site, "sitemap-#{idx + 1}.xml", body)
      end
      index = +"<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<sitemapindex xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n"
      chunks.each_index { |idx| index << "  <sitemap><loc>#{base}/sitemap-#{idx + 1}.xml</loc></sitemap>\n" }
      index << "</sitemapindex>\n"
      site.pages << raw_page(site, 'sitemap.xml', index)
      Jekyll.logger.info 'GongsiSitemap:', "#{urls.size}개 URL → #{chunks.size}개 사이트맵"
    end

    private

    def raw_page(site, name, content)
      pg = PageWithoutAFile.new(site, site.source, '', name)
      pg.content = content
      pg.data['layout'] = nil
      pg.data['sitemap'] = false
      pg
    end
  end
end
