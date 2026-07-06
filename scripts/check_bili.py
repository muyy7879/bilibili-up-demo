import json
import os
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

CONFIG_FILE = "config.json"
DATA_FILE = "data/latest.json"


def fetch_rss(uid):
    url = f"https://rsshub.app/bilibili/user/video/{uid}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()
    except Exception as e:
        print(f"[ERROR] 获取 UID={uid} 的 RSS 失败: {e}")
        return None


def parse_latest_video(xml_data):
    root = ET.fromstring(xml_data)
    channel = root.find("channel")
    if channel is None:
        return None

    item = channel.find("item")
    if item is None:
        return None

    title = item.findtext("title", default="")
    link = item.findtext("link", default="")
    pub_date = item.findtext("pubDate", default="")
    description = item.findtext("description", default="")

    # 提取视频ID
    video_id = ""
    if "/video/" in link:
        video_id = link.rstrip("/").split("/video/")[-1].split("?")[0]

    # 提取封面图
    cover = ""
    if 'src="' in description:
        try:
            cover = description.split('src="')[1].split('"')[0]
            if cover.startswith("//"):
                cover = "https:" + cover
        except Exception:
            cover = ""

    return {
        "title": title,
        "link": link,
        "pub_date": pub_date,
        "video_id": video_id,
        "cover": cover
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
        print("config.json 中没有配置 UP 主")
        return

    old_data = load_json(DATA_FILE)
    new_data = {}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    for up in up_list:
        uid = up["uid"]
        name = up.get("name", uid)
        print(f"\n--- 检查: {name} (UID: {uid}) ---")

        xml_data = fetch_rss(uid)
        if xml_data is None:
            if uid in old_data:
                new_data[uid] = old_data[uid]
                new_data[uid]["checked_at"] = now
                new_data[uid]["fetch_error"] = True
            continue

        video = parse_latest_video(xml_data)
        if video is None:
            print(f"  解析失败，跳过")
            if uid in old_data:
                new_data[uid] = old_data[uid]
                new_data[uid]["checked_at"] = now
                new_data[uid]["fetch_error"] = True
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

        status = "新视频!" if is_new else "无变化"
        print(f"  标题: {video['title']}")
        print(f"  状态: {status}")

    save_json(DATA_FILE, new_data)
    print(f"\n检查完成，共 {len(new_data)} 个 UP 主")


if __name__ == "__main__":
    main()
