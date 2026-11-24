"""
YouTube Newsletter Generator - Main Script
Fetch videos → transcripts → articles → email, with per-video state machine.
Each video advances: discovered → transcripted → article_written → sent.
A failed step resumes from that step on the next run, relying on cached data.
"""

from get_videos import main as fetch_videos
from get_transcripts import get_transcript
from write_articles import write_article
from send_email import send_newsletter
import video_tracker as tracker


def run():
    print("=" * 60)
    print("  YOUTUBE NEWSLETTER GENERATOR")
    print("=" * 60)
    print(f"  State: {tracker.summary()}")

    # Step 1: Fetch latest videos from your channels
    print("\n📺 STEP 1: Fetching latest videos...\n")
    videos = fetch_videos()

    if not videos:
        print("No videos found. Check your channel list.")
        return

    # Step 1b: Register new videos / collect unfinished ones (resume workset)
    print("\n🔍 Checking for unfinished videos...\n")
    pending = tracker.sync_videos(videos)

    if not pending:
        print("Nothing to do. All videos have been sent before.")
        return

    print(f"\n  → {len(pending)} video(s) to process\n")

    ready = []
    for video in pending:
        vid = video["video_id"]
        print(f"\n--- {video['title'][:60]}")
        print(f"  state: {tracker.get_status(vid)}")

        # Step 2: Get transcript (local cache → Supadata → youtube-transcript-api)
        transcript = get_transcript(vid)
        if not transcript:
            print("  ⚠ No transcript available, skipping")
            continue
        tracker.set_status(vid, tracker.STATUS_TRANSCRIPTED,
                           title=video["title"], channel=video["channel"], url=video["url"])
        video["transcript"] = transcript

        # Step 3: Write article (cached on disk; AI only called when missing)
        cached = tracker.load_article(vid)
        if cached:
            article = cached["article"]
            print("  ✓ Article loaded from local cache")
        else:
            article = write_article(video)
            if not article:
                print("  ✗ Article generation failed, will retry next run")
                continue
            tracker.save_article(vid, {"title": video["title"], "channel": video["channel"],
                                       "url": video["url"], "article": article})
            print("  ✓ Article generated and saved")
        tracker.set_status(vid, tracker.STATUS_ARTICLE_WRITTEN,
                           title=video["title"], channel=video["channel"], url=video["url"])
        ready.append({"video_id": vid, "title": video["title"],
                      "channel": video["channel"], "url": video["url"], "article": article})

    if not ready:
        print("\nNo articles ready to send.")
        return

    # Step 4: Send the newsletter via email
    print("\n📧 STEP 4: Sending newsletter...\n")
    success = send_newsletter(ready)

    if success:
        tracker.mark_sent([v["video_id"] for v in ready])
        print(f"\n  ✓ Newsletter delivered, marked {len(ready)} video(s) as sent")
    else:
        print("\n  ⚠ Email failed — articles stay at 'article_written', will retry delivery next run")

    print("\n" + "=" * 60)
    print("  DONE!")
    print("=" * 60)


if __name__ == "__main__":
    run()
