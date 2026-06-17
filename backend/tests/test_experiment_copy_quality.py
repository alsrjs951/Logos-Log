import os
import sys
import unittest
import base64
from unittest.mock import patch

os.environ.setdefault("JWT_SECRET", "test-secret-for-experiment-copy-32bytes")
os.environ.setdefault("ENCRYPTION_KEY", base64.urlsafe_b64encode(b"0" * 32).decode("ascii"))

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from api.value_cards import (  # noqa: E402
    ExperimentCopyQualityError,
    _cached_experiment_response,
    _experiment_cache_text_fields,
    _safe_cached_experiment_response,
    _validate_experiment_copy,
)


class ExperimentCopyQualityTests(unittest.TestCase):
    def test_small_action_copy_passes(self):
        _validate_experiment_copy(
            "이번 주에 내가 원하는 선택과 타인의 기대를 한 줄씩 적고, 작은 선택 하나를 직접 골라보세요.",
            "최근 가치 카드에서 자율성과 자기 이해가 함께 반복되어 나온 흐름입니다.",
            "그 선택은 내가 무엇을 원하는지 조금 더 선명하게 해주었나요?",
        )

    def test_clinical_copy_is_rejected(self):
        with self.assertRaises(ExperimentCopyQualityError) as ctx:
            _validate_experiment_copy(
                "이번 주에 우울증을 치료하기 위한 계획을 세워보세요.",
                "증상을 줄이는 데 도움이 될 수 있습니다.",
                "치료 효과가 있었나요?",
            )

        self.assertEqual(ctx.exception.code, "clinical_or_crisis_copy")

    def test_high_pressure_copy_is_rejected(self):
        with self.assertRaises(ExperimentCopyQualityError) as ctx:
            _validate_experiment_copy(
                "이번 주에 반드시 매일 한 가지 선택을 바꿔야 합니다.",
                "지금은 강하게 밀어붙일 때입니다.",
                "실패하지 않았나요?",
            )

        self.assertEqual(ctx.exception.code, "high_pressure_copy")

    def test_non_specific_copy_is_rejected(self):
        with self.assertRaises(ExperimentCopyQualityError) as ctx:
            _validate_experiment_copy(
                "삶의 방향을 깊이 성찰해보세요.",
                "최근 기록에서 성찰의 흐름이 보입니다.",
                "무엇을 느꼈나요?",
            )

        self.assertEqual(ctx.exception.code, "not_small_action_copy")

    def test_overlong_experiment_is_rejected(self):
        with self.assertRaises(ExperimentCopyQualityError) as ctx:
            _validate_experiment_copy(
                "이번 주에 " + "작은 선택을 기록하고 " * 20,
                "최근 카드 흐름에서 나온 제안입니다.",
                "어땠나요?",
            )

        self.assertEqual(ctx.exception.code, "experiment_too_long")

    def test_experiment_cache_text_fields_are_encrypted_and_readable(self):
        fields = _experiment_cache_text_fields(
            "자기 이해 흐름에서 이어진 제안입니다.",
            "이번 주에 작은 선택 하나를 직접 골라보세요.",
            "그 선택은 내 마음을 더 선명하게 했나요?",
        )

        self.assertNotEqual(fields["experiment"], "이번 주에 작은 선택 하나를 직접 골라보세요.")
        self.assertTrue(fields["experiment"].startswith("enc:v1:"))

        response = _cached_experiment_response({
            "anchor_card_id": "card-1",
            "related_card_ids": ["card-1"],
            "cache_key": "cache-1",
            **fields,
        })

        self.assertEqual(response.reason, "자기 이해 흐름에서 이어진 제안입니다.")
        self.assertEqual(response.experiment, "이번 주에 작은 선택 하나를 직접 골라보세요.")
        self.assertEqual(response.reflection_question, "그 선택은 내 마음을 더 선명하게 했나요?")
        self.assertEqual(response.source, "llm_cache")

    def test_legacy_plain_experiment_cache_still_reads(self):
        response = _cached_experiment_response({
            "anchor_card_id": "card-1",
            "related_card_ids": ["card-1"],
            "reason": "기존 평문 이유",
            "experiment": "기존 평문 실험",
            "reflection_question": "기존 평문 질문",
        })

        self.assertEqual(response.reason, "기존 평문 이유")
        self.assertEqual(response.experiment, "기존 평문 실험")
        self.assertEqual(response.reflection_question, "기존 평문 질문")

    def test_safe_cache_reader_ignores_corrupt_encrypted_cache(self):
        with patch("api.value_cards.log_event") as log_event:
            response = _safe_cached_experiment_response({
                "anchor_card_id": "card-1",
                "related_card_ids": ["card-1"],
                "cache_key": "cache-1",
                "reason": "enc:v1:not-valid-cache",
                "experiment": "enc:v1:not-valid-cache",
                "reflection_question": "enc:v1:not-valid-cache",
            }, user_hash="user-hash")

        self.assertIsNone(response)
        self.assertEqual(log_event.call_args.args[0], "recommended_experiment_cache_read_error")
        self.assertEqual(log_event.call_args.kwargs["cache_key"], "cache-1")

    def test_safe_cache_reader_ignores_empty_experiment_cache(self):
        fields = _experiment_cache_text_fields(
            "최근 가치 흐름에서 이어진 제안입니다.",
            "",
            "무엇이 달라졌나요?",
        )

        response = _safe_cached_experiment_response({
            "anchor_card_id": "card-1",
            "related_card_ids": ["card-1"],
            **fields,
        })

        self.assertIsNone(response)


if __name__ == "__main__":
    unittest.main()
