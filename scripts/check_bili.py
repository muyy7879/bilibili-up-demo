import hashlib
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

CONFIG_FILE = "config.json"
DATA_FILE = "data/latest.json"

USER_AGENT = "Mozilla/5.0"
MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52
]


def http_get_json(url, params=None):
    if params:
        query = urllib.parse.urlencode(params)
        url = f"{url}?{query}"

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Referer": "https://www.bilibili.com/"
        }
    )

    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))



def get_wbi_keys():
    data = http_get_json("https://api.bilibili.com/x/web-interface/nav")

    wbi_img = data.get("data", {}).get("wbi_img", {})
    img_url = wbi_img.get("img_url", "")
    sub_url = wbi_img.get("sub_url", "")

    if not img_url or not sub_url:
        raise Exception(f"获取 WBI key 失败: {data}")

    img_key = os.path.basename(urllib.parse.urlparse(img_url).path).split(".")[0]
    sub_key = os.path.basename(urllib.parse.urlparse(sub_url).path).split(".")[0]
    return img_key, sub_key

def get_mixin_key(orig):
    return "".join(orig[i] for i in MIXIN_KEY_ENC_TAB)[:32]


def sign_wbi_params(params, img_key, sub_key):
    mixin_key = get_mixin_key(img_key + sub_key)

    params = {k: str(v) for k, v in params.items()}
    params["wts"] = str(int(time.time()))

    filtered = {}
    for k in sorted(params.keys()):
        v = params[k]
        v = "".join(ch for ch in v if ch not in "!'()*")
        filtered[k] = v

    query = urllib.parse.urlencode(filtered)
    w_rid = hashlib.md5((query + mixin_key).encode("utf-8")).hexdigest()
    filtered["w_rid"] = w_rid
    return filtered


def fetch_latest_video(uid, img_key, sub_key):
    base_url = "https://api.bilibili.com/x/space/wbi/arc/search"
    params = {
        "mid": uid,
        "pn": 1,
        "ps": 1,
        "order": "pubdate"
    }

    signed_params = sign_wbi_params(params, img_key, sub_key)
    data = http_get_json(base_url, signed_params)

    if data.get("code") != 0:
        raise Exception(f"获取视频列表失败: code={data.get('code')}, message={data.get('message')}")

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

    img_key, sub_key = get_wbi_keys()
    success_count = 0

    for up in up_list:
        uid = up["uid"]
        name = up.get("name", uid)
        print(f"\n--- 检查: {name} (UID: {uid}) ---")

        try:
            video = fetch_latest_video(uid, img_key, sub_key)
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
            new_data[uid] = {
                "name": name,
                "uid": uid,
                "title": "该 UP 暂无公开视频",
                "link": f"https://space.bilibili.com/{uid}",
                "pub_date": "",
                "video_id": old_data.get(uid, {}).get("video_id", ""),
                "cover": "",
                "checked_at": now,
                "updated_at": old_data.get(uid, {}).get("updated_at", ""),
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

        print(f"标题: {video['title']}")
        print(f"状态: {'🆕 新视频' if is_new else '无变化'}")

    save_json(DATA_FILE, new_data)

    print("\n生成的 latest.json 内容：")
    print(json.dumps(new_data, ensure_ascii=False, indent=2))

    if success_count == 0:
        raise Exception("所有 UP 主都获取失败，请检查接口是否变更")

    print(f"\n 检查完成，成功处理 {success_count} 个 UP 主")


if __name__ == "__main__":
    main()
