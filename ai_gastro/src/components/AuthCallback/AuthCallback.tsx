import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './AuthCallback.css';

export default function AuthCallback() {
    const navigate = useNavigate();

    useEffect(() => {
        const timer = window.setTimeout(() => {
            navigate('/login', { replace: true });
        }, 1800);

        return () => window.clearTimeout(timer);
    }, [navigate]);

    return (
        <div className="auth-callback">
            <div className="auth-callback-card">
                <div className="auth-callback-icon">!</div>
                <h2>Яндекс-вход отключён</h2>
                <p>Сейчас приложение использует локальную регистрацию и авторизацию по email.</p>
                <button onClick={() => navigate('/login', { replace: true })} className="auth-callback-btn">
                    Перейти ко входу
                </button>
            </div>
        </div>
    );
}
