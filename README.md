# IT HR 위클리 📋

IT·테크 기업 HR 담당자를 위한 **주간 노무·법령 뉴스레터** 웹사이트입니다.
데이터(JSON)만 추가하면 정적 사이트가 생성되고, GitHub Actions가 매주 자동으로 빌드·배포합니다.

- **콘텐츠**: 사례 중심(포괄임금·통상임금·노란봉투법·주4.5일제·플랫폼 근로자성 등) IT 인사 시사점 + 출처 링크
- **배포**: GitHub Pages 자동 게시 (PC가 꺼져 있어도 동작)
- **자동화**: 매주 월요일 자동 빌드·배포 + (선택) 콘텐츠 자동 생성
- **의존성**: 빌드는 Python 표준 라이브러리만 사용 (설치 불필요)

---

## 폴더 구조

```
it-hr-weekly/
├── data/
│   ├── site.json              # 사이트 전역 설정(제목·발행처·면책고지 등)
│   └── issues/                # 호별 콘텐츠 — 파일 1개 = 1개 호
│       └── 2026-w26.json      # 창간호
├── assets/styles.css          # 디자인(라이트·다크·반응형·인쇄 대응)
├── build.py                   # 생성기: data → dist/ (HTML + RSS)
├── scripts/
│   ├── new_issue.py           # 다음 호 빈 초안 생성(오프라인)
│   └── generate_issue.py      # [선택] Claude API로 자동 리서치·작성
├── .github/workflows/
│   ├── publish.yml            # 빌드 + GitHub Pages 배포
│   └── weekly-issue.yml       # 매주 새 호 생성·커밋
└── dist/                      # 빌드 산출물(자동 생성, git 미추적)
```

---

## 1. 로컬에서 미리 보기

Python 3.10+ 만 있으면 됩니다.

```bash
python build.py            # dist/ 로 빌드
python build.py --serve    # 빌드 후 http://localhost:8000 미리보기
```

`dist/index.html`(보관함), `dist/issues/<slug>.html`(각 호), `dist/feed.xml`(RSS)이 생성됩니다.

---

## 2. 새 호 추가하기

### 방법 A — 직접 작성 (권장)

`data/issues/` 에 `YYYY-wNN.json` 파일을 만들고 아래 구조로 채웁니다.
가장 쉬운 방법은 초안을 생성한 뒤 내용을 채우는 것입니다:

```bash
python scripts/new_issue.py                 # 다음 호 초안 생성
python scripts/new_issue.py --date 2026-06-29   # 발행일 지정
```

생성된 JSON에서 `_draft`/`_todo` 키를 지우고 내용을 채운 뒤 커밋하면 됩니다.

#### 호 JSON 필드

| 필드 | 설명 |
|---|---|
| `issueNumber` | 호 번호(정수) |
| `slug` | URL용 식별자(예: `2026-w26`) — 파일명과 동일 |
| `weekLabel` | 표시용 주차(예: `2026년 6월 4주차`) |
| `date` | 발행일 `YYYY-MM-DD` |
| `headline` | 리드 헤드라인 |
| `intro` | 편집자 인트로(3~4문장) |
| `sections[]` | `{title, emoji, items[]}` — 주제 섹션 |
| `sections[].items[]` | `{headline, category, effectiveDate, summary, whatChanged, itImpact, sources[]}` |
| `sources[]` | `{name, url}` 출처 링크 |
| `lawWatch[]` | `{law, status, effectiveDate, note, url}` 입법·시행 캘린더 표 |
| `quickStats[]` | `{value, label, url}` 핵심 수치 카드 |
| `actionItems[]` | HR 실무 체크리스트(문자열 배열) |

`data/issues/2026-w26.json`(창간호)을 템플릿으로 복사해 쓰면 가장 빠릅니다.

### 방법 B — Claude API로 자동 생성 (선택)

웹검색으로 이번 주 이슈를 조사해 호 JSON을 자동 작성합니다.

```bash
pip install anthropic
export ANTHROPIC_API_KEY=sk-ant-...      # Windows PowerShell: $env:ANTHROPIC_API_KEY="sk-ant-..."
python scripts/generate_issue.py
```

> ⚠️ 자동 생성 결과는 배포 전 **사실관계·출처를 사람이 검수**하는 것을 권장합니다.

---

## 3. GitHub Pages 자동 배포 설정

1. 이 폴더를 GitHub 저장소로 올립니다.
   ```bash
   cd it-hr-weekly
   git init && git add . && git commit -m "init: IT HR 위클리"
   git branch -M main
   git remote add origin https://github.com/<계정>/<저장소>.git
   git push -u origin main
   ```
2. GitHub 저장소 → **Settings → Pages → Build and deployment → Source 를 "GitHub Actions"** 로 설정합니다.
3. 끝입니다. 이후 동작:
   - `data/` 등을 push할 때마다 자동 빌드·배포 (`publish.yml`)
   - **매주 월요일 아침(KST)** 자동 재빌드·배포
   - 사이트 주소: `https://<계정>.github.io/<저장소>/`
     - `data/site.json` 의 `baseUrl` 에 이 주소를 넣으면 RSS·공유 링크가 절대경로가 됩니다.

### 매주 콘텐츠 자동 생성(선택)

`weekly-issue.yml` 이 매주 월요일 새 호를 만들어 커밋합니다.

- **완전 자동(실제 콘텐츠)**: 저장소 → **Settings → Secrets and variables → Actions** 에 `ANTHROPIC_API_KEY` 를 등록하면, 매주 Claude API가 리서치·작성한 호가 자동 커밋·배포됩니다.
- **반자동(초안)**: 키가 없으면 빈 초안이 커밋되어, 사람이 채우도록 대기합니다.
- 수동 실행: Actions 탭 → **Weekly issue → Run workflow** (발행일 지정 가능).

---

## 4. 사이트 설정 바꾸기

`data/site.json` 에서 제목·태그라인·발행처·강조색·구독 안내·면책 고지를 수정합니다.
`accent`(강조색)만 바꿔도 전체 테마 색이 바뀝니다.

---

## 면책

본 뉴스레터는 공개된 자료를 수집·요약한 **일반 정보**이며 법률 자문이 아닙니다.
실제 적용 전 링크된 원문과 사내·외부 노무 자문으로 사실관계를 반드시 확인하세요.
