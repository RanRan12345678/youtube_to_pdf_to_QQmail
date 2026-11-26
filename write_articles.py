"""
Part 3: Transform Transcripts into Magazine Articles using Claude AI
Takes raw video transcripts and turns them into polished, readable articles.
"""

import os

import anthropic
import httpx
from dotenv import load_dotenv

# Load config from .env
load_dotenv()
ANTHROPIC_AUTH_TOKEN = os.getenv("ANTHROPIC_AUTH_TOKEN")
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

# MiniMax 是国内服务，trust_env=False 强制直连（与验证通过的 curl 路径一致），不依赖代理状态
client = anthropic.Anthropic(
    auth_token=ANTHROPIC_AUTH_TOKEN,
    base_url=ANTHROPIC_BASE_URL,
    http_client=httpx.Client(trust_env=False, timeout=120.0),
)


MAX_CONTINUATIONS = 3


def _extract_text(message):
    return [
        block.text
        for block in message.content
        if getattr(block, "type", None) == "text" and getattr(block, "text", None)
    ]


def _create_with_continuation(prompt):
    messages = [{"role": "user", "content": prompt}]
    full_text_parts = []

    for _ in range(MAX_CONTINUATIONS + 1):
        message = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=16000,
            messages=messages,
        )

        full_text_parts.extend(_extract_text(message))

        if getattr(message, "stop_reason", None) != "max_tokens":
            return "\n".join(full_text_parts)

        print(f"  ↻ Output hit max_tokens, continuing... ({sum(len(p) for p in full_text_parts)} chars so far)")
        messages = messages + [
            {"role": "assistant", "content": message.content},
            {"role": "user", "content": "Continue the article exactly where it stopped. Do not repeat previous text and do not add any commentary. Continue seamlessly."},
        ]

    return "\n".join(full_text_parts)


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
        article = _create_with_continuation(prompt)

        if not article:
            print("  ⚠ Model returned no text content")
            return None

        return article

    except Exception as e:
        print(f"  ⚠ Error generating article: {type(e).__name__}: {e}")
        cause = e.__cause__ or e.__context__
        if cause:
            print(f"    caused by: {type(cause).__name__}: {cause}")
        return None


def summarize_article(article_text, limit=100):
    """
    Ask MiniMax to write a short Simplified Chinese summary (~100 chars)
    of the article, for display in the newsletter table of contents.
    """
    prompt = f"""Below is a magazine article. Write a summary of it in Simplified Chinese, at most 100 Chinese characters, for display in a table of contents.

Rules:
- Output ONLY the summary text. No title, no quotes, no prefix like "总结：", no extra commentary.
- Capture the core topic and the single most interesting takeaway.
- Plain text only, no markdown.

ARTICLE:
{article_text}

---

Write the summary now (max 100 Chinese characters):"""

    try:
        message = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}],
        )
        summary = "".join(_extract_text(message)).strip()
        if not summary:
            return None
        summary = summary.splitlines()[0].strip()
        return summary[:limit]
    except Exception as e:
        print(f"  ⚠ Error generating summary: {type(e).__name__}: {e}")
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
