import asyncio
import os
import sys
import unittest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(BACKEND_DIR, "scripts")
EVAL_DIR = os.path.join(BACKEND_DIR, "eval")
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, SCRIPTS_DIR)
sys.path.insert(0, EVAL_DIR)

import chunk_and_embed
import analyze_claim_support
import combine_rag_runs
import evaluate_retrieval
import preprocess
import refresh_problem_qrels
import upload_to_mongodb
from services.rag_service import RAGService


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows

    def sort(self, key, direction):
        reverse = direction < 0
        self.rows = sorted(self.rows, key=lambda row: row.get(key, 0), reverse=reverse)
        return self

    def limit(self, count):
        self.rows = self.rows[:count]
        return self

    def __iter__(self):
        return iter(self.rows)


class FakeDocuments:
    def __init__(self, rows):
        self.rows = rows

    def find(self, query, projection):
        document_id = query["document_id"]
        bounds = query["chunk_index"]
        rows = [
            row for row in self.rows
            if row["document_id"] == document_id
            and bounds["$gte"] <= row["chunk_index"] <= bounds["$lte"]
        ]
        return FakeCursor(rows)

    def distinct(self, key, query):
        values = set(query.get(key, {}).get("$in", []))
        return [row[key] for row in self.rows if row.get(key) in values]


class FakeDB:
    def __init__(self, rows):
        self.documents = FakeDocuments(rows)


class FailingLLM:
    async def ainvoke(self, *args, **kwargs):
        raise RuntimeError("bad json")


class FakeLLMResponse:
    def __init__(self, content):
        self.content = content


class StaticLLM:
    def __init__(self, content):
        self.content = content
        self.calls = []

    async def ainvoke(self, *args, **kwargs):
        self.calls.append({"args": args, "kwargs": kwargs})
        return FakeLLMResponse(self.content)


class RAGPipelineTests(unittest.TestCase):
    def test_claim_support_sentence_split_preserves_citations(self):
        sentences = analyze_claim_support.split_sentences(
            "감사는 웰빙과 관련됩니다[1](#source-1). 작은 실천을 탐색해 볼 수 있습니다[2](#source-2)."
        )

        self.assertEqual(sentences, [
            "감사는 웰빙과 관련됩니다[1](#source-1).",
            "작은 실천을 탐색해 볼 수 있습니다[2](#source-2).",
        ])

    def test_claim_support_average_excludes_not_applicable_labels(self):
        labels = [
            {"support": "not_applicable", "support_score": 0.0},
            {"support": "supported", "support_score": 1.0},
            {"support": "unsupported", "support_score": 0.0},
        ]
        scored = [
            item.get("support_score")
            for item in labels
            if item.get("support") != "not_applicable"
            and isinstance(item.get("support_score"), (int, float))
        ]

        self.assertEqual(sum(scored) / len(scored), 0.5)

    def test_combine_rag_runs_deduplicates_cases_and_averages_metrics(self):
        payload = combine_rag_runs.combine_payloads([
            {
                "targets": {"faithfulness": 0.9},
                "settings": {"answer_template_mode": "standard"},
                "cases": [
                    {
                        "id": "g01",
                        "faithfulness": 0.8,
                        "answer_relevancy": 0.9,
                        "context_precision": 0.7,
                        "context_recall": 0.6,
                        "claim_support": 1.0,
                    },
                    {
                        "id": "g02",
                        "faithfulness": 0.9,
                        "answer_relevancy": 1.0,
                        "context_precision": 0.8,
                        "context_recall": 0.7,
                        "claim_support": 0.5,
                    },
                ],
                "rows": [{"id": "g01"}, {"id": "g02"}],
            },
            {
                "cases": [
                    {
                        "id": "g02",
                        "faithfulness": 1.0,
                        "answer_relevancy": 0.9,
                        "context_precision": 0.9,
                        "context_recall": 0.8,
                        "claim_support": 0.75,
                    },
                ],
                "rows": [{"id": "g02", "latest": True}],
            },
        ])

        self.assertEqual([case["id"] for case in payload["cases"]], ["g01", "g02"])
        self.assertAlmostEqual(payload["summary"]["faithfulness"], 0.9)
        self.assertAlmostEqual(payload["summary"]["context_precision"], 0.8)
        self.assertAlmostEqual(payload["summary"]["claim_support"], 0.875)
        self.assertTrue(payload["rows"][1]["latest"])
        self.assertEqual(payload["diagnostics"]["retrieval_review_cases"], ["g01"])
        self.assertEqual(payload["diagnostics"]["faithfulness_review_cases"][0]["id"], "g01")

    def test_known_prefix_filename_parse(self):
        metadata = preprocess.parse_filename_metadata(
            "positive_psych_kern_2014_assessing_employee_wellbeing_in_schools_using_a_multifac.pdf"
        )

        self.assertEqual(metadata["category"], "positive_psych")
        self.assertEqual(metadata["author"], "Kern")
        self.assertEqual(metadata["year"], "2014")

    def test_page_section_split_stops_before_references(self):
        text = preprocess.clean_text(
            "Abstract\n"
            "This abstract explains the study purpose and main finding in enough detail.\n\n"
            "Introduction\n"
            "This introduction preserves the page text and section metadata for chunking.\n\n"
            "References\n"
            "Smith, J. 2020. This should not be embedded."
        )

        sections, current_section, reached_references = preprocess.split_page_sections(text)

        self.assertTrue(reached_references)
        self.assertEqual(current_section, "Introduction")
        self.assertEqual([section["section"] for section in sections], ["Abstract", "Introduction"])
        self.assertNotIn("Smith", "\n".join(section["text"] for section in sections))

    def test_language_and_quality_detection(self):
        english_text = (
            "This study examines psychological well being and motivation among participants. "
            "The results show meaningful relationships between autonomy, competence, and life meaning. "
        ) * 10
        non_english_text = (
            "zamanlarda bireyde olumsuz davranışlar ortaya çıkmaktadır ve kişinin yaşamında anlam arayışı önemlidir. "
        ) * 10

        self.assertEqual(preprocess.detect_language(english_text), "en")
        self.assertNotEqual(preprocess.detect_language(non_english_text), "en")
        self.assertGreater(preprocess.text_quality_score(english_text), 0.55)

    def test_chunk_records_include_page_and_document_metadata(self):
        splitter = chunk_and_embed.make_text_splitter()
        data = {
            "filename": "sdt_deci_2008_motivation_and_education.pdf",
            "document_id": "sdt_deci_2008_motivation_and_education",
            "title": "Motivation and Education",
            "metadata": {"category": "sdt", "author": "Deci", "year": "2008"},
            "language": "en",
            "text_quality": 0.91,
            "pages": [
                {
                    "page": 3,
                    "section": "Methods",
                    "text": "Methods\n" + ("Autonomy support and competence satisfaction. " * 40),
                }
            ],
        }

        records = chunk_and_embed.build_chunk_records(data, splitter)

        self.assertGreaterEqual(len(records), 1)
        first = records[0]
        self.assertEqual(first["chunk_id"], "sdt_deci_2008_motivation_and_education_chunk_0")
        self.assertEqual(first["document_id"], "sdt_deci_2008_motivation_and_education")
        self.assertEqual(first["page_start"], 3)
        self.assertEqual(first["page_end"], 3)
        self.assertEqual(first["section"], "Methods")
        self.assertEqual(first["chunk_index"], 0)
        self.assertEqual(first["metadata"]["title"], "Motivation and Education")
        self.assertEqual(first["language"], "en")
        self.assertGreaterEqual(first["text_quality"], 0.55)

    def test_upload_document_preserves_expanded_schema(self):
        record = {
            "chunk_id": "doc_chunk_2",
            "document_id": "doc",
            "filename": "doc.pdf",
            "title": "A Better Chunk",
            "section": "Results",
            "page_start": 5,
            "page_end": 5,
            "chunk_index": 2,
            "language": "en",
            "text_quality": 0.92,
            "text": "The retrieved excerpt.",
            "embedding": [0.1, 0.2],
            "metadata": {"category": "cbt", "author": "Beck", "year": "1979"},
        }

        doc = upload_to_mongodb.build_mongodb_document(record)

        for key in ("content", "embedding", "chunk_id", "document_id", "filename", "title",
                    "section", "page_start", "page_end", "chunk_index", "metadata"):
            self.assertIn(key, doc)
        self.assertEqual(doc["metadata"]["title"], "A Better Chunk")
        self.assertEqual(doc["metadata"]["filename"], "doc.pdf")
        self.assertEqual(doc["language"], "en")
        self.assertEqual(doc["text_quality"], 0.92)

    def test_upload_filters_non_english_and_low_quality_records(self):
        self.assertTrue(upload_to_mongodb.record_is_eligible(
            {"language": "en", "text_quality": 0.7}, include_non_english=False, min_quality=0.55
        ))
        self.assertFalse(upload_to_mongodb.record_is_eligible(
            {"language": "non_en", "text_quality": 0.9}, include_non_english=False, min_quality=0.55
        ))
        self.assertFalse(upload_to_mongodb.record_is_eligible(
            {"language": "en", "text_quality": 0.2}, include_non_english=False, min_quality=0.55
        ))

    def test_adjacent_context_handles_first_and_last_chunks(self):
        service = RAGService.__new__(RAGService)
        rows = [
            {
                "chunk_id": f"doc_chunk_{idx}",
                "document_id": "doc",
                "chunk_index": idx,
                "content": f"chunk {idx}",
                "metadata": {"title": "Doc"},
                "page_start": idx + 1,
            }
            for idx in range(3)
        ]
        docs = [
            {"document_id": "doc", "chunk_index": 0, "content": "chunk 0", "metadata": {}},
            {"document_id": "doc", "chunk_index": 2, "content": "chunk 2", "metadata": {}},
        ]

        service._attach_context_windows(FakeDB(rows), docs)

        self.assertIn("chunk 0", docs[0]["expanded_content"])
        self.assertIn("chunk 1", docs[0]["expanded_content"])
        self.assertNotIn("chunk 2", docs[0]["expanded_content"])
        self.assertIn("chunk 1", docs[1]["expanded_content"])
        self.assertIn("chunk 2", docs[1]["expanded_content"])

    def test_reranker_parse_failure_falls_back_to_vector_order(self):
        service = RAGService.__new__(RAGService)
        service.reranker_llm = FailingLLM()
        docs = [{"content": f"doc {idx}", "metadata": {}} for idx in range(6)]

        result = asyncio.run(service._rerank_documents("query", docs))

        self.assertEqual(result, docs[:4])

    def test_answer_verifier_requires_flag_and_sources(self):
        service = RAGService.__new__(RAGService)

        service.verifier_mode = "off"
        self.assertFalse(service._answer_verifier_enabled([{"content": "source"}]))

        service.verifier_mode = "on"
        self.assertTrue(service._answer_verifier_enabled([{"content": "source"}]))
        self.assertFalse(service._answer_verifier_enabled([]))

    def test_answer_verifier_rewrites_unsupported_claims(self):
        service = RAGService.__new__(RAGService)
        service.verifier_llm = StaticLLM(
            '{"answer": "이 발췌는 의미 탐색이 고통을 이해하는 한 방식과 관련될 수 있음을 시사합니다 [1](#source-1).", '
            '"changed": true, '
            '"unsupported_claims": ["효과가 있습니다"]}'
        )

        result = asyncio.run(service._verify_answer_against_context(
            query="고통 속에서 의미를 찾고 싶어요.",
            answer="의미 탐색은 반드시 효과가 있습니다 [1](#source-1).",
            context_text="[논문 1] meaning in suffering can be understood as an interpretive resource.",
            sources=[{"title": "Meaning in Suffering", "page_start": 2, "page_end": 2}],
        ))

        self.assertTrue(result["changed"])
        self.assertIn("시사합니다", result["answer"])
        self.assertIn("효과가 있습니다", result["unsupported_claims"][0])

    def test_answer_verifier_failure_falls_back_to_draft_answer(self):
        service = RAGService.__new__(RAGService)
        service.verifier_llm = FailingLLM()
        draft = "이 발췌는 의미 탐색과 관련될 수 있음을 시사합니다 [1](#source-1)."

        result = asyncio.run(service._verify_answer_against_context(
            query="고통 속에서 의미를 찾고 싶어요.",
            answer=draft,
            context_text="[논문 1] meaning in suffering can be understood as an interpretive resource.",
            sources=[{"title": "Meaning in Suffering", "page_start": 2, "page_end": 2}],
        ))

        self.assertFalse(result["changed"])
        self.assertEqual(result["answer"], draft)
        self.assertIn("bad json", result["error"])

    def test_claim_checker_requires_flag_and_sources(self):
        service = RAGService.__new__(RAGService)

        service.claim_checker_mode = "off"
        self.assertFalse(service._claim_checker_enabled([{"content": "source"}]))

        service.claim_checker_mode = "on"
        self.assertTrue(service._claim_checker_enabled([{"content": "source"}]))
        self.assertFalse(service._claim_checker_enabled([]))

    def test_claim_candidate_sentences_prefilters_research_claims(self):
        service = RAGService.__new__(RAGService)
        answer = (
            "많이 외로우셨겠어요.\n"
            "연구에 따르면 관계 욕구는 동기와 관련됩니다 [1](#source-1).\n"
            "오늘 어떤 관계를 원하고 있나요?"
        )

        candidates = service._claim_candidate_sentences(answer)

        self.assertTrue(any("연구에 따르면" in candidate for candidate in candidates))
        self.assertFalse(any("많이 외로우셨겠어요" in candidate for candidate in candidates))

    def test_claim_checker_minimally_rewrites_unsupported_sentence(self):
        service = RAGService.__new__(RAGService)
        service.claim_checker_llm = StaticLLM(
            '{"answer": "많이 외로우셨겠어요.\\n이 발췌는 관계 욕구가 동기와 관련될 수 있음을 시사합니다 [1](#source-1).\\n오늘 어떤 관계를 원하고 있나요?", '
            '"changed": true, '
            '"edits": [{"sentence": "관계 훈련은 외로움을 반드시 줄입니다.", "action": "softened", "reason": "effect was unsupported"}]}'
        )

        result = asyncio.run(service._check_answer_claim_citations(
            query="사람들과 잘 어울리지 못하는 것 같고 늘 외로워요.",
            answer=(
                "많이 외로우셨겠어요.\n"
                "관계 훈련은 외로움을 반드시 줄입니다.\n"
                "오늘 어떤 관계를 원하고 있나요?"
            ),
            context_text="[논문 1] relatedness needs can be associated with motivation and satisfaction.",
            sources=[{"title": "Relatedness", "page_start": 2, "page_end": 2}],
        ))

        self.assertTrue(result["changed"])
        self.assertIn("[1](#source-1)", result["answer"])
        self.assertEqual(result["edits"][0]["action"], "softened")

    def test_claim_checker_failure_falls_back_to_draft_answer(self):
        service = RAGService.__new__(RAGService)
        service.claim_checker_llm = FailingLLM()
        draft = "이 발췌는 관계 욕구가 동기와 관련될 수 있음을 시사합니다 [1](#source-1)."

        result = asyncio.run(service._check_answer_claim_citations(
            query="사람들과 잘 어울리지 못하는 것 같고 늘 외로워요.",
            answer=draft,
            context_text="[논문 1] relatedness needs can be associated with motivation and satisfaction.",
            sources=[{"title": "Relatedness", "page_start": 2, "page_end": 2}],
        ))

        self.assertFalse(result["changed"])
        self.assertEqual(result["answer"], draft)
        self.assertIn("bad json", result["error"])

    def test_grounded_answer_template_requires_sentence_level_citations(self):
        service = RAGService.__new__(RAGService)

        template = service._grounded_answer_template(is_journal=False)

        self.assertIn("전체 답변은 5~7문장", template)
        self.assertIn("한 문장에는 하나의 연구 claim", template)
        self.assertIn("문단 끝 citation은 앞 문장들을 대신 증명하지 않습니다", template)
        self.assertIn("source token: [N](#source-N)", template)
        self.assertIn("고민", template)

    def test_sentence_template_is_feature_flagged(self):
        service = RAGService.__new__(RAGService)

        service.answer_template_mode = "standard"
        self.assertFalse(service._sentence_template_enabled())

        service.answer_template_mode = "sentence"
        self.assertTrue(service._sentence_template_enabled())

    def test_standard_grounding_rules_keep_evidence_to_reflection(self):
        service = RAGService.__new__(RAGService)

        rules = service._standard_grounding_rules(is_journal=False)

        self.assertIn("Evidence-to-Reflection", rules)
        self.assertIn("5~8문장", rules)
        self.assertIn("고민", rules)
        self.assertNotIn("source token", rules)

    def test_grounded_answer_template_uses_journal_scope(self):
        service = RAGService.__new__(RAGService)

        template = service._grounded_answer_template(is_journal=True)

        self.assertIn("사용자의 일기", template)
        self.assertNotIn("사용자의 고민과 감정", template)

    def test_vector_rrf_merge_deduplicates_by_chunk_id(self):
        service = RAGService.__new__(RAGService)
        rankings = [
            [
                {"chunk_id": "a", "id": "a", "content": "a", "similarity": 0.8},
                {"chunk_id": "b", "id": "b", "content": "b", "similarity": 0.7},
            ],
            [
                {"chunk_id": "b", "id": "b", "content": "b stronger", "similarity": 0.9},
                {"chunk_id": "c", "id": "c", "content": "c", "similarity": 0.6},
            ],
        ]

        merged = service._merge_vector_rankings(rankings, limit=3)

        self.assertEqual([doc["chunk_id"] for doc in merged], ["b", "a", "c"])
        self.assertEqual(merged[0]["content"], "b stronger")
        self.assertEqual(len(merged[0]["variant_hits"]), 2)

    def test_focus_boost_promotes_direct_achievement_evidence(self):
        service = RAGService.__new__(RAGService)
        docs = [
            {
                "chunk_id": "generic",
                "document_id": "sdt_generic",
                "content": "Need frustration relates to self-critical perfectionism and ill-being.",
                "rrf_score": 0.03,
                "similarity": 0.9,
            },
            {
                "chunk_id": "direct",
                "document_id": "positive_psych_direct",
                "content": "Gratitude and self-compassion support subjective well-being and accomplishment satisfaction.",
                "rrf_score": 0.015,
                "similarity": 0.7,
            },
            {
                "chunk_id": "keywords",
                "document_id": "positive_psych_keywords",
                "content": "Keywords: wellbeing, flourishing, assessment, positive psychology",
                "rrf_score": 0.02,
                "similarity": 0.8,
            },
        ]

        ranked = service._apply_focus_boosts(
            docs,
            "작은 성취에는 만족하지 못하고 늘 부족하다고 느껴요.",
            ["savoring accomplishments, gratitude, achievement satisfaction, social comparison"],
        )

        self.assertEqual(ranked[0]["chunk_id"], "direct")
        self.assertGreater(ranked[0]["focus_boost"], 0)
        self.assertGreater(ranked[-1]["quality_penalty"], 0)

    def test_quality_penalty_distinguishes_tables_from_citation_rich_text(self):
        service = RAGService.__new__(RAGService)
        item_table = "AC 1 I always stick to my aims. .798 AC 2 I achieve goals. .820 AC 3 .792 AC 4 .810 AC 5 .736 AC 6 .843"
        citation_rich = (
            "Gratitude is recognition of positive things in life (Emmons, 2004). "
            "Self-compassion is a warm and accepting attitude toward oneself "
            "(Neff, 2003; Neff et al., 2007; Gilbert, 2009). "
            "These constructs can be discussed as part of psychological health and adaptive functioning. "
        ) * 2

        self.assertGreater(service._quality_penalty({"content": item_table}), 0)
        self.assertEqual(service._quality_penalty({"content": citation_rich}), 0)

    def test_trace_doc_includes_expanded_context(self):
        service = RAGService.__new__(RAGService)
        traced = service._trace_doc(
            {
                "id": "doc_chunk_0",
                "chunk_id": "doc_chunk_0",
                "content": "primary",
                "expanded_content": "expanded",
                "language": "en",
                "text_quality": 0.9,
            },
            include_expanded=True,
        )

        self.assertEqual(traced["primary_excerpt"], "primary")
        self.assertEqual(traced["expanded_context"], "expanded")
        self.assertEqual(traced["language"], "en")

    def test_query_fallback_replaces_generic_theory_variant(self):
        service = RAGService.__new__(RAGService)
        variants = service._apply_query_fallbacks(
            "작은 성취에는 만족하지 못하고 늘 부족하다고 느껴요.",
            [
                "I feel unsatisfied with small achievements.",
                "achievement dissatisfaction and inadequacy",
                "Maslows Hierarchy of Needs, Cognitive Dissonance Theory",
            ],
        )

        self.assertEqual(len(variants), 3)
        self.assertIn("achievement satisfaction", variants[-1])
        self.assertIn("savoring", variants[-1])
        self.assertIn("social comparison", variants[-1])

    def test_query_fallback_keeps_specific_sdt_variant(self):
        service = RAGService.__new__(RAGService)
        variants = service._apply_query_fallbacks(
            "보상을 받으면 오히려 하던 일에 흥미가 떨어지는 것 같아요.",
            [
                "Rewards reduce my interest.",
                "reward effects and intrinsic motivation",
                "Self-Determination Theory, Overjustification Effect",
            ],
        )

        self.assertEqual(variants[-1], "Self-Determination Theory, Overjustification Effect")

    def test_positive_psych_specific_fallbacks_are_topic_aware(self):
        service = RAGService.__new__(RAGService)

        achievement = service._apply_query_fallbacks(
            "작은 성취에는 만족하지 못하고 늘 부족하다고 느껴요.",
            ["dissatisfied with small achievements", "self-criticism", "positive psychology"],
        )
        hope = service._apply_query_fallbacks(
            "희망을 갖고 싶은데 미래가 자꾸 막막하게 느껴져요.",
            ["future feels overwhelming", "hope and anxiety", "positive psychology, hope theory"],
        )

        self.assertIn("achievement satisfaction", achievement[-1])
        self.assertIn("savoring", achievement[-1])
        self.assertIn("social comparison", achievement[-1])
        self.assertIn("agency thinking", hope[-1])
        self.assertIn("pathways thinking", hope[-1])

    def test_loneliness_query_uses_social_connection_fallback_not_generic_sdt(self):
        service = RAGService.__new__(RAGService)

        variants = service._apply_query_fallbacks(
            "사람들과 잘 어울리지 못하는 것 같아 늘 외로워요.",
            [
                "I feel lonely because I struggle to connect with others.",
                "social isolation, interpersonal relationships, loneliness",
                "autonomy, competence, relatedness, intrinsic motivation",
            ],
        )

        self.assertEqual(service._infer_query_focus("사람들과 잘 어울리지 못하는 것 같아 늘 외로워요."), "positive_psych")
        self.assertIn("social support", variants[-1])
        self.assertIn("peer relations", variants[-1])
        self.assertNotIn("intrinsic motivation", variants[-1])

    def test_loneliness_reranker_guidance_prioritizes_direct_social_evidence(self):
        service = RAGService.__new__(RAGService)

        terms = service._focus_terms_for_query("사람들과 잘 어울리지 못하는 것 같아 늘 외로워요.")
        guidance = service._reranker_focus_guidance("사람들과 잘 어울리지 못하는 것 같아 늘 외로워요.")

        self.assertIn("loneliness", terms)
        self.assertIn("social support", terms)
        self.assertIn("peer relations", terms)
        self.assertIn("directly discuss loneliness", guidance)
        self.assertIn("deprioritize generic SDT motivation", guidance)

    def test_loneliness_answer_guidance_blocks_source_external_advice(self):
        service = RAGService.__new__(RAGService)

        guidance = service._topic_answer_guidance("사람들과 잘 어울리지 못하는 것 같아 늘 외로워요.")

        self.assertIn("외로움/사회적 연결", guidance)
        self.assertIn("사용자의 외로움 원인을 단정하지 마십시오", guidance)
        self.assertIn("총 5문장만 작성하십시오", guidance)
        self.assertIn("검색된 발췌 중 하나는 이 연구 맥락에서", guidance)
        self.assertIn("다른 발췌는 이 표본에서", guidance)
        self.assertIn("표본·맥락", guidance)
        self.assertIn("그래서 지금의 외로움은", guidance)
        self.assertIn("사회적 연결의 필요성을 반영", guidance)
        self.assertIn("가치나 의미를 발견", guidance)
        self.assertIn("작은 변화를 시도", guidance)
        self.assertIn("줄이는 데 중요한 역할", guidance)

    def test_loneliness_reflection_instruction_avoids_meaning_detour(self):
        service = RAGService.__new__(RAGService)

        instruction = service._reflection_instruction("사람들과 잘 어울리지 못하는 것 같아 늘 외로워요.")

        self.assertIn("가치·의미 탐색으로 전환하지 말고", instruction)
        self.assertIn("어떤 관계 상황에서 외로움이 커지는지", instruction)

    def test_gratitude_query_forces_intervention_fallback_over_broad_theory(self):
        service = RAGService.__new__(RAGService)

        variants = service._apply_query_fallbacks(
            "작은 일에도 감사하는 마음을 갖고 싶은데 잘 안 돼요.",
            [
                "I want to cultivate gratitude for small things.",
                "gratitude cultivation and positive psychology",
                "logotherapy, meaning-making, positive psychology",
            ],
        )

        self.assertEqual(service._infer_query_focus("작은 일에도 감사하는 마음을 갖고 싶은데 잘 안 돼요."), "positive_psych")
        self.assertIn("gratitude journal", variants[-1])
        self.assertIn("three good things", variants[-1])
        self.assertIn("subjective well-being", variants[-1])
        self.assertNotIn("logotherapy", variants[-1])

    def test_gratitude_reranker_guidance_prioritizes_intervention_evidence(self):
        service = RAGService.__new__(RAGService)

        terms = service._focus_terms_for_query("작은 일에도 감사하는 마음을 갖고 싶은데 잘 안 돼요.")
        guidance = service._reranker_focus_guidance("작은 일에도 감사하는 마음을 갖고 싶은데 잘 안 돼요.")

        self.assertIn("gratitude journal", terms)
        self.assertIn("three good things", terms)
        self.assertIn("subjective well-being", terms)
        self.assertIn("gratitude interventions", guidance)
        self.assertIn("job-performance-only gratitude chunks", guidance)

    def test_rumination_sleep_query_forces_specific_cbt_fallback(self):
        service = RAGService.__new__(RAGService)

        variants = service._apply_query_fallbacks(
            "지나간 실수를 계속 곱씹으며 잠을 못 자요.",
            [
                "I cant sleep because I keep ruminating on past mistakes.",
                "rumination, sleep disturbances, cognitive behavioral therapy",
                "cognitive distortion, cognitive restructuring, negative automatic thoughts",
            ],
        )

        self.assertEqual(service._infer_query_focus("지나간 실수를 계속 곱씹으며 잠을 못 자요."), "cbt")
        self.assertIn("repetitive negative thinking", variants[-1])
        self.assertIn("rumination-focused CBT", variants[-1])
        self.assertIn("dysfunctional beliefs about sleep", variants[-1])
        self.assertNotIn("negative automatic thoughts", variants[-1])

    def test_plain_mistake_cbt_query_does_not_trigger_rumination_fallback(self):
        service = RAGService.__new__(RAGService)

        variants = service._apply_query_fallbacks(
            "한 번 실수하면 나는 항상 무능하다는 생각이 들어요.",
            [
                "I feel incompetent whenever I make a mistake.",
                "cognitive distortions, self-efficacy, negative self-talk",
                "cognitive distortion, cognitive restructuring, negative automatic thoughts",
            ],
        )

        self.assertIn("negative automatic thoughts", variants[-1])
        self.assertNotIn("rumination-focused CBT", variants[-1])

    def test_social_evaluation_query_forces_specific_cbt_fallback(self):
        service = RAGService.__new__(RAGService)

        variants = service._apply_query_fallbacks(
            "남들이 저를 어떻게 볼지 늘 신경 쓰이고 불안해요.",
            [
                "I constantly worry about how others perceive me and feel anxious about it.",
                "social anxiety, self-perception, interpersonal relationships",
                "cognitive distortion, cognitive restructuring, catastrophizing, negative automatic thoughts",
            ],
        )

        self.assertEqual(service._infer_query_focus("남들이 저를 어떻게 볼지 늘 신경 쓰이고 불안해요."), "cbt")
        self.assertEqual(service._cbt_topic("남들이 저를 어떻게 볼지 늘 신경 쓰이고 불안해요.", variants), "social_evaluation")
        self.assertIn("fear of negative evaluation", variants[-1])
        self.assertIn("mind reading", variants[-1])
        self.assertIn("self-focused attention", variants[-1])
        self.assertIn("maladaptive thoughts about how others judge them", variants[-1])
        self.assertIn("misinterpretation of social experiences", variants[-1])
        self.assertNotIn("negative automatic thoughts", variants[-1])

    def test_social_evaluation_focus_boost_prefers_direct_social_anxiety_evidence(self):
        service = RAGService.__new__(RAGService)
        docs = [
            {
                "chunk_id": "generic",
                "document_id": "cbt_generic",
                "content": "CBT identifies cognitive distortions and negative automatic thoughts.",
                "rrf_score": 0.03,
                "similarity": 0.9,
            },
            {
                "chunk_id": "direct",
                "document_id": "cbt_social",
                "content": (
                    "Social anxiety involves fear of negative evaluation and mind reading about "
                    "being judged by others in social situations."
                ),
                "rrf_score": 0.015,
                "similarity": 0.7,
            },
        ]

        ranked = service._apply_focus_boosts(
            docs,
            "남들이 저를 어떻게 볼지 늘 신경 쓰이고 불안해요.",
            ["social anxiety, self-perception, interpersonal relationships"],
        )

        self.assertEqual(ranked[0]["chunk_id"], "direct")
        self.assertGreater(ranked[0]["focus_boost"], ranked[1]["focus_boost"])

    def test_social_evaluation_reranker_guidance_prioritizes_judgment_fear(self):
        service = RAGService.__new__(RAGService)

        terms = service._focus_terms_for_query(
            "남들이 저를 어떻게 볼지 늘 신경 쓰이고 불안해요.",
            ["social anxiety, self-perception, interpersonal relationships"],
        )
        guidance = service._reranker_focus_guidance(
            "남들이 저를 어떻게 볼지 늘 신경 쓰이고 불안해요.",
            ["social anxiety, self-perception, interpersonal relationships"],
        )

        self.assertIn("fear of negative evaluation", terms)
        self.assertIn("maladaptive thoughts", terms)
        self.assertIn("how others judge", terms)
        self.assertIn("cognitive errors", terms)
        self.assertIn("others' evaluations", terms)
        self.assertIn("mind-reading and fortune-telling", terms)
        self.assertIn("mind reading", terms)
        self.assertIn("self-focused attention", terms)
        self.assertIn("being judged by others", guidance)
        self.assertIn("preconceptions about others' evaluations", guidance)
        self.assertIn("session agenda/protocol fragments", guidance)
        self.assertIn("Deprioritize generic CBT", guidance)

    def test_grief_loss_query_forces_specific_logotherapy_fallback(self):
        service = RAGService.__new__(RAGService)

        variants = service._apply_query_fallbacks(
            "가까운 사람을 떠나보낸 뒤로 살아갈 이유를 찾기 어려워요.",
            [
                "I find it hard to find a reason to live after losing someone close to me.",
                "existential crisis, grief, meaning-making, loss of a loved one",
                "logotherapy, meaning in suffering, Viktor Frankls theory of meaning",
            ],
        )

        self.assertEqual(service._infer_query_focus("가까운 사람을 떠나보낸 뒤로 살아갈 이유를 찾기 어려워요."), "logotherapy")
        self.assertEqual(service._logotherapy_topic("가까운 사람을 떠나보낸 뒤로 살아갈 이유를 찾기 어려워요.", variants), "grief_loss")
        self.assertIn("bereavement", variants[-1])
        self.assertIn("death of the next of kin", variants[-1])
        self.assertIn("meaning reconstruction", variants[-1])
        self.assertIn("continuing bonds", variants[-1])
        self.assertIn("responding to values", variants[-1])
        self.assertNotIn("attitudinal values", variants[-1])

    def test_grief_loss_focus_boost_prefers_bereavement_evidence(self):
        service = RAGService.__new__(RAGService)
        docs = [
            {
                "chunk_id": "generic",
                "document_id": "logotherapy_generic",
                "content": "Frankl's logotherapy emphasizes meaning in suffering and existential meaning.",
                "rrf_score": 0.03,
                "similarity": 0.9,
            },
            {
                "chunk_id": "direct",
                "document_id": "logotherapy_grief",
                "content": (
                    "We mourn the deaths of our loved ones, and grief can create a crisis "
                    "of meaning. Meaning-making after loss can have a relational nature."
                ),
                "rrf_score": 0.015,
                "similarity": 0.7,
            },
        ]

        ranked = service._apply_focus_boosts(
            docs,
            "가까운 사람을 떠나보낸 뒤로 살아갈 이유를 찾기 어려워요.",
            ["grief, bereavement, meaning reconstruction, continuing bonds"],
        )

        self.assertEqual(ranked[0]["chunk_id"], "direct")
        self.assertGreater(ranked[0]["focus_boost"], ranked[1]["focus_boost"])

    def test_grief_loss_answer_guidance_blocks_premature_lessons(self):
        service = RAGService.__new__(RAGService)

        guidance = service._topic_answer_guidance(
            "가까운 사람을 떠나보낸 뒤로 살아갈 이유를 찾기 어려워요.",
            ["grief, bereavement, meaning reconstruction, continuing bonds"],
        )
        reflection = service._reflection_instruction(
            "가까운 사람을 떠나보낸 뒤로 살아갈 이유를 찾기 어려워요.",
            ["grief, bereavement, meaning reconstruction, continuing bonds"],
        )

        self.assertIn("상실/애도", guidance)
        self.assertIn("고통이 기회", guidance)
        self.assertIn("배운 것은 무엇", guidance)
        self.assertIn("관계에서 아직 마음에 남아 있는 의미", guidance)
        self.assertIn("death of the next of kin", service._reranker_focus_guidance(
            "가까운 사람을 떠나보낸 뒤로 살아갈 이유를 찾기 어려워요.",
            ["grief, bereavement, meaning reconstruction, continuing bonds"],
        ))
        self.assertIn("교훈, 성장, 새로운 목적 찾기", reflection)

    def test_grief_loss_companion_replaces_less_direct_last_source(self):
        service = RAGService.__new__(RAGService)
        selected = [
            {
                "chunk_id": "paper_a_chunk_23",
                "document_id": "paper_a",
                "chunk_index": 23,
                "content": "We mourn the deaths of our loved ones and face a crisis of meaning.",
            },
            {
                "chunk_id": "paper_b_chunk_1",
                "document_id": "paper_b",
                "chunk_index": 1,
                "content": "Meaning-oriented care can support loss experiences.",
            },
            {
                "chunk_id": "paper_a_chunk_53",
                "document_id": "paper_a",
                "chunk_index": 53,
                "content": "The death of a loved one can affect meaningfulness.",
            },
            {
                "chunk_id": "paper_c_chunk_24",
                "document_id": "paper_c",
                "chunk_index": 24,
                "content": "Patients with family members may find meaning in care.",
            },
        ]
        candidates = [
            *selected,
            {
                "chunk_id": "paper_a_chunk_24",
                "document_id": "paper_a",
                "chunk_index": 24,
                "ranking_score": 0.07,
                "content": (
                    "Deep suffering can inflict a crisis of meaning and a need for "
                    "meaning-making in one's personal sense of meaningfulness."
                ),
            },
        ]

        reinforced = service._reinforce_grief_loss_companion(
            selected,
            candidates,
            "가까운 사람을 떠나보낸 뒤로 살아갈 이유를 찾기 어려워요.",
            ["grief, bereavement, meaning reconstruction, continuing bonds"],
        )

        self.assertEqual([doc["chunk_id"] for doc in reinforced], [
            "paper_a_chunk_23",
            "paper_b_chunk_1",
            "paper_a_chunk_53",
            "paper_a_chunk_24",
        ])

    def test_rumination_sleep_focus_boost_prefers_direct_rumination_evidence(self):
        service = RAGService.__new__(RAGService)
        docs = [
            {
                "chunk_id": "generic",
                "document_id": "cbt_generic",
                "content": "CBT identifies cognitive distortions and reframes systematic errors in thinking.",
                "rrf_score": 0.03,
                "similarity": 0.9,
            },
            {
                "chunk_id": "direct",
                "document_id": "cbt_direct",
                "content": (
                    "Rumination-focused CBT was designed to reduce ruminative habits and repetitive "
                    "negative thinking through cognitive restructuring and behavioral tests."
                ),
                "rrf_score": 0.015,
                "similarity": 0.7,
            },
            {
                "chunk_id": "sleep",
                "document_id": "cbt_sleep",
                "content": (
                    "In a cognitive model of insomnia, thinking repetitively about possible "
                    "sleep deficiencies contributes to arousal and distress and monitoring "
                    "of sleep-related threats."
                ),
                "rrf_score": 0.014,
                "similarity": 0.7,
            },
            {
                "chunk_id": "sleep_generic",
                "document_id": "cbt_sleep_generic",
                "content": "Dysfunctional beliefs about sleep and CBT-I are discussed in insomnia treatment.",
                "rrf_score": 0.02,
                "similarity": 0.8,
            },
        ]

        ranked = service._apply_focus_boosts(
            docs,
            "지나간 실수를 계속 곱씹으며 잠을 못 자요.",
            ["rumination, sleep disturbances, cognitive behavioral therapy"],
        )

        self.assertEqual(ranked[0]["chunk_id"], "direct")
        self.assertGreater(ranked[0]["focus_boost"], docs[0].get("focus_boost", 0))
        self.assertGreater(
            next(doc for doc in ranked if doc["chunk_id"] == "sleep")["focus_boost"],
            next(doc for doc in ranked if doc["chunk_id"] == "sleep_generic")["focus_boost"],
        )

    def test_rumination_sleep_reranker_guidance_separates_sleep_scope(self):
        service = RAGService.__new__(RAGService)

        terms = service._focus_terms_for_query("지나간 실수를 계속 곱씹으며 잠을 못 자요.")
        guidance = service._reranker_focus_guidance("지나간 실수를 계속 곱씹으며 잠을 못 자요.")

        self.assertIn("rumination-focused CBT", terms)
        self.assertIn("thinking repetitively", terms)
        self.assertIn("sleep-related threats", terms)
        self.assertIn("directly discuss rumination", guidance)
        self.assertIn("repetitive thinking", guidance)
        self.assertIn("select one such sleep-specific", guidance)
        self.assertIn("deprioritize sleep chunks that only mention dysfunctional beliefs", guidance)
        self.assertIn("table/theme-code fragments", guidance)
        self.assertIn("sleep/insomnia claims clearly scoped", guidance)
        self.assertIn("generic CBT introductions", guidance)

    def test_quality_penalty_detects_theme_code_table_fragments(self):
        service = RAGService.__new__(RAGService)

        penalty = service._quality_penalty({
            "content": (
                "Table 1 Themes, Subthemes, and Concepts of Relapse Indicators. "
                "Category (Main Theme) Subcategory Concepts (Open Codes) emotional triggers "
                "cognitive triggers behavioral indicators social factors."
            )
        })

        self.assertGreaterEqual(penalty, 0.037)

    def test_quality_penalty_detects_session_protocol_fragments(self):
        service = RAGService.__new__(RAGService)

        penalty = service._quality_penalty({
            "content": (
                "Homework review and a summary review of the previous session. "
                "Relaxation exercise through guided imagery. Receiving feedback and "
                "summarizing the meeting."
            )
        })

        self.assertGreaterEqual(penalty, 0.02)

    def test_rumination_sleep_answer_guidance_blocks_unbacked_meaning_and_journaling(self):
        service = RAGService.__new__(RAGService)

        guidance = service._topic_answer_guidance(
            "지나간 실수를 계속 곱씹으며 잠을 못 자요.",
            ["rumination, sleep disturbances, cognitive behavioral therapy"],
        )
        generic_guidance = service._topic_answer_guidance(
            "한 번 실수하면 나는 항상 무능하다는 생각이 들어요.",
            ["cognitive distortions, self-efficacy, negative self-talk"],
        )

        self.assertIn("반추/수면", guidance)
        self.assertIn("일기 쓰기", guidance)
        self.assertIn("의미 찾기", guidance)
        self.assertIn("배운 점", guidance)
        self.assertIn("긍정적인 측면", guidance)
        self.assertIn("이 섹션은 위의 일반 상담 원칙보다 우선합니다", guidance)
        self.assertIn("직접 원인-효과 사슬로 합치지 마십시오", guidance)
        self.assertIn("주요 원인", guidance)
        self.assertIn("수면의 질을 떨어뜨린다", guidance)
        self.assertIn("도움을 줄 수", guidance)
        self.assertIn("효과적", guidance)
        self.assertIn("이 발췌만으로는 직접 원인을 확인하기 어렵다", guidance)
        self.assertIn("인지 오류가 섞여 있나요", guidance)
        self.assertIn("수면을 다룰 때는 과거 실수 반추와 수면을 직접 연결하지 말고", guidance)
        self.assertIn("반복적인 수면 걱정", guidance)
        self.assertIn("수면 문제를 악화", guidance)
        self.assertEqual(generic_guidance, "")

    def test_rumination_sleep_reflection_instruction_avoids_logotherapy_detour(self):
        service = RAGService.__new__(RAGService)

        instruction = service._reflection_instruction(
            "지나간 실수를 계속 곱씹으며 잠을 못 자요.",
            ["rumination, sleep disturbances, cognitive behavioral therapy"],
        )
        generic_instruction = service._reflection_instruction(
            "한 번 실수하면 나는 항상 무능하다는 생각이 들어요.",
            ["cognitive distortions, self-efficacy, negative self-talk"],
        )

        self.assertIn("인지 오류 가능성", instruction)
        self.assertIn("가치·의미·교훈 탐색으로 전환하지 말고", instruction)
        self.assertIn("가치와 의미", generic_instruction)

    def test_competence_query_forces_specific_sdt_fallback(self):
        service = RAGService.__new__(RAGService)

        variants = service._apply_query_fallbacks(
            "유능하다는 느낌을 받고 싶은데 늘 제가 부족해 보여요.",
            [
                "I want to feel competent, but I always feel inadequate.",
                "competence, self-efficacy, self-esteem, feelings of inadequacy",
                "Self-Determination Theory, Cognitive Behavioral Therapy (CBT)",
            ],
        )

        self.assertEqual(service._infer_query_focus("유능하다는 느낌을 받고 싶은데 늘 제가 부족해 보여요."), "sdt")
        self.assertEqual(service._sdt_topic("유능하다는 느낌을 받고 싶은데 늘 제가 부족해 보여요."), "competence_inadequacy")
        self.assertIn("perceived competence", variants[-1])
        self.assertIn("challenging but achievable tasks", variants[-1])
        self.assertIn("positive feedback", variants[-1])
        self.assertNotIn("Cognitive Behavioral Therapy", variants[-1])

    def test_competence_focus_boost_prefers_direct_competence_support(self):
        service = RAGService.__new__(RAGService)
        docs = [
            {
                "chunk_id": "generic",
                "document_id": "sdt_generic",
                "content": "Autonomy and relatedness can support motivation in self-determination theory.",
                "rrf_score": 0.03,
                "similarity": 0.9,
            },
            {
                "chunk_id": "direct",
                "document_id": "sdt_direct",
                "content": (
                    "Perceived competence can be supported by challenging but achievable tasks "
                    "and positive feedback that helps people feel effective."
                ),
                "rrf_score": 0.015,
                "similarity": 0.7,
            },
        ]

        ranked = service._apply_focus_boosts(
            docs,
            "유능하다는 느낌을 받고 싶은데 늘 제가 부족해 보여요.",
            ["competence, self-efficacy, self-esteem, feelings of inadequacy"],
        )

        self.assertEqual(ranked[0]["chunk_id"], "direct")
        self.assertGreater(ranked[0]["focus_boost"], ranked[1]["focus_boost"])

    def test_focus_boost_uses_matching_corpus_prefix(self):
        service = RAGService.__new__(RAGService)
        shared_content = "Perceived competence and positive feedback can support a feeling of competence."
        docs = [
            {
                "chunk_id": "sdt",
                "document_id": "sdt_direct",
                "content": shared_content,
                "rrf_score": 0.02,
                "similarity": 0.8,
            },
            {
                "chunk_id": "positive",
                "document_id": "positive_psych_overlap",
                "content": shared_content,
                "rrf_score": 0.02,
                "similarity": 0.8,
            },
        ]

        ranked = service._apply_focus_boosts(
            docs,
            "유능하다는 느낌을 받고 싶은데 늘 제가 부족해 보여요.",
            ["competence, self-efficacy, self-esteem, feelings of inadequacy"],
        )

        self.assertEqual(ranked[0]["chunk_id"], "sdt")
        self.assertGreater(ranked[0]["focus_boost"], ranked[1]["focus_boost"])

    def test_competence_reranker_guidance_prioritizes_direct_need_evidence(self):
        service = RAGService.__new__(RAGService)

        terms = service._focus_terms_for_query(
            "유능하다는 느낌을 받고 싶은데 늘 제가 부족해 보여요.",
            ["competence, self-efficacy, self-esteem, feelings of inadequacy"],
        )
        guidance = service._reranker_focus_guidance(
            "유능하다는 느낌을 받고 싶은데 늘 제가 부족해 보여요.",
            ["competence, self-efficacy, self-esteem, feelings of inadequacy"],
        )

        self.assertIn("perceived competence", terms)
        self.assertIn("challenging but achievable", terms)
        self.assertIn("positive feedback", terms)
        self.assertIn("need for competence", guidance)
        self.assertIn("Deprioritize generic autonomy/reward/relatedness chunks", guidance)

    def test_competence_answer_guidance_blocks_causal_diagnosis(self):
        service = RAGService.__new__(RAGService)

        guidance = service._topic_answer_guidance(
            "유능하다는 느낌을 받고 싶은데 늘 제가 부족해 보여요.",
            ["competence, self-efficacy, self-esteem, feelings of inadequacy"],
        )
        generic_guidance = service._topic_answer_guidance(
            "보상을 받으면 오히려 하던 일에 흥미가 떨어지는 것 같아요.",
            ["reward effects and intrinsic motivation"],
        )

        self.assertIn("유능감", guidance)
        self.assertIn("원인을", guidance)
        self.assertIn("진단하지 마십시오", guidance)
        self.assertIn("일반적 효과나 확실한 개선", guidance)
        self.assertIn("이 섹션은 위의 일반 상담 원칙보다 우선합니다", guidance)
        self.assertIn("총 5문장만 작성하십시오", guidance)
        self.assertIn("검색된 발췌에서 유능감은", guidance)
        self.assertIn("또 다른 발췌는", guidance)
        self.assertIn("그래서 지금의 부족감은", guidance)
        self.assertIn("[1](#source-1)", guidance)
        self.assertIn("(논문 1)", guidance)
        self.assertIn("감정이 메시지를 준다", guidance)
        self.assertIn("작은 성공/작은 목표", guidance)
        self.assertIn("떠올려 보세요", guidance)
        self.assertIn("도움이 될 수 있습니다", guidance)
        self.assertIn("어떤 피드백이나 지원", guidance)
        self.assertIn("더 나은 성과", guidance)
        self.assertIn("자신에 대한 믿음이 커진다", guidance)
        self.assertIn("질문으로만", guidance)
        self.assertEqual(generic_guidance, "")

    def test_competence_reflection_instruction_avoids_meaning_detour(self):
        service = RAGService.__new__(RAGService)

        instruction = service._reflection_instruction(
            "유능하다는 느낌을 받고 싶은데 늘 제가 부족해 보여요.",
            ["competence, self-efficacy, self-esteem, feelings of inadequacy"],
        )
        generic_instruction = service._reflection_instruction(
            "보상을 받으면 오히려 하던 일에 흥미가 떨어지는 것 같아요.",
            ["reward effects and intrinsic motivation"],
        )

        self.assertIn("부족감의 의미·메시지·교훈을 묻지 말고", instruction)
        self.assertIn("과제가 너무 어렵거나 지원이 부족한 지점", instruction)
        self.assertIn("직접 지시형 실천 제안", instruction)
        self.assertIn("가치와 의미", generic_instruction)

    def test_reranker_guidance_prioritizes_achievement_constructs(self):
        service = RAGService.__new__(RAGService)
        guidance = service._reranker_focus_guidance(
            "작은 성취에는 만족하지 못하고 늘 부족하다고 느껴요.",
            [
                "dissatisfied with small achievements",
                "self-criticism",
                "savoring accomplishments, gratitude, achievement satisfaction, social comparison",
            ],
        )

        self.assertIn("savoring accomplishments", guidance)
        self.assertIn("social comparison", guidance)
        self.assertIn("Deprioritize generic motivation", guidance)

    def test_reranker_guidance_deprioritizes_reference_lists_for_burnout(self):
        service = RAGService.__new__(RAGService)
        guidance = service._reranker_focus_guidance(
            "번아웃이 와서 무기력한데 어떻게 회복할 수 있을까요?",
            ["burnout intervention", "positive psychology intervention"],
        )

        self.assertIn("burnout interventions", guidance)
        self.assertIn("only list references", guidance)

    def test_problem_qrels_candidate_merge_prioritizes_grade2_and_trace(self):
        merged = refresh_problem_qrels.merge_candidate_ids(
            vector_ids=["v1", "v2", "g2", "trace"],
            existing_qrels={"g1": 1, "g2": 2, "g3": 2},
            trace_ids=["trace", "g1"],
            max_candidates=5,
        )

        self.assertEqual(merged, ["g2", "g3", "trace", "g1", "v1"])

    def test_problem_qrels_rules_are_case_specific(self):
        g11 = refresh_problem_qrels._case_specific_rules("g11")
        g12 = refresh_problem_qrels._case_specific_rules("g12")
        g27 = refresh_problem_qrels._case_specific_rules("g27")

        self.assertIn("death/finitude/aging", g11)
        self.assertIn("Generic logotherapy", g11)
        self.assertIn("bereavement", g12)
        self.assertIn("Generic suffering/meaning/logotherapy", g12)
        self.assertIn("social-evaluative", g27)

    def test_problem_qrels_quality_flags_detect_noisy_chunks(self):
        noisy = {
            "content": (
                "sociais e econômicos. A finitude da vida gera um sentimento de medo "
                "e ansiedade nos indivíduos. Porém, também aponta que o sentido da vida "
                "com sofrimento e morte pode aparecer em alguns textos."
            ),
            "text_quality": 0.72,
        }
        table = {
            "content": "Table 1 Study outcome Intervention Measure " * 8,
            "text_quality": 0.95,
        }

        self.assertIn("probable_non_english", refresh_problem_qrels._quality_flags(noisy))
        self.assertIn("low_text_quality", refresh_problem_qrels._quality_flags(noisy))
        self.assertIn("table_fragment", refresh_problem_qrels._quality_flags(table))

    def test_existing_qrel_ids_excludes_missing_current_chunks(self):
        db = FakeDB([
            {"chunk_id": "a", "document_id": "doc", "chunk_index": 0},
            {"chunk_id": "c", "document_id": "doc", "chunk_index": 1},
        ])
        existing, missing = evaluate_retrieval._existing_qrel_ids(
            db,
            {"g01": {"a": 2, "b": 2}, "g02": {"c": 1}},
        )

        self.assertEqual(existing, {"a", "c"})
        self.assertEqual(missing, 1)


if __name__ == "__main__":
    unittest.main()
