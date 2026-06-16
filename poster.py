import os
import json
import time
import requests
import argparse
from datetime import datetime
from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler

load_dotenv()

ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
API_BASE = "https://graph.instagram.com/v25.0"


def create_container(image_url: str, caption: str) -> str:
    r = requests.post(
        f"{API_BASE}/{ACCOUNT_ID}/media",
        data={"image_url": image_url, "caption": caption, "access_token": ACCESS_TOKEN},
    )
    r.raise_for_status()
    creation_id = r.json()["id"]
    print(f"[{datetime.now()}] Media container created: {creation_id}")
    return creation_id


def publish_container(creation_id: str) -> dict:
    time.sleep(5)
    r = requests.post(
        f"{API_BASE}/{ACCOUNT_ID}/media_publish",
        data={"creation_id": creation_id, "access_token": ACCESS_TOKEN},
    )
    r.raise_for_status()
    result = r.json()
    print(f"[{datetime.now()}] Published! Post ID: {result.get('id')}")
    return result


def post_image(image_url: str, caption: str) -> dict:
    creation_id = create_container(image_url, caption)
    return publish_container(creation_id)


def post_carousel(image_urls: list[str], caption: str) -> dict:
    children = []
    for url in image_urls:
        r = requests.post(
            f"{API_BASE}/{ACCOUNT_ID}/media",
            data={"image_url": url, "is_carousel_item": "true", "access_token": ACCESS_TOKEN},
        )
        r.raise_for_status()
        children.append(r.json()["id"])
        print(f"  Carousel item created: {r.json()['id']}")

    r2 = requests.post(
        f"{API_BASE}/{ACCOUNT_ID}/media",
        data={
            "media_type": "CAROUSEL",
            "children": ",".join(children),
            "caption": caption,
            "access_token": ACCESS_TOKEN,
        },
    )
    r2.raise_for_status()
    creation_id = r2.json()["id"]
    print(f"[{datetime.now()}] Carousel container created: {creation_id}")
    return publish_container(creation_id)


def load_queue(queue_file: str) -> list:
    if not os.path.exists(queue_file):
        return []
    with open(queue_file, "r", encoding="utf-8") as f:
        return json.load(f)


def save_queue(queue: list, queue_file: str):
    with open(queue_file, "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)


def process_queue(queue_file: str):
    """Post all items in the queue whose scheduled time has passed."""
    queue = load_queue(queue_file)
    now = datetime.now()
    remaining = []

    for item in queue:
        scheduled = datetime.fromisoformat(item["scheduled_at"])
        if scheduled <= now:
            print(f"\n==> Posting: {item.get('caption', '')[:30]}...")
            try:
                urls = item.get("image_urls", [])
                caption = item.get("caption", "")
                creation_id = item.get("creation_id")

                # コンテナがまだ作成されていない場合のみ作成
                if not creation_id:
                    if len(urls) == 1:
                        creation_id = create_container(urls[0], caption)
                    else:
                        # カルーセルの場合はpost_carouselに委譲
                        post_carousel(urls, caption)
                        continue  # 成功したのでremainingに追加しない

                    # creation_idをキューに保存（publish失敗時の再利用のため）
                    item["creation_id"] = creation_id
                    save_queue([item] + [q for q in queue if q != item and datetime.fromisoformat(q["scheduled_at"]) > now], queue_file)

                publish_container(creation_id)
                # 成功 → remainingに追加しない（削除）

            except Exception as e:
                print(f"  ERROR: {e}")
                item["error"] = str(e)
                remaining.append(item)
        else:
            remaining.append(item)

    save_queue(remaining, queue_file)


def add_to_queue(queue_file: str, image_urls: list, caption: str, scheduled_at: str):
    queue = load_queue(queue_file)
    entry = {"image_urls": image_urls, "caption": caption, "scheduled_at": scheduled_at}
    queue.append(entry)
    save_queue(queue, queue_file)
    print(f"Added to queue: scheduled at {scheduled_at}")


def main():
    parser = argparse.ArgumentParser(description="Instagram Auto Poster")
    sub = parser.add_subparsers(dest="cmd")

    p_now = sub.add_parser("post", help="Post immediately")
    p_now.add_argument("--urls", nargs="+", required=True, help="Public image URL(s)")
    p_now.add_argument("--caption", default="", help="Caption text")

    p_add = sub.add_parser("add", help="Add to scheduled queue")
    p_add.add_argument("--urls", nargs="+", required=True, help="Public image URL(s)")
    p_add.add_argument("--caption", default="", help="Caption text")
    p_add.add_argument("--at", required=True, help="Schedule time (YYYY-MM-DD HH:MM)")

    sub.add_parser("list", help="Show pending queue")

    p_run = sub.add_parser("run", help="Start scheduler (checks queue every minute)")
    p_run.add_argument("--queue", default="queue.json", help="Queue file path")

    args = parser.parse_args()
    queue_file = getattr(args, "queue", "queue.json")

    if args.cmd == "post":
        if len(args.urls) == 1:
            post_image(args.urls[0], args.caption)
        else:
            post_carousel(args.urls, args.caption)

    elif args.cmd == "add":
        add_to_queue(queue_file, args.urls, args.caption, args.at)

    elif args.cmd == "list":
        queue = load_queue(queue_file)
        if not queue:
            print("Queue is empty.")
        for i, item in enumerate(queue):
            print(f"[{i+1}] {item['scheduled_at']} | {item['caption'][:40]} | {len(item['image_urls'])} image(s)")

    elif args.cmd == "run":
        print(f"Scheduler started. Queue file: {queue_file}")
        scheduler = BlockingScheduler()
        scheduler.add_job(process_queue, "interval", minutes=1, args=[queue_file])
        process_queue(queue_file)
        try:
            scheduler.start()
        except KeyboardInterrupt:
            print("Scheduler stopped.")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
