#!/usr/bin/env python3
"""YouTube Book Skill 核心脚本.

用法:
  python scripts/digest.py fetch [--days N]   发现新视频并拉取字幕, 输出 worklist JSON
  python scripts/digest.py build              用 articles/ 生成带目录的 PDF
  python scripts/digest.py send               把最新 PDF 作为附件发邮件
"""
import glob
import hashlib
import json
import os
import smtplib
import sys
from datetime import datetime, timedelta, timezone
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(ROOT, "config.json")
STATE_FILE = os.path.join(ROOT, "videos_state.json")
CACHE_FILE = os.path.join(ROOT, "transcripts_cache.json")
ARTICLE_DIR = os.path.join(ROOT, "articles")

S_BASE = "https://api.supadata.ai/v1"
S_DISCOVERED = "discovered"
S_SKIPPED_OLD = "skipped_old"
S_TRANSCRIPTED = "transcripted"
S_SENT = "sent"

def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_config():
    cfg = load_json(CONFIG_FILE, None)
    if not isinstance(cfg, dict) or not cfg.get("supadata_api_key"):
        sys.exit("config.json 缺失或 supadata_api_key 为空, 请先按 SKILL.md 完成首次配置")
    return cfg

def sync_state(videos):
    state = load_json(STATE_FILE, {"videos": {}})
    pending = []
    for v in videos:
        vid = v["video_id"]
        if vid in state["videos"]:
            info = state["videos"][vid]
        else:
            info = {
                "title": v.get("title", ""), "channel": v.get("channel", ""),
                "url": v.get("url", ""), "status": v.get("status", S_DISCOVERED),
                "updated_at": datetime.now().isoformat(),
            }
            state["videos"][vid] = info
        if info["status"] == S_DISCOVERED:
            pending.append(v)
    save_json(STATE_FILE, state)
    return pending

def mark(ids, status):
    state = load_json(STATE_FILE, {"videos": {}})
    now = datetime.now().isoformat()
    for vid in ids:
        if vid in state["videos"]:
            state["videos"][vid]["status"] = status
            state["videos"][vid]["updated_at"] = now
    save_json(STATE_FILE, state)

def sd_get(cfg, path, params):
    r = requests.get(S_BASE + path, params=params,
                     headers={"x-api-key": cfg["supadata_api_key"]}, timeout=60)
    r.raise_for_status()
    return r.json()

def cmd_fetch(days):
    cfg = load_config()
    state = load_json(STATE_FILE, {"videos": {}})
    limit = cfg.get("max_videos_per_channel", 10)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    candidates = []
    for ch in cfg["channels"]:
        handle = ch.lstrip("@")
        try:
            data = sd_get(cfg, "/youtube/channel/videos",
                          {"id": handle, "type": "video", "limit": limit})
        except Exception as e:
            print(f"warn: channel {handle} fetch failed: {e}", file=sys.stderr)
            continue
        for vid in data.get("videoIds") or []:
            if vid in state["videos"]:
                continue
            try:
                meta = sd_get(cfg, "/metadata",
                              {"url": f"https://www.youtube.com/watch?v={vid}"})
            except Exception as e:
                print(f"warn: metadata failed for {vid}: {e}", file=sys.stderr)
                continue
            item = {
                "video_id": vid,
                "title": meta.get("title") or "",
                "channel": (meta.get("author") or {}).get("displayName") or handle,
                "url": meta.get("url") or f"https://www.youtube.com/watch?v={vid}",
                "description": meta.get("description") or "",
                "published_at": meta.get("createdAt") or "",
            }
            too_old = False
            if item["published_at"]:
                try:
                    too_old = datetime.fromisoformat(
                        item["published_at"].replace("Z", "+00:00")) < cutoff
                except ValueError:
                    pass
            item["status"] = S_SKIPPED_OLD if too_old else S_DISCOVERED
            candidates.append(item)

    pending = sync_state(candidates)
    if not pending:
        print(json.dumps({"worklist": [], "note": "no new videos"}, ensure_ascii=False))
        return

    cache = load_json(CACHE_FILE, {})
    worklist = []
    for v in pending:
        vid = v["video_id"]
        if cache.get(vid):
            t = cache[vid]
        else:
            try:
                data = sd_get(cfg, "/transcript", {"url": v["url"], "text": "true"})
            except Exception as e:
                print(f"warn: transcript failed for {vid}: {e}", file=sys.stderr)
                continue
            content = data.get("content")
            if isinstance(content, list):
                t = " ".join(s.get("text", "") for s in content).strip()
            else:
                t = (content or "").strip()
            if not t:
                print(f"warn: empty transcript for {vid}", file=sys.stderr)
                continue
            cache[vid] = t
            save_json(CACHE_FILE, cache)
        mark([vid], S_TRANSCRIPTED)
        worklist.append({**v, "transcript": t})
    print(json.dumps({"worklist": worklist}, ensure_ascii=False))

def _pick_font():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    for path, idx in [
        ("/System/Library/Fonts/PingFang.ttc", 1),
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0),
        ("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", 0),
    ]:
        try:
            pdfmetrics.registerFont(TTFont("DigestCJK", path, subfontIndex=idx))
            return "DigestCJK"
        except Exception:
            continue
    return "Helvetica"

def _md_inline(text):
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                .replace("**", "<b>").replace("*", "<i>"))

def cmd_build():
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, PageBreak, SimpleDocTemplate, Spacer
    from reportlab.platypus.tableofcontents import TableOfContents

    arts = []
    for p in sorted(glob.glob(os.path.join(ARTICLE_DIR, "*.json"))):
        data = load_json(p, None)
        if isinstance(data, dict) and data.get("article"):
            arts.append(data)
    if not arts:
        sys.exit("articles/ 下没有文章, 请先按 SKILL.md 第 2 步撰写")

    font = _pick_font()
    styles = getSampleStyleSheet()
    st_cover = ParagraphStyle("Cover", parent=styles["Heading1"], fontName=font,
                              fontSize=26, alignment=TA_CENTER, spaceAfter=24)
    st_art = ParagraphStyle("ArticleTitle", parent=styles["Heading1"], fontName=font,
                            fontSize=18, alignment=TA_LEFT, spaceAfter=10)
    st_meta = ParagraphStyle("Meta", parent=styles["Normal"], fontName=font,
                             fontSize=9, textColor=colors.gray, spaceAfter=16)
    st_body = ParagraphStyle("Body", parent=styles["BodyText"], fontName=font,
                             fontSize=11, leading=16, spaceAfter=10)
    st_toc = ParagraphStyle("TOCEntry", parent=styles["Normal"], fontName=font,
                            fontSize=10, leading=15, spaceAfter=12)

    class Doc(SimpleDocTemplate):
        def afterFlowable(self, flowable):
            if isinstance(flowable, Paragraph) and flowable.style.name == "ArticleTitle":
                entry = getattr(flowable, "_toc", None)
                if not entry:
                    return
                key = "toc-" + hashlib.sha1(entry["title"].encode("utf-8")).hexdigest()[:10]
                self.canv.bookmarkPage(key)
                self.notify("TOCEntry", (
                    0,
                    f'<b>{entry["num"]}. {_md_inline(entry["title"])}</b>'
                    f'<br/><font size="8" color="#666666">简介：{_md_inline(entry["summary"])}'
                    f'<br/>作者：{_md_inline(entry["channel"])} ｜ 创建时间：{entry["created"]}</font>',
                    self.page, key))

    out_path = os.path.join(ROOT, f"youtube_digest_{datetime.now().strftime('%Y%m%d')}.pdf")
    doc = Doc(out_path, pagesize=letter, rightMargin=72, leftMargin=72,
              topMargin=72, bottomMargin=54)
    toc = TableOfContents()
    toc.levelStyles = [st_toc]
    toc.dotsMinLevel = 0
    story = [
        Spacer(1, 2.5 * inch),
        Paragraph("YOUTUBE DIGEST", st_cover),
        Paragraph(datetime.now().strftime("%B %d, %Y"),
                  ParagraphStyle("Date", parent=st_cover, fontSize=14, spaceAfter=0)),
        PageBreak(),
        Paragraph("目录 · Contents", st_cover),
        Spacer(1, 0.3 * inch),
        toc,
        PageBreak(),
    ]
    for i, a in enumerate(arts, 1):
        header = Paragraph(f"{i}. {_md_inline(a['title'])}", st_art)
        header._toc = {"num": i, "title": a.get("title", ""), "summary": a.get("summary", ""),
                       "channel": a.get("channel", ""), "created": a.get("created", "")}
        story.append(header)
        story.append(Paragraph(
            f"作者：{_md_inline(a.get('channel', ''))} ｜ 创建时间：{a.get('created', '')}"
            f" ｜ {_md_inline(a.get('url', ''))}", st_meta))
        for para in a["article"].split("\n"):
            para = para.strip()
            if not para or para.startswith("#"):
                continue
            story.append(Paragraph(_md_inline(para), st_body))
        story.append(PageBreak())
    doc.multiBuild(story)

    mark([a["video_id"] for a in arts if a.get("video_id")], S_SENT)
    print(out_path)

def cmd_send():
    cfg = load_config()
    mail = cfg.get("email") or {}
    if not mail.get("enabled"):
        sys.exit("config.json 中 email.enabled 为 false, PDF 即交付物")
    pdfs = sorted(glob.glob(os.path.join(ROOT, "youtube_digest_*.pdf")))
    if not pdfs:
        sys.exit("没有找到 PDF, 请先执行 build")
    msg = MIMEMultipart()
    msg["Subject"] = f"YouTube Digest - {datetime.now().strftime('%B %d, %Y')}"
    msg["From"] = mail["address"]
    msg["To"] = mail.get("to") or mail["address"]
    msg.attach(MIMEText("YouTube digest attached.", "plain", "utf-8"))
    part = MIMEBase("application", "pdf")
    with open(pdfs[-1], "rb") as f:
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition",
                    f"attachment; filename={os.path.basename(pdfs[-1])}")
    msg.attach(part)
    with smtplib.SMTP_SSL(mail.get("smtp_host", "smtp.qq.com"),
                          int(mail.get("smtp_port", 465)), timeout=30) as s:
        s.login(mail["address"], mail["auth_code"])
        s.sendmail(mail["address"], [msg["To"]], msg.as_string())
    print(f"sent {os.path.basename(pdfs[-1])}")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "fetch":
        days = int(sys.argv[sys.argv.index("--days") + 1]) if "--days" in sys.argv else 7
        cmd_fetch(days)
    elif cmd == "build":
        cmd_build()
    elif cmd == "send":
        cmd_send()
    else:
        sys.exit("usage: digest.py fetch [--days N] | build | send")