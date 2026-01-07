import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './MessageItem.css';
import SuggestionButton from '../SuggestionButton/SuggestionButton';
import type { FrontendMessage, BackendVideoResult } from '../../types';

interface MessageItemProps {
    sender: FrontendMessage['sender'];
    text: FrontendMessage['text'];
    timestamp: FrontendMessage['timestamp'];
    suggestions?: FrontendMessage['suggestions'];
    videos?: BackendVideoResult[];
    onSuggestionClick: (suggestionText: string) => void;
}

const MessageItem: React.FC<MessageItemProps> = ({ 
    sender, 
    text, 
    timestamp, 
    suggestions, 
    videos, 
    onSuggestionClick 
}) => {
    const formatTime = (date: Date): string => {
        return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
    };

    // Бот это либо 'bot' (фронтенд), либо 'assistant' (бэкенд)
    const isBot = sender === 'bot' || (sender as string) === 'assistant';

    return (
        <div className={`message-wrapper ${isBot ? 'bot' : 'user'}`}>
            <div className={`message ${isBot ? 'bot' : 'user'}`}>
                <div className="avatar">
                    {isBot ? '🤖' : '🧑'} 
                </div>
                <div className="message-content">
                    <div className="sender-name">
                        {isBot ? 'Гастро-Помощник' : 'Ты'}
                    </div>

                    {isBot ? (
                        <div className="text markdown-content">
                           <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
                        </div>
                    ) : (
                        <div className="text"> 
                            {text} 
                        </div>
                    )}

                    {videos && videos.length > 0 && (
                        <div className="videos-container">
                            {videos.map(video => (
                                <div key={video.video_id} className="video-item">
                                    <a href={`https://www.youtube.com/watch?v=${video.video_id}`} target="_blank" rel="noopener noreferrer" className="video-link">
                                        {video.thumbnail_url && <img src={video.thumbnail_url} alt={video.title} className="video-thumbnail" />}
                                        <div className="video-info">
                                            <span className="video-title">{video.title}</span>
                                            {video.channel_title && <span className="video-channel">Канал: {video.channel_title}</span>}
                                        </div>
                                    </a>
                                </div>
                            ))}
                        </div>
                    )}

                    {timestamp && <div className="timestamp">{formatTime(timestamp)}</div>}
                </div>
            </div>
            {suggestions && suggestions.length > 0 && (
                <div className={`suggestion-buttons-container ${isBot ? 'bot-suggestions' : ''}`}>
                    {suggestions.map((suggestion, index) => (
                        <SuggestionButton
                            key={`${suggestion}-${index}`}
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