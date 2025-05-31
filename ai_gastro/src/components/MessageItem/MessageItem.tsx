// src/components/MessageItem/MessageItem.tsx
import React from 'react';
import ReactMarkdown from 'react-markdown'; // Оставляем основной импорт
import type { Options as ReactMarkdownOptions } from 'react-markdown'; // <--- ИМПОРТИРУЕМ ТИП ОТДЕЛЬНО
import remarkGfm from 'remark-gfm';
import './MessageItem.css';
import SuggestionButton from '../SuggestionButton/SuggestionButton';

// Импортируем типы, которые приходят в пропсах
import type { FrontendMessage } from '../../App'; // Предполагая, что FrontendMessage определен в App.tsx

// Тип для видео, если он передается в FrontendMessage (совпадает с BackendVideoResult из App.tsx)
interface VideoResult {
    title: string;
    video_id: string;
    thumbnail_url?: string;
    channel_title?: string;
}

// Обновляем пропсы, чтобы они соответствовали FrontendMessage из App.tsx
interface MessageItemProps {
    sender: FrontendMessage['sender'];
    text: FrontendMessage['text'];
    timestamp: FrontendMessage['timestamp'];
    suggestions?: FrontendMessage['suggestions'];
    videos?: VideoResult[]; // <--- Добавляем проп videos
    onSuggestionClick: (suggestionText: string) => void;
}

const MessageItem: React.FC<MessageItemProps> = ({ 
    sender, 
    text, 
    timestamp, 
    suggestions, 
    videos, // <--- Получаем videos из пропсов
    onSuggestionClick 
}) => {
    const formatTime = (date: Date): string => {
        return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
    };

    const markdownProps: ReactMarkdownOptions = {
        remarkPlugins: [remarkGfm],
        components: {
            a: ({node, ...props}) => <a {...props} target="_blank" rel="noopener noreferrer" />,
        },
    };

    return (
        <div className={`message-wrapper ${sender}`}>
            <div className={`message ${sender}`}>
                <div className="avatar">
                    {/* Используем эмодзи повара для пользователя, как было ранее задумано */}
                    {sender === 'bot' ? '🤖' : '🧑‍🍳'} 
                </div>
                <div className="message-content">
                    <div className="sender-name">
                        {sender === 'bot' ? 'Гастро-Помощник' : 'Ты'}
                    </div>

                    {/* Основной текст сообщения */}
                    {sender === 'bot' ? (
                        <div className="text markdown-content">
                           <ReactMarkdown {...markdownProps}>{text}</ReactMarkdown>
                        </div>
                    ) : (
                        <div className="text"> 
                            {text} 
                        </div>
                    )}

                    {/* Блок для отображения видео, если они есть */}
                    {videos && videos.length > 0 && (
                        <div className="videos-container">
                            {/* Можно добавить заголовок, если видео идут после основного текста */}
                            {/* {text && <h4 className="videos-header">Видео по теме:</h4>} */}
                            {videos.map(video => (
                                <div key={video.video_id} className="video-item">
                                    <a 
                                        href={`https://www.youtube.com/watch?v=${video.video_id}`} 
                                        target="_blank" 
                                        rel="noopener noreferrer" 
                                        className="video-link"
                                    >
                                        {video.thumbnail_url && 
                                            <img 
                                                src={video.thumbnail_url} 
                                                alt={video.title} 
                                                className="video-thumbnail"
                                            />
                                        }
                                        <div className="video-info">
                                            <span className="video-title">{video.title}</span>
                                            {video.channel_title && 
                                                <span className="video-channel">Канал: {video.channel_title}</span>
                                            }
                                        </div>
                                    </a>
                                    {/* 
                                    // Вариант с встроенным плеером:
                                    <iframe 
                                        width="100%" // или фиксированная ширина, например 300
                                        height="180" // или фиксированная высота
                                        src={`https://www.youtube.com/embed/${video.video_id}`}
                                        title={video.title}
                                        frameBorder="0" 
                                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" 
                                        allowFullScreen
                                        className="video-embed"
                                    ></iframe> 
                                    */}
                                </div>
                            ))}
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