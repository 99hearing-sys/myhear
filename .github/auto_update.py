#!/usr/bin/env python3
"""
MyHear Auto Update v2 - Full Autonomous Mode
매일 자동 실행 - 진짜 자율 사이트
- Hero 영상 포맷 자동 감지 (쇼츠=세로, 가로=가로)
- 재생목록 실제 YouTube 동기화
- 헤드라인/통계/배지 AI 자율 생성
"""

import os
import re
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path

try:
    from googleapiclient.discovery import build
    from anthropic import Anthropic
except ImportError as e:
    print(f"❌ 라이브러리 import 실패: {e}")
    sys.exit(1)

CHANNEL_HANDLE = "@hearing_device_editor"
HTML_FILE = "index.html"

YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')

if not YOUTUBE_API_KEY:
    print("❌ YOUTUBE_API_KEY 환경변수 없음")
    sys.exit(1)


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
    """쇼츠 판별 - 여러 신호 종합"""
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
            print("⚠️ 최근 30일 영상 없음 - 전체 인기 영상")
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
                'id': item['id'],
                'title': title,
                'description': description,
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


def get_channel_playlists(youtube, channel_id, max_results=10):
    try:
        request = youtube.playlists().list(
            part="snippet,contentDetails", channelId=channel_id, maxResults=max_results
        )
        response = request.execute()
        playlists = []
        for item in response.get('items', []):
            playlists.append({
                'id': item['id'],
                'title': item['snippet']['title'],
                'description': item['snippet'].get('description', '')[:200],
                'video_count': item['contentDetails']['itemCount']
            })
        playlists.sort(key=lambda x: x['video_count'], reverse=True)
        return playlists
    except Exception as e:
        print(f"⚠️ 재생목록 조회 실패: {e}")
        return []


def curate_with_claude(all_videos, playlists):
    if not ANTHROPIC_API_KEY or not all_videos:
        return fallback_curation(all_videos, playlists)
    try:
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        video_list = [{'id': v['id'], 'title': v['title'], 'views': v['views'],
                       'likes': v['likes'], 'is_short': v['is_short'],
                       'published': v['published'][:10]} for v in all_videos[:30]]
        playlist_list = [{'id': p['id'], 'title': p['title'], 
                          'video_count': p['video_count']} for p in playlists[:6]]
        
        prompt = f"""당신은 MyHear 보청기 사이트의 전속 AI 운영자입니다.

MyHear 철학:
- "거품 없는 보청기 - 합리적 가격, 대량 회전" (코스트코/샤오미 디스럽션 모델)
- 15년 청각학 전공 김진영 대표 직영
- 타겟: 5070 본인 + 3040 자녀
- 전환율 85%

[YouTube 최근 30일 인기 영상 {len(video_list)}개]
{json.dumps(video_list, ensure_ascii=False, indent=1)}

[YouTube 재생목록 {len(playlist_list)}개]
{json.dumps(playlist_list, ensure_ascii=False, indent=1)}

반드시 아래 JSON 형식으로만 답변 (다른 말 없이):
{{
  "hero_video_id": "가장 주목받는 영상 1개 ID (쇼츠/가로 모두 가능)",
  "hero_headline": "Hero 영상 아래 한 줄 카피 (25자 이내, 감정+호기심 자극)",
  "hero_reason": "선정 이유 (20자 내)",
  "longform_videos": ["가로 영상 ID 6개 - is_short=false만"],
  "longform_badges": ["각 영상 2단어 배지 6개"],
  "shorts_videos": ["쇼츠 ID 4개 - is_short=true만"],
  "shorts_badges": ["각 쇼츠 2단어 배지 4개"],
  "playlist_ids": ["재생목록 ID 4개"],
  "playlist_titles_custom": ["각 재생목록 매력적 제목 4개"],
  "playlist_descriptions": ["각 재생목록 2줄 설명 4개"],
  "today_summary": "오늘 변경 1줄 (30자 내)",
  "ai_status_message": "AI 상태 메시지 (35자 내, 활기)"
}}

주의: 의료광고법 위반 표현 금지 (최고·1위·완치)"""

        message = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}]
        )
        response_text = message.content[0].text.strip()
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            return json.loads(json_match.group())
        return fallback_curation(all_videos, playlists)
    except Exception as e:
        print(f"⚠️ Claude 에러: {e}")
        return fallback_curation(all_videos, playlists)


def fallback_curation(all_videos, playlists):
    longform = [v for v in all_videos if not v['is_short']]
    shorts = [v for v in all_videos if v['is_short']]
    hero_id = all_videos[0]['id'] if all_videos else ''
    return {
        'hero_video_id': hero_id,
        'hero_headline': '구독자가 가장 많이 본 영상',
        'hero_reason': '조회수 1위',
        'longform_videos': [v['id'] for v in longform[:6]],
        'longform_badges': ['🔥 최다 조회', '📺 인기', '💡 교육', '🎯 가이드', '💙 후기', '📊 비교'],
        'shorts_videos': [v['id'] for v in shorts[:4]],
        'shorts_badges': ['⚡ Shorts', '⚡ 꿀팁', '⚡ 핫', '⚡ 신규'],
        'playlist_ids': [p['id'] for p in playlists[:4]],
        'playlist_titles_custom': [p['title'] for p in playlists[:4]],
        'playlist_descriptions': [f"영상 {p['video_count']}편 수록" for p in playlists[:4]],
        'today_summary': f'자동 업데이트 {datetime.now().strftime("%Y-%m-%d")}',
        'ai_status_message': 'AI가 사장님 없이 스스로 관리합니다'
    }


def update_html(curation, videos_by_id, playlists_by_id):
    if not Path(HTML_FILE).exists():
        print(f"❌ {HTML_FILE} 파일 없음")
        return False
    
    with open(HTML_FILE, 'r', encoding='utf-8') as f:
        html = f.read()
    
    changes = 0
    
    # 1. HERO 영상 - 포맷 자동 감지
    hero_id = curation.get('hero_video_id')
    hero_headline = curation.get('hero_headline', '')
    
    if hero_id:
        hero_video = videos_by_id.get(hero_id)
        is_short = hero_video.get('is_short', False) if hero_video else False
        
        hero_pattern = r'(class="video-hero-wrap"[^>]*>[\s\S]*?<iframe src="https://www\.youtube\.com/embed/)([a-zA-Z0-9_-]+)(")'
        new_html, count = re.subn(hero_pattern, rf'\g<1>{hero_id}\g<3>', html, count=1)
        if count > 0:
            html = new_html
            changes += 1
            print(f"✅ Hero 영상 교체: {hero_id} (포맷: {'쇼츠' if is_short else '가로'})")
        
        # Hero Wrap 스타일 업데이트
        if is_short:
            hero_wrap_pattern = r'<div class="video-hero-wrap"[^>]*>'
            html = re.sub(
                hero_wrap_pattern,
                '<div class="video-hero-wrap" style="max-width:380px;margin:0 auto;aspect-ratio:9/16;border-radius:24px;overflow:hidden;background:#000;position:relative;">',
                html, count=1
            )
        else:
            hero_wrap_pattern = r'<div class="video-hero-wrap"[^>]*>'
            html = re.sub(
                hero_wrap_pattern,
                '<div class="video-hero-wrap" style="max-width:900px;margin:0 auto;aspect-ratio:16/9;border-radius:24px;overflow:hidden;background:#000;position:relative;">',
                html, count=1
            )
        
        if hero_headline:
            hero_caption_pattern = r'(<p class="video-hero-caption"[^>]*>)([^<]+)(</p>)'
            html = re.sub(hero_caption_pattern, rf'\g<1>▶ {hero_headline}\g<3>', html, count=1)
    
    # 2. 가로 영상 6개
    longform_ids = curation.get('longform_videos', [])[:6]
    longform_badges = curation.get('longform_badges', [])
    
    if longform_ids:
        longform_match = re.search(
            r'(<div class="video-grid" id="longform-videos">)([\s\S]*?)(</div>\s*</div>\s*<!-- ============)',
            html
        )
        if longform_match:
            new_cards = build_longform_cards(longform_ids, longform_badges, videos_by_id)
            new_section = longform_match.group(1) + '\n' + new_cards + '\n      ' + longform_match.group(3)
            html = html.replace(longform_match.group(0), new_section)
            changes += len(longform_ids)
            print(f"✅ 가로 영상 {len(longform_ids)}개 교체")
    
    # 3. 쇼츠 4개
    shorts_ids = curation.get('shorts_videos', [])[:4]
    shorts_badges = curation.get('shorts_badges', [])
    
    if shorts_ids:
        shorts_match = re.search(
            r'(<div class="video-grid" id="shorts-videos"[^>]*>)([\s\S]*?)(</div>\s*<p style=)',
            html
        )
        if shorts_match:
            new_cards = build_shorts_cards(shorts_ids, shorts_badges, videos_by_id)
            new_section = shorts_match.group(1) + '\n' + new_cards + '\n      ' + shorts_match.group(3)
            html = html.replace(shorts_match.group(0), new_section)
            changes += len(shorts_ids)
            print(f"✅ 쇼츠 {len(shorts_ids)}개 교체")
    
    # 4. 재생목록 동기화
    playlist_ids = curation.get('playlist_ids', [])[:4]
    playlist_titles = curation.get('playlist_titles_custom', [])
    playlist_descs = curation.get('playlist_descriptions', [])
    
    if playlist_ids:
        playlists_match = re.search(
            r'(<div style="display:grid;grid-template-columns:repeat\(2,1fr\);gap:18px;" id="playlists-grid">)([\s\S]*?)(</div>\s*</div>\s*\n\s*<!-- AI 자동 업데이트 배지 -->)',
            html
        )
        if playlists_match:
            new_cards = build_playlist_cards(playlist_ids, playlist_titles, playlist_descs, playlists_by_id)
            new_section = playlists_match.group(1) + '\n' + new_cards + '\n      ' + playlists_match.group(3)
            html = html.replace(playlists_match.group(0), new_section)
            changes += len(playlist_ids)
            print(f"✅ 재생목록 {len(playlist_ids)}개 동기화")
    
    # 5. AI 상태 & 타임스탬프
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    ai_status = curation.get('ai_status_message', 'AI가 자율 관리 중')
    today_summary = curation.get('today_summary', '')
    
    ai_pattern = r'(<strong>AI 자동 관리 중</strong>[^<]*)'
    new_ai_text = f'<strong>AI 자동 관리 중</strong> · {ai_status} · {timestamp}'
    html = re.sub(ai_pattern, new_ai_text, html, count=1)
    
    if changes > 0:
        with open(HTML_FILE, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"\n✅ 총 {changes}개 요소 업데이트")
        print(f"💬 오늘: {today_summary}")
        return True
    else:
        print("ℹ️ 변경사항 없음")
        return False


def build_longform_cards(ids, badges, videos_by_id):
    default_badges = ['🔥 최다 조회', '📺 인기', '💡 교육', '🎯 가이드', '💙 후기', '📊 비교']
    cards = []
    for i, vid_id in enumerate(ids):
        v = videos_by_id.get(vid_id, {})
        title = v.get('title', '영상')[:60]
        badge = badges[i] if i < len(badges) else default_badges[i % 6]
        card = f'''        <a href="https://www.youtube.com/watch?v={vid_id}" target="_blank" rel="noopener" class="video-card fade-up">
          <div class="video-thumb-wrap" style="aspect-ratio:16/9;background:#000;"><iframe src="https://www.youtube.com/embed/{vid_id}" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe></div>
          <div class="video-meta"><span class="video-badge">{badge}</span><div class="video-title">{title}</div></div>
        </a>'''
        cards.append(card)
    return '\n'.join(cards)


def build_shorts_cards(ids, badges, videos_by_id):
    default_badges = ['⚡ Shorts', '⚡ 꿀팁', '⚡ 핫', '⚡ 신규']
    cards = []
    for i, vid_id in enumerate(ids):
        v = videos_by_id.get(vid_id, {})
        title = v.get('title', '쇼츠')[:50]
        badge = badges[i] if i < len(badges) else default_badges[i % 4]
        card = f'''        <a href="https://www.youtube.com/shorts/{vid_id}" target="_blank" rel="noopener" class="video-card fade-up" style="aspect-ratio:9/16;">
          <div style="position:relative;width:100%;padding-bottom:177.78%;background:#000;">
            <iframe src="https://www.youtube.com/embed/{vid_id}" style="position:absolute;top:0;left:0;width:100%;height:100%;border:none;" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
          </div>
          <div class="video-meta"><span class="video-badge">{badge}</span><div class="video-title">{title}</div></div>
        </a>'''
        cards.append(card)
    return '\n'.join(cards)


def build_playlist_cards(ids, titles, descs, playlists_by_id):
    emojis = ['🎯', '🔬', '💰', '🛡']
    cards = []
    for i, pl_id in enumerate(ids):
        pl = playlists_by_id.get(pl_id, {})
        title = titles[i] if i < len(titles) else pl.get('title', '재생목록')
        desc = descs[i] if i < len(descs) else f"영상 {pl.get('video_count', 0)}편 수록"
        emoji = emojis[i % 4]
        video_count = pl.get('video_count', 0)
        
        if i == 0:
            style = 'padding:32px;text-decoration:none;color:inherit;background:linear-gradient(135deg,#000,#1a1a1a);color:#fff;'
            desc_color = '#b4b4b4'
            cta_color = '#fff'
            label_color = '#9a9a9a'
        else:
            style = 'padding:32px;text-decoration:none;color:inherit;'
            desc_color = '#4a4a4a'
            cta_color = '#000'
            label_color = '#8a8a8a'
        title_color = '#fff' if i == 0 else '#000'
        
        card = f'''        <a href="https://www.youtube.com/playlist?list={pl_id}" target="_blank" rel="noopener" class="video-card fade-up" style="{style}">
          <div style="font-size:36px;margin-bottom:16px;">{emoji}</div>
          <div style="font-size:11px;color:{label_color};font-weight:600;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:10px;">PLAYLIST · {video_count}편</div>
          <h4 style="font-size:20px;font-weight:700;margin-bottom:10px;color:{title_color};">{title}</h4>
          <p style="font-size:13px;color:{desc_color};line-height:1.6;">{desc}</p>
          <div style="margin-top:20px;font-size:12px;color:{cta_color};font-weight:600;">재생목록 보기 →</div>
        </a>'''
        cards.append(card)
    return '\n'.join(cards)


def main():
    print("🚀 MyHear Auto Update v2 - 자율 운영 모드")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    
    print(f"\n1️⃣ 채널 조회: {CHANNEL_HANDLE}")
    channel_id = get_channel_id(youtube, CHANNEL_HANDLE)
    if not channel_id:
        print("❌ 채널 찾기 실패")
        sys.exit(1)
    print(f"   ✅ Channel ID: {channel_id}")
    
    print(f"\n2️⃣ 인기 영상 조회")
    videos = get_popular_videos(youtube, channel_id, days=30, max_results=40)
    print(f"   ✅ {len(videos)}개")
    if videos:
        shorts_count = sum(1 for v in videos if v['is_short'])
        longform_count = len(videos) - shorts_count
        print(f"   📺 가로: {longform_count} / ⚡ 쇼츠: {shorts_count}")
        print(f"   🔥 TOP: {videos[0]['title'][:40]} ({videos[0]['views']:,}회, {'쇼츠' if videos[0]['is_short'] else '가로'})")
    
    videos_by_id = {v['id']: v for v in videos}
    
    print(f"\n3️⃣ 재생목록 조회")
    playlists = get_channel_playlists(youtube, channel_id)
    print(f"   ✅ {len(playlists)}개")
    playlists_by_id = {p['id']: p for p in playlists}
    
    print(f"\n4️⃣ Claude 자율 큐레이션")
    curation = curate_with_claude(videos, playlists)
    hero_v = videos_by_id.get(curation.get('hero_video_id', ''), {})
    print(f"   🎯 Hero: {curation.get('hero_video_id')} ({'쇼츠' if hero_v.get('is_short') else '가로'})")
    print(f"   📝 {curation.get('hero_headline', '')}")
    print(f"   💬 {curation.get('today_summary', '')}")
    
    print(f"\n5️⃣ HTML 자율 업데이트")
    updated = update_html(curation, videos_by_id, playlists_by_id)
    
    if updated:
        print("\n✨ MyHear가 스스로 진화했습니다.")
    else:
        print("\nℹ️ 이미 최적 상태")


if __name__ == '__main__':
    main()
