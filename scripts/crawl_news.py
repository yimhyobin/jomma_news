#!/usr/bin/env python3
"""
네이버 뉴스 랭킹에서 카테고리별 가장 많이 본 뉴스 1위를 크롤링하여
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

# 카테고리 설정
CATEGORIES = {
    'economy': {
        'name': '경제',
        'url': 'https://news.naver.com/main/ranking/popularDay.naver?mid=etc&sid1=101',
        'sid1': '101',
        'sid2': None
    },
    'realestate': {
        'name': '부동산',
        'url': 'https://news.naver.com/main/ranking/popularDay.naver?mid=etc&sid1=101&sid2=260',
        'sid1': '101',
        'sid2': '260'
    },
    'stock': {
        'name': '주식',
        'url': 'https://news.naver.com/main/ranking/popularDay.naver?mid=etc&sid1=101&sid2=258',
        'sid1': '101',
        'sid2': '258'
    },
    'it': {
        'name': 'IT',
        'url': 'https://news.naver.com/main/ranking/popularDay.naver?mid=etc&sid1=105',
        'sid1': '105',
        'sid2': None
    }
}

# HTTP 요청 헤더
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
}


def init_firebase():
    """Firebase 초기화"""
    # GitHub Actions에서 환경 변수로 전달된 서비스 계정 JSON 사용
    service_account_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT')

    if service_account_json:
        # 환경 변수에서 JSON 파싱
        service_account_info = json.loads(service_account_json)
        cred = credentials.Certificate(service_account_info)
    else:
        # 로컬 개발용: 파일에서 읽기
        cred_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', 'serviceAccountKey.json')
        if os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
        else:
            raise ValueError("Firebase 인증 정보가 없습니다. FIREBASE_SERVICE_ACCOUNT 환경 변수를 설정하세요.")

    firebase_admin.initialize_app(cred)
    return firestore.client()


def fetch_ranking_page(url: str) -> Optional[BeautifulSoup]:
    """랭킹 페이지 HTML 가져오기"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'html.parser')
    except requests.RequestException as e:
        print(f"페이지 로딩 실패: {url}, 에러: {e}")
        return None


def extract_top_news(soup: BeautifulSoup, category_key: str) -> Optional[Dict]:
    """랭킹 페이지에서 1위 뉴스 추출"""
    try:
        # 랭킹 리스트에서 첫 번째 뉴스 찾기
        ranking_list = soup.select('.rankingnews_list li')

        if not ranking_list:
            # 대체 선택자 시도
            ranking_list = soup.select('.list_ranking li')

        if not ranking_list:
            print(f"랭킹 리스트를 찾을 수 없습니다: {category_key}")
            return None

        first_item = ranking_list[0]

        # 뉴스 링크 및 제목
        link_elem = first_item.select_one('a')
        if not link_elem:
            return None

        link = link_elem.get('href', '')
        title = link_elem.get_text(strip=True)

        # 이미지 URL (있는 경우)
        img_elem = first_item.select_one('img')
        image_url = img_elem.get('src', '') if img_elem else ''

        # 언론사
        source_elem = first_item.select_one('.rankingnews_name') or first_item.select_one('.writing')
        source = source_elem.get_text(strip=True) if source_elem else ''

        return {
            'title': title,
            'link': link,
            'imageUrl': image_url,
            'source': source,
            'category': category_key
        }
    except Exception as e:
        print(f"뉴스 추출 실패 ({category_key}): {e}")
        return None


def fetch_article_content(url: str) -> Dict:
    """기사 본문에서 요약 및 이미지 추출"""
    result = {'summary': '', 'imageUrl': ''}

    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # 본문 추출 (네이버 뉴스 기사 페이지)
        article_body = soup.select_one('#newsct_article') or soup.select_one('#articeBody') or soup.select_one('.newsct_article')

        if article_body:
            # 텍스트만 추출하고 앞 3문장 가져오기
            text = article_body.get_text(strip=True)
            text = re.sub(r'\s+', ' ', text)  # 공백 정리

            # 문장 분리 (마침표, 물음표, 느낌표 기준)
            sentences = re.split(r'(?<=[.?!])\s+', text)
            sentences = [s.strip() for s in sentences if len(s.strip()) > 10][:3]
            result['summary'] = ' '.join(sentences)

        # 대표 이미지 추출
        og_image = soup.select_one('meta[property="og:image"]')
        if og_image:
            result['imageUrl'] = og_image.get('content', '')
        else:
            # 본문 내 첫 번째 이미지
            img = article_body.select_one('img') if article_body else None
            if img:
                result['imageUrl'] = img.get('src', '') or img.get('data-src', '')

    except Exception as e:
        print(f"기사 본문 추출 실패: {url}, 에러: {e}")

    return result


def crawl_category_news(category_key: str, category_info: Dict) -> Optional[Dict]:
    """특정 카테고리의 1위 뉴스 크롤링"""
    print(f"크롤링 중: {category_info['name']} ({category_key})")

    # 랭킹 페이지에서 1위 뉴스 추출
    soup = fetch_ranking_page(category_info['url'])
    if not soup:
        return None

    news = extract_top_news(soup, category_key)
    if not news:
        return None

    # 기사 본문에서 요약 및 이미지 가져오기
    if news['link']:
        article_data = fetch_article_content(news['link'])
        news['summary'] = article_data['summary'] or f"{news['title']}..."
        if article_data['imageUrl']:
            news['imageUrl'] = article_data['imageUrl']

    # 날짜 추가
    news['date'] = datetime.now()
    news['createdAt'] = datetime.now()

    print(f"  완료: {news['title'][:50]}...")
    return news


def save_to_firestore(db, news_list: List[Dict]):
    """Firestore에 뉴스 저장"""
    today = datetime.now().strftime('%Y-%m-%d')
    batch = db.batch()

    for news in news_list:
        # 문서 ID: 날짜_카테고리
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

    # Firebase 초기화
    try:
        db = init_firebase()
        print("Firebase 연결 성공")
    except Exception as e:
        print(f"Firebase 연결 실패: {e}")
        return

    # 각 카테고리별 크롤링
    news_list = []
    for category_key, category_info in CATEGORIES.items():
        news = crawl_category_news(category_key, category_info)
        if news:
            news_list.append(news)

    # Firestore에 저장
    if news_list:
        save_to_firestore(db, news_list)
    else:
        print("크롤링된 뉴스가 없습니다.")

    print("=" * 50)
    print("완료!")


if __name__ == '__main__':
    main()
