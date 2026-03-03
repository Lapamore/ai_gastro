import React from 'react';
import './Sidebar.css';
import type { SessionDisplayInfo, DailyProgress, CookingMode, GroupSettings } from '../../types';

const COMMON_ALLERGIES = ['Глютен', 'Лактоза', 'Орехи', 'Яйца', 'Морепродукты', 'Соя'];
const COMMON_RESTRICTIONS = ['Вегетарианство', 'Веганство', 'Халяль', 'Кошер', 'Без сахара', 'Без свинины'];

interface SidebarProps {
    isOpen: boolean;
    sessions: SessionDisplayInfo[];
    activeSessionId: string | null;
    isLoadingSuggestions: boolean;
    dailyProgress?: DailyProgress;
    cookingMode: CookingMode;
    groupSettings: GroupSettings;
    onCookingModeChange: (mode: CookingMode) => void;
    onGroupSettingsChange: (settings: GroupSettings) => void;
    onSelectSession: (id: string) => void;
    onNewChat: () => void;
    onDeleteSession: (id: string) => void;
    onFetchSuggestions: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({
    isOpen,
    sessions,
    activeSessionId,
    isLoadingSuggestions,
    dailyProgress,
    cookingMode,
    groupSettings,
    onCookingModeChange,
    onGroupSettingsChange,
    onSelectSession,
    onNewChat,
    onDeleteSession,
    onFetchSuggestions
}) => {
    const formatDate = (d: Date) => 
        !d || isNaN(d.getTime()) ? "недавно" : d.toLocaleString('ru-RU', {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});

    // Расчет процента для прогресс-бара
    const progressPercent = dailyProgress 
        ? Math.min((dailyProgress.totalCalories / dailyProgress.targetCalories) * 100, 100) 
        : 0;

    const toggleTag = (list: string[], tag: string): string[] =>
        list.includes(tag) ? list.filter(t => t !== tag) : [...list, tag];

    return (
        <div className={`sidebar-panel ${isOpen ? 'open' : ''}`}>
            {/* Режим готовки */}
            <div className="cooking-mode-section">
                <h3 className="cooking-mode-title">Режим готовки</h3>
                <div className="cooking-mode-toggle">
                    <button
                        className={`mode-btn ${cookingMode === 'solo' ? 'active' : ''}`}
                        onClick={() => onCookingModeChange('solo')}
                    >
                        🧑‍🍳 Для себя
                    </button>
                    <button
                        className={`mode-btn ${cookingMode === 'group' ? 'active' : ''}`}
                        onClick={() => onCookingModeChange('group')}
                    >
                        👨‍👩‍👧‍👦 Компания
                    </button>
                </div>
            </div>

            {cookingMode === 'solo' && (
                <>
                    <h2>Гастро-Дневник</h2>
                    {/* Виджет калорий */}
                    <div className="calorie-widget">
                        <div className="calorie-info">
                            <span>{dailyProgress?.totalCalories || 0} / {dailyProgress?.targetCalories || 2000} ккал</span>
                        </div>
                        <div className="progress-container">
                            <div className="progress-bar" style={{ width: `${progressPercent}%` }}></div>
                        </div>
                        <div className="macros-info">
                            <span>Б: {dailyProgress?.protein || 0}г</span>
                            <span>Ж: {dailyProgress?.fat || 0}г</span>
                            <span>У: {dailyProgress?.carbs || 0}г</span>
                        </div>
                    </div>
                </>
            )}

            {cookingMode === 'group' && (
                <div className="group-settings-section">
                    <div className="group-guest-count">
                        <label>Гостей: <strong>{groupSettings.guestCount}</strong></label>
                        <input
                            type="range"
                            min={2}
                            max={20}
                            value={groupSettings.guestCount}
                            onChange={e => onGroupSettingsChange({ ...groupSettings, guestCount: Number(e.target.value) })}
                            className="guest-slider"
                        />
                    </div>

                    <div className="group-tags-block">
                        <label className="group-tags-label">🚫 Аллергии группы</label>
                        <div className="group-tags">
                            {COMMON_ALLERGIES.map(tag => (
                                <button
                                    key={tag}
                                    className={`group-tag ${groupSettings.allergies.includes(tag) ? 'active' : ''}`}
                                    onClick={() => onGroupSettingsChange({ ...groupSettings, allergies: toggleTag(groupSettings.allergies, tag) })}
                                >
                                    {tag}
                                </button>
                            ))}
                        </div>
                    </div>

                    <div className="group-tags-block">
                        <label className="group-tags-label">🥗 Ограничения</label>
                        <div className="group-tags">
                            {COMMON_RESTRICTIONS.map(tag => (
                                <button
                                    key={tag}
                                    className={`group-tag ${groupSettings.restrictions.includes(tag) ? 'active' : ''}`}
                                    onClick={() => onGroupSettingsChange({ ...groupSettings, restrictions: toggleTag(groupSettings.restrictions, tag) })}
                                >
                                    {tag}
                                </button>
                            ))}
                        </div>
                    </div>
                </div>
            )}

            <hr className="sidebar-divider" />

            <h2>Диалоги</h2>
            <button onClick={onNewChat} className="sidebar-action-button new-chat-button"> + Новый чат </button>
            <button 
                onClick={onFetchSuggestions} 
                disabled={isLoadingSuggestions}
                className="sidebar-action-button suggestions-button"
            >
                {isLoadingSuggestions ? "Думаю..." : "💡 Идеи для меня"}
            </button>
            <div className="sessions-list">
                {sessions.map(s => (
                    <div key={s.id} className={`session-item ${s.id===activeSessionId?'active':''}`} onClick={()=>onSelectSession(s.id)}>
                        <span className="session-title">{s.title}</span>
                        <div className="session-meta">
                            <span className="session-timestamp">{formatDate(s.updated_at)}</span>
                            <button className="delete-session-button" 
                                onClick={e => { e.stopPropagation(); if(window.confirm(`Удалить "${s.title}"?`)) onDeleteSession(s.id); }}>
                                🗑️
                            </button>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default Sidebar;