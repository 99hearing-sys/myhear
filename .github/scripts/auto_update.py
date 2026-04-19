#!/usr/bin/env python3
"""
MyHear Auto Update Script
매일 자동 실행 - YouTube 인기 영상 반영 + Claude AI 판단
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

# ============================================
# 설정
# ============================================
CHANNEL_HANDLE = "@hearing_device_editor"
CHANNEL_ID = None  # 자동으로 찾음
HTML_FILE = "index.html"

YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')

if not YOUTUBE_API_KEY:
    print("❌ YOUTUBE_API_KEY 환경변수 없음")
    sys.exit(1)

if not ANTHROPIC_API_KEY:
    print("⚠️ ANTHROPIC_API_KEY 없음 - Claude 없이 단순 모드로 실행")

# ============================================
# 1. YouTube API - 채널 ID 찾기
# ============================================
def get_channel_id(youtube, handle):
    """채널 핸들로 Channel ID 조회"""
    try:
        handle_clean = handle.lstrip('@')
        
        request = youtube.search().list(
            part="snippet",
            q=handle_clean,
            type="channel",
            maxResults=5
        )
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

# ============================================
# 2. YouTube API - 인기 영상 조회
# ============================================
def get_popular_videos(youtube, channel_id, days=30, max_results=30):
    """최근 N일 인기 영상 조회"""
    try:
        published_after = (datetime.utcnow() - timedelta(days=days)).isoformat() + 'Z'
        
        search_request = youtube.search().list(
            part="id,snippet",
            channelId=channel_id,
            order="viewCount",
            type="video",
            publishedAfter=published_after,
            maxResults=max_results
        )
        search_response = search_request.execute()
        
        video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
        
        if not video_ids:
            print("⚠️ 최근 30일 영상 없음 - 전체 인기 영상으로 대체")
            search_request = youtube.search().list(
                part="id,snippet",
                channelId=channel_id,
                order="viewCount",
                type="video",
                maxResults=max_results
            )
            search_response = search_request.execute()
            video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
        
        if not video_ids:
            return []
        
        videos_request = youtube.videos().list(
            part="snippet,statistics,contentDetails",
            id=','.join(video_ids)
        )
        videos_response = videos_request.execute()
        
        videos = []
        for item in videos_response.get('items', []):
            duration = item['contentDetails']['duration']
            is_short = is_short_video(duration)
            
            videos.append({
                'id': item['id'],
                'title': item['snippet']['title'],
                'description': item['snippet']['description'][:200],
                'published': item['snippet']['publishedAt'],
                'thumbnail': item['snippet']['thumbnails'].get('high', {}).get('url', ''),
                'views': int(item['statistics'].get('viewCount', 0)),
                'likes': int(item['statistics'].get('likeCount', 0)),
                'comments': int(item['statistics'].get('commentCount', 0)),
                'duration': duration,
                'is_short': is_short
            })
        
        videos.sort(key=lambda x: x['views'], reverse=True)
        return videos
    
    except Exception as e:
        print(f"❌ 영상 조회 실패: {e}")
        return []

def is_short_video(duration_str):
    """ISO 8601 duration을 파싱해서 쇼츠 판별 (60초 이하)"""
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
    if not match:
        return False
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    total_seconds = hours * 3600 + minutes * 60 + seconds
    return total_seconds <= 60

# ============================================
# 3. Claude API - 영상 선정 및 판단
# ============================================
def select_videos_with_claude(all_videos):
    """Claude에게 어떤 영상을 사이트에 배치할지 물어봄"""
    if not ANTHROPIC_API_KEY or not all_videos:
        return fallback_selection(all_videos)
    
    try:
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        
        video_list = []
        for v in all_videos[:30]:
            video_list.append({
                'id': v['id'],
                'title': v['title'],
                'views': v['views'],
                'likes': v['likes'],
                'is_short': v['is_short'],
                'published': v['published'][:10]
            })
        
        prompt = f"""당신은 MyHear 보청기 사이트의 AI 큐레이터입니다.

MyHear 철학: "거품 없는 보청기 - 합리적 가격, 대량 회전"
타겟: 5070 본인 (직접 구매) + 3040 자녀

아래는 "보청기에디터" YouTube 채널의 최근 인기 영상 리스트입니다:

{json.dumps(video_list, ensure_ascii=False, indent=2)}

다음 기준으로 영상을 선정해주세요:
1. Hero 영상 1개: 사이트 최상단에 보일 대표 영상 (가로 영상 중 구매 결정에 직결되는 영상)
2. 가로 영상 본편 6개: 다양한 주제로 가격/제품/교육/감정 균형
3. 쇼츠 4개: 빠른 꿀팁 형식

반드시 JSON 형식으로만 답변:
{{
  "hero_video_id": "xxx",
  "hero_reason": "선정 이유 짧게",
  "longform_videos": ["id1", "id2", "id3", "id4", "id5", "id6"],
  "shorts_videos": ["id1", "id2", "id3", "id4"],
  "summary": "오늘의 업데이트 요약 1줄"
}}"""

        message = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response_text = message.content[0].text.strip()
        
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        else:
            print("⚠️ Claude 응답에서 JSON 추출 실패 - fallback 사용")
            return fallback_selection(all_videos)
    
    except Exception as e:
        print(f"⚠️ Claude API 에러: {e} - fallback 사용")
        return fallback_selection(all_videos)

def fallback_selection(all_videos):
    """Claude 없을 때 규칙 기반 선정"""
    longform = [v for v in all_videos if not v['is_short']]
    shorts = [v for v in all_videos if v['is_short']]
    
    hero_id = longform[0]['id'] if longform else (all_videos[0]['id'] if all_videos else '')
    
    return {
        'hero_video_id': hero_id,
        'hero_reason': '조회수 1위 (규칙 기반 선정)',
        'longform_videos': [v['id'] for v in longform[:6]],
        'shorts_videos': [v['id'] for v in shorts[:4]],
        'summary': f'인기 영상 자동 반영 ({datetime.now().strftime("%Y-%m-%d")})'
    }

# ============================================
# 4. HTML 수정
# ============================================
def update_html(selection, videos_by_id):
    """index.html의 YouTube 영상을 선정된 영상으로 교체"""
    if not Path(HTML_FILE).exists():
        print(f"❌ {HTML_FILE} 파일 없음")
        return False
    
    with open(HTML_FILE, 'r', encoding='utf-8') as f:
        html = f.read()
    
    changes = 0
    
    hero_id = selection.get('hero_video_id')
    if hero_id:
        hero_pattern = r'(class="video-hero-wrap"[\s\S]*?<iframe src="https://www\.youtube\.com/embed/)([a-zA-Z0-9_-]+)(")'
        new_html, count = re.subn(hero_pattern, rf'\g<1>{hero_id}\g<3>', html, count=1)
        if count > 0:
            html = new_html
            changes += 1
            print(f"✅ Hero 영상 교체: {hero_id}")
    
    longform_ids = selection.get('longform_videos', [])[:6]
    if longform_ids:
        longform_match = re.search(
            r'(<div class="video-grid" id="longform-videos">)([\s\S]*?)(</div>\s*</div>\s*<!-- ============)',
            html
        )
        if longform_match:
            new_cards = build_longform_cards(longform_ids, videos_by_id)
            new_section = longform_match.group(1) + '\n' + new_cards + '\n      ' + longform_match.group(3)
            html = html.replace(longform_match.group(0), new_section)
            changes += len(longform_ids)
            print(f"✅ 가로 영상 {len(longform_ids)}개 교체")
    
    shorts_ids = selection.get('shorts_videos', [])[:4]
    if shorts_ids:
        shorts_match = re.search(
            r'(<div class="video-grid" id="shorts-videos"[^>]*>)([\s\S]*?)(</div>\s*<p style=)',
            html
        )
        if shorts_match:
            new_cards = build_shorts_cards(shorts_ids, videos_by_id)
            new_section = shorts_match.group(1) + '\n' + new_cards + '\n      ' + shorts_match.group(3)
            html = html.replace(shorts_match.group(0), new_section)
            changes += len(shorts_ids)
            print(f"✅ 쇼츠 {len(shorts_ids)}개 교체")
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    ai_managed_pattern = r'(AI 자동 관리 중</strong> · YouTube 데이터 기반 )([^<]+)(\()'
    html = re.sub(ai_managed_pattern, rf'\g<1>마지막 업데이트: {timestamp} \g<3>', html)
    
    if changes > 0:
        with open(HTML_FILE, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"✅ 총 {changes}개 영상 업데이트 완료")
        return True
    else:
        print("ℹ️ 변경사항 없음")
        return False

def build_longform_cards(ids, videos_by_id):
    """가로 영상 카드 HTML 생성"""
    cards = []
    badges = ['🔥 최다 조회', '📺 인기', '💡 교육', '🎯 가이드', '💙 후기', '📊 비교']
    
    for i, vid_id in enumerate(ids):
        v = videos_by_id.get(vid_id, {})
        title = v.get('title', '영상')[:60]
        badge = badges[i] if i < len(badges) else '📺'
        
        card = f'''        <a href="https://www.youtube.com/watch?v={vid_id}" target="_blank" rel="noopener" class="video-card fade-up">
          <div class="video-thumb-wrap"><iframe src="https://www.youtube.com/embed/{vid_id}" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe></div>
          <div class="video-meta"><span class="video-badge">{badge}</span><div class="video-title">{title}</div></div>
        </a>'''
        cards.append(card)
    
    return '\n'.join(cards)

def build_shorts_cards(ids, videos_by_id):
    """쇼츠 카드 HTML 생성"""
    cards = []
    badges = ['⚡ Shorts', '⚡ 꿀팁', '⚡ 핫', '⚡ 신규']
    
    for i, vid_id in enumerate(ids):
        v = videos_by_id.get(vid_id, {})
        title = v.get('title', '쇼츠')[:50]
        badge = badges[i] if i < len(badges) else '⚡'
        
        card = f'''        <a href="https://www.youtube.com/shorts/{vid_id}" target="_blank" rel="noopener" class="video-card fade-up" style="aspect-ratio:9/16;">
          <div style="position:relative;width:100%;padding-bottom:177.78%;background:#000;">
            <iframe src="https://www.youtube.com/embed/{vid_id}" style="position:absolute;top:0;left:0;width:100%;height:100%;border:none;" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
          </div>
          <div class="video-meta"><span class="video-badge">{badge}</span><div class="video-title">{title}</div></div>
        </a>'''
        cards.append(card)
    
    return '\n'.join(cards)

# ============================================
# 메인 실행
# ============================================
def main():
    print("🚀 MyHear Auto Update 시작")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    
    print(f"\n1️⃣ 채널 ID 조회: {CHANNEL_HANDLE}")
    channel_id = get_channel_id(youtube, CHANNEL_HANDLE)
    if not channel_id:
        print("❌ 채널 ID 찾기 실패")
        sys.exit(1)
    print(f"   ✅ Channel ID: {channel_id}")
    
    print(f"\n2️⃣ 인기 영상 조회 (최근 30일)")
    videos = get_popular_videos(youtube, channel_id, days=30, max_results=30)
    if not videos:
        print("❌ 영상 조회 실패")
        sys.exit(1)
    print(f"   ✅ {len(videos)}개 영상 조회됨")
    print(f"   🔥 최다 조회: {videos[0]['title'][:40]} ({videos[0]['views']:,}회)")
    
    videos_by_id = {v['id']: v for v in videos}
    
    print(f"\n3️⃣ Claude AI로 영상 선정")
    selection = select_videos_with_claude(videos)
    print(f"   ✅ Hero: {selection['hero_video_id']}")
    print(f"   📺 가로: {len(selection.get('longform_videos', []))}개")
    print(f"   ⚡ 쇼츠: {len(selection.get('shorts_videos', []))}개")
    print(f"   💬 {selection.get('summary', '')}")
    
    print(f"\n4️⃣ index.html 업데이트")
    updated = update_html(selection, videos_by_id)
    
    if updated:
        print("\n✨ 자동 업데이트 완료 - 곧 GitHub 커밋 진행")
    else:
        print("\nℹ️ 업데이트할 변경사항 없음")

if __name__ == '__main__':
    main()
