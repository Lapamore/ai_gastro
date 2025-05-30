// src/App.tsx
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { v4 as uuidv4 } from 'uuid';
import axios from 'axios';
import './App.css'; 

// Импорт компонентов
import ChatHeader from './components/ChatHeader/ChatHeader';
import MessageList from './components/MessageList/MessageList';
import ChatInput from './components/ChatInput/ChatInput';
import SidebarToggle from './components/SidebarToggle/SidebarToggle'; // Предполагаем, что он стилизуется и позиционируется сам
import QuickActions from './components/QuickActions/QuickActions';
import SettingsModal from './components/SettingsModal/SettingsModal'; // Импортируем модальное окно

// Типы для фронтенда
export interface FrontendMessage {
    id: string; 
    text: string;
    sender: 'user' | 'bot';
    suggestions?: string[];
    timestamp: Date; 
}

interface BackendSessionMetadata { 
    id: string;
    title: string;
    updated_at: string; 
}

interface SessionDisplayInfo {
    id: string;
    title: string;
    updated_at: Date; 
}

export interface UserPreferences { // Экспортируем для использования в SettingsModal
    allergies: string[];
    dietaryRestrictions: string[];
    favoriteCuisines: string[];
    dislikedCuisines: string[];
    favoriteIngredients: string[];
    dislikedIngredients: string[];
    preferredDifficulty: 'легко' | 'средне' | 'сложно' | null;
    availableTime: '15 мин' | '30 мин' | '1 час' | '>1 часа' | null;
}

const initialUserPreferences: UserPreferences = {
    allergies: [],
    dietaryRestrictions: [],
    favoriteCuisines: [],
    dislikedCuisines: [],
    favoriteIngredients: [],
    dislikedIngredients: [],
    preferredDifficulty: null,
    availableTime: null,
};

const API_BASE_URL = 'http://localhost:8000/api';

function App() {
    const [messages, setMessages] = useState<FrontendMessage[]>([]);
    const [isBotTyping, setIsBotTyping] = useState<boolean>(false);
    const [userInput, setUserInput] = useState<string>('');
    const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(false);
    const [isSettingsModalOpen, setIsSettingsModalOpen] = useState<boolean>(false);
    
    const [sessionsList, setSessionsList] = useState<SessionDisplayInfo[]>([]);
    const [activeSessionId, setActiveSessionId] = useState<string | null>(() => {
        return localStorage.getItem('activeChatSessionId');
    });
    const [userPreferences, setUserPreferences] = useState<UserPreferences>(() => {
        const storedPrefs = localStorage.getItem('userGastronomicPreferences');
        if (storedPrefs) {
            try { return JSON.parse(storedPrefs); } catch (e) { return initialUserPreferences; }
        }
        return initialUserPreferences;
    });

    const initialGreetingSentRef = useRef(false);

    // Эффект для блокировки скролла body
    useEffect(() => {
        if (isSettingsModalOpen || isSidebarOpen) {
            document.body.style.overflow = 'hidden';
        } else {
            document.body.style.overflow = 'auto';
        }
        return () => { // Очистка при размонтировании компонента
            document.body.style.overflow = 'auto';
        };
    }, [isSettingsModalOpen, isSidebarOpen]);

    useEffect(() => {
        if (activeSessionId) localStorage.setItem('activeChatSessionId', activeSessionId);
        else localStorage.removeItem('activeChatSessionId');
    }, [activeSessionId]);

    useEffect(() => {
        localStorage.setItem('userGastronomicPreferences', JSON.stringify(userPreferences));
    }, [userPreferences]);

    const addMessage = useCallback((text: string, sender: 'user' | 'bot', suggestions: string[] = [], id?: string) => {
        const displayId = id || uuidv4();
        setMessages(prev => [...prev, { id: displayId, text, sender, suggestions, timestamp: new Date() }]);
    }, []);

    const fetchSessions = useCallback(async (newlyCreatedSessionIdToSelect?: string) => {
        try {
            const response = await axios.get<BackendSessionMetadata[]>(`${API_BASE_URL}/sessions`);
            const fetchedSessions = response.data.map(s => ({...s, updated_at: new Date(s.updated_at)}))
                .sort((a,b) => b.updated_at.getTime() - a.updated_at.getTime()); 
            setSessionsList(fetchedSessions);
        } catch (error) { console.error("Error fetching sessions:", error); }
    }, []);

    useEffect(() => { fetchSessions(); }, [fetchSessions]);

    useEffect(() => {
        const loadActiveSessionOrGreet = async () => {
            if (activeSessionId) {
                initialGreetingSentRef.current = true; 
                setIsBotTyping(true); setMessages([]); 
                try {
                    const response = await axios.get<Array<{sender: string, text: string, timestamp: string}>>(
                        `${API_BASE_URL}/sessions/${activeSessionId}/history`);
                    setMessages(response.data.map(msg => ({
                        id: uuidv4(), text: msg.text, sender: msg.sender === 'assistant' ? 'bot' : 'user',
                        timestamp: new Date(msg.timestamp)
                    })));
                } catch (error) {
                    addMessage("Не удалось загрузить историю чата.", 'bot');
                    setActiveSessionId(null); 
                } finally { setIsBotTyping(false); }
            } else {
                if (!initialGreetingSentRef.current && messages.length === 0) { 
                    addMessage("Привет! Я Гастро-Помощник с AI! 🍽️ Чем могу помочь?", 'bot', ["Что на ужин?", "Легкий десерт"]);
                    initialGreetingSentRef.current = true; 
                }
            }
        };
        loadActiveSessionOrGreet();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [activeSessionId]); 

    useEffect(() => {
        if (!activeSessionId && messages.length === 0) initialGreetingSentRef.current = false;
    }, [activeSessionId, messages.length]);

    const handleSendMessage = async (textFromInputOrSuggestion: string) => {
        if (!textFromInputOrSuggestion.trim()) return;
        const userText = textFromInputOrSuggestion;
        addMessage(userText, 'user'); setUserInput(''); setIsBotTyping(true);
        const currentSessionIdForRequest = activeSessionId; 

        try {
            const response = await axios.post(`${API_BASE_URL}/chat`, {
                prompt: userText,
                session_id: currentSessionIdForRequest,
                preferences: userPreferences 
            });

            const botReply: string = response.data.reply;
            const returnedSessionId: string = response.data.session_id;

            if (!currentSessionIdForRequest && returnedSessionId) { 
                setActiveSessionId(returnedSessionId); 
                await fetchSessions(returnedSessionId); 
            } else if (currentSessionIdForRequest && returnedSessionId === currentSessionIdForRequest) {
                setSessionsList(prev => prev.map(s => s.id === currentSessionIdForRequest ? {...s, updated_at: new Date()} : s)
                    .sort((a,b) => b.updated_at.getTime() - a.updated_at.getTime()));
            }
            
            let suggestionsForBotReply: string[] = []; /* ... логика suggestions ... */
            addMessage(botReply, 'bot', suggestionsForBotReply);
        } catch (error: unknown) { 
            let errMsg = "Ошибка AI."; 
            if (axios.isAxiosError(error)) {
                if (error.response) {
                    const responseData = error.response.data as any; 
                    errMsg = responseData?.detail || responseData?.error || `Ошибка сервера: ${error.response.status}`;
                } else if (error.request) { errMsg = "Не удалось связаться с сервером."; } 
                else { errMsg = "Ошибка при отправке запроса."; }
            } else if (error instanceof Error) { errMsg = error.message; }
            addMessage(errMsg, 'bot');
        } finally { setIsBotTyping(false); }
    };

    const handleSelectSession = (id: string) => { if (id !== activeSessionId) setActiveSessionId(id); setIsSidebarOpen(false); };
    const handleNewChat = () => { if (activeSessionId || messages.length > 0) { setActiveSessionId(null); setMessages([]); initialGreetingSentRef.current = false; } setIsSidebarOpen(false); };
    const handleDeleteSession = async (id: string | null) => {
        if (!id) { handleNewChat(); return; }
        try {
            await axios.delete(`${API_BASE_URL}/sessions/${id}`);
            setSessionsList(prev => prev.filter(s => s.id !== id));
            if (activeSessionId === id) handleNewChat();
        } catch (error) { addMessage(`Не удалось удалить диалог.`, 'bot'); }
    };
    const toggleSidebar = () => setIsSidebarOpen(p => !p);
    const handlePreferencesChange = (newPrefs: UserPreferences) => setUserPreferences(newPrefs);
    const formatDate = (d: Date) => !d || isNaN(d.getTime()) ? "недавно" : d.toLocaleString('ru-RU', {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});

    return (
        <div className="chat-app-wrapper">
            {/* Кнопки управления интерфейсом */}
            <SidebarToggle onClick={toggleSidebar} isOpen={isSidebarOpen} />
            <button 
                className="settings-toggle-button top-right-button" 
                onClick={() => setIsSettingsModalOpen(true)}
                title="Настройки пользователя"
            >
                ⚙️
            </button>
            
            <div className={`sidebar-panel ${isSidebarOpen ? 'open' : ''}`}>
                <h2>Диалоги</h2>
                <button onClick={handleNewChat} className="sidebar-action-button new-chat-button"> + Новый чат </button>
                <div className="sessions-list">
                    {sessionsList.map(s => (
                        <div key={s.id} className={`session-item ${s.id===activeSessionId?'active':''}`} onClick={()=>handleSelectSession(s.id)} title={s.title}>
                            <span className="session-title">{s.title}</span>
                            <div className="session-meta">
                                <span className="session-timestamp">{formatDate(s.updated_at)}</span>
                                <button className="delete-session-button" title={`Удалить "${s.title}"`}
                                    onClick={e=>{e.stopPropagation(); if(window.confirm(`Удалить "${s.title}"?`)) handleDeleteSession(s.id);}}>🗑️</button>
                            </div>
                        </div>
                    ))}
                    {sessionsList.length === 0 && <p className="no-sessions-message">Нет диалогов.</p>}
                </div>
            </div>

            <div className={`chat-app-container`}> {/* Класс shifted может быть не нужен, если кнопки fixed */}
                <ChatHeader onClearChat={() => handleDeleteSession(activeSessionId)} />
                <MessageList messages={messages} isBotTyping={isBotTyping} onSuggestionClick={handleSendMessage} />
                <ChatInput userInput={userInput} setUserInput={setUserInput} onSendMessage={handleSendMessage} isBotTyping={isBotTyping} />
                <QuickActions onActionClick={handleSendMessage} />
            </div>

            <SettingsModal
                isOpen={isSettingsModalOpen}
                onClose={() => setIsSettingsModalOpen(false)}
                preferences={userPreferences}
                onPreferencesChange={handlePreferencesChange}
            />
            <button 
                className="settings-toggle-button top-right-button" // <--- Добавлен класс
                onClick={() => setIsSettingsModalOpen(true)}
                title="Настройки пользователя"
            >
                ⚙️
            </button>
        </div>
    );
}

export default App;