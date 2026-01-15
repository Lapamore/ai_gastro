import { useState, useEffect } from 'react';
import type { AxiosInstance } from 'axios';
import type { DiaryEntry, DiaryEntryInput, DailyProgress, UserPreferences } from '../../types';
import './DiaryModal.css';

interface DiaryModalProps {
    isOpen: boolean;
    onClose: () => void;
    dailyProgress: DailyProgress;
    onProgressUpdate: (progress: DailyProgress) => void;
    api: AxiosInstance;
    preferences: UserPreferences;
    onPreferencesChange: (prefs: UserPreferences) => void;
}

const mealTypeLabels: Record<string, string> = {
    breakfast: '🌅 Завтрак',
    lunch: '☀️ Обед',
    dinner: '🌙 Ужин',
    snack: '🍿 Перекус'
};

const activityLabels: Record<string, string> = {
    sedentary: 'Сидячий образ жизни',
    light: 'Лёгкая активность (1-3 раза/нед)',
    moderate: 'Умеренная (3-5 раз/нед)',
    active: 'Высокая (6-7 раз/нед)',
    very_active: 'Очень высокая (спортсмены)'
};

const goalLabels: Record<string, string> = {
    lose: '📉 Похудеть',
    maintain: '⚖️ Поддерживать вес',
    gain: '📈 Набрать массу'
};

function DiaryModal({ isOpen, onClose, dailyProgress, onProgressUpdate, api, preferences, onPreferencesChange }: DiaryModalProps) {
    const [entries, setEntries] = useState<DiaryEntry[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [showAddForm, setShowAddForm] = useState(false);
    const [activeTab, setActiveTab] = useState<'diary' | 'profile'>('diary');
    const [isSaving, setIsSaving] = useState(false);
    
    // Локальное состояние профиля
    const [bodyParams, setBodyParams] = useState({
        weight: preferences.weight || '',
        height: preferences.height || '',
        age: preferences.age || '',
        gender: preferences.gender || '',
        activityLevel: preferences.activityLevel || '',
        goal: preferences.goal || ''
    });
    
    // Форма добавления еды
    const [newEntry, setNewEntry] = useState<DiaryEntryInput>({
        name: '',
        calories: 0,
        protein: 0,
        fat: 0,
        carbs: 0,
        mealType: 'snack'
    });

    // Обновляем локальные данные при изменении preferences
    useEffect(() => {
        setBodyParams({
            weight: preferences.weight || '',
            height: preferences.height || '',
            age: preferences.age || '',
            gender: preferences.gender || '',
            activityLevel: preferences.activityLevel || '',
            goal: preferences.goal || ''
        });
    }, [preferences]);

    const fetchEntries = async () => {
        setIsLoading(true);
        try {
            const res = await api.get('/diary/entries');
            setEntries(res.data.map((e: any) => ({
                ...e,
                timestamp: new Date(e.timestamp)
            })));
        } catch (error) {
            console.error('Ошибка загрузки записей дневника:', error);
        } finally {
            setIsLoading(false);
        }
    };

    const fetchProgress = async () => {
        try {
            const res = await api.get('/diary/daily-summary');
            onProgressUpdate({
                ...res.data,
                targetCalories: dailyProgress.targetCalories,
                targetProtein: dailyProgress.targetProtein,
                targetFat: dailyProgress.targetFat,
                targetCarbs: dailyProgress.targetCarbs
            });
        } catch (error) {
            console.error('Ошибка обновления прогресса:', error);
        }
    };

    useEffect(() => {
        if (isOpen) {
            fetchEntries();
        }
    }, [isOpen]);

    const handleAddEntry = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!newEntry.name.trim()) return;

        try {
            await api.post('/diary/add', newEntry);
            await fetchEntries();
            await fetchProgress();
            setNewEntry({
                name: '',
                calories: 0,
                protein: 0,
                fat: 0,
                carbs: 0,
                mealType: 'snack'
            });
            setShowAddForm(false);
        } catch (error) {
            console.error('Ошибка добавления записи:', error);
        }
    };

    const handleDeleteEntry = async (name: string) => {
        if (!window.confirm(`Удалить "${name}" из дневника?`)) return;
        
        try {
            await api.delete(`/diary/delete/${encodeURIComponent(name)}`);
            await fetchEntries();
            await fetchProgress();
        } catch (error) {
            console.error('Ошибка удаления записи:', error);
        }
    };

    const handleSaveProfile = async () => {
        setIsSaving(true);
        try {
            const updatedPrefs: UserPreferences = {
                ...preferences,
                weight: bodyParams.weight ? Number(bodyParams.weight) : undefined,
                height: bodyParams.height ? Number(bodyParams.height) : undefined,
                age: bodyParams.age ? Number(bodyParams.age) : undefined,
                gender: bodyParams.gender as 'male' | 'female' | undefined,
                activityLevel: bodyParams.activityLevel as UserPreferences['activityLevel'],
                goal: bodyParams.goal as 'lose' | 'maintain' | 'gain' | undefined
            };
            
            const res = await api.post('/user/preferences', updatedPrefs);
            
            // Обновляем preferences с рассчитанными значениями от бэкенда
            onPreferencesChange({
                ...updatedPrefs,
                targetCalories: res.data.targetCalories,
                targetProtein: res.data.targetProtein,
                targetFat: res.data.targetFat,
                targetCarbs: res.data.targetCarbs
            });
            
            // Обновляем dailyProgress с новыми целями
            onProgressUpdate({
                ...dailyProgress,
                targetCalories: res.data.targetCalories,
                targetProtein: res.data.targetProtein,
                targetFat: res.data.targetFat,
                targetCarbs: res.data.targetCarbs
            });
            
            alert('✅ Профиль сохранён! Норма калорий рассчитана.');
        } catch (error) {
            console.error('Ошибка сохранения профиля:', error);
            alert('Ошибка сохранения профиля');
        } finally {
            setIsSaving(false);
        }
    };

    if (!isOpen) return null;

    const progressPercent = Math.min((dailyProgress.totalCalories / dailyProgress.targetCalories) * 100, 100);
    const hasBodyData = preferences.weight && preferences.height && preferences.age && preferences.gender;

    return (
        <div className="diary-modal-overlay" onClick={onClose}>
            <div className="diary-modal-content diary-modal-wide" onClick={e => e.stopPropagation()}>
                <div className="diary-modal-header">
                    <h2>📔 Дневник питания</h2>
                    <button className="diary-modal-close" onClick={onClose}>×</button>
                </div>

                {/* Вкладки */}
                <div className="diary-tabs">
                    <button 
                        className={`diary-tab ${activeTab === 'diary' ? 'active' : ''}`}
                        onClick={() => setActiveTab('diary')}
                    >
                        🍽️ Дневник
                    </button>
                    <button 
                        className={`diary-tab ${activeTab === 'profile' ? 'active' : ''}`}
                        onClick={() => setActiveTab('profile')}
                    >
                        👤 Мой профиль
                    </button>
                </div>

                {activeTab === 'diary' ? (
                    <>
                        {/* Прогресс-бар */}
                        <div className="diary-progress-section">
                            <div className="diary-progress-header">
                                <span>Калории за сегодня</span>
                                <span className="diary-progress-numbers">
                                    {dailyProgress.totalCalories} / {dailyProgress.targetCalories} ккал
                                </span>
                            </div>
                            <div className="diary-progress-bar">
                                <div 
                                    className="diary-progress-fill" 
                                    style={{ width: `${progressPercent}%` }}
                                />
                            </div>
                            <div className="diary-macros">
                                <div className="diary-macro">
                                    <span className="macro-label">Белки</span>
                                    <span className="macro-value protein">
                                        {dailyProgress.protein}г
                                        {dailyProgress.targetProtein && <span className="macro-target"> / {dailyProgress.targetProtein}г</span>}
                                    </span>
                                </div>
                                <div className="diary-macro">
                                    <span className="macro-label">Жиры</span>
                                    <span className="macro-value fat">
                                        {dailyProgress.fat}г
                                        {dailyProgress.targetFat && <span className="macro-target"> / {dailyProgress.targetFat}г</span>}
                                    </span>
                                </div>
                                <div className="diary-macro">
                                    <span className="macro-label">Углеводы</span>
                                    <span className="macro-value carbs">
                                        {dailyProgress.carbs}г
                                        {dailyProgress.targetCarbs && <span className="macro-target"> / {dailyProgress.targetCarbs}г</span>}
                                    </span>
                                </div>
                            </div>
                            {!hasBodyData && (
                                <div className="diary-profile-hint">
                                    💡 Заполните профиль во вкладке "Мой профиль" для точного расчёта нормы калорий!
                                </div>
                            )}
                        </div>

                        {/* Список записей */}
                        <div className="diary-entries-section">
                            <div className="diary-entries-header">
                                <h3>Записи за сегодня</h3>
                                <button 
                                    className="diary-add-button"
                                    onClick={() => setShowAddForm(!showAddForm)}
                                >
                                    {showAddForm ? '✕ Отмена' : '+ Добавить'}
                                </button>
                            </div>

                            {/* Форма добавления */}
                            {showAddForm && (
                                <form className="diary-add-form" onSubmit={handleAddEntry}>
                                    <input
                                        type="text"
                                        placeholder="Название блюда"
                                        value={newEntry.name}
                                        onChange={e => setNewEntry({...newEntry, name: e.target.value})}
                                        required
                                    />
                                    <div className="diary-form-row">
                                        <div className="diary-form-field">
                                            <label>Калории</label>
                                            <input
                                                type="number"
                                                min="0"
                                                value={newEntry.calories}
                                                onChange={e => setNewEntry({...newEntry, calories: +e.target.value})}
                                            />
                                        </div>
                                        <div className="diary-form-field">
                                            <label>Белки (г)</label>
                                            <input
                                                type="number"
                                                min="0"
                                                step="0.1"
                                                value={newEntry.protein}
                                                onChange={e => setNewEntry({...newEntry, protein: +e.target.value})}
                                            />
                                        </div>
                                        <div className="diary-form-field">
                                            <label>Жиры (г)</label>
                                            <input
                                                type="number"
                                                min="0"
                                                step="0.1"
                                                value={newEntry.fat}
                                                onChange={e => setNewEntry({...newEntry, fat: +e.target.value})}
                                            />
                                        </div>
                                        <div className="diary-form-field">
                                            <label>Углеводы (г)</label>
                                            <input
                                                type="number"
                                                min="0"
                                                step="0.1"
                                                value={newEntry.carbs}
                                                onChange={e => setNewEntry({...newEntry, carbs: +e.target.value})}
                                            />
                                        </div>
                                    </div>
                                    <div className="diary-form-row">
                                        <select
                                            value={newEntry.mealType}
                                            onChange={e => setNewEntry({...newEntry, mealType: e.target.value as any})}
                                        >
                                            <option value="breakfast">🌅 Завтрак</option>
                                            <option value="lunch">☀️ Обед</option>
                                            <option value="dinner">🌙 Ужин</option>
                                            <option value="snack">🍿 Перекус</option>
                                        </select>
                                        <button type="submit" className="diary-submit-button">
                                            Добавить в дневник
                                        </button>
                                    </div>
                                </form>
                            )}

                            {/* Список */}
                            {isLoading ? (
                                <div className="diary-loading">Загрузка...</div>
                            ) : entries.length === 0 ? (
                                <div className="diary-empty">
                                    Записей пока нет. Добавьте еду через форму выше или напишите боту!
                                </div>
                            ) : (
                                <div className="diary-entries-list">
                                    {entries.map((entry, idx) => (
                                        <div key={entry.id || idx} className="diary-entry-card">
                                            <div className="diary-entry-main">
                                                <span className="diary-entry-meal">{mealTypeLabels[entry.mealType] || '🍽️'}</span>
                                                <span className="diary-entry-name">{entry.name}</span>
                                                <span className="diary-entry-calories">{entry.calories} ккал</span>
                                            </div>
                                            <div className="diary-entry-details">
                                                <span>Б: {entry.protein || 0}г</span>
                                                <span>Ж: {entry.fat || 0}г</span>
                                                <span>У: {entry.carbs || 0}г</span>
                                                <span className="diary-entry-time">
                                                    {entry.timestamp.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
                                                </span>
                                            </div>
                                            <button 
                                                className="diary-entry-delete"
                                                onClick={() => handleDeleteEntry(entry.name)}
                                                title="Удалить"
                                            >
                                                🗑️
                                            </button>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </>
                ) : (
                    /* Вкладка профиля */
                    <div className="diary-profile-section">
                        <h3>👤 Физические параметры</h3>
                        <p className="diary-profile-desc">
                            Заполните данные для автоматического расчёта нормы калорий и БЖУ по формуле Миффлина-Сан Жеора
                        </p>
                        
                        <div className="diary-profile-form">
                            <div className="profile-row">
                                <div className="profile-field">
                                    <label>Вес (кг)</label>
                                    <input
                                        type="number"
                                        min="30"
                                        max="300"
                                        placeholder="70"
                                        value={bodyParams.weight}
                                        onChange={e => setBodyParams({...bodyParams, weight: e.target.value})}
                                    />
                                </div>
                                <div className="profile-field">
                                    <label>Рост (см)</label>
                                    <input
                                        type="number"
                                        min="100"
                                        max="250"
                                        placeholder="175"
                                        value={bodyParams.height}
                                        onChange={e => setBodyParams({...bodyParams, height: e.target.value})}
                                    />
                                </div>
                                <div className="profile-field">
                                    <label>Возраст</label>
                                    <input
                                        type="number"
                                        min="10"
                                        max="120"
                                        placeholder="25"
                                        value={bodyParams.age}
                                        onChange={e => setBodyParams({...bodyParams, age: e.target.value})}
                                    />
                                </div>
                            </div>

                            <div className="profile-row">
                                <div className="profile-field">
                                    <label>Пол</label>
                                    <select
                                        value={bodyParams.gender}
                                        onChange={e => setBodyParams({...bodyParams, gender: e.target.value})}
                                    >
                                        <option value="">Выберите...</option>
                                        <option value="male">👨 Мужской</option>
                                        <option value="female">👩 Женский</option>
                                    </select>
                                </div>
                                <div className="profile-field wide">
                                    <label>Уровень активности</label>
                                    <select
                                        value={bodyParams.activityLevel}
                                        onChange={e => setBodyParams({...bodyParams, activityLevel: e.target.value})}
                                    >
                                        <option value="">Выберите...</option>
                                        {Object.entries(activityLabels).map(([key, label]) => (
                                            <option key={key} value={key}>{label}</option>
                                        ))}
                                    </select>
                                </div>
                            </div>

                            <div className="profile-row">
                                <div className="profile-field wide">
                                    <label>🎯 Цель</label>
                                    <div className="goal-buttons">
                                        {Object.entries(goalLabels).map(([key, label]) => (
                                            <button
                                                key={key}
                                                type="button"
                                                className={`goal-btn ${bodyParams.goal === key ? 'active' : ''}`}
                                                onClick={() => setBodyParams({...bodyParams, goal: key})}
                                            >
                                                {label}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            </div>

                            {preferences.targetCalories && preferences.targetProtein && (
                                <div className="profile-calculated">
                                    <h4>📊 Ваша норма (рассчитано):</h4>
                                    <div className="calculated-values">
                                        <div className="calc-item">
                                            <span className="calc-label">Калории</span>
                                            <span className="calc-value">{preferences.targetCalories} ккал</span>
                                        </div>
                                        <div className="calc-item">
                                            <span className="calc-label">Белки</span>
                                            <span className="calc-value protein">{preferences.targetProtein}г</span>
                                        </div>
                                        <div className="calc-item">
                                            <span className="calc-label">Жиры</span>
                                            <span className="calc-value fat">{preferences.targetFat}г</span>
                                        </div>
                                        <div className="calc-item">
                                            <span className="calc-label">Углеводы</span>
                                            <span className="calc-value carbs">{preferences.targetCarbs}г</span>
                                        </div>
                                    </div>
                                </div>
                            )}

                            <button 
                                className="profile-save-button"
                                onClick={handleSaveProfile}
                                disabled={isSaving}
                            >
                                {isSaving ? 'Сохранение...' : '💾 Сохранить и рассчитать норму'}
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

export default DiaryModal;
