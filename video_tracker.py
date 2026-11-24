"""
Video Tracker: per-video state machine with resumable pipeline.
States: discovered → transcripted → article_written → sent.
A run picks up every non-sent video and resumes it from its current step,
relying on cached transcripts and cached articles (articles/<id>.json)
instead of re-calling paid APIs.
"""

import json
import os
from datetime import datetime

STATE_FILE = os.path.join(os.path.dirname(__file__), "videos_state.json")
ARTICLES_DIR = os.path.join(os.path.dirname(__file__), "articles")

STATUS_DISCOVERED = "discovered"
STATUS_TRANSCRIPTED = "transcripted"
STATUS_ARTICLE_WRITTEN = "article_written"
STATUS_SENT = "sent"


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"videos": {}}


def save_state(data):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _update(video_id, **fields):
    data = load_state()
    info = data["videos"].setdefault(video_id, {})
    info.update(fields)
    info["updated_at"] = datetime.now().isoformat()
    save_state(data)
    return info


def get_status(video_id):
    info = load_state()["videos"].get(video_id)
    return info.get("status") if info else None


def set_status(video_id, status, title="", channel="", url=""):
    return _update(video_id, status=status, title=title, channel=channel, url=url)


def sync_videos(videos):
    """
    Register unseen videos as 'discovered'.
    Returns every video that is not 'sent' yet — the resumable workset.
    """
    data = load_state()
    pending = []
    for video in videos:
        vid = video["video_id"]
        info = data["videos"].get(vid)
        if info is None:
            data["videos"][vid] = {
                "title": video["title"],
                "channel": video["channel"],
                "url": video["url"],
                "status": STATUS_DISCOVERED,
                "updated_at": datetime.now().isoformat(),
            }
            pending.append(video)
            print(f"  🆕 New video discovered: {video['title'][:50]}...")
        elif info.get("status") != STATUS_SENT:
            pending.append(video)
        else:
            print(f"  ⏭ Skipping (sent): {video['title'][:50]}...")
    save_state(data)
    return pending


def article_path(video_id):
    return os.path.join(ARTICLES_DIR, f"{video_id}.json")


def load_article(video_id):
    if os.path.exists(article_path(video_id)):
        with open(article_path(video_id), "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_article(video_id, data):
    os.makedirs(ARTICLES_DIR, exist_ok=True)
    with open(article_path(video_id), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def mark_sent(video_ids):
    for vid in video_ids:
        _update(vid, status=STATUS_SENT)


def summary():
    counts = {}
    for info in load_state()["videos"].values():
        s = info.get("status", "unknown")
        counts[s] = counts.get(s, 0) + 1
    return counts


# Utility to view current state
if __name__ == "__main__":
    data = load_state()
    print(f"Total tracked videos: {len(data['videos'])}\n")
    for video_id, info in data["videos"].items():
        print(f"• [{info.get('status')}] {info.get('channel')}: {info.get('title', '')[:50]}")
