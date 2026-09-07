import yt_dlp
import json
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin

BASE_URL = "https://k.3chk.net"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def get_dubbed_series(page=1):
    """جلب قائمة المسلسلات المدبلجة"""
    url = f"{BASE_URL}/search/%D9%85%D8%AF%D8%A8%D9%84%D8%AC/page/{page}/"
    try:
        resp = requests.get(url, timeout=30, headers={'User-Agent': USER_AGENT})
        resp.raise_for_status()
    except Exception as e:
        print(f"❌ فشل جلب المسلسلات: {e}")
        return []

    soup = BeautifulSoup(resp.text, 'html.parser')
    series_list = []
    blocks = soup.find_all('div', class_='EpisodeBlock')
    for block in blocks:
        link = block.find('a', href=True)
        if not link:
            continue
        title_tag = block.find(['h2', 'h3', 'div'], class_=re.compile(r'title|EpisodeBlockTitle'))
        if title_tag:
            name = title_tag.text.strip()
            url = link['href']
            if not url.startswith('http'):
                url = urljoin(BASE_URL, url)
            series_list.append({'name': name, 'url': url})
    return series_list

def get_episodes(series_url):
    """جلب حلقات المسلسل"""
    try:
        resp = requests.get(series_url, timeout=30, headers={'User-Agent': USER_AGENT})
        resp.raise_for_status()
    except Exception as e:
        print(f"❌ فشل جلب حلقات المسلسل: {e}")
        return []

    soup = BeautifulSoup(resp.text, 'html.parser')
    episodes = []
    ep_boxes = soup.find_all('a', class_='EPNumber_box')
    for ep in ep_boxes[:5]:  # أول 5 حلقات فقط
        href = ep.get('href')
        num_span = ep.find('span')
        if href and num_span:
            num = num_span.text.strip()
            if not href.startswith('http'):
                href = urljoin(BASE_URL, href)
            episodes.append({'number': num, 'url': href})
    return episodes

def extract_video_url_with_ytdlp(episode_url):
    """استخدام yt-dlp لاستخراج رابط الفيديو المباشر"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'format': 'best',
        'extract_flat': True,
        'user_agent': USER_AGENT,
        'ignoreerrors': True,
        'allow_unplayable_formats': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(episode_url, download=False)
            if not info:
                return None
            # استخراج الرابط المباشر
            video_url = info.get('url')
            if video_url:
                return video_url
            # محاولة من التنسيقات
            formats = info.get('formats', [])
            if formats:
                best = max(formats, key=lambda x: x.get('height', 0) or 0)
                return best.get('url')
            # محاولة من الإدخالات (للتشغيل)
            entries = info.get('entries', [])
            if entries:
                entry = entries[0]
                video_url = entry.get('url')
                if video_url:
                    return video_url
                formats = entry.get('formats', [])
                if formats:
                    best = max(formats, key=lambda x: x.get('height', 0) or 0)
                    return best.get('url')
            return None
    except Exception as e:
        print(f"⚠️ yt-dlp error: {e}")
        return None

def main():
    print("🔄 جاري جلب المسلسلات المدبلجة...")
    series_list = get_dubbed_series(page=1)
    if not series_list:
        print("❌ لم يتم العثور على مسلسلات.")
        return

    results = {}
    for idx, series in enumerate(series_list[:3], 1):
        print(f"📺 {idx}. {series['name']}")
        episodes = get_episodes(series['url'])
        if not episodes:
            continue
        for ep in episodes:
            print(f"   ↳ الحلقة {ep['number']}: جاري استخراج الرابط باستخدام yt-dlp...")
            video_url = extract_video_url_with_ytdlp(ep['url'])
            if video_url:
                print(f"      ✅ الرابط: {video_url}")
                results[f"{series['name']} - حلقة {ep['number']}"] = video_url
            else:
                print(f"      ❌ لم يتم العثور على رابط")

    with open('servers.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n📁 تم حفظ النتائج في servers.json")
    print(f"عدد الروابط المستخرجة: {len(results)}")

if __name__ == '__main__':
    main()
