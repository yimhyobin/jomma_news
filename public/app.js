// Firebase 설정 - 프로젝트 생성 후 실제 값으로 교체 필요
const firebaseConfig = {
    apiKey: "YOUR_API_KEY",
    authDomain: "YOUR_PROJECT_ID.firebaseapp.com",
    projectId: "YOUR_PROJECT_ID",
    storageBucket: "YOUR_PROJECT_ID.appspot.com",
    messagingSenderId: "YOUR_SENDER_ID",
    appId: "YOUR_APP_ID"
};

// Firebase 초기화
firebase.initializeApp(firebaseConfig);
const db = firebase.firestore();

// 카테고리 매핑
const categoryNames = {
    realestate: '부동산',
    stock: '주식',
    economy: '경제',
    it: 'IT'
};

// 상태 변수
let currentCategory = 'all';
let newsData = [];

// DOM 요소
const newsContainer = document.getElementById('news-container');
const loadingEl = document.getElementById('loading');
const todayDateEl = document.getElementById('today-date');

// 오늘 날짜 표시
function displayTodayDate() {
    const today = new Date();
    const options = { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' };
    todayDateEl.textContent = today.toLocaleDateString('ko-KR', options);
}

// 뉴스 카드 HTML 생성
function createNewsCard(news) {
    return `
        <article class="news-card" data-category="${news.category}">
            <a href="${news.link}" target="_blank" rel="noopener noreferrer">
                <img
                    class="news-image"
                    src="${news.imageUrl || 'https://via.placeholder.com/400x200?text=No+Image'}"
                    alt="${news.title}"
                    loading="lazy"
                    onerror="this.src='https://via.placeholder.com/400x200?text=No+Image'"
                >
                <div class="news-content">
                    <span class="news-category ${news.category}">
                        ${categoryNames[news.category] || news.category}
                    </span>
                    <h2 class="news-title">${news.title}</h2>
                    <p class="news-summary">${news.summary}</p>
                    <div class="news-meta">
                        <span class="news-source">${news.source || '네이버 뉴스'}</span>
                        <span class="read-more">자세히 보기</span>
                    </div>
                </div>
            </a>
        </article>
    `;
}

// 뉴스 렌더링
function renderNews(category = 'all') {
    const filteredNews = category === 'all'
        ? newsData
        : newsData.filter(news => news.category === category);

    if (filteredNews.length === 0) {
        newsContainer.innerHTML = `
            <div class="empty-state">
                <p>아직 오늘의 뉴스가 없습니다.</p>
                <p>매일 오전 7시에 업데이트됩니다.</p>
            </div>
        `;
        return;
    }

    newsContainer.innerHTML = filteredNews.map(createNewsCard).join('');
}

// 로딩 상태 토글
function setLoading(isLoading) {
    if (isLoading) {
        loadingEl.classList.remove('hidden');
    } else {
        loadingEl.classList.add('hidden');
    }
}

// Firestore에서 뉴스 가져오기
async function fetchNews() {
    setLoading(true);

    try {
        // 오늘 날짜 기준으로 뉴스 조회
        const today = new Date();
        today.setHours(0, 0, 0, 0);

        const snapshot = await db.collection('news')
            .where('date', '>=', today)
            .orderBy('date', 'desc')
            .get();

        if (snapshot.empty) {
            // 오늘 뉴스가 없으면 가장 최근 뉴스 조회
            const recentSnapshot = await db.collection('news')
                .orderBy('date', 'desc')
                .limit(4)
                .get();

            newsData = recentSnapshot.docs.map(doc => ({
                id: doc.id,
                ...doc.data()
            }));
        } else {
            newsData = snapshot.docs.map(doc => ({
                id: doc.id,
                ...doc.data()
            }));
        }

        renderNews(currentCategory);
    } catch (error) {
        console.error('뉴스 로딩 실패:', error);
        newsContainer.innerHTML = `
            <div class="error-message">
                <h3>뉴스를 불러올 수 없습니다</h3>
                <p>잠시 후 다시 시도해주세요.</p>
            </div>
        `;
    } finally {
        setLoading(false);
    }
}

// 탭 클릭 이벤트 핸들러
function handleTabClick(e) {
    if (!e.target.classList.contains('tab')) return;

    // 활성 탭 변경
    document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
    e.target.classList.add('active');

    // 카테고리 필터링
    currentCategory = e.target.dataset.category;
    renderNews(currentCategory);
}

// 이벤트 리스너 등록
document.querySelector('.category-tabs').addEventListener('click', handleTabClick);

// 초기화
displayTodayDate();
fetchNews();

// 데모 데이터 (Firebase 연결 전 테스트용)
function loadDemoData() {
    newsData = [
        {
            id: '1',
            category: 'realestate',
            title: '서울 아파트 전세가율 70% 돌파...매매가 하락에도 전세가는 상승',
            summary: '서울 아파트 전세가율이 70%를 넘어섰다. 매매가격 하락에도 전세 수요는 여전히 높아 전세가격은 오히려 상승세를 보이고 있다. 전문가들은 전세 시장 안정화까지 시간이 필요하다고 분석했다.',
            imageUrl: 'https://via.placeholder.com/400x200/e8f5e9/2e7d32?text=Real+Estate',
            link: 'https://news.naver.com',
            source: '한국경제',
            date: new Date()
        },
        {
            id: '2',
            category: 'stock',
            title: '코스피 2,600선 회복..."연말 산타랠리 기대감"',
            summary: '코스피가 2,600선을 다시 회복했다. 외국인과 기관의 동반 순매수에 힘입어 상승세를 이어갔다. 증권가에서는 연말 산타랠리에 대한 기대감이 커지고 있다.',
            imageUrl: 'https://via.placeholder.com/400x200/fff3e0/ef6c00?text=Stock',
            link: 'https://news.naver.com',
            source: '매일경제',
            date: new Date()
        },
        {
            id: '3',
            category: 'economy',
            title: '한국은행 기준금리 동결..."물가 안정 추이 지켜볼 것"',
            summary: '한국은행 금융통화위원회가 기준금리를 현 수준에서 동결했다. 이창용 총재는 물가 안정 추이를 면밀히 관찰하겠다고 밝혔다. 시장에서는 내년 상반기 금리 인하 가능성에 주목하고 있다.',
            imageUrl: 'https://via.placeholder.com/400x200/e3f2fd/1565c0?text=Economy',
            link: 'https://news.naver.com',
            source: '연합뉴스',
            date: new Date()
        },
        {
            id: '4',
            category: 'it',
            title: 'AI 반도체 경쟁 가열...삼성-SK, 차세대 HBM 개발 박차',
            summary: '글로벌 AI 반도체 시장을 선점하기 위한 경쟁이 치열해지고 있다. 삼성전자와 SK하이닉스는 차세대 고대역폭메모리(HBM) 개발에 속도를 내고 있다. 업계는 내년 HBM 시장이 더욱 커질 것으로 전망했다.',
            imageUrl: 'https://via.placeholder.com/400x200/f3e5f5/7b1fa2?text=IT',
            link: 'https://news.naver.com',
            source: '조선일보',
            date: new Date()
        }
    ];
    renderNews(currentCategory);
    setLoading(false);
}

// Firebase 설정이 완료되지 않은 경우 데모 데이터 사용
if (firebaseConfig.apiKey === 'YOUR_API_KEY') {
    console.log('Firebase 설정이 필요합니다. 데모 데이터를 표시합니다.');
    loadDemoData();
}
