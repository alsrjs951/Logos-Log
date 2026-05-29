import React, { useState } from 'react';
import { Sparkles } from 'lucide-react';

const EMOTIONS = [
  { key: 'happy', label: '행복', emoji: '😊' },
  { key: 'sad', label: '슬픔', emoji: '😢' },
  { key: 'stressed', label: '스트레스', emoji: '🤯' },
  { key: 'calm', label: '평온', emoji: '🧘' },
  { key: 'tired', label: '피로', emoji: '😴' }
];

const JournalEditor = ({ onStartAnalysis }) => {
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [selectedEmotion, setSelectedEmotion] = useState('calm');
  const [isSaving, setIsSaving] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!title.trim() || !content.trim()) return;

    setIsSaving(true);
    try {
      // 1. 일기를 Supabase 백엔드에 저장
      const response = await fetch('http://localhost:8000/api/journals', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          title: title.trim(),
          content: content.trim(),
          emotion: selectedEmotion
        })
      });

      if (!response.ok) {
        throw new Error('일기 저장 실패');
      }

      const savedJournal = await response.json();
      
      // 2. 부모 컴포넌트에 분석 시작을 알림 (저장된 일기 객체 전달)
      onStartAnalysis(savedJournal);
      
      // 에디터 초기화
      setTitle('');
      setContent('');
      setSelectedEmotion('calm');
    } catch (error) {
      console.error('Error saving journal:', error);
      alert('일기를 저장하는 도중 오류가 발생했습니다. 백엔드가 켜져 있는지 확인하세요.');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <form className="editor-container" onSubmit={handleSubmit}>
      <input
        type="text"
        className="editor-title-input"
        placeholder="오늘 하루의 제목을 붙여보세요..."
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        disabled={isSaving}
        required
      />

      <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
        <span className="emotion-selector-label">오늘의 핵심 감정</span>
        <div className="emotion-buttons">
          {EMOTIONS.map((emo) => (
            <button
              key={emo.key}
              type="button"
              className={`emotion-btn ${selectedEmotion === emo.key ? 'active' : ''}`}
              onClick={() => setSelectedEmotion(emo.key)}
              disabled={isSaving}
            >
              <span>{emo.emoji}</span>
              <span>{emo.label}</span>
            </button>
          ))}
        </div>
      </div>

      <textarea
        className="editor-content-textarea"
        placeholder="오늘 있었던 일이나 떠오르는 생각, 느꼈던 감정을 편안하게 적어보세요. 마침표를 누른 후 '분석 시작'을 누르면 성찰을 위한 대화가 시작됩니다..."
        value={content}
        onChange={(e) => setContent(e.target.value)}
        disabled={isSaving}
        required
      />

      <button
        type="submit"
        className="editor-submit-btn"
        disabled={isSaving || !title.trim() || !content.trim()}
      >
        <Sparkles size={18} />
        {isSaving ? '일기 저장 및 분석 중...' : '일기 분석 및 대화 시작하기'}
      </button>
    </form>
  );
};

export default JournalEditor;
