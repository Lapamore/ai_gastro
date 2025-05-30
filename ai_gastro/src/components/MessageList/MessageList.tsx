import React, { useEffect, useRef } from 'react';
import './MessageList.css';
import MessageItem from '../MessageItem/MessageItem';
import TypingIndicator from '../TypingIndicator/TypingIndicator';
import type { Message } from '../../types';

interface MessageListProps {
    messages: Message[];
    isBotTyping: boolean;
    onSuggestionClick: (suggestionText: string) => void;
}

const MessageList: React.FC<MessageListProps> = ({ messages, isBotTyping, onSuggestionClick }) => {
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(scrollToBottom, [messages, isBotTyping]);

    return (
        <div className="chat-messages">
            {messages.map((msg) => (
                <MessageItem
                    key={msg.id}
                    sender={msg.sender}
                    text={msg.text}
                    timestamp={msg.timestamp}
                    suggestions={msg.suggestions}
                    onSuggestionClick={onSuggestionClick}
                />
            ))}
            {isBotTyping && <TypingIndicator />}
            <div ref={messagesEndRef} />
        </div>
    );
};

export default MessageList;