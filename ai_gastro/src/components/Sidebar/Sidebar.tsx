import React from 'react';
import './Sidebar.css';
import type { SessionDisplayInfo } from '../../types';

interface SidebarProps {
    isOpen: boolean;
    sessions: SessionDisplayInfo[];
    activeSessionId: string | null;
    isLoadingSuggestions: boolean;
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
    onSelectSession,
    onNewChat,
    onDeleteSession,
    onFetchSuggestions
}) => {
    const formatDate = (d: Date) => 
        !d || isNaN(d.getTime()) ? "недавно" : d.toLocaleString('ru-RU', {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});

    return (
        <div className={`sidebar-panel ${isOpen ? 'open' : ''}`}>
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
                {sessions.length === 0 && <p className="no-sessions-message">Нет диалогов.</p>}
            </div>
        </div>
    );
};

export default Sidebar;