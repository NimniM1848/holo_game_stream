#!/usr/bin/env python3
"""ホロライブ（JP/EN/ID）のチラズアート作品のライブ配信を Holodex から集める。

使い方（APIキーは Holodex のアカウント設定で発行し、環境変数に入れる）:
    export HOLODEX_API_KEY=xxxxxxxx
    （または、プロジェクト直下の .env に「HOLODEX_API_KEY=xxxxxxxx」と1行書く。.env は .gitignore 済み）
    python scripts/collect.py channels        # 最初に1回: チャンネル一覧(所属情報)を取得して data/channels.json に保存
    python scripts/collect.py                 # 収集（結果を data/videos.json に保存）
    python scripts/collect.py --recent [日数]  # 日次更新用: 直近N日(既定 RECENT_DAYS 日)の新着だけを取って追加する
    python scripts/collect.py --show-raw      # 最初に取れた1件の生データも表示（項目名の確認用）
    python scripts/collect.py clean           # 保存済みの動画に、現在の除外条件と games.json の一致条件を適用し直す
    python scripts/collect.py stats           # 作品ごとの件数（auto / pending / confirmed / rejected）
    python scripts/collect.py pending [GAME]  # 確認待ちの一覧（GAME は games.json の id。省略で全作品）
    python scripts/collect.py set STATUS GAME VIDEO_ID [VIDEO_ID ...]   # 判定を付ける
    python scripts/collect.py reject-pending GAME   # その作品の確認待ちを全部 rejected にする

判定（STATUS）は「動画 × 作品」ごとに持つ:
    auto       検索で見つかった（要確認フラグなしの作品）。サイトに載せる
    pending    要確認フラグありの作品。確認するまでサイトに載せない
    confirmed  人が確定。サイトに載せる
    rejected   人が除外。サイトに載せない（再収集しても復活しない）

収集の条件（ライブ配信のみ）:
    - Holodex の種別が stream であること
    - 動画の長さが MIN_DURATION 秒以上（ショート・MVをほぼ除外）
    - タイトルに #shorts / MV / Instrumental / 切り抜き を含まない
    - ホロスターズ所属は除外（チャンネルの所属情報 または タイトルのタグ）

注意: Holodex API の仕様（エンドポイントとフィールド名）は記憶に基づく。
動かない場合は --show-raw の出力とエラー本文を確認すること。

データ提供 / Data provided by Holodex: https://holodex.net

ライセンスへの言及 / License notice:
    Holodex API の利用は、Holodex API Documentation の「LICENSE」の項に従う。
    Use of the Holodex API is governed by the license set out in the "LICENSE" section of
    the Holodex API Documentation: https://docs.holodex.net/#section/LICENSE

保証の免責 / Disclaimer of warranties:
    Holodex の API とそのコンテンツには、上記ライセンスの保証の免責条項が適用される。
    The disclaimer of warranties in the license above applies to the Holodex API and its
    content. See the license above and https://holodex.net .
    詳細はリポジトリの NOTICE も参照。
"""
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

API = "https://holodex.net/api/v2/search/videoSearch"
CHANNELS_API = "https://holodex.net/api/v2/channels"
ORG = ["Hololive"]  # JP / EN / ID（ホロスターズも含まれるので、後段で除外する）
PAGE = 50
MAX_PAGES = 20  # 1キーワードあたり最大 1000 件
SLEEP = 0.6
MIN_DURATION = 600  # 秒。これ未満はライブ配信とみなさない
RECENT_DAYS = 14  # --recent の既定。配信日と Holodex への反映の遅れを見込んで、毎日実行でも余裕を持たせる

EXCLUDE_TITLE = re.compile(
    r"#shorts|\bshorts\b|music\s*video|instrumental|切り抜き|\bmv\b|\bclips?\b", re.I
)
HOLOSTARS_TITLE = re.compile(
    r"holostars|ホロスターズ|ホロスタ|uproar|アップロー|holotempus", re.I
)
# チャンネルの suborg / group にこれらの語が含まれたらホロスターズ扱い（小文字で比較）
HOLOSTARS_WORDS = ("holostar", "tempus", "uproar")

DATA = Path(__file__).resolve().parent.parent / "data"
GAMES_PATH = DATA / "games.json"
VIDEOS_PATH = DATA / "videos.json"
CHANNELS_PATH = DATA / "channels.json"
STATUSES = ("auto", "pending", "confirmed", "rejected")


def load_dotenv():
    """プロジェクト直下の .env / apikey.env（KEY=VALUE の行）を読む。既に設定済みの環境変数は上書きしない。"""
    for name in (".env", "apikey.env"):
        path = DATA.parent / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip().removeprefix("export ").strip()
            v = v.strip().strip("\"'")
            if k and k not in os.environ:
                os.environ[k] = v


load_dotenv()


# ---------- 判定ロジック（通信なし） ----------

def norm(s: str) -> str:
    """全角半角・大小文字・空白の違いを無視して比較する。"""
    return "".join(unicodedata.normalize("NFKC", s).lower().split())


def match_games(title: str, games: list) -> list:
    """タイトルに作品名が含まれる作品の id を返す。ignore_if に当たるものは除く。"""
    t = norm(title)
    out = []
    for g in games:
        if not any(norm(k) in t for k in g["keywords"]):
            continue
        ignored = False
        for rule in g.get("ignore_if", []):
            if re.search(rule["pattern"], t) and not re.search(rule.get("unless", "(?!)"), t):
                ignored = True
                break
        if not ignored:
            out.append(g["id"])
    return out


def is_holostars(info) -> bool:
    """チャンネル情報（suborg / group を持つ dict）がホロスターズ所属かどうか。"""
    if not info:
        return False
    blob = f"{info.get('suborg') or ''} {info.get('group') or ''}".lower()
    return any(w in blob for w in HOLOSTARS_WORDS)


def reject_reason(title, typ, dur, channel_id, chmap, suborg_hint=None):
    """ライブ配信として扱わない動画なら理由を返す。扱うなら None。"""
    if typ and typ != "stream":
        return "種別が配信でない"
    if isinstance(dur, (int, float)) and 0 < dur < MIN_DURATION:
        return "短い動画(ショート/MV等)"
    title = title or ""
    if EXCLUDE_TITLE.search(title):
        return "タイトルがショート/MV/切り抜き"
    if (
        HOLOSTARS_TITLE.search(title)
        or is_holostars(chmap.get(channel_id))
        or is_holostars({"suborg": suborg_hint})
    ):
        return "ホロスターズ"
    return None


def since_dt(s: str) -> datetime:
    y, m = s.split("-")
    return datetime(int(y), int(m), 1, tzinfo=timezone.utc)


def parse_dt(s):
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# ---------- API ----------

def http(url: str, key: str, data=None):
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "X-APIKEY": key,
            "Content-Type": "application/json",
            # Cloudflare が Python 標準の User-Agent を弾く(error 1010)ため明示する
            "User-Agent": "chillas-art-game-archive/0.1 (personal fan site; non-commercial)",
        },
        method="POST" if data is not None else "GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode(errors='replace')[:500]}")


def post(body: dict, key: str):
    return http(API, key, data=json.dumps(body).encode())


def search_keyword(kw: str, since: datetime, key: str):
    """新しい順に取り、since より古い動画が出たら打ち切る。"""
    for page in range(MAX_PAGES):
        body = {
            "sort": "newest",
            "lang": ["all"],
            "target": ["stream"],
            "conditions": [{"text": kw}],
            "org": ORG,
            "paginated": True,
            "offset": page * PAGE,
            "limit": PAGE,
        }
        res = post(body, key)
        items = res.get("items", []) if isinstance(res, dict) else res
        if not items:
            return
        for it in items:
            dt = parse_dt(it.get("available_at") or it.get("published_at"))
            if dt and dt < since:
                return
            yield it
        time.sleep(SLEEP)


def fetch_channels(key: str) -> dict:
    """ホロライブ所属のチャンネル一覧を取得する。{channel_id: {name, suborg, group}}"""
    out = {}
    for page in range(30):
        qs = urllib.parse.urlencode(
            {"type": "vtuber", "org": ORG[0], "limit": 100, "offset": page * 100}
        )
        res = http(f"{CHANNELS_API}?{qs}", key)
        chans = res if isinstance(res, list) else res.get("items", [])
        if not chans:
            break
        for ch in chans:
            out[ch["id"]] = {
                "name": ch.get("english_name") or ch.get("name"),
                "suborg": ch.get("suborg"),
                "group": ch.get("group"),
                "inactive": ch.get("inactive"),
            }
        if len(chans) < 100:
            break
        time.sleep(SLEEP)
    return out


# ---------- データの読み書き ----------

def load_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def load_chmap() -> dict:
    if not CHANNELS_PATH.exists():
        sys.exit("data/channels.json がありません。先に `python scripts/collect.py channels` を実行してください。")
    return json.loads(CHANNELS_PATH.read_text(encoding="utf-8"))["channels"]


def load_videos() -> dict:
    videos = load_json(VIDEOS_PATH, {"videos": {}})["videos"]
    for v in videos.values():
        if not isinstance(v.get("games"), dict):
            sys.exit("videos.json が古い形式です。data/videos.json を削除して、収集し直してください。")
    return videos


def save_videos(videos: dict):
    ordered = dict(sorted(videos.items(), key=lambda kv: kv[1].get("available_at") or ""))
    tmp = VIDEOS_PATH.with_suffix(".tmp")
    tmp.write_text(
        json.dumps({"videos": ordered}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    tmp.replace(VIDEOS_PATH)


# ---------- コマンド ----------

def cmd_channels():
    key = os.environ.get("HOLODEX_API_KEY")
    if not key:
        sys.exit("環境変数 HOLODEX_API_KEY を設定してください。")
    chmap = fetch_channels(key)
    tmp = CHANNELS_PATH.with_suffix(".tmp")
    tmp.write_text(
        json.dumps({"channels": chmap}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    tmp.replace(CHANNELS_PATH)
    print(f"{len(chmap)} チャンネルを保存しました。\n")
    print("所属情報（suborg / group）ごとの件数と、チャンネル名の例:")
    groups = {}
    for info in chmap.values():
        groups.setdefault((info["suborg"], info["group"]), []).append(info["name"])
    for (suborg, group), names in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        flag = "  ← ホロスターズ扱い" if is_holostars({"suborg": suborg, "group": group}) else ""
        print(f"  suborg={suborg!r} group={group!r}: {len(names)}件 例: {', '.join(names[:3])}{flag}")


def collect(show_raw: bool, recent_days=None):
    key = os.environ.get("HOLODEX_API_KEY")
    if not key:
        sys.exit("環境変数 HOLODEX_API_KEY を設定してください。")
    chmap = load_chmap()
    games = load_json(GAMES_PATH, {})["games"]
    videos = load_videos()
    by_id = {g["id"]: g for g in games}
    new_videos = 0
    new_pending = Counter()
    dropped = Counter()
    raw_shown = False

    for g in games:
        since = since_dt(g["since"])
        if recent_days is not None:
            since = max(since, datetime.now(timezone.utc) - timedelta(days=recent_days))
        seen = set()
        for kw in g["keywords"]:
            for it in search_keyword(kw, since, key):
                if show_raw and not raw_shown:
                    print("--- 最初の1件（生データ） ---")
                    print(json.dumps(it, ensure_ascii=False, indent=1)[:1500])
                    print("---------------------------")
                    raw_shown = True
                vid = it["id"]
                if vid in seen:
                    continue
                seen.add(vid)
                matched = match_games(it.get("title", ""), games)
                if g["id"] not in matched:
                    continue  # 検索はあいまい一致なので、タイトルに実際に含まれるものだけ残す
                ch = it.get("channel") or {}
                reason = reject_reason(
                    it.get("title", ""), it.get("type"), it.get("duration"),
                    ch.get("id"), chmap, ch.get("suborg"),
                )
                if reason:
                    dropped[reason] += 1
                    continue
                rec = videos.get(vid)
                if rec is None:
                    rec = videos[vid] = {
                        "title": it.get("title", ""),
                        "channel_id": ch.get("id"),
                        "channel_name": ch.get("english_name") or ch.get("name"),
                        "type": it.get("type"),
                        "duration": it.get("duration"),
                        "available_at": it.get("available_at") or it.get("published_at"),
                        "games": {},
                    }
                    new_videos += 1
                rec["title"] = it.get("title", rec["title"])
                for m in matched:
                    if m not in rec["games"]:  # 既存の判定は上書きしない
                        rec["games"][m] = "pending" if by_id[m]["review_required"] else "auto"
                        if rec["games"][m] == "pending":
                            new_pending[m] += 1
        print(f"{g['ja']}: 完了")

    save_videos(videos)
    print(f"\n新規の動画 {new_videos} 件を追加。")
    if new_pending:
        print("確認待ち(pending)が増えました。`pending GAME` で確認し、`set` / `reject-pending` で判定してください:")
        for gid, n in new_pending.most_common():
            print(f"  {gid}: {n} 件")
    if dropped:
        print("除外した動画（理由別、重複を含む概数）:")
        for r, n in dropped.most_common():
            print(f"  {r}: {n}")
    print()
    stats()


def clean():
    """保存済みの動画に、現在の除外条件を適用し直す。confirmed は触らず、警告だけ出す。"""
    chmap = load_chmap()
    games = load_json(GAMES_PATH, {})["games"]
    videos = load_videos()
    removed = Counter()
    by_channel = Counter()
    kept_confirmed = []
    for vid, v in videos.items():
        title = v.get("title") or ""
        video_reason = reject_reason(
            title, v.get("type"), v.get("duration"), v.get("channel_id"), chmap
        )
        matched = set(match_games(title, games))  # games.json の現在の条件で照合し直す
        changed_reason = None
        for gid, st in v["games"].items():
            reason = video_reason or (None if gid in matched else "作品名の一致条件に合わない(ignore_if等)")
            if not reason:
                continue
            if st == "confirmed":
                kept_confirmed.append((vid, gid, v.get("channel_name"), reason))
            elif st != "rejected":
                v["games"][gid] = "rejected"
                removed[gid] += 1
                changed_reason = reason
        if changed_reason:
            by_channel[(v.get("channel_name"), changed_reason)] += 1
    save_videos(videos)
    print(f"除外条件を適用しました。rejected にした（動画×作品）: {sum(removed.values())} 件")
    for gid, n in removed.most_common():
        print(f"  {gid}: {n}")
    print("\n除外された配信者（上位20。ホロスターズ以外が混ざっていないか確認）:")
    for (name, reason), n in by_channel.most_common(20):
        print(f"  {name}: {n}件（{reason}）")
    if kept_confirmed:
        print("\n警告: 確定済み(confirmed)だが、現在の条件では除外対象のもの（そのまま残しています）:")
        for vid, gid, name, reason in kept_confirmed:
            print(f"  [{gid}] {vid} {name}（{reason}）")


def stats():
    games = load_json(GAMES_PATH, {})["games"]
    videos = load_videos()
    cnt = {g["id"]: Counter() for g in games}
    for v in videos.values():
        for gid, st in v["games"].items():
            if gid in cnt:
                cnt[gid][st] += 1
    print("作品\tauto\tpending\tconfirmed\trejected")
    for g in games:
        c = cnt[g["id"]]
        print(f"{g['ja']}\t{c['auto']}\t{c['pending']}\t{c['confirmed']}\t{c['rejected']}")


def pending(game_id=None):
    videos = load_videos()
    for vid, v in videos.items():
        for gid, st in v["games"].items():
            if st == "pending" and (game_id is None or gid == game_id):
                print(f"[{gid}] {vid}  {(v['available_at'] or '')[:10]}  {v['channel_name']}  {v['title']}")
                print(f"    https://www.youtube.com/watch?v={vid}")


def set_status(status: str, game_id: str, ids: list):
    if status not in STATUSES:
        sys.exit("STATUS は " + " / ".join(STATUSES) + " のいずれか")
    videos = load_videos()
    for i in ids:
        if i not in videos or game_id not in videos[i]["games"]:
            print(f"見つからない: {i}（作品 {game_id}）")
            continue
        videos[i]["games"][game_id] = status
    save_videos(videos)
    print("更新しました。")


def reject_pending(game_id: str):
    videos = load_videos()
    n = 0
    for v in videos.values():
        if v["games"].get(game_id) == "pending":
            v["games"][game_id] = "rejected"
            n += 1
    save_videos(videos)
    print(f"{n} 件を rejected にしました。")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args == ["--show-raw"]:
        collect(show_raw=bool(args))
    elif args[0] == "--recent" and len(args) <= 2:
        try:
            days = int(args[1]) if len(args) == 2 else RECENT_DAYS
        except ValueError:
            sys.exit("--recent の日数は整数で指定してください。")
        if days < 1:
            sys.exit("--recent の日数は 1 以上にしてください。")
        collect(show_raw=False, recent_days=days)
    elif args == ["channels"]:
        cmd_channels()
    elif args == ["clean"]:
        clean()
    elif args == ["stats"]:
        stats()
    elif args[0] == "pending":
        pending(args[1] if len(args) > 1 else None)
    elif args[0] == "set" and len(args) >= 4:
        set_status(args[1], args[2], args[3:])
    elif args[0] == "reject-pending" and len(args) == 2:
        reject_pending(args[1])
    else:
        sys.exit(__doc__)
