import React from 'react';
import './QuickActions.css';

interface QuickActionsProps {
    onActionClick: (action: string) => void;
}

const QuickActions: React.FC<QuickActionsProps> = ({ onActionClick }) => {
    const actions = [
        { label: "🇮🇹 Итальянская", action: "хочу итальянскую кухню" },
        { label: "🍣 Азиатская", action: "посоветуй азиатскую кухню" },
        { label: "🍰 Десерт!", action: "хочу десерт" },
        { label: "🍲 Супчик", action: "посоветуй суп" },
    ];

    return (
        <div className="quick-actions-bar">
            {actions.map(item => (
                <button 
                    key={item.action} 
                    onClick={() => onActionClick(item.action)}
                    className="quick-action-button"
                    title={`Быстрый запрос: ${item.action}`}
                >
                    {item.label}
                </button>
            ))}
        </div>
    );
};

export default QuickActions;