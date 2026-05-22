# Logos-Log 데이터 수집 가이드라인 (Data Collection Guide)

Logos-Log의 AI가 사용자의 일기를 분석하고 소크라테스식 질문을 던지기 위해서는 **탄탄한 학술적 배경(Context)** 이 필요합니다. RAG (Retrieval-Augmented Generation) 시스템에 입력할 초기 데이터셋으로 **약 8~12편의 논문 및 학술 자료**를 수집하는 것을 권장합니다.

## 🎯 추천 논문/문헌 주제 및 수량

다음 4가지 핵심 심리학/치료 프레임워크를 바탕으로 자료를 수집해 주세요. (각 PDF 파일은 영어 또는 한국어로 된 텍스트 추출이 가능한 형식이어야 합니다.)

### 1. 의미 치료 (Logotherapy) - 2~3편
* **핵심 내용:** 실존적 공허함 극복, 삶의 의미 찾기, 시련 속에서의 태도 가치, 빅터 프랭클(Viktor Frankl)의 주요 개념
* **검색 키워드:** Logotherapy, Viktor Frankl, Meaning in life, Existential vacuum, Tragic optimism
* **추천 자료:** 
  - 의미 치료의 이론적 배경을 다룬 리뷰 논문 (Review Article)
  - 임상 현장에서의 의미 치료 적용 사례 논문

### 2. 긍정 심리학 (Positive Psychology) - 2~3편
* **핵심 내용:** 마틴 셀리그만의 PERMA 모델 (긍정적 감정, 몰입, 관계, 의미, 성취), 강점(Strengths), 감사(Gratitude), 회복탄력성(Resilience)
* **검색 키워드:** Positive psychology, PERMA model, Well-being, Resilience, Character strengths
* **추천 자료:**
  - PERMA 모델을 설명하고 측정하는 학술 논문
  - 긍정 심리학적 개입(Positive Psychological Interventions, PPIs)의 효과성 연구

### 3. 자기결정성 이론 (Self-Determination Theory, SDT) - 2편
* **핵심 내용:** 인간의 3가지 기본 심리적 욕구 (자율성, 유능성, 관계성), 내재적 동기 유발
* **검색 키워드:** Self-determination theory, Edward Deci, Richard Ryan, Intrinsic motivation, Basic psychological needs
* **추천 자료:**
  - SDT의 기본 개념과 프레임워크를 총망라한 주요 논문 (예: Deci & Ryan의 문헌)

### 4. 인지행동치료 (CBT) 기반 프레임워크 - 2~3편
* **핵심 내용:** 인지적 오류(Cognitive Distortions - 흑백논리, 재앙화 등) 식별, 인지 재구성(Cognitive Restructuring), 감정과 생각의 분리
* **검색 키워드:** Cognitive behavioral therapy, Cognitive distortions, Cognitive restructuring, Beck's cognitive triad
* **추천 자료:**
  - 흔한 인지적 오류의 종류와 이를 바로잡는 소크라테스식 문답법(Socratic Questioning) 가이드북 또는 논문

---

## 📥 수집 방법 및 파일 네이밍 규칙

논문은 Google Scholar, RISS, DBpia, ResearchGate 등에서 PDF 형식으로 다운로드해 주세요. 
다운로드한 파일은 프로젝트의 `data/raw/` 폴더에 넣습니다. 전처리 스크립트가 인식하기 쉽도록 다음과 같은 네이밍 규칙을 지켜주세요.

* **네이밍 규칙:** `[카테고리]_[저자명]_[연도]_[키워드].pdf`
* **예시:**
  * `logotherapy_frankl_1985_mans_search_for_meaning.pdf`
  * `positive_psych_seligman_2011_perma_flourish.pdf`
  * `sdt_deci_ryan_2000_intrinsic_motivation.pdf`
  * `cbt_beck_1979_cognitive_distortions.pdf`

## ⚙️ 다음 단계
수집된 PDF 파일들이 `data/raw/` 폴더에 준비되면, 백엔드의 `preprocess.py` 스크립트를 실행하여 PDF 텍스트 추출 및 노이즈 제거 작업을 자동으로 수행할 수 있습니다.
