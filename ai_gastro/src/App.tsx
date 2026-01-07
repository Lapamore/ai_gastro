import { useState, useEffect, useCallback } from 'react';
import { v4 as uuidv4 } from 'uuid';
import axios from 'axios';
import './App.css'; 

import ChatHeader from './components/ChatHeader/ChatHeader';
import MessageList from './components/MessageList/MessageList';
import ChatInput from './components/ChatInput/ChatInput';
import SidebarToggle from './components/SidebarToggle/SidebarToggle';
import Sidebar from './components/Sidebar/Sidebar';
import QuickActions from './components/QuickActions/QuickActions';
import SettingsModal from './components/SettingsModal/SettingsModal';

import type { 
    FrontendMessage, 
    UserPreferences, 
    SessionDisplayInfo, 
    BackendChatResponse, 
    BackendPersonalizedSuggestions 
} from './types';

const API_BASE_URL = 'http://localhost:8000/api';

const initialUserPreferences: UserPreferences = {
    allergies: [], dietaryRestrictions: [], favoriteCuisines: [], dislikedCuisines: [],
    favoriteIngredients: [], dislikedIngredients: [], preferredDifficulty: null, availableTime: null,
};

function App() {
    const [messages, setMessages] = useState<FrontendMessage[]>([]);
    const [isBotTyping, setIsBotTyping] = useState<boolean>(false);
    const [userInput, setUserInput] = useState<string>('');
    const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(false);
    const [isSettingsModalOpen, setIsSettingsModalOpen] = useState<boolean>(false);
    const [sessionsList, setSessionsList] = useState<SessionDisplayInfo[]>([]);
    const [isLoadingSuggestions, setIsLoadingSuggestions] = useState<boolean>(false);
    
    const [activeSessionId, setActiveSessionId] = useState<string | null>(() => localStorage.getItem('activeChatSessionId'));
    const [userPreferences, setUserPreferences] = useState<UserPreferences>(() => {
        const stored = localStorage.getItem('userGastronomicPreferences');
        try { return stored ? JSON.parse(stored) : initialUserPreferences; } catch { return initialUserPreferences; }
    });

    const fetchSessions = useCallback(async () => {
        try {
            const res = await axios.get(`${API_BASE_URL}/sessions`);
            setSessionsList(res.data.map((s: any) => ({
                ...s, 
                updated_at: new Date(s.updated_at)
            })).sort((a: any, b: any) => b.updated_at.getTime() - a.updated_at.getTime()));
        } catch {}
    }, []);

    useEffect(() => { fetchSessions(); }, [fetchSessions]);

    useEffect(() => {
        if (activeSessionId) localStorage.setItem('activeChatSessionId', activeSessionId);
        else localStorage.removeItem('activeChatSessionId');
    }, [activeSessionId]);

    useEffect(() => {
        localStorage.setItem('userGastronomicPreferences', JSON.stringify(userPreferences));
    }, [userPreferences]);

    useEffect(() => {
        const loadInitialData = async () => {
            if (activeSessionId) {
                setIsBotTyping(true);
                try {
                    const res = await axios.get(`${API_BASE_URL}/sessions/${activeSessionId}/history`);
                    // ВАЖНО: Нормализуем sender из бэкенда ('assistant' -> 'bot')
                    const normalizedHistory = res.data.map((msg: any) => ({
                        ...msg,
                        id: uuidv4(),
                        sender: msg.sender === 'assistant' ? 'bot' : 'user',
                        timestamp: new Date(msg.timestamp)
                    }));
                    setMessages(normalizedHistory);
                } catch { 
                    setActiveSessionId(null); 
                } finally { 
                    setIsBotTyping(false); 
                }
            } else {
                setMessages([{ 
                    id: uuidv4(), 
                    text: "Привет! Я Гастро-Помощник! 🍽️ Чем могу помочь?", 
                    sender: 'bot', 
                    timestamp: new Date(), 
                    suggestions: ["Что на ужин?", "Легкий десерт"] 
                }]);
            }
        };
        loadInitialData();
    }, [activeSessionId]);

    const handleSendMessage = async (text: string) => {
        if (!text.trim()) return;
        
        setMessages(prev => [...prev, { id: uuidv4(), text, sender: 'user', timestamp: new Date() }]);
        setUserInput(''); 
        setIsBotTyping(true);

        try {
            const res = await axios.post<BackendChatResponse>(`${API_BASE_URL}/chat`, { 
                prompt: text, 
                session_id: activeSessionId, 
                preferences: userPreferences 
            });

            if (!activeSessionId) { 
                setActiveSessionId(res.data.session_id); 
                fetchSessions(); 
            }

            setMessages(prev => [...prev, { 
                id: uuidv4(), 
                text: res.data.reply, 
                sender: 'bot', // Здесь мы жестко ставим 'bot' для нового сообщения
                timestamp: new Date(), 
                videos: res.data.videos 
            }]);
        } catch {
            // обработка ошибки
        } finally { 
            setIsBotTyping(false); 
        }
    };

    const fetchPersonalizedSuggestions = async () => {
        if (isLoadingSuggestions) return;
        setIsLoadingSuggestions(true);
        try {
            const res = await axios.post<BackendPersonalizedSuggestions>(`${API_BASE_URL}/suggestions`, {
                session_id: activeSessionId, preferences: userPreferences
            });
            if (res.data.suggestions.length > 0) {
                const combinedText = "Вот несколько идей для тебя:\n" + res.data.suggestions.join('\n');
                setMessages(prev => [...prev, { id: uuidv4(), text: combinedText, sender: 'bot', timestamp: new Date() }]);
            }
        } catch {
        } finally { setIsLoadingSuggestions(false); }
    };

    return (
        <div className="chat-app-wrapper">
            <SidebarToggle onClick={() => setIsSidebarOpen(!isSidebarOpen)} isOpen={isSidebarOpen} />
            <button className="settings-toggle-button top-right-button" onClick={() => setIsSettingsModalOpen(true)}>⚙️</button>
            
            <Sidebar 
                isOpen={isSidebarOpen} sessions={sessionsList} activeSessionId={activeSessionId} isLoadingSuggestions={isLoadingSuggestions}
                onSelectSession={id => { setActiveSessionId(id); setIsSidebarOpen(false); }}
                onNewChat={() => { setActiveSessionId(null); setIsSidebarOpen(false); }}
                onDeleteSession={async id => { 
                    await axios.delete(`${API_BASE_URL}/sessions/${id}`); 
                    fetchSessions(); 
                    if(activeSessionId === id) setActiveSessionId(null); 
                }}
                onFetchSuggestions={fetchPersonalizedSuggestions}
            />

            <div className="chat-app-container">
                <ChatHeader onClearChat={() => {
                    if (activeSessionId && window.confirm("Удалить этот диалог?")) {
                        axios.delete(`${API_BASE_URL}/sessions/${activeSessionId}`).then(() => setActiveSessionId(null));
                    }
                }} />
                <MessageList messages={messages} isBotTyping={isBotTyping} onSuggestionClick={handleSendMessage} />
                <ChatInput userInput={userInput} setUserInput={setUserInput} onSendMessage={handleSendMessage} isBotTyping={isBotTyping} />
                <QuickActions onActionClick={handleSendMessage} />
            </div>

            <SettingsModal isOpen={isSettingsModalOpen} onClose={() => setIsSettingsModalOpen(false)} preferences={userPreferences} onPreferencesChange={setUserPreferences} />
        </div>
    );
}

export default App;