import { Fragment, useState, useEffect } from 'react';
import { Loader2, ArrowRight, Sparkles, Info } from 'lucide-react';
import IntentionReview from './IntentionReview';

// Schwartz circumplex 4상위차원 → 색상(가치 색의 가족)
const HIGHER_ORDER_COLORS = {
  openness_to_change: '#6366f1', // Indigo — 변화 개방
  self_enhancement: '#f59e0b',   // Amber — 자기 고양
  conservation: '#06b6d4',       // Cyan — 보존
  self_transcendence: '#10b981', // Emerald — 자기 초월
};
const FALLBACK_COLOR = '#64748b';

/**
 * 의미 네트워크의 "변화(Change)" 뷰 — 종단적 도구의 핵심.
 * 가치카드의 canonical 분포가 시간축으로 어떻게 이동했는지(then-vs-now, 월별 추이)를
 * 보여준다. 데이터가 부족하거나 변화가 미미하면 단언하지 않는다(과잉 정밀 방지).
 */
const MeaningChange = ({ token }) => {
  const [trends, setTrends] = useState(null);
  const [taxonomy, setTaxonomy] = useState({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const load = async () => {
      try {
        const [trendsRes, taxRes] = await Promise.all([
          fetch('http://localhost:8000/api/value-cards/trends', {
            headers: { Authorization: `Bearer ${token}` },
          }),
          fetch('http://localhost:8000/api/value-cards/taxonomy'),
        ]);
        if (!trendsRes.ok) throw new Error('추세 데이터를 불러오지 못했습니다.');
        const trendsData = await trendsRes.json();
        const taxData = taxRes.ok ? await taxRes.json() : { values: [] };
        const taxMap = {};
        (taxData.values || []).forEach((v) => { taxMap[v.key] = v; });
        setTrends(trendsData);
        setTaxonomy(taxMap);
      } catch (err) {
        console.error('Error loading meaning change:', err);
        setError(err.message || '변화 데이터를 불러오지 못했습니다.');
      } finally {
        setIsLoading(false);
      }
    };
    load();
  }, [token]);

  const label = (key) => taxonomy[key]?.label_kr || key;
  const color = (key) => HIGHER_ORDER_COLORS[taxonomy[key]?.higher_order] || FALLBACK_COLOR;

  if (isLoading) {
    return (
      <div className="network-loading">
        <Loader2 className="animate-spin" size={32} color="var(--accent-primary)" />
        <p>가치의 변화를 시간축으로 그려보는 중...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="network-empty-state">
        <div className="network-empty-icon">⚠️</div>
        <p>{error}</p>
      </div>
    );
  }

  const tvn = trends.then_vs_now || {};
  const topShift = tvn.top_shift;

  return (
    <div className="meaning-change" style={{ padding: '8px 4px', maxWidth: '880px', margin: '0 auto' }}>
      {/* 돌아볼 다짐 (pull 재질문) — 있을 때만 표시 */}
      <IntentionReview token={token} />

      {/* 정직한 요약 한 문장 */}
      <div
        className="glass-panel animate-fade-in"
        style={{
          display: 'flex', alignItems: 'flex-start', gap: '12px',
          padding: '18px 20px', borderRadius: '14px', marginBottom: '20px',
          background: 'rgba(99, 102, 241, 0.06)', border: '1px solid var(--border-glass)',
        }}
      >
        <Sparkles size={20} color="var(--accent-primary)" style={{ flexShrink: 0, marginTop: '2px' }} />
        <p style={{ margin: 0, lineHeight: 1.6, color: 'var(--text-main)', fontSize: '0.95rem' }}>
          {trends.summary}
        </p>
      </div>

      {/* 데이터 부족 상태 — 정직하게, engagement 압박 없이 */}
      {trends.insufficient ? (
        <InsufficientPanel trends={trends} />
      ) : (
        <>
          {/* 핵심 이동 콜아웃 */}
          {topShift && (
            <div
              className="animate-fade-in"
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '16px',
                padding: '20px', marginBottom: '20px', borderRadius: '14px',
                background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-glass)',
              }}
            >
              <ShiftChip text={topShift.from_label} c={color(topShift.from)} dir="down" />
              <ArrowRight size={24} color="var(--text-muted)" />
              <ShiftChip text={topShift.to_label} c={color(topShift.to)} dir="up" />
            </div>
          )}

          {/* 예전 vs 지금 */}
          <ThenVsNow tvn={tvn} label={label} color={color} />

          {/* 월별 구성 추이 */}
          {trends.timeline && trends.timeline.length > 0 && (
            <Timeline timeline={trends.timeline} label={label} color={color} />
          )}
        </>
      )}

      <Legend />
      {trends.unmapped_count > 0 && (
        <p style={{ marginTop: '12px', fontSize: '0.78rem', color: 'var(--text-muted)', textAlign: 'center' }}>
          <Info size={12} style={{ verticalAlign: 'middle', marginRight: '4px' }} />
          {trends.unmapped_count}개 카드는 표준 가치로 분류되지 않아(미분류) 추세 계산에서 제외했습니다.
        </p>
      )}
    </div>
  );
};

const ShiftChip = ({ text, c, dir }) => (
  <div style={{ textAlign: 'center' }}>
    <div style={{
      padding: '8px 18px', borderRadius: '999px', fontWeight: 700, fontSize: '1.05rem',
      color: '#fff', background: c, boxShadow: `0 4px 14px ${c}55`,
    }}>
      {text}
    </div>
    <div style={{ marginTop: '6px', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
      {dir === 'down' ? '예전엔 더 컸던' : '지금 더 커진'}
    </div>
  </div>
);

const InsufficientPanel = ({ trends }) => {
  const pct = Math.min(100, Math.round((trends.mapped_cards / trends.min_cards) * 100));
  return (
    <div
      className="glass-panel animate-fade-in"
      style={{ padding: '28px 24px', borderRadius: '14px', textAlign: 'center', border: '1px solid var(--border-glass)' }}
    >
      <div style={{ fontSize: '2rem', marginBottom: '10px' }}>🌱</div>
      <h3 style={{ margin: '0 0 8px', color: 'var(--text-main)' }}>변화는 시간이 쌓여야 보입니다</h3>
      <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', lineHeight: 1.6, margin: '0 auto 18px', maxWidth: '440px' }}>
        지금까지 분류된 가치 카드는 <strong>{trends.mapped_cards}개</strong>입니다.
        의미 있는 변화 추이를 정직하게 그리려면 최소 <strong>{trends.min_cards}개</strong>가
        여러 시기에 걸쳐 쌓여야 합니다. 서두를 필요는 없어요 — 성찰이 모일 때 다시 들러보세요.
      </p>
      <div style={{ height: '8px', borderRadius: '999px', background: 'rgba(255,255,255,0.08)', overflow: 'hidden', maxWidth: '320px', margin: '0 auto' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: 'var(--accent-gradient, #6366f1)', transition: 'width 0.4s' }} />
      </div>
      <div style={{ marginTop: '6px', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
        {trends.mapped_cards} / {trends.min_cards}
      </div>
    </div>
  );
};

const ThenVsNow = ({ tvn, label, color }) => {
  const then = tvn.then || { distribution: {}, count: 0 };
  const now = tvn.now || { distribution: {}, count: 0 };
  const keys = Array.from(new Set([...Object.keys(then.distribution), ...Object.keys(now.distribution)]))
    .sort((a, b) => (now.distribution[b] || 0) - (now.distribution[a] || 0));

  return (
    <div className="glass-panel" style={{ padding: '20px', borderRadius: '14px', marginBottom: '20px', border: '1px solid var(--border-glass)' }}>
      <h4 style={{ margin: '0 0 14px', color: 'var(--text-main)', fontSize: '0.95rem' }}>예전 → 지금, 가치 비중의 이동</h4>
      <div style={{ display: 'grid', gridTemplateColumns: '90px 1fr 1fr', gap: '6px 14px', alignItems: 'center' }}>
        <div />
        <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontWeight: 600 }}>예전 ({then.count})</div>
        <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontWeight: 600 }}>지금 ({now.count})</div>
        {keys.map((k) => (
          <Fragment key={k}>
            <div style={{ fontSize: '0.82rem', color: 'var(--text-main)', textAlign: 'right', fontWeight: 600 }}>{label(k)}</div>
            <Bar pct={(then.distribution[k] || 0) * 100} c={color(k)} />
            <Bar pct={(now.distribution[k] || 0) * 100} c={color(k)} />
          </Fragment>
        ))}
      </div>
    </div>
  );
};

const Bar = ({ pct, c }) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
    <div style={{ flex: 1, height: '14px', borderRadius: '4px', background: 'rgba(255,255,255,0.06)', overflow: 'hidden' }}>
      <div style={{ width: `${pct}%`, height: '100%', background: c, transition: 'width 0.4s' }} />
    </div>
    <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', width: '34px', textAlign: 'right' }}>{Math.round(pct)}%</span>
  </div>
);

const Timeline = ({ timeline, label, color }) => {
  const W = 760, H = 180, padL = 8, padB = 28, padT = 8;
  const colGap = 10;
  const n = timeline.length;
  const colW = Math.max(18, (W - padL * 2 - colGap * (n - 1)) / n);
  const chartH = H - padB - padT;

  return (
    <div className="glass-panel" style={{ padding: '20px', borderRadius: '14px', marginBottom: '20px', border: '1px solid var(--border-glass)' }}>
      <h4 style={{ margin: '0 0 14px', color: 'var(--text-main)', fontSize: '0.95rem' }}>월별 가치 구성 추이</h4>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 'auto' }}>
        {timeline.map((m, i) => {
          const x = padL + i * (colW + colGap);
          const total = m.total || 1;
          const entries = Object.entries(m.counts).sort((a, b) => b[1] - a[1]);
          let yCursor = padT;
          return (
            <g key={m.month}>
              {entries.map(([k, cnt]) => {
                const segH = (cnt / total) * chartH;
                const rect = (
                  <rect key={k} x={x} y={yCursor} width={colW} height={Math.max(0, segH - 1)}
                    rx={2} fill={color(k)} opacity={0.88}>
                    <title>{`${m.month} · ${label(k)}: ${cnt}`}</title>
                  </rect>
                );
                yCursor += segH;
                return rect;
              })}
              <text x={x + colW / 2} y={H - 10} textAnchor="middle"
                fontSize="10" fill="var(--text-muted)">
                {m.month.slice(2)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
};

const Legend = () => {
  const items = [
    ['변화 개방', HIGHER_ORDER_COLORS.openness_to_change],
    ['자기 고양', HIGHER_ORDER_COLORS.self_enhancement],
    ['보존', HIGHER_ORDER_COLORS.conservation],
    ['자기 초월', HIGHER_ORDER_COLORS.self_transcendence],
  ];
  return (
    <div style={{ display: 'flex', gap: '16px', justifyContent: 'center', flexWrap: 'wrap', marginTop: '6px' }}>
      {items.map(([name, c]) => (
        <div key={name} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.76rem', color: 'var(--text-muted)' }}>
          <span style={{ width: '10px', height: '10px', borderRadius: '3px', background: c, display: 'inline-block' }} />
          {name}
        </div>
      ))}
    </div>
  );
};

export default MeaningChange;
