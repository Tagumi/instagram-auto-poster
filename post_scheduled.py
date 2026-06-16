import os
import json
import time
import requests
from datetime import datetime

ACCOUNT_ID = os.environ["INSTAGRAM_ACCOUNT_ID"]
ACCESS_TOKEN = os.environ["ACCESS_TOKEN"]
API_BASE = "https://graph.instagram.com/v25.0"
POSTS_FILE = "posts.json"
STATE_FILE = "state.json"


def create_container(image_url: str, caption: str) -> str:
    r = requests.post(
        f"{API_BASE}/{ACCOUNT_ID}/media",
        data={"image_url": image_url, "caption": caption, "access_token": ACCESS_TOKEN},
    )
    if not r.ok:
        print(f"API error response: {r.text}")
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


def load_state() -> int:
    if not os.path.exists(STATE_FILE):
        return 0
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f).get("next_index", 0)


def save_state(index: int):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"next_index": index}, f, ensure_ascii=False, indent=2)


def main():
    with open(POSTS_FILE, "r", encoding="utf-8") as f:
        posts = json.load(f)

    env_index = os.environ.get("POST_INDEX")
    index = int(env_index) % len(posts) if env_index else load_state() % len(posts)
    post = posts[index]

    print(f"[{datetime.utcnow().isoformat()}] Index {index}: {post['caption'][:50]}")

    creation_id = create_container(post["image_url"], post["caption"])
    result = publish_container(creation_id)
    print(f"Published! Post ID: {result.get('id')}")

    save_state((index + 1) % len(posts))
    print(f"Next index saved: {(index + 1) % len(posts)}")


if __name__ == "__main__":
    main()
