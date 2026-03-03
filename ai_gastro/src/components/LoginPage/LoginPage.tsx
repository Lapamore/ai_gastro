import './LoginPage.css';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

export default function LoginPage() {
    const handleYandexLogin = () => {
        // Перенаправляем на бэкенд, который сделает redirect на Яндекс
        window.location.href = `${API_BASE_URL}/auth/yandex`;
    };

    return (
        <div className="login-page">
            <div className="login-card">
                <div className="login-logo">🍽️</div>
                <h1 className="login-title">Гастро-Помощник</h1>
                <p className="login-subtitle">
                    Умный AI-ассистент для подбора рецептов,<br />
                    планирования питания и подсчёта калорий
                </p>

                <button className="yandex-login-btn" onClick={handleYandexLogin}>
                    <svg viewBox="0 0 24 24" fill="currentColor">
                        <path d="M13.32 7.666h-.924c-1.694 0-2.585.858-2.585 2.123 0 1.43.616 2.1 1.881 2.959l1.045.704-3.003 4.487H7.49l2.695-4.014c-1.55-1.111-2.42-2.19-2.42-4.015 0-2.288 1.595-3.85 4.62-3.85h3.003v11.868H13.32V7.666z" />
                    </svg>
                    Войти через Яндекс ID
                </button>

                <div className="login-features">
                    <div className="login-feature">
                        <span className="login-feature-icon">🤖</span>
                        <span>AI-помощник для подбора рецептов</span>
                    </div>
                    <div className="login-feature">
                        <span className="login-feature-icon">📔</span>
                        <span>Дневник калорий с автоподсчётом КБЖУ</span>
                    </div>
                    <div className="login-feature">
                        <span className="login-feature-icon">🎯</span>
                        <span>Персональные рекомендации</span>
                    </div>
                    <div className="login-feature">
                        <span className="login-feature-icon">📺</span>
                        <span>Видео-рецепты с YouTube</span>
                    </div>
                </div>
            </div>
        </div>
    );
}
