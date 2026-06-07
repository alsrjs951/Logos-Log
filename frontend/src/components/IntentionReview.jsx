import React, { useState, useEffect } from 'react';
import { Check, X } from 'lucide-react';

/**
 * 돌아볼 다짐 — insight→행동→결과 루프의 닫는 고리.
 * 며칠 지난 '열린 다짐'을 사용자가 변화뷰에 들렀을 때만 보여준다(pull, not push).
 * "그 선택, 해보니 어땠나요?"의 결과와 도움정도를 기록하거나, 부담 없이 접어둘 수 있다.
 * 돌아볼 다짐이 없으면 아무것도 렌더링하지 않는다.
 */
const IntentionReview = ({ token, onChange }) => {
  const [due, setDue] = useState([]);
  const [drafts, setDrafts] = useState({}); // id -> { outcome, helpfulness }
  const [busyId, setBusyId] = useState(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch('http://localhost:8000/api/intentions/due', {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) setDue(await res.json());
      } catch (err) {
        console.error('Error loading due intentions:', err);
      } finally {
        setLoaded(true);
      }
    };
    load();
  }, [token]);

  const setDraft = (id, patch) =>
    setDrafts((d) => ({ ...d, [id]: { outcome: '', helpfulness: null, ...d[id], ...patch } }));

  const remove = (id) => setDue((list) => list.filter((it) => it.id !== id));

  const reflect = async (id) => {
    const draft = drafts[id] || {};
    if (!draft.outcome || !draft.outcome.trim()) return;
    setBusyId(id);
    try {
      const res = await fetch(`http://localhost:8000/api/intentions/${id}/reflect`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ outcome: draft.outcome.trim(), helpfulness: draft.helpfulness }),
      });
      if (!res.ok) throw new Error('결과 기록 실패');
      remove(id);
      onChange && onChange();
    } catch (err) {
      console.error('Error reflecting intention:', err);
      alert('결과 기록 중 오류가 발생했습니다.');
    } finally {
      setBusyId(null);
    }
  };

  const dismiss = async (id) => {
    setBusyId(id);
    try {
      const res = await fetch(`http://localhost:8000/api/intentions/${id}/dismiss`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error('접어두기 실패');
      remove(id);
      onChange && onChange();
    } catch (err) {
      console.error('Error dismissing intention:', err);
    } finally {
      setBusyId(null);
    }
  };

  if (!loaded || due.length === 0) return null;

  return (
    <div className="glass-panel animate-fade-in" style={{ padding: '20px', borderRadius: '14px', marginBottom: '20px', border: '1px solid rgba(16,185,129,0.25)', background: 'rgba(16,185,129,0.05)' }}>
      <h4 style={{ margin: '0 0 4px', color: 'var(--text-main)', fontSize: '0.98rem' }}>🌱 돌아볼 다짐</h4>
      <p style={{ margin: '0 0 16px', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
        지난 성찰에서 세운 다짐이에요. 그 선택, 실제로 해보니 어땠나요? (지금 아니어도 괜찮아요.)
      </p>

      {due.map((it) => {
        const draft = drafts[it.id] || { outcome: '', helpfulness: null };
        const busy = busyId === it.id;
        return (
          <div key={it.id} style={{ padding: '14px', borderRadius: '10px', background: 'rgba(0,0,0,0.18)', border: '1px solid var(--border-glass)', marginBottom: '12px' }}>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
              {it.card_keyword ? `‘${it.card_keyword}’에서 세운 다짐` : '지난 다짐'}
            </div>
            <p style={{ margin: '0 0 12px', color: 'var(--text-main)', fontSize: '0.92rem', lineHeight: 1.5 }}>
              "{it.intention}"
            </p>

            <textarea
              value={draft.outcome}
              onChange={(e) => setDraft(it.id, { outcome: e.target.value })}
              disabled={busy}
              placeholder="해보니 어땠는지 적어보세요…"
              rows={2}
              style={{ width: '100%', boxSizing: 'border-box', resize: 'vertical', padding: '8px 10px', borderRadius: '8px', background: 'rgba(0,0,0,0.25)', border: '1px solid var(--border-glass)', color: 'var(--text-main)', fontFamily: 'inherit', fontSize: '0.86rem' }}
            />

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', margin: '10px 0' }}>
              <span style={{ fontSize: '0.76rem', color: 'var(--text-muted)' }}>그 선택, 도움이 됐나요?</span>
              {[1, 2, 3, 4, 5].map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setDraft(it.id, { helpfulness: n })}
                  disabled={busy}
                  style={{
                    width: '26px', height: '26px', borderRadius: '50%', cursor: 'pointer',
                    fontSize: '0.78rem', fontFamily: 'inherit', fontWeight: 600,
                    border: '1px solid var(--border-glass)',
                    background: draft.helpfulness === n ? '#10b981' : 'transparent',
                    color: draft.helpfulness === n ? '#fff' : 'var(--text-muted)',
                  }}
                >
                  {n}
                </button>
              ))}
            </div>

            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
              <button
                type="button"
                onClick={() => dismiss(it.id)}
                disabled={busy}
                style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '7px 12px', borderRadius: '8px', border: '1px solid var(--border-glass)', background: 'transparent', color: 'var(--text-muted)', fontSize: '0.8rem', fontFamily: 'inherit', cursor: 'pointer' }}
              >
                <X size={14} /> 접어두기
              </button>
              <button
                type="button"
                onClick={() => reflect(it.id)}
                disabled={busy || !draft.outcome.trim()}
                style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '7px 14px', borderRadius: '8px', border: 'none', background: '#10b981', color: '#fff', fontSize: '0.8rem', fontWeight: 600, fontFamily: 'inherit', cursor: draft.outcome.trim() ? 'pointer' : 'not-allowed', opacity: draft.outcome.trim() ? 1 : 0.5 }}
              >
                <Check size={14} /> {busy ? '기록 중…' : '기록하기'}
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default IntentionReview;
