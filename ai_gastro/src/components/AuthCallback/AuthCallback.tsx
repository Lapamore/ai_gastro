import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import './AuthCallback.css';

export default function AuthCallback() {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const { login } = useAuth();
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const code = searchParams.get('code');

        if (!code) {
            setError('Не получен код авторизации от Яндекса');
            return;
        }

        login(code)
            .then(() => {
                navigate('/', { replace: true });
            })
            .catch((err) => {
                console.error('OAuth callback error:', err);
                setError('Ошибка авторизации. Попробуйте ещё раз.');
            });
    }, [searchParams, login, navigate]);

    if (error) {
        return (
            <div className="auth-callback">
                <div className="auth-callback-card">
                    <div className="auth-callback-icon">❌</div>
                    <h2>Ошибка авторизации</h2>
                    <p>{error}</p>
                    <button onClick={() => navigate('/login', { replace: true })} className="auth-callback-btn">
                        Попробовать ещё раз
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="auth-callback">
            <div className="auth-callback-card">
                <div className="auth-callback-spinner" />
                <h2>Авторизация...</h2>
                <p>Подождите, входим в систему</p>
            </div>
        </div>
    );
}
