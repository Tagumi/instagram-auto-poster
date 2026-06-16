import os
import json
import time
import requests
from datetime import datetime

ACCOUNT_ID = os.environ["INSTAGRAM_ACCOUNT_ID"]
ACCESS_TOKEN = os.environ["ACCESS_TOKEN"]
API_BASE = "https://graph.instagram.com/v25.0"
POSTS_FILE = "posts.json"


def create_container(image_url: str, caption: str) -> str:
    r = requests.post(
        f"{API_BASE}/{ACCOUNT_ID}/media",
        data={"image_url": image_url, "caption": caption, "access_token": ACCESS_TOKEN},
    )
    r.raise_for_status()
    return r.json()["id"]


def publish_container(creation_id: str) -> dict:
    time.sleep(5)
    r = requests.post(
        f"{API_BASE}/{ACCOUNT_ID}/media_publish",
        data={"creation_id": creation_id, "access_token": ACCESS_TOKEN},
    )
    r.raise_for_status()
    return r.json()


def main():
    with open(POSTS_FILE, "r", encoding="utf-8") as f:
        posts = json.load(f)

    # POST_INDEX secret/variable で何番目を投稿するか指定（省略時は0番目）
    index = int(os.environ.get("POST_INDEX", "0")) % len(posts)
    post = posts[index]

    print(f"[{datetime.utcnow().isoformat()}] Index {index}: {post['caption'][:50]}")

    creation_id = create_container(post["image_url"], post["caption"])
    result = publish_container(creation_id)
    print(f"Published! Post ID: {result.get('id')}")
    print(f"Next index to use: {(index + 1) % len(posts)}")


if __name__ == "__main__":
    main()
