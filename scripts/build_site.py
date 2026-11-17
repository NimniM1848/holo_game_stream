#!/usr/bin/env python3
"""data/ の JSON から、静的なサイト一式（HTML/CSS/JS）を site/ に生成する。

使い方:
    python scripts/build_site.py                 # data/ を読んで site/ に出力
    python scripts/build_site.py --data DIR --out DIR

生成物は相対リンクだけなので、site/index.html をダブルクリックして開いても見られる。
公開するときは site/ の中身をそのままホスティング先に置く。

載せる動画は、判定が auto または confirmed のものだけ。
標準ライブラリだけで動く（追加のインストール不要）。

データ提供 / Data provided by Holodex: https://holodex.net
ライセンスへの言及と保証の免責は、リポジトリの NOTICE を参照
（https://docs.holodex.net/#section/LICENSE）。
"""
import argparse
import html
import json
import re
import shutil
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKER = ".generated-by-build_site"
PUBLISHED = ("auto", "confirmed")
JST = timezone(timedelta(hours=9))
SITE_TITLE = "ホロライブ　チラズアート配信まとめ"
RECENT_N = 10
DAILY_DAYS = 7  # タイムライン: 直近この日数は日ごと、それ以前は週ごと
WD = "月火水木金土日"

THEME_LIGHT = {
    "bg": "#f1f7fb", "card": "#ffffff", "bd": "#d2e3ee", "tx": "#1e2f3a",
    "mu": "#5b7485", "ac": "#1a6ea6", "ac2": "#dbedf9", "th": "#d6e6f1",
}
THEME_DARK = {
    "bg": "#0f1620", "card": "#172230", "bd": "#263646", "tx": "#e4ebf1",
    "mu": "#8fa3b3", "ac": "#6cb8e8", "ac2": "#1b3447", "th": "#223446",
}


def vars_css(t):
    return ";".join(f"--{k}:{v}" for k, v in t.items())


CSS = (
    ":root{" + vars_css(THEME_LIGHT) + "}\n"
    "@media (prefers-color-scheme: dark){:root:not([data-theme=\"light\"]){" + vars_css(THEME_DARK) + "}}\n"
    "[data-theme=\"dark\"]{" + vars_css(THEME_DARK) + "}\n"
    """
*{box-sizing:border-box}
[hidden]{display:none!important}
body{margin:0;background:var(--bg);color:var(--tx);font-family:system-ui,-apple-system,"Hiragino Sans","Noto Sans JP","Yu Gothic",sans-serif;line-height:1.7;font-size:15px}
a{color:var(--ac);text-decoration:none}
a:hover{text-decoration:underline}
a:focus-visible,button:focus-visible,select:focus-visible{outline:2px solid var(--ac);outline-offset:2px}
.wrap{max-width:1600px;margin:0 auto;padding:0 16px}
header{border-bottom:1px solid var(--bd);background:var(--card);position:sticky;top:0;z-index:20}
header .wrap{display:flex;align-items:center;gap:16px;min-height:52px;flex-wrap:wrap}
.brand{font-weight:600;font-size:16px;color:var(--tx)}
nav{display:flex;gap:14px;flex:1;font-size:14px}
.tbtn{width:34px;height:34px;border-radius:8px;border:1px solid var(--bd);background:var(--card);color:var(--tx);cursor:pointer;display:flex;align-items:center;justify-content:center}
.tbtn svg{width:18px;height:18px}
.ico-sun{display:none}
[data-theme="dark"] .ico-sun{display:block}
[data-theme="dark"] .ico-moon{display:none}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]) .ico-sun{display:block}:root:not([data-theme="light"]) .ico-moon{display:none}}
main{padding:20px 0 40px}
html{scroll-behavior:smooth}
h2[id]{scroll-margin-top:72px}
input[type=search]{font:inherit;font-size:14px;padding:6px 12px;border-radius:8px;border:1px solid var(--bd);background:var(--card);color:var(--tx);width:100%;max-width:360px}
h1{font-size:22px;margin:0 0 4px}
h2{font-size:16px;margin:28px 0 8px;font-weight:600}
.sub{color:var(--mu);font-size:13px;margin:0 0 12px}
.mu{color:var(--mu)}
.list{list-style:none;margin:0;padding:0}
.item{display:flex;gap:12px;align-items:center;padding:10px 0;border-top:1px solid var(--bd)}
.item:first-child{border-top:0}
.item img{width:192px;height:108px;object-fit:cover;border-radius:6px;background:var(--th);flex:none}
.item .t{font-size:14px;line-height:1.5;display:block;color:var(--tx)}
.item .m{font-size:12px;color:var(--mu);margin-top:2px}
.tag{font-size:11px;padding:1px 7px;border-radius:4px;background:var(--ac2);color:var(--ac);white-space:nowrap}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:10px}
.card{display:block;background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:12px 14px;color:var(--tx)}
.card:hover{text-decoration:none;border-color:var(--ac)}
.card .n{font-weight:600;font-size:15px}
.card .e{font-size:12px;color:var(--mu)}
.card .c{font-size:13px;color:var(--ac);margin-top:8px}
.card .z{font-size:13px;color:var(--mu);margin-top:8px}
.bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:8px 0 12px}
.chip,select{font:inherit;font-size:13px;padding:4px 10px;border-radius:999px;border:1px solid var(--bd);background:var(--card);color:var(--tx);cursor:pointer}
select{border-radius:8px;padding:5px 8px}
.chip[aria-pressed="true"]{background:var(--ac2);border-color:var(--ac);color:var(--ac)}
.wide{overflow:auto;border:1px solid var(--bd);border-radius:10px;background:var(--card);max-height:75vh}
table.mx{border-collapse:separate;border-spacing:0;font-size:13px}
.mx th,.mx td{padding:4px 6px;text-align:center;border-bottom:1px solid var(--bd);white-space:nowrap}
.mx thead th{position:sticky;top:0;background:var(--card);z-index:2;height:120px;vertical-align:bottom}
.mx thead th a{writing-mode:vertical-rl;display:inline-block}
.mx th.r,.mx td.r{position:sticky;left:0;background:var(--card);text-align:left;z-index:1;min-width:150px;max-width:190px;overflow:hidden;text-overflow:ellipsis}
.mx thead th.r{z-index:3}
.mx td.on{background:var(--ac2)}
.mx td.on a{font-weight:600}
.note{font-size:13px;color:var(--mu)}
.wide.tl{max-height:80vh}
table.tl{border-collapse:separate;border-spacing:0;font-size:12px}
.tl th,.tl td{border-bottom:1px solid var(--bd);border-right:1px solid var(--bd);padding:4px;vertical-align:top;min-width:156px;width:156px}
.tl thead th{position:sticky;top:0;z-index:2;background:var(--card);text-align:center;font-weight:500;line-height:1.3;vertical-align:bottom;height:48px}
.tl thead th .y{display:block;font-size:11px;color:var(--mu);min-height:14px}
.tl th.r,.tl td.r{position:sticky;left:0;z-index:1;background:var(--card);min-width:150px;width:150px;max-width:150px;text-align:left;vertical-align:middle;font-size:13px}
.tl thead th.r{z-index:3}
.tl .sep{border-left:2px solid var(--ac)}
.tl td.dly{background:var(--ac2)}
.tl .th{display:block;margin:0 0 4px}
.tl .th:last-child{margin-bottom:0}
.tl .th img{display:block;width:144px;height:81px;object-fit:cover;border-radius:4px;background:var(--th)}
.tl .th:hover img,.tl .th:focus-visible img{outline:2px solid var(--ac)}
footer{border-top:1px solid var(--bd);padding:16px 0 28px;font-size:12px;color:var(--mu)}
footer p{margin:2px 0}
.prose p{margin:0 0 10px}
.prose ul{margin:0 0 10px;padding-left:20px}
.list.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:16px 14px}
.list.grid .item{flex-direction:column;align-items:stretch;gap:6px;padding:0;border-top:0}
.list.grid .item img{width:100%;height:auto;aspect-ratio:16/9}
.tbtn#menu-toggle{display:none}
@media (max-width:640px){
header .wrap{gap:8px;min-height:48px;padding-top:6px;padding-bottom:6px}
.brand{flex:1;min-width:0;font-size:15px;line-height:1.3}
.js .tbtn#menu-toggle{display:flex}
.js nav{display:none;order:9;flex:none;width:100%;flex-direction:column;gap:0;border-top:1px solid var(--bd);margin-top:2px}
.js nav.open{display:flex}
.js nav a{padding:11px 4px;border-bottom:1px solid var(--bd);color:var(--tx);font-size:15px}
.js nav a:last-child{border-bottom:0}
nav{flex-wrap:wrap;gap:4px 14px;order:9;width:100%}
}
@media (max-width:520px){.item img{width:120px;height:68px}.list.grid .item img{width:100%;height:auto}}
@media (max-width:640px){
#tl-group,#f-region{gap:4px}
#tl-group .chip,#f-region .chip{font-size:12px;padding:2px 8px}
.wide:not(.tl){margin:0 -16px;border-radius:0;border-left:0;border-right:0;max-height:calc(100vh - 170px);max-height:calc(100dvh - 170px)}
.mx th,.mx td{padding:3px 4px}
.mx th.r,.mx td.r{min-width:76px;width:76px;max-width:76px;white-space:normal;word-break:break-all;font-size:11px;line-height:1.3;padding:3px 4px;overflow:visible;text-overflow:clip}
.mx thead th{height:96px}
.wide.tl{margin:0 -16px;border-radius:0;border-left:0;border-right:0;max-height:calc(100vh - 170px);max-height:calc(100dvh - 170px)}
.tl th,.tl td{padding:3px;min-width:112px;width:112px}
.tl th.r,.tl td.r{min-width:76px;width:76px;max-width:76px;font-size:11px;line-height:1.3;padding:3px 4px;word-break:break-all}
.tl .th img{width:104px;height:58px}
.tl thead th{height:42px;font-size:11px}
}
"""
)

THEME_BOOT = (
    "<script>try{var t=localStorage.getItem('theme');"
    "if(t==='dark'||t==='light')document.documentElement.setAttribute('data-theme',t)}catch(e){}"
    "document.documentElement.className+=' js'</script>"
)

JS = r"""
(function(){
  var d=document;
  var mb=d.getElementById('menu-toggle'),nv=d.getElementById('site-nav');
  if(mb&&nv){
    var setMenu=function(o){nv.classList.toggle('open',o);mb.setAttribute('aria-expanded',o?'true':'false');mb.setAttribute('aria-label',o?'メニューを閉じる':'メニューを開く');};
    mb.addEventListener('click',function(){setMenu(!nv.classList.contains('open'));});
    nv.addEventListener('click',function(e){if(e.target.closest('a'))setMenu(false);});
    d.addEventListener('keydown',function(e){if(e.key==='Escape')setMenu(false);});
  }
  var btn=d.getElementById('theme-toggle');
  if(btn){btn.addEventListener('click',function(){
    var cur=d.documentElement.getAttribute('data-theme');
    if(!cur){cur=(window.matchMedia&&matchMedia('(prefers-color-scheme: dark)').matches)?'dark':'light';}
    var next=cur==='dark'?'light':'dark';
    d.documentElement.setAttribute('data-theme',next);
    try{localStorage.setItem('theme',next)}catch(e){}
  });}

  function press(group,btnEl){
    Array.prototype.forEach.call(group.querySelectorAll('.chip'),function(b){b.setAttribute('aria-pressed',b===btnEl?'true':'false');});
  }

  var cards=d.getElementById('cards');
  var sortBar=d.getElementById('sort-bar');
  if(cards&&sortBar){
    sortBar.addEventListener('click',function(e){
      var b=e.target.closest('.chip');if(!b)return;
      press(sortBar,b);
      var key=b.getAttribute('data-sort');
      var arr=Array.prototype.slice.call(cards.children);
      arr.sort(function(x,y){
        var a=Number(x.getAttribute('data-'+key)),c=Number(y.getAttribute('data-'+key));
        return key==='order'?a-c:c-a;
      });
      arr.forEach(function(n){cards.appendChild(n);});
    });
  }

  var q=d.getElementById('game-q');
  if(cards&&q){
    var norm=function(s){
      return (s||'').normalize('NFKC').toLowerCase().replace(/\s+/g,'').replace(/[\u30a1-\u30f6]/g,function(c){return String.fromCharCode(c.charCodeAt(0)-96);});
    };
    var near=function(text,k,max){
      var m=k.length,prev=[],cur=[],i,j;
      for(i=0;i<=m;i++)prev[i]=i;
      for(j=1;j<=text.length;j++){
        cur[0]=0;
        for(i=1;i<=m;i++)cur[i]=Math.min(prev[i]+1,cur[i-1]+1,prev[i-1]+(k.charAt(i-1)===text.charAt(j-1)?0:1));
        if(cur[m]<=max)return true;
        prev=cur.slice();
      }
      return false;
    };
    q.addEventListener('input',function(){
      var k=norm(q.value),n=0,all=cards.children.length;
      var max=k.length>=5?2:(k.length>=3?1:0);
      Array.prototype.forEach.call(cards.children,function(c){
        var t=norm(c.getAttribute('data-q'));
        var hit=!k||t.indexOf(k)>=0||(max>0&&near(t,k,max));
        c.hidden=!hit;if(hit)n++;
      });
      var o=d.getElementById('game-q-n');if(o)o.textContent=k?(n+' / '+all+' 作品'):'';
    });
  }

  var list=d.getElementById('vlist');
  if(list){
    var selT=d.getElementById('f-talent'),selS=d.getElementById('f-sort'),
        regBar=d.getElementById('f-region'),cnt=d.getElementById('f-count');
    var region='all';
    function apply(){
      var items=Array.prototype.slice.call(list.children);
      var asc=selS.value==='old';
      items.sort(function(x,y){
        var a=Number(x.getAttribute('data-ts')),c=Number(y.getAttribute('data-ts'));
        return asc?a-c:c-a;
      });
      var n=0;
      items.forEach(function(it){
        var ok=(selT.value==='all'||it.getAttribute('data-talent')===selT.value)&&
               (region==='all'||it.getAttribute('data-group')===region);
        it.hidden=!ok;if(ok)n++;
        list.appendChild(it);
      });
      cnt.textContent=n+'件を表示';
    }
    selT.addEventListener('change',apply);
    selS.addEventListener('change',apply);
    regBar.addEventListener('click',function(e){
      var b=e.target.closest('.chip');if(!b)return;
      press(regBar,b);region=b.getAttribute('data-group');apply();
    });
    apply();
  }

  var tl=d.getElementById('tl-body');
  if(tl){
    var tg=d.getElementById('tl-group'),ts=d.getElementById('tl-game'),tc=d.getElementById('tl-count');
    var grp='all';
    function tlApply(){
      var g=ts.value,rows=0,vs=0;
      Array.prototype.forEach.call(tl.rows,function(row){
        var okG=(grp==='all'||row.getAttribute('data-group')===grp),n=0;
        Array.prototype.forEach.call(row.querySelectorAll('.th'),function(a){
          var ok=(g==='all')||((' '+a.getAttribute('data-games')+' ').indexOf(' '+g+' ')>=0);
          a.hidden=!ok;if(ok)n++;
        });
        var show=okG&&(g==='all'||n>0);
        row.hidden=!show;if(show){rows++;vs+=n;}
      });
      tc.textContent=rows+'人 ・ '+vs+'件';
    }
    ts.addEventListener('change',tlApply);
    tg.addEventListener('click',function(e){
      var b=e.target.closest('.chip');if(!b)return;
      press(tg,b);grp=b.getAttribute('data-group');tlApply();
    });
    tlApply();
  }

  var mx=d.getElementById('mx-body'),mxBar=d.getElementById('mx-region');
  if(mx&&mxBar){
    mxBar.addEventListener('click',function(e){
      var b=e.target.closest('.chip');if(!b)return;
      press(mxBar,b);
      var r=b.getAttribute('data-group');
      Array.prototype.forEach.call(mx.rows,function(row){
        row.hidden=!(r==='all'||row.getAttribute('data-group')===r);
      });
    });
  }
})();
"""

ICON_MOON = ('<svg class="ico-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
             'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>')
ICON_SUN = ('<svg class="ico-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/>'
            '<path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>')

# 絞り込みボタンの並び。(id, 表示名, Holodexのgroupの先頭一致・小文字)
GROUPS = [
    ("g0", "0期生", "0th generation"),
    ("g1", "1期生", "1st generation"),
    ("g2", "2期生", "2nd generation"),
    ("gamers", "ゲーマーズ", "gamers"),
    ("g3", "3期生", "3rd generation"),
    ("g4", "4期生", "4th generation"),
    ("g5", "5期生", "5th generation"),
    ("holox", "holoX", "6th generation"),
    ("regloss", "ReGLOSS", "dev_is regloss"),
    ("flowglow", "FLOW GLOW", "dev_is flow glow"),
    ("asobi", "アソビ★まわり隊!", "asobi"),
    ("en", "EN", "english"),
    ("id", "ID", "indonesia"),
    ("mekpark", "mekPark", "mekpark"),
]
GROUP_LABEL = {gid: label for gid, label, _ in GROUPS}
GROUP_ORDER = {gid: i for i, (gid, _, _) in enumerate(GROUPS)}


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def group_of(info):
    """チャンネルの group からボタン用のグループidを返す。対象外(Misc/Official/holo-n/CN/Holostars/不明)は None。"""
    if not info:
        return None
    g = (info.get("group") or "").lower()
    for gid, _, prefix in GROUPS:
        if g.startswith(prefix):
            return gid
    return None


def display_name(name, ja):
    """日本語名の対応表にあれば日本語名、無ければ英語表記のまま。"""
    if name in ja:
        return ja[name]
    m = re.match(r"^(.*) \(Sub\)$", name)
    if m and m.group(1) in ja:
        return ja[m.group(1)] + "（サブ）"
    return name


def parse_dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def jst_date(dt) -> str:
    return dt.astimezone(JST).strftime("%Y-%m-%d") if dt else "日付不明"


def page(title, body, root, desc=""):
    d = f'<meta name="description" content="{esc(desc)}">' if desc else ""
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
{d}
{THEME_BOOT}
<link rel="stylesheet" href="{root}assets/style.css">
</head>
<body>
<header><div class="wrap">
<a class="brand" href="{root}index.html">{esc(SITE_TITLE)}</a>
<nav id="site-nav"><a href="{root}index.html#works">作品</a><a href="{root}timeline/index.html">タイムライン</a><a href="{root}matrix/index.html">タレント×作品</a><a href="{root}about/index.html">このサイトについて</a></nav>
<button id="theme-toggle" class="tbtn" type="button" aria-label="表示の明るさを切り替える" title="明るさを切り替える">{ICON_MOON}{ICON_SUN}</button>
<button id="menu-toggle" class="tbtn" type="button" aria-label="メニューを開く" aria-expanded="false" aria-controls="site-nav"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 6h16M4 12h16M4 18h16"/></svg></button>
</div></header>
<main><div class="wrap">
{body}
</div></main>
<footer><div class="wrap">
<p>非公式のファンサイトです。ホロライブプロダクション、カバー株式会社、Chilla's Art とは関係ありません。</p>
<p>データ提供: <a href="https://holodex.net" rel="noopener">Holodex</a> ・ 動画はすべて YouTube 上のものです。</p>
<p>最終更新: {{UPDATED}}</p>
</div></footer>
<script src="{root}assets/app.js"></script>
</body>
</html>
"""


def video_row(v, root, show_game=None, games_by_id=None, show_talent=True):
    thumb = f"https://i.ytimg.com/vi/{esc(v['id'])}/mqdefault.jpg"
    url = f"https://www.youtube.com/watch?v={esc(v['id'])}"
    meta = []
    if show_talent:
        meta.append(f'<a href="{root}talents/{esc(v["channel_id"])}/index.html">{esc(v["channel_name"])}</a>')
    meta.append(esc(v["date"]))
    tags = ""
    if show_game and games_by_id:
        for gid in v["games"]:
            g = games_by_id[gid]
            tags += f' <a class="tag" href="{root}games/{esc(gid)}/index.html">{esc(g["ja"])}</a>'
    return (
        f'<li class="item" data-ts="{v["ts"]}" data-talent="{esc(v["channel_id"])}" data-group="{v["group"]}">'
        f'<a href="{url}" target="_blank" rel="noopener"><img src="{thumb}" alt="" loading="lazy" width="192" height="108"></a>'
        f'<div><a class="t" href="{url}" target="_blank" rel="noopener">{esc(v["title"])}</a>'
        f'<div class="m">{" ・ ".join(meta)}{tags}</div></div></li>'
    )


def load(data_dir: Path):
    games = json.loads((data_dir / "games.json").read_text(encoding="utf-8"))["games"]
    raw = json.loads((data_dir / "videos.json").read_text(encoding="utf-8"))["videos"]
    ch_path = data_dir / "channels.json"
    chmap = json.loads(ch_path.read_text(encoding="utf-8"))["channels"] if ch_path.exists() else {}
    nm_path = data_dir / "names_ja.json"
    ja = json.loads(nm_path.read_text(encoding="utf-8"))["names"] if nm_path.exists() else {}
    games = list(reversed(games))  # games.json は古い順。サイト内では最新作が先頭になるよう逆順にする
    return games, raw, chmap, ja


def collect_published(games, raw, chmap, ja):
    ids = {g["id"] for g in games}
    out = []
    for vid, r in raw.items():
        gl = [gid for gid, st in r["games"].items() if st in PUBLISHED and gid in ids]
        if not gl:
            continue
        dt = parse_dt(r.get("available_at"))
        cid = r.get("channel_id") or "unknown"
        grp = group_of(chmap.get(cid))
        if grp is None:  # Misc / Official / CN / Holostars / 不明 は載せない
            continue
        out.append({
            "id": vid,
            "title": r.get("title") or "",
            "channel_id": cid,
            "channel_name": display_name(r.get("channel_name") or "不明", ja),
            "group": grp,
            "date": jst_date(dt),
            "day": dt.astimezone(JST).date() if dt else None,
            "ts": int(dt.timestamp()) if dt else 0,
            "games": [g["id"] for g in games if g["id"] in gl],  # games.json の並び順
        })
    out.sort(key=lambda v: v["ts"], reverse=True)
    return out


def build(data_dir: Path, out_dir: Path):
    games, raw, chmap, ja = load(data_dir)
    games_by_id = {g["id"]: g for g in games}
    vids = collect_published(games, raw, chmap, ja)

    by_game = {g["id"]: [] for g in games}
    for v in vids:
        for gid in v["games"]:
            by_game[gid].append(v)

    talents = {}
    for v in vids:
        t = talents.setdefault(v["channel_id"], {"id": v["channel_id"], "name": v["channel_name"],
                                                  "group": v["group"], "by_game": {}, "vids": []})
        t["vids"].append(v)
        for gid in v["games"]:
            t["by_game"].setdefault(gid, []).append(v)

    if out_dir.exists():
        if not (out_dir / MARKER).exists():
            sys.exit(f"{out_dir} は既に存在し、このスクリプトが作ったものではありません。別の出力先を指定してください。")
        shutil.rmtree(out_dir)
    (out_dir / "assets").mkdir(parents=True)
    (out_dir / MARKER).write_text("このフォルダは build_site.py が生成しました。手で編集しても、次の生成で消えます。\n", encoding="utf-8")
    (out_dir / "assets" / "style.css").write_text(CSS, encoding="utf-8")
    (out_dir / "assets" / "app.js").write_text(JS, encoding="utf-8")

    updated = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    pages = {}

    # ---- トップ ----
    recent = "".join(video_row(v, "", show_game=True, games_by_id=games_by_id) for v in vids[:RECENT_N])
    cards = []
    for i, g in enumerate(games):  # load() で最新作が先頭の順にしてある
        vs = by_game[g["id"]]
        latest = vs[0] if vs else None
        if vs:
            stat = f'<div class="c">{len(vs)}件 ・ 最新 {esc(latest["date"])}</div>'
        else:
            stat = '<div class="z">配信が見つかっていません</div>'
        cards.append(
            f'<a class="card" href="games/{esc(g["id"])}/index.html" data-order="{i}" data-q="{esc(g["ja"] + " " + g["en"] + " " + " ".join(g.get("keywords", [])))}" '
            f'data-count="{len(vs)}" data-latest="{latest["ts"] if latest else 0}">'
            f'<div class="n">{esc(g["ja"])}</div><div class="e">{esc(g["en"])}</div>{stat}</a>'
        )
    body = (
        f"<h1>{esc(SITE_TITLE)}</h1>"
        '<p class="sub">ホロライブのタレントがYouTubeでライブ配信した、Chilla\'s Art の作品をまとめています。</p>'
        f"<h2>最近の配信</h2><ul class=\"list grid\">{recent or '<li class=\"mu\">まだ配信が登録されていません。</li>'}</ul>"
        "<h2 id=\"works\">作品</h2>"
        '<div class="bar"><input id="game-q" type="search" placeholder="作品名で検索" aria-label="作品名で検索" autocomplete="off"><span id="game-q-n" class="note"></span></div>'
        '<div id="sort-bar" class="bar"><span class="note">並べ替え:</span>'
        '<button class="chip" type="button" data-sort="order" aria-pressed="true">発売順（新しい順）</button>'
        '<button class="chip" type="button" data-sort="count" aria-pressed="false">配信数順</button>'
        '<button class="chip" type="button" data-sort="latest" aria-pressed="false">最新配信順</button></div>'
        f'<div id="cards" class="cards">{"".join(cards)}</div>'
        '<p class="note" style="margin-top:16px"><a href="timeline/index.html">いつ誰が配信したか(タイムライン) →</a> ・ <a href="matrix/index.html">タレント×作品の一覧表 →</a></p>'
    )
    pages["index.html"] = page(SITE_TITLE, body, "", "ホロライブのタレントがYouTubeで配信した Chilla's Art の作品の配信まとめ")

    # ---- 作品ページ ----
    for g in games:
        vs = by_game[g["id"]]
        steam = ""
        if g.get("steam_app_id"):
            steam = (f' ・ <a href="https://store.steampowered.com/app/{int(g["steam_app_id"])}/" '
                     'target="_blank" rel="noopener">Steamのページ</a>')
        head = (f'<p class="sub"><a href="../../index.html">作品一覧</a> › </p>'
                f'<h1>{esc(g["ja"])}</h1><p class="sub">{esc(g["en"])} ・ {len(vs)}件{steam}</p>')
        if not vs:
            body = head + '<p class="mu">配信が見つかっていません。</p>'
        else:
            tal = {}
            for v in vs:
                tal.setdefault(v["channel_id"], [v["channel_name"], 0])[1] += 1
            opts = '<option value="all">全員</option>' + "".join(
                f'<option value="{esc(cid)}">{esc(n)}（{c}）</option>'
                for cid, (n, c) in sorted(tal.items(), key=lambda kv: kv[1][0].lower()))
            regs = sorted({v["group"] for v in vs}, key=GROUP_ORDER.get)
            chips = '<button class="chip" type="button" data-group="all" aria-pressed="true">すべて</button>' + "".join(
                f'<button class="chip" type="button" data-group="{r}" aria-pressed="false">{GROUP_LABEL[r]}</button>' for r in regs)
            body = (
                head +
                '<div class="bar"><label class="note" for="f-talent">タレント</label>'
                f'<select id="f-talent">{opts}</select>'
                '<label class="note" for="f-sort">並び順</label>'
                '<select id="f-sort"><option value="new">新しい順</option><option value="old">古い順</option></select></div>'
                f'<div id="f-region" class="bar"><span class="note">グループ:</span>{chips}</div>'
                '<p id="f-count" class="note"></p>'
                f'<ul id="vlist" class="list">{"".join(video_row(v, "../../") for v in vs)}</ul>'
            )
        pages[f"games/{g['id']}/index.html"] = page(f"{g['ja']} - {SITE_TITLE}", body, "../../",
                                                    f"{g['ja']}（{g['en']}）を配信したホロライブのタレントの一覧")

    # ---- タレントページ ----
    for t in talents.values():
        secs = ""
        total = 0
        for g in games:
            vs = t["by_game"].get(g["id"])
            if not vs:
                continue
            total += len(vs)
            secs += (f'<h2 id="{esc(g["id"])}"><a href="../../games/{esc(g["id"])}/index.html">{esc(g["ja"])}</a> '
                     f'<span class="mu">（{len(vs)}件）</span></h2><ul class="list">'
                     + "".join(video_row(v, "../../", show_talent=False) for v in vs) + "</ul>")
        body = (f'<p class="sub"><a href="../../matrix/index.html">タレント×作品</a> › </p>'
                f'<h1>{esc(t["name"])}</h1><p class="sub">{GROUP_LABEL[t["group"]]} ・ 合計 {total}件</p>{secs}')
        pages[f"talents/{t['id']}/index.html"] = page(f"{t['name']} - {SITE_TITLE}", body, "../../")

    # ---- タイムライン ----
    today = datetime.now(JST).date()
    dated = [v for v in vids if v["day"]]
    undated = len(vids) - len(dated)
    cols = []  # {"y","label","kind"}
    for i in range(DAILY_DAYS):
        dd = today - timedelta(days=i)
        cols.append({"y": dd.year, "label": f"{dd.month}/{dd.day}({WD[dd.weekday()]})", "kind": "dly"})

    def monday(dd):
        return dd - timedelta(days=dd.weekday())

    weekly_new = monday(today - timedelta(days=DAILY_DAYS))
    older = [v for v in dated if v["day"] <= today - timedelta(days=DAILY_DAYS)]
    if older:
        weekly_old = monday(min(v["day"] for v in older))
        nweeks = (weekly_new - weekly_old).days // 7 + 1
        for k in range(nweeks):
            mm = weekly_new - timedelta(days=7 * k)
            cols.append({"y": mm.year, "label": f"{mm.month}/{mm.day}〜", "kind": "wk"})

    def col_index(day):
        if day >= today - timedelta(days=DAILY_DAYS - 1):
            return max(0, (today - day).days)
        return DAILY_DAYS + (weekly_new - monday(day)).days // 7

    heads = ""
    for i, c in enumerate(cols):
        ytxt = f'{c["y"]}年'  # 横スクロール中も年が分かるよう、全ての列に表示する
        cls = ' class="sep"' if i == DAILY_DAYS else ""
        heads += f'<th{cls}><span class="y">{ytxt}</span>{esc(c["label"])}</th>'
    trows = ""
    tl_order = sorted((t for t in talents.values() if any(v["day"] for v in t["vids"])),
                      key=lambda t: (GROUP_ORDER[t["group"]], -len(t["vids"]), t["name"]))
    for t in tl_order:
        cells = [[] for _ in cols]
        for v in t["vids"]:  # vids は新しい順
            if v["day"]:
                cells[col_index(v["day"])].append(v)
        tds = ""
        for i, cl in enumerate(cells):
            cls = ["dly"] if cols[i]["kind"] == "dly" else []
            if i == DAILY_DAYS:
                cls.append("sep")
            inner = ""
            for v in cl:
                gnames = "・".join(games_by_id[gid]["ja"] for gid in v["games"])
                tip = f'{v["date"]} {gnames} {v["title"]}'
                inner += (f'<a class="th" href="https://www.youtube.com/watch?v={esc(v["id"])}" target="_blank" rel="noopener" '
                          f'data-games="{esc(" ".join(v["games"]))}" title="{esc(tip)}">'
                          f'<img src="https://i.ytimg.com/vi/{esc(v["id"])}/mqdefault.jpg" alt="{esc(tip)}" loading="lazy" width="144" height="81"></a>')
            tds += f'<td class="{" ".join(cls)}">{inner}</td>'
        trows += (f'<tr data-group="{t["group"]}"><td class="r"><a href="../talents/{esc(t["id"])}/index.html">{esc(t["name"])}</a>'
                  f'<div class="note">{esc(GROUP_LABEL[t["group"]])}</div></td>{tds}</tr>')
    tregs = sorted({t["group"] for t in tl_order}, key=GROUP_ORDER.get)
    tchips = '<button class="chip" type="button" data-group="all" aria-pressed="true">すべて</button>' + "".join(
        f'<button class="chip" type="button" data-group="{r}" aria-pressed="false">{GROUP_LABEL[r]}</button>' for r in tregs)
    gopts = '<option value="all">すべての作品</option>' + "".join(
        f'<option value="{esc(g["id"])}">{esc(g["ja"])}</option>' for g in games if by_game[g["id"]])
    if tl_order:
        body = (
            "<h1>タイムライン</h1>"
            f'<p class="sub">いつ誰が配信したかの一覧です。左が新しく、右へスクロールすると過去に遡ります。直近{DAILY_DAYS}日は日ごと(色付き)、それ以前は週ごと(月曜始まり)です。サムネイルを押すとYouTubeが開きます。</p>'
            f'<div id="tl-group" class="bar"><span class="note">グループ:</span>{tchips}</div>'
            f'<div class="bar"><label class="note" for="tl-game">作品</label><select id="tl-game">{gopts}</select>'
            '<span id="tl-count" class="note"></span></div>'
            f'<div class="wide tl"><table class="tl"><thead><tr><th class="r">タレント</th>{heads}</tr></thead>'
            f'<tbody id="tl-body">{trows}</tbody></table></div>'
        )
    else:
        body = '<h1>タイムライン</h1><p class="mu">まだ配信が登録されていません。</p>'
    pages["timeline/index.html"] = page(f"タイムライン - {SITE_TITLE}", body, "../")

    # ---- 一覧表 ----
    order = sorted(talents.values(), key=lambda t: (GROUP_ORDER[t["group"]], -sum(len(x) for x in t["by_game"].values()), t["name"].lower()))  # グループ順（タイムラインと同じ）、同グループ内は配信数の多い順
    head_cells = "".join(
        f'<th title="{esc(g["en"])}"><a href="../games/{esc(g["id"])}/index.html">{esc(g["ja"])}</a></th>' for g in games)
    rows = ""
    for t in order:
        cells = ""
        for g in games:
            n = len(t["by_game"].get(g["id"], []))
            cells += (f'<td class="on"><a href="../talents/{esc(t["id"])}/index.html#{esc(g["id"])}">{n}</a></td>'
                      if n else "<td></td>")
        rows += f'<tr data-group="{t["group"]}"><td class="r"><a href="../talents/{esc(t["id"])}/index.html">{esc(t["name"])}</a></td>{cells}</tr>'
    regs = sorted({t["group"] for t in order}, key=GROUP_ORDER.get)
    chips = '<button class="chip" type="button" data-group="all" aria-pressed="true">すべて</button>' + "".join(
        f'<button class="chip" type="button" data-group="{r}" aria-pressed="false">{GROUP_LABEL[r]}</button>' for r in regs)
    body = (
        "<h1>タレント×作品</h1>"
        '<p class="sub">誰がどの作品を配信したか。数字は配信数で、クリックすると配信の一覧に移ります。配信数の多いタレントが上です。</p>'
        f'<div id="mx-region" class="bar"><span class="note">グループ:</span>{chips}</div>'
        '<div class="wide"><table class="mx"><thead><tr><th class="r">タレント</th>'
        f'{head_cells}</tr></thead><tbody id="mx-body">{rows}</tbody></table></div>'
        if order else "<h1>タレント×作品</h1><p class=\"mu\">まだ配信が登録されていません。</p>"
    )
    pages["matrix/index.html"] = page(f"タレント×作品 - {SITE_TITLE}", body, "../")

    # ---- このサイトについて ----
    body = """<h1>このサイトについて</h1>
<div class="prose">
<h2>どんなサイトか</h2>
<p>ホロライブのタレントが、YouTube でライブ配信した Chilla's Art の作品を、作品ごと・タレントごとにまとめた非公式のファンサイトです。動画そのものは掲載せず、YouTube へのリンクとタイトルなどの情報だけを載せています。</p>
<h2>集めている範囲</h2>
<ul>
<li>ホロライブ（JP・EN・ID）のタレントによるライブ配信です。</li>
<li>ホロスターズ、ショート動画、MV、切り抜きは対象外です。</li>
<li>配信のタイトルから作品を判定しているため、抜けや誤りがあるかもしれません。</li>
</ul>
<h2>出典</h2>
<p>配信の情報は <a href="https://holodex.net" rel="noopener">Holodex</a> の API を利用して集めています。Holodex の API の利用は、<a href="https://docs.holodex.net/#section/LICENSE" rel="noopener">Holodex API Documentation の LICENSE の項</a>に従います。</p>
<h2>プライバシー</h2>
<ul>
<li>このサイトは、アクセス解析や広告のツールを使っていません。</li>
<li>表示の明るさの設定（明るい／暗い）だけを、お使いのブラウザに保存します。</li>
<li>配信のサムネイル画像は YouTube から直接読み込まれます。そのため、ページを開くと、YouTube にアクセス情報が送られます。</li>
<li>動画のリンクを開くと、YouTube のサイトに移ります。</li>
</ul>
<h2>お問い合わせ・修正の依頼</h2>
<p>載せる配信の誤りや、掲載の停止の希望などは、サイト運営者の X アカウント <a href="https://x.com/Laniakea_bloom" target="_blank" rel="noopener">@Laniakea_bloom</a> までお知らせください。</p>
</div>"""
    pages["about/index.html"] = page(f"このサイトについて - {SITE_TITLE}", body, "../")

    for rel, content in pages.items():
        path = out_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content.replace("{UPDATED}", updated), encoding="utf-8")

    print(f"生成しました: {out_dir}")
    print(f"  公開する動画: {len(vids)} 件 / 作品: {len(games)} / タレント: {len(talents)} / ページ: {len(pages)}")
    unmapped = sorted({t["name"] for t in talents.values()
                       if t["group"] not in ("en", "id") and not re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", t["name"])})
    if unmapped:
        print("  日本語名が未登録のチャンネル(英語のまま表示):", "、".join(unmapped))
    if undated:
        print(f"  配信日が不明でタイムラインに載らない動画: {undated}件")
    empty = [g["ja"] for g in games if not by_game[g["id"]]]
    if empty:
        print("  配信が0件の作品:", "、".join(empty))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=ROOT / "data")
    ap.add_argument("--out", type=Path, default=ROOT / "site")
    a = ap.parse_args()
    build(a.data, a.out)
