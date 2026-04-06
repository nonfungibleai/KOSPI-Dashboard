# Vercel 배포 가이드

## 폴더 구조
```
vercel-deploy/
├── index.html        ← 대시보드 프론트엔드
├── api/
│   └── index.py      ← Flask 백엔드 (서버리스)
├── vercel.json       ← Vercel 라우팅 설정
├── requirements.txt  ← Python 패키지
└── DEPLOY_GUIDE.md   ← 이 파일
```

---

## 배포 순서

### 1단계 – GitHub 업로드
1. GitHub에서 새 저장소(Repository) 생성
2. `vercel-deploy/` 폴더 안의 파일들을 전부 저장소 루트에 업로드
   - `index.html`, `api/index.py`, `vercel.json`, `requirements.txt`

### 2단계 – Vercel 연동
1. [vercel.com](https://vercel.com) 접속 → GitHub 계정으로 로그인
2. **"Add New Project"** → 방금 만든 GitHub 저장소 선택
3. **Framework Preset**: `Other` 선택
4. **"Deploy"** 클릭 (첫 배포, 환경변수 없어도 일단 진행)

### 3단계 – 환경변수 설정 (필수!)
Vercel Dashboard → 프로젝트 선택 → **Settings** → **Environment Variables**

| 변수명 | 값 |
|---|---|
| `KIS_APP_KEY` | `PS5ONsikMloU26m6QkDX...` (config.py의 APP_KEY) |
| `KIS_APP_SECRET` | `7u2xLeizSSt/RVND...` (config.py의 APP_SECRET) |
| `KIS_ACCOUNT_NO` | `78711158` |
| `KIS_ACCOUNT_CODE` | `01` |
| `KIS_TRADE_MODE` | `real` |

환경변수 저장 후 **Redeploy** 클릭

### 4단계 – 완료
Vercel이 제공하는 URL (예: `https://my-dashboard.vercel.app`) 을
어느 컴퓨터, 어느 브라우저에서든 접속 가능!

---

## 로컬 테스트 (선택)
```bash
cd vercel-deploy
pip install -r requirements.txt
python api/index.py   # localhost:5000 에서 실행
```
로컬 테스트 시 `index.html` 열 때 `const API = "http://localhost:5000"` 으로 임시 변경 후 사용

---

## 주의사항
- **KIS API IP 허용**: KIS Developers에서 Vercel 서버 IP를 허용해야 할 수 있음
  - KIS API 호출이 실패하면 [KIS Developers](https://apiportal.koreainvestment.com) → API 신청 → IP 설정 확인
- **Vercel 무료 플랜**: 서버리스 함수 실행시간 최대 60초 (관심종목 병렬조회로 ~3초 처리)
- **yfinance (차트/시장지수)**: KIS API 없어도 작동
