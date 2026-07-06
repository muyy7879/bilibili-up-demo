import json
import os
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone

CONFIG_FILE = "config.json"
DATA_FILE = "data/latest.json"


def http_get_json(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.bilibili.com/",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
        }
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_latest_video(uid):
    url = f"https://api.bilibili.com/x/space/arc/search?mid={uid}&pn=1&ps=1&order=pubdate"

    data = http_get_json(url)
    code = data.get("code", -1)

    if code != 0:
        msg = data.get("message", "unknown")
        raise Exception(f"API 返回错误: code={code}, message={msg}")

    vlist = data.get("data", {}).get("list", {}).get("vlist", [])
    if not vlist:
        return None

    video = vlist[0]
    bvid = video.get("bvid", "")
    aid = video.get("aid", "")
    title = video.get("title", "")
    created = video.get("created", 0)
    pic = video.get("pic", "")

    if pic.startswith("//"):
        pic = "https:" + pic

    if bvid:
        link = f"https://www.bilibili.com/video/{bvid}"
        video_id = bvid
    elif aid:
        link = f"https://www.bilibili.com/video/av{aid}"
        video_id = str(aid)
    else:
        link = ""
        video_id = ""

    pub_date = ""
    if created:
        pub_date = datetime.fromtimestamp(created, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    return {
        "title": title,
        "link": link,
        "pub_date": pub_date,
        "video_id": video_id,
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

        time.sleep(3)

        try:
            video = fetch_latest_video(uid)
        except Exception as e:
            print(f"[ERROR] 获取失败: {e}")
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

        if video is None:
            print("  该 UP 暂无公开视频")
            new_data[uid] = {
                "name": name,
                "uid": uid,
                "title": "该 UP 暂无公开视频",
                "link": f"https://space.bilibili.com/{uid}",
                "pub_date": "",
                "video_id": "",
                "cover": "",
                "checked_at": now,
                "updated_at": "",
                "is_new": False,
                "fetch_error": False
            }
            continue

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

        print(f"  标题: {video['title']}")
        print(f"  状态: {'新视频!' if is_new else '无变化'}")

    save_json(DATA_FILE, new_data)

    print("\n生成的 latest.json 内容：")
    print(json.dumps(new_data, ensure_ascii=False, indent=2))

    if success_count == 0:
        raise Exception("所有 UP 主都获取失败")

    print(f"\n完成，成功处理 {success_count} 个 UP 主")


if __name__ == "__main__":
    main()
