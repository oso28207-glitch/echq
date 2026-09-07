import requests
from bs4 import BeautifulSoup
import json
import re
import sys
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
    """جلب حلقات المسلسل (جميعها أو عينة)"""
    try:
        resp = requests.get(series_url, timeout=30, headers={'User-Agent': USER_AGENT})
        resp.raise_for_status()
    except Exception as e:
        print(f"❌ فشل جلب حلقات المسلسل: {e}")
        return []

    soup = BeautifulSoup(resp.text, 'html.parser')
    episodes = []
    ep_boxes = soup.find_all('a', class_='EPNumber_box')
    for ep in ep_boxes[:5]:  # أول 5 حلقات فقط للاختبار
        href = ep.get('href')
        num_span = ep.find('span')
        if href and num_span:
            num = num_span.text.strip()
            if not href.startswith('http'):
                href = urljoin(BASE_URL, href)
            episodes.append({'number': num, 'url': href})
    return episodes

def extract_links_from_page(page_url):
    """محاولة استخراج أي رابط مشغل من الصفحة بطرق متعددة"""
    try:
        resp = requests.get(page_url, timeout=30, headers={'User-Agent': USER_AGENT})
        resp.raise_for_status()
    except Exception as e:
        print(f"❌ فشل جلب الصفحة: {e}")
        return None

    html = resp.text
    soup = BeautifulSoup(html, 'html.parser')

    # 1. البحث عن iframe
    iframe = soup.find('iframe', src=True)
    if iframe:
        src = iframe['src']
        if not src.startswith('http'):
            src = urljoin(BASE_URL, src)
        return src

    # 2. البحث عن روابط camalk.net في أي عنصر
    for tag in soup.find_all(['a', 'form', 'div', 'script']):
        if tag.name == 'script' and tag.string:
            # البحث داخل كود JavaScript
            content = tag.string
            matches = re.findall(r'(https?://camalk\.net/[^\s"\']+)', content)
            if matches:
                return matches[0]
            # البحث عن روابط embed
            matches = re.findall(r'(https?://k\.3chk\.net/embed/[^\s"\']+)', content)
            if matches:
                return matches[0]
        else:
            # البحث في النص أو السمات
            text = str(tag)
            matches = re.findall(r'(https?://camalk\.net/[^\s"\']+)', text)
            if matches:
                return matches[0]
            matches = re.findall(r'(https?://k\.3chk\.net/embed/[^\s"\']+)', text)
            if matches:
                return matches[0]

    # 3. البحث العام عن أي رابط يحتوي على 'embed' أو 'camalk'
    all_links = re.findall(r'(https?://[^\s"\']+embed[^\s"\']*)', html)
    if all_links:
        return all_links[0]
    all_links = re.findall(r'(https?://camalk\.net[^\s"\']+)', html)
    if all_links:
        return all_links[0]

    return None

def follow_camalk(camalk_url):
    """متابعة رابط camalk.net لاستخراج iframe النهائي"""
    try:
        # جلب صفحة camalk.net
        resp = requests.get(camalk_url, timeout=30, headers={'User-Agent': USER_AGENT})
        resp.raise_for_status()
        html = resp.text
        soup = BeautifulSoup(html, 'html.parser')

        # البحث عن iframe داخل صفحة camalk.net
        iframe = soup.find('iframe', src=True)
        if iframe:
            src = iframe['src']
            if not src.startswith('http'):
                src = urljoin(camalk_url, src)
            return src

        # البحث عن نموذج (form) وإرساله لمتابعة إعادة التوجيه
        form = soup.find('form', action=True)
        if form:
            action = form['action']
            inputs = form.find_all('input')
            data = {inp.get('name'): inp.get('value', '') for inp in inputs if inp.get('name')}
            if not action.startswith('http'):
                action = urljoin(camalk_url, action)
            # إرسال النموذج ومتابعة إعادة التوجيه
            resp2 = requests.post(action, data=data, allow_redirects=True, timeout=30)
            # البحث عن iframe في الصفحة النهائية
            soup2 = BeautifulSoup(resp2.text, 'html.parser')
            iframe2 = soup2.find('iframe', src=True)
            if iframe2:
                return iframe2['src']
            # البحث عن روابط فيديو مباشرة
            video = soup2.find('video', src=True)
            if video:
                return video['src']
        return None
    except Exception as e:
        print(f"⚠️ خطأ في متابعة camalk: {e}")
        return None

def main():
    print("🔄 جاري جلب المسلسلات المدبلجة...")
    series_list = get_dubbed_series(page=1)
    if not series_list:
        print("❌ لم يتم العثور على مسلسلات.")
        sys.exit(1)

    results = {}
    for idx, series in enumerate(series_list[:3], 1):
        print(f"📺 {idx}. {series['name']}")
        episodes = get_episodes(series['url'])
        if not episodes:
            continue
        for ep in episodes:
            print(f"   ↳ الحلقة {ep['number']}: جاري البحث عن الرابط...")
            link = extract_links_from_page(ep['url'])
            if link:
                print(f"      ✅ تم العثور على: {link}")
                # إذا كان الرابط من camalk.net، نتابعه
                if 'camalk.net' in link:
                    print(f"      ↳ متابعة camalk.net...")
                    final_link = follow_camalk(link)
                    if final_link:
                        link = final_link
                        print(f"      ✅ الرابط النهائي: {link}")
                results[f"{series['name']} - حلقة {ep['number']}"] = link
            else:
                print(f"      ❌ لم يتم العثور على رابط")

    # حفظ النتائج
    with open('servers.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n📁 تم حفظ النتائج في servers.json")
    print(f"عدد الروابط المستخرجة: {len(results)}")

if __name__ == '__main__':
    main()
