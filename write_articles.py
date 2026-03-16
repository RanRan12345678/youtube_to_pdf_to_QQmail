"""
Part 3: Transform Transcripts into Magazine Articles using Claude AI
Takes raw video transcripts and turns them into polished, readable articles.
"""

import os
import anthropic
from dotenv import load_dotenv

# Load your API key
load_dotenv()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Create the Claude client
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def write_article(video):
    """
    Use Claude to transform a video transcript into a magazine-style article.
    """
    prompt = f"""You are a skilled magazine writer. Transform this YouTube video transcript into a well-written, engaging article in BOTH English and Chinese.

VIDEO TITLE: {video['title']}
CHANNEL: {video['channel']}
VIDEO URL: {video['url']}

VIDEO DESCRIPTION:
{video['description']}

TRANSCRIPT:
{video['transcript']}

---

Remix this YouTube transcript into a magazine article in BOTH English and Chinese. Guidelines:
- Write in alternating paragraphs: one paragraph in English, followed by its Chinese translation, then the next English paragraph, and so on.
- Use the video title and description to correct any transcription errors, especially names of people, companies, or technical terms. The description often contains the correct spellings.
- Start with an engaging headline (different from the video title) in both English and Chinese
- The audience is a curious individual who is generally smart but not a specialist or expert in the area mentioned in the video
- Highly engaging and readable. Wherever jargon or obscure references appear, explain them. Extremely well-written; think New Yorker or the Atlantic
- Capture the key insights, especially contrarian viewpoints, memorable anecdotes, and surprising insights. Preserve key quotes (clean up filler words or transcription errors).
- There's no fixed length requirement; it depends on the length of the original article as well as the insight density. Make your own judgment. This should be a satisfying long-read.
- Do NOT include phrases like "In this video" - write it as a standalone article. Assume the reader has not watched the video and has zero context about it. This article is meant to be as a replacement, not complement, for watching the video.
- The Chinese translation MUST be in Simplified Chinese (简体中文), not Traditional Chinese (繁体字).
- The Chinese translation should be natural, fluent, and maintain the same engaging style as the English version.

Format the article in clean markdown.

Example format:
# English Headline / 中文标题

First paragraph in English.

第一段中文翻译。

Second paragraph in English.

第二段中文翻译。
"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        return message.content[0].text

    except Exception as e:
        print(f"  ⚠ Error generating article: {e}")
        return None


def write_articles_for_videos(videos):
    """
    Generate articles for all videos with transcripts.
    """
    print("\nGenerating articles with Claude AI...\n")
    print("=" * 60)

    articles = []

    for video in videos:
        print(f"Writing article: {video['title'][:50]}...")

        article = write_article(video)

        if article:
            articles.append({
                "title": video["title"],
                "channel": video["channel"],
                "url": video["url"],
                "article": article
            })
            print(f"  ✓ Article generated!\n")
        else:
            print(f"  ✗ Failed to generate article\n")

    print("=" * 60)
    print(f"Generated {len(articles)} articles")

    return articles


# Test it standalone
if __name__ == "__main__":
    # Test with a mock video
    test_video = {
        "title": "Test Video",
        "channel": "Test Channel",
        "url": "https://youtube.com/watch?v=test",
        "transcript": "Hello everyone, today we're going to talk about something really exciting. I've been working on this project for months and I can't wait to share it with you. The main idea is simple but powerful..."
    }

    print("Testing article generation...")
    article = write_article(test_video)
    if article:
        print("\nGenerated article:\n")
        print(article)
