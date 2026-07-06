import json
import os
import urllib.request
from datetime import datetime, timezone, timedelta

CONFIG_FILE = "config.json"
DATA_FILE = "data/latest.json"


def fetch_latest_video(uid):
    url = f"https://api.bilibili.com/x/space/arc/search?mid={uid}&ps=1&pn=1&order=pubdate"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": f"https://space.bilibili.com/{uid}",
        "Origin": "https://www.bilibili.com",
        "Accept": "application/json, text/plain, */*"
    }

    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
    except Exception as e:
        print(f"[ERROR] 获取 UID={uid} 的视频列表失败: {e}")
        return None

    if data.get("code") != 0:
        print(f"[ERROR] UID={uid} 接口返回错误: code={data.get('code')}, message={data.get('message')}")
        return None

    vlist = data.get("data", {}).get("list", {}).get("vlist", [])
    if not vlist:
        print(f"[WARN] UID={uid} 没有找到视频")
        return None

    video = vlist[0]
    bvid = video.get("bvid", "")
    title = video.get("title", "")
    pic = video.get("pic", "")
    created = video.get("created", 0)

    if pic.startswith("//"):
        pic = "https:" + pic
    elif pic.startswith("http://"):
        pic = "https://" + pic[len("http://"):]

    try:
        pub_dt = datetime.fromtimestamp(int(created), tz=timezone.utc).astimezone(timezone(timedelta(hours=8)))
        pub_date = pub_dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        pub_date = str(created)

    return {
        "title": title,
        "link": f"https://www.bilibili.com/video/{bvid}" if bvid else "",
        "pub_date": pub_date,
        "video_id": bvid,
        "cover": pic
    }


def load_json(filepath):
    if not os.path.exists(filepath):
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    config = load_json(CONFIG_FILE)
    up_list = config.get("up_list", [])

    if not up_list:
        raise Exception("config.json 中没有配置 UP 主")

    old_data = load_json(DATA_FILE)
    new_data = {}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    success_count = 0

    for up in up_list:
        uid = up["uid"]
        name = up.get("name", uid)
        print(f"\n--- 检查: {name} (UID: {uid}) ---")

        video = fetch_latest_video(uid)
        if video is None:
            new_data[uid] = {
                "name": name,
                "uid": uid,
                "title": "",
                "link": "",
                "pub_date": "",
                "video_id": old_data.get(uid, {}).get("video_id", ""),
                "cover": "",
                "checked_at": now,
                "updated_at": old_data.get(uid, {}).get("updated_at", ""),
                "is_new": False,
                "fetch_error": True
            }
            continue

        success_count += 1

        old_video_id = old_data.get(uid, {}).get("video_id", "")
        is_new = video["video_id"] != old_video_id and old_video_id != ""

        if is_new:
            updated_at = now
        else:
            updated_at = old_data.get(uid, {}).get("updated_at", "")

        new_data[uid] = {
            "name": name,
            "uid": uid,
            "title": video["title"],
            "link": video["link"],
            "pub_date": video["pub_date"],
            "video_id": video["video_id"],
            "cover": video["cover"],
            "checked_at": now,
            "updated_at": updated_at,
            "is_new": is_new,
            "fetch_error": False
        }

        status = "🆕 新视频!" if is_new else "无变化"
        print(f"  标题: {video['title']}")
        print(f"  状态: {status}")

    save_json(DATA_FILE, new_data)

    print("\n生成的 latest.json 内容：")
    print(json.dumps(new_data, ensure_ascii=False, indent=2))

    if success_count == 0:
        raise Exception("所有 UP 主抓取失败，请检查 B 站接口是否可用")

    print(f"\n✅ 检查完成，成功抓取 {success_count} 个 UP 主")


if __name__ == "__main__":
    main()
