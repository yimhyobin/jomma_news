#!/usr/bin/env python3
"""
네이버 뉴스 섹션별 헤드라인 뉴스를 크롤링하여
Firebase Firestore에 저장하는 스크립트
"""

import os
import json
import re
from datetime import datetime
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore

# 카테고리 설정 (네이버 뉴스 섹션 URL)
CATEGORIES = {
    'economy': {
        'name': '경제',
        'url': 'https://news.naver.com/section/101'
    },
    'realestate': {
        'name': '부동산',
        'url': 'https://news.naver.com/section/101/260'
    },
    'stock': {
        'name': '주식',
        'url': 'https://news.naver.com/section/101/258'
    },
    'it': {
        'name': 'IT',
        'url': 'https://news.naver.com/section/105'
    }
}

# HTTP 요청 헤더
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
    'Referer': 'https://news.naver.com/',
}


def init_firebase():
    """Firebase 초기화"""
    service_account_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT')

    if service_account_json:
        service_account_info = json.loads(service_account_json)
        cred = credentials.Certificate(service_account_info)
    else:
        cred_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', 'serviceAccountKey.json')
        if os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
        else:
            raise ValueError("Firebase 인증 정보가 없습니다.")

    firebase_admin.initialize_app(cred)
    return firestore.client()


def fetch_page(url: str) -> Optional[BeautifulSoup]:
    """페이지 HTML 가져오기"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'html.parser')
    except requests.RequestException as e:
        print(f"페이지 로딩 실패: {url}, 에러: {e}")
        return None


def extract_headline_news(soup: BeautifulSoup, category_key: str) -> Optional[Dict]:
    """섹션 페이지에서 헤드라인 뉴스 추출"""
    try:
        # 방법 1: 헤드라인 영역에서 첫 번째 뉴스
        headline = soup.select_one('.sa_text_title')

        if not headline:
            # 방법 2: 메인 뉴스 영역
            headline = soup.select_one('.ct_head_wrap a')

        if not headline:
            # 방법 3: 뉴스 리스트에서 첫 번째
            headline = soup.select_one('.sa_item a.sa_text_title')

        if not headline:
            # 방법 4: 다른 선택자 시도
            headline = soup.select_one('a.sa_text_title')

        if not headline:
            print(f"헤드라인을 찾을 수 없습니다: {category_key}")
            # 디버깅: 페이지 구조 출력
            all_links = soup.select('a[href*="news.naver.com/article"]')[:5]
            for link in all_links:
                print(f"  발견된 링크: {link.get('href', '')[:80]}")
            return None

        link = headline.get('href', '')
        if not link.startswith('http'):
            link = 'https://news.naver.com' + link

        title = headline.get_text(strip=True)

        # 이미지 찾기
        img_elem = soup.select_one('.sa_thumb_inner img') or soup.select_one('.ct_head_wrap img')
        image_url = ''
        if img_elem:
            image_url = img_elem.get('data-src', '') or img_elem.get('src', '')

        return {
            'title': title,
            'link': link,
            'imageUrl': image_url,
            'source': '',
            'category': category_key
        }
    except Exception as e:
        print(f"뉴스 추출 실패 ({category_key}): {e}")
        return None


def fetch_article_details(url: str) -> Dict:
    """기사 상세 페이지에서 정보 추출"""
    result = {'summary': '', 'imageUrl': '', 'source': ''}

    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # 언론사명 추출
        source_elem = soup.select_one('.media_end_head_top_logo img')
        if source_elem:
            result['source'] = source_elem.get('alt', '') or source_elem.get('title', '')

        if not result['source']:
            source_elem = soup.select_one('.media_end_head_journalist_box a')
            if source_elem:
                result['source'] = source_elem.get_text(strip=True)

        # 본문 추출
        article_body = (
            soup.select_one('#dic_area') or
            soup.select_one('#newsct_article') or
            soup.select_one('.newsct_article')
        )

        if article_body:
            # 불필요한 요소 제거
            for tag in article_body.select('script, style, .reporter_area, .byline'):
                tag.decompose()

            text = article_body.get_text(separator=' ', strip=True)
            text = re.sub(r'\s+', ' ', text)

            # 문장 분리 후 앞 3문장
            sentences = re.split(r'(?<=[.?!])\s+', text)
            sentences = [s.strip() for s in sentences if len(s.strip()) > 15][:3]
            result['summary'] = ' '.join(sentences)

        # 대표 이미지
        og_image = soup.select_one('meta[property="og:image"]')
        if og_image:
            result['imageUrl'] = og_image.get('content', '')

    except Exception as e:
        print(f"기사 상세 추출 실패: {url}, 에러: {e}")

    return result


def crawl_category_news(category_key: str, category_info: Dict) -> Optional[Dict]:
    """특정 카테고리의 헤드라인 뉴스 크롤링"""
    print(f"크롤링 중: {category_info['name']} ({category_key})")

    soup = fetch_page(category_info['url'])
    if not soup:
        return None

    news = extract_headline_news(soup, category_key)
    if not news:
        return None

    # 기사 상세 페이지에서 추가 정보 가져오기
    if news['link']:
        details = fetch_article_details(news['link'])
        news['summary'] = details['summary'] or f"{news['title']}"
        news['source'] = details['source'] or '네이버 뉴스'
        if details['imageUrl']:
            news['imageUrl'] = details['imageUrl']

    # 날짜 추가
    news['date'] = datetime.now()
    news['createdAt'] = datetime.now()

    print(f"  제목: {news['title'][:50]}...")
    print(f"  언론사: {news['source']}")
    return news


def save_to_firestore(db, news_list: List[Dict]):
    """Firestore에 뉴스 저장"""
    today = datetime.now().strftime('%Y-%m-%d')
    batch = db.batch()

    for news in news_list:
        doc_id = f"{today}_{news['category']}"
        doc_ref = db.collection('news').document(doc_id)
        batch.set(doc_ref, news)
        print(f"저장: {doc_id}")

    batch.commit()
    print(f"총 {len(news_list)}개 뉴스 저장 완료")


def main():
    """메인 실행 함수"""
    print("=" * 50)
    print(f"뉴스 크롤링 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    try:
        db = init_firebase()
        print("Firebase 연결 성공")
    except Exception as e:
        print(f"Firebase 연결 실패: {e}")
        return

    news_list = []
    for category_key, category_info in CATEGORIES.items():
        news = crawl_category_news(category_key, category_info)
        if news:
            news_list.append(news)

    if news_list:
        save_to_firestore(db, news_list)
    else:
        print("크롤링된 뉴스가 없습니다.")

    print("=" * 50)
    print("완료!")


if __name__ == '__main__':
    main()
