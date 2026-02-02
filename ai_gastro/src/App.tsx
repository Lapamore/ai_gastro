import { useState, useEffect, useCallback, useMemo } from 'react';
import { v4 as uuidv4 } from 'uuid';
import axios from 'axios';
import type { AxiosInstance } from 'axios';
import './App.css'; 

import ChatHeader from './components/ChatHeader/ChatHeader';
import MessageList from './components/MessageList/MessageList';
import ChatInput from './components/ChatInput/ChatInput';
import SidebarToggle from './components/SidebarToggle/SidebarToggle';
import Sidebar from './components/Sidebar/Sidebar';
import QuickActions from './components/QuickActions/QuickActions';
import SettingsModal from './components/SettingsModal/SettingsModal';
import DiaryModal from './components/DiaryModal/DiaryModal';

import type { 
    FrontendMessage, 
    UserPreferences, 
    SessionDisplayInfo, 
    BackendChatResponse, 
    BackendPersonalizedSuggestions,
    DailyProgress 
} from './types';

const API_BASE_URL = 'http://localhost:8000/api';

const initialUserPreferences: UserPreferences = {
    allergies: [], dietaryRestrictions: [], favoriteCuisines: [], dislikedCuisines: [],
    favoriteIngredients: [], dislikedIngredients: [], preferredDifficulty: null, availableTime: null,
    targetCalories: 2000
};

// Получаем или создаём user_id
const getUserId = (): string => {
    let userId = localStorage.getItem('gastro_user_id');
    if (!userId) {
        userId = uuidv4();
        localStorage.setItem('gastro_user_id', userId);
    }
    return userId;
};

function App() {
    const [messages, setMessages] = useState<FrontendMessage[]>([]);
    const [isBotTyping, setIsBotTyping] = useState<boolean>(false);
    const [userInput, setUserInput] = useState<string>('');
    const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(false);
    const [isSettingsModalOpen, setIsSettingsModalOpen] = useState<boolean>(false);
    const [isDiaryModalOpen, setIsDiaryModalOpen] = useState<boolean>(false);
    const [sessionsList, setSessionsList] = useState<SessionDisplayInfo[]>([]);
    const [isLoadingSuggestions, setIsLoadingSuggestions] = useState<boolean>(false);
    const [, setPreferencesLoaded] = useState<boolean>(false);
    
    // User ID хранится локально
    const userId = useMemo(() => getUserId(), []);
    
    // Axios instance с заголовком X-User-ID
    const api: AxiosInstance = useMemo(() => axios.create({
        baseURL: API_BASE_URL,
        headers: { 'X-User-ID': userId }
    }), [userId]);
    
    // Состояние дневника калорий
    const [dailyProgress, setDailyProgress] = useState<DailyProgress>({
        totalCalories: 0,
        targetCalories: 2000,
        protein: 0,
        fat: 0,
        carbs: 0
    });
    
    const [activeSessionId, setActiveSessionId] = useState<string | null>(() => localStorage.getItem('activeChatSessionId'));
    const [userPreferences, setUserPreferences] = useState<UserPreferences>(initialUserPreferences);

    // Загрузка предпочтений с бэкенда при старте
    const fetchPreferences = useCallback(async () => {
        try {
            const res = await api.get('/user/preferences');
            const loadedPrefs = {
                ...res.data,
                targetCalories: res.data.targetCalories || 2000
            };
            setUserPreferences(prev => ({
                ...prev,
                ...loadedPrefs
            }));
            // Сразу обновляем dailyProgress с загруженными целями
            setDailyProgress(prev => ({
                ...prev,
                targetCalories: loadedPrefs.targetCalories,
                targetProtein: res.data.targetProtein || prev.targetProtein,
                targetFat: res.data.targetFat || prev.targetFat,
                targetCarbs: res.data.targetCarbs || prev.targetCarbs
            }));
            setPreferencesLoaded(true);
        } catch (error) {
            console.error("Не удалось загрузить предпочтения с сервера");
            // Загружаем из localStorage как fallback
            const stored = localStorage.getItem('userGastronomicPreferences');
            if (stored) {
                try { setUserPreferences(JSON.parse(stored)); } catch {}
            }
            setPreferencesLoaded(true);
        }
    }, [api]);

    // Сохранение предпочтений на бэкенд
    const savePreferencesToBackend = useCallback(async (prefs: UserPreferences) => {
        try {
            await api.post('/user/preferences', prefs);
            localStorage.setItem('userGastronomicPreferences', JSON.stringify(prefs));
        } catch (error) {
            console.error("Не удалось сохранить предпочтения");
        }
    }, [api]);

    // Обработчик изменения предпочтений
    const handlePreferencesChange = useCallback((newPrefs: UserPreferences) => {
        setUserPreferences(newPrefs);
        savePreferencesToBackend(newPrefs);
        // Обновляем targetCalories в dailyProgress
        setDailyProgress(prev => ({ ...prev, targetCalories: newPrefs.targetCalories || 2000 }));
    }, [savePreferencesToBackend]);

    // Загрузка прогресса калорий из БД
    const fetchDailyProgress = useCallback(async () => {
        try {
            const res = await api.get('/diary/daily-summary');
            setDailyProgress(prev => ({
                ...res.data,
                targetCalories: prev.targetCalories || userPreferences.targetCalories || 2000
            }));
        } catch (error) {
            console.error("Не удалось загрузить прогресс калорий");
        }
    }, [api, userPreferences.targetCalories]);

    const fetchSessions = useCallback(async () => {
        try {
            const res = await api.get('/sessions');
            setSessionsList(res.data.map((s: any) => ({
                ...s, 
                updated_at: new Date(s.updated_at)
            })).sort((a: any, b: any) => b.updated_at.getTime() - a.updated_at.getTime()));
        } catch {}
    }, [api]);

    // Инициализация при старте
    useEffect(() => { 
        fetchPreferences();
        fetchSessions(); 
        fetchDailyProgress();
    }, [fetchPreferences, fetchSessions, fetchDailyProgress]);

    useEffect(() => {
        if (activeSessionId) localStorage.setItem('activeChatSessionId', activeSessionId);
        else localStorage.removeItem('activeChatSessionId');
    }, [activeSessionId]);

    useEffect(() => {
        const loadInitialData = async () => {
            if (activeSessionId) {
                setIsBotTyping(true);
                try {
                    const res = await api.get(`/sessions/${activeSessionId}/history`);
                    const normalizedHistory = res.data.map((msg: any) => ({
                        ...msg,
                        id: uuidv4(),
                        sender: msg.sender === 'assistant' ? 'bot' : 'user',
                        timestamp: new Date(msg.timestamp)
                    }));
                    setMessages(normalizedHistory);
                } catch { setActiveSessionId(null); } finally { setIsBotTyping(false); }
            } else {
                setMessages([{ 
                    id: uuidv4(), 
                    text: "Привет! Я Гастро-Помощник! 🍽️ Чем могу помочь? Я также могу записывать твои калории!", 
                    sender: 'bot', 
                    timestamp: new Date(), 
                    suggestions: ["Что на ужин?", "Запиши: я съел яблоко"] 
                }]);
            }
        };
        loadInitialData();
    }, [activeSessionId, api]);

    const handleSendMessage = async (text: string) => {
        if (!text.trim()) return;
        setMessages(prev => [...prev, { id: uuidv4(), text, sender: 'user', timestamp: new Date() }]);
        setUserInput(''); 
        setIsBotTyping(true);

        try {
            const res = await api.post<BackendChatResponse>('/chat', { 
                prompt: text, 
                session_id: activeSessionId, 
                preferences: userPreferences 
            });

            if (!activeSessionId) { 
                setActiveSessionId(res.data.session_id); 
                fetchSessions(); 
            }

            let botText = res.data.reply;

            // Если бэкенд вернул обновлённые данные дневника — применяем их сразу
            if (res.data.diary_updated) {
                setDailyProgress(prev => ({
                    ...res.data.diary_updated!.summary,
                    targetCalories: prev.targetCalories
                }));
            }

            setMessages(prev => [...prev, { 
                id: uuidv4(), 
                text: botText, 
                sender: 'bot', 
                timestamp: new Date(), 
                videos: res.data.videos 
            }]);
        } catch {
            setMessages(prev => [...prev, { id: uuidv4(), text: "Ошибка связи с шефом...", sender: 'bot', timestamp: new Date() }]);
        } finally { 
            setIsBotTyping(false); 
        }
    };

    const fetchPersonalizedSuggestions = async () => {
        if (isLoadingSuggestions) return;
        setIsLoadingSuggestions(true);
        try {
            const res = await api.post<BackendPersonalizedSuggestions>('/suggestions', {
                session_id: activeSessionId, preferences: userPreferences
            });
            if (res.data.suggestions.length > 0) {
                const combinedText = "Вот несколько идей для тебя:\n" + res.data.suggestions.join('\n');
                setMessages(prev => [...prev, { id: uuidv4(), text: combinedText, sender: 'bot', timestamp: new Date() }]);
            }
        } catch {
            // Ошибка получения персонализированных предложений
        } finally { setIsLoadingSuggestions(false); }
    };

    return (
        <div className="chat-app-wrapper">
            <SidebarToggle onClick={() => setIsSidebarOpen(!isSidebarOpen)} isOpen={isSidebarOpen} />
            <button className="settings-toggle-button top-right-button" onClick={() => setIsSettingsModalOpen(true)}>⚙️</button>
            <button className="diary-toggle-button top-right-button" onClick={() => setIsDiaryModalOpen(true)}>📔</button>
            
            <Sidebar 
                isOpen={isSidebarOpen} 
                sessions={sessionsList} 
                activeSessionId={activeSessionId} 
                isLoadingSuggestions={isLoadingSuggestions}
                dailyProgress={dailyProgress} // Передаем данные калорий
                onSelectSession={id => { setActiveSessionId(id); setIsSidebarOpen(false); }}
                onNewChat={() => { setActiveSessionId(null); setIsSidebarOpen(false); }}
                onDeleteSession={async id => { 
                    await api.delete(`/sessions/${id}`); 
                    fetchSessions(); 
                    if(activeSessionId === id) setActiveSessionId(null); 
                }}
                onFetchSuggestions={fetchPersonalizedSuggestions}
            />

            <div className={`chat-app-container ${isSidebarOpen ? 'shifted' : ''}`}>
                <ChatHeader onClearChat={() => {
                    if (activeSessionId && window.confirm("Удалить этот диалог?")) {
                        api.delete(`/sessions/${activeSessionId}`).then(() => setActiveSessionId(null));
                    }
                }} />
                <MessageList messages={messages} isBotTyping={isBotTyping} onSuggestionClick={handleSendMessage} />
                <ChatInput userInput={userInput} setUserInput={setUserInput} onSendMessage={handleSendMessage} isBotTyping={isBotTyping} />
                <QuickActions onActionClick={handleSendMessage} />
            </div>

            <SettingsModal isOpen={isSettingsModalOpen} onClose={() => setIsSettingsModalOpen(false)} preferences={userPreferences} onPreferencesChange={handlePreferencesChange} />
            <DiaryModal 
                isOpen={isDiaryModalOpen} 
                onClose={() => setIsDiaryModalOpen(false)} 
                dailyProgress={dailyProgress}
                onProgressUpdate={setDailyProgress}
                api={api}
                preferences={userPreferences}
                onPreferencesChange={handlePreferencesChange}
            />
        </div>
    );
}

export default App;