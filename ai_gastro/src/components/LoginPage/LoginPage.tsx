import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import './LoginPage.css';

type AuthMode = 'login' | 'register';

export default function LoginPage() {
    const navigate = useNavigate();
    const { login, register } = useAuth();
    const [mode, setMode] = useState<AuthMode>('login');
    const [username, setUsername] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);

    const isRegisterMode = mode === 'register';

    const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        setError(null);

        if (isRegisterMode && password !== confirmPassword) {
            setError('Пароли не совпадают');
            return;
        }

        setIsSubmitting(true);
        try {
            if (isRegisterMode) {
                await register(username, email, password);
            } else {
                await login(email, password);
            }
            navigate('/', { replace: true });
        } catch (err: any) {
            setError(err?.response?.data?.detail || 'Не удалось выполнить авторизацию');
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="login-page">
            <div className="login-card">
                <div className="login-badge">Gastro AI</div>
                <h1 className="login-title">Безопасный вход</h1>
                <p className="login-subtitle">
                    Регистрируйся по email, входи в систему и продолжай работать с дневником,
                    чат-ассистентом и планировщиком питания без внешнего OAuth.
                </p>

                <div className="login-switcher" role="tablist" aria-label="Режим авторизации">
                    <button
                        type="button"
                        className={`login-switcher-btn ${mode === 'login' ? 'active' : ''}`}
                        onClick={() => setMode('login')}
                    >
                        Вход
                    </button>
                    <button
                        type="button"
                        className={`login-switcher-btn ${mode === 'register' ? 'active' : ''}`}
                        onClick={() => setMode('register')}
                    >
                        Регистрация
                    </button>
                </div>

                <form className="login-form" onSubmit={handleSubmit}>
                    {isRegisterMode && (
                        <label className="login-field">
                            <span>Имя</span>
                            <input
                                value={username}
                                onChange={(event) => setUsername(event.target.value)}
                                type="text"
                                autoComplete="name"
                                placeholder="Как к тебе обращаться"
                                minLength={2}
                                maxLength={50}
                                required
                            />
                        </label>
                    )}

                    <label className="login-field">
                        <span>Email</span>
                        <input
                            value={email}
                            onChange={(event) => setEmail(event.target.value)}
                            type="email"
                            autoComplete="email"
                            placeholder="you@example.com"
                            required
                        />
                    </label>

                    <label className="login-field">
                        <span>Пароль</span>
                        <input
                            value={password}
                            onChange={(event) => setPassword(event.target.value)}
                            type="password"
                            autoComplete={isRegisterMode ? 'new-password' : 'current-password'}
                            placeholder="Минимум 8 символов"
                            minLength={8}
                            required
                        />
                    </label>

                    {isRegisterMode && (
                        <label className="login-field">
                            <span>Повтори пароль</span>
                            <input
                                value={confirmPassword}
                                onChange={(event) => setConfirmPassword(event.target.value)}
                                type="password"
                                autoComplete="new-password"
                                placeholder="Повтори пароль"
                                minLength={8}
                                required
                            />
                        </label>
                    )}

                    <button className="login-submit-btn" type="submit" disabled={isSubmitting}>
                        {isSubmitting ? 'Подожди...' : isRegisterMode ? 'Создать аккаунт' : 'Войти'}
                    </button>
                </form>

                {error && <div className="login-error">{error}</div>}

                <div className="login-hint">
                    Пароль должен содержать заглавную и строчную букву, а также хотя бы одну цифру.
                </div>

                <div className="login-features">
                    <div className="login-feature">
                        <span className="login-feature-icon">AI</span>
                        <span>Персональный гастро-ассистент и история диалогов</span>
                    </div>
                    <div className="login-feature">
                        <span className="login-feature-icon">K</span>
                        <span>Дневник калорий и автоматический расчёт КБЖУ</span>
                    </div>
                    <div className="login-feature">
                        <span className="login-feature-icon">P</span>
                        <span>План питания и сохранённые рецепты под аккаунтом</span>
                    </div>
                </div>
            </div>
        </div>
    );
}
