import os
import subprocess
import shutil
import logging
import yt_dlp
from pathlib import Path

logger = logging.getLogger(__name__)

DOWNLOAD_DIR = Path("downloads")
PROCESSED_DIR = Path("processed")

# إنشاء المجلدات إذا لم تكن موجودة
DOWNLOAD_DIR.mkdir(exist_ok=True)
PROCESSED_DIR.mkdir(exist_ok=True)

def download_video(url, progress_callback=None):
    """
    تحميل الفيديو باستخدام yt-dlp
    تعيد مسار الملف المحمل
    """
    output_template = str(DOWNLOAD_DIR / "%(title)s.%(ext)s")
    
    ydl_opts = {
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'progress_hooks': [lambda d: _progress_hook(d, progress_callback)] if progress_callback else [],
        'format': 'best[height<=720]',  # تفضيل جودة منخفضة لتسريع التحميل
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            # التحقق من وجود الملف
            if not os.path.exists(filename):
                # قد يكون الامتداد مختلفاً
                for ext in ['.mp4', '.mkv', '.webm']:
                    test_file = filename.rsplit('.', 1)[0] + ext
                    if os.path.exists(test_file):
                        filename = test_file
                        break
            
            if os.path.exists(filename):
                logger.info(f"تم تحميل الفيديو: {filename}")
                return filename
            else:
                logger.error("لم يتم العثور على الملف المحمل")
                return None
                
    except Exception as e:
        logger.error(f"خطأ في تحميل الفيديو: {e}")
        return None

def _progress_hook(d, callback):
    """دالة لتتبع تقدم التحميل"""
    if d['status'] == 'downloading':
        if 'total_bytes' in d:
            percent = int((d['downloaded_bytes'] / d['total_bytes']) * 100)
            if callback:
                callback(percent, f"تحميل... {percent}%")
    elif d['status'] == 'finished':
        if callback:
            callback(100, "اكتمل التحميل، جارٍ الضغط...")

def compress_video(input_path, progress_callback=None):
    """
    ضغط الفيديو إلى دقة 144p باستخدام ffmpeg
    تعيد مسار الفيديو المضغوط
    """
    output_filename = Path(input_path).stem + "_144p.mp4"
    output_path = PROCESSED_DIR / output_filename
    
    # أمر ffmpeg للضغط
    cmd = [
        'ffmpeg',
        '-i', input_path,
        '-vf', 'scale=-1:144',      # تغيير الحجم إلى ارتفاع 144 بكسل مع الحفاظ على النسبة
        '-c:v', 'libx264',           # ترميز الفيديو
        '-preset', 'ultrafast',      # تسريع الضغط
        '-crf', '28',                # جودة مقبولة مع حجم صغير
        '-c:a', 'aac',               # ترميز الصوت
        '-b:a', '16k',               # معدل بت منخفض للصوت
        '-movflags', '+faststart',   # تحسين البث
        '-y',                        # استبدال الملف إذا وجد
        str(output_path)
    ]
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # قراءة مخرجات ffmpeg لتحديد التقدم (صعب جداً مع ffmpeg، نستخدم تقدير تقريبي)
        # نعطي تقدم وهمي لأن ffmpeg لا يوفر نسبة مئوية مباشرة
        if progress_callback:
            progress_callback(20, "بدء الضغط...")
            progress_callback(50, "جارٍ الضغط... من فضلك انتظر")
            progress_callback(80, "الضغط يقترب من الانتهاء...")
        
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            logger.error(f"خطأ في ffmpeg: {stderr}")
            return None
        
        if os.path.exists(output_path):
            if progress_callback:
                progress_callback(100, "اكتمل الضغط!")
            return str(output_path)
        else:
            logger.error("لم يتم إنشاء ملف الفيديو المضغوط")
            return None
            
    except Exception as e:
        logger.error(f"خطأ في تنفيذ ffmpeg: {e}")
        return None

def process_video(video_url, progress_callback=None):
    """
    الوظيفة الرئيسية: تحميل الفيديو ثم ضغطه
    تعيد مسار الفيديو النهائي
    """
    if progress_callback:
        progress_callback(0, "بدء العملية...")
    
    # 1. تحميل الفيديو
    if progress_callback:
        progress_callback(5, "جارٍ تحميل الفيديو...")
    
    downloaded_path = download_video(video_url, progress_callback)
    if not downloaded_path:
        if progress_callback:
            progress_callback(0, "فشل التحميل!")
        return None
    
    if progress_callback:
        progress_callback(40, "اكتمل التحميل، جارٍ الضغط...")
    
    # 2. ضغط الفيديو
    compressed_path = compress_video(downloaded_path, progress_callback)
    
    # 3. حذف الملف الأصلي لتوفير المساحة (اختياري)
    try:
        os.remove(downloaded_path)
    except:
        pass
    
    if compressed_path:
        if progress_callback:
            progress_callback(100, "اكتمل! يمكنك مشاهدة الفيديو.")
        return compressed_path
    else:
        if progress_callback:
            progress_callback(0, "فشل الضغط!")
        return None

def delete_old_files(max_age_hours=24):
    """
    حذف الملفات القديمة لتوفير المساحة
    """
    import time
    now = time.time()
    for folder in [DOWNLOAD_DIR, PROCESSED_DIR]:
        for file in folder.iterdir():
            if file.is_file():
                age = now - file.stat().st_mtime
                if age > max_age_hours * 3600:
                    try:
                        file.unlink()
                        logger.info(f"تم حذف الملف القديم: {file.name}")
                    except:
                        pass
