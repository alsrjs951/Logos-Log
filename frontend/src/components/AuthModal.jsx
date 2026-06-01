import React, { useState } from 'react';
import { Mail, Lock, Loader2, ArrowRight } from 'lucide-react';

const AuthModal = ({ onLoginSuccess }) => {
  const [isLoginMode, setIsLoginMode] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setMessage('');
    setIsLoading(true);

    const endpoint = isLoginMode ? 'login' : 'signup';

    try {
      const response = await fetch(`http://localhost:8000/api/auth/${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || '인증 요청에 실패했습니다.');
      }

      if (isLoginMode) {
        // 로그인 성공 시 세션 저장 및 상위 앱에 알림
        localStorage.setItem('access_token', data.access_token);
        localStorage.setItem('user_email', data.user.email);
        onLoginSuccess(data.access_token, data.user.email);
      } else {
        // 회원가입 성공 시
        setMessage('회원가입이 완료되었습니다! 로그인해 주세요.');
        setIsLoginMode(true);
        setPassword('');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="auth-overlay" style={{ position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', background: 'rgba(5, 5, 15, 0.85)', backdropFilter: 'blur(8px)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className="auth-card glass-panel" style={{ width: '400px', padding: '35px 30px', borderRadius: '16px', border: '1px solid rgba(255, 255, 255, 0.08)', background: 'rgba(10, 11, 26, 0.75)', boxShadow: '0 15px 35px rgba(0, 0, 0, 0.6)', display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <div style={{ textAlign: 'center' }}>
          <h2 style={{ fontSize: '1.75rem', fontWeight: '800', background: 'var(--accent-gradient)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', margin: '0 0 8px 0' }}>Logos-Log</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.88rem', margin: 0 }}>심리학 RAG 기반의 자아 성찰 은하수 다이어리</p>
        </div>

        <div style={{ display: 'flex', borderBottom: '1px solid rgba(255, 255, 255, 0.08)' }}>
          <button 
            onClick={() => { setIsLoginMode(true); setError(''); setMessage(''); }}
            style={{ flex: 1, padding: '12px 0', border: 'none', background: 'none', color: isLoginMode ? 'var(--accent-secondary)' : 'var(--text-muted)', fontWeight: '700', fontSize: '0.95rem', cursor: 'pointer', borderBottom: isLoginMode ? '2px solid var(--accent-secondary)' : 'none', transition: 'all 0.2s', fontFamily: 'inherit' }}
          >
            로그인
          </button>
          <button 
            onClick={() => { setIsLoginMode(false); setError(''); setMessage(''); }}
            style={{ flex: 1, padding: '12px 0', border: 'none', background: 'none', color: !isLoginMode ? 'var(--accent-secondary)' : 'var(--text-muted)', fontWeight: '700', fontSize: '0.95rem', cursor: 'pointer', borderBottom: !isLoginMode ? '2px solid var(--accent-secondary)' : 'none', transition: 'all 0.2s', fontFamily: 'inherit' }}
          >
            회원가입
          </button>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
          {error && (
            <div style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', padding: '10px 14px', borderRadius: '8px', color: '#ef4444', fontSize: '0.82rem', display: 'flex', gap: '6px' }}>
              <span>⚠️</span>
              <span>{error}</span>
            </div>
          )}
          {message && (
            <div style={{ background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.3)', padding: '10px 14px', borderRadius: '8px', color: '#10b981', fontSize: '0.82rem', display: 'flex', gap: '6px' }}>
              <span>✨</span>
              <span>{message}</span>
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '0.82rem', color: 'var(--text-muted)', fontWeight: '600' }}>이메일 주소</label>
            <div style={{ position: 'relative' }}>
              <Mail size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input 
                type="email" 
                placeholder="example@email.com" 
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                disabled={isLoading}
                style={{ width: '100%', padding: '12px 12px 12px 38px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.03)', color: 'var(--text-main)', fontSize: '0.9rem', outline: 'none', transition: 'all 0.25s', boxSizing: 'border-box' }}
                onFocus={(e) => e.target.style.borderColor = 'var(--accent-secondary)'}
                onBlur={(e) => e.target.style.borderColor = 'rgba(255,255,255,0.08)'}
              />
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '0.82rem', color: 'var(--text-muted)', fontWeight: '600' }}>비밀번호</label>
            <div style={{ position: 'relative' }}>
              <Lock size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input 
                type="password" 
                placeholder="••••••••" 
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                disabled={isLoading}
                minLength={6}
                style={{ width: '100%', padding: '12px 12px 12px 38px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.03)', color: 'var(--text-main)', fontSize: '0.9rem', outline: 'none', transition: 'all 0.25s', boxSizing: 'border-box' }}
                onFocus={(e) => e.target.style.borderColor = 'var(--accent-secondary)'}
                onBlur={(e) => e.target.style.borderColor = 'rgba(255,255,255,0.08)'}
              />
            </div>
            {!isLoginMode && <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '2px' }}>최소 6자 이상이어야 합니다.</span>}
          </div>

          <button 
            type="submit" 
            disabled={isLoading}
            style={{ width: '100%', padding: '14px', borderRadius: '8px', border: 'none', background: 'var(--accent-gradient)', color: '#ffffff', fontWeight: '700', fontSize: '0.95rem', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', marginTop: '10px', boxShadow: '0 4px 15px rgba(99, 102, 241, 0.2)', transition: 'all 0.25s', fontFamily: 'inherit' }}
            onMouseEnter={(e) => e.currentTarget.style.opacity = '0.9'}
            onMouseLeave={(e) => e.currentTarget.style.opacity = '1'}
          >
            {isLoading ? (
              <Loader2 className="animate-spin" size={18} />
            ) : (
              <>
                <span>{isLoginMode ? '로그인 하기' : '가입 완료하기'}</span>
                <ArrowRight size={16} />
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
};

export default AuthModal;
