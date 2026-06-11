import { Trash2 } from 'lucide-react';

const EMOTION_MAP = {
  happy: { emoji: '😊', label: '행복' },
  sad: { emoji: '😢', label: '슬픔' },
  stressed: { emoji: '🤯', label: '스트레스' },
  calm: { emoji: '🧘', label: '평온' },
  tired: { emoji: '😴', label: '피로' }
};

const JournalList = ({ journals, onSelectJournal, onDeleteJournal, activeJournalId }) => {
  const formatDate = (dateString) => {
    try {
      const date = new Date(dateString);
      return `${date.getMonth() + 1}월 ${date.getDate()}일`;
    } catch {
      return dateString;
    }
  };

  if (!journals || journals.length === 0) {
    return (
      <div className="no-journals-placeholder">
        작성된 일기가 없습니다.<br />첫 일기를 작성해 보세요!
      </div>
    );
  }

  return (
    <div className="journal-list">
      {journals.map((journal) => {
        const emotionInfo = EMOTION_MAP[journal.emotion] || { emoji: '📝', label: '일반' };
        
        return (
          <div
            key={journal.id}
            className="journal-item-wrapper"
            style={{ display: 'flex', width: '100%', position: 'relative' }}
          >
            <button
              className={`journal-item ${activeJournalId === journal.id ? 'active' : ''}`}
              onClick={() => onSelectJournal(journal)}
              style={{ flex: 1, textAlign: 'left', paddingRight: '42px' }}
            >
              <div className="journal-item-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px' }}>
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{journal.title}</span>
                {journal.is_analyzed && (
                  <span className="analyzed-badge animate-fade-in" style={{ fontSize: '0.62rem', background: 'rgba(16, 185, 129, 0.12)', color: '#10b981', border: '1px solid rgba(16, 185, 129, 0.25)', padding: '1px 5px', borderRadius: '10px', fontWeight: '700', flexShrink: 0, letterSpacing: '0.2px' }}>
                    ✨ 성찰됨
                  </span>
                )}
              </div>
              <div className="journal-item-meta">
                <span>{formatDate(journal.created_at)}</span>
                <span className="journal-item-emotion">
                  {emotionInfo.emoji} {emotionInfo.label}
                </span>
              </div>
            </button>
            <button
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onDeleteJournal(journal.id);
              }}
              style={{
                position: 'absolute',
                right: '12px',
                top: '50%',
                transform: 'translateY(-50%)',
                background: 'none',
                border: 'none',
                color: 'rgba(239, 68, 68, 0.4)',
                cursor: 'pointer',
                padding: '6px',
                borderRadius: '6px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transition: 'all 0.2s',
                zIndex: 10,
              }}
              onMouseEnter={e => {
                e.currentTarget.style.color = '#ef4444';
                e.currentTarget.style.background = 'rgba(239, 68, 68, 0.12)';
              }}
              onMouseLeave={e => {
                e.currentTarget.style.color = 'rgba(239, 68, 68, 0.4)';
                e.currentTarget.style.background = 'none';
              }}
              title="이 일기 성찰 기록 삭제"
            >
              <Trash2 size={13} />
            </button>
          </div>
        );
      })}
    </div>
  );
};

export default JournalList;
