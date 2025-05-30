// src/App.tsx
import { useState, useEffect, useCallback, useRef } from 'react';
import { v4 as uuidv4 } from 'uuid';
import axios from 'axios';
import './App.css'; 

import ChatHeader from './components/ChatHeader/ChatHeader';
import MessageList from './components/MessageList/MessageList';
import ChatInput from './components/ChatInput/ChatInput';
import SidebarToggle from './components/SidebarToggle/SidebarToggle';
import QuickActions from './components/QuickActions/QuickActions';

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

const API_BASE_URL = 'http://localhost:8000/api';

function App() {
    const [messages, setMessages] = useState<FrontendMessage[]>([]);
    const [isBotTyping, setIsBotTyping] = useState<boolean>(false);
    const [userInput, setUserInput] = useState<string>('');
    const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(false);
    
    const [sessionsList, setSessionsList] = useState<SessionDisplayInfo[]>([]);
    const [activeSessionId, setActiveSessionId] = useState<string | null>(() => {
        return localStorage.getItem('activeChatSessionId');
    });

    const initialGreetingSentRef = useRef(false); // Ref для отслеживания приветствия

    useEffect(() => {
        if (activeSessionId) {
            localStorage.setItem('activeChatSessionId', activeSessionId);
        } else {
            localStorage.removeItem('activeChatSessionId');
        }
    }, [activeSessionId]);

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
            const fetchedSessions = response.data.map(s => ({
                ...s,
                updated_at: new Date(s.updated_at) 
            })).sort((a,b) => b.updated_at.getTime() - a.updated_at.getTime()); 
            setSessionsList(fetchedSessions);
        } catch (error) {
            console.error("Frontend: Error fetching sessions list:", error);
        }
    }, []);

    useEffect(() => {
        fetchSessions();
    }, [fetchSessions]);

    useEffect(() => {
        const loadActiveSessionOrGreet = async () => {
            if (activeSessionId) {
                initialGreetingSentRef.current = true; 
                setIsBotTyping(true);
                setMessages([]); 
                try {
                    const response = await axios.get<Array<{sender: string, text: string, timestamp: string}>>(
                        `${API_BASE_URL}/sessions/${activeSessionId}/history`
                    );
                    const historyMessages: FrontendMessage[] = response.data.map(msg => ({
                        id: uuidv4(), 
                        text: msg.text,
                        sender: msg.sender === 'assistant' ? 'bot' : 'user',
                        timestamp: new Date(msg.timestamp)
                    }));
                    setMessages(historyMessages);
                } catch (error) {
                    addMessage("Не удалось загрузить историю этого чата.", 'bot');
                    setActiveSessionId(null); 
                } finally {
                    setIsBotTyping(false);
                }
            } else {
                if (!initialGreetingSentRef.current && messages.length === 0) { 
                    const initialGreetingText = "Привет! Я Гастро-Помощник с AI! 🍽️ Чем могу помочь?";
                    addMessage(initialGreetingText, 'bot', ["Что на ужин?", "Легкий десерт"]);
                    initialGreetingSentRef.current = true; 
                }
            }
        };
        loadActiveSessionOrGreet();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [activeSessionId]); // Зависимость только от activeSessionId

    useEffect(() => {
        if (!activeSessionId && messages.length === 0) {
            initialGreetingSentRef.current = false;
        }
    }, [activeSessionId, messages.length]);


    const handleSendMessage = async (textFromInputOrSuggestion: string) => {
        if (!textFromInputOrSuggestion.trim()) return;
        const userText = textFromInputOrSuggestion;
        addMessage(userText, 'user');
        setUserInput('');
        setIsBotTyping(true);
        const currentSessionIdForRequest = activeSessionId; 

        try {
            const response = await axios.post(`${API_BASE_URL}/chat`, {
                prompt: userText,
                conversation_history: [], 
                session_id: currentSessionIdForRequest 
            });

            const botReply: string = response.data.reply;
            const returnedSessionId: string = response.data.session_id;

            if (!currentSessionIdForRequest && returnedSessionId) { 
                setActiveSessionId(returnedSessionId); 
                await fetchSessions(returnedSessionId); 
            } else if (currentSessionIdForRequest && returnedSessionId === currentSessionIdForRequest) {
                setSessionsList(prevSessions => 
                    prevSessions.map(s => 
                        s.id === currentSessionIdForRequest ? {...s, updated_at: new Date()} : s
                    ).sort((a,b) => b.updated_at.getTime() - a.updated_at.getTime())
                );
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
            let errorMessage = "Ой, что-то пошло не так с моим AI-помощником.";
            if (axios.isAxiosError(error)) {
                if (error.response) {
                    const responseData = error.response.data as any; 
                    errorMessage = responseData?.detail || responseData?.error || `Ошибка сервера: ${error.response.status}`;
                } else if (error.request) {
                    errorMessage = "Не удалось связаться с сервером.";
                } else { errorMessage = "Ошибка при отправке запроса."; }
            } else if (error instanceof Error) { errorMessage = error.message; }
            addMessage(errorMessage, 'bot');
        } finally {
            setIsBotTyping(false);
        }
    };

    const handleSelectSession = (sessionIdToSelect: string) => {
        if (sessionIdToSelect !== activeSessionId) {
            setActiveSessionId(sessionIdToSelect);
        }
        setIsSidebarOpen(false);
    };

    const handleNewChat = () => { 
        if (activeSessionId !== null || messages.length > 0) {
            setActiveSessionId(null); 
            setMessages([]); 
            initialGreetingSentRef.current = false; 
        }
        setIsSidebarOpen(false); 
    };
    
    const handleDeleteSession = async (sessionIdToDelete: string | null) => {
        if (!sessionIdToDelete) {
            handleNewChat(); 
            return;
        }
        try {
            await axios.delete(`${API_BASE_URL}/sessions/${sessionIdToDelete}`);
            setSessionsList(prevSessions => prevSessions.filter(s => s.id !== sessionIdToDelete));
            if (activeSessionId === sessionIdToDelete) {
                handleNewChat(); 
            }
        } catch (error) {
            addMessage(`Не удалось удалить диалог.`, 'bot');
        }
    };

    const toggleSidebar = () => setIsSidebarOpen(prev => !prev);

    const formatDateForDisplay = (date: Date): string => {
        if (!(date instanceof Date) || isNaN(date.getTime())) { 
            return "недавно";
        }
        return date.toLocaleString('ru-RU', { 
            month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
        });
    };

    return (
        <div className="chat-app-wrapper">
            <SidebarToggle onClick={toggleSidebar} isOpen={isSidebarOpen} />
            <div className={`sidebar-panel ${isSidebarOpen ? 'open' : ''}`}>
                <h2>Диалоги</h2>
                <button onClick={handleNewChat} className="sidebar-action-button new-chat-button">
                    + Новый чат
                </button>
                <div className="sessions-list">
                    {sessionsList.length > 0 ? (
                        sessionsList.map(session => (
                            <div 
                                key={session.id} 
                                className={`session-item ${session.id === activeSessionId ? 'active' : ''}`}
                                onClick={() => handleSelectSession(session.id)}
                                title={session.title}
                            >
                                <span className="session-title">{session.title}</span>
                                <div className="session-meta">
                                    <span className="session-timestamp">{formatDateForDisplay(session.updated_at)}</span>
                                    <button 
                                        className="delete-session-button" 
                                        title={`Удалить диалог "${session.title}"`}
                                        onClick={(e) => {
                                            e.stopPropagation(); 
                                            if (window.confirm(`Удалить диалог "${session.title}"?`)) {
                                                handleDeleteSession(session.id);
                                            }
                                        }}
                                    >
                                        🗑️
                                    </button>
                                </div>
                            </div>
                        ))
                    ) : (
                        <p className="no-sessions-message">Пока нет сохраненных диалогов.</p>
                    )}
                </div>
            </div>

            <div className={`chat-app-container ${isSidebarOpen ? 'shifted' : ''}`}>
                <ChatHeader 
                    onClearChat={() => handleDeleteSession(activeSessionId)} 
                />
                <MessageList 
                    messages={messages} 
                    isBotTyping={isBotTyping} 
                    onSuggestionClick={handleSendMessage} 
                />
                <ChatInput
                    userInput={userInput}
                    setUserInput={setUserInput}
                    onSendMessage={handleSendMessage}
                    isBotTyping={isBotTyping}
                />
                <QuickActions onActionClick={handleSendMessage} />
            </div>
        </div>
    );
}

export default App;