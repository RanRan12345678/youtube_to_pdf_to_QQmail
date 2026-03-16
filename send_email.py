"""
Part 4: Send Newsletter via Email
Sends the generated articles as a nicely formatted email newsletter with EPUB and PDF attachments.
"""

import os
import smtplib
import markdown
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from dotenv import load_dotenv
from ebooklib import epub
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors

# Load your credentials
load_dotenv()
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
PUSHPLUS_TOKEN = os.getenv("PUSHPLUS_TOKEN")


def create_epub(articles):
    """
    Create an EPUB ebook from the articles for reading on mobile devices.
    Returns the path to the generated EPUB file.
    """
    today = datetime.now().strftime("%B %d, %Y")
    filename = f"youtube_digest_{datetime.now().strftime('%Y%m%d')}.epub"
    filepath = os.path.join(os.path.dirname(__file__), filename)

    # Create the ebook
    book = epub.EpubBook()

    # Set metadata
    book.set_identifier(f"youtube-digest-{datetime.now().strftime('%Y%m%d%H%M%S')}")
    book.set_title(f"YouTube Digest - {today}")
    book.set_language("en")
    book.add_author("YouTube Newsletter Bot")

    # CSS for nice formatting on ebook readers
    style = """
    body {
        font-family: Georgia, serif;
        line-height: 1.6;
        padding: 1em;
    }
    h1 {
        font-size: 1.5em;
        margin-top: 1em;
        border-bottom: 1px solid #ccc;
        padding-bottom: 0.3em;
    }
    h2 {
        font-size: 1.3em;
        margin-top: 1em;
    }
    h3 {
        font-size: 1.1em;
    }
    .intro {
        background: #f5f5f5;
        padding: 1em;
        border-left: 3px solid #666;
        margin-bottom: 1.5em;
        font-size: 0.95em;
    }
    .watch-link {
        margin-top: 1.5em;
        padding: 0.5em;
        background: #f0f0f0;
        display: block;
    }
    """
    nav_css = epub.EpubItem(
        uid="style_nav",
        file_name="style/nav.css",
        media_type="text/css",
        content=style
    )
    book.add_item(nav_css)

    chapters = []

    # Create a chapter for each article
    for i, article in enumerate(articles):
        # Convert markdown to HTML
        article_html = markdown.markdown(article['article'])

        chapter_content = f"""
        <html>
        <head>
            <link rel="stylesheet" type="text/css" href="style/nav.css"/>
        </head>
        <body>
            <div class="intro">
                <p><em>This article is based on the video "<strong>{article['title']}</strong>" from the YouTube channel <strong>{article['channel']}</strong>.</em></p>
            </div>
            {article_html}
            <p class="watch-link">Watch the original video: {article['url']}</p>
        </body>
        </html>
        """

        chapter = epub.EpubHtml(
            title=article['title'][:50],
            file_name=f"chapter_{i+1}.xhtml",
            lang="en"
        )
        chapter.content = chapter_content
        chapter.add_item(nav_css)

        book.add_item(chapter)
        chapters.append(chapter)

    # Create table of contents
    book.toc = tuple(chapters)

    # Add navigation files
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Set the reading order
    book.spine = ["nav"] + chapters

    # Write the EPUB file
    epub.write_epub(filepath, book)

    print(f"  ✓ Created EPUB: {filename}")
    return filepath


def push_to_wechat(epub_path, pdf_path, articles):
    """
    Push the ebook to WeChat using PushPlus API.
    """
    if not PUSHPLUS_TOKEN:
        print("  ⚠ PUSHPLUS_TOKEN not set, skipping WeChat push")
        return False
    
    try:
        # Create summary with article titles
        summary = "📚 YouTube Digest\n\n"
        summary += "**📑 Articles:**\n"
        for i, article in enumerate(articles, 1):
            summary += f"{i}. {article['title'][:50]}" + ("..." if len(article['title']) > 50 else "") + "\n"
        
        # Add ebook information
        summary += "\n**📱 Ebook Files:**\n"
        summary += f"- EPUB: {os.path.basename(epub_path)}\n"
        summary += f"- PDF: {os.path.basename(pdf_path)}\n"
        summary += "\n*Ebooks are attached to the email.*"
        
        # Prepare data for PushPlus API
        data = {
            "token": PUSHPLUS_TOKEN,
            "title": f"📚 YouTube Digest - {datetime.now().strftime('%B %d, %Y')}",
            "content": summary,
            "template": "html"
        }
        
        # Send request
        response = requests.post(
            "http://www.pushplus.plus/send",
            json=data,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 200:
                print("  ✓ Pushed to WeChat successfully")
                return True
            else:
                print(f"  ✗ PushPlus error: {result.get('msg', 'Unknown error')}")
                return False
        else:
            print(f"  ✗ HTTP error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"  ✗ Failed to push to WeChat: {e}")
        return False


def create_pdf(articles):
    """
    Create a PDF ebook from the articles for reading on any device.
    Returns the path to the generated PDF file.
    """
    today = datetime.now().strftime("%B %d, %Y")
    filename = f"youtube_digest_{datetime.now().strftime('%Y%m%d')}.pdf"
    filepath = os.path.join(os.path.dirname(__file__), filename)

    # Create PDF document
    doc = SimpleDocTemplate(
        filepath,
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=18
    )

    # Register Chinese fonts for macOS
    try:
        # Try to register PingFang SC (macOS default Chinese font)
        pdfmetrics.registerFont(TTFont('PingFangSC', '/System/Library/Fonts/PingFang.ttc', subfontIndex=1))
        chinese_font = 'PingFangSC'
        print("  ✓ Using PingFang SC font for Chinese text")
    except:
        try:
            # Fallback to STHeiti
            pdfmetrics.registerFont(TTFont('STHeiti', '/System/Library/Fonts/STHeiti Light.ttc', subfontIndex=0))
            chinese_font = 'STHeiti'
            print("  ✓ Using STHeiti font for Chinese text")
        except:
            # If both fail, use Helvetica (Chinese won't display properly)
            chinese_font = 'Helvetica'
            print("  ⚠ Warning: Chinese font not found, Chinese text may not display properly")

    # Create styles
    styles = getSampleStyleSheet()
    
    # Custom styles for better formatting
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.darkblue,
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName=chinese_font
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.darkblue,
        spaceAfter=12,
        spaceBefore=20,
        fontName=chinese_font
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['BodyText'],
        fontSize=11,
        spaceAfter=12,
        leading=16,
        fontName=chinese_font
    )
    
    intro_style = ParagraphStyle(
        'CustomIntro',
        parent=styles['BodyText'],
        fontSize=10,
        textColor=colors.gray,
        spaceAfter=20,
        leading=14,
        fontName=chinese_font,
        leftIndent=20,
        rightIndent=20
    )
    
    link_style = ParagraphStyle(
        'CustomLink',
        parent=styles['BodyText'],
        fontSize=10,
        textColor=colors.blue,
        spaceAfter=30,
        fontName=chinese_font
    )

    # Build the story (content)
    story = []

    # Add title page
    story.append(Spacer(1, 2*inch))
    story.append(Paragraph("YOUR YOUTUBE DIGEST", title_style))
    story.append(Paragraph(today, ParagraphStyle(
        'DateStyle',
        parent=styles['Normal'],
        fontSize=14,
        alignment=TA_CENTER,
        spaceAfter=30,
        fontName=chinese_font
    )))
    story.append(PageBreak())

    # Add each article
    for i, article in enumerate(articles):
        # Convert markdown article to HTML, then to paragraphs
        article_html = markdown.markdown(article['article'])
        
        # Add article intro
        story.append(Paragraph(
            f"This article is based on the video <b>{article['title']}</b> from the YouTube channel <b>{article['channel']}</b>.",
            intro_style
        ))
        
        # Parse and add article content
        lines = article_html.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Remove HTML tags and convert to reportlab format
            if line.startswith('<h1>'):
                text = line.replace('<h1>', '').replace('</h1>', '')
                story.append(Paragraph(text, title_style))
            elif line.startswith('<h2>'):
                text = line.replace('<h2>', '').replace('</h2>', '')
                story.append(Paragraph(text, heading_style))
            elif line.startswith('<h3>'):
                text = line.replace('<h3>', '').replace('</h3>', '')
                story.append(Paragraph(text, heading_style))
            elif line.startswith('<p>'):
                text = line.replace('<p>', '').replace('</p>', '')
                # Convert markdown bold and italic to reportlab format
                text = text.replace('<strong>', '<b>').replace('</strong>', '</b>')
                text = text.replace('<em>', '<i>').replace('</em>', '</i>')
                text = text.replace('**', '<b>').replace('*', '<i>')
                story.append(Paragraph(text, body_style))
            elif line.startswith('<ul>') or line.startswith('</ul>') or line.startswith('<li>') or line.startswith('</li>'):
                continue  # Skip list tags for simplicity
            else:
                # Try to add as paragraph
                text = line.replace('<strong>', '<b>').replace('</strong>', '</b>')
                text = text.replace('<em>', '<i>').replace('</em>', '</i>')
                text = text.replace('**', '<b>').replace('*', '<i>')
                story.append(Paragraph(text, body_style))
        
        # Add video link
        story.append(Paragraph(f"Watch the original video: {article['url']}", link_style))
        
        # Add page break between articles (except for the last one)
        if i < len(articles) - 1:
            story.append(PageBreak())

    # Build the PDF
    doc.build(story)

    print(f"  ✓ Created PDF: {filename}")
    return filepath


def create_newsletter_html(articles):
    """
    Create a beautifully formatted HTML newsletter from the articles.
    Uses larger fonts for better readability.
    """
    today = datetime.now().strftime("%B %d, %Y")

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Georgia, serif;
                font-size: 18px;
                max-width: 700px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f9f9f9;
                color: #333;
            }}
            .header {{
                text-align: center;
                padding: 30px 0;
                border-bottom: 3px solid #333;
                margin-bottom: 30px;
            }}
            .header h1 {{
                margin: 0;
                font-size: 32px;
                letter-spacing: 2px;
            }}
            .header p {{
                color: #666;
                font-size: 18px;
                margin: 10px 0 0 0;
            }}
            .article {{
                background: white;
                padding: 30px;
                margin-bottom: 30px;
                border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }}
            .article-intro {{
                background: #f8f8f8;
                padding: 15px 20px;
                border-left: 4px solid #666;
                margin-bottom: 25px;
                font-size: 16px;
                color: #555;
                line-height: 1.6;
            }}
            .article-content {{
                font-size: 18px;
                line-height: 1.9;
            }}
            .article-content h1 {{
                color: #222;
                font-size: 26px;
                margin-top: 25px;
            }}
            .article-content h2 {{
                color: #222;
                font-size: 22px;
                margin-top: 25px;
            }}
            .article-content h3 {{
                color: #222;
                font-size: 20px;
                margin-top: 25px;
            }}
            .article-content p {{
                font-size: 18px;
                margin-bottom: 1em;
            }}
            .watch-link {{
                display: inline-block;
                margin-top: 20px;
                padding: 12px 24px;
                background: #ff0000;
                color: white !important;
                text-decoration: none;
                border-radius: 5px;
                font-size: 16px;
            }}
            .footer {{
                text-align: center;
                color: #999;
                font-size: 14px;
                padding: 20px;
            }}
            .epub-note {{
                text-align: center;
                background: #e8f4e8;
                padding: 15px;
                border-radius: 5px;
                margin-bottom: 30px;
                font-size: 16px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>YOUR YOUTUBE DIGEST</h1>
            <p>{today}</p>
        </div>
        <div class="epub-note">
            📚 EPUB ebook attached - open on your phone's ebook reader!<br>
            📄 PDF ebook attached - open on any device!
        </div>
    """

    for article in articles:
        # Convert markdown article to HTML
        article_html = markdown.markdown(article['article'])

        html += f"""
        <div class="article">
            <div class="article-intro">
                <em>This article is based on the video "<strong>{article['title']}</strong>" from the YouTube channel <strong>{article['channel']}</strong>.</em>
            </div>
            <div class="article-content">
                {article_html}
            </div>
            <a href="{article['url']}" class="watch-link">Watch the original video</a>
        </div>
        """

    html += """
        <div class="footer">
            Generated by YouTube Newsletter Bot
        </div>
    </body>
    </html>
    """

    return html


def save_newsletter_archive(html_content, epub_path, articles):
    """
    Save a copy of the newsletter for viewing in the archive.
    """
    newsletters_dir = os.path.join(os.path.dirname(__file__), "newsletters")
    os.makedirs(newsletters_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    date_display = datetime.now().strftime("%B %d, %Y")

    # Save HTML
    html_path = os.path.join(newsletters_dir, f"newsletter_{timestamp}.html")
    with open(html_path, "w") as f:
        f.write(html_content)

    # Copy EPUB
    import shutil
    epub_archive_path = os.path.join(newsletters_dir, f"newsletter_{timestamp}.epub")
    shutil.copy(epub_path, epub_archive_path)

    # Save metadata
    metadata = {
        "date": date_display,
        "timestamp": timestamp,
        "article_count": len(articles),
        "channels": [a["channel"] for a in articles],
        "titles": [a["title"] for a in articles],
        "html_file": f"newsletter_{timestamp}.html",
        "epub_file": f"newsletter_{timestamp}.epub"
    }

    metadata_path = os.path.join(newsletters_dir, f"newsletter_{timestamp}.json")
    import json
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"  ✓ Saved newsletter to archive")


def send_newsletter(articles, recipient_email=None):
    """
    Send the newsletter via Gmail with EPUB and PDF attachments.
    If no recipient specified, sends to yourself.
    """
    if not articles:
        print("No articles to send!")
        return False

    # Default to sending to yourself
    if recipient_email is None:
        recipient_email = GMAIL_ADDRESS

    print(f"\nPreparing newsletter for {recipient_email}...")

    # Create EPUB ebook
    print("  Creating EPUB ebook...")
    epub_path = create_epub(articles)
    
    # Create PDF ebook
    print("  Creating PDF ebook...")
    pdf_path = create_pdf(articles)

    # Push to WeChat
    print("  Pushing to WeChat...")
    #push_to_wechat(epub_path, pdf_path, articles)

    # Create the email (mixed type for attachments)
    msg = MIMEMultipart("mixed")
    msg["Subject"] = f"Your YouTube Digest - {datetime.now().strftime('%B %d, %Y')}"
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = recipient_email

    # Create the body part (alternative for text/html)
    body = MIMEMultipart("alternative")

    # Create HTML content
    html_content = create_newsletter_html(articles)

    # Create plain text version (simple fallback)
    text_content = "Your YouTube Newsletter\n\n"
    text_content += "📚 EPUB and PDF ebooks attached - open on your phone's ebook reader!\n\n"
    for article in articles:
        text_content += f"--- {article['channel']} ---\n"
        text_content += f"{article['article']}\n"
        text_content += f"Watch: {article['url']}\n\n"

    # Attach both text versions to body
    body.attach(MIMEText(text_content, "plain"))
    body.attach(MIMEText(html_content, "html"))

    # Add body to message
    msg.attach(body)

    # Attach EPUB file
    print("  Attaching EPUB file...")
    with open(epub_path, "rb") as attachment:
        epub_part = MIMEBase("application", "epub+zip")
        epub_part.set_payload(attachment.read())
        encoders.encode_base64(epub_part)
        epub_part.add_header(
            "Content-Disposition",
            f"attachment; filename={os.path.basename(epub_path)}"
        )
        msg.attach(epub_part)
    
    # Attach PDF file
    print("  Attaching PDF file...")
    with open(pdf_path, "rb") as attachment:
        pdf_part = MIMEBase("application", "pdf")
        pdf_part.set_payload(attachment.read())
        encoders.encode_base64(pdf_part)
        pdf_part.add_header(
            "Content-Disposition",
            f"attachment; filename={os.path.basename(pdf_path)}"
        )
        msg.attach(pdf_part)

    try:
        # Connect to SMTP server and send
        print("  Sending email...")
        
        # Detect if using QQ email
        if "qq.com" in GMAIL_ADDRESS:
            # Use QQ SMTP server
            smtp_server = "smtp.qq.com"
            smtp_port = 465
        else:
            # Use Gmail SMTP server
            smtp_server = "smtp.gmail.com"
            smtp_port = 465
        
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, recipient_email, msg.as_string())

        print("✓ Newsletter sent successfully with EPUB and PDF attachments!")

        # Save to archive before cleaning up
        save_newsletter_archive(html_content, epub_path, articles)

        # Clean up temporary files
        os.remove(epub_path)
        os.remove(pdf_path)

        return True

    except Exception as e:
        print(f"✗ Failed to send email: {e}")
        return False


# Test it standalone
if __name__ == "__main__":
    # Test with mock articles
    test_articles = [
        {
            "title": "Test Article",
            "channel": "Test Channel",
            "url": "https://youtube.com/watch?v=test",
            "article": "# Test Headline\n\nThis is a test article with **bold** and *italic* text.\n\n## Section 1\n\nSome content here."
        }
    ]

    print("Sending test newsletter...")
    send_newsletter(test_articles)
