import { useState } from 'react';
import { ArrowRight, BookOpen, MessageSquare, Sparkles, BrainCircuit } from 'lucide-react';
import { markOnboardingComplete } from '../utils/onboardingState';

const STEPS = [
  {
    id: 'welcome',
    emoji: '🌌',
    title: 'Logos-Log에 오신 것을 환영합니다',
    description:
      '오늘의 기록이 가치 카드가 되고, 가치 카드는 이번 주의 작은 실험으로 이어집니다.\n분석에서 멈추지 않고 내 선택이 실제로 도움이 됐는지 함께 돌아봅니다.',
    cta: '시작하기',
    visual: (
      <div style={{ fontSize: '4rem', textAlign: 'center', marginBottom: '8px', filter: 'drop-shadow(0 0 20px rgba(99,102,241,0.5))' }}>
        🌌
      </div>
    ),
  },
  {
    id: 'features',
    emoji: '✨',
    title: '세 가지 핵심 경험',
    description: null,
    cta: '다음',
    visual: null,
    features: [
      {
        icon: <BookOpen size={18} color="#a5b4fc" />,
        title: '근거가 보이는 성찰 대화',
        desc: '심리학 연구 발췌를 바탕으로 생각을 더 선명하게 정리합니다',
        color: 'rgba(99,102,241,0.15)',
        border: 'rgba(99,102,241,0.3)',
      },
      {
        icon: <MessageSquare size={18} color="#6ee7b7" />,
        title: '소크라테스식 대화',
        desc: '정답 대신 질문으로, 스스로 깨달음을 얻도록 안내합니다',
        color: 'rgba(16,185,129,0.12)',
        border: 'rgba(16,185,129,0.3)',
      },
      {
        icon: <Sparkles size={18} color="#f9a8d4" />,
        title: '작은 실험과 회고',
        desc: '저장한 가치 카드가 이번 주에 해볼 행동과 나중의 회고로 이어집니다',
        color: 'rgba(236,72,153,0.12)',
        border: 'rgba(236,72,153,0.3)',
      },
    ],
  },
  {
    id: 'start',
    emoji: '📝',
    title: '첫 번째 성찰을 시작해볼까요?',
    description:
      '오늘 하루 어떤 감정을 느꼈나요?\n짧은 메모라도 좋습니다. 기록을 남기면 성찰 대화와 가치 카드로 이어갈 수 있어요.',
    cta: '첫 일기 작성하기',
    visual: (
      <div style={{ fontSize: '3.5rem', textAlign: 'center', marginBottom: '8px' }}>
        📝
      </div>
    ),
  },
];

const OnboardingFlow = ({ onComplete }) => {
  const [step, setStep] = useState(0);
  const [isExiting, setIsExiting] = useState(false);

  const currentStep = STEPS[step];
  const isLast = step === STEPS.length - 1;

  const complete = () => {
    setIsExiting(true);
    setTimeout(() => {
      markOnboardingComplete();
      onComplete();
    }, 350);
  };

  const handleNext = () => {
    if (isLast) {
      complete();
    } else {
      setStep(s => s + 1);
    }
  };

  const handleSkip = complete;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(5, 5, 15, 0.96)',
        backdropFilter: 'blur(12px)',
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '24px',
        opacity: isExiting ? 0 : 1,
        transition: 'opacity 0.35s ease',
      }}
    >
      {/* 배경 그라디언트 오브 */}
      <div style={{ position: 'absolute', top: '20%', left: '15%', width: '300px', height: '300px', borderRadius: '50%', background: 'radial-gradient(circle, rgba(99,102,241,0.08) 0%, transparent 70%)', pointerEvents: 'none' }} />
      <div style={{ position: 'absolute', bottom: '20%', right: '15%', width: '250px', height: '250px', borderRadius: '50%', background: 'radial-gradient(circle, rgba(16,185,129,0.06) 0%, transparent 70%)', pointerEvents: 'none' }} />

      <div
        style={{
          width: '100%',
          maxWidth: '480px',
          background: 'rgba(10, 11, 26, 0.9)',
          border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: '24px',
          padding: '40px 36px 32px',
          boxShadow: '0 30px 60px rgba(0,0,0,0.6)',
          display: 'flex',
          flexDirection: 'column',
          gap: '28px',
          position: 'relative',
        }}
      >
        {/* 로고 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', justifyContent: 'center' }}>
          <BrainCircuit size={20} color="var(--accent-primary)" />
          <span style={{ fontSize: '0.85rem', fontWeight: '700', color: 'var(--text-muted)', letterSpacing: '0.05em' }}>
            LOGOS-LOG
          </span>
        </div>

        {/* 스텝 인디케이터 */}
        <div style={{ display: 'flex', gap: '6px', justifyContent: 'center' }}>
          {STEPS.map((_, i) => (
            <div
              key={i}
              style={{
                height: '4px',
                borderRadius: '100px',
                background: i === step ? 'var(--accent-primary)' : i < step ? 'rgba(99,102,241,0.4)' : 'rgba(255,255,255,0.1)',
                width: i === step ? '28px' : '12px',
                transition: 'all 0.35s ease',
              }}
            />
          ))}
        </div>

        {/* 메인 콘텐츠 */}
        <div style={{ textAlign: 'center' }}>
          {currentStep.visual}

          <h2
            style={{
              fontSize: '1.35rem',
              fontWeight: '800',
              margin: '0 0 14px 0',
              background: 'linear-gradient(135deg, #ffffff 0%, rgba(165,180,252,0.9) 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              lineHeight: '1.35',
            }}
          >
            {currentStep.title}
          </h2>

          {currentStep.description && (
            <p
              style={{
                fontSize: '0.88rem',
                color: 'var(--text-muted)',
                lineHeight: '1.7',
                margin: 0,
                whiteSpace: 'pre-line',
              }}
            >
              {currentStep.description}
            </p>
          )}

          {/* 피처 카드들 (step 1) */}
          {currentStep.features && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '4px', textAlign: 'left' }}>
              {currentStep.features.map((f, i) => (
                <div
                  key={i}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '14px',
                    background: f.color,
                    border: `1px solid ${f.border}`,
                    borderRadius: '14px',
                    padding: '14px 16px',
                  }}
                >
                  <div
                    style={{
                      width: '36px',
                      height: '36px',
                      borderRadius: '10px',
                      background: 'rgba(255,255,255,0.07)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                    }}
                  >
                    {f.icon}
                  </div>
                  <div>
                    <p style={{ margin: '0 0 3px 0', fontWeight: '700', fontSize: '0.85rem', color: '#ffffff' }}>{f.title}</p>
                    <p style={{ margin: 0, fontSize: '0.76rem', color: 'var(--text-muted)', lineHeight: '1.45' }}>{f.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 액션 버튼 */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <button
            id="onboarding-next-btn"
            onClick={handleNext}
            style={{
              width: '100%',
              padding: '14px',
              borderRadius: '12px',
              border: 'none',
              background: 'var(--accent-gradient)',
              color: '#ffffff',
              fontWeight: '700',
              fontSize: '0.95rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              boxShadow: '0 6px 20px rgba(99,102,241,0.3)',
              transition: 'all 0.2s',
              fontFamily: 'inherit',
            }}
            onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-1px)'; e.currentTarget.style.boxShadow = '0 8px 24px rgba(99,102,241,0.4)'; }}
            onMouseLeave={e => { e.currentTarget.style.transform = 'none'; e.currentTarget.style.boxShadow = '0 6px 20px rgba(99,102,241,0.3)'; }}
          >
            <span>{currentStep.cta}</span>
            <ArrowRight size={16} />
          </button>

          {!isLast && (
            <button
              onClick={handleSkip}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--text-muted)',
                fontSize: '0.8rem',
                cursor: 'pointer',
                padding: '6px',
                fontFamily: 'inherit',
                transition: 'color 0.2s',
              }}
              onMouseEnter={e => { e.currentTarget.style.color = '#ffffff'; }}
              onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-muted)'; }}
            >
              건너뛰기
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default OnboardingFlow;
