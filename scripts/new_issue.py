#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""다음 호의 빈 초안(JSON)을 생성한다 — 의존성 없음, 오프라인 동작.

매주 자동화에서 Claude API 키가 없을 때 사용하는 기본 경로다.
생성된 data/issues/<slug>.json 을 사람이 채운 뒤 커밋하면 빌드·배포된다.

사용법:
    python scripts/new_issue.py            # 다음 호 초안 생성
    python scripts/new_issue.py --date 2026-06-29   # 발행일 지정
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

ROOT = Path(__file__).resolve().parent.parent
ISSUES = ROOT / "data" / "issues"


def load_issues():
    out = []
    if ISSUES.exists():
        for p in ISSUES.glob("*.json"):
            try:
                out.append(json.loads(p.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                pass
    return out


def next_meta(pub_date: datetime):
    issues = load_issues()
    next_no = max((i.get("issueNumber", 0) for i in issues), default=0) + 1
    iso = pub_date.isocalendar()
    slug = f"{iso[0]}-w{iso[1]:02d}"
    week_of_month = (pub_date.day - 1) // 7 + 1
    week_label = f"{pub_date.year}년 {pub_date.month}월 {week_of_month}주차"
    return next_no, slug, week_label


def draft(issue_no, slug, week_label, date_str):
    return {
        "issueNumber": issue_no,
        "slug": slug,
        "weekLabel": week_label,
        "date": date_str,
        "headline": "(제목을 입력하세요) — 이번 주 IT HR 핵심 이슈",
        "intro": "(이번 주 호 편집자 인트로를 3~4문장으로 작성하세요.)",
        "sections": [
            {
                "title": "이번 주 핵심 — 법령·지침",
                "emoji": "⚖️",
                "items": [
                    {
                        "headline": "(항목 제목)",
                        "category": "법령개정",
                        "effectiveDate": "(시행/발표일)",
                        "summary": "(무슨 일인지 2~4문장)",
                        "whatChanged": "(바뀐 핵심 사실·수치)",
                        "itImpact": "(IT 인사 담당자가 무엇을 해야 하는가)",
                        "sources": [
                            {"name": "출처명", "url": "https://example.com"}
                        ]
                    }
                ]
            }
        ],
        "lawWatch": [
            {"law": "(법령/법안)", "status": "(상태)", "effectiveDate": "(시점)", "note": "(한줄 메모)", "url": "https://example.com"}
        ],
        "quickStats": [
            {"value": "(수치)", "label": "(설명)", "url": "https://example.com"}
        ],
        "actionItems": [
            "(이번 주 HR 실무 체크리스트 항목)"
        ],
        "_draft": True,
        "_todo": "이 파일의 내용을 채운 뒤 '_draft'/'_todo' 키를 삭제하고 커밋하세요."
    }


def main():
    date_str = None
    if "--date" in sys.argv:
        date_str = sys.argv[sys.argv.index("--date") + 1]
    pub_date = datetime.strptime(date_str, "%Y-%m-%d") if date_str else (datetime.now() + timedelta(days=0))

    issue_no, slug, week_label = next_meta(pub_date)
    out_path = ISSUES / f"{slug}.json"
    if out_path.exists():
        print(f"이미 존재함: {out_path} (덮어쓰지 않음)")
        return
    data = draft(issue_no, slug, week_label, pub_date.strftime("%Y-%m-%d"))
    ISSUES.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ 초안 생성: {out_path}")
    print(f"   제{issue_no}호 · {week_label} · {pub_date.strftime('%Y-%m-%d')}")


if __name__ == "__main__":
    main()
