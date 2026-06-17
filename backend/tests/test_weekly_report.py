import os
import sys
import unittest
from unittest.mock import patch

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from api.report import (  # noqa: E402
    MAX_WEEKLY_REPORT_INPUT_CHARS,
    WeeklyReportQualityError,
    _build_weekly_journal_text,
    _normalize_weekly_report_payload,
    _parse_llm_json,
)


class WeeklyReportTests(unittest.TestCase):
    def test_parse_llm_json_accepts_markdown_json_block(self):
        parsed = _parse_llm_json("""
```json
{
  "summary": "이번 주 기록에서 반복된 흐름입니다.",
  "keywords": ["자율성", "성찰"],
  "next_question": "다음 선택에서 무엇을 직접 고르고 싶나요?"
}
```
""")

        self.assertEqual(parsed["summary"], "이번 주 기록에서 반복된 흐름입니다.")
        self.assertEqual(parsed["keywords"], ["자율성", "성찰"])

    def test_normalize_weekly_report_payload_cleans_and_bounds_fields(self):
        normalized = _normalize_weekly_report_payload({
            "summary": "  이번 주 기록에서\n\n반복된 흐름이 보입니다.  ",
            "keywords": "자율성, 자기 이해, 자율성, 매우긴키워드" * 4,
            "next_question": "  다음 주에 내가 직접 고를 수 있는 작은 선택은 무엇인가요?  ",
        })

        self.assertEqual(normalized["summary"], "이번 주 기록에서 반복된 흐름이 보입니다.")
        self.assertEqual(normalized["keywords"][:2], ["자율성", "자기 이해"])
        self.assertLessEqual(len(normalized["keywords"]), 3)
        self.assertEqual(normalized["next_question"], "다음 주에 내가 직접 고를 수 있는 작은 선택은 무엇인가요?")

    def test_normalize_weekly_report_payload_rejects_blank_summary(self):
        with self.assertRaises(WeeklyReportQualityError) as ctx:
            _normalize_weekly_report_payload({
                "summary": " ",
                "keywords": ["성찰"],
                "next_question": "다음 주 질문",
            })

        self.assertEqual(ctx.exception.code, "missing_summary")

    def test_normalize_weekly_report_payload_rejects_blank_next_question(self):
        with self.assertRaises(WeeklyReportQualityError) as ctx:
            _normalize_weekly_report_payload({
                "summary": "이번 주 요약",
                "keywords": ["성찰"],
                "next_question": "",
            })

        self.assertEqual(ctx.exception.code, "missing_next_question")

    def test_build_weekly_journal_text_truncates_large_input(self):
        journals = [
            {
                "created_at": "2026-06-10T12:00:00",
                "emotion": "calm",
                "title": "긴 일기",
                "content": "a" * (MAX_WEEKLY_REPORT_INPUT_CHARS + 1000),
            }
        ]

        with patch("api.report.decrypt", side_effect=lambda value: value):
            text = _build_weekly_journal_text(journals)

        self.assertLessEqual(len(text), MAX_WEEKLY_REPORT_INPUT_CHARS)
        self.assertIn("감정: calm", text)


if __name__ == "__main__":
    unittest.main()
