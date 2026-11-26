---
name: youtube-book-skill
description: 拉取指定 YouTube 频道的最新视频，用 Supadata 获取字幕，由宿主大模型撰写中英双语文章，生成带目录的 PDF 杂志并交付（可选发邮件）。当用户说"推送youtube内容"、"youtube digest"、"做个youtube杂志"时使用。
---

# YouTube Book Skill

把指定 YouTube 频道的新视频变成一份带目录的中英双语 PDF 杂志。写作由宿主 Agent 的大模型完成，不需要额外 AI API key，网络请求只用 Supadata。本技能完全自包含，整个目录可直接删除或上传到 codex / workbuddy。

## 目录结构

```text
youtube_book_skill/
├── SKILL.md
├── config.json
├── videos_state.json
├── transcripts_cache.json
├── articles/<video_id>.json
├── youtube_digest_YYYYMMDD.pdf
└── scripts/digest.py
```

## 首次配置

当 config.json 缺失或 supadata_api_key 为空时，依次向用户确认并写入：

1. 频道（默认 TheEconomist、xiao_lin_shuo，不带 @）
2. Supadata API Key（必填）：https://dash.supadata.ai 注册 → API Keys → 复制；免费额度 100 次/月
3. 是否发邮件（可选，默认不发）：QQ 邮箱在 mail.qq.com → 设置 → 账户 → 开启 POP3/SMTP 服务 → 生成 16 位授权码（非登录密码）

提醒用户：config.json 含密钥，不要提交到仓库。

## 依赖

pip install requests reportlab

中文字体：macOS 自带 PingFang；Linux 需安装 fonts-noto-cjk。

## 执行流程

第 1 步 拉视频与字幕：python scripts/digest.py fetch --days 7
输出 {"worklist": [...]}，每项含 video_id、title、description、channel、url、published_at、transcript。worklist 为空则告知用户“没有新视频”并结束。状态机与字幕缓存保证老视频零请求。

第 2 步 撰写文章（由你完成，不调用外部 AI API）
对 worklist 每一项写 articles/<video_id>.json，字段：video_id、title、channel、url、created（YYYY-MM-DD）、summary（不超过 100 字的简体中文总结）、article（markdown 正文）。
写作要求：杂志风格（参考 The New Yorker / The Atlantic），面向聪明但非专家的读者；中英交替成段（一段英文紧跟其中文译文）；用 title/description 纠正字幕转写错误（人名、公司名、术语）；保留关键引语、反直觉观点、意外洞见，术语就地解释；开头给一个与视频标题不同的标题（英文 + 中文）；禁止出现 In this video 类表述，当作独立文章写。

第 3 步 生成 PDF：python scripts/digest.py build
打印 PDF 路径。PDF 含封面、目录页（标题 + 简介 + 作者 + 创建时间 + 可点击页码）、正文。build 成功即把本批视频标记为 sent。

第 4 步 交付
默认把 PDF 路径作为产物交给用户或平台；若 config.json 中 email.enabled 为 true，执行 python scripts/digest.py send 发送邮件，成功后才标记 sent。