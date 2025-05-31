// src/components/MessageList/MessageList.tsx
import React, { useRef, useLayoutEffect } from 'react'; // Добавляем useLayoutEffect для лучшего скролла
import './MessageList.css';
import MessageItem from '../MessageItem/MessageItem';
import TypingIndicator from '../TypingIndicator/TypingIndicator';
// Убедись, что тип Message (или FrontendMessage) включает поле videos
// import type { Message } from '../../types'; // Если у тебя есть types.ts
import type { FrontendMessage as Message } from '../../App'; // Если тип определен в App.tsx

interface MessageListProps {
    messages: Message[]; // Этот тип Message ДОЛЖЕН включать опциональное поле videos
    isBotTyping: boolean;
    onSuggestionClick: (suggestionText: string) => void;
}

const MessageList: React.FC<MessageListProps> = ({ messages, isBotTyping, onSuggestionClick }) => {
    // Используем улучшенную логику скролла, которую обсуждали
    const chatMessagesContainerRef = useRef<HTMLDivElement>(null);
    const prevMessagesLengthRef = useRef(messages.length);
    const prevIsBotTypingRef = useRef(isBotTyping);

    useLayoutEffect(() => {
        const container = chatMessagesContainerRef.current;
        if (!container) return;

        const newMessagesAdded = messages.length > prevMessagesLengthRef.current;
        const typingIndicatorChanged = isBotTyping !== prevIsBotTypingRef.current;

        if (newMessagesAdded || typingIndicatorChanged) {
            const scrollThreshold = 150; 
            const isScrolledToBottom = container.scrollHeight - container.clientHeight <= container.scrollTop + scrollThreshold;

            if (isScrolledToBottom || newMessagesAdded) { 
                container.scrollTop = container.scrollHeight;
            }
        }
        prevMessagesLengthRef.current = messages.length;
        prevIsBotTypingRef.current = isBotTyping;
    }, [messages, isBotTyping]);

    return (
        <div className="chat-messages" ref={chatMessagesContainerRef}>
            {messages.map((msg) => (
                <MessageItem
                    key={msg.id}
                    sender={msg.sender}
                    text={msg.text}
                    timestamp={msg.timestamp}
                    suggestions={msg.suggestions}
                    videos={msg.videos} // <--- ВОТ ВАЖНОЕ ДОБАВЛЕНИЕ!
                    onSuggestionClick={onSuggestionClick}
                />
            ))}
            {isBotTyping && <TypingIndicator />}
            {/* Якорь messagesEndRef больше не нужен с новой логикой скролла */}
        </div>
    );
};

export default MessageList;