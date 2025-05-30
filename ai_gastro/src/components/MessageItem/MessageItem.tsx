// src/components/MessageItem/MessageItem.tsx
import React from 'react';
import ReactMarkdown from 'react-markdown'; // Оставляем основной импорт
import type { Options as ReactMarkdownOptions } from 'react-markdown'; // <--- ИМПОРТИРУЕМ ТИП ОТДЕЛЬНО
import remarkGfm from 'remark-gfm';
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

    // Опции для ReactMarkdown
    const markdownProps: ReactMarkdownOptions = { // Теперь ReactMarkdownOptions это импортированный тип
        remarkPlugins: [remarkGfm],
        components: {
            a: ({node, ...props}) => <a {...props} target="_blank" rel="noopener noreferrer" />,
        },
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

                    {sender === 'bot' ? (
                        <div className="text markdown-content">
                           <ReactMarkdown {...markdownProps}>{text}</ReactMarkdown>
                        </div>
                    ) : (
                        <div className="text"> 
                            {text} 
                        </div>
                    )}

                    {timestamp && <div className="timestamp">{formatTime(timestamp)}</div>}
                </div>
            </div>
            {suggestions && suggestions.length > 0 && (
                <div className={`suggestion-buttons-container ${sender === 'bot' ? 'bot-suggestions' : ''}`}>
                    {suggestions.map((suggestion, index) => (
                        <SuggestionButton
                            key={`${suggestion}-${index}-${timestamp.getTime()}`}
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