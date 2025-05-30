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

// Тип ответа от бэкенда для списка сессий
interface BackendSessionMetadata { 
    id: string;
    title: string;
    updated_at: string; // Бэкенд вернет строку ISO
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

    const fetchSessions = useCallback(async (newlyCreatedSessionIdToSelect?: string) => {
        console.log("Frontend: Fetching sessions list...");
        try {
            const response = await axios.get<BackendSessionMetadata[]>(`${API_BASE_URL}/sessions`);
            const fetchedSessions = response.data.map(s => ({
                ...s,
                updated_at: new Date(s.updated_at) 
            })).sort((a,b) => b.updated_at.getTime() - a.updated_at.getTime()); 
            setSessionsList(fetchedSessions);
            console.log("Frontend: Sessions list fetched:", fetchedSessions.length, "sessions");

            // Если был передан ID только что созданной сессии, и ее еще нет в activeSessionId,
            // и список сессий не пуст, можно сделать ее активной.
            // Однако, setActiveSessionId(returnedSessionId) в handleSendMessage уже должен это сделать.
            if (newlyCreatedSessionIdToSelect && activeSessionId !== newlyCreatedSessionIdToSelect) {
                const newSessionExists = fetchedSessions.some(s => s.id === newlyCreatedSessionIdToSelect);
                if (newSessionExists) {
                    console.log("Frontend: Newly created session found in list, ensuring it's active:", newlyCreatedSessionIdToSelect);
                    // setActiveSessionId(newlyCreatedSessionIdToSelect); // Это может вызвать лишний ререндер, если уже установлено
                } else {
                    console.warn(`Frontend: Newly created session ${newlyCreatedSessionIdToSelect} not in fetched list. Might be a race condition or list is stale.`);
                }
            } else if (!activeSessionId && fetchedSessions.length > 0 && !newlyCreatedSessionIdToSelect) {
                // Если нет активной сессии, но есть сессии в списке, можно выбрать самую последнюю
                // console.log("Frontend: No active session, selecting most recent from list:", fetchedSessions[0].id);
                // setActiveSessionId(fetchedSessions[0].id); // Опционально: автоматически выбирать последнюю
            }


        } catch (error) {
            console.error("Frontend: Error fetching sessions list:", error);
        }
    }, [activeSessionId]); // Добавляем activeSessionId в зависимости, чтобы правильно обработать случай с newlyCreatedSessionIdToSelect

    // Загрузка списка сессий при первом монтировании
    useEffect(() => {
        fetchSessions();
    }, [fetchSessions]);

    // Загрузка истории сообщений для активной сессии или приветствие для нового чата
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
                    addMessage("Не удалось загрузить историю этого чата. Возможно, сессия была удалена или произошла ошибка.", 'bot');
                    // Сбрасываем на новый чат, если активная сессия не загрузилась
                    setActiveSessionId(null); 
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
    }, [activeSessionId]); // Зависимость только от activeSessionId 

    const handleSendMessage = async (textFromInputOrSuggestion: string) => {
        if (!textFromInputOrSuggestion.trim()) return;

        const userText = textFromInputOrSuggestion;
        addMessage(userText, 'user');
        setUserInput('');
        setIsBotTyping(true);
        
        const currentSessionIdForRequest = activeSessionId; 

        console.log("Frontend: Sending to backend. Session ID:", currentSessionIdForRequest, "Prompt:", userText);

        try {
            const response = await axios.post(`${API_BASE_URL}/chat`, {
                prompt: userText,
                conversation_history: [], 
                session_id: currentSessionIdForRequest 
            });

            const botReply: string = response.data.reply;
            const returnedSessionId: string = response.data.session_id;

            if (!currentSessionIdForRequest && returnedSessionId) { 
                console.log("Frontend: New session created by backend, ID:", returnedSessionId);
                setActiveSessionId(returnedSessionId); 
                await fetchSessions(returnedSessionId); // Обновляем список сессий, передаем ID новой сессии
            } else if (currentSessionIdForRequest && returnedSessionId === currentSessionIdForRequest) {
                // Сессия продолжилась, обновим дату в списке сессий для корректной сортировки
                // Это полезно, если fetchSessions не вызывается сразу или не содержит самую свежую дату
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

    const handleNewChat = () => { // Эта функция теперь для кнопки "+ Новый чат"
        console.log("Frontend: Initiating new chat (clearing active session).");
        if (activeSessionId !== null) { // Только если была активная сессия
            setActiveSessionId(null); 
        }
        setMessages([]); // Очищаем текущие сообщения на фронте
                          // useEffect [activeSessionId] покажет приветствие для нового чата
        setIsSidebarOpen(false); 
    };
    
    const handleDeleteSession = async (sessionIdToDelete: string | null) => {
        if (!sessionIdToDelete) {
            // Если нет активной сессии, то кнопка "удалить" в хедере должна просто начать новый чат
            handleNewChat();
            return;
        }

        console.log("Frontend: Attempting to delete session:", sessionIdToDelete);
        try {
            await axios.delete(`${API_BASE_URL}/sessions/${sessionIdToDelete}`);
            console.log("Frontend: Session deleted successfully on backend:", sessionIdToDelete);
            
            setSessionsList(prevSessions => prevSessions.filter(s => s.id !== sessionIdToDelete));
            
            if (activeSessionId === sessionIdToDelete) {
                // Если удалили активную сессию, переключаемся на "новый чат"
                handleNewChat(); 
            }
            // Если удалили неактивную сессию, активная сессия не меняется
            // и список сессий обновился.

        } catch (error) {
            console.error("Frontend: Error deleting session:", sessionIdToDelete, error);
            addMessage(`Не удалось удалить диалог.`, 'bot');
        }
        // После удаления сессии из списка, сайдбар может остаться открытым,
        // если пользователь захочет выбрать другую сессию или создать новую.
        // setIsSidebarOpen(false); // Опционально
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
                                <div className="session-meta">
                                    <span className="session-timestamp">{formatDateForDisplay(session.updated_at)}</span>
                                    <button 
                                        className="delete-session-button" 
                                        title={`Удалить диалог "${session.title}"`}
                                        onClick={(e) => {
                                            e.stopPropagation(); 
                                            if (window.confirm(`Удалить диалог "${session.title}"? Это действие необратимо.`)) {
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
                {/* Кнопка "Закрыть панель" убрана, как ты просил */}
            </div>

            <div className={`chat-app-container ${isSidebarOpen ? 'shifted' : ''}`}>
                <ChatHeader 
                    onClearChat={() => handleDeleteSession(activeSessionId)} // Кнопка в хедере УДАЛЯЕТ ТЕКУЩУЮ АКТИВНУЮ сессию
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