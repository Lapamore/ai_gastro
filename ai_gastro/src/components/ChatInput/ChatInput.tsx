import React from 'react';
import './ChatInput.css';

interface ChatInputProps {
    userInput: string;
    setUserInput: (value: string) => void;
    onSendMessage: (message: string) => void;
    isBotTyping: boolean;
}

const ChatInput: React.FC<ChatInputProps> = ({ userInput, setUserInput, onSendMessage, isBotTyping }) => {
    const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        if (userInput.trim()) {
            onSendMessage(userInput);
        }
    };

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setUserInput(e.target.value);
    };

    return (
        <form className="chat-input-area" onSubmit={handleSubmit}>
            <input
                type="text"
                value={userInput}
                onChange={handleChange}
                placeholder={isBotTyping ? "Помощник печатает..." : "Спроси меня о еде..."}
                disabled={isBotTyping}
                autoComplete="off"
            />
            <button type="submit" title="Отправить" disabled={!userInput.trim() || isBotTyping}>
                <svg viewBox="0 0 24 24" fill="currentColor">
                    <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"></path>
                </svg>
            </button>
        </form>
    );
};

export default ChatInput;