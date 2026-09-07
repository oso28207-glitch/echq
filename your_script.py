import requests
from bs4 import BeautifulSoup

def extract_video_url(episode_url):
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})

    # 1. جلب صفحة الحلقة
    resp = session.get(episode_url)
    soup = BeautifulSoup(resp.text, 'html.parser')

    # 2. استخراج الرابط المشفر (camalk.net)
    form = soup.find('form', action=lambda x: x and 'camalk.net' in x)
    if not form:
        return None

    action = form.get('action')
    data = {inp.get('name'): inp.get('value') for inp in form.find_all('input') if inp.get('name')}

    # 3. إرسال الطلب إلى camalk.net
    resp2 = session.post(action, data=data, allow_redirects=True)

    # 4. استخراج iframe من صفحة camalk.net
    soup2 = BeautifulSoup(resp2.text, 'html.parser')
    iframe = soup2.find('iframe', src=True)
    if not iframe:
        return None

    # 5. جلب صفحة iframe (غالباً miraved.com)
    iframe_url = iframe.get('src')
    resp3 = session.get(iframe_url)

    # 6. استخراج رابط الفيديو النهائي (قد يكون داخل <video> أو script)
    soup3 = BeautifulSoup(resp3.text, 'html.parser')
    video = soup3.find('video', src=True)
    if video:
        return video.get('src')

    # محاولة البحث داخل script
    for script in soup3.find_all('script'):
        if script.string and '.m3u8' in script.string:
            import re
            match = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', script.string)
            if match:
                return match.group(1)

    return None

# مثال للاستخدام
url = "https://k.3chk.net/video/ep/mslsl-ask-ve-mavi-mudblij-season-1-episode-4/"
video_link = extract_video_url(url)
print(video_link)
