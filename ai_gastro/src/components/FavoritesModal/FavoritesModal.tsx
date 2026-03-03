import React, { useEffect, useState, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { AxiosInstance } from 'axios';
import type { SavedRecipe } from '../../types';
import './FavoritesModal.css';

interface FavoritesModalProps {
    isOpen: boolean;
    onClose: () => void;
    api: AxiosInstance;
}

const FavoritesModal: React.FC<FavoritesModalProps> = ({ isOpen, onClose, api }) => {
    const [recipes, setRecipes] = useState<SavedRecipe[]>([]);
    const [loading, setLoading] = useState(false);
    const [expandedId, setExpandedId] = useState<number | null>(null);

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
        }
    }, [isOpen, fetchFavorites]);

    const handleDelete = async (id: number) => {
        try {
            await api.delete(`/recipes/${id}`);
            setRecipes(prev => prev.filter(r => r.id !== id));
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

                    {!loading && recipes.map(recipe => (
                        <div key={recipe.id} className="favorite-recipe-card">
                            <div 
                                className="favorite-recipe-header"
                                onClick={() => setExpandedId(expandedId === recipe.id ? null : recipe.id)}
                            >
                                <div className="favorite-recipe-preview">
                                    {recipe.message_text.slice(0, 100).replace(/\n/g, ' ')}
                                    {recipe.message_text.length > 100 ? '...' : ''}
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
                                            {recipe.message_text}
                                        </ReactMarkdown>
                                    </div>
                                    <button 
                                        className="favorite-recipe-delete"
                                        onClick={() => handleDelete(recipe.id)}
                                    >
                                        🗑️ Удалить из избранного
                                    </button>
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};

export default FavoritesModal;
