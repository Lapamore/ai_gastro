// src/components/SettingsModal/SettingsModal.tsx
import React, { useState, useEffect } from 'react';
import type { UserPreferences } from '../../App'; // Импортируем тип из App.tsx
import './SettingsModal.css';

interface SettingsModalProps {
    isOpen: boolean;
    onClose: () => void;
    preferences: UserPreferences;
    onPreferencesChange: (newPreferences: UserPreferences) => void;
}

const ALLERGY_OPTIONS = ["глютен", "лактоза", "орехи", "морепродукты", "яйца", "соя", "цитрус"];
const DIET_OPTIONS = ["вегетарианство", "веганство", "пескетарианство", "без сахара", "низкокалорийное", "кето"];
const CUISINE_OPTIONS = ["итальянская", "французская", "азиатская", "мексиканская", "русская", "индийская", "средиземноморская"];
const DIFFICULTY_OPTIONS: UserPreferences['preferredDifficulty'][] = [null, "легко", "средне", "сложно"];
const TIME_OPTIONS: UserPreferences['availableTime'][] = [null, "15 мин", "30 мин", "1 час", ">1 часа"];


const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose, preferences, onPreferencesChange }) => {
    const [currentPrefs, setCurrentPrefs] = useState<UserPreferences>(preferences);

    useEffect(() => {
        if (isOpen) { // Обновляем внутреннее состояние только при открытии, чтобы не сбрасывать изменения пользователя
            setCurrentPrefs(preferences); 
        }
    }, [preferences, isOpen]);

    if (!isOpen) {
        return null;
    }

    const handleMultiSelectChange = (field: keyof Pick<UserPreferences, 'allergies' | 'dietaryRestrictions' | 'favoriteCuisines' | 'dislikedCuisines'>, value: string) => {
        const currentValues = currentPrefs[field] as string[];
        const newValues = currentValues.includes(value)
            ? currentValues.filter(item => item !== value)
            : [...currentValues, value];
        setCurrentPrefs(prev => ({ ...prev, [field]: newValues }));
    };
    
    const handleTagInputChange = (field: keyof Pick<UserPreferences, 'favoriteIngredients' | 'dislikedIngredients'>, e: React.ChangeEvent<HTMLInputElement>) => {
        const tags = e.target.value.split(',').map(tag => tag.trim()).filter(tag => tag !== '');
        setCurrentPrefs(prev => ({ ...prev, [field]: tags }));
    };

    const handleSingleSelectChange = (field: keyof Pick<UserPreferences, 'preferredDifficulty' | 'availableTime'>, value: string) => {
        // Если выбрано "Любая/Любое", значение будет пустой строкой, преобразуем в null
        const actualValue = value === "" ? null : value;
        setCurrentPrefs(prev => ({ ...prev, [field]: actualValue as any }));
    };

    const handleSave = () => {
        onPreferencesChange(currentPrefs);
        onClose();
    };
    
    const renderMultiSelect = (label: string, field: keyof Pick<UserPreferences, 'allergies' | 'dietaryRestrictions' | 'favoriteCuisines' | 'dislikedCuisines'>, options: readonly string[]) => (
        <div className="settings-group">
            <label>{label}:</label>
            <div className="checkbox-group">
                {options.map(option => (
                    <label key={option} className={`checkbox-label ${ (currentPrefs[field] as string[]).includes(option) ? 'checked' : ''}`}>
                        <input
                            type="checkbox"
                            checked={(currentPrefs[field] as string[]).includes(option)}
                            onChange={() => handleMultiSelectChange(field, option)}
                        />
                        <span>{option.charAt(0).toUpperCase() + option.slice(1)}</span>
                    </label>
                ))}
            </div>
        </div>
    );

    return (
        <div className="settings-modal-overlay" onClick={onClose}>
            <div className="settings-modal-content" onClick={(e) => e.stopPropagation()}>
                <div className="settings-modal-header">
                    <h2>Настройки Помощника</h2>
                    <button onClick={onClose} className="close-settings-button">×</button>
                </div>
                <div className="settings-modal-body">
                    {renderMultiSelect("Аллергии", "allergies", ALLERGY_OPTIONS)}
                    {renderMultiSelect("Диетические ограничения", "dietaryRestrictions", DIET_OPTIONS)}
                    {renderMultiSelect("Любимые кухни", "favoriteCuisines", CUISINE_OPTIONS)}
                    {renderMultiSelect("Нелюбимые кухни", "dislikedCuisines", CUISINE_OPTIONS)}

                    <div className="settings-group">
                        <label htmlFor="favIngredients">Любимые ингредиенты (через запятую):</label>
                        <input 
                            type="text" 
                            id="favIngredients" 
                            placeholder="например: курица, брокколи, чеснок"
                            value={currentPrefs.favoriteIngredients.join(', ')} 
                            onChange={(e) => handleTagInputChange('favoriteIngredients', e)}
                        />
                    </div>
                    <div className="settings-group">
                        <label htmlFor="dislikedIngredients">Нелюбимые ингредиенты (через запятую):</label>
                        <input 
                            type="text" 
                            id="dislikedIngredients" 
                            placeholder="например: лук, оливки"
                            value={currentPrefs.dislikedIngredients.join(', ')} 
                            onChange={(e) => handleTagInputChange('dislikedIngredients', e)}
                        />
                    </div>

                    <div className="settings-group">
                        <label htmlFor="difficulty">Предпочитаемая сложность:</label>
                        <select 
                            id="difficulty" 
                            value={currentPrefs.preferredDifficulty || ''} 
                            onChange={(e) => handleSingleSelectChange('preferredDifficulty', e.target.value)}
                        >
                            {DIFFICULTY_OPTIONS.map(opt => <option key={opt || 'any-diff'} value={opt || ''}>{opt || 'Любая'}</option>)}
                        </select>
                    </div>

                    <div className="settings-group">
                        <label htmlFor="time">Доступное время на готовку:</label>
                        <select 
                            id="time" 
                            value={currentPrefs.availableTime || ''} 
                            onChange={(e) => handleSingleSelectChange('availableTime', e.target.value)}
                        >
                             {TIME_OPTIONS.map(opt => <option key={opt || 'any-time'} value={opt || ''}>{opt || 'Любое'}</option>)}
                        </select>
                    </div>
                </div>
                <div className="settings-modal-footer">
                    <button onClick={handleSave} className="save-settings-button">Сохранить</button>
                    <button onClick={onClose} className="cancel-settings-button">Отмена</button>
                </div>
            </div>
        </div>
    );
};

export default SettingsModal;