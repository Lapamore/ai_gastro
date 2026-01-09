import React from 'react';
import './Sidebar.css';
import type { SessionDisplayInfo, DailyProgress } from '../../types';

interface SidebarProps {
    isOpen: boolean;
    sessions: SessionDisplayInfo[];
    activeSessionId: string | null;
    isLoadingSuggestions: boolean;
    dailyProgress?: DailyProgress; // Новое
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

    return (
        <div className={`sidebar-panel ${isOpen ? 'open' : ''}`}>
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