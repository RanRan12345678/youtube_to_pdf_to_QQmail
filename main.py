"""
YouTube Newsletter Generator - Main Script
Ties together all the pieces: fetch videos → get transcripts → write articles → send email
Tracks processed videos to avoid sending duplicates.
"""

from get_videos import main as fetch_videos
from get_transcripts import get_transcripts_for_videos
from write_articles import write_articles_for_videos
from send_email import send_newsletter
from video_tracker import filter_new_videos, mark_videos_processed, get_processed_count


def run():
    """
    Run the full newsletter pipeline.
    """
    print("=" * 60)
    print("  YOUTUBE NEWSLETTER GENERATOR")
    print("=" * 60)
    print(f"  Previously processed: {get_processed_count()} videos")

    # Step 1: Fetch latest videos from your channels
    print("\n📺 STEP 1: Fetching latest videos...\n")
    videos = fetch_videos()

    if not videos:
        print("No videos found. Check your channel list.")
        return

    # Step 1b: Filter out already-processed videos
    print("\n🔍 Checking for new videos...\n")
    new_videos = filter_new_videos(videos)

    if not new_videos:
        print("No new videos to process. All videos have been sent before.")
        print("=" * 60)
        return

    print(f"\n  → {len(new_videos)} new video(s) to process\n")

    # Step 2: Get transcripts for those videos
    print("\n📝 STEP 2: Extracting transcripts...\n")
    videos_with_transcripts = get_transcripts_for_videos(new_videos)

    if not videos_with_transcripts:
        print("No transcripts available for any videos.")
        return

    # Step 3: Generate articles using Claude AI
    print("\n✍️ STEP 3: Writing articles with Claude AI...\n")
    articles = write_articles_for_videos(videos_with_transcripts)

    if not articles:
        print("No articles generated.")
        return

    # Step 3b: Mark as processed AFTER article generation succeeds
    # (so we don't re-burn MiniMax token on reruns even if email fails)
    mark_videos_processed(videos_with_transcripts)
    print(f"\n  ✓ Marked {len(videos_with_transcripts)} video(s) as processed after article generation")

    # Step 4: Send the newsletter via email
    print("\n📧 STEP 4: Sending newsletter...\n")
    success = send_newsletter(articles)

    if not success:
        print("\n  ⚠ Email failed — but articles were saved, run again later to retry delivery")

    print("\n" + "=" * 60)
    print("  DONE!")
    print("=" * 60)

    return articles


if __name__ == "__main__":
    run()
