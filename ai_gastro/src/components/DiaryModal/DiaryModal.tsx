import { useState, useEffect } from 'react';
import type { AxiosInstance } from 'axios';
import type { DiaryEntry, DiaryEntryInput, DailyProgress } from '../../types';
import './DiaryModal.css';

interface DiaryModalProps {
    isOpen: boolean;
    onClose: () => void;
    dailyProgress: DailyProgress;
    onProgressUpdate: (progress: DailyProgress) => void;
    api: AxiosInstance;
}

const mealTypeLabels: Record<string, string> = {
    breakfast: '🌅 Завтрак',
    lunch: '☀️ Обед',
    dinner: '🌙 Ужин',
    snack: '🍿 Перекус'
};

function DiaryModal({ isOpen, onClose, dailyProgress, onProgressUpdate, api }: DiaryModalProps) {
    const [entries, setEntries] = useState<DiaryEntry[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [showAddForm, setShowAddForm] = useState(false);
    
    // Форма добавления
    const [newEntry, setNewEntry] = useState<DiaryEntryInput>({
        name: '',
        calories: 0,
        protein: 0,
        fat: 0,
        carbs: 0,
        mealType: 'snack'
    });

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
                targetCalories: dailyProgress.targetCalories
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

    if (!isOpen) return null;

    const progressPercent = Math.min((dailyProgress.totalCalories / dailyProgress.targetCalories) * 100, 100);

    return (
        <div className="diary-modal-overlay" onClick={onClose}>
            <div className="diary-modal-content" onClick={e => e.stopPropagation()}>
                <div className="diary-modal-header">
                    <h2>📔 Дневник питания</h2>
                    <button className="diary-modal-close" onClick={onClose}>×</button>
                </div>

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
                            <span className="macro-value protein">{dailyProgress.protein}г</span>
                        </div>
                        <div className="diary-macro">
                            <span className="macro-label">Жиры</span>
                            <span className="macro-value fat">{dailyProgress.fat}г</span>
                        </div>
                        <div className="diary-macro">
                            <span className="macro-label">Углеводы</span>
                            <span className="macro-value carbs">{dailyProgress.carbs}г</span>
                        </div>
                    </div>
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
            </div>
        </div>
    );
}

export default DiaryModal;
