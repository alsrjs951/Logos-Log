import React from 'react';

const SourceCards = ({ sources }) => {
  if (!sources || sources.length === 0) return null;

  return (
    <div className="sources-container">
      {sources.map((src, index) => (
        <div key={index} className="source-card">
          <h4>논문 출처 {index + 1}</h4>
          <p style={{ fontSize: '0.75rem', marginBottom: '4px', color: 'var(--text-main)' }}>
            <strong>{src.author}</strong> ({src.year}) - {src.category}
          </p>
          <p>{src.content}</p>
          <p style={{ fontSize: '0.7rem', marginTop: '6px', textAlign: 'right' }}>
            유사도: {(src.similarity * 100).toFixed(1)}%
          </p>
        </div>
      ))}
    </div>
  );
};

export default SourceCards;
