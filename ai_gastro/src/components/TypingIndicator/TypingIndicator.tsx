import React from 'react';
import './TypingIndicator.css';

const TypingIndicator: React.FC = () => {
    return (
        <div className="message-wrapper bot">
            <div className="message bot typing-indicator">
                <div className="avatar">🤖</div>
                <div className="message-content">
                    <div className="dot"></div>
                    <div className="dot"></div>
                    <div className="dot"></div>
                </div>
            </div>
        </div>
    );
};

export default TypingIndicator;