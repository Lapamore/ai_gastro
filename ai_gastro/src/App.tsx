import { useState, useEffect, useCallback, useRef } from 'react';
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
interface BackendVideoResult {
    title: string;
    video_id: string;
    thumbnail_url?: string;
    channel_title?: string;
}

export interface FrontendMessage {
    id: string; 
    text: string;
    sender: 'user' | 'bot';
    suggestions?: string[];
    timestamp: Date; 
    videos?: BackendVideoResult[]; // Поле для видео уже есть - отлично!
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

interface BackendChatResponse { 
    reply: string;
    session_id: string;
    videos?: BackendVideoResult[]; 
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
            try { return JSON.parse(storedPrefs); } catch { return initialUserPreferences; }
        }
        return initialUserPreferences;
    });
    const [isLoadingSuggestions, setIsLoadingSuggestions] = useState<boolean>(false);
    const isInitialMountRef = useRef(true);

    useEffect(() => {
        if (activeSessionId) localStorage.setItem('activeChatSessionId', activeSessionId);
        else localStorage.removeItem('activeChatSessionId');
    }, [activeSessionId]);

    useEffect(() => {
        localStorage.setItem('userGastronomicPreferences', JSON.stringify(userPreferences));
    }, [userPreferences]);

    const fetchSessions = useCallback(async () => {
        try {
            const response = await axios.get<BackendSessionMetadata[]>(`${API_BASE_URL}/sessions`);
            const fetchedSessions = response.data.map(s => ({...s, updated_at: new Date(s.updated_at)}))
                .sort((a,b) => b.updated_at.getTime() - a.updated_at.getTime()); 
            setSessionsList(fetchedSessions);
        } catch {}
    }, []);

    useEffect(() => { fetchSessions(); }, [fetchSessions]);

    // При старте/смене сессии — если нет истории, показываем приветствие
    useEffect(() => {
        const loadInitialData = async () => {
            if (activeSessionId) { 
                setIsBotTyping(true); 
                setMessages([]); 
                try {
                    const response = await axios.get<Array<Omit<FrontendMessage, 'id'|'videos'|'suggestions'|'timestamp'> & {timestamp: string}>>(`${API_BASE_URL}/sessions/${activeSessionId}/history`);
                    setMessages(response.data.map(msg => ({
                        ...msg, id: uuidv4(), sender: msg.sender as 'user' | 'bot',
                        timestamp: new Date(msg.timestamp)
                    })));
                } catch {
                    setMessages([{
                        id: uuidv4(),
                        text: "Не удалось загрузить историю этого чата.",
                        sender: 'bot',
                        suggestions: [],
                        timestamp: new Date(),
                    }]);
                    setActiveSessionId(null); 
                } finally { 
                    setIsBotTyping(false); 
                }
            } else { 
                if (messages.length === 0) { 
                    setIsBotTyping(true);
                    setMessages([{
                        id: uuidv4(),
                        text: "Привет! Я Гастро-Помощник с AI! 🍽️ Чем могу помочь?",
                        sender: 'bot',
                        suggestions: ["Что на ужин?", "Легкий десерт"],
                        timestamp: new Date(),
                    }]);
                    setIsBotTyping(false);
                }
            }
        };
        loadInitialData();
        if (isInitialMountRef.current) {
            isInitialMountRef.current = false;
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [activeSessionId]);

    // Главное: всегда добавляем сообщения через setMessages(prev => [...prev, ...])
    const handleSendMessage = async (textFromInputOrSuggestion: string) => {
        if (!textFromInputOrSuggestion.trim()) return;
        const userText = textFromInputOrSuggestion;
        setMessages(prevMsgs => [
            ...prevMsgs,
            {
                id: uuidv4(),
                text: userText,
                sender: 'user',
                suggestions: [],
                timestamp: new Date(),
            }
        ]);
        setUserInput('');
        setIsBotTyping(true);
        const currentSessionIdForRequest = activeSessionId;

        try {
            const response = await axios.post<BackendChatResponse>(`${API_BASE_URL}/chat`, {
                prompt: userText,
                session_id: currentSessionIdForRequest,
                preferences: userPreferences
            });

            const botReply: string = response.data.reply;
            const returnedSessionId: string = response.data.session_id;
            const foundVideos: BackendVideoResult[] | undefined = response.data.videos;

            if (!currentSessionIdForRequest && returnedSessionId) {
                setActiveSessionId(returnedSessionId);
                await fetchSessions();
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
            setMessages(prevMsgs => [
                ...prevMsgs,
                {
                    id: uuidv4(),
                    text: botReply,
                    sender: 'bot',
                    suggestions: suggestionsForBotReply,
                    timestamp: new Date(),
                    videos: foundVideos
                }
            ]);

        } catch (error: unknown) {
            let errMsg = "Ошибка AI.";
            if (axios.isAxiosError(error)) {
                if (error.response) {
                    const responseData = error.response.data as { detail?: string; error?: string };
                    errMsg = responseData?.detail || responseData?.error || `Ошибка сервера: ${error.response.status}`;
                } else if (error.request) { errMsg = "Не удалось связаться с сервером."; }
                else { errMsg = "Ошибка при отправке запроса."; }
            } else if (error instanceof Error) { errMsg = error.message; }
            setMessages(prevMsgs => [
                ...prevMsgs,
                {
                    id: uuidv4(),
                    text: errMsg,
                    sender: 'bot',
                    suggestions: [],
                    timestamp: new Date(),
                }
            ]);
        } finally { setIsBotTyping(false); }
    };

    const fetchPersonalizedSuggestions = async () => {
        if (isLoadingSuggestions) return;
        setIsLoadingSuggestions(true);
        setMessages(prevMsgs => [
            ...prevMsgs,
            {
                id: uuidv4(),
                text: "Подбираю персональные идеи для тебя...",
                sender: 'bot',
                suggestions: [],
                timestamp: new Date(),
            }
        ]);
        try {
            const response = await axios.post<BackendPersonalizedSuggestions>(`${API_BASE_URL}/suggestions`, {
                session_id: activeSessionId, preferences: userPreferences
            });
            if (response.data.suggestions && response.data.suggestions.length > 0) {
                let combinedSuggestionsText = "Вот несколько идей, которые могут тебе понравиться:\n";
                combinedSuggestionsText += response.data.suggestions
                                            .map(s => s.startsWith('- ') || s.startsWith('* ') || /^\d+\.\s/.test(s) ? s : `- ${s}`)
                                            .join('\n'); 
                setMessages(prevMsgs => [
                    ...prevMsgs,
                    {
                        id: uuidv4(),
                        text: combinedSuggestionsText,
                        sender: 'bot',
                        suggestions: [],
                        timestamp: new Date(),
                    }
                ]);
            } else {
                setMessages(prevMsgs => [
                    ...prevMsgs,
                    {
                        id: uuidv4(),
                        text: "Хм, пока не могу придумать ничего особенного...",
                        sender: 'bot',
                        suggestions: [],
                        timestamp: new Date(),
                    }
                ]);
            }
        } catch {
            setMessages(prevMsgs => [
                ...prevMsgs,
                {
                    id: uuidv4(),
                    text: "Не удалось подобрать персональные рекомендации.",
                    sender: 'bot',
                    suggestions: [],
                    timestamp: new Date(),
                }
            ]);
        } finally { setIsLoadingSuggestions(false); }
    };

    const handleSelectSession = (id: string) => { if (id !== activeSessionId) setActiveSessionId(id); setIsSidebarOpen(false); };
    
    const handleNewChat = () => { 
        setActiveSessionId(null); 
        setMessages([{
            id: uuidv4(),
            text: "Привет! Я Гастро-Помощник с AI! 🍽️ Чем могу помочь?",
            sender: 'bot',
            suggestions: ["Что на ужин?", "Легкий десерт"],
            timestamp: new Date(),
        }]);
        setIsSidebarOpen(false); 
    };
    
    const handleDeleteSession = async (id: string | null) => {
        if (!id) { handleNewChat(); return; }
        try {
            await axios.delete(`${API_BASE_URL}/sessions/${id}`);
            setSessionsList(prev => prev.filter(s => s.id !== id));
            if (activeSessionId === id) handleNewChat();
        } catch {
            setMessages(prevMsgs => [
                ...prevMsgs,
                {
                    id: uuidv4(),
                    text: `Не удалось удалить диалог.`,
                    sender: 'bot',
                    suggestions: [],
                    timestamp: new Date(),
                }
            ]);
        }
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
                <MessageList 
                    messages={messages}
                    isBotTyping={isBotTyping} 
                    onSuggestionClick={handleSendMessage} 
                />
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