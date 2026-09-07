import requests
from bs4 import BeautifulSoup
import json
import re
import sys
from urllib.parse import urljoin

BASE_URL = "https://k.3chk.net"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def get_dubbed_series(page=1):
    """جلب قائمة المسلسلات المدبلجة من صفحة البحث"""
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
    """جلب حلقات مسلسل معين (أول 5 حلقات فقط للاختبار)"""
    try:
        resp = requests.get(series_url, timeout=30, headers={'User-Agent': USER_AGENT})
        resp.raise_for_status()
    except Exception as e:
        print(f"❌ فشل جلب حلقات المسلسل: {e}")
        return []

    soup = BeautifulSoup(resp.text, 'html.parser')
    episodes = []
    ep_boxes = soup.find_all('a', class_='EPNumber_box')
    for ep in ep_boxes[:5]:  # نأخذ أول 5 حلقات فقط لتسريع العملية
        href = ep.get('href')
        num_span = ep.find('span')
        if href and num_span:
            num = num_span.text.strip()
            if not href.startswith('http'):
                href = urljoin(BASE_URL, href)
            episodes.append({'number': num, 'url': href})
    return episodes

def extract_iframe_from_episode(episode_url):
    """استخراج رابط iframe من صفحة الحلقة"""
    try:
        resp = requests.get(episode_url, timeout=30, headers={'User-Agent': USER_AGENT})
        resp.raise_for_status()
    except Exception as e:
        print(f"❌ فشل جلب صفحة الحلقة: {e}")
        return None

    soup = BeautifulSoup(resp.text, 'html.parser')
    iframe = soup.find('iframe', src=True)
    if iframe:
        src = iframe['src']
        if not src.startswith('http'):
            src = urljoin(BASE_URL, src)
        return src
    return None

def main():
    print("🔄 جاري جلب المسلسلات المدبلجة...")
    series_list = get_dubbed_series(page=1)
    if not series_list:
        print("❌ لم يتم العثور على مسلسلات.")
        sys.exit(1)

    results = {}
    for idx, series in enumerate(series_list[:3], 1):  # نأخذ أول 3 مسلسلات فقط للاختبار
        print(f"📺 {idx}. {series['name']}")
        episodes = get_episodes(series['url'])
        if not episodes:
            continue
        for ep in episodes:
            print(f"   ↳ الحلقة {ep['number']}: جاري استخراج iframe...")
            iframe = extract_iframe_from_episode(ep['url'])
            if iframe:
                results[f"{series['name']} - حلقة {ep['number']}"] = iframe
                print(f"      ✅ iframe: {iframe}")
            else:
                print(f"      ❌ لم يتم العثور على iframe")

    # حفظ النتائج في ملف JSON
    with open('servers.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("\n📁 تم حفظ النتائج في servers.json")
    print(f"عدد الروابط المستخرجة: {len(results)}")

if __name__ == '__main__':
    main()
