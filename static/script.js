let currentPage = 1;
let isLoading = false;

document.addEventListener('DOMContentLoaded', function() {
    // تفعيل بطاقات المسلسلات
    document.querySelectorAll('.series-card').forEach(card => {
        card.addEventListener('click', function() {
            const url = this.dataset.url;
            const name = this.dataset.name;
            showEpisodes(url, name);
        });
    });

    // زر تحميل المزيد
    document.getElementById('load-more').addEventListener('click', loadMoreSeries);

    // النوافذ المنبثقة
    window.episodesModal = new bootstrap.Modal(document.getElementById('episodesModal'));
    window.loadingModal = new bootstrap.Modal(document.getElementById('loadingModal'));
});

async function showEpisodes(seriesUrl, seriesName) {
    document.getElementById('episodesModalLabel').textContent = `حلقات: ${seriesName}`;
    document.getElementById('episodes-list').innerHTML = `
        <div class="text-center"><div class="spinner-border text-danger"></div></div>
    `;
    window.episodesModal.show();

    try {
        const response = await fetch(`/api/episodes?url=${encodeURIComponent(seriesUrl)}`);
        const data = await response.json();

        if (!data.episodes || data.episodes.length === 0) {
            document.getElementById('episodes-list').innerHTML = `
                <div class="alert alert-warning">لا توجد حلقات متاحة.</div>
            `;
            return;
        }

        let html = '<div class="d-flex flex-wrap justify-content-center">';
        data.episodes.forEach(ep => {
            html += `
                <div class="episode-item m-1">
                    <button class="btn btn-outline-danger episode-btn" 
                            data-url="${ep.url}"
                            onclick="playEpisode(this)">
                        ${ep.number}
                    </button>
                </div>
            `;
        });
        html += '</div>';
        document.getElementById('episodes-list').innerHTML = html;

    } catch (error) {
        console.error(error);
        document.getElementById('episodes-list').innerHTML = `
            <div class="alert alert-danger">حدث خطأ في تحميل الحلقات.</div>
        `;
    }
}

async function playEpisode(button) {
    const url = button.dataset.url;

    // عرض نافذة التحميل
    document.getElementById('loading-status').textContent = '⏳ جاري استخراج رابط المشاهدة...';
    window.loadingModal.show();
    window.episodesModal.hide();

    try {
        const response = await fetch(`/api/video?url=${encodeURIComponent(url)}`);
        const data = await response.json();

        window.loadingModal.hide();

        if (data.success && data.video_url) {
            // فتح صفحة المشاهدة
            window.location.href = `/watch?url=${encodeURIComponent(url)}`;
        } else {
            alert('❌ لم يتم العثور على رابط الفيديو. حاول مرة أخرى.');
        }

    } catch (error) {
        console.error(error);
        window.loadingModal.hide();
        alert('❌ حدث خطأ في الخادم. حاول مرة أخرى.');
    }
}

async function loadMoreSeries() {
    if (isLoading) return;
    isLoading = true;

    currentPage++;
    const button = document.getElementById('load-more');
    button.textContent = 'جاري التحميل...';
    button.disabled = true;

    try {
        const response = await fetch(`/api/series?page=${currentPage}`);
        const series = await response.json();

        if (series.length === 0) {
            button.textContent = 'لا يوجد المزيد';
            button.disabled = true;
            isLoading = false;
            return;
        }

        const container = document.getElementById('series-list');
        series.forEach(item => {
            const col = document.createElement('div');
            col.className = 'col-6 col-md-3 col-lg-2 mb-3';
            col.innerHTML = `
                <div class="series-card card h-100" data-url="${item.url}" data-name="${item.name}">
                    <div class="card-body text-center">
                        <i class="bi bi-play-circle-fill display-4 text-danger"></i>
                        <h6 class="card-title mt-2">${item.name}</h6>
                        <span class="badge bg-secondary">${item.type}</span>
                    </div>
                </div>
            `;
            container.appendChild(col);

            const card = col.querySelector('.series-card');
            card.addEventListener('click', function() {
                showEpisodes(this.dataset.url, this.dataset.name);
            });
        });

        button.textContent = 'تحميل المزيد';
        button.disabled = false;
        isLoading = false;

    } catch (error) {
        console.error(error);
        button.textContent = 'حدث خطأ، حاول مرة أخرى';
        button.disabled = false;
        isLoading = false;
    }
}
