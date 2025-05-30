import React from 'react';
import './SidebarToggle.css';

interface SidebarToggleProps {
    onClick: () => void;
    isOpen: boolean; // Добавим, чтобы менять иконку, если нужно
}

const SidebarToggle: React.FC<SidebarToggleProps> = ({ onClick, isOpen }) => {
    return (
        <button 
            className="sidebar-toggle-button" 
            onClick={onClick} 
            title={isOpen ? "Закрыть боковую панель" : "Открыть боковую панель"}
            aria-expanded={isOpen}
        >
            {isOpen ? '✕' : '☰'}
        </button>
    );
};

export default SidebarToggle;