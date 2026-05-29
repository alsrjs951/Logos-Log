import React from 'react';

const EMOTION_MAP = {
  happy: { emoji: '😊', label: '행복' },
  sad: { emoji: '😢', label: '슬픔' },
  stressed: { emoji: '🤯', label: '스트레스' },
  calm: { emoji: '🧘', label: '평온' },
  tired: { emoji: '😴', label: '피로' }
};

const JournalList = ({ journals, onSelectJournal, activeJournalId }) => {
  const formatDate = (dateString) => {
    try {
      const date = new Date(dateString);
      return `${date.getMonth() + 1}월 ${date.getDate()}일`;
    } catch (e) {
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
          <button
            key={journal.id}
            className={`journal-item ${activeJournalId === journal.id ? 'active' : ''}`}
            onClick={() => onSelectJournal(journal)}
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
        );
      })}
    </div>
  );
};

export default JournalList;
