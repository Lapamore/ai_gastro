import React from 'react';
import './SuggestionButton.css';

interface SuggestionButtonProps {
    text: string;
    onClick: () => void;
}

const SuggestionButton: React.FC<SuggestionButtonProps> = ({ text, onClick }) => {
    return (
        <button className="suggestion-button" onClick={onClick}>
            {text}
        </button>
    );
};

export default SuggestionButton;