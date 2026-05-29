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
            <div className="journal-item-title">{journal.title}</div>
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
