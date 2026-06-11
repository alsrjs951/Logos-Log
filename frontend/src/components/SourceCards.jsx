import { useState } from 'react';
import { createPortal } from 'react-dom';
import { BookOpen, ChevronDown, ChevronUp, X, Sparkles } from 'lucide-react';

// 카테고리별 색상 및 아이콘 매핑
const CATEGORY_STYLES = {
  'logotherapy': { color: '#6366f1', bg: 'rgba(99,102,241,0.12)', label: '의미치료' },
  'positive_psych': { color: '#10b981', bg: 'rgba(16,185,129,0.12)', label: '긍정심리학' },
  'positive_psychology': { color: '#10b981', bg: 'rgba(16,185,129,0.12)', label: '긍정심리학' },
  'sdt': { color: '#f59e0b', bg: 'rgba(245,158,11,0.12)', label: '자기결정이론' },
  'existential': { color: '#8b5cf6', bg: 'rgba(139,92,246,0.12)', label: '실존주의' },
  'self_determination': { color: '#f59e0b', bg: 'rgba(245,158,11,0.12)', label: '자기결정이론' },
  'cbt': { color: '#06b6d4', bg: 'rgba(6,182,212,0.12)', label: '인지행동치료' },
  'cognitive': { color: '#06b6d4', bg: 'rgba(6,182,212,0.12)', label: '인지심리' },
  'trauma': { color: '#ec4899', bg: 'rgba(236,72,153,0.12)', label: '트라우마/회복' },
  'mindfulness': { color: '#34d399', bg: 'rgba(52,211,153,0.12)', label: '마음챙김' },
  'default': { color: '#94a3b8', bg: 'rgba(148,163,184,0.12)', label: '심리학' },
};

function getCategoryStyle(category) {
  if (!category) return CATEGORY_STYLES.default;
  const key = category.toLowerCase().replace(/[^a-z_]/g, '').replace(/ /g, '_');
  return CATEGORY_STYLES[key] || CATEGORY_STYLES.default;
}

function getRelevanceLabel(similarity) {
  if (similarity >= 0.85) return { label: '매우 높음', color: '#10b981' };
  if (similarity >= 0.70) return { label: '높음', color: '#6366f1' };
  if (similarity >= 0.55) return { label: '보통', color: '#f59e0b' };
  return { label: '참고', color: '#94a3b8' };
}

function normalizeText(value) {
  return String(value || '').replace(/\s+/g, ' ').trim();
}

function truncateText(value, maxLength) {
  const text = normalizeText(value);
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength).trim()}…`;
}

function getReferenceSummary(src) {
  const summary = normalizeText(src.summary_ko);
  if (summary) return summary;

  const translated = normalizeText(src.content_ko);
  if (translated) return truncateText(translated, 170);

  const original = normalizeText(src.content);
  if (original) return truncateText(original, 170);

  return 'AI 답변과 관련된 연구 발췌입니다. 자세한 맥락은 논문 원문에서 확인해 보세요.';
}

function getSearchHint(src, categoryLabel) {
  return [src.title, src.author, src.year, categoryLabel]
    .filter(Boolean)
    .join(' ');
}

function getSourceTitle(src) {
  return normalizeText(src.title || src.filename);
}

function getLocationLabel(src) {
  const parts = [];
  if (src.section) parts.push(src.section);
  if (src.page_start && src.page_end && src.page_start !== src.page_end) {
    parts.push(`p. ${src.page_start}-${src.page_end}`);
  } else if (src.page_start) {
    parts.push(`p. ${src.page_start}`);
  }
  if (src.chunk_index !== undefined && src.chunk_index !== null) {
    parts.push(`chunk ${src.chunk_index}`);
  }
  return parts.join(' · ');
}

// 개별 논문 카드 컴포넌트
const SourceCard = ({ src, index, msgIndex }) => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [showOriginal, setShowOriginal] = useState(false);
  const [showExcerpt, setShowExcerpt] = useState(false);
  const catStyle = getCategoryStyle(src.category);
  const relevance = getRelevanceLabel(src.similarity);
  const similarityPct = Math.round(src.similarity * 100);

  // 한국어 번역이 있으면 번역을 기본으로 노출
  const hasTranslation = src.content_ko && src.content_ko !== src.content;
  const mainText = hasTranslation && !showOriginal ? src.content_ko : src.content;
  const referenceSummary = getReferenceSummary(src);
  const searchHint = getSearchHint(src, catStyle.label);
  const hasExcerpt = Boolean(normalizeText(src.content_ko || src.content));
  const sourceTitle = getSourceTitle(src);
  const locationLabel = getLocationLabel(src);

  // 근거 발췌 요약 미리보기
  const previewText = truncateText(referenceSummary, 92);

  return (
    <>
      <div
        id={`source-card-${msgIndex}-${index + 1}`}
        className="source-card-v2"
        style={{
          flex: '0 0 260px',
          background: 'rgba(10, 11, 26, 0.65)',
          border: `1px solid ${catStyle.color}30`,
          borderRadius: '14px',
          padding: '0',
          transition: 'all 0.25s',
          cursor: 'pointer',
          overflow: 'hidden',
          backdropFilter: 'blur(8px)',
          boxShadow: `0 4px 20px rgba(0,0,0,0.3), inset 0 0 0 1px ${catStyle.color}15`,
        }}
        onClick={() => {
          setShowOriginal(false); // 모달 열릴 때 번역본(기본값) 초기화
          setShowExcerpt(false);
          setIsModalOpen(true);
        }}
        title="클릭하여 근거 발췌와 출처 정보 보기"
      >
        {/* 카드 상단 헤더 - 관련도 진행 바 */}
        <div style={{
          height: '3px',
          background: `linear-gradient(90deg, ${catStyle.color} ${similarityPct}%, rgba(255,255,255,0.05) ${similarityPct}%)`,
          borderRadius: '14px 14px 0 0',
        }} />

        <div style={{ padding: '14px' }}>
          {/* 카테고리 배지 + 관련도 */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <span style={{
              fontSize: '0.68rem',
              fontWeight: '700',
              color: catStyle.color,
              background: catStyle.bg,
              padding: '2px 8px',
              borderRadius: '20px',
              letterSpacing: '0.3px',
              border: `1px solid ${catStyle.color}25`,
            }}>
              {catStyle.label}
            </span>
            <span style={{
              fontSize: '0.68rem',
              fontWeight: '700',
              color: relevance.color,
              display: 'flex',
              alignItems: 'center',
              gap: '3px',
            }}>
              <Sparkles size={9} />
              관련도 {similarityPct}%
            </span>
          </div>

          {/* 저자 및 연도 - 학술 인용 형식 */}
          <div style={{
            display: 'flex',
            alignItems: 'baseline',
            gap: '6px',
            marginBottom: '8px',
          }}>
            <BookOpen size={11} color={catStyle.color} style={{ flexShrink: 0, marginTop: '2px' }} />
            <p style={{
              fontSize: '0.78rem',
              fontWeight: '700',
              color: 'var(--text-main)',
              lineHeight: '1.3',
            }}>
              {src.author || '저자 미상'}
              {src.year && (
                <span style={{
                  fontWeight: '400',
                  color: 'var(--text-muted)',
                  marginLeft: '4px',
                }}>({src.year})</span>
              )}
            </p>
          </div>

          {sourceTitle && (
            <p style={{
              fontSize: '0.72rem',
              fontWeight: '650',
              color: 'var(--text-main)',
              lineHeight: '1.35',
              margin: '0 0 8px',
            }}>
              {truncateText(sourceTitle, 76)}
            </p>
          )}

          {locationLabel && (
            <p style={{
              fontSize: '0.66rem',
              color: catStyle.color,
              lineHeight: '1.35',
              margin: '0 0 8px',
              fontWeight: 700,
            }}>
              {locationLabel}
            </p>
          )}

          {/* 내용 미리보기 */}
          <p style={{
            fontSize: '0.76rem',
            color: 'var(--text-muted)',
            lineHeight: '1.55',
            margin: 0,
            fontStyle: 'italic',
          }}>
            "{previewText}"
          </p>

          {/* 하단 전문 보기 버튼 */}
          <div style={{
            marginTop: '12px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '6px',
            color: '#ffffff',
            background: 'rgba(255, 255, 255, 0.04)',
            border: `1px solid ${catStyle.color}35`,
            borderRadius: '8px',
            padding: '6px 12px',
            fontSize: '0.74rem',
            fontWeight: '600',
            transition: 'all 0.2s',
          }}
          onMouseEnter={e => {
            e.currentTarget.style.background = `${catStyle.color}20`;
            e.currentTarget.style.borderColor = catStyle.color;
          }}
          onMouseLeave={e => {
            e.currentTarget.style.background = 'rgba(255, 255, 255, 0.04)';
            e.currentTarget.style.borderColor = `${catStyle.color}35`;
          }}
          >
            <BookOpen size={11} color={catStyle.color} />
            <span>근거 발췌 보기</span>
          </div>
        </div>
      </div>

      {/* 전체 내용 모달 */}
      {isModalOpen && createPortal(
        <div
          style={{
            position: 'fixed',
            top: 0, left: 0, width: '100vw', height: '100vh',
            background: 'rgba(5, 5, 15, 0.80)',
            backdropFilter: 'blur(10px)',
            zIndex: 9000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '30px',
          }}
          onClick={() => setIsModalOpen(false)}
        >
          <div
            style={{
              width: '100%',
              maxWidth: '600px',
              maxHeight: '80vh',
              background: 'rgba(12, 14, 28, 0.97)',
              border: `1px solid ${catStyle.color}40`,
              borderRadius: '20px',
              boxShadow: `0 25px 60px rgba(0,0,0,0.6), 0 0 0 1px ${catStyle.color}15`,
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
            }}
            onClick={e => e.stopPropagation()}
          >
            {/* 모달 상단 헤더 */}
            <div style={{
              height: '4px',
              background: `linear-gradient(90deg, ${catStyle.color}, ${catStyle.color}60)`,
              flexShrink: 0,
            }} />
            <div style={{
              padding: '20px 24px 16px',
              borderBottom: `1px solid rgba(255,255,255,0.06)`,
              flexShrink: 0,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ flex: 1, marginRight: '16px' }}>
                  {/* 인용 번호 + 카테고리 */}
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '10px' }}>
                    <span style={{
                      fontSize: '0.68rem',
                      fontWeight: '800',
                      color: 'rgba(255,255,255,0.4)',
                      letterSpacing: '0.5px',
                    }}>
                      [참고문헌 {index + 1}]
                    </span>
                    <span style={{
                      fontSize: '0.68rem',
                      fontWeight: '700',
                      color: catStyle.color,
                      background: catStyle.bg,
                      padding: '2px 8px',
                      borderRadius: '20px',
                      border: `1px solid ${catStyle.color}25`,
                    }}>
                      {catStyle.label}
                    </span>
                  </div>
                  {/* 저자, 연도 */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <BookOpen size={14} color={catStyle.color} />
                    <p style={{
                      fontSize: '0.92rem',
                      fontWeight: '700',
                      color: 'var(--text-main)',
                    }}>
                      {src.author || '저자 미상'}
                      {src.year && (
                        <span style={{
                          fontWeight: '400',
                          color: 'var(--text-muted)',
                          fontSize: '0.82rem',
                          marginLeft: '6px',
                        }}>({src.year})</span>
                      )}
                    </p>
                  </div>
                  {sourceTitle && (
                    <p style={{
                      marginTop: '8px',
                      fontSize: '0.82rem',
                      fontWeight: '650',
                      color: 'var(--text-main)',
                      lineHeight: '1.45',
                    }}>
                      {sourceTitle}
                    </p>
                  )}
                  {locationLabel && (
                    <p style={{
                      marginTop: '6px',
                      fontSize: '0.7rem',
                      fontWeight: 700,
                      color: catStyle.color,
                    }}>
                      {locationLabel}
                    </p>
                  )}
                </div>
                
                {/* 닫기 버튼 */}
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <button
                    onClick={() => setIsModalOpen(false)}
                    style={{
                      background: 'rgba(255,255,255,0.06)',
                      border: '1px solid rgba(255,255,255,0.1)',
                      borderRadius: '8px',
                      width: '32px',
                      height: '32px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      cursor: 'pointer',
                      color: 'var(--text-muted)',
                      flexShrink: 0,
                    }}
                  >
                    <X size={15} />
                  </button>
                </div>
              </div>
              {/* 관련도 바 */}
              <div style={{ marginTop: '14px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>AI 성찰 답변과의 관련도</span>
                  <span style={{ fontSize: '0.7rem', fontWeight: '700', color: relevance.color }}>
                    {relevance.label} ({similarityPct}%)
                  </span>
                </div>
                <div style={{
                  height: '5px',
                  background: 'rgba(255,255,255,0.06)',
                  borderRadius: '10px',
                  overflow: 'hidden',
                }}>
                  <div style={{
                    height: '100%',
                    width: `${similarityPct}%`,
                    background: `linear-gradient(90deg, ${catStyle.color}, ${relevance.color})`,
                    borderRadius: '10px',
                    transition: 'width 0.8s ease',
                  }} />
                </div>
              </div>
            </div>

            {/* 본문 내용 */}
            <div style={{
              padding: '20px 24px',
              overflowY: 'auto',
              flex: 1,
            }}>
              <div style={{
                marginBottom: '14px',
                padding: '16px 18px',
                background: 'rgba(99, 102, 241, 0.08)',
                border: '1px solid rgba(99, 102, 241, 0.24)',
                borderRadius: '14px',
                display: 'flex',
                gap: '10px',
                alignItems: 'flex-start',
              }}>
                <span style={{ fontSize: '1.1rem', flexShrink: 0 }}>💡</span>
                <div>
                  <p style={{ fontSize: '0.7rem', fontWeight: '800', color: '#a5b4fc', margin: '0 0 6px 0', letterSpacing: '0.3px' }}>근거 발췌 요약</p>
                  <p style={{ fontSize: '0.9rem', fontWeight: '650', color: 'var(--text-main)', lineHeight: '1.65', margin: 0 }}>
                    {referenceSummary}
                  </p>
                </div>
              </div>

              <div style={{
                marginBottom: '16px',
                padding: '14px 16px',
                background: 'rgba(255,255,255,0.035)',
                border: `1px solid ${catStyle.color}22`,
                borderRadius: '12px',
              }}>
                <p style={{
                  fontSize: '0.72rem',
                  fontWeight: '800',
                  color: catStyle.color,
                  margin: '0 0 6px 0',
                  letterSpacing: '0.2px',
                }}>
                  더 깊게 읽어보고 싶다면
                </p>
                <p style={{
                  fontSize: '0.82rem',
                  lineHeight: '1.6',
                  color: 'var(--text-muted)',
                  margin: 0,
                }}>
                  이 요약은 AI 답변에 사용된 검색 발췌를 읽기 쉽게 정리한 것입니다.
                  연구의 방법, 표본, 한계, 전체 맥락까지 확인하고 싶다면 아래 정보로 논문을 찾아 원문을 읽어보세요.
                </p>
                {searchHint && (
                  <div style={{
                    marginTop: '10px',
                    padding: '9px 11px',
                    borderRadius: '9px',
                    background: 'rgba(10, 11, 26, 0.45)',
                    border: '1px solid rgba(255,255,255,0.06)',
                  }}>
                    <p style={{ fontSize: '0.65rem', color: 'var(--text-muted)', margin: '0 0 3px 0', fontWeight: 700 }}>추천 검색어</p>
                    <p style={{ fontSize: '0.78rem', color: 'var(--text-main)', margin: 0, lineHeight: 1.45, wordBreak: 'break-word' }}>
                      {searchHint}
                    </p>
                  </div>
                )}
              </div>

              {hasExcerpt && (
                <div style={{
                  marginBottom: '16px',
                  border: '1px solid rgba(255,255,255,0.06)',
                  borderRadius: '12px',
                  background: 'rgba(255,255,255,0.02)',
                  overflow: 'hidden',
                }}>
                  <button
                    onClick={() => setShowExcerpt(v => !v)}
                    style={{
                      width: '100%',
                      border: 'none',
                      background: 'transparent',
                      color: 'var(--text-main)',
                      padding: '12px 14px',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: '12px',
                      fontSize: '0.78rem',
                      fontWeight: 800,
                      fontFamily: 'inherit',
                    }}
                  >
                    <span>근거 발췌 확인</span>
                    <span style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}>{showExcerpt ? '접기' : '펼치기'}</span>
                  </button>

                  {showExcerpt && (
                    <div style={{ padding: '0 14px 14px' }}>
                      {hasTranslation && (
                        <button
                          onClick={() => setShowOriginal(v => !v)}
                          style={{
                            marginBottom: '10px',
                            background: showOriginal ? 'rgba(99,102,241,0.15)' : 'rgba(255,255,255,0.06)',
                            border: '1px solid rgba(255,255,255,0.1)',
                            borderRadius: '20px',
                            padding: '6px 12px',
                            fontSize: '0.68rem',
                            fontWeight: '700',
                            color: showOriginal ? '#a5b4fc' : 'var(--text-muted)',
                            cursor: 'pointer',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            transition: 'all 0.2s',
                            fontFamily: 'inherit',
                          }}
                          title="언어 전환"
                        >
                          <span>{showOriginal ? '🇺🇸 English' : '🇰🇷 한국어 번역'}</span>
                        </button>
                      )}

                      <blockquote style={{
                        margin: 0,
                        padding: '14px 16px',
                        background: `${catStyle.bg}`,
                        border: `none`,
                        borderLeft: `3px solid ${catStyle.color}`,
                        borderRadius: '0 10px 10px 0',
                      }}>
                        <p style={{
                          fontSize: '0.84rem',
                          lineHeight: '1.7',
                          color: 'var(--text-main)',
                          fontStyle: 'italic',
                          margin: 0,
                        }}>
                          "{mainText}"
                        </p>
                      </blockquote>

                      <p style={{
                        marginTop: '10px',
                        fontSize: '0.68rem',
                        color: 'rgba(255,255,255,0.28)',
                        textAlign: 'center',
                      }}>
                        {showOriginal ? '영문 원문 발췌입니다.' : 'AI가 한글로 번역한 발췌입니다.'}
                      </p>
                    </div>
                  )}
                </div>
              )}

              {!hasExcerpt && (
                <p style={{
                  margin: '0 0 16px',
                  fontSize: '0.78rem',
                  lineHeight: '1.55',
                  color: 'var(--text-main)',
                  background: 'rgba(255,255,255,0.03)',
                  border: '1px solid rgba(255,255,255,0.06)',
                  borderRadius: '10px',
                  padding: '12px 14px',
                }}>
                  표시할 발췌 본문은 없지만, 위 요약과 출처 정보를 바탕으로 관련 논문을 찾아볼 수 있습니다.
                </p>
              )}

              {/* 출처 메타 정보 */}
              <div style={{
                marginTop: '16px',
                padding: '12px 14px',
                background: 'rgba(255,255,255,0.03)',
                borderRadius: '10px',
                border: '1px solid rgba(255,255,255,0.06)',
                display: 'flex',
                flexWrap: 'wrap',
                gap: '12px',
              }}>
                {src.author && (
                  <div>
                    <p style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginBottom: '2px' }}>저자</p>
                    <p style={{ fontSize: '0.78rem', fontWeight: '600', color: 'var(--text-main)' }}>{src.author}</p>
                  </div>
                )}
                {src.year && (
                  <div>
                    <p style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginBottom: '2px' }}>출판 연도</p>
                    <p style={{ fontSize: '0.78rem', fontWeight: '600', color: 'var(--text-main)' }}>{src.year}년</p>
                  </div>
                )}
                {src.category && (
                  <div>
                    <p style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginBottom: '2px' }}>분야</p>
                    <p style={{ fontSize: '0.78rem', fontWeight: '600', color: catStyle.color }}>{catStyle.label}</p>
                  </div>
                )}
                {sourceTitle && (
                  <div>
                    <p style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginBottom: '2px' }}>논문명</p>
                    <p style={{ fontSize: '0.78rem', fontWeight: '600', color: 'var(--text-main)' }}>{sourceTitle}</p>
                  </div>
                )}
                {locationLabel && (
                  <div>
                    <p style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginBottom: '2px' }}>발췌 위치</p>
                    <p style={{ fontSize: '0.78rem', fontWeight: '600', color: 'var(--text-main)' }}>{locationLabel}</p>
                  </div>
                )}
              </div>

              <p style={{ marginTop: '14px', fontSize: '0.68rem', color: 'rgba(255,255,255,0.28)', textAlign: 'center', lineHeight: 1.5 }}>
                근거 발췌 요약은 성찰 답변을 이해하기 위한 안내입니다. 학술적 판단에는 원 논문의 전체 맥락을 함께 확인하는 것이 좋습니다.
              </p>
            </div>
          </div>
        </div>,
        document.body
      )}
    </>
  );
};

// 메인 SourceCards 컴포넌트
const SourceCards = ({ sources, msgIndex }) => {
  const [isCollapsed, setIsCollapsed] = useState(true);

  if (!sources || sources.length === 0) return null;

  return (
    <div style={{ marginTop: '16px' }}>
      {/* 출처 토글 헤더 */}
      <button
        onClick={() => setIsCollapsed(v => !v)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          color: 'var(--text-muted)',
          fontSize: '0.72rem',
          fontWeight: '600',
          letterSpacing: '0.5px',
          padding: '0 0 8px 0',
          fontFamily: 'inherit',
          transition: 'color 0.2s',
        }}
        onMouseEnter={e => e.currentTarget.style.color = 'var(--text-main)'}
        onMouseLeave={e => e.currentTarget.style.color = 'var(--text-muted)'}
      >
        <BookOpen size={12} />
        <span>📚 근거 발췌 {sources.length}건 · AI 답변에 사용된 연구 문맥</span>
        {isCollapsed
          ? <ChevronDown size={12} />
          : <ChevronUp size={12} />
        }
      </button>

      <div
        className="sources-scroll-wrapper"
        style={{
          display: isCollapsed ? 'none' : 'flex',
          gap: '10px',
          overflowX: 'auto',
          paddingBottom: '10px',
          scrollbarWidth: 'thin',
        }}
      >
        {sources.map((src, index) => (
          <SourceCard key={index} src={src} index={index} msgIndex={msgIndex} />
        ))}
      </div>
    </div>
  );
};

export default SourceCards;
