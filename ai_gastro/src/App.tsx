// src/App.tsx
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { v4 as uuidv4 } from 'uuid';
import axios from 'axios';
import './App.css'; 

import ChatHeader from './components/ChatHeader/ChatHeader';
import MessageList from './components/MessageList/MessageList';
import ChatInput from './components/ChatInput/ChatInput';
import SidebarToggle from './components/SidebarToggle/SidebarToggle';
import QuickActions from './components/QuickActions/QuickActions';
import SettingsModal from './components/SettingsModal/SettingsModal';

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

export interface UserPreferences {
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

interface BackendPersonalizedSuggestions {
    suggestions: string[];
}

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
    const [isLoadingSuggestions, setIsLoadingSuggestions] = useState<boolean>(false);
    const isInitialMountRef = useRef(true); // Для отслеживания первого монтирования/запуска приложения

    useEffect(() => {
        if (activeSessionId) localStorage.setItem('activeChatSessionId', activeSessionId);
        else localStorage.removeItem('activeChatSessionId');
    }, [activeSessionId]);

    useEffect(() => {
        localStorage.setItem('userGastronomicPreferences', JSON.stringify(userPreferences));
    }, [userPreferences]);

    const addMessage = useCallback((text: string, sender: 'user' | 'bot', suggestions: string[] = [], id?: string) => {
        const displayId = id || uuidv4();
        const newMessage: FrontendMessage = { 
            id: displayId, 
            text, 
            sender, 
            suggestions, 
            timestamp: new Date() 
        };
        setMessages(prev => [...prev, newMessage]);
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

    // Загрузка истории для активной сессии ИЛИ начальное приветствие/предложения
    useEffect(() => {
        const loadInitialData = async () => {
            if (activeSessionId) { // Есть активная сессия - грузим историю
                setIsBotTyping(true); 
                setMessages([]); 
                try {
                    const response = await axios.get<Array<{sender: string, text: string, timestamp: string}>>(
                        `${API_BASE_URL}/sessions/${activeSessionId}/history`);
                    setMessages(response.data.map(msg => ({
                        id: uuidv4(), text: msg.text, sender: msg.sender === 'assistant' ? 'bot' : 'user',
                        timestamp: new Date(msg.timestamp)
                    })));
                } catch (error) {
                    addMessage("Не удалось загрузить историю этого чата.", 'bot');
                    setActiveSessionId(null); // Сбрасываем, если ошибка
                } finally { 
                    setIsBotTyping(false); 
                }
            } else { // Нет активной сессии (новый чат ИЛИ самый первый запуск)
                if (messages.length === 0) { // Показываем что-то, только если чат реально пуст
                    setIsBotTyping(true);
                    if (isInitialMountRef.current) { // Это самый первый рендер приложения (или после полного обновления)
                        const hasPreviousDataForSuggestions = sessionsList.length > 0 || Object.values(userPreferences).some(val => Array.isArray(val) ? val.length > 0 : val !== null);
                        if (hasPreviousDataForSuggestions) {
                            console.log("Frontend (Initial App Load with Data): Fetching personalized suggestions.");
                            try {
                                const response = await axios.post<BackendPersonalizedSuggestions>(`${API_BASE_URL}/suggestions`, {
                                    session_id: null, preferences: userPreferences
                                });
                                if (response.data.suggestions?.length) {
                                    addMessage("Привет! 👋 С возвращением! У меня есть несколько идей для тебя:", 'bot');
                                    response.data.suggestions.forEach(suggestion => addMessage(suggestion, 'bot'));
                                } else {
                                    addMessage("Привет! Я Гастро-Помощник! Чем могу помочь сегодня?", 'bot', ["Что на ужин?"]);
                                }
                            } catch (error) {
                                addMessage("Привет! Гастро-Помощник к твоим услугам!", 'bot');
                            }
                        } else { // Первый запуск, но нет данных для персонализации
                            console.log("Frontend (Initial App Load without Data): Showing standard greeting.");
                            addMessage("Привет! Я Гастро-Помощник с AI! 🍽️ Чем могу помочь?", 'bot', ["Что на ужин?", "Легкий десерт"]);
                        }
                    } else { // Не первый рендер, и activeSessionId === null (значит, это результат handleNewChat)
                        console.log("Frontend (New Chat Initialized): Showing standard greeting.");
                        addMessage("Привет! Я Гастро-Помощник с AI! 🍽️ Чем могу помочь?", 'bot', ["Что на ужин?", "Легкий десерт"]);
                    }
                    setIsBotTyping(false);
                }
            }
        };
        
        loadInitialData();
        // Устанавливаем isInitialMountRef в false ПОСЛЕ первого выполнения этого эффекта,
        // чтобы при последующих сбросах activeSessionId (через handleNewChat) он уже был false.
        // Но делаем это только один раз.
        if (isInitialMountRef.current) {
            isInitialMountRef.current = false;
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [activeSessionId]); // Основная зависимость - activeSessionId. sessionsList и userPreferences используются только на initialMount.


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
            
            let suggestionsForBotReply: string[] = [];
            const lowerBotReply = botReply.toLowerCase();
            if (lowerBotReply.includes("рецепт") || lowerBotReply.includes("предлагаю") || lowerBotReply.includes("вариант")) {
                suggestionsForBotReply = ["Это интересно!", "Другой рецепт?", "Спасибо!"];
            } else if (lowerBotReply.includes("какие у тебя предпочтения") || lowerBotReply.includes("что бы ты хотел")) {
                suggestionsForBotReply = ["Сладкое 🍰", "Основное блюдо 🍲", "Острое 🌶️", "Что-то легкое 🥗"];
            }
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
    
    const fetchPersonalizedSuggestions = async () => {
        if (isLoadingSuggestions) return;
        setIsLoadingSuggestions(true);
        addMessage("Подбираю персональные идеи для тебя...", 'bot');
        try {
            const response = await axios.post<BackendPersonalizedSuggestions>(`${API_BASE_URL}/suggestions`, {
                session_id: activeSessionId, preferences: userPreferences
            });
            if (response.data.suggestions && response.data.suggestions.length > 0) {
                let combinedSuggestionsText = "Вот несколько идей, которые могут тебе понравиться:\n\n";
                // Предполагаем, что AI уже вернул строки в формате "1. Предложение..." или "- Предложение..."
                combinedSuggestionsText += response.data.suggestions.join('\n'); 
                addMessage(combinedSuggestionsText, 'bot'); // Все предложения в одном сообщении
            } else {
                addMessage("Хм, пока не могу придумать ничего особенного...", 'bot');
            }
        } catch (error) { addMessage("Не удалось подобрать персональные рекомендации.", 'bot');} 
        finally { setIsLoadingSuggestions(false); }
    };

    const handleSelectSession = (id: string) => { if (id !== activeSessionId) setActiveSessionId(id); setIsSidebarOpen(false); };
    
    const handleNewChat = () => { 
        console.log("Frontend: Initiating new chat explicitly.");
        // isInitialMountRef.current остается false, так как это не первый монтирование компонента App
        // но мы хотим, чтобы useEffect [activeSessionId] показал стандартное приветствие.
        // Он это сделает, так как activeSessionId станет null, а messages очистятся.
        if (activeSessionId !== null || messages.length > 0) {
            setActiveSessionId(null); 
            setMessages([]); 
        }
        setIsSidebarOpen(false); 
    };
    
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
                <button 
                    onClick={fetchPersonalizedSuggestions} 
                    disabled={isLoadingSuggestions}
                    className="sidebar-action-button suggestions-button"
                >
                    {isLoadingSuggestions ? "Думаю..." : "💡 Идеи для меня"}
                </button>
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

            <div className={`chat-app-container`}>
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
        </div>
    );
}

export default App;