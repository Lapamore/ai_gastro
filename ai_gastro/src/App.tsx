// src/App.tsx
import { useState, useEffect, useCallback } from 'react';
import { v4 as uuidv4 } from 'uuid';
import axios from 'axios';
import './App.css'; // Основные стили приложения

// Импорт компонентов
import ChatHeader from './components/ChatHeader/ChatHeader';
import MessageList from './components/MessageList/MessageList';
import ChatInput from './components/ChatInput/ChatInput';
import SidebarToggle from './components/SidebarToggle/SidebarToggle';
import QuickActions from './components/QuickActions/QuickActions';

// Типы для фронтенда
export interface FrontendMessage {
    id: string; 
    text: string;
    sender: 'user' | 'bot';
    suggestions?: string[];
    timestamp: Date; 
}

// Тип для сообщений, отправляемых на бэкенд в составе истории

// Тип ответа от бэкенда для списка сессий
interface BackendSessionMetadata { 
    id: string;
    title: string;
    updated_at: string; 
}

// Для отображения в списке на фронте
interface SessionDisplayInfo {
    id: string;
    title: string;
    updated_at: Date; // Храним как Date для сортировки/форматирования
}


const API_BASE_URL = 'http://localhost:8000/api'; // Базовый URL для API

function App() {
    const [messages, setMessages] = useState<FrontendMessage[]>([]);
    const [isBotTyping, setIsBotTyping] = useState<boolean>(false);
    const [userInput, setUserInput] = useState<string>('');
    const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(false);
    
    const [sessionsList, setSessionsList] = useState<SessionDisplayInfo[]>([]);
    const [activeSessionId, setActiveSessionId] = useState<string | null>(() => {
        const storedSessionId = localStorage.getItem('activeChatSessionId');
        console.log("Frontend (App Init): Active Session ID from localStorage:", storedSessionId);
        return storedSessionId;
    });

    // Сохранение activeSessionId в localStorage
    useEffect(() => {
        if (activeSessionId) {
            localStorage.setItem('activeChatSessionId', activeSessionId);
            console.log("Frontend (Session Update): Active Session ID saved to localStorage:", activeSessionId);
        } else {
            localStorage.removeItem('activeChatSessionId');
            console.log("Frontend (Session Update): Active Session ID removed from localStorage.");
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

    const fetchSessions = useCallback(async (newlyCreatedSessionId?: string) => {
        console.log("Frontend: Fetching sessions list...");
        try {
            const response = await axios.get<BackendSessionMetadata[]>(`${API_BASE_URL}/sessions`);
            const fetchedSessions = response.data.map(s => ({
                ...s,
                updated_at: new Date(s.updated_at) 
            })).sort((a,b) => b.updated_at.getTime() - a.updated_at.getTime()); 
            setSessionsList(fetchedSessions);
            console.log("Frontend: Sessions list fetched:", fetchedSessions);

            // Если была только что создана новая сессия, и ее еще нет в списке (из-за кэша или задержки),
            // и она еще не активна, то можно ее сделать активной.
            // Но setActiveSessionId(returnedSessionId) в handleSendMessage уже это делает.
            // Этот fetchSessions вызывается после, чтобы обновить список.
            if (newlyCreatedSessionId && !fetchedSessions.find(s => s.id === newlyCreatedSessionId)) {
                 console.warn(`Frontend: Newly created session ${newlyCreatedSessionId} not immediately in fetched list. List might be stale or it's the very first one.`);
            }

        } catch (error) {
            console.error("Frontend: Error fetching sessions list:", error);
        }
    }, []);

    // Загрузка списка сессий при первом монтировании
    useEffect(() => {
        fetchSessions();
    }, [fetchSessions]);

    // Загрузка истории сообщений для активной сессии или приветствие для новой
    useEffect(() => {
        const loadActiveSessionOrGreet = async () => {
            if (activeSessionId) {
                console.log("Frontend (Effect): Active session ID present, fetching history for:", activeSessionId);
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
                    console.log(`Frontend (Effect): History for session ${activeSessionId} loaded:`, historyMessages.length, "messages");
                } catch (error) {
                    console.error(`Frontend (Effect): Error fetching history for session ${activeSessionId}:`, error);
                    addMessage("Не удалось загрузить историю этого чата. Пожалуйста, попробуйте начать новый чат.", 'bot');
                    setActiveSessionId(null); // Сбрасываем сессию, если история не загрузилась
                } finally {
                    setIsBotTyping(false);
                }
            } else {
                // Нет активной сессии (новый чат)
                if (messages.length === 0) { 
                    console.log("Frontend (Effect): No active session, showing initial greeting.");
                    const initialGreetingText = "Привет! Я Гастро-Помощник с AI! 🍽️ Чем могу помочь?";
                    addMessage(initialGreetingText, 'bot', ["Что на ужин?", "Легкий десерт"]);
                }
            }
        };
        loadActiveSessionOrGreet();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [activeSessionId]); // Зависимость только от activeSessionId (addMessage мемоизирован)

    const handleSendMessage = async (textFromInputOrSuggestion: string) => {
        if (!textFromInputOrSuggestion.trim()) return;

        const userText = textFromInputOrSuggestion;
        // Добавляем сообщение пользователя на фронт СРАЗУ
        const userMessageId = uuidv4(); // Генерируем ID здесь, чтобы передать в addMessage
        addMessage(userText, 'user', [], userMessageId); 
        setUserInput('');
        setIsBotTyping(true);
        
        const currentSessionIdForRequest = activeSessionId; // Сохраняем ID на момент запроса

        // ЯВНАЯ ТИПИЗАЦИЯ clientSideHistoryForContext
        // Добавляем текущее сообщение пользователя в историю, которую отправляем (если оно еще не в messages)
        // Но так как мы вызываем addMessage ПЕРЕД этим, оно уже будет в messages при следующем рендере,
        // но не в текущем значении messages здесь. Поэтому лучше его добавить явно.
        // Однако, бэкенд все равно грузит историю из БД, так что clientSideHistoryForContext больше для "свежести".
        // Если бэкенд полагается ТОЛЬКО на историю из БД, то clientSideHistoryForContext можно отправлять пустой.
        // Мы решили отправлять пустую, т.к. бэкенд грузит по sessionId.
        
        console.log("Frontend: Sending to backend. Session ID:", currentSessionIdForRequest, "Prompt:", userText);

        try {
            const response = await axios.post(`${API_BASE_URL}/chat`, {
                prompt: userText,
                conversation_history: [], // Отправляем пустую, бэкенд сам загрузит по sessionId
                session_id: currentSessionIdForRequest 
            });

            const botReply: string = response.data.reply;
            const returnedSessionId: string = response.data.session_id; // Бэкенд всегда возвращает session_id

            if (!currentSessionIdForRequest && returnedSessionId) { // Это был новый чат
                console.log("Frontend: New session created by backend, ID:", returnedSessionId);
                setActiveSessionId(returnedSessionId); // Устанавливаем как активную
                await fetchSessions(returnedSessionId); // Обновляем список сессий, передаем ID новой сессии
            } else if (currentSessionIdForRequest && returnedSessionId === currentSessionIdForRequest) {
                // Сессия продолжилась, обновим дату в списке сессий для корректной сортировки
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
            console.error("Frontend: Ошибка при отправке сообщения на бэкенд:", error);
            let errorMessage = "Ой, что-то пошло не так с моим AI-помощником. Пожалуйста, попробуйте еще раз.";
            if (axios.isAxiosError(error)) {
                if (error.response) {
                    const responseData = error.response.data as any; 
                    errorMessage = responseData?.detail || responseData?.error || `Ошибка сервера: ${error.response.status}`;
                } else if (error.request) {
                    errorMessage = "Не удалось связаться с сервером. Проверьте ваше интернет-соединение и что бэкенд запущен.";
                } else {
                    errorMessage = "Произошла ошибка при формировании запроса.";
                }
            } else if (error instanceof Error) {
                errorMessage = error.message;
            }
            addMessage(errorMessage, 'bot');
        } finally {
            setIsBotTyping(false);
        }
    };

    const handleSelectSession = (sessionIdToSelect: string) => {
        console.log("Frontend: Selecting session:", sessionIdToSelect);
        if (sessionIdToSelect !== activeSessionId) {
            setActiveSessionId(sessionIdToSelect);
        }
        setIsSidebarOpen(false);
    };

    const handleNewChat = () => {
        console.log("Frontend: Initiating new chat.");
        setActiveSessionId(null); 
        setMessages([]); // Очищаем сообщения, чтобы useEffect [activeSessionId] показал приветствие
        setIsSidebarOpen(false);
    };
    
    const toggleSidebar = () => setIsSidebarOpen(prev => !prev);

    const formatDateForDisplay = (date: Date): string => {
        if (!(date instanceof Date) || isNaN(date.getTime())) { // Проверка на валидность даты
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
                <button 
                    onClick={handleNewChat} 
                    className="sidebar-action-button new-chat-button"
                >
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
                                <span className="session-timestamp">{formatDateForDisplay(session.updated_at)}</span>
                            </div>
                        ))
                    ) : (
                        <p className="no-sessions-message">Пока нет сохраненных диалогов.</p>
                    )}
                </div>
            </div>

            <div className={`chat-app-container ${isSidebarOpen ? 'shifted' : ''}`}>
                <ChatHeader onClearChat={handleNewChat} /> {/* Кнопка "Очистить чат" теперь начинает новый чат */}
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