import os
import json
import datetime
from pymongo import MongoClient
from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from typing import AsyncGenerator
from models.chat import ChatSource
from services.safety import detect_crisis
from services.encryption import encrypt, decrypt
from services.observability import log_event, safe_hash
from db import get_db

class RAGService:
    def __init__(self):
        # OpenAI LLM 및 임베딩 로드
        import torch
        if torch.cuda.is_available():
            device = "cuda"
        elif torch.backends.mps.is_available():
            device = "mps"
        else:
            device = "cpu"
        self.embeddings = HuggingFaceEmbeddings(
            model_name="BAAI/bge-m3",
            model_kwargs={"device": device}
        )
        
        # 스트리밍을 지원하는 LLM 인스턴스 생성
        self.llm = ChatOpenAI(
            model_name="gpt-4o-mini",
            temperature=0.3,
            streaming=True
        )
        self.reranker_llm = ChatOpenAI(
            model_name="gpt-4o-mini",
            temperature=0.0,
            streaming=False
        )
        self.query_llm = ChatOpenAI(
            model_name="gpt-4o-mini",
            temperature=0.0,
            streaming=False
        )
        self.answer_llm = ChatOpenAI(
            model_name="gpt-4o-mini",
            temperature=0.0,
            streaming=True
        )
        self.answer_review_llm = ChatOpenAI(
            model_name="gpt-4o-mini",
            temperature=0.0,
            streaming=False
        )
        self.verifier_llm = ChatOpenAI(
            model_name="gpt-4o-mini",
            temperature=0.0,
            streaming=False
        )
        self.claim_checker_llm = ChatOpenAI(
            model_name="gpt-4o-mini",
            temperature=0.0,
            streaming=False
        )
        self.reranker_mode = os.getenv("RERANKER_MODE", "llm").strip().lower()
        self.verifier_mode = os.getenv("RAG_VERIFIER_MODE", "off").strip().lower()
        self.claim_checker_mode = os.getenv("RAG_CLAIM_CHECKER_MODE", "off").strip().lower()
        self.answer_template_mode = os.getenv("RAG_ANSWER_TEMPLATE_MODE", "standard").strip().lower()
        self.cross_encoder = None
        self.last_retrieval_trace = {}
        self.last_generation_trace = {}

    async def _expand_query(self, query: str) -> str:
        variants = await self._expand_query_variants(query)
        return variants[0] if variants else query

    async def _expand_query_variants(self, query: str, primary: str = None) -> list[str]:
        """
        Produce deterministic English vector-search variants:
        user concern, academic keywords, and framework/theory phrasing.
        """
        try:
            system_prompt = (
                "You are an academic search query optimization assistant.\n"
                "Translate the user's Korean psychological concern to English if needed and create up to 3 search variants.\n"
                "Variant 1: a natural user concern sentence.\n"
                "Variant 2: academic keywords and constructs.\n"
                "Variant 3: relevant psychology theories/frameworks when applicable.\n"
                "Prefer specific constructs from logotherapy, positive psychology, CBT, or self-determination theory.\n"
                "Avoid broad filler theories such as Maslow's hierarchy unless the user explicitly asks about it.\n"
                "Output ONLY raw JSON: {\"variants\": [\"...\", \"...\", \"...\"]}.\n"
                "Do not include Korean, markdown, explanations, or more than 3 variants."
            )
            prompt = query if not primary else f"Original query: {query}\nPrimary English query: {primary}"
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ]

            response = await self.query_llm.ainvoke(messages, response_format={"type": "json_object"})
            data = json.loads(response.content.strip())
            raw_variants = data.get("variants", [])
            if isinstance(raw_variants, str):
                raw_variants = [raw_variants]

            variants = []
            for item in raw_variants:
                if not isinstance(item, str):
                    continue
                cleaned = item.strip().replace('"', "").replace("'", "")
                if cleaned and cleaned not in variants:
                    variants.append(cleaned)
                if len(variants) >= 3:
                    break

            if not variants:
                variants = [primary or query]
            variants = self._apply_query_fallbacks(query, variants)

            log_event("rag_query_expanded", variant_count=len(variants))
            return variants
        except Exception as e:
            log_event("rag_query_expansion_error", level="warning", error_type=type(e).__name__)
            return self._apply_query_fallbacks(query, [primary or query])

    def _infer_query_focus(self, query: str, variants: list[str] = None) -> str:
        original = (query or "").lower()
        original_terms = [
            ("cbt", ["부정", "왜곡", "최악", "실수", "무능", "실패", "완벽", "곱씹", "불안", "인지"]),
            ("positive_psych", ["행복", "감사", "번아웃", "무기력", "성취", "만족", "희망", "강점", "몰입", "외로", "고립", "어울리지", "소외", "소속"]),
            ("sdt", ["동기", "의욕", "자율", "보상", "유능", "시켜서", "공부", "운동"]),
            ("logotherapy", ["의미", "공허", "고통", "죽음", "은퇴", "상실", "떠나보낸", "떠나 보낸", "사별", "애도", "쓸모", "병", "허무"]),
        ]
        for focus, terms in original_terms:
            if any(term in original for term in terms):
                return focus

        text = " ".join([query or "", *(variants or [])]).lower()
        focus_terms = [
            ("cbt", [
                "부정", "왜곡", "최악", "실수", "무능", "실패", "완벽", "곱씹", "불안", "인지",
                "negative thinking", "cognitive distortion", "cognitive restructuring",
                "catastrophizing", "automatic thoughts", "rumination", "perfectionism",
            ]),
            ("positive_psych", [
                "행복", "감사", "번아웃", "무기력", "성취", "희망", "강점", "몰입", "관계", "외로", "고립", "소외", "소속",
                "happiness", "gratitude", "burnout", "well-being", "perma", "savoring",
                "hope", "engagement", "flourishing", "positive psychology", "loneliness",
                "lonely", "social isolation", "social connection", "social support", "belonging",
            ]),
            ("sdt", [
                "동기", "의욕", "자율", "보상", "유능", "시켜서", "공부", "운동",
                "autonomy", "competence", "relatedness", "intrinsic motivation",
                "extrinsic motivation", "controlling rewards", "self-determination",
            ]),
            ("logotherapy", [
                "의미", "공허", "고통", "죽음", "은퇴", "상실", "쓸모", "병", "허무",
                "meaning in life", "existential", "logotherapy", "frankl", "suffering",
                "attitudinal values", "human worth", "grief", "bereavement", "mourning",
                "loss of a loved one", "death of a loved one", "meaning reconstruction",
                "meaning-making after loss", "continuing bonds",
            ]),
        ]
        for focus, terms in focus_terms:
            if any(term in text for term in terms):
                return focus
        return ""

    def _positive_psych_topic(self, query: str) -> str:
        query = (query or "").lower()
        if any(term in query for term in ("외로", "고립", "어울리지", "소외", "소속", "lonely", "loneliness", "social isolation")):
            return "loneliness"
        if any(term in query for term in ("감사", "gratitude", "grateful", "thankful")):
            return "gratitude"
        if any(term in query for term in ("성취", "만족", "부족")):
            return "achievement"
        if "희망" in query:
            return "hope"
        if any(term in query for term in ("번아웃", "무기력")):
            return "burnout"
        if "행복" in query:
            return "happiness"
        return ""

    def _cbt_topic(self, query: str, query_variants: list[str] = None) -> str:
        text = " ".join([query or "", *(query_variants or [])]).lower()
        social_eval_terms = (
            "남들", "다른 사람", "어떻게 볼", "시선", "평가", "판단", "눈치", "신경 쓰",
            "사회불안", "social anxiety", "fear of negative evaluation", "negative judgment",
            "being judged", "judged by others", "how others perceive", "others perceive me",
            "mind reading", "self-focused attention", "social-evaluative", "social situations",
        )
        if any(term in text for term in social_eval_terms):
            return "social_evaluation"

        rumination_terms = (
            "곱씹", "반추", "rumination", "ruminating", "ruminative",
            "repetitive negative thinking",
        )
        sleep_terms = ("잠", "수면", "sleep", "insomnia")
        if any(term in text for term in rumination_terms) and any(term in text for term in sleep_terms):
            return "rumination_sleep"
        if any(term in text for term in rumination_terms):
            return "rumination"
        return ""

    def _sdt_topic(self, query: str, query_variants: list[str] = None) -> str:
        original = (query or "").lower()
        if any(term in original for term in ("유능", "유능감", "무능")):
            return "competence_inadequacy"

        text = " ".join([query or "", *(query_variants or [])]).lower()
        direct_competence_terms = (
            "inadequate", "inadequacy", "self-efficacy", "perceived competence",
            "competence satisfaction", "need for competence", "mastery",
        )
        if any(term in text for term in direct_competence_terms):
            return "competence_inadequacy"
        if "competent" in text and any(term in text for term in ("inadequate", "self-efficacy", "mastery")):
            return "competence_inadequacy"
        return ""

    def _logotherapy_topic(self, query: str, query_variants: list[str] = None) -> str:
        text = " ".join([query or "", *(query_variants or [])]).lower()
        grief_terms = (
            "떠나보낸", "떠나 보낸", "잃", "상실", "사별", "애도", "고인",
            "가까운 사람", "사랑하는 사람", "grief", "bereavement", "mourning",
            "loss of a loved one", "death of a loved one", "deaths of our loved ones",
            "meaning reconstruction", "meaning-making after loss", "meaning making after loss",
            "continuing bonds",
        )
        if any(term in text for term in grief_terms):
            return "grief_loss"
        return ""

    def _fallback_query_variant(self, focus: str, query: str = "") -> str:
        topic = self._positive_psych_topic(query)
        if focus == "positive_psych":
            if topic == "loneliness":
                return "loneliness, social isolation, social connection, social support, belonging, peer relations, interpersonal relationships, positive psychology"
            if topic == "gratitude":
                return "gratitude intervention, gratitude journal, three good things, gratitude letter, gratitude visit, subjective well-being, positive affect, positive psychology"
            if topic == "achievement":
                return "social comparison, achievement satisfaction, gratitude, savoring, self-compassion, positive psychology"
            if topic == "hope":
                return "hope theory, agency thinking, pathways thinking, goals, future anxiety, positive psychology"
            if topic == "burnout":
                return "burnout intervention, positive psychology intervention, work engagement, meaning, well-being"
            if topic == "happiness":
                return "PERMA, subjective well-being, positive psychology interventions, happiness, flourishing"
        if focus == "cbt":
            cbt_topic = self._cbt_topic(query)
            if cbt_topic == "social_evaluation":
                return "social anxiety, fear of negative evaluation, fear of negative judgment from others, maladaptive thoughts about how others judge them, cognitive errors, misinterpretation of social experiences, mind reading, self-focused attention, Socratic questioning, reality testing"
            if cbt_topic == "rumination_sleep":
                return "rumination, repetitive negative thinking, worry, rumination-focused CBT, cognitive restructuring, insomnia, sleep disturbance, dysfunctional beliefs about sleep, CBT-I"
            if cbt_topic == "rumination":
                return "rumination, repetitive negative thinking, worry, rumination-focused CBT, cognitive restructuring, cognitive behavioral therapy"
        if focus == "sdt":
            sdt_topic = self._sdt_topic(query)
            if sdt_topic == "competence_inadequacy":
                return "competence need satisfaction, perceived competence, need for competence, mastery experiences, optimal challenge, challenging but achievable tasks, positive feedback, self-efficacy, self-determination theory"
        if focus == "logotherapy":
            logotherapy_topic = self._logotherapy_topic(query)
            if logotherapy_topic == "grief_loss":
                return "grief, bereavement, mourning, death of a loved one, death of the next of kin, loss of a loved one, meaning reconstruction, meaning-making after loss, continuing bonds, relational meaning, responding to values, logotherapy"
        fallbacks = {
            "logotherapy": "attitudinal values, meaning in suffering, illness and meaning, human worth beyond productivity, logotherapy",
            "positive_psych": "PERMA, savoring, gratitude, hope theory, burnout intervention, well-being intervention, positive psychology",
            "cbt": "cognitive distortion, cognitive restructuring, catastrophizing, negative automatic thoughts, cognitive behavioral therapy",
            "sdt": "autonomy, competence, relatedness, intrinsic motivation, controlling rewards, self-determination theory",
        }
        return fallbacks.get(focus, "")

    def _apply_query_fallbacks(self, query: str, variants: list[str]) -> list[str]:
        cleaned = []
        for variant in variants:
            if isinstance(variant, str):
                value = variant.strip()
                if value and value not in cleaned:
                    cleaned.append(value)
        if not cleaned:
            cleaned = [query]

        focus = self._infer_query_focus(query, cleaned)
        fallback = self._fallback_query_variant(focus, query)
        if not fallback:
            return cleaned[:3]

        combined = " ".join(cleaned).lower()
        if self._should_force_specific_fallback(query, focus, combined):
            if len(cleaned) < 3:
                cleaned.append(fallback)
            else:
                cleaned[-1] = fallback
            return cleaned[:3]

        broad_theory_names = {
            "positive psychology",
            "cognitive behavioral therapy",
            "self-determination theory",
            "logotherapy",
        }
        fallback_terms = [
            term.strip().lower()
            for term in fallback.split(",")
            if term.strip().lower() not in broad_theory_names
        ]
        has_focus_terms = any(term and term in combined for term in fallback_terms)
        if has_focus_terms:
            return cleaned[:3]

        generic_markers = [
            "maslow", "hierarchy of needs", "cognitive dissonance theory",
            "social identity theory", "attachment theory",
        ]
        if len(cleaned) < 3:
            cleaned.append(fallback)
        elif any(marker in cleaned[-1].lower() for marker in generic_markers):
            cleaned[-1] = fallback
        else:
            cleaned[-1] = fallback
        return cleaned[:3]

    def _should_force_specific_fallback(self, query: str, focus: str, combined_variants: str) -> bool:
        if focus == "positive_psych":
            topic = self._positive_psych_topic(query)
            if topic == "achievement":
                return not any(term in combined_variants for term in ("savoring", "gratitude", "social comparison"))
            if topic == "hope":
                return not any(term in combined_variants for term in ("agency", "pathway", "pathways"))
            if topic == "burnout":
                return not any(term in combined_variants for term in ("burnout intervention", "work engagement"))
            if topic == "happiness":
                return not any(term in combined_variants for term in ("perma", "subjective well-being", "flourishing"))
            if topic == "loneliness":
                return not any(term in combined_variants for term in ("social support", "peer relation", "peer relations", "belonging"))
            if topic == "gratitude":
                return not any(term in combined_variants for term in ("gratitude journal", "three good things", "gratitude letter", "gratitude visit"))
        if focus == "cbt":
            cbt_topic = self._cbt_topic(query)
            if cbt_topic == "social_evaluation":
                return not any(
                    term in combined_variants
                    for term in (
                        "fear of negative evaluation", "mind reading", "self-focused attention",
                        "social-evaluative", "being judged", "judged by others", "reality testing",
                        "maladaptive thoughts", "how others judge", "cognitive errors",
                        "misinterpretation of social experiences", "negative judgment from others",
                    )
                )
            if cbt_topic == "rumination_sleep":
                return not any(
                    term in combined_variants
                    for term in ("repetitive negative thinking", "rumination-focused", "dysfunctional beliefs about sleep", "cbt-i")
                )
            if cbt_topic == "rumination":
                return not any(term in combined_variants for term in ("repetitive negative thinking", "rumination-focused"))
        if focus == "sdt":
            sdt_topic = self._sdt_topic(query)
            if sdt_topic == "competence_inadequacy":
                return not any(
                    term in combined_variants
                    for term in (
                        "perceived competence", "need for competence", "competence satisfaction",
                        "mastery", "optimal challenge", "challenging but achievable", "positive feedback",
                    )
                )
        if focus == "logotherapy":
            logotherapy_topic = self._logotherapy_topic(query)
            if logotherapy_topic == "grief_loss":
                return not any(
                    term in combined_variants
                    for term in (
                        "bereavement", "mourning", "meaning reconstruction",
                        "meaning-making after loss", "meaning making after loss",
                        "continuing bonds", "death of a loved one", "deaths of our loved ones",
                    )
                )
        return False

    def _focus_terms_for_query(self, query: str, query_variants: list[str] = None) -> list[str]:
        focus = self._infer_query_focus(query, query_variants)
        if focus == "positive_psych":
            topic = self._positive_psych_topic(query)
            if topic == "loneliness":
                return [
                    "loneliness", "lonely", "social isolation", "social connection",
                    "social support", "belonging", "peer relations",
                    "interpersonal relationships", "social competence",
                ]
            if topic == "gratitude":
                return [
                    "gratitude intervention", "gratitude journal", "three good things",
                    "gratitude letter", "gratitude visit", "grateful", "thankful",
                    "positive affect", "positive emotions", "subjective well-being",
                    "life satisfaction",
                ]
            if topic == "achievement":
                return [
                    "savoring", "savour", "gratitude", "achievement satisfaction",
                    "sense of satisfaction", "self-compassion", "social comparison",
                ]
            if topic == "burnout":
                return [
                    "burnout intervention", "positive psychology intervention", "burnout",
                    "work engagement", "meaningfulness in work", "meaning in work",
                    "professional supporting relationship", "well-being", "resilience",
                    "mindfulness", "three good things",
                ]
            if topic == "hope":
                return ["hope theory", "agency thinking", "pathways thinking", "goals", "resilience"]
            if topic == "happiness":
                return ["perma", "subjective well-being", "flourishing", "happiness", "positive psychology intervention"]
            return ["perma", "savoring", "gratitude", "hope theory", "well-being intervention"]
        if focus == "cbt":
            cbt_topic = self._cbt_topic(query, query_variants)
            if cbt_topic == "social_evaluation":
                return [
                    "social anxiety", "fear of negative evaluation", "negative judgment",
                    "fear of negative judgment", "negative judgment from others",
                    "being judged", "judged by others", "how others perceive",
                    "others' evaluations", "others’ evaluations", "preconceptions about others",
                    "negative expectations", "evaluations are negative",
                    "how others judge", "maladaptive thoughts", "maladaptive thoughts and beliefs",
                    "cognitive errors", "misinterpretation of their experiences",
                    "misinterpretation of social experiences", "present oneself favorably",
                    "mind reading", "mind-reading", "mind-reading and fortune-telling",
                    "self-focused attention", "social-evaluative",
                    "social situations", "cognitive restructuring", "reality testing",
                    "socratic questioning", "safety behaviors",
                ]
            if cbt_topic == "rumination_sleep":
                return [
                    "rumination", "ruminative", "repetitive negative thinking",
                    "post-event rumination", "worry", "worries", "rumination-focused CBT",
                    "cognitive restructuring", "behavioral tests", "insomnia",
                    "sleep disturbance", "sleep disorders", "thinking repetitively",
                    "sleep deficiencies", "arousal and distress", "monitoring of sleep-related threats",
                    "sleep-related threats", "catastrophizing about sleep",
                ]
            if cbt_topic == "rumination":
                return [
                    "rumination", "ruminative", "repetitive negative thinking",
                    "post-event rumination", "worry", "worries", "rumination-focused CBT",
                    "cognitive restructuring", "behavioral tests",
                ]
            return ["cognitive distortion", "cognitive restructuring", "catastrophizing", "negative automatic thoughts", "cbt"]
        if focus == "sdt":
            if self._sdt_topic(query, query_variants) == "competence_inadequacy":
                return [
                    "competence", "competent", "perceived competence", "competence satisfaction",
                    "need for competence", "feeling effective", "effective in", "capacities",
                    "talents", "mastery", "self-efficacy", "optimal challenge",
                    "challenging but achievable", "positive feedback", "basic psychological needs",
                ]
            return ["autonomy", "competence", "relatedness", "intrinsic motivation", "controlling rewards", "self-determination"]
        if focus == "logotherapy":
            if self._logotherapy_topic(query, query_variants) == "grief_loss":
                return [
                    "grief", "bereavement", "mourning", "mourn", "loss of a loved one",
                    "death of a loved one", "death of the next of kin", "next of kin",
                    "deaths of our loved ones", "loved ones",
                    "meaning reconstruction", "meaning-making", "meaning making",
                    "meaning-making after loss", "continuing bonds", "relational meaning",
                    "relationships", "personal sense of meaningfulness", "crisis of meaning",
                    "responding to values", "professed values", "responsibility for the consequences",
                ]
            return ["attitudinal values", "meaning in suffering", "existential meaning", "illness and meaning", "human worth"]
        return []

    def _reranker_focus_guidance(self, query: str, query_variants: list[str] = None) -> str:
        focus = self._infer_query_focus(query, query_variants)

        if focus == "positive_psych":
            topic = self._positive_psych_topic(query)
            if topic == "loneliness":
                return (
                    "For this query, prioritize chunks that directly discuss loneliness, social isolation, "
                    "social connection, social support, belonging, peer relations, interpersonal relationships, "
                    "or social competence. Prefer chunks that describe the population/context clearly, and "
                    "deprioritize generic SDT motivation chunks unless they directly discuss loneliness or social connection."
                )
            if topic == "gratitude":
                return (
                    "For this query, prioritize chunks that directly discuss gratitude interventions, gratitude "
                    "journals, Three Good Things, gratitude letters or visits, subjective well-being, positive "
                    "affect, positive emotions, or life satisfaction. Prefer intervention/result chunks over "
                    "broad positive-psychology lists or job-performance-only gratitude chunks."
                )
            if topic == "achievement":
                return (
                    "For this query, prioritize chunks that directly discuss savoring accomplishments, "
                    "gratitude, achievement/accomplishment satisfaction, self-compassion, social comparison, "
                    "subjective well-being, or PERMA accomplishment. Deprioritize generic motivation, "
                    "need frustration, or self-criticism chunks unless no direct positive-psychology evidence is present."
                )
            if topic == "burnout":
                return (
                    "For this query, prioritize chunks that directly discuss burnout interventions, positive "
                    "psychology interventions, work engagement, meaning in work, professional relationships, "
                    "well-being, or recovery resources. Prefer synthesis/result chunks over table fragments. "
                    "Deprioritize generic wellness claims and chunks that only list references."
                )
            if topic == "hope":
                return (
                    "For this query, prioritize chunks that directly discuss hope theory, agency thinking, "
                    "pathways thinking, goal pursuit, resilience, or future-oriented positive psychology."
                )
            if topic == "happiness":
                return (
                    "For this query, prioritize chunks that directly discuss PERMA, subjective well-being, "
                    "flourishing, happiness, or evidence-based positive psychology interventions."
                )
        if focus == "cbt":
            cbt_topic = self._cbt_topic(query, query_variants)
            if cbt_topic == "social_evaluation":
                return (
                    "For this query, prioritize chunks that directly discuss social anxiety, fear of "
                    "negative evaluation, being judged by others, mind-reading assumptions, self-focused "
                    "attention, social-evaluative threat, maladaptive thoughts about how others judge the "
                    "person, cognitive errors, misinterpretation of social experiences, cognitive restructuring, "
                    "preconceptions about others' evaluations, or mind-reading and fortune-telling biases. "
                    "Also prioritize Socratic questioning or reality testing in social situations. Prefer explanatory chunks "
                    "about social-anxiety cognition over session agenda/protocol fragments. Deprioritize generic "
                    "CBT, generic anxiety, or broad cognitive-distortion chunks unless they clearly address "
                    "social-evaluative thoughts."
                )
            if cbt_topic == "rumination_sleep":
                return (
                    "For this query, prioritize chunks that directly discuss rumination, repetitive negative "
                    "thinking, worry, rumination-focused CBT, cognitive restructuring, or behavioral tests. "
                    "Also include sleep-specific chunks only when they directly discuss repetitive thinking "
                    "about sleep deficiencies, arousal/distress, monitoring of sleep-related threats, insomnia, "
                    "sleep disturbance, or catastrophizing about sleep. "
                    "If at least one candidate directly discusses repetitive thinking about sleep deficiencies, "
                    "arousal/distress, or monitoring of sleep-related threats, select one such sleep-specific "
                    "chunk along with the rumination/CBT chunks. "
                    "Prefer evidence that keeps rumination/anxiety claims and sleep/insomnia claims clearly "
                    "scoped; deprioritize sleep chunks that only mention dysfunctional beliefs or CBT-I without "
                    "repetitive thinking/arousal, table/theme-code fragments, and generic CBT introductions that "
                    "do not directly discuss rumination or sleep."
                )
            if cbt_topic == "rumination":
                return (
                    "For this query, prioritize chunks that directly discuss rumination, repetitive negative "
                    "thinking, worry, rumination-focused CBT, cognitive restructuring, or behavioral tests. "
                    "Deprioritize generic CBT or cognitive-distortion introductions unless no direct rumination "
                    "evidence is available."
                )
            return (
                "For this query, prioritize chunks that directly discuss cognitive distortions, negative "
                "automatic thoughts, catastrophizing, cognitive restructuring, or CBT interventions."
            )
        if focus == "sdt":
            if self._sdt_topic(query, query_variants) == "competence_inadequacy":
                return (
                    "For this query, prioritize chunks that directly discuss need for competence, perceived "
                    "competence, competence satisfaction, feeling effective, mastery, self-efficacy, positive "
                    "feedback, or challenging-but-achievable tasks. Prefer chunks that explain competence as a "
                    "basic psychological need or describe concrete competence-supportive conditions. Deprioritize "
                    "generic autonomy/reward/relatedness chunks and measurement-only chunks unless they clearly "
                    "define competence."
                )
            return (
                "For this query, prioritize chunks that directly discuss autonomy, competence, relatedness, "
                "intrinsic motivation, extrinsic motivation, controlling rewards, or self-determination theory."
            )
        if focus == "logotherapy":
            if self._logotherapy_topic(query, query_variants) == "grief_loss":
                return (
                    "For this query, prioritize chunks that directly discuss grief, bereavement, mourning, "
                    "death or loss of a loved one, death of the next of kin, meaning reconstruction or "
                    "meaning-making after loss, responding to values after suffering, continuing bonds, "
                    "relational meaning, or how close relationships shape meaning after "
                    "loss. Prefer chunks that mention loved ones, mourning, grief, or bereavement directly. "
                    "Deprioritize generic Frankl/logotherapy or broad meaning-in-suffering chunks unless "
                    "they clearly address grief, bereavement, or loss of a loved one."
                )
            return (
                "For this query, prioritize chunks that directly discuss attitudinal values, meaning in "
                "suffering, existential meaning, illness and meaning, or human worth beyond productivity."
            )
        return ""

    async def _translate_to_korean(self, text: str) -> str:
        """
        영문 학술 논문 문단을 자연스럽고 전문적인 한국어로 번역합니다.
        (이미 한글 텍스트인 경우에는 번역 없이 반환)
        """
        import re
        if not text:
            return ""
        if re.search('[ㄱ-ㅎㅏ-ㅣ가-힣]', text):
            return text
            
        try:
            system_prompt = (
                "You are an expert academic translator specializing in psychology and logotherapy.\n"
                "Translate the following English paper chunk into natural, fluent, and highly professional Korean academic language.\n"
                "Maintain precise psychological terminologies and appropriate academic tone.\n"
                "Output ONLY the translated Korean text without any extra explanation, greetings, or formatting."
            )
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=text)
            ]
            response = await self.llm.ainvoke(messages)
            return response.content.strip()
        except Exception as e:
            log_event("rag_translation_error", level="warning", error_type=type(e).__name__)
            return text

    async def _translate_and_summarize_paper(self, text: str) -> dict:
        """
        영문 연구 발췌를 한국어로 번역하고, 동시에 1줄 발췌 요약(insight summary)을 생성합니다.
        결과는 JSON 형식을 따르며 {"content_ko": "번역문", "summary_ko": "1줄 요약문"} 구조를 가집니다.
        """
        import re
        if not text:
            return {"content_ko": "", "summary_ko": ""}
            
        if re.search('[ㄱ-ㅎㅏ-ㅣ가-힣]', text):
            summary = text.split('.')[0].strip() + "."
            if len(summary) > 80:
                summary = summary[:80] + "..."
            return {"content_ko": text, "summary_ko": summary}

        try:
            system_prompt = (
                "You are an expert academic translator and psychologist specializing in logotherapy and positive psychology.\n"
                "Your task is to translate the given English research excerpt into professional Korean AND provide a one-line warm, intuitive Korean insight summary for general users.\n"
                "You MUST output the result as a raw JSON object with the following keys:\n"
                "  - 'content_ko': The precise, academic translation of the excerpt into natural Korean.\n"
                "  - 'summary_ko': A warm, concise, and intuitive one-line summary in Korean of the key point in this excerpt (within 100 characters). This summary will be shown in a popover when users hover on citations, so it should be easy to understand (e.g., '목표를 설정하고 이를 시각화하는 활동이 일상의 성취감과 무력감 개선에 긍정적인 영향을 미친다는 연구 발췌입니다.').\n"
                "Output ONLY the JSON object, no explanation, no markdown wrappers."
            )
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=text)
            ]
            
            response = await self.llm.ainvoke(messages, response_format={"type": "json_object"})
            data = json.loads(response.content.strip())
            return {
                "content_ko": data.get("content_ko", "").strip(),
                "summary_ko": data.get("summary_ko", "").strip()
            }
        except Exception as e:
            log_event("rag_translation_summary_error", level="warning", error_type=type(e).__name__)
            try:
                translated = await self._translate_to_korean(text)
                summary = translated.split('.')[0].strip() + "."
                if len(summary) > 80:
                    summary = summary[:80] + "..."
                return {"content_ko": translated, "summary_ko": summary}
            except Exception:
                return {"content_ko": text, "summary_ko": text[:80] + "..."}

    def is_casual_query(self, query: str, is_journal: bool) -> bool:
        if is_journal:
            return False
        
        # 1. 공백 제거 후 12자 이하의 짧은 단문은 무조건 캐주얼 쿼리로 분류
        clean_query = query.replace(" ", "").strip()
        if len(clean_query) <= 12:
            return True
            
        # 2. 특수문자/구두점 제거
        import re
        normalized = re.sub(r'[^\w\s]', '', query)
        normalized_clean = normalized.replace(" ", "").strip()
        
        # 3. 일상어 및 질문 오프닝용 스톱워드 목록 (공백이 제거된 상태에서 매칭)
        casual_stop_words = [
            "안녕하세요", "안녕", "하이", "반가워", "반갑네", "반갑습니다", "하이요",
            "고민이있습니다", "고민이있어요", "고민있습니다", "고민있어요", "고민이있어", "고민있어", "고민",
            "이야기", "대화하자", "대화하고", "대화해", "대화", "도와줘", "도와주세요", "도움",
            "질문이있습니다", "질문있습니다", "질문이있어요", "질문있어요", "질문이있어", "질문있어", "질문",
            "제가", "저기", "혹시", "요즘", "있어서요", "있습니다", "있어요", "있어", "바랍니다",
            "누구", "이름", "소개", "자기소개", "너는", "당신은", "뭐해", "뭐하니", "심심",
            "말동무", "상담", "받고", "받고싶어", "해줘", "해줘요", "해주세요", "합니다",
            "궁금", "궁금해서", "궁금해요", "물어볼게", "물어볼것이", "물어볼게있어", "물어볼게있습니다"
        ]
        
        temp = normalized_clean
        for word in casual_stop_words:
            temp = temp.replace(word, "")
            
        # 스톱워드 제거 후 남은 의미 있는 글자 수가 3자 이하인 경우 일상 쿼리로 판정
        if len(temp) <= 3:
            return True
            
        return False

    async def retrieve(self, query: str, english_query: str = None, query_variants: list[str] = None) -> tuple:
        """
        쿼리 확장 → multi-query MongoDB Atlas $vectorSearch → vector-only RRF merge →
        optional two-stage reranker → LLM 재랭킹 → 주변 청크 확장까지
        수행하고 (재랭킹된 primary 청크 리스트, 원시 검색 결과)를 반환한다.

        스트리밍·생성 부수효과가 없으므로 프로덕션(get_streaming_response)과 평가(evaluate_rag.py)가
        동일한 검색 경로를 공유한다.
        """
        db = get_db()
        if query_variants is None:
            query_variants = await self._expand_query_variants(query, primary=english_query)
        query_variants = [variant for variant in query_variants if variant][:3] or [english_query or query]
        english_query = english_query or query_variants[0]

        social_eval_query = (
            self._infer_query_focus(query, query_variants) == "cbt"
            and self._cbt_topic(query, query_variants) == "social_evaluation"
        )
        grief_loss_query = (
            self._infer_query_focus(query, query_variants) == "logotherapy"
            and self._logotherapy_topic(query, query_variants) == "grief_loss"
        )
        vector_limit = 25 if (social_eval_query or grief_loss_query) else 15
        merge_limit = 32 if (social_eval_query or grief_loss_query) else 24

        rankings = []
        raw_results = []
        for variant_index, variant in enumerate(query_variants):
            results = self._vector_search(db, variant, variant_index=variant_index, limit=vector_limit)
            raw_results.extend(results)
            rankings.append([self._candidate_from_result(res) for res in results if res.get("content")])

        candidates = self._merge_vector_rankings(rankings, limit=merge_limit)
        candidates = self._apply_focus_boosts(candidates, query, query_variants)

        if self.reranker_mode == "two_stage" and len(candidates) > 10:
            candidates = self._cross_encoder_rerank(english_query, candidates, limit=10)

        # LLM Re-ranking 적용
        if len(candidates) <= 4:
            reranked_results = candidates
            log_event("rag_llm_rerank_skipped", candidate_count=len(candidates), reason="few_candidates")
        else:
            reranked_results = await self._rerank_documents(query, candidates, query_variants=query_variants)

        self._attach_context_windows(db, reranked_results)
        self.last_retrieval_trace = {
            "query": query,
            "english_query": english_query,
            "query_variants": query_variants,
            "reranker_mode": self.reranker_mode,
            "vector_candidates": [self._trace_doc(doc) for doc in candidates],
            "selected_primary": [self._trace_doc(doc, include_expanded=True) for doc in reranked_results],
        }
        return reranked_results, raw_results

    def _vector_search(self, db, query_text: str, variant_index: int = 0, limit: int = 15) -> list:
        query_embedding = self.embeddings.embed_query(query_text)
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "embedding",
                    "queryVector": query_embedding,
                    "numCandidates": 120,
                    "limit": limit
                }
            },
            {
                "$project": {
                    "content": 1,
                    "metadata": 1,
                    "chunk_id": 1,
                    "document_id": 1,
                    "filename": 1,
                    "title": 1,
                    "section": 1,
                    "page_start": 1,
                    "page_end": 1,
                    "chunk_index": 1,
                    "language": 1,
                    "text_quality": 1,
                    "similarity": {"$meta": "vectorSearchScore"}
                }
            }
        ]

        try:
            results = list(db.documents.aggregate(pipeline))
            for rank, result in enumerate(results):
                result["variant_index"] = variant_index
                result["variant_rank"] = rank
                result["query_text"] = query_text
            return results
        except Exception as e:
            log_event("rag_vector_search_error", level="error", error_type=type(e).__name__)
            return []

    def _merge_vector_rankings(self, rankings: list[list[dict]], limit: int = 24, k: int = 60) -> list[dict]:
        merged = {}
        for variant_index, ranking in enumerate(rankings):
            for rank, doc in enumerate(ranking):
                chunk_id = doc.get("chunk_id") or doc.get("id")
                if not chunk_id:
                    continue
                score = 1.0 / (k + rank + 1)
                current = merged.get(chunk_id)
                if current is None:
                    current = {**doc, "rrf_score": 0.0, "variant_hits": [], "best_vector_rank": rank}
                    merged[chunk_id] = current
                elif doc.get("similarity", 0) > current.get("similarity", 0):
                    preserved = {
                        "rrf_score": current.get("rrf_score", 0.0),
                        "variant_hits": current.get("variant_hits", []),
                        "best_vector_rank": min(current.get("best_vector_rank", rank), rank),
                    }
                    current.update(doc)
                    current.update(preserved)
                current["rrf_score"] += score
                current["variant_hits"].append({"variant_index": variant_index, "rank": rank, "score": score})
                current["best_vector_rank"] = min(current.get("best_vector_rank", rank), rank)

        return sorted(
            merged.values(),
            key=lambda doc: (
                -doc.get("rrf_score", 0.0),
                -doc.get("similarity", 0.0),
                doc.get("chunk_id") or "",
            ),
        )[:limit]

    def _quality_penalty(self, doc: dict) -> float:
        content = (doc.get("content") or "").strip()
        lower = content.lower()
        penalty = 0.0

        if len(content) < 220:
            penalty += 0.025
        if lower.startswith("keywords:") or lower.startswith("| abstract") or " keywords:" in lower[:120]:
            penalty += 0.02

        import re
        loading_values = len(re.findall(r"\s\.\d{2,3}\b", content))
        if loading_values >= 6:
            penalty += 0.025

        years = len(re.findall(r"\b(?:19|20)\d{2}\b", content))
        journal_markers = sum(
            marker in lower
            for marker in (" j. ", "journal", "doi", "vol.", "pp.", "frontiers", "acad. manag.", "psychosom.")
        )
        if years >= 7 and journal_markers >= 2:
            penalty += 0.025

        table_markers = ("table", "study\naim", "intervention\nintervention", "study outcome")
        if any(marker in lower for marker in table_markers):
            penalty += 0.012
        structured_table_markers = (
            "themes, subthemes", "category (main theme)", "subcategory",
            "concepts (open codes)", "open codes", "table 1",
        )
        if any(marker in lower for marker in structured_table_markers):
            penalty += 0.025
        protocol_markers = (
            "homework review", "summary review of the previous session",
            "reviewing a summary of the previous session", "summarizing the meeting",
            "relaxation exercise through guided imagery",
        )
        if any(marker in lower for marker in protocol_markers):
            penalty += 0.02
        return penalty

    def _focus_boost(self, doc: dict, query: str, query_variants: list[str] = None) -> float:
        terms = self._focus_terms_for_query(query, query_variants)
        if not terms:
            return 0.0
        focus = self._infer_query_focus(query, query_variants)

        searchable = f"{doc.get('title') or ''}\n{doc.get('content') or ''}".lower()
        matched = []
        for term in terms:
            normalized = term.lower()
            if normalized and normalized in searchable:
                matched.append(normalized)

        boost = min(0.024, len(set(matched)) * 0.006)
        document_id = doc.get("document_id") or ""
        expected_prefix = {
            "positive_psych": "positive_psych_",
            "cbt": "cbt_",
            "sdt": "sdt_",
            "logotherapy": "logotherapy_",
        }.get(focus)
        if matched and expected_prefix and document_id.startswith(expected_prefix):
            boost += 0.004
        return boost

    def _apply_focus_boosts(self, documents: list[dict], query: str, query_variants: list[str] = None) -> list[dict]:
        boosted = []
        for doc in documents:
            copied = {**doc}
            focus_boost = self._focus_boost(copied, query, query_variants)
            quality_penalty = self._quality_penalty(copied)
            copied["focus_boost"] = focus_boost
            copied["quality_penalty"] = quality_penalty
            copied["ranking_score"] = copied.get("rrf_score", 0.0) + focus_boost - quality_penalty
            boosted.append(copied)

        return sorted(
            boosted,
            key=lambda doc: (
                -doc.get("ranking_score", 0.0),
                -doc.get("rrf_score", 0.0),
                -doc.get("similarity", 0.0),
                doc.get("chunk_id") or "",
            ),
        )

    def _reinforce_grief_loss_companion(
        self,
        selected: list[dict],
        candidates: list[dict],
        query: str,
        query_variants: list[str] = None,
    ) -> list[dict]:
        if (
            self._infer_query_focus(query, query_variants) != "logotherapy"
            or self._logotherapy_topic(query, query_variants) != "grief_loss"
            or not selected
        ):
            return selected

        selected_ids = {doc.get("chunk_id") for doc in selected if doc.get("chunk_id")}
        selected_pairs = {
            (doc.get("document_id"), doc.get("chunk_index"))
            for doc in selected
            if doc.get("document_id") and isinstance(doc.get("chunk_index"), int)
        }
        if not selected_pairs:
            return selected

        def direct_signal(doc: dict) -> int:
            text = f"{doc.get('title') or ''}\n{doc.get('content') or ''}".lower()
            terms = (
                "mourn", "death of a loved one", "death of the next of kin",
                "loved ones", "crisis of meaning", "meaning-making",
                "meaning making", "personal sense of meaningfulness",
                "meaning reconstruction", "suffering",
            )
            return sum(1 for term in terms if term in text)

        companion_candidates = []
        for candidate in candidates:
            chunk_id = candidate.get("chunk_id")
            document_id = candidate.get("document_id")
            chunk_index = candidate.get("chunk_index")
            if not chunk_id or chunk_id in selected_ids:
                continue
            if not document_id or not isinstance(chunk_index, int):
                continue
            if not any(
                document_id == selected_document and abs(chunk_index - selected_index) == 1
                for selected_document, selected_index in selected_pairs
            ):
                continue
            signal = direct_signal(candidate)
            if signal < 2:
                continue
            companion_candidates.append((signal, candidate.get("ranking_score", 0.0), candidate))

        if not companion_candidates:
            return selected

        companion_candidates.sort(key=lambda item: (-item[0], -item[1], item[2].get("chunk_id") or ""))
        companion = companion_candidates[0][2]
        if len(selected) < 4:
            return [*selected, companion]
        return [*selected[:3], companion]

    def _cross_encoder_rerank(self, query: str, documents: list, limit: int = 10) -> list:
        try:
            if self.cross_encoder is None:
                import torch
                from sentence_transformers import CrossEncoder

                if torch.cuda.is_available():
                    device = "cuda"
                elif torch.backends.mps.is_available():
                    device = "mps"
                else:
                    device = "cpu"
                self.cross_encoder = CrossEncoder("BAAI/bge-reranker-v2-m3", device=device)

            pairs = [[query, f"{doc.get('title') or ''}\n{doc.get('content') or ''}"] for doc in documents]
            scores = self.cross_encoder.predict(pairs)
            reranked = []
            for doc, score in zip(documents, scores):
                copied = {**doc, "cross_encoder_score": float(score)}
                reranked.append(copied)
            reranked.sort(key=lambda doc: (-doc.get("cross_encoder_score", 0.0), -doc.get("rrf_score", 0.0)))
            return reranked[:limit]
        except Exception as e:
            log_event("rag_cross_encoder_rerank_error", level="warning", error_type=type(e).__name__)
            return documents[:limit]

    def _trace_doc(self, doc: dict, include_expanded: bool = False) -> dict:
        traced = {
            "id": doc.get("id"),
            "chunk_id": doc.get("chunk_id"),
            "document_id": doc.get("document_id"),
            "title": doc.get("title"),
            "filename": doc.get("filename"),
            "section": doc.get("section"),
            "page_start": doc.get("page_start"),
            "page_end": doc.get("page_end"),
            "chunk_index": doc.get("chunk_index"),
            "language": doc.get("language"),
            "text_quality": doc.get("text_quality"),
            "similarity": doc.get("similarity", 0),
            "rrf_score": doc.get("rrf_score"),
            "focus_boost": doc.get("focus_boost"),
            "quality_penalty": doc.get("quality_penalty"),
            "ranking_score": doc.get("ranking_score"),
            "cross_encoder_score": doc.get("cross_encoder_score"),
            "variant_hits": doc.get("variant_hits", []),
            "primary_excerpt": doc.get("content"),
        }
        if include_expanded:
            traced["expanded_context"] = doc.get("expanded_content") or doc.get("content")
        return traced

    def _candidate_from_result(self, res: dict) -> dict:
        meta = res.get("metadata") or {}

        def pick(key, default=None):
            value = res.get(key)
            if value is None or value == "":
                value = meta.get(key, default)
            return value

        return {
            "id": str(res.get("_id") or pick("chunk_id") or ""),
            "content": res.get("content") or "",
            "metadata": meta,
            "similarity": res.get("similarity", 0),
            "chunk_id": pick("chunk_id"),
            "document_id": pick("document_id"),
            "filename": pick("filename"),
            "title": pick("title"),
            "section": pick("section"),
            "page_start": pick("page_start"),
            "page_end": pick("page_end"),
            "chunk_index": pick("chunk_index"),
            "language": pick("language"),
            "text_quality": pick("text_quality"),
            "variant_index": res.get("variant_index"),
            "variant_rank": res.get("variant_rank"),
        }

    def _source_location_text(self, doc: dict) -> str:
        parts = []
        section = doc.get("section") or (doc.get("metadata") or {}).get("section")
        page_start = doc.get("page_start")
        page_end = doc.get("page_end")

        if section:
            parts.append(f"section: {section}")
        if page_start and page_end and page_start != page_end:
            parts.append(f"pages: {page_start}-{page_end}")
        elif page_start:
            parts.append(f"page: {page_start}")
        if doc.get("chunk_index") is not None:
            parts.append(f"chunk: {doc.get('chunk_index')}")
        return ", ".join(parts) or "location unknown"

    def _truncate_context(self, text: str, max_chars: int = 3500) -> str:
        text = (text or "").strip()
        if len(text) <= max_chars:
            return text
        return text[:max_chars - 3].rstrip() + "..."

    def _answer_verifier_enabled(self, documents: list) -> bool:
        mode = (getattr(self, "verifier_mode", "off") or "off").strip().lower()
        return bool(documents) and mode in {"1", "true", "on", "llm", "strict"}

    def _claim_checker_enabled(self, documents: list) -> bool:
        mode = (getattr(self, "claim_checker_mode", "off") or "off").strip().lower()
        return bool(documents) and mode in {"1", "true", "on", "llm", "strict"}

    def _sentence_template_enabled(self) -> bool:
        mode = (getattr(self, "answer_template_mode", "standard") or "standard").strip().lower()
        return mode in {"1", "true", "on", "sentence", "sentence_citation", "sentence_citations"}

    def _stream_text_chunks(self, text: str, max_chars: int = 96) -> list[str]:
        if not text:
            return []
        return [text[i:i + max_chars] for i in range(0, len(text), max_chars)]

    async def _generate_answer_text(self, messages: list) -> str:
        llm = getattr(self, "answer_review_llm", None) or getattr(self, "reranker_llm", None) or self.llm
        response = await llm.ainvoke(messages)
        return (response.content or "").strip()

    async def _verify_answer_against_context(
        self,
        query: str,
        answer: str,
        context_text: str,
        sources: list,
        is_journal: bool = False,
    ) -> dict:
        """
        Rewrite the generated RAG answer only when it makes claims that are not
        grounded in the retrieved excerpts. This is feature-flagged because it
        requires buffering the draft answer before streaming it to the client.
        """
        fallback = {
            "answer": answer,
            "changed": False,
            "error": None,
            "unsupported_claims": [],
        }
        if not answer or not context_text:
            return fallback

        citation_list = ", ".join(f"[{idx}](#source-{idx})" for idx in range(1, len(sources) + 1)) or "(none)"
        source_brief = "\n".join(
            f"[{idx}] {src.get('title') or src.get('filename') or 'Untitled'} | "
            f"section={src.get('section') or 'unknown'} | "
            f"pages={src.get('page_start') or 'unknown'}-{src.get('page_end') or src.get('page_start') or 'unknown'}"
            for idx, src in enumerate(sources, start=1)
        )
        mode_text = "journal reflection" if is_journal else "user conversation"

        system_prompt = (
            "You are a strict RAG faithfulness verifier for a Korean counseling assistant.\n"
            "Your job is to revise the DRAFT ANSWER only when it goes beyond the supplied academic excerpts.\n"
            "Keep the answer in Korean and preserve a warm reflective tone, but prioritize factual grounding.\n\n"
            "Rules:\n"
            "1. Every factual research claim, intervention/effect claim, methodology/sample claim, or concrete practice suggestion must be directly supported by the CONTEXT and end with a valid citation.\n"
            "2. Valid citations are only these markdown links: "
            f"{citation_list}.\n"
            "3. If a claim is not supported, remove it or soften it to say that the excerpt only suggests a limited interpretation.\n"
            "4. Do not add new research facts, practices, mechanisms, outcomes, sample details, or causal effects.\n"
            "5. If methodology, sample, limitations, causal effects, or expected outcomes are absent from the CONTEXT, say they are difficult to confirm from these excerpts when relevant.\n"
            "6. Keep or add citations only where the cited source actually supports the sentence.\n"
            "7. Preserve the user's reflective question at the end, unless it contains an unsupported factual claim.\n"
            "8. Do not mention this verification process.\n\n"
            "9. Rewrite aggressively when needed. The final answer should be concise: 5 to 8 Korean sentences, with one claim per sentence.\n"
            "10. Empathy and open questions may be uncited, but all explanatory psychology/research/practice sentences need citations.\n"
            "11. Any sentence containing effects, benefits, worsening, improvement, recovery, importance, mechanisms, or recommendations must either have direct citation support or be removed.\n"
            "12. Convert unsupported advice into an open reflective question instead of presenting it as a helpful practice.\n"
            "13. Banned unsupported Korean phrases: '효과적일 수 있습니다', '도움이 될 수 있습니다', '기여할 수 있습니다', '향상시키는 데', '중요합니다', '악화시킬 수 있습니다', '비롯됩니다'. If they appear without direct support and citation, rewrite or remove them.\n\n"
            "Output ONLY raw JSON with this shape:\n"
            "{\"answer\": \"verified Korean answer\", \"changed\": true, \"unsupported_claims\": [\"...\"]}"
        )
        user_prompt = (
            f"MODE:\n{mode_text}\n\n"
            f"USER QUESTION:\n{query}\n\n"
            f"SOURCES:\n{source_brief}\n\n"
            f"CONTEXT:\n{context_text}\n\n"
            f"DRAFT ANSWER:\n{answer}"
        )

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
            response = await self.verifier_llm.ainvoke(messages, response_format={"type": "json_object"})
            data = json.loads(response.content.strip())
            verified_answer = (data.get("answer") or "").strip()
            if len(verified_answer) < 20:
                return {**fallback, "error": "empty_or_too_short_verifier_answer"}
            unsupported_claims = data.get("unsupported_claims", [])
            if not isinstance(unsupported_claims, list):
                unsupported_claims = [str(unsupported_claims)]
            return {
                "answer": verified_answer,
                "changed": bool(data.get("changed")) or verified_answer != answer,
                "error": None,
                "unsupported_claims": [str(item) for item in unsupported_claims if item],
            }
        except Exception as e:
            log_event("rag_answer_verification_error", level="warning", error_type=type(e).__name__)
            return {**fallback, "error": str(e)}

    def _claim_candidate_sentences(self, answer: str) -> list[str]:
        """
        Heuristic prefilter for the LLM claim checker. It does not decide support;
        it only highlights sentences likely to contain research/practice claims.
        """
        import re
        sentences = [
            part.strip()
            for part in re.split(r"(?<=[.!?。！？])\s+|\n+", answer or "")
            if part.strip()
        ]
        claim_markers = (
            "연구", "발췌", "논문", "따르면", "시사", "보고", "효과", "도움",
            "기여", "향상", "악화", "증진", "감소", "회복", "개입", "방법",
            "실천", "전략", "중요", "관련", "관계", "영향", "역할", "필요",
            "sample", "method", "effect", "intervention", "study", "research",
        )
        return [sentence for sentence in sentences if any(marker in sentence for marker in claim_markers)]

    async def _check_answer_claim_citations(
        self,
        query: str,
        answer: str,
        context_text: str,
        sources: list,
        is_journal: bool = False,
    ) -> dict:
        """
        Narrow post-generation guard: keep the answer mostly intact, but fix only
        sentences that make unsupported research/effect/practice claims.
        """
        fallback = {
            "answer": answer,
            "changed": False,
            "error": None,
            "edits": [],
        }
        if not answer or not context_text:
            return fallback

        citation_list = ", ".join(f"[{idx}](#source-{idx})" for idx in range(1, len(sources) + 1)) or "(none)"
        source_brief = "\n".join(
            f"[{idx}] {src.get('title') or src.get('filename') or 'Untitled'} | "
            f"section={src.get('section') or 'unknown'} | "
            f"pages={src.get('page_start') or 'unknown'}-{src.get('page_end') or src.get('page_start') or 'unknown'}"
            for idx, src in enumerate(sources, start=1)
        )
        candidates = self._claim_candidate_sentences(answer)
        candidate_block = "\n".join(f"- {sentence}" for sentence in candidates) or "(none)"
        mode_text = "journal reflection" if is_journal else "user conversation"

        system_prompt = (
            "You are a sentence-level RAG claim and citation checker for a Korean counseling assistant.\n"
            "Do NOT rewrite the whole answer. Preserve the draft answer's structure, tone, paragraph order, and final open question.\n"
            "Only edit individual sentences that contain unsupported research, psychology, intervention, effect, method/sample, or concrete practice claims.\n\n"
            "Rules:\n"
            "1. Empathy, user reflection, and open questions may remain uncited when they do not assert research facts.\n"
            "2. A research/effect/practice sentence must be directly supported by the CONTEXT and end with a valid citation.\n"
            "3. Valid citations are only these markdown links: "
            f"{citation_list}.\n"
            "4. If a claim lacks support, either remove that sentence, soften it to the narrow context, or convert it to an open reflective question.\n"
            "5. Do not add new facts, mechanisms, practices, outcomes, sample details, or causal explanations.\n"
            "6. Do not change source numbering. Do not cite a source unless that source supports the sentence.\n"
            "7. Keep the final answer in Korean. Do not mention the checking process.\n"
            "8. Prefer minimal edits. If the draft is already supported, return it unchanged.\n\n"
            "Output ONLY raw JSON with this shape:\n"
            "{\"answer\": \"minimally corrected Korean answer\", \"changed\": false, "
            "\"edits\": [{\"sentence\": \"original sentence\", \"action\": \"kept|softened|removed|citation_added\", \"reason\": \"short reason\"}]}"
        )
        user_prompt = (
            f"MODE:\n{mode_text}\n\n"
            f"USER QUESTION:\n{query}\n\n"
            f"SOURCES:\n{source_brief}\n\n"
            f"CONTEXT:\n{context_text}\n\n"
            f"LIKELY CLAIM SENTENCES TO CHECK:\n{candidate_block}\n\n"
            f"DRAFT ANSWER:\n{answer}"
        )

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
            response = await self.claim_checker_llm.ainvoke(messages, response_format={"type": "json_object"})
            data = json.loads(response.content.strip())
            checked_answer = (data.get("answer") or "").strip()
            if len(checked_answer) < 20:
                return {**fallback, "error": "empty_or_too_short_claim_checker_answer"}
            edits = data.get("edits", [])
            if not isinstance(edits, list):
                edits = []
            return {
                "answer": checked_answer,
                "changed": bool(data.get("changed")) or checked_answer != answer,
                "error": None,
                "edits": edits,
            }
        except Exception as e:
            log_event("rag_claim_check_error", level="warning", error_type=type(e).__name__)
            return {**fallback, "error": str(e)}

    def _grounded_answer_template(self, is_journal: bool = False) -> str:
        user_scope = "일기" if is_journal else "고민"
        return (
            "\n[문장별 근거 답변 템플릿]\n"
            "아래 구조를 지키되, 제목/번호/불릿 없이 자연스러운 한국어 단락으로 작성하십시오. 전체 답변은 5~7문장으로 제한하십시오.\n"
            f"1. 첫 문장은 사용자의 {user_scope}와 감정을 짧게 반영하는 공감 문장으로 시작하십시오. 이 문장은 citation 없이 가능하지만 연구 주장이나 심리학 일반 설명을 넣지 마십시오.\n"
            "2. 그다음 2~3문장은 [검색된 연구 발췌와 주변 문맥]이 실제로 말하는 범위만 설명하십시오. 한 문장에는 하나의 연구 claim만 쓰고, 각 문장 끝에는 반드시 해당 source token을 붙이십시오. 예: [1](#source-1)\n"
            f"3. 사용자 {user_scope}와 연결하는 문장은 조심스러운 가설로만 표현하십시오. 근거 발췌의 개념을 사용했다면 그 문장 끝에도 citation을 붙이십시오.\n"
            "4. 실천 제안은 발췌에 명시된 개념을 작게 탐색하는 수준으로만 쓰십시오. 발췌에 없는 실천법은 제안하지 말고 열린 질문으로 바꾸십시오.\n"
            "5. 마지막은 열린 질문 1~2개로 마무리하십시오. 질문에는 새로운 연구 주장이나 효과 예측을 넣지 마십시오.\n\n"
            "[문장별 citation 규칙]\n"
            "- 문단 끝 citation은 앞 문장들을 대신 증명하지 않습니다. 연구/효과/개입/실천/방법론/표본/한계 문장은 각 문장 끝에 citation이 있어야 합니다.\n"
            "- source token은 context에 표시된 `source token: [N](#source-N)`만 사용하십시오.\n"
            "- citation 없이 '연구에 따르면', '효과', '도움', '회복', '향상', '감소', '기여', '중요합니다' 같은 표현을 쓰지 마십시오.\n"
            "- context에 없는 방법론, 표본, 한계, 인과효과, 예상 결과는 말하지 마십시오. 필요하면 '이 발췌만으로는 확인하기 어렵다'고 쓰십시오.\n"
            "- 금지 표현: '효과적일 수 있습니다', '도움이 될 수 있습니다', '회복력을 높입니다', '향상시킵니다'. 대신 '이 발췌는 ...를 보고합니다', '...와 관련될 수 있음을 시사합니다', '...를 탐색해 볼 수 있습니다'처럼 근거 범위를 드러내십시오.\n"
        )

    def _standard_grounding_rules(self, is_journal: bool = False) -> str:
        scope = "일기" if is_journal else "고민"
        return (
            "6. [검색된 연구 발췌와 주변 문맥]에 기재된 특정 연구 근거나 구절을 활용하는 서술문 끝에는 반드시 괄호 형식의 인라인 마크다운 링크로 출처를 추가하십시오 (예: `[1](#source-1)` 또는 `[2](#source-2)`). 인덱스 번호는 `[논문 N]`의 번호 N과 정확히 매칭되도록 하십시오.\n"
            "7. 방법론, 표본, 한계, 인과효과는 발췌나 주변 문맥에 명시된 경우에만 언급하십시오. 명시되지 않았다면 '이 발췌만으로는 확인하기 어렵다'고 정직하게 표현하십시오.\n"
            f"8. 답변 본문은 [Evidence-to-Reflection] 구조를 따르십시오. 먼저 발췌가 실제로 말하는 범위를 짧게 밝히고, 그다음 사용자의 {scope}와 연결되는 조심스러운 해석을 제안한 뒤, 확정적 효과가 아닌 작은 성찰/실천 가능성을 제시하십시오. 근거에 없는 결과 예측이나 인과 단정은 피하고, 마지막에는 열린 질문으로 마무리하십시오.\n"
            "9. 근거 문장은 '입증합니다/효과가 있습니다/반드시 좋아집니다'처럼 단정하지 말고, '이 발췌는 ...을 시사합니다', '이 문맥 안에서는 ...로 이해할 수 있습니다'처럼 출처 범위가 드러나는 표현을 쓰십시오. 사용자의 구체 상황에 대한 해석은 반드시 조심스러운 가설로 표현하십시오.\n\n"
            "10. '연구에 따르면'으로 시작하는 문장, 개입/효과/회복 가능성을 말하는 문장, 또는 구체적 실천 제안은 같은 문장 끝에 반드시 citation을 붙이십시오. citation 없이 새로운 효과나 결과를 덧붙이지 마십시오.\n"
            "11. 발췌에 등장하지 않은 실천법이나 효과를 임의로 추가하지 마십시오. 사용자가 해볼 수 있는 제안은 발췌에 명시된 개념을 '작게 탐색해 볼 수 있다' 수준으로만 표현하십시오.\n\n"
            "12. 금지 표현: '효과적일 수 있습니다', '도움이 될 수 있습니다', '회복력을 높입니다', '향상시킵니다'. 대신 '이 발췌는 ...를 보고합니다', '...와 관련될 수 있음을 시사합니다', '...를 탐색해 볼 수 있습니다'처럼 근거 범위가 드러나는 표현을 쓰십시오.\n"
            "13. 공감 문장과 열린 질문을 제외한 설명 문장은 모두 검색된 발췌에 직접 근거해야 합니다. 근거가 약한 일반 심리 설명은 쓰지 말고, 답변은 5~8문장의 간결한 성찰형 구조로 유지하십시오.\n\n"
        )

    def _topic_answer_guidance(self, query: str, query_variants: list[str] = None) -> str:
        focus = self._infer_query_focus(query, query_variants)
        if focus == "positive_psych" and self._positive_psych_topic(query) == "loneliness":
            return (
                "[주제별 근거 제한: 외로움/사회적 연결]\n"
                "- 이 섹션은 위의 일반 상담 원칙보다 우선합니다. 검색 발췌가 아동, 환자, 특정 사례 등 "
                "좁은 맥락을 다룬다면, 그 맥락을 넘어 사용자의 외로움 원인을 단정하지 마십시오.\n"
                "- 반드시 제목/번호/불릿 없이 총 5문장만 작성하십시오. 1문장은 공감만 담고 citation 없이 씁니다. "
                "2문장은 '검색된 발췌 중 하나는 이 연구 맥락에서...'로 시작해 사회적 고립/소속감 근거와 그 표본·맥락을 함께 밝히고 citation으로 끝냅니다. "
                "3문장은 '다른 발췌는 이 표본에서...'로 시작해 또래 관계, 사회적 지지, 피해 경험, 대인관계 중 선택된 근거만 설명하고 citation으로 끝냅니다. "
                "4문장은 '그래서 지금의 외로움은...'으로 시작해 사용자의 원인을 단정하지 않고 관계 상황과 필요한 지원을 살펴볼 수 있다는 조심스러운 연결만 씁니다. "
                "5문장은 열린 질문 1개만 씁니다. 이 5문장 외에 어떤 설명·제안·마무리도 추가하지 마십시오.\n"
                "- '주요 원인', '사회적 연결의 필요성을 반영', '가치나 의미를 발견', '풍부하게 만들', "
                "'긍정적인 영향을 미칠', '작은 변화를 시도', '생각해보는 것이 중요/좋', '주로', "
                "'비롯', '줄이는 데 중요한 역할'처럼 "
                "발췌 밖의 원인·가치·처방으로 넓어지는 표현을 피하십시오.\n"
                "- 사용자에게 직접 해결책을 제안하지 말고, 어떤 관계 상황에서 외로움이 커지는지와 "
                "어떤 종류의 관계나 지원이 조금 덜 외롭게 느껴지는지를 묻는 질문으로 마무리하십시오.\n"
            )
        if focus == "cbt" and self._cbt_topic(query, query_variants) == "rumination_sleep":
            return (
                "[주제별 근거 제한: 반추/수면]\n"
                "- 이 섹션은 위의 일반 상담 원칙보다 우선합니다. 이 답변에서는 의미치료식 의미 찾기, 가치 발견, "
                "교훈 찾기, 일기 쓰기, 감정 정리 효과를 제안하지 마십시오.\n"
                "- 이 질문에서는 근거 범위를 분리하십시오: (1) 반추/반복적 부정 사고와 불안·우울, "
                "(2) CBT/인지 재구성과 반추 습관, (3) 수면·불면 맥락의 재앙화/역기능적 믿음. "
                "세 범위를 하나의 직접 원인-효과 사슬로 합치지 마십시오.\n"
                "- 검색 발췌에 직접 나오지 않는 일기 쓰기, 감정 표출, 의미 찾기, 교훈 찾기, 가치 탐색, "
                "현재 순간 집중, 정서 조절 효과를 실천 제안이나 효과처럼 말하지 마십시오. "
                "특히 '의미', '가치', '교훈', '배운 점', '긍정적인 측면', '도움이 될 수', "
                "'감정을 정리', '생각을 정리', '앞으로 나아가'라는 표현을 피하십시오.\n"
                "- 답변 전체에서 다음 표현은 쓰지 마십시오: '유발', '심화', '수면의 질을 떨어뜨', "
                "'효과적', '도움을 줄 수', '도움이 될 수', '중요합니다', '살펴보는 것이 도움이'. "
                "대신 '이 발췌는 ...와 관련될 수 있음을 시사한다', '이 발췌만으로는 직접 원인을 확인하기 어렵다'처럼 쓰십시오.\n"
                "- 과거 실수 반추가 사용자의 수면 문제를 직접 일으킨다고 단정하지 마십시오. 수면을 언급할 때는 "
                "발췌가 불면·수면장애의 재앙화나 역기능적 믿음만 다루는지 범위를 밝히십시오. "
                "'주요 원인', '악화', '이어질 수', '결국', '수면의 질을 떨어뜨린다'처럼 직접 인과를 암시하는 표현은 피하십시오.\n"
                "- 답변 구조는 5~6문장으로 제한하십시오: 공감 1문장, 반추 근거 1~2문장, CBT/인지 재구성 근거 "
                "1문장, 수면 근거가 선택된 경우 그 범위 제한 1문장, 열린 질문 1문장.\n"
                "- 수면을 다룰 때는 과거 실수 반추와 수면을 직접 연결하지 말고, 수면 관련 발췌가 불면·수면장애 "
                "맥락의 역기능적 믿음이나 반복적인 수면 걱정만 다루는지 범위를 밝히십시오.\n"
                "- 특히 '우울한 기분을 유발', '우울증으로 이어질 수', '수면의 질에 영향을', "
                "'수면의 질을 악화', '수면의 질을 떨어뜨', '수면을 방해', '수면 문제를 악화', '회복에 부정적인 영향', "
                "'주목할 필요', '살펴보는 것이 좋'처럼 "
                "출처 범위를 넘어 원인·악화·처방을 암시하는 표현을 피하십시오.\n"
                "- 마지막 열린 질문은 다음 범위로만 제한하십시오: '반복해서 떠오르는 생각은 무엇인가요?', "
                "'그 생각을 뒷받침하는 근거와 반대되는 근거는 각각 무엇인가요?', "
                "'그 생각 안에 재앙화나 흑백논리 같은 인지 오류가 섞여 있나요?'. "
                "배운 점, 긍정적 의미, 가치 발견을 묻지 마십시오.\n"
            )
        if focus == "sdt" and self._sdt_topic(query, query_variants) == "competence_inadequacy":
            return (
                "[주제별 근거 제한: 유능감]\n"
                "- 이 섹션은 위의 일반 상담 원칙보다 우선합니다. 유능감은 SDT의 기본 심리 욕구라는 범위에서 설명하되, 사용자가 부족감을 느끼는 원인을 "
                "과거 실패, 성격, 노력 부족 등으로 진단하지 마십시오.\n"
                "- 실패 경험 관련 발췌가 선택되었다면, 해당 연구의 특정 맥락에서 반복된 실패나 좌절이 "
                "유능감 저하와 연결될 수 있다고만 제한해 말하십시오.\n"
                "- 도전적이지만 달성 가능한 과제, 긍정적 피드백, 숙달 경험을 언급할 때는 발췌가 다루는 "
                "맥락을 넘어 일반적 효과나 확실한 개선으로 말하지 마십시오.\n"
                "- 실천 제안은 '작게 탐색해 볼 수 있다' 수준으로만 쓰고, 자기 칭찬이나 작은 목표가 "
                "유능감을 반드시 만든다고 약속하지 마십시오.\n"
                "- 반드시 제목/번호/불릿 없이 총 5문장만 작성하십시오. 1문장은 공감만 담고 citation 없이 씁니다. "
                "2문장은 '검색된 발췌에서 유능감은...'으로 시작해 유능감의 정의/범위만 설명하고 citation으로 끝냅니다. "
                "3문장은 '또 다른 발췌는...'으로 시작해 도전 가능 과제와 긍정적 피드백의 연구 맥락만 설명하고 citation으로 끝냅니다. "
                "4문장은 '그래서 지금의 부족감은...'으로 시작해 능력이 없다는 결론이 아니라 과제 난이도와 필요한 지원을 살펴볼 신호로만 조심스럽게 연결하고 citation으로 끝냅니다. "
                "5문장은 열린 질문 1개만 씁니다. 이 5문장 외에 어떤 설명·제안·마무리도 추가하지 마십시오.\n"
                "- citation은 반드시 `[1](#source-1)`처럼 인라인 마크다운 링크 형식으로 쓰십시오. `(논문 1)`, `[논문 1]`, 일반 괄호 표기는 쓰지 마십시오.\n"
                "- 특히 '과거의 경험이나 현재의 상황에서 비롯', '감정이 메시지를 준다', "
                "'작은 성공/작은 목표가 유능감을 느끼는 데 도움이 된다', '중요합니다'처럼 "
                "출처 밖의 원인·효과·가치 해석으로 들리는 표현을 피하십시오.\n"
                "- 사용자에게 직접 지시하는 실천 문장으로 확장하지 마십시오. '떠올려 보세요', "
                "'생각해보세요', '설정해보세요', '도움이 될 수 있습니다', '기여할 수 있습니다', "
                "'중요한 역할을 합니다'라는 표현을 쓰지 마십시오.\n"
                "- 발췌가 직접 말하지 않은 결과 예측을 붙이지 마십시오. 특히 '더 나은 성과', "
                "'성과를 경험', '자신에 대한 믿음이 커진다', '자신감이 생긴다'처럼 유능감 근거를 "
                "성과나 자기확신 향상으로 넓히는 표현을 피하십시오.\n"
                "- 마지막 열린 질문은 다음 범위로만 제한하십시오: '지금 하는 일 중 너무 쉽거나 너무 어렵게 "
                "느껴지는 과제는 무엇인가요?', '어떤 피드백이나 지원이 있으면 조금 더 해볼 만하다고 "
                "느껴질까요?'. 작은 목표의 효과나 부족감의 메시지를 묻지 마십시오. 마지막은 질문으로만 "
                "끝내고, 질문 뒤에 '도움이 되기를 바랍니다' 같은 효과 암시 문장을 덧붙이지 마십시오.\n"
            )
        if focus == "logotherapy" and self._logotherapy_topic(query, query_variants) == "grief_loss":
            return (
                "[주제별 근거 제한: 상실/애도]\n"
                "- 이 섹션은 위의 일반 상담 원칙보다 우선합니다. 이 답변에서는 일반적인 Frankl 설명, "
                "고통이 기회가 된다는 표현, 상실에서 교훈을 찾아야 한다는 표현으로 넓히지 마십시오.\n"
                "- 검색 발췌가 직접 말하는 범위만 다루십시오: 가까운 사람의 죽음/상실, 애도나 고통이 의미의 "
                "위기를 만들 수 있다는 점, 그리고 의미가 개인적·관계적 맥락에서 다시 구성될 수 있다는 점입니다.\n"
                "- 반드시 제목/번호/불릿 없이 총 5문장만 작성하십시오. 1문장은 공감만 담고 citation 없이 씁니다. "
                "2문장은 '검색된 발췌 중 하나는...'으로 시작해 가까운 사람의 죽음/상실 또는 애도와 의미 위기의 근거만 설명하고 citation으로 끝냅니다. "
                "3문장은 '또 다른 발췌는...'으로 시작해 의미 형성이 개인적·관계적 맥락에서 일어날 수 있다는 근거만 설명하고 citation으로 끝냅니다. "
                "4문장은 '그래서 지금의 질문은...'으로 시작해 살아갈 이유를 당장 찾아야 한다는 압박이 아니라, 관계가 남긴 의미를 천천히 살펴볼 수 있다는 조심스러운 연결만 쓰고 citation으로 끝냅니다. "
                "5문장은 열린 질문 1개만 씁니다. 이 5문장 외에 어떤 설명·제안·마무리도 추가하지 마십시오.\n"
                "- '새로운 목적', '새로운 방향', '고통이 기회', '도움이 될 수', '마음을 정리', "
                "'배운 것은 무엇', '가르침', '원했던 삶의 방식', '적용할 수 있을까', '의미를 찾아야'처럼 "
                "상실을 성급한 교훈·처방·성장 이야기로 바꾸는 표현을 피하십시오.\n"
                "- 마지막 열린 질문은 다음 범위로만 제한하십시오: '그 사람과의 관계에서 아직 마음에 남아 있는 의미는 무엇인가요?', "
                "'그 사람을 떠올릴 때 가장 선명하게 남는 가치나 장면은 무엇인가요?'. 답변은 질문으로만 끝내십시오.\n"
            )
        return ""

    def _reflection_instruction(self, query: str, query_variants: list[str] = None) -> str:
        if self._infer_query_focus(query, query_variants) == "positive_psych" and self._positive_psych_topic(query) == "loneliness":
            return (
                "해결책을 성급하게 직접 주지 마십시오. 이 케이스에서는 가치·의미 탐색으로 전환하지 말고, "
                "사용자가 어떤 관계 상황에서 외로움이 커지는지, 어떤 종류의 관계나 지원이 조금 덜 외롭게 "
                "느껴지는지 살펴보도록 돕는 질문만 사용하세요."
            )
        if self._infer_query_focus(query, query_variants) == "cbt" and self._cbt_topic(query, query_variants) == "rumination_sleep":
            return (
                "해결책을 성급하게 직접 주지 마십시오. 다만 이 케이스에서는 가치·의미·교훈 탐색으로 전환하지 말고, "
                "사용자가 반복되는 생각의 내용, 그 생각의 근거와 반대 근거, 인지 오류 가능성을 차분히 살펴보도록 돕는 질문만 사용하세요."
            )
        if self._infer_query_focus(query, query_variants) == "sdt" and self._sdt_topic(query, query_variants) == "competence_inadequacy":
            return (
                "해결책을 성급하게 직접 주지 마십시오. 다만 이 케이스에서는 부족감의 의미·메시지·교훈을 묻지 말고, "
                "사용자가 최근 유능감을 조금이라도 느꼈던 상황, 지금 과제가 너무 어렵거나 지원이 부족한 지점, "
                "어떤 피드백이나 지원이 필요한지를 살펴보도록 돕는 질문만 사용하세요. 답변 본문에서는 "
                "'떠올려 보세요', '생각해보세요', '설정해보세요' 같은 직접 지시형 실천 제안을 쓰지 마세요."
            )
        if self._infer_query_focus(query, query_variants) == "logotherapy" and self._logotherapy_topic(query, query_variants) == "grief_loss":
            return (
                "해결책을 성급하게 직접 주지 마십시오. 이 케이스에서는 상실을 교훈, 성장, 새로운 목적 찾기로 "
                "서둘러 바꾸지 말고, 사용자가 그 사람과의 관계에서 아직 마음에 남아 있는 의미나 가치를 "
                "천천히 살펴보도록 돕는 질문만 사용하세요."
            )
        return (
            "해결책을 성급하게 직접 주지 마십시오. 대신 사용자가 스스로 가치와 의미(창조적 가치, 경험적 가치, 태도적 가치)를 깨달을 수 있도록 유도하세요."
        )

    def _attach_context_windows(self, db, documents: list) -> None:
        projection = {
            "content": 1,
            "metadata": 1,
            "chunk_id": 1,
            "document_id": 1,
            "filename": 1,
            "title": 1,
            "section": 1,
            "page_start": 1,
            "page_end": 1,
            "chunk_index": 1,
            "language": 1,
            "text_quality": 1,
        }

        for doc in documents:
            doc["expanded_content"] = doc.get("content") or ""
            document_id = doc.get("document_id")
            chunk_index = doc.get("chunk_index")

            if document_id is None or chunk_index is None:
                continue

            try:
                chunk_index = int(chunk_index)
                cursor = db.documents.find(
                    {
                        "document_id": document_id,
                        "chunk_index": {"$gte": chunk_index - 1, "$lte": chunk_index + 1},
                    },
                    projection,
                ).sort("chunk_index", 1).limit(3)
                neighbors = list(cursor)
            except Exception as e:
                log_event(
                    "rag_adjacent_chunks_error",
                    level="warning",
                    document_id=document_id,
                    chunk_index=chunk_index,
                    error_type=type(e).__name__,
                )
                continue

            if not neighbors:
                continue

            parts = []
            for neighbor in neighbors[:3]:
                candidate = self._candidate_from_result(neighbor)
                location = self._source_location_text(candidate)
                parts.append(f"[{location}]\n{candidate.get('content')}")

            doc["expanded_content"] = self._truncate_context("\n\n".join(parts))

    async def get_streaming_response(self, query: str, history: list = None, is_journal: bool = False, journal_id: str = None, user_id: str = None) -> AsyncGenerator[str, None]:
        if history is None:
            history = []
            
        db = get_db()

        # 0단계: 위기 신호(자해/자살) 우선 감지 — RAG/소크라테스식 질문보다 먼저 처리한다.
        if detect_crisis(query):
            yield f"data: {json.dumps({'type': 'status', 'data': 'generating'}, ensure_ascii=False)}\n\n"
            # 프론트엔드가 검증된 전문 상담 핫라인 배너를 노출하도록 신호를 보낸다.
            yield f"data: {json.dumps({'type': 'crisis'}, ensure_ascii=False)}\n\n"

            crisis_system_prompt = (
                "당신은 위기 상황에 처한 사용자를 돕는 따뜻하고 침착한 정신건강 동반자 'Logos-Log'입니다.\n"
                "사용자의 메시지에서 자해 또는 자살과 관련된 신호가 감지되었습니다. 지금은 학술적 분석이나 소크라테스식 역질문을 하는 시간이 아닙니다.\n\n"
                "[반드시 지켜야 할 응답 원칙]\n"
                "1. 사용자의 고통을 가볍게 여기지 말고, 진심 어린 공감으로 지금의 감정을 따뜻하게 인정해 주십시오.\n"
                "2. '당신은 혼자가 아니며, 당신의 안전이 무엇보다 소중하다'는 메시지를 분명하게 전하십시오.\n"
                "3. 지금 즉시 신뢰할 수 있는 전문가의 도움을 받도록 부드럽지만 분명하게 권유하고, 24시간 운영되는 '자살예방 상담전화 1393'으로 연락할 것을 따뜻하게 안내하십시오.\n"
                "4. 자해 방법이나 위험한 행동에 관한 구체적 정보는 어떤 경우에도 절대 언급하지 마십시오.\n"
                "5. 섣부른 해결책 제시나 가치 분석, 논문 인용을 하지 말고, 짧고 진솔하며 인간적인 어조로 3~5문장 이내로 답하십시오.\n"
                "6. 곁에 있어 주겠다는 안정감과 함께, 도움을 요청하는 것이 결코 약함이 아니라 용기 있는 일임을 전하며 마무리하십시오."
            )

            messages = [SystemMessage(content=crisis_system_prompt)]
            for h in history:
                if h.role == "user":
                    messages.append(HumanMessage(content=h.content))
                elif h.role == "bot":
                    messages.append(AIMessage(content=h.content))
            messages.append(HumanMessage(content=query))

            full_answer = ""
            async for chunk in self.llm.astream(messages):
                if chunk.content:
                    full_answer += chunk.content
                    yield f"data: {json.dumps({'type': 'chunk', 'data': chunk.content}, ensure_ascii=False)}\n\n"

            if journal_id:
                try:
                    db.chat_messages.insert_one({
                        "journal_id": journal_id,
                        "role": "user",
                        "content": encrypt(query),
                        "sources": [],
                        "user_id": user_id,
                        "created_at": datetime.datetime.utcnow().isoformat()
                    })
                    db.chat_messages.insert_one({
                        "journal_id": journal_id,
                        "role": "bot",
                        "content": encrypt(full_answer),
                        "sources": [],
                        "crisis": True,
                        "user_id": user_id,
                        "created_at": datetime.datetime.utcnow().isoformat()
                    })
                except Exception as e:
                    log_event(
                        "rag_crisis_chat_save_error",
                        level="warning",
                        user_hash=safe_hash(user_id),
                        journal_hash=safe_hash(journal_id),
                        error_type=type(e).__name__,
                    )

            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        # 장기 기억: 사용자 가치 프로필 로드
        value_profile = self._get_user_value_profile(user_id)
        
        # 쿼리가 일상적(인사, 단순 오프닝 등)인지 확인
        is_casual = self.is_casual_query(query, is_journal)
        
        if is_casual:
            # RAG 검색 우회: 빈 리스트 및 가이드 생략
            sources = []
            yield f"data: {json.dumps({'type': 'status', 'data': 'generating'}, ensure_ascii=False)}\n\n"
            
            system_prompt = (
                "당신은 의미치료(Logotherapy) 및 긍정 심리학을 기반으로 사용자의 내면 성찰을 돕는 따뜻하고 다정한 카운셀러 AI 'Logos-Log'입니다.\n\n"
                "[대화 원칙]\n"
                "1. 사용자가 구체적인 고민 대신 단순한 인사나 짧은 오프닝 멘트를 건넸습니다. 친절하고 열린 태도로 사용자를 따뜻하게 환대해 주세요.\n"
                "2. 답변에 '논문 자료를 찾지 못했다'거나 '학술 자료가 없다'는 식의 투박하거나 부정적인 시스템 안내 문구를 절대로 출력하지 마십시오. 자연스럽고 일상적인 대화 톤으로 응답하십시오.\n"
                "3. 상투적인 리액션을 넘어, 사용자가 오늘 하루 느낀 구체적인 감정이나 직면하고 있는 마음속 고민을 편안하게 털어놓을 수 있도록 다정하게 유도하십시오.\n"
                "4. 답변의 마무리에는 사용자가 자신의 마음을 돌아보거나 오늘의 이야기를 구체적으로 시작할 수 있도록 돕는 따뜻하고 열린 질문을 1~2개 건네주십시오.\n\n"
                f"{value_profile}"
            )
            
            messages = [SystemMessage(content=system_prompt)]
            for h in history:
                if h.role == "user":
                    messages.append(HumanMessage(content=h.content))
                elif h.role == "bot":
                    messages.append(AIMessage(content=h.content))
            messages.append(HumanMessage(content=query))
            
            # 소스 데이터 전송 (RAG 우회이므로 빈 배열 전달)
            yield f"data: {json.dumps({'type': 'sources', 'data': sources}, ensure_ascii=False)}\n\n"
            
            full_answer = ""
            async for chunk in self.llm.astream(messages):
                if chunk.content:
                    full_answer += chunk.content
                    yield f"data: {json.dumps({'type': 'chunk', 'data': chunk.content}, ensure_ascii=False)}\n\n"
            
            if journal_id:
                try:
                    user_msg = {
                        "journal_id": journal_id,
                        "role": "user",
                        "content": encrypt(query),
                        "sources": [],
                        "user_id": user_id,
                        "created_at": datetime.datetime.utcnow().isoformat()
                    }
                    db.chat_messages.insert_one(user_msg)
                    
                    bot_msg = {
                        "journal_id": journal_id,
                        "role": "bot",
                        "content": encrypt(full_answer),
                        "sources": sources,
                        "user_id": user_id,
                        "created_at": datetime.datetime.utcnow().isoformat()
                    }
                    db.chat_messages.insert_one(bot_msg)
                except Exception as e:
                    log_event(
                        "rag_casual_chat_save_error",
                        level="warning",
                        user_hash=safe_hash(user_id),
                        journal_hash=safe_hash(journal_id),
                        error_type=type(e).__name__,
                    )
            
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return
            
        # 1단계: 쿼리 영어 번역 및 학술 키워드 확장 (Query Expansion)
        yield f"data: {json.dumps({'type': 'status', 'data': 'translating'}, ensure_ascii=False)}\n\n"
        query_variants = await self._expand_query_variants(query)
        english_query = query_variants[0] if query_variants else query
            
        # 2단계: 질문 임베딩 및 벡터 검색 (검색 단계는 retrieve()로 분리되어 평가와 동일 경로를 공유)
        yield f"data: {json.dumps({'type': 'status', 'data': 'searching'}, ensure_ascii=False)}\n\n"
        reranked_results, results = await self.retrieve(query, english_query=english_query, query_variants=query_variants)

        # 최종 선별된 문서들에 대해 병렬 한국어 번역 및 요약 수행
        import asyncio
        yield f"data: {json.dumps({'type': 'status', 'data': 'translating_sources'}, ensure_ascii=False)}\n\n"
        
        translation_tasks = [self._translate_and_summarize_paper(res.get("content")) for res in reranked_results]
        translated_results = await asyncio.gather(*translation_tasks)

        sources = []
        context_text = ""
        expanded_contexts = []
        primary_excerpts = []
        sentence_template_enabled = self._sentence_template_enabled()
        
        for idx, res in enumerate(reranked_results):
            meta = res.get("metadata", {})
            author = meta.get("author", "Unknown")
            year = meta.get("year", "")
            title = res.get("title") or meta.get("title") or "Untitled"
            trans_res = translated_results[idx]
            
            # Primary excerpt is sent to the frontend; expanded context is used only for generation.
            sources.append({
                "id": res.get("id"),
                "content": res.get("content"),        # 영어 원문 primary 발췌
                "content_ko": trans_res.get("content_ko"), # 한국어 번역본
                "summary_ko": trans_res.get("summary_ko"), # 한국어 1줄 발췌 요약
                "author": author,
                "year": year,
                "title": title,
                "filename": res.get("filename") or meta.get("filename", ""),
                "section": res.get("section"),
                "page_start": res.get("page_start"),
                "page_end": res.get("page_end"),
                "chunk_id": res.get("chunk_id"),
                "chunk_index": res.get("chunk_index"),
                "language": res.get("language") or meta.get("language"),
                "text_quality": res.get("text_quality") or meta.get("text_quality"),
                "category": meta.get("category", ""),
                "similarity": res.get("similarity", 0)
            })
            primary_excerpts.append(res.get("content") or "")
            expanded_contexts.append(res.get("expanded_content") or res.get("content") or "")
            location = self._source_location_text(res)
            source_header = (
                f"\n- [논문 {idx+1}] source token: [{idx+1}](#source-{idx+1}) | 제목: {title} | 저자: {author}, 연도: {year} | 위치: {location}\n"
                if sentence_template_enabled
                else f"\n- [논문 {idx+1}] 제목: {title} | 저자: {author}, 연도: {year} | 위치: {location}\n"
            )
            context_text += (
                source_header +
                f"검색된 핵심 발췌:\n{res.get('content')}\n\n"
                f"주변 문맥(최대 앞뒤 1청크):\n{res.get('expanded_content') or res.get('content')}\n"
            )

        self.last_generation_trace = {
            **(self.last_retrieval_trace or {}),
            "sources": sources,
            "primary_excerpts": primary_excerpts,
            "expanded_contexts": expanded_contexts,
            "context_text": context_text,
            "verifier_mode": getattr(self, "verifier_mode", "off"),
            "claim_checker_mode": getattr(self, "claim_checker_mode", "off"),
            "answer_template_mode": getattr(self, "answer_template_mode", "standard"),
            "verification": {
                "enabled": False,
                "mode": getattr(self, "verifier_mode", "off"),
            },
            "claim_check": {
                "enabled": False,
                "mode": getattr(self, "claim_checker_mode", "off"),
            },
        }

        # 3단계: RAG 답변 생성 돌입
        yield f"data: {json.dumps({'type': 'status', 'data': 'generating'}, ensure_ascii=False)}\n\n"

        # 소크라테스식 대화법 & 의미치료 기반 시스템 프롬프트 생성
        grounded_answer_template = (
            self._grounded_answer_template(is_journal=is_journal)
            if sentence_template_enabled
            else self._standard_grounding_rules(is_journal=is_journal)
        )
        topic_answer_guidance = self._topic_answer_guidance(query, query_variants)
        reflection_instruction = self._reflection_instruction(query, query_variants)
        self.last_generation_trace["topic_answer_guidance"] = topic_answer_guidance
        self.last_generation_trace["reflection_instruction"] = reflection_instruction
        if is_journal:
            if reranked_results:
                system_prompt = (
                    "당신은 의미치료(Logotherapy) 및 긍정 심리학을 기반으로 사용자의 일기(저널)를 분석하고 깊이 있는 성찰을 돕는 전문 카운셀러 AI 'Logos-Log'입니다.\n\n"
                    "[대화 원칙]\n"
                    "1. 사용자가 작성한 일기 내용과 감정을 따뜻하고 분석적인 시선으로 살펴보고 공감해주세요. 피상적인 위로는 삼가고, 사용자가 털어놓은 마음에 귀를 기울이고 있음을 느끼게 하십시오.\n"
                    "2. 제공된 [검색된 연구 발췌와 주변 문맥]의 학술적/심리학적 통찰을 자연스럽게 녹여 일기의 고민을 새로운 각도에서 볼 수 있도록 지원하세요. 절대 논문 전체를 요약한 것처럼 말하지 말고, 검색된 발췌를 근거로 삼으세요.\n"
                    "3. 일기 성찰에 사용할 연구 발췌가 포함되었으므로, '논문 자료를 찾지 못했다' 또는 '매칭되는 논문이 없다'는 뉘앙스의 부정적인 안내 문구를 절대로 답변에 출력하지 마십시오.\n"
                    "4. 사용자의 일기 속 고민을 의미치료 관점(예: 태도의 가치, 시련 속 의미 찾기, 선택과 책임)으로 전환할 수 있는 가능성을 정중히 제안해 보세요.\n"
                    "5. 답변 마무리에는 일기 내용을 토대로 사용자가 스스로 내면의 답을 찾아가도록 돕는 '소크라테스식 열린 역질문'을 1~2개 반드시 던져 대화를 이어가십시오.\n"
                    f"{grounded_answer_template}\n"
                    f"{topic_answer_guidance}\n"
                    f"{value_profile}"
                    f"[검색된 연구 발췌와 주변 문맥]\n{context_text}"
                )
            else:
                system_prompt = (
                    "당신은 의미치료(Logotherapy) 및 긍정 심리학을 기반으로 사용자의 일기(저널)를 분석하고 깊이 있는 성찰을 돕는 전문 카운셀러 AI 'Logos-Log'입니다.\n\n"
                    "[대화 원칙]\n"
                    "1. 사용자가 쓴 일기의 주제와 관련하여 직접 매칭되는 특정 논문 자료를 찾지 못했습니다. 답변의 서두에 다음과 같이 자연스럽게 안내하십시오: "
                    "\"작성하신 일기와 밀접하게 부합하는 논문 자료는 찾지 못했지만, 의미치료와 심리학적 원칙을 바탕으로 마음에 대해 깊은 대화를 나누고 싶습니다.\"\n"
                    "2. 논문 직접 인용 없이도, 빅터 프랭클의 의미 치료 이론 및 긍정 심리학 지식을 기반으로 깊이 있고 따뜻한 대답과 공감을 구성하십시오.\n"
                    "3. 답변의 마지막에는 사용자가 자신의 상황을 찬찬히 되돌아볼 수 있게 돕는 열린 소크라테스식 역질문을 1~2개 포함하세요.\n\n"
                    f"{value_profile}"
                )
        else:
            if reranked_results:
                system_prompt = (
                    "당신은 의미치료(Logotherapy) 및 긍정 심리학을 기반으로 사용자의 자아 성찰을 돕는 전문 카운셀러 AI 'Logos-Log'입니다.\n\n"
                    "[대화 원칙]\n"
                    "1. 제공된 [검색된 연구 발췌와 주변 문맥]의 학술적 통찰을 자연스럽게 대화에 녹여 설명하되, 논문 전체 요약이 아닌 따뜻하고 신뢰감 있는 상담 톤을 유지하세요.\n"
                    "2. 답변에 검색된 연구 발췌가 포함되었으므로, 절대로 '학술 자료를 찾지 못했다'거나 '직접 매칭되는 논문은 없다'는 부정적인 안내 문구를 출력하지 마십시오. 검색된 발췌 내용을 아하 모먼트의 핵심 학술 근거로 활용하여 답변하세요.\n"
                    "3. 상투적인 위로(\"힘드셨겠네요\", \"힘내세요\")는 피하고, 사용자의 마음에 깊이 공감한 후 그 안의 감정을 정돈해 주는 반영적 태도를 취하세요.\n"
                    f"4. {reflection_instruction}\n"
                    "5. 대화의 마무리에는 사용자가 자신의 상황을 되돌아보고 성찰할 수 있는 구체적이고 깊이 있는 '소크라테스식 열린 질문(역질문)'을 1~2개 던져주세요.\n"
                    f"{grounded_answer_template}\n"
                    f"{topic_answer_guidance}\n"
                    f"{value_profile}"
                    f"[검색된 연구 발췌와 주변 문맥]\n{context_text}"
                )
            else:
                system_prompt = (
                    "당신은 의미치료(Logotherapy) 및 긍정 심리학을 기반으로 사용자의 자아 성찰을 돕는 전문 카운셀러 AI 'Logos-Log'입니다.\n\n"
                    "[대화 원칙]\n"
                    "1. 사용자의 질문/고민과 완벽히 매칭되는 논문을 데이터베이스에서 찾지 못했습니다. 따라서 답변의 서두는 반드시 다음 안내 문구로 시작하십시오: "
                    "\"고민하신 내용과 직접적으로 매칭되는 특정 학술 논문은 찾지 못했지만, 의미치료와 심리학적 관점에서 이야기를 나누어보고 싶습니다.\"\n"
                    "2. 특정 논문 인용 없이도, 빅터 프랭클의 의미 치료 이론(시련을 가치로 승화하기, 고통 속에서 태도 선택하기) 및 긍정 심리학 지식을 기반으로 깊이 있고 따뜻한 대답을 구성하세요.\n"
                    "3. 해결책을 직접 제시하지 말고, 사용자가 스스로 생각하여 내면의 자유와 책임을 인식하도록 소크라테스식 질문을 건네세요.\n"
                    "4. 답변 끝에는 성찰을 이끌어낼 수 있는 열린 질문(역질문)을 반드시 1~2개 포함하세요.\n\n"
                    f"{value_profile}"
                )
        
        messages = [SystemMessage(content=system_prompt)]
        
        # 이전 대화 내역(히스토리) 추가
        for h in history:
            if h.role == "user":
                messages.append(HumanMessage(content=h.content))
            elif h.role == "bot":
                messages.append(AIMessage(content=h.content))
                
        # 현재 질문 추가
        messages.append(HumanMessage(content=query))
        
        # 4. 소스(출처) 데이터를 첫 번째 이벤트로 전송
        yield f"data: {json.dumps({'type': 'sources', 'data': sources}, ensure_ascii=False)}\n\n"
        
        # 5. LLM 스트리밍 응답 (한 글자씩 Yield & 누적)
        full_answer = ""
        response_llm = self.answer_llm if reranked_results else self.llm
        if self._answer_verifier_enabled(reranked_results):
            try:
                draft_answer = await self._generate_answer_text(messages)
                self.last_generation_trace["draft_answer"] = draft_answer
                yield f"data: {json.dumps({'type': 'status', 'data': 'verifying'}, ensure_ascii=False)}\n\n"
                verification = await self._verify_answer_against_context(
                    query=query,
                    answer=draft_answer,
                    context_text=context_text,
                    sources=sources,
                    is_journal=is_journal,
                )
                full_answer = verification.get("answer") or draft_answer
                self.last_generation_trace["verification"] = {
                    "enabled": True,
                    "mode": getattr(self, "verifier_mode", "off"),
                    "changed": verification.get("changed", False),
                    "error": verification.get("error"),
                    "unsupported_claims": verification.get("unsupported_claims", []),
                }
                for text_chunk in self._stream_text_chunks(full_answer):
                    yield f"data: {json.dumps({'type': 'chunk', 'data': text_chunk}, ensure_ascii=False)}\n\n"
            except Exception as e:
                log_event("rag_verified_generation_error", level="warning", error_type=type(e).__name__)
                self.last_generation_trace["verification"] = {
                    "enabled": True,
                    "mode": getattr(self, "verifier_mode", "off"),
                    "changed": False,
                    "error": str(e),
                    "unsupported_claims": [],
                }
                async for chunk in response_llm.astream(messages):
                    if chunk.content:
                        full_answer += chunk.content
                        yield f"data: {json.dumps({'type': 'chunk', 'data': chunk.content}, ensure_ascii=False)}\n\n"
        elif self._claim_checker_enabled(reranked_results):
            try:
                draft_answer = await self._generate_answer_text(messages)
                self.last_generation_trace["draft_answer"] = draft_answer
                yield f"data: {json.dumps({'type': 'status', 'data': 'checking_claims'}, ensure_ascii=False)}\n\n"
                claim_check = await self._check_answer_claim_citations(
                    query=query,
                    answer=draft_answer,
                    context_text=context_text,
                    sources=sources,
                    is_journal=is_journal,
                )
                full_answer = claim_check.get("answer") or draft_answer
                self.last_generation_trace["claim_check"] = {
                    "enabled": True,
                    "mode": getattr(self, "claim_checker_mode", "off"),
                    "changed": claim_check.get("changed", False),
                    "error": claim_check.get("error"),
                    "edits": claim_check.get("edits", []),
                }
                for text_chunk in self._stream_text_chunks(full_answer):
                    yield f"data: {json.dumps({'type': 'chunk', 'data': text_chunk}, ensure_ascii=False)}\n\n"
            except Exception as e:
                log_event("rag_claim_checked_generation_error", level="warning", error_type=type(e).__name__)
                self.last_generation_trace["claim_check"] = {
                    "enabled": True,
                    "mode": getattr(self, "claim_checker_mode", "off"),
                    "changed": False,
                    "error": str(e),
                    "edits": [],
                }
                async for chunk in response_llm.astream(messages):
                    if chunk.content:
                        full_answer += chunk.content
                        yield f"data: {json.dumps({'type': 'chunk', 'data': chunk.content}, ensure_ascii=False)}\n\n"
        else:
            async for chunk in response_llm.astream(messages):
                if chunk.content:
                    full_answer += chunk.content
                    yield f"data: {json.dumps({'type': 'chunk', 'data': chunk.content}, ensure_ascii=False)}\n\n"
                
        # 6. 대화 이력 데이터베이스 저장 (journal_id가 전달된 경우에만 수행)
        if journal_id:
            try:
                user_content = query
                if query.startswith("[일기 분석 요청]"):
                    lines = query.split('\n')
                    title = ""
                    emotion = ""
                    body = ""
                    if len(lines) > 1:
                        title = lines[1].replace("제목: ", "").strip()
                    if len(lines) > 2:
                        emotion = lines[2].replace("감정 상태: ", "").strip()
                    if len(lines) > 4:
                        body = "\n".join(lines[4:]).strip()
                    user_content = f"📖 **[일기 분석 시작]**\n\n**제목:** {title}\n**감정:** {emotion}\n\n{body}"

                # 1) 사용자 질문 메시지 저장
                user_msg = {
                    "journal_id": journal_id,
                    "role": "user",
                    "content": encrypt(user_content),
                    "sources": [],
                    "user_id": user_id,
                    "created_at": datetime.datetime.utcnow().isoformat()
                }
                db.chat_messages.insert_one(user_msg)

                # 2) AI 답변 메시지 저장
                bot_msg = {
                    "journal_id": journal_id,
                    "role": "bot",
                    "content": full_answer,
                    "sources": sources,
                    "user_id": user_id,
                    "created_at": datetime.datetime.utcnow().isoformat()
                }
                db.chat_messages.insert_one(bot_msg)
            except Exception as e:
                log_event(
                    "rag_chat_save_error",
                    level="warning",
                    user_hash=safe_hash(user_id),
                    journal_hash=safe_hash(journal_id),
                    error_type=type(e).__name__,
                )

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    def get_chat_history(self, journal_id: str, user_id: str = None) -> list:
        """
        특정 일기 ID에 종속된 대화 이력을 생성 시간 순으로 조회합니다.
        """
        db = get_db()
        try:
            query = {"journal_id": journal_id}
            if user_id:
                query["user_id"] = user_id
            cursor = db.chat_messages.find(query).sort("created_at", 1)
            docs = list(cursor)
            for d in docs:
                d["content"] = decrypt(d.get("content"))
            return docs
        except Exception as e:
            log_event(
                "rag_chat_history_fetch_error",
                level="error",
                user_hash=safe_hash(user_id),
                journal_hash=safe_hash(journal_id),
                error_type=type(e).__name__,
            )
            return []

    async def _rerank_documents(self, query: str, documents: list, query_variants: list[str] = None) -> list:
        if not documents:
            return []

        try:
            focus_guidance = self._reranker_focus_guidance(query, query_variants)
            docs_text = ""
            for idx, doc in enumerate(documents):
                meta = doc.get("metadata") or {}
                ranking_score = doc.get("ranking_score")
                rrf_score = doc.get("rrf_score")
                focus_boost = doc.get("focus_boost")
                relevance_signal = []
                if ranking_score is not None:
                    relevance_signal.append(f"ranking_score={ranking_score:.4f}")
                if rrf_score is not None:
                    relevance_signal.append(f"rrf_score={rrf_score:.4f}")
                if focus_boost is not None:
                    relevance_signal.append(f"focus_boost={focus_boost:.4f}")
                docs_text += (
                    f"\n[Document {idx}]\n"
                    f"Title: {doc.get('title') or meta.get('title') or 'Untitled'}\n"
                    f"Document ID: {doc.get('document_id')}\n"
                    f"Section: {doc.get('section') or 'unknown'}\n"
                    f"Page: {doc.get('page_start') or 'unknown'}\n"
                    f"Retrieval Signal: {', '.join(relevance_signal) if relevance_signal else 'not available'}\n"
                    f"Content: {doc.get('content')}\n"
                )

            system_prompt = (
                "You are an academic document retrieval re-ranking assistant.\n"
                "Your task is to evaluate the relevance of the retrieved academic paper chunks to the user's query.\n"
                "Select up to 4 chunks that are most relevant and directly helpful in addressing the user's psychological concern or question.\n"
                "Use the focus guidance as the relevance rubric when it is provided.\n"
                "Use Retrieval Signal only as a secondary hint; direct support for the query is more important than the numeric score.\n"
                "Prefer chunks that directly support the specific constructs in the query or search variants, not merely adjacent broad theories.\n"
                "Do not select chunks that are mostly bibliography/reference-list entries, citation lists, or paper-title lists unless the query asks for references.\n"
                "Prefer diversity across different papers when relevance is comparable, but keep the most relevant chunk first.\n"
                "You MUST output a raw JSON object with this shape: {\"indices\": [2, 0, 4]}.\n"
                "If less than 4 chunks are relevant, include only the relevant indices. If none are relevant, output {\"indices\": []}.\n"
                "Do NOT provide any explanations, markdown, or extra text."
            )

            variants_text = "\n".join(f"- {variant}" for variant in (query_variants or []) if variant)
            user_prompt = (
                f"User Query: {query}\n\n"
                f"Search Variants:\n{variants_text or '(none)'}\n\n"
                f"Focus Guidance:\n{focus_guidance or '(none)'}\n\n"
                f"Retrieved Academic Chunks:{docs_text}"
            )

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]

            response = await self.reranker_llm.ainvoke(messages, response_format={"type": "json_object"})
            result = response.content.strip()
            log_event("rag_llm_rerank_result", selected_count=len(documents))

            data = json.loads(result)
            indices = data.get("indices", [])
            if not isinstance(indices, list):
                return documents[:4]
            indices = [int(idx) for idx in indices if isinstance(idx, int) or str(idx).isdigit()]
            indices = [idx for idx in indices if 0 <= idx < len(documents)]
            
            seen = set()
            unique_indices = []
            for idx in indices:
                if idx not in seen:
                    seen.add(idx)
                    unique_indices.append(idx)
            
            reranked_docs = [documents[idx] for idx in unique_indices[:4]]
            reranked_docs = self._reinforce_grief_loss_companion(
                reranked_docs,
                documents,
                query,
                query_variants,
            )
            return reranked_docs

        except Exception as e:
            log_event("rag_llm_rerank_error", level="warning", error_type=type(e).__name__)
            return documents[:4]

    def _get_user_value_profile(self, user_id: str = None) -> str:
        if not user_id:
            return ""
        db = get_db()
        try:
            cursor = db.value_cards.find(
                {"user_id": user_id},
                {"keyword": 1, "insight": 1}
            ).sort("created_at", -1).limit(5)
            
            cards = list(cursor)
            if not cards:
                return ""
                
            profile_text = "\n[사용자가 과거 성찰을 통해 깨달아 저장한 핵심 가치 목록]\n"
            for card in cards:
                keyword = card.get("keyword", "").strip()
                insight = (decrypt(card.get("insight", "")) or "").strip()
                if keyword and insight:
                    profile_text += f"- 핵심 가치: **{keyword}** | 인사이트: \"{insight}\"\n"
            profile_text += "\n[행동 지침] 대화 시 사용자의 과거 가치 목록을 은연중에 상기시키거나, 오늘의 고민과 자연스럽게 결합하여 1인칭 반영 및 질문을 전개하십시오. 단, 과거 가치를 부자연스럽게 나열하지 말고 대화의 흐름 속에 자연스럽게 스며들도록 인용하십시오.\n"
            return profile_text
        except Exception as e:
            log_event("rag_user_value_profile_error", level="warning", user_hash=safe_hash(user_id), error_type=type(e).__name__)
            return ""
