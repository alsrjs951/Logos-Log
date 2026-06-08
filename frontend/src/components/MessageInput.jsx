import { useState } from 'react';
import { Send } from 'lucide-react';

const MessageInput = ({ onSendMessage, isLoading }) => {
  const [text, setText] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (text.trim() && !isLoading) {
      onSendMessage(text.trim());
      setText('');
    }
  };

  return (
    <div className="input-area">
      <form className="input-wrapper" onSubmit={handleSubmit}>
        <input
          type="text"
          placeholder="논문과 관련된 질문을 입력해보세요..."
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={isLoading}
        />
        <button type="submit" className="send-btn" disabled={!text.trim() || isLoading}>
          <Send size={18} />
        </button>
      </form>
    </div>
  );
};

export default MessageInput;
