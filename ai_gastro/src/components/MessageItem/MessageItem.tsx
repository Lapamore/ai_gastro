import React from 'react';
import './MessageItem.css';
import SuggestionButton from '../SuggestionButton/SuggestionButton';

interface MessageItemProps {
    sender: 'user' | 'bot';
    text: string;
    timestamp: Date;
    suggestions?: string[];
    onSuggestionClick: (suggestionText: string) => void;
}

const MessageItem: React.FC<MessageItemProps> = ({ sender, text, timestamp, suggestions, onSuggestionClick }) => {
    const formatTime = (date: Date): string => {
        return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
    };

    return (
        <div className={`message-wrapper ${sender}`}>
            <div className={`message ${sender}`}>
                <div className="avatar">
                    {sender === 'bot' ? '🤖' : '🧑'}
                </div>
                <div className="message-content">
                    <div className="sender-name">
                        {sender === 'bot' ? 'Гастро-Помощник' : 'Ты'}
                    </div>
                    <div className="text" dangerouslySetInnerHTML={{ __html: text }}></div>
                    {timestamp && <div className="timestamp">{formatTime(timestamp)}</div>}
                </div>
            </div>
            {suggestions && suggestions.length > 0 && (
                <div className={`suggestion-buttons-container ${sender === 'bot' ? 'bot-suggestions' : ''}`}>
                    {suggestions.map((suggestion, index) => (
                        <SuggestionButton
                            key={index}
                            text={suggestion}
                            onClick={() => onSuggestionClick(suggestion)}
                        />
                    ))}
                </div>
            )}
        </div>
    );
};

export default MessageItem;