import React, { useEffect, useState, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { AxiosInstance } from 'axios';
import type { DiaryEntryInput, SavedRecipe } from '../../types';
import './FavoritesModal.css';

interface FavoritesModalProps {
    isOpen: boolean;
    onClose: () => void;
    api: AxiosInstance;
    onDiaryEntryAdded?: () => void | Promise<void>;
}

type AddStatus = {
    type: 'success' | 'error';
    text: string;
};

const readNumber = (value: unknown): number | undefined => {
    if (typeof value === 'number' && Number.isFinite(value)) return value;
    if (typeof value !== 'string') return undefined;

    const parsed = Number(value.replace(',', '.').replace(/[^\d.-]/g, ''));
    return Number.isFinite(parsed) ? parsed : undefined;
};

const toMacro = (value: unknown): number => {
    const parsed = readNumber(value);
    return parsed == null ? 0 : Math.max(0, Math.round(parsed * 10) / 10);
};

const toCalories = (value: unknown): number => {
    const parsed = readNumber(value);
    return parsed == null ? 0 : Math.max(0, Math.round(parsed));
};

const firstNumberByPatterns = (text: string, patterns: RegExp[]): number | undefined => {
    for (const pattern of patterns) {
        const match = text.match(pattern);
        const parsed = readNumber(match?.[1]);
        if (parsed != null) return parsed;
    }
    return undefined;
};

const cleanRecipeText = (text: string): string =>
    text
        .replace(/\[ADD_FOOD:\s*\{[\s\S]*?\}\]/g, '')
        .replace(/\[YOUTUBE_SEARCH:\s*"[^"]*"\]/g, '')
        .trim();

const cleanTitle = (text: string): string =>
    text
        .replace(/[*_`>#]/g, '')
        .replace(/^[-–—•\d.)\s]+/, '')
        .replace(/\s+/g, ' ')
        .trim();

const extractTitle = (text: string): string => {
    const heading = text.match(/^#{1,3}\s+(.+)$/m)?.[1];
    const bold = text.match(/\*\*([^*\n]{3,100})\*\*/)?.[1];
    const firstUsefulLine = text
        .split('\n')
        .map(cleanTitle)
        .find(line =>
            line.length >= 3 &&
            line.length <= 90 &&
            !line.endsWith(':') &&
            !line.toLowerCase().startsWith('ингредиенты') &&
            !line.toLowerCase().startsWith('инструкция') &&
            !line.toLowerCase().startsWith('приготовление')
        );

    return cleanTitle(heading || bold || firstUsefulLine || 'Избранный рецепт');
};

const extractAddFoodPayload = (text: string): Record<string, unknown> | null => {
    const match = text.match(/\[ADD_FOOD:\s*(\{[\s\S]*?\})\]/);
    if (!match?.[1]) return null;

    try {
        const parsed: unknown = JSON.parse(match[1]);
        return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
            ? parsed as Record<string, unknown>
            : null;
    } catch {
        return null;
    }
};

const buildDiaryDraft = (messageText: string): DiaryEntryInput => {
    const cleanText = cleanRecipeText(messageText);
    const addFood = extractAddFoodPayload(messageText);

    const calories = addFood?.calories ?? firstNumberByPatterns(cleanText, [
        /(?:калории|калорийность)[^\d]{0,20}(\d+(?:[.,]\d+)?)/i,
        /(\d+(?:[.,]\d+)?)\s*(?:ккал|калори[йяие]*)/i,
    ]);

    const protein = addFood?.protein ?? firstNumberByPatterns(cleanText, [
        /(?:белк[а-яё]*|protein)[^\d]{0,20}(\d+(?:[.,]\d+)?)/i,
        /(?:^|[\s(])Б\s*[:=-]?\s*(\d+(?:[.,]\d+)?)/im,
    ]);

    const fat = addFood?.fat ?? firstNumberByPatterns(cleanText, [
        /(?:жир[а-яё]*|fat)[^\d]{0,20}(\d+(?:[.,]\d+)?)/i,
        /(?:^|[\s(])Ж\s*[:=-]?\s*(\d+(?:[.,]\d+)?)/im,
    ]);

    const carbs = addFood?.carbs ?? firstNumberByPatterns(cleanText, [
        /(?:углевод[а-яё]*|carbs)[^\d]{0,20}(\d+(?:[.,]\d+)?)/i,
        /(?:^|[\s(])У\s*[:=-]?\s*(\d+(?:[.,]\d+)?)/im,
    ]);

    return {
        name: String(addFood?.name || extractTitle(cleanText)),
        calories: toCalories(calories),
        protein: toMacro(protein),
        fat: toMacro(fat),
        carbs: toMacro(carbs),
        mealType: 'snack',
    };
};

const FavoritesModal: React.FC<FavoritesModalProps> = ({ isOpen, onClose, api, onDiaryEntryAdded }) => {
    const [recipes, setRecipes] = useState<SavedRecipe[]>([]);
    const [loading, setLoading] = useState(false);
    const [expandedId, setExpandedId] = useState<number | null>(null);
    const [diaryDrafts, setDiaryDrafts] = useState<Record<number, DiaryEntryInput>>({});
    const [addingRecipeId, setAddingRecipeId] = useState<number | null>(null);
    const [addStatuses, setAddStatuses] = useState<Record<number, AddStatus>>({});

    const fetchFavorites = useCallback(async () => {
        setLoading(true);
        try {
            const res = await api.get('/recipes/favorites');
            setRecipes(res.data);
        } catch (e) {
            console.error('Ошибка загрузки избранных рецептов', e);
        } finally {
            setLoading(false);
        }
    }, [api]);

    useEffect(() => {
        if (isOpen) {
            fetchFavorites();
            setExpandedId(null);
            setAddStatuses({});
        }
    }, [isOpen, fetchFavorites]);

    const handleToggleRecipe = (recipe: SavedRecipe) => {
        const shouldOpen = expandedId !== recipe.id;
        setExpandedId(shouldOpen ? recipe.id : null);

        if (shouldOpen) {
            setDiaryDrafts(prev => (
                prev[recipe.id]
                    ? prev
                    : { ...prev, [recipe.id]: buildDiaryDraft(recipe.message_text) }
            ));
        }
    };

    const updateDiaryDraft = (recipe: SavedRecipe, patch: Partial<DiaryEntryInput>) => {
        setDiaryDrafts(prev => {
            const currentDraft = prev[recipe.id] || buildDiaryDraft(recipe.message_text);
            return {
                ...prev,
                [recipe.id]: {
                    ...currentDraft,
                    ...patch,
                },
            };
        });
        setAddStatuses(prev => {
            const next = { ...prev };
            delete next[recipe.id];
            return next;
        });
    };

    const handleAddToDiary = async (recipe: SavedRecipe) => {
        const draft = diaryDrafts[recipe.id] || buildDiaryDraft(recipe.message_text);
        const entry: DiaryEntryInput = {
            name: draft.name.trim(),
            calories: toCalories(draft.calories),
            protein: toMacro(draft.protein),
            fat: toMacro(draft.fat),
            carbs: toMacro(draft.carbs),
            mealType: draft.mealType,
        };

        if (!entry.name) {
            setAddStatuses(prev => ({
                ...prev,
                [recipe.id]: { type: 'error', text: 'Укажите название блюда.' },
            }));
            return;
        }

        setAddingRecipeId(recipe.id);
        try {
            await api.post('/diary/add', entry);
            await onDiaryEntryAdded?.();
            setAddStatuses(prev => ({
                ...prev,
                [recipe.id]: { type: 'success', text: 'Добавлено в дневник питания.' },
            }));
        } catch (e) {
            console.error('Ошибка добавления рецепта в дневник', e);
            setAddStatuses(prev => ({
                ...prev,
                [recipe.id]: { type: 'error', text: 'Не удалось добавить в дневник.' },
            }));
        } finally {
            setAddingRecipeId(null);
        }
    };

    const handleDelete = async (id: number) => {
        try {
            await api.delete(`/recipes/${id}`);
            setRecipes(prev => prev.filter(r => r.id !== id));
            setDiaryDrafts(prev => {
                const next = { ...prev };
                delete next[id];
                return next;
            });
            setAddStatuses(prev => {
                const next = { ...prev };
                delete next[id];
                return next;
            });
        } catch (e) {
            console.error('Ошибка удаления рецепта', e);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="favorites-modal-overlay" onClick={onClose}>
            <div className="favorites-modal-content" onClick={e => e.stopPropagation()}>
                <div className="favorites-modal-header">
                    <h2>⭐ Избранные рецепты</h2>
                    <button className="favorites-modal-close" onClick={onClose}>✕</button>
                </div>

                <div className="favorites-modal-body">
                    {loading && <div className="favorites-loading">Загрузка...</div>}

                    {!loading && recipes.length === 0 && (
                        <div className="favorites-empty">
                            <span className="favorites-empty-icon">📭</span>
                            <p>У вас пока нет избранных рецептов</p>
                            <p className="favorites-empty-hint">
                                Нажмите 👍 на сообщении бота, чтобы сохранить рецепт
                            </p>
                        </div>
                    )}

                    {!loading && recipes.map(recipe => {
                        const displayText = cleanRecipeText(recipe.message_text);

                        return (
                        <div key={recipe.id} className="favorite-recipe-card">
                            <div 
                                className="favorite-recipe-header"
                                onClick={() => handleToggleRecipe(recipe)}
                            >
                                <div className="favorite-recipe-preview">
                                    {displayText.slice(0, 100).replace(/\n/g, ' ')}
                                    {displayText.length > 100 ? '...' : ''}
                                </div>
                                <div className="favorite-recipe-meta">
                                    <span className="favorite-recipe-date">
                                        {new Date(recipe.created_at).toLocaleDateString('ru-RU')}
                                    </span>
                                    <span className={`favorite-recipe-expand ${expandedId === recipe.id ? 'expanded' : ''}`}>
                                        ▼
                                    </span>
                                </div>
                            </div>

                            {expandedId === recipe.id && (
                                <div className="favorite-recipe-body">
                                    <div className="favorite-recipe-text markdown-content">
                                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                            {displayText}
                                        </ReactMarkdown>
                                    </div>

                                    {(() => {
                                        const draft = diaryDrafts[recipe.id] || buildDiaryDraft(recipe.message_text);
                                        const status = addStatuses[recipe.id];

                                        return (
                                            <>
                                                <div className="favorite-diary-form">
                                                    <div className="favorite-diary-title">Добавить в дневник</div>
                                                    <div className="favorite-diary-grid">
                                                        <label className="favorite-diary-field favorite-diary-field-wide">
                                                            <span>Название</span>
                                                            <input
                                                                type="text"
                                                                value={draft.name}
                                                                onChange={e => updateDiaryDraft(recipe, { name: e.target.value })}
                                                            />
                                                        </label>
                                                        <label className="favorite-diary-field">
                                                            <span>Приём пищи</span>
                                                            <select
                                                                value={draft.mealType}
                                                                onChange={e => updateDiaryDraft(recipe, { mealType: e.target.value as DiaryEntryInput['mealType'] })}
                                                            >
                                                                <option value="breakfast">Завтрак</option>
                                                                <option value="lunch">Обед</option>
                                                                <option value="dinner">Ужин</option>
                                                                <option value="snack">Перекус</option>
                                                            </select>
                                                        </label>
                                                        <label className="favorite-diary-field">
                                                            <span>Ккал</span>
                                                            <input
                                                                type="number"
                                                                min="0"
                                                                value={draft.calories}
                                                                onChange={e => updateDiaryDraft(recipe, { calories: toCalories(e.target.value) })}
                                                            />
                                                        </label>
                                                        <label className="favorite-diary-field">
                                                            <span>Белки</span>
                                                            <input
                                                                type="number"
                                                                min="0"
                                                                step="0.1"
                                                                value={draft.protein}
                                                                onChange={e => updateDiaryDraft(recipe, { protein: toMacro(e.target.value) })}
                                                            />
                                                        </label>
                                                        <label className="favorite-diary-field">
                                                            <span>Жиры</span>
                                                            <input
                                                                type="number"
                                                                min="0"
                                                                step="0.1"
                                                                value={draft.fat}
                                                                onChange={e => updateDiaryDraft(recipe, { fat: toMacro(e.target.value) })}
                                                            />
                                                        </label>
                                                        <label className="favorite-diary-field">
                                                            <span>Углеводы</span>
                                                            <input
                                                                type="number"
                                                                min="0"
                                                                step="0.1"
                                                                value={draft.carbs}
                                                                onChange={e => updateDiaryDraft(recipe, { carbs: toMacro(e.target.value) })}
                                                            />
                                                        </label>
                                                    </div>
                                                    <button
                                                        className="favorite-recipe-add"
                                                        onClick={() => handleAddToDiary(recipe)}
                                                        disabled={addingRecipeId === recipe.id}
                                                    >
                                                        {addingRecipeId === recipe.id ? 'Добавляю...' : '➕ Добавить в дневник'}
                                                    </button>
                                                    {status && (
                                                        <div className={`favorite-diary-status ${status.type}`}>
                                                            {status.text}
                                                        </div>
                                                    )}
                                                </div>

                                                <button 
                                                    className="favorite-recipe-delete"
                                                    onClick={() => handleDelete(recipe.id)}
                                                >
                                                    🗑️ Удалить из избранного
                                                </button>
                                            </>
                                        );
                                    })()}
                                </div>
                            )}
                        </div>
                        );
                    })}
                </div>
            </div>
        </div>
    );
};

export default FavoritesModal;
