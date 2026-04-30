제공해주신 'WEEK 9 AI OPEN SOURCE SOFTWARE Deploying to Any Platform' 강의 자료를 바탕으로 핵심 내용과 실습 과제를 마크다운으로 정리해 드립니다.

## 📌 강의 개요 및 학습 목표
* **과목명:** AI Open Source Software (9주차)
* **담당 교수:** 전세진 교수
* **강의 주제:** 다양한 플랫폼으로 배포하기 (Deploying to Any Platform)
* **학습 목표:**
  * **자동 배포:** 웹(Web) 및 서버리스(Serverless) 등 다양한 플랫폼에 대한 자동화된 배포 파이프라인 구축 능력을 기릅니다.
  * **컨테이너 배포:** Docker 및 Kubernetes를 활용하여 일관된 배포 환경을 구현합니다.
  * **클라우드 자동화:** AWS, GCP 등 주요 클라우드 플랫폼의 인프라 및 배포 자동화 방법을 학습합니다.
  * **배포 전략 수립:** 개발(Dev), 스테이징(Staging), 운영(Prod) 등 환경별 특성에 맞는 배포 전략과 프로세스를 설계합니다.
  * **무중단 배포:** Rolling Update, Blue-Green 등의 배포 전략을 통해 서비스 중단 없는 배포 환경을 구현합니다.

---

## ☁️ 배포 플랫폼 개요 및 설정
서비스의 규모와 요구사항에 따라 다음과 같은 4가지 주요 배포 유형으로 분류됩니다.

* **정적 사이트 호스팅 (Static Site Hosting):** GitHub Pages, Vercel, Netlify, Cloudflare Pages
  * **GitHub Pages:** `.github/workflows/deploy-pages.yml`을 설정하여 `main` 브랜치 푸시 시 자동 배포를 구성할 수 있습니다. 프레임워크에 따라 환경 변수(예: React의 `PUBLIC_URL`, Vue의 `NODE_ENV: production`, Angular의 `--base-href`)를 다르게 설정하여 경로 및 최적화 문제를 해결합니다.
  * **Vercel:** `vercel.json` 파일을 통해 빌더 지정, 라우팅, 환경 변수를 설정하며, Vercel CLI(`vercel --prod`, `vercel env add`)를 통해 터미널 배포가 가능합니다.
  * **Netlify:** `netlify.toml` 파일에 빌드 명령어, 배포 디렉토리, SPA 리다이렉트(`[[redirects]]`), 보안 헤더(`[[headers]]`) 등을 설정합니다.

* **컨테이너 플랫폼 (Container Platforms):** Docker, Kubernetes, AWS ECS/EKS, Google Cloud Run
  * **Docker:** Multi-stage Build를 활용하여 빌드 환경(Builder)과 실행 환경(Production)을 분리함으로써 최종 이미지 크기를 최적화하고 보안을 강화합니다. `docker-compose.yml`을 통해 App과 DB(PostgreSQL), 캐시(Redis) 등 멀티 컨테이너 애플리케이션을 정의하고 실행 순서(`depends_on`)를 제어합니다.

* **클라우드 및 PaaS:** AWS(EC2, S3), GCP, Heroku 등
  * **AWS S3 + CloudFront:** GitHub Actions의 `aws s3 sync`와 `cloudfront create-invalidation`을 활용해 동기화 및 캐시 무효화를 자동화합니다.
  * **AWS Lambda:** 서버리스 함수 패키징 후 `aws lambda update-function-code`로 코드를 갱신합니다.
  * **GCP Cloud Run:** `setup-gcloud`로 인증 후 컨테이너를 빌드, GCR에 푸시하고 Cloud Run 서비스에 배포합니다.

---

## 🔄 배포 전략 (Deployment Strategies)
* **환경별 배포 (Multi-Environment Setup):** GitHub Actions의 Matrix Strategy(`branch: develop, staging, main`)와 동적 시크릿 조회를 활용하여 환경별 파이프라인을 구축합니다.
* **Blue-Green Deployment:** 서비스 중인 환경(Blue)과 새 버전이 배포될 환경(Green)을 동시 운영하며, 충분한 검증 후 트래픽을 전환해 다운타임을 없앱니다.
* **Canary Deployment:** 소수의 사용자(예: 10%)에게 신규 버전을 먼저 배포해 안정성을 검증한 뒤 점진적으로 트래픽을 늘립니다.
* **Rolling Update:** Kubernetes에서 `maxUnavailable: 0` 설정과 Readiness Probe를 결합해 배포 중에도 정상 파드가 100% 작동하도록 보장합니다.
* **Health Check & Rollback:** 배포 후 서비스 응답을 확인하고, 검증 실패 시 즉시 이전 버전으로 복구하는 자동 롤백 로직을 구성해야 합니다.

---

## 🚀 [중요] 9주차 실습 과제 상세

배포 역량 강화를 위한 4단계 실습 과제입니다. 과제 1, 2, 4의 제출 기한은 다음 주 수업 전까지입니다. 과제 3은 파이프라인 최적화에 중점을 둡니다.

### 📝 과제 1: GitHub Pages 배포
정적 웹사이트 호스팅 서비스인 GitHub Pages에 자동 배포 파이프라인을 구축합니다.
* **수행 내용:** 
  1. React(CRA) 또는 Vue CLI로 프로젝트를 생성하고 로컬 빌드를 확인합니다.
  2. `.github/workflows/deploy.yml`을 작성하여 `main` 브랜치 푸시 시 자동 배포되도록 설정합니다.
  3. (선택 사항) CNAME 레코드를 설정하여 커스텀 도메인을 연결해 봅니다.
* **제출 요구사항:** 
  * GitHub Repository URL
  * 배포된 웹사이트 URL (Live)
  * Actions 성공 로그 스크린샷

### 📝 과제 2: Vercel / Netlify 배포
Next.js 또는 Nuxt 프레임워크 기반의 서버리스 배포 및 CI/CD 실습을 진행합니다.
* **수행 내용:** 
  1. Next.js(React) 또는 Nuxt(Vue) 프로젝트를 생성 후 GitHub에 연동합니다.
  2. 플랫폼(Vercel/Netlify) 대시보드에 리포지토리를 연결하고 필요한 환경 변수를 설정합니다.
  3. PR 생성 시 Preview 배포 확인 및 Main 브랜치 병합 시 Production 배포를 확인합니다.
* **제출 요구사항:** 
  * 배포된 데모 사이트 URL
  * 환경 변수 설정 화면 스크린샷
  * CI/CD 빌드 로그 스크린샷

### 📝 과제 3: Docker 컨테이너 배포
컨테이너 기반 애플리케이션 패키징 및 배포 파이프라인을 구축합니다.
* **수행 내용:** 
  1. Node.js Alpine 베이스의 Multi-stage build를 적용한 `Dockerfile`을 작성합니다.
  2. App과 DB 서비스 간 네트워크를 연결한 `docker-compose.yml`을 작성합니다.
  3. GitHub Actions로 이미지를 빌드하고 레지스트리(GHCR 또는 Docker Hub)에 Push합니다.
  4. 서버 배포 스크립트를 작성하여 Health Check 실패 시 이전 버전으로 자동 롤백되도록 구현합니다.
* **제출 요구사항:** 
  * Docker Image Tag / URL
  * `docker-compose.yml` 파일
  * 배포 및 롤백 테스트 로그
* **평가 기준:** 이미지 크기 최적화 및 파이프라인 안정성.

### 📝 과제 4: 클라우드 배포
AWS/GCP 클라우드 서비스를 활용한 자동 배포 파이프라인을 구축합니다.
* **수행 내용:** 
  1. AWS 또는 GCP Free Tier 계정을 생성하고 컴퓨팅 서비스(Lambda, ECS, Cloud Run 등) 초기 설정을 완료합니다.
  2. GitHub Actions에 IAM 권한과 Secret 키를 설정하여 자동 배포 파이프라인을 구축합니다.
  3. **(필수)** CloudWatch(AWS) 또는 Cloud Monitoring(GCP) 대시보드를 구성하여 실시간 상태를 모니터링합니다.
* **제출 요구사항:** 
  * 배포된 서비스 URL (Live)
  * IaC 또는 Workflow 코드 파일
  * 모니터링 대시보드 캡처