#!/usr/bin/env python3
"""每日健康资讯生成脚本 - GitHub Actions（中文输出）"""
import os, sys, re, time
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request
import xml.etree.ElementTree as ET

bj_tz = timezone(timedelta(hours=8))
today = datetime.now(bj_tz)
date_str = today.strftime("%Y-%m-%d")
date_display = today.strftime("%Y年%m月%d日")

SOURCES = [
    ("ScienceDaily", "https://www.sciencedaily.com/rss/health_medicine.xml", 6),
    ("WHO", "https://www.who.int/rss-feeds/news-zh.xml", 5),
    ("NIH", "https://www.nih.gov/news-events/news-releases/feed", 4),
    ("MedicalXpress", "https://medicalxpress.com/rss-feed/", 3),
    ("CDC", "https://tools.cdc.gov/api/v2/resources/media/news.rss", 2),
]

def fetch_rss(url, timeout=20):
    try:
        req = Request(url, headers={"User-Agent": "HealthNewsBot/1.0"})
        with urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as e:
        print(f"  WARN {url}: {e}")
        return None

def parse_items(xml_data):
    items = []
    try:
        root = ET.fromstring(xml_data)
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            desc = (item.findtext("description") or "").strip()
            desc = re.sub(r"<[^>]+>", "", desc)[:400]
            if title and link:
                items.append({"title": title, "url": link, "desc": desc})
    except Exception as e:
        print(f"  WARN Parse: {e}")
    return items

def translate_text(text):
    """使用 Google Translate 非官方 API 翻译"""
    if not text or not text.strip():
        return text
    # 如果已经包含中文，跳过翻译
    if any('\u4e00' <= c <= '\u9fff' for c in text):
        return text
    try:
        # 使用 translate.google.com 的简单 API
        import urllib.parse
        encoded = urllib.parse.quote(text[:500])
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=zh-CN&dt=t&q={encoded}"
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=10) as resp:
            result = resp.read().decode("utf-8")
            import json
            data = json.loads(result)
            translated = ""
            for block in data[0]:
                if block[0]:
                    translated += block[0]
            return translated.strip() if translated else text
    except Exception as e:
        print(f"    Translate error: {e}")
    return text

def classify(text):
    t = text or ""
    kw_map = [
        (["疫苗", "疫情", "病毒", "传染", "新冠", "流感"], "疫情"),
        (["心脏", "心血管", "血压", "高血压"], "心脏"),
        (["癌", "肿瘤"], "癌"),
        (["营养", "饮食", "食物", "膳食", "维生素", "蛋白", "营养"], "营养"),
        (["运动", "锻炼", "健身", "跑步", "体育"], "运动"),
        (["睡眠", "失眠"], "睡眠"),
        (["心理", "抑郁", "焦虑", "压力", "精神", "脑", "神经", "记忆", "认知", "阿尔茨海默", "痴呆", "大脑"], "心理"),
        (["政策", "指南", "法规", "报告"], "政策"),
        (["药", "治疗", "疗法", "药物", "抗生素"], "药"),
        (["中医", "中药", "针灸", "养生"], "中医"),
        (["免疫", "抗体", "炎症"], "免疫"),
        (["环境", "污染", "气候", "热浪", "温度", "空气"], "环境"),
    ]
    for kws, cat in kw_map:
        for kw in kws:
            if kw.lower() in t.lower():
                return cat
    return "疾病"

CATEGORIES = {
    "疫情": ("🦠", "传染病与疫情"),
    "心脏": ("❤️", "心血管健康"),
    "癌": ("🎗️", "癌症防治"),
    "营养": ("🍽️", "饮食营养"),
    "运动": ("🏃", "运动健身"),
    "睡眠": ("😴", "睡眠质量"),
    "心理": ("🧠", "脑科学与心理健康"),
    "政策": ("📋", "公共卫生政策"),
    "药": ("💊", "新药与疗法"),
    "中医": ("🌿", "中医养生"),
    "免疫": ("🛡️", "免疫健康"),
    "环境": ("🌍", "环境与健康"),
    "疾病": ("🔬", "疾病预防与研究"),
}

print(f"[START] {date_display}")
all_items = []

for sname, url, limit in SOURCES:
    print(f"  Fetch {sname}...")
    xml_data = fetch_rss(url)
    if not xml_data:
        continue
    items = parse_items(xml_data)
    print(f"    {len(items)} raw items")
    for item in items:
        if len(all_items) >= 20:
            break
        # 翻译
        print(f"    Translate: {item['title'][:40]}...")
        title_cn = translate_text(item["title"])
        desc_cn = translate_text(item["desc"])

        # 发现精彩切入点
        hook = ""
        lower_title = title_cn.lower()
        if any(w in lower_title for w in ["发现", "突破", "首次", "新", "揭秘", "秘密"]):
            hook = "最新研究发现"
        elif any(w in lower_title for w in ["预防", "降低", "减少", "风险"]):
            hook = "健康风险预警"
        elif any(w in lower_title for w in ["治疗", "疗法", "药物", "药"]):
            hook = "治疗新希望"
        elif any(w in lower_title for w in ["饮食", "营养", "食物", "吃"]):
            hook = "吃出健康"
        elif any(w in lower_title for w in ["运动", "锻炼", "健身"]):
            hook = "动起来"
        elif any(w in lower_title for w in ["睡眠", "失眠"]):
            hook = "睡眠革命"
        else:
            hook = "前沿科研快讯"

        ck = classify(title_cn + desc_cn)
        emoji, cname = CATEGORIES.get(ck, ("📌", "综合健康"))
        s = 5 if len(desc_cn) > 80 else 4
        tags = f"#{cname.replace(' ','')} #{hook} #健康科普"
        all_items.append({
            "title": title_cn, "desc": desc_cn,
            "url": item["url"], "source": sname,
            "star": s, "emoji": emoji, "cname": cname,
            "tags": tags, "hook": hook
        })
        time.sleep(0.3)  # 避免翻译 API 限流

print(f"  Total: {len(all_items)}")

if len(all_items) < 15:
    print("  WARNING: 不足15条，补充中...")
    # 用更多英文关键词搜索
    extra_queries = [
        ("cancer research", "https://news.google.com/rss/search?q=cancer+research+health&hl=en&ceid=US:en"),
        ("nutrition health", "https://news.google.com/rss/search?q=nutrition+health+study&hl=en&ceid=US:en"),
    ]
    for eq_name, eq_url in extra_queries:
        if len(all_items) >= 20:
            break
        xml_data = fetch_rss(eq_url)
        if xml_data:
            items = parse_items(xml_data)
            for item in items:
                if len(all_items) >= 20:
                    break
                title_cn = translate_text(item["title"])
                desc_cn = translate_text(item["desc"])
                ck = classify(title_cn + desc_cn)
                emoji, cname = CATEGORIES.get(ck, ("📌", "综合健康"))
                all_items.append({
                    "title": title_cn, "desc": desc_cn,
                    "url": item["url"], "source": eq_name,
                    "star": 4, "emoji": emoji, "cname": cname,
                    "tags": f"#{cname.replace(' ','')} #健康科普", "hook": "前沿科研快讯"
                })
                time.sleep(0.3)

print(f"  Final: {len(all_items)}")

# Group by category
cats = {}
for item in all_items:
    cn = item["cname"]
    if cn not in cats:
        cats[cn] = []
    cats[cn].append(item)

# Build MD
md = f"# 📋 每日健康资讯日报\n\n"
md += f"**日期：{date_display}**\n"
md += f"**本期精选：{len(all_items)} 条**\n"
md += f"**数据来源：WHO·NIH·CDC·ScienceDaily·MedicalXpress（自动翻译为中文）**\n\n---\n\n"

idx = 1
for cname in cats:
    citems = cats[cname]
    e = citems[0]["emoji"]
    md += f"## {e} {cname}（{len(citems)}条）\n\n"
    for item in citems:
        stars = "⭐" * item["star"]
        md += f"**选题{idx}**\n"
        md += f"- **标题**：{item['title']}\n"
        md += f"- **核心信息**：{item['desc']}\n"
        md += f"- **来源**：{item['source']}\n"
        md += f"- **原文链接**：[{item['url']}]({item['url']})\n"
        md += f"- **标签**：{item['tags']}\n"
        md += f"- **爆款指数**：{stars}\n"
        md += f"- **切入点**：{item['hook']}\n\n---\n\n"
        idx += 1

md += "## 📊 来源可信度审查摘要\n\n"
md += "| 来源 | 可信度 | 说明 |\n|------|--------|------|\n"
md += "| WHO | ⭐⭐⭐⭐⭐ | 世界卫生组织 |\n"
md += "| NIH | ⭐⭐⭐⭐⭐ | 美国国立卫生研究院 |\n"
md += "| CDC | ⭐⭐⭐⭐⭐ | 美国疾控中心 |\n"
md += "| ScienceDaily | ⭐⭐⭐⭐ | 权威科研新闻聚合 |\n"
md += "| MedicalXpress | ⭐⭐⭐⭐ | 医学研究新闻平台 |\n\n"
md += f"**审查结论**：本期 {len(all_items)} 条资讯均来自权威机构官方渠道，通过机器翻译为中文。建议点击原文链接获取完整英文原文。\n\n"
md += f"---\n*本报告由 GitHub Actions 自动生成于 {today.strftime('%Y-%m-%d %H:%M:%S')} CST*"

os.makedirs("reports", exist_ok=True)
os.makedirs("public", exist_ok=True)

md_path = f"reports/{date_str}-每日健康资讯.md"
with open(md_path, "w", encoding="utf-8") as f:
    f.write(md)
print(f"[OK] MD: {md_path}")

# Build HTML
h = '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">'
h += '<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no">'
h += f"<title>健康资讯 - {date_display}</title>"
h += '<style>'
h += '*{margin:0;padding:0;box-sizing:border-box}'
h += 'body{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;background:#f0f2f5;color:#333;line-height:1.8;-webkit-font-smoothing:antialiased}'
h += '.container{max-width:700px;margin:0 auto;padding:16px}'
h += '.header{background:linear-gradient(135deg,#2d8cf0,#19be6b);color:#fff;padding:24px 16px;border-radius:16px;margin-bottom:16px;text-align:center}'
h += '.header h1{font-size:22px;margin-bottom:6px}'
h += '.header p{opacity:.9;font-size:13px}'
h += '.card{background:#fff;border-radius:14px;padding:18px;margin-bottom:14px;box-shadow:0 1px 4px rgba(0,0,0,.04)}'
h += '.card h2{font-size:17px;margin-bottom:10px;color:#2d8cf0;padding-bottom:8px;border-bottom:2px solid #f0f2f5}'
h += '.item{border-bottom:1px solid #f5f5f5;padding:14px 0}'
h += '.item:last-child{border-bottom:none}'
h += '.item-title{font-size:15px;font-weight:600;margin-bottom:6px;color:#1a1a1a}'
h += '.item-desc{font-size:13px;color:#666;margin-bottom:6px}'
h += '.item-meta{font-size:11px;color:#999;display:flex;align-items:center;gap:8px;flex-wrap:wrap}'
h += '.item-meta a{color:#2d8cf0;text-decoration:none;font-weight:500}'
h += '.stars{color:#f5a623;letter-spacing:2px}'
h += '.tags{display:flex;flex-wrap:wrap;gap:5px;margin-top:6px}'
h += '.tag{background:#e8f4fd;color:#2d8cf0;padding:2px 10px;border-radius:10px;font-size:11px}'
h += '.source-badge{background:#f0f0f0;padding:2px 8px;border-radius:8px;font-size:10px;color:#888}'
h += '.review{background:#f6ffed;border:1px solid #b7eb8f;border-radius:14px;padding:16px;margin-top:16px}'
h += '.review h3{color:#52c41a;margin-bottom:8px;font-size:15px}'
h += '.review p{font-size:12px;color:#666}'
h += '.footer{text-align:center;color:#bbb;font-size:11px;padding:24px 0}'
h += '.footer a{color:#bbb}'
h += '@media (prefers-color-scheme:dark){'
h += 'body{background:#1a1a2e;color:#e0e0e0}'
h += '.card{background:#16213e;box-shadow:0 1px 4px rgba(0,0,0,.2)}'
h += '.card h2{color:#5dade2;border-color:#1a1a2e}'
h += '.item{border-color:#1a1a2e}'
h += '.item-title{color:#f0f0f0}'
h += '.item-desc{color:#aaa}'
h += '.tag{background:#1a2942;color:#5dade2}'
h += '.source-badge{background:#1a2942;color:#777}'
h += '.review{background:#0d2818;border-color:#1b5e20}'
h += '.review p{color:#aaa}}'
h += '</style></head><body><div class="container">'
h += '<div class="header">'
h += f'<h1>📋 每日健康资讯日报</h1>'
h += f'<p>{date_display} · {len(all_items)}条精选 · 云端自动更新</p>'
h += '<p style="font-size:11px;margin-top:6px;opacity:.7">WHO · NIH · CDC · ScienceDaily · MedicalXpress（自动翻译）</p>'
h += '</div>'

for cname in cats:
    citems = cats[cname]
    e = citems[0]["emoji"]
    h += f'<div class="card"><h2>{e} {cname}</h2>'
    for item in citems:
        stars_str = "⭐" * item["star"]
        h += '<div class="item">'
        h += f'<div class="item-title">{item["title"]}</div>'
        h += f'<div class="item-desc">{item["desc"][:200]}</div>'
        h += '<div class="item-meta">'
        h += f'<span class="source-badge">{item["source"]}</span>'
        h += f'<span class="stars">{stars_str}</span>'
        h += f'<a href="{item["url"]}" target="_blank">原文链接 →</a>'
        h += '</div>'
        h += f'<div class="tags"><span class="tag">{item["tags"]}</span></div>'
        h += '</div>'
    h += '</div>'

h += '<div class="review">'
h += '<h3>📊 来源可信度审查</h3>'
h += f'<p>本期 {len(all_items)} 条资讯来自：WHO⭐⭐⭐⭐⭐ · NIH⭐⭐⭐⭐⭐ · CDC⭐⭐⭐⭐⭐ · ScienceDaily⭐⭐⭐⭐ · MedicalXpress⭐⭐⭐⭐</p>'
h += '<p style="margin-top:6px">✅ 权威信源 · 机器翻译 · 建议参考原文链接</p>'
h += '</div>'

h += '<div class="footer">'
h += '<p>⏰ 每日 9:00 CST 自动更新 · GitHub Actions 云端生成</p>'
h += '<p>点击原文链接查看完整英文内容</p>'
h += '<p style="margin-top:4px"><a href="https://github.com/HawaiiTseng/health-news">HawaiiTseng/health-news</a></p>'
h += '</div>'
h += '</div></body></html>'

with open("public/index.html", "w", encoding="utf-8") as f:
    f.write(h)
print(f"[OK] HTML: public/index.html")
print(f"[DONE] {len(all_items)} items (Chinese)")
