#!/usr/bin/env python3
"""
MyHear Auto Update v3 - "Breathing MyHear"
매일 자동 실행 - 진짜 숨쉬는 사이트

v2 기능 유지:
- YouTube 인기 영상 자동 교체
- Hero/재생목록 AI 큐레이션 (Claude)
- HTML 자율 수정

v3 신규:
- 매일 블로그 1편 자동 작성 (Claude)
- /blog/ 폴더 구조 자동 생성
- sitemap.xml 자동 생성 (SEO)
- robots.txt 생성
- 메인 index.html에 "최근 블로그" 섹션 자동 갱신

운영 철학: 사장님 개입 0. AI가 매일 오전 9시 숨 한 번 쉬고 성장.
"""

import os
import re
import sys
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

try:
    from googleapiclient.discovery import build
    from anthropic import Anthropic
except ImportError as e:
    print(f"❌ 라이브러리 import 실패: {e}")
    sys.exit(1)

# ============================================================
# 설정
# ============================================================
CHANNEL_HANDLE = "@hearing_device_editor"
HTML_FILE = "index.html"
BLOG_DIR = "blog"
BLOG_HISTORY_FILE = "blog/_history.json"
SITEMAP_FILE = "sitemap.xml"
ROBOTS_FILE = "robots.txt"
SITE_URL = "https://myhear.pages.dev"

YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')

if not YOUTUBE_API_KEY:
    print("❌ YOUTUBE_API_KEY 환경변수 없음")
    sys.exit(1)


# ============================================================
# 블로그 주제 풀 (SEO 키워드 50개, 타겟 별)
# ============================================================
BLOG_TOPIC_POOL = [
    # 1차 타겟 5070 (실사용자)
    {"slug": "보청기-처음-사용-주의사항", "title": "보청기 처음 사용할 때 꼭 알아야 할 것", "keyword": "보청기 처음 사용", "audience": "5070"},
    {"slug": "보청기-배터리-수명", "title": "보청기 배터리는 얼마나 오래 가나요?", "keyword": "보청기 배터리", "audience": "5070"},
    {"slug": "보청기-젖었을-때", "title": "보청기가 물에 젖었을 때 응급 대처법", "keyword": "보청기 물", "audience": "5070"},
    {"slug": "보청기-관리-방법", "title": "보청기 수명을 늘리는 5가지 관리 습관", "keyword": "보청기 관리", "audience": "5070"},
    {"slug": "보청기-as-비용", "title": "보청기 AS 비용, 어떻게 해야 할까?", "keyword": "보청기 AS", "audience": "5070"},
    {"slug": "보청기-적응-기간", "title": "보청기 적응 기간은 얼마나 걸릴까?", "keyword": "보청기 적응", "audience": "5070"},
    {"slug": "보청기-귀에-안-맞을-때", "title": "보청기가 귀에 잘 안 맞을 때 체크할 3가지", "keyword": "보청기 불편", "audience": "5070"},
    {"slug": "노인성-난청-원인", "title": "노인성 난청은 왜 생길까? 원인과 예방", "keyword": "노인성 난청", "audience": "5070"},
    {"slug": "이명과-난청", "title": "이명이 있다면 난청도 있을 수 있습니다", "keyword": "이명 난청", "audience": "5070"},
    {"slug": "보청기-수명", "title": "보청기 평균 수명은 몇 년일까?", "keyword": "보청기 수명", "audience": "5070"},
    {"slug": "양쪽-착용-필요성", "title": "보청기는 왜 양쪽 다 끼는 것이 좋을까", "keyword": "양쪽 보청기", "audience": "5070"},
    {"slug": "청력검사-주기", "title": "청력 검사는 얼마나 자주 받아야 할까?", "keyword": "청력검사", "audience": "5070"},
    {"slug": "보청기-충전식-vs-배터리", "title": "충전식 보청기 vs 배터리식, 뭐가 좋을까?", "keyword": "충전식 보청기", "audience": "5070"},
    {"slug": "보청기-블루투스", "title": "보청기 블루투스 연결, 어떻게 쓰나요?", "keyword": "블루투스 보청기", "audience": "5070"},
    {"slug": "보청기-세척-방법", "title": "보청기 올바른 세척과 소독 방법", "keyword": "보청기 세척", "audience": "5070"},
    {"slug": "보청기-습도-관리", "title": "장마철 보청기 습기 관리 완벽 가이드", "keyword": "보청기 습기", "audience": "5070"},
    {"slug": "보청기-필터-교체", "title": "보청기 필터는 언제 교체해야 할까?", "keyword": "보청기 필터", "audience": "5070"},

    # 2차 타겟 3040 (자녀)
    {"slug": "부모님-보청기-선물", "title": "부모님께 보청기 선물하기 전 꼭 확인할 것", "keyword": "부모님 보청기", "audience": "3040"},
    {"slug": "청각장애-보조금-131만원", "title": "청각장애 등록 시 받는 보조금 131만원 완전 정리", "keyword": "청각장애 보조금", "audience": "3040"},
    {"slug": "보청기-보험-신청", "title": "건강보험 보청기 보조금 신청 절차 안내", "keyword": "보청기 보험", "audience": "3040"},
    {"slug": "중고-보청기-주의", "title": "중고 보청기 구매 전 반드시 알아야 할 3가지", "keyword": "중고 보청기", "audience": "3040"},
    {"slug": "아이들-청력-관리", "title": "우리 아이 청력, 언제 검사해야 할까?", "keyword": "아이 청력", "audience": "3040"},
    {"slug": "난청-증상-체크리스트", "title": "부모님 난청 의심되는 5가지 신호", "keyword": "난청 증상", "audience": "3040"},
    {"slug": "돌발성-난청", "title": "돌발성 난청, 골든타임 72시간", "keyword": "돌발성 난청", "audience": "3040"},

    # 제품·기술
    {"slug": "보청기-가격-차이", "title": "같은 제품인데 가격이 다른 이유", "keyword": "보청기 가격", "audience": "both"},
    {"slug": "포낙-오티콘-비교", "title": "포낙 vs 오티콘, 무엇이 다른가?", "keyword": "포낙 오티콘", "audience": "both"},
    {"slug": "시그니아-특징", "title": "독일 시그니아 보청기의 특징 3가지", "keyword": "시그니아", "audience": "both"},
    {"slug": "ric-vs-bte", "title": "RIC형 vs BTE형 보청기, 어떤 게 맞을까", "keyword": "RIC BTE", "audience": "both"},
    {"slug": "cic-보청기", "title": "CIC 초소형 보청기의 장단점", "keyword": "CIC 보청기", "audience": "both"},
    {"slug": "ai-보청기-장점", "title": "AI 보청기, 정말 차이가 있을까?", "keyword": "AI 보청기", "audience": "both"},
    {"slug": "환경-자동-분석", "title": "보청기의 '환경 자동 분석' 기능이란?", "keyword": "환경 분석 보청기", "audience": "both"},
    {"slug": "음성-명료도", "title": "보청기 고를 때 '음성 명료도'가 중요한 이유", "keyword": "음성 명료도", "audience": "both"},
    {"slug": "피드백-소음", "title": "보청기 삐- 소리(피드백) 해결법", "keyword": "보청기 소음", "audience": "5070"},

    # 의료 지식
    {"slug": "인공와우-vs-보청기", "title": "인공와우와 보청기는 어떻게 다른가", "keyword": "인공와우", "audience": "both"},
    {"slug": "감각신경성-난청", "title": "감각신경성 난청이란?", "keyword": "감각신경성 난청", "audience": "both"},
    {"slug": "전음성-난청", "title": "전음성 난청, 보청기로 해결 가능할까", "keyword": "전음성 난청", "audience": "both"},
    {"slug": "소음성-난청", "title": "소음성 난청, 직업인의 경고등", "keyword": "소음성 난청", "audience": "both"},
    {"slug": "고주파-난청", "title": "고주파 난청: 새소리가 안 들린다면", "keyword": "고주파 난청", "audience": "both"},
    {"slug": "저주파-난청", "title": "저주파 난청의 원인과 대처", "keyword": "저주파 난청", "audience": "both"},
    {"slug": "청신경종양", "title": "청신경종양이 의심될 때", "keyword": "청신경종양", "audience": "both"},

    # 예방·청력보호 (세레니티 초이스 연결)
    {"slug": "공연장-귀마개", "title": "공연·페스티벌 갈 때 귀 보호하는 법", "keyword": "공연 귀마개", "audience": "3040"},
    {"slug": "수영-귀-보호", "title": "수영할 때 귀 물 들어가는 걸 막는 법", "keyword": "수영 귀마개", "audience": "3040"},
    {"slug": "직업성-난청-예방", "title": "공장·건설 현장 직업성 난청 예방", "keyword": "직업성 난청", "audience": "3040"},
    {"slug": "수면-소음-차단", "title": "수면 중 소음 차단, 잠 못 드는 분들께", "keyword": "수면 귀마개", "audience": "3040"},
    {"slug": "음악가-귀마개", "title": "음악가를 위한 고품질 귀마개 추천 기준", "keyword": "음악가 귀마개", "audience": "3040"},
    {"slug": "귀-청소-방법", "title": "귀지 제거, 이렇게 하면 위험합니다", "keyword": "귀지 제거", "audience": "5070"},

    # 지역·브랜드
    {"slug": "은평구-보청기-센터", "title": "은평구에서 보청기 맞추기 — 구파발역 가이드", "keyword": "은평 보청기", "audience": "5070"},
    {"slug": "부산-보청기", "title": "부산·경남 지역 보청기 방문 상담", "keyword": "부산 보청기", "audience": "both"},
    {"slug": "보청기에디터-누구", "title": "보청기에디터 김진영은 누구인가", "keyword": "보청기에디터", "audience": "both"},
    {"slug": "15년-피팅-이야기", "title": "15년 피팅 전문가가 본 보청기 트렌드", "keyword": "보청기 트렌드", "audience": "both"},
]


# ============================================================
# 유틸리티
# ============================================================
def load_blog_history():
    """이미 작성한 블로그 주제 기록 로드"""
    path = Path(BLOG_HISTORY_FILE)
    if not path.exists():
        return {"written": [], "last_updated": None}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {"written": [], "last_updated": None}


def save_blog_history(history):
    """블로그 주제 기록 저장"""
    Path(BLOG_DIR).mkdir(exist_ok=True)
    with open(BLOG_HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def pick_next_topic(history):
    """아직 안 쓴 주제 중 하나 선택 (순환)"""
    written_slugs = set(history.get("written", []))
    candidates = [t for t in BLOG_TOPIC_POOL if t["slug"] not in written_slugs]
    if not candidates:
        # 전부 돌았으면 가장 오래된 주제부터 재활용
        print("ℹ️ 모든 주제 1회 완료 → 재순환 시작")
        history["written"] = []
        candidates = BLOG_TOPIC_POOL
    # 날짜 해시로 의사 랜덤 선택 (매일 다른 주제)
    today_str = datetime.now().strftime("%Y-%m-%d")
    idx = int(hashlib.md5(today_str.encode()).hexdigest(), 16) % len(candidates)
    return candidates[idx]


# ============================================================
# YouTube 관련 (v2 그대로)
# ============================================================
def get_channel_id(youtube, handle):
    try:
        handle_clean = handle.lstrip('@')
        request = youtube.search().list(part="snippet", q=handle_clean, type="channel", maxResults=5)
        response = request.execute()
        for item in response.get('items', []):
            channel_title = item['snippet']['channelTitle']
            if '보청기' in channel_title or 'hearing' in channel_title.lower():
                return item['snippet']['channelId']
        if response.get('items'):
            return response['items'][0]['snippet']['channelId']
        return None
    except Exception as e:
        print(f"❌ 채널 ID 조회 실패: {e}")
        return None


def is_short_video(duration_str, title="", description=""):
    text = (title + " " + description).lower()
    if '#shorts' in text or '#쇼츠' in text:
        return True
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
    if not match:
        return False
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    total_seconds = hours * 3600 + minutes * 60 + seconds
    return total_seconds <= 65


def get_popular_videos(youtube, channel_id, days=30, max_results=40):
    try:
        published_after = (datetime.utcnow() - timedelta(days=days)).isoformat() + 'Z'
        search_request = youtube.search().list(
            part="id,snippet", channelId=channel_id, order="viewCount",
            type="video", publishedAfter=published_after, maxResults=max_results
        )
        search_response = search_request.execute()
        video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
        if not video_ids:
            search_request = youtube.search().list(
                part="id,snippet", channelId=channel_id, order="viewCount",
                type="video", maxResults=max_results
            )
            search_response = search_request.execute()
            video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
        if not video_ids:
            return []
        videos_request = youtube.videos().list(
            part="snippet,statistics,contentDetails", id=','.join(video_ids)
        )
        videos_response = videos_request.execute()
        videos = []
        for item in videos_response.get('items', []):
            duration = item['contentDetails']['duration']
            title = item['snippet']['title']
            description = item['snippet'].get('description', '')[:300]
            videos.append({
                'id': item['id'], 'title': title, 'description': description,
                'published': item['snippet']['publishedAt'],
                'views': int(item['statistics'].get('viewCount', 0)),
                'likes': int(item['statistics'].get('likeCount', 0)),
                'comments': int(item['statistics'].get('commentCount', 0)),
                'duration': duration,
                'is_short': is_short_video(duration, title, description)
            })
        videos.sort(key=lambda x: x['views'], reverse=True)
        return videos
    except Exception as e:
        print(f"❌ 영상 조회 실패: {e}")
        return []


# ============================================================
# 블로그 자동 작성 (v3 신규)
# ============================================================
def write_blog_with_claude(topic):
    """Claude로 블로그 글 1편 작성"""
    if not ANTHROPIC_API_KEY:
        print("⚠️ ANTHROPIC_API_KEY 없음 - 블로그 작성 건너뜀")
        return None

    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    audience_guide = {
        "5070": "5070대 보청기 사용자 본인. 큰 글씨로 읽는 걸 상상하고 어려운 기술 용어 없이 친근하게.",
        "3040": "부모님 보청기를 알아보는 3040대 자녀. 효율적·비교 중심. 핵심 요약 + 결론.",
        "both": "일반 독자. 기술 용어는 한 번 풀어주면서 전문성도 유지."
    }.get(topic["audience"], "일반 독자")

    prompt = f"""당신은 MyHear 사이트의 전속 블로그 에디터입니다. 운영자는 15년 청각학 경력의 김진영 대표(보청기에디터 유튜브 45,600 구독자). 99유럽보청기 운영.

[오늘 작성할 글]
- 제목 후보: "{topic['title']}"
- 핵심 키워드: {topic['keyword']}
- 타겟 독자: {audience_guide}

[필수 규칙]
1. 1,500~2,000자 한국어 블로그 포스트
2. 의료광고법 위반 표현 절대 금지: "최고", "1위", "완치", "가장 좋은", "효과 보장"
3. 특정 제품 단정·비방 금지. "A사 대비 B 차별화" 구조만 허용.
4. 판매자 시점이 아닌 **독자의 고민 해결** 시점.
5. 마지막에 자연스러운 CTA 1문장. 판매 강매 X. "더 궁금하면 02-389-6999" 같이 부담 없이.
6. 본문 구조: 3초 후킹 도입 → H2 2~3개 → 결론
7. 모든 H2는 독자 관점 질문형 또는 호기심 자극
8. 마크다운 금지. HTML 직접 작성.

[출력 형식 — 반드시 이 JSON만, 다른 말 금지]
{{
  "title": "실제 글 제목 (30자 이내)",
  "meta_description": "검색 결과 노출용 요약 (150자 이내)",
  "keywords": "쉼표로 구분된 SEO 키워드 5~7개",
  "html_body": "<p>도입...</p><h2>질문1</h2><p>답...</p><h2>질문2</h2><p>답...</p>",
  "excerpt": "목록 페이지용 2줄 요약 (100자 내)"
}}"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )
        response_text = message.content[0].text.strip()
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            return json.loads(json_match.group())
        return None
    except Exception as e:
        print(f"❌ Claude 블로그 작성 실패: {e}")
        return None


def render_blog_html(blog_data, topic, date_str):
    """블로그 글 HTML 페이지 생성 (메인 사이트 스타일 통일)"""
    title = blog_data.get("title", topic["title"])
    meta_desc = blog_data.get("meta_description", "")
    keywords = blog_data.get("keywords", topic["keyword"])
    body = blog_data.get("html_body", "")
    slug = topic["slug"]
    url = f"{SITE_URL}/{BLOG_DIR}/{date_str}-{slug}.html"

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} | MyHear 보청기에디터</title>
<meta name="description" content="{meta_desc}">
<meta name="keywords" content="{keywords}">
<meta name="author" content="김진영 · 보청기에디터">
<meta name="theme-color" content="#000000">
<link rel="canonical" href="{url}">

<!-- Open Graph -->
<meta property="og:title" content="{title}">
<meta property="og:description" content="{meta_desc}">
<meta property="og:type" content="article">
<meta property="og:url" content="{url}">
<meta property="og:site_name" content="MyHear · 보청기에디터">
<meta property="og:locale" content="ko_KR">
<meta property="article:published_time" content="{date_str}T09:00:00+09:00">
<meta property="article:author" content="김진영">

<!-- Schema.org Article -->
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "{title}",
  "description": "{meta_desc}",
  "author": {{
    "@type": "Person",
    "name": "김진영",
    "jobTitle": "청각학 전공 · 보청기에디터"
  }},
  "publisher": {{
    "@type": "Organization",
    "name": "99유럽보청기 · MyHear",
    "url": "{SITE_URL}"
  }},
  "datePublished": "{date_str}",
  "mainEntityOfPage": "{url}",
  "keywords": "{keywords}"
}}
</script>

<link rel="preconnect" href="https://cdn.jsdelivr.net">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/variable/pretendardvariable.css">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ctext y='.9em' font-size='90'%3E👂%3C/text%3E%3C/svg%3E">
<style>
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{font-family:'Pretendard Variable',Pretendard,-apple-system,sans-serif;background:#fff;color:#000;line-height:1.75;font-size:17px;-webkit-font-smoothing:antialiased;}}
a{{color:inherit;}}
.nav{{position:sticky;top:0;background:rgba(255,255,255,0.92);backdrop-filter:blur(20px);border-bottom:1px solid #f0f0f0;z-index:100;}}
.nav-inner{{max-width:840px;margin:0 auto;padding:18px 24px;display:flex;justify-content:space-between;align-items:center;}}
.nav-brand{{font-weight:700;font-size:18px;letter-spacing:-0.02em;text-decoration:none;}}
.nav-back{{font-size:14px;color:#666;text-decoration:none;}}
.nav-back:hover{{color:#000;}}
article{{max-width:720px;margin:0 auto;padding:64px 24px 96px;}}
.breadcrumb{{font-size:13px;color:#888;margin-bottom:20px;}}
.breadcrumb a{{text-decoration:none;color:#888;}}
.breadcrumb a:hover{{color:#000;}}
h1{{font-size:clamp(28px,4vw,40px);font-weight:800;letter-spacing:-0.03em;line-height:1.25;margin-bottom:20px;}}
.post-meta{{font-size:13px;color:#888;margin-bottom:48px;padding-bottom:24px;border-bottom:1px solid #eee;}}
.post-meta strong{{color:#000;}}
article p{{margin-bottom:22px;color:#2a2a2a;}}
article h2{{font-size:clamp(22px,3vw,28px);font-weight:700;margin:56px 0 18px;letter-spacing:-0.02em;line-height:1.35;}}
article h3{{font-size:20px;font-weight:700;margin:32px 0 12px;letter-spacing:-0.01em;}}
article ul,article ol{{margin:16px 0 22px 20px;}}
article li{{margin-bottom:8px;color:#2a2a2a;}}
article strong{{color:#000;font-weight:700;}}
article blockquote{{border-left:3px solid #000;padding-left:20px;margin:24px 0;color:#555;font-style:italic;}}
.cta-box{{margin-top:64px;padding:32px;border:1px solid #eee;border-radius:16px;background:#fafafa;text-align:center;}}
.cta-box h3{{margin-top:0;margin-bottom:12px;}}
.cta-box p{{margin-bottom:20px;color:#555;font-size:15px;}}
.cta-btn{{display:inline-block;background:#000;color:#fff;padding:14px 28px;border-radius:999px;text-decoration:none;font-weight:700;font-size:15px;}}
.back-to-blog{{display:inline-block;margin-top:48px;font-size:14px;color:#666;text-decoration:none;}}
.back-to-blog:hover{{color:#000;}}
footer{{border-top:1px solid #eee;padding:32px 24px;text-align:center;font-size:12px;color:#888;}}
footer a{{color:#666;text-decoration:none;margin:0 8px;}}
.floating-cta{{position:fixed;bottom:24px;right:24px;z-index:9999;background:#000;color:#fff !important;padding:14px 22px;border-radius:999px;display:inline-flex;align-items:center;gap:10px;text-decoration:none;font-weight:700;font-size:15px;box-shadow:0 10px 30px rgba(0,0,0,0.28);}}
@media(max-width:640px){{.floating-cta{{bottom:16px;right:16px;padding:12px 18px;font-size:14px;}}}}
</style>
</head>
<body>

<nav class="nav">
  <div class="nav-inner">
    <a href="{SITE_URL}" class="nav-brand">MyHear</a>
    <a href="{SITE_URL}/{BLOG_DIR}/" class="nav-back">← 블로그 목록</a>
  </div>
</nav>

<article>
  <div class="breadcrumb">
    <a href="{SITE_URL}">홈</a> / <a href="{SITE_URL}/{BLOG_DIR}/">블로그</a> / {title}
  </div>
  <h1>{title}</h1>
  <div class="post-meta">
    <strong>보청기에디터 김진영</strong> · {date_str} · 키워드: {keywords}
  </div>

  {body}

  <div class="cta-box">
    <h3>📞 보청기 전문 상담</h3>
    <p>15년 청각학 전공 김진영 대표가 직접 상담합니다. 은평구 구파발역 3번 출구 도보 1분.</p>
    <a href="tel:02-389-6999" class="cta-btn">02-389-6999 무료 상담</a>
  </div>

  <a href="{SITE_URL}/{BLOG_DIR}/" class="back-to-blog">← 다른 글도 읽어보기</a>
</article>

<footer>
  <div>99유럽보청기 · 대표 김진영 · 사업자등록번호 126-34-00739</div>
  <div>통신판매업신고 제2019-서울은평-1086호 · 의료기기 판매업 신고 제1240호</div>
  <div style="margin-top:8px;">
    <a href="{SITE_URL}">홈</a>
    <a href="{SITE_URL}/{BLOG_DIR}/">블로그</a>
    <a href="https://www.youtube.com/@hearing_device_editor" target="_blank">유튜브</a>
  </div>
</footer>

<a href="tel:02-389-6999" class="floating-cta" aria-label="전화 상담 02-389-6999">
  <span>📞</span><span>무료 상담</span>
</a>

</body>
</html>"""


def render_blog_index(posts):
    """블로그 목록 페이지 생성 (/blog/index.html)"""
    post_cards = ""
    for p in posts[:20]:  # 최신 20개
        post_cards += f"""
    <a href="{p['filename']}" class="post-card">
      <div class="post-date">{p['date']}</div>
      <h3 class="post-title">{p['title']}</h3>
      <p class="post-excerpt">{p['excerpt']}</p>
      <span class="post-arrow">→</span>
    </a>"""

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>블로그 | MyHear 보청기에디터</title>
<meta name="description" content="15년 보청기 전문가가 매일 1편씩 쌓는 보청기 지식 아카이브. 난청·보청기 관리·보조금·브랜드 비교까지.">
<meta name="author" content="김진영 · 보청기에디터">
<link rel="canonical" href="{SITE_URL}/{BLOG_DIR}/">
<meta property="og:title" content="MyHear 블로그 — 보청기 지식 아카이브">
<meta property="og:description" content="매일 1편씩 쌓이는 보청기 지식. 15년 전문가의 생생한 현장 경험.">
<meta property="og:type" content="website">
<meta property="og:url" content="{SITE_URL}/{BLOG_DIR}/">
<link rel="preconnect" href="https://cdn.jsdelivr.net">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/variable/pretendardvariable.css">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ctext y='.9em' font-size='90'%3E👂%3C/text%3E%3C/svg%3E">
<style>
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{font-family:'Pretendard Variable',Pretendard,-apple-system,sans-serif;background:#fff;color:#000;font-size:17px;-webkit-font-smoothing:antialiased;}}
a{{color:inherit;text-decoration:none;}}
.nav{{position:sticky;top:0;background:rgba(255,255,255,0.92);backdrop-filter:blur(20px);border-bottom:1px solid #f0f0f0;z-index:100;}}
.nav-inner{{max-width:1080px;margin:0 auto;padding:18px 24px;display:flex;justify-content:space-between;align-items:center;}}
.nav-brand{{font-weight:700;font-size:18px;letter-spacing:-0.02em;}}
.nav-back{{font-size:14px;color:#666;}}
.hero{{max-width:1080px;margin:0 auto;padding:80px 24px 48px;}}
.hero h1{{font-size:clamp(34px,5vw,52px);font-weight:800;letter-spacing:-0.03em;line-height:1.15;margin-bottom:16px;}}
.hero p{{color:#666;font-size:18px;max-width:540px;line-height:1.6;}}
main{{max-width:1080px;margin:0 auto;padding:32px 24px 96px;}}
.post-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:20px;}}
.post-card{{display:block;padding:28px;border:1px solid #eee;border-radius:18px;transition:all 0.2s ease;position:relative;background:#fff;}}
.post-card:hover{{border-color:#000;transform:translateY(-3px);box-shadow:0 16px 40px rgba(0,0,0,0.06);}}
.post-date{{font-size:12px;color:#888;margin-bottom:10px;letter-spacing:0.02em;}}
.post-title{{font-size:20px;font-weight:700;letter-spacing:-0.02em;line-height:1.35;margin-bottom:10px;}}
.post-excerpt{{font-size:14px;color:#555;line-height:1.6;margin-bottom:16px;}}
.post-arrow{{font-size:18px;color:#888;}}
.post-card:hover .post-arrow{{color:#000;}}
footer{{border-top:1px solid #eee;padding:32px 24px;text-align:center;font-size:12px;color:#888;}}
footer a{{color:#666;margin:0 8px;}}
.floating-cta{{position:fixed;bottom:24px;right:24px;z-index:9999;background:#000;color:#fff !important;padding:14px 22px;border-radius:999px;display:inline-flex;align-items:center;gap:10px;font-weight:700;font-size:15px;box-shadow:0 10px 30px rgba(0,0,0,0.28);}}
@media(max-width:640px){{.floating-cta{{bottom:16px;right:16px;padding:12px 18px;font-size:14px;}}}}
</style>
</head>
<body>
<nav class="nav">
  <div class="nav-inner">
    <a href="{SITE_URL}" class="nav-brand">MyHear</a>
    <a href="{SITE_URL}" class="nav-back">← 메인</a>
  </div>
</nav>
<section class="hero">
  <h1>MyHear 블로그</h1>
  <p>15년 청각학 전공 김진영 대표가 매일 한 편씩 쌓는 보청기 지식 아카이브. 난청·관리·보조금·브랜드 비교까지.</p>
</section>
<main>
  <div class="post-grid">{post_cards}
  </div>
</main>
<footer>
  <div>99유럽보청기 · 대표 김진영 · 사업자등록번호 126-34-00739</div>
  <div>통신판매업신고 제2019-서울은평-1086호 · 의료기기 판매업 신고 제1240호</div>
  <div style="margin-top:8px;">
    <a href="{SITE_URL}">홈</a>
    <a href="https://www.youtube.com/@hearing_device_editor" target="_blank">유튜브</a>
  </div>
</footer>
<a href="tel:02-389-6999" class="floating-cta" aria-label="전화 상담 02-389-6999">
  <span>📞</span><span>무료 상담</span>
</a>
</body>
</html>"""


def generate_blog_post():
    """블로그 1편 생성 프로세스"""
    print("\n📝 블로그 자동 작성 시작")

    history = load_blog_history()
    topic = pick_next_topic(history)
    print(f"   🎯 오늘 주제: {topic['title']} ({topic['audience']})")

    blog_data = write_blog_with_claude(topic)
    if not blog_data:
        print("   ❌ Claude 블로그 작성 실패")
        return None

    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"{date_str}-{topic['slug']}.html"
    filepath = Path(BLOG_DIR) / filename

    Path(BLOG_DIR).mkdir(exist_ok=True)
    html = render_blog_html(blog_data, topic, date_str)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"   ✅ 저장: {filepath}")

    # history 업데이트
    history["written"].append(topic["slug"])
    history.setdefault("posts", []).insert(0, {
        "slug": topic["slug"],
        "filename": filename,
        "date": date_str,
        "title": blog_data.get("title", topic["title"]),
        "excerpt": blog_data.get("excerpt", ""),
        "keywords": blog_data.get("keywords", topic["keyword"])
    })
    history["last_updated"] = date_str
    save_blog_history(history)

    # 블로그 인덱스 갱신
    index_html = render_blog_index(history.get("posts", []))
    with open(Path(BLOG_DIR) / "index.html", 'w', encoding='utf-8') as f:
        f.write(index_html)
    print(f"   ✅ 인덱스 갱신: blog/index.html")

    return history["posts"][0]


# ============================================================
# sitemap.xml / robots.txt 생성 (v3 신규)
# ============================================================
def generate_sitemap():
    """전체 사이트 URL을 sitemap.xml로 생성 (네이버·구글 검색 등록용)"""
    today = datetime.now().strftime("%Y-%m-%d")
    urls = [
        (f"{SITE_URL}/", "1.0", "daily"),
        (f"{SITE_URL}/{BLOG_DIR}/", "0.9", "daily"),
    ]

    history = load_blog_history()
    for post in history.get("posts", []):
        urls.append((f"{SITE_URL}/{BLOG_DIR}/{post['filename']}", "0.7", "monthly"))

    xml_items = "\n".join([
        f'  <url><loc>{u[0]}</loc><lastmod>{today}</lastmod><changefreq>{u[2]}</changefreq><priority>{u[1]}</priority></url>'
        for u in urls
    ])
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{xml_items}
</urlset>'''
    with open(SITEMAP_FILE, 'w', encoding='utf-8') as f:
        f.write(xml)
    print(f"   ✅ {SITEMAP_FILE} ({len(urls)} URLs)")


def generate_robots():
    """robots.txt — 모든 검색봇 허용 + sitemap 명시"""
    content = f"""User-agent: *
Allow: /

Sitemap: {SITE_URL}/{SITEMAP_FILE}
"""
    with open(ROBOTS_FILE, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"   ✅ {ROBOTS_FILE}")


# ============================================================
# 메인 index.html에 "최근 블로그 3개" 섹션 주입
# ============================================================
def update_main_with_recent_blog(recent_posts):
    """메인 index.html에 최근 블로그 섹션 자동 갱신"""
    if not Path(HTML_FILE).exists():
        print(f"   ⚠️ {HTML_FILE} 없음 - 메인 갱신 건너뜀")
        return

    if not recent_posts:
        return

    cards_html = ""
    for p in recent_posts[:3]:
        cards_html += f"""
      <a href="/{BLOG_DIR}/{p['filename']}" class="blog-card fade-up">
        <div class="blog-date">{p['date']}</div>
        <div class="blog-title">{p['title']}</div>
        <div class="blog-excerpt">{p['excerpt']}</div>
        <div class="blog-link">읽어보기 →</div>
      </a>"""

    marker_start = "<!-- RECENT_BLOG_START -->"
    marker_end = "<!-- RECENT_BLOG_END -->"

    section_html = f"""{marker_start}
<section class="block soft" id="blog-recent" style="padding:80px 0;">
  <div class="container">
    <div class="block-label">Blog · 매일 자동 발행</div>
    <h2 class="block-title fade-up">최근 보청기 이야기</h2>
    <p style="color:#666;max-width:560px;margin-bottom:40px;">AI가 매일 1편씩 쌓아가는 보청기 지식. 15년 경력 김진영 에디터 감수.</p>
    <div class="blog-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:20px;">{cards_html}
    </div>
    <div style="margin-top:32px;text-align:center;">
      <a href="/{BLOG_DIR}/" style="display:inline-block;padding:14px 28px;border:1px solid #000;border-radius:999px;text-decoration:none;font-weight:700;color:#000;">블로그 전체 보기</a>
    </div>
  </div>
</section>
<style>
.blog-card{{display:block;padding:26px;background:#fff;border:1px solid #eee;border-radius:16px;text-decoration:none;color:inherit;transition:all 0.2s ease;}}
.blog-card:hover{{border-color:#000;transform:translateY(-3px);box-shadow:0 16px 40px rgba(0,0,0,0.06);}}
.blog-date{{font-size:12px;color:#888;margin-bottom:10px;}}
.blog-title{{font-size:18px;font-weight:700;letter-spacing:-0.02em;margin-bottom:10px;line-height:1.4;}}
.blog-excerpt{{font-size:14px;color:#555;line-height:1.6;margin-bottom:16px;}}
.blog-link{{font-size:13px;color:#000;font-weight:600;}}
</style>
{marker_end}"""

    with open(HTML_FILE, 'r', encoding='utf-8') as f:
        html = f.read()

    if marker_start in html and marker_end in html:
        # 기존 블록 교체
        html = re.sub(
            rf"{re.escape(marker_start)}[\s\S]*?{re.escape(marker_end)}",
            section_html,
            html
        )
        print("   ✅ 메인 블로그 섹션 갱신")
    else:
        # 최초: 푸터 바로 앞에 삽입
        if "<footer>" in html:
            html = html.replace("<footer>", f"{section_html}\n<footer>", 1)
            print("   ✅ 메인 블로그 섹션 신규 삽입")
        else:
            print("   ⚠️ 메인 구조 이상 - 블로그 섹션 삽입 건너뜀")
            return

    with open(HTML_FILE, 'w', encoding='utf-8') as f:
        f.write(html)


# ============================================================
# YouTube 큐레이션 (v2 로직 그대로 - 간소화 버전)
# ============================================================
def update_youtube_section(videos, videos_by_id):
    """간단 버전: Hero 영상 ID만 최신 인기 영상으로 교체"""
    if not Path(HTML_FILE).exists() or not videos:
        return

    hero_id = videos[0]['id']
    hero_video = videos_by_id.get(hero_id)
    is_short = hero_video.get('is_short', False) if hero_video else False

    with open(HTML_FILE, 'r', encoding='utf-8') as f:
        html = f.read()

    hero_pattern = r'(class="video-hero-wrap"[^>]*>[\s\S]*?<iframe src="https://www\.youtube\.com/embed/)([a-zA-Z0-9_-]+)(")'
    new_html, count = re.subn(hero_pattern, rf'\g<1>{hero_id}\g<3>', html, count=1)
    if count > 0:
        with open(HTML_FILE, 'w', encoding='utf-8') as f:
            f.write(new_html)
        print(f"   ✅ Hero 영상 교체: {hero_id} ({'쇼츠' if is_short else '가로'})")


# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 60)
    print("🫁 MyHear Auto Update v3 — Breathing Mode")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 1. YouTube 갱신
    print("\n1️⃣ YouTube 인기 영상 갱신")
    try:
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        channel_id = get_channel_id(youtube, CHANNEL_HANDLE)
        if channel_id:
            videos = get_popular_videos(youtube, channel_id, days=30, max_results=40)
            videos_by_id = {v['id']: v for v in videos}
            if videos:
                update_youtube_section(videos, videos_by_id)
    except Exception as e:
        print(f"   ⚠️ YouTube 갱신 실패 (스킵): {e}")

    # 2. 블로그 자동 작성
    print("\n2️⃣ 블로그 자동 작성")
    new_post = generate_blog_post()

    # 3. 메인에 최근 블로그 섹션 갱신
    print("\n3️⃣ 메인 페이지에 최근 블로그 주입")
    history = load_blog_history()
    update_main_with_recent_blog(history.get("posts", []))

    # 4. SEO 기본 파일 생성
    print("\n4️⃣ SEO 파일 생성")
    generate_sitemap()
    generate_robots()

    print("\n" + "=" * 60)
    print("✨ MyHear가 스스로 한 번 숨을 쉬었습니다.")
    if new_post:
        print(f"📝 오늘의 글: {new_post['title']}")
    print("=" * 60)


if __name__ == '__main__':
    main()
