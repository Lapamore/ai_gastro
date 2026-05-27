import React from 'react';
import './ChatHeader.css';

interface ChatHeaderProps {
    onClearChat?: () => void;
}

const ChatHeader: React.FC<ChatHeaderProps> = ({ onClearChat }) => {
    return (
        <div className="chat-header">
            <span className="chat-header-icon" role="img" aria-label="Chef Emoji">👨‍🍳</span>
            Гастро-Помощник
            {onClearChat && (
                <button onClick={onClearChat} className="clear-chat-button" title="Очистить чат">
                    🗑️
                </button>
            )}
        </div>
    );
};

export default ChatHeader;