// --- Базовые сущности YouTube ---
export interface BackendVideoResult {
    title: string;
    video_id: string;
    thumbnail_url?: string;
    channel_title?: string;
}

// --- Сообщения для фронтенда ---
export interface FrontendMessage {
    id: string;
    text: string;
    sender: 'user' | 'bot';
    suggestions?: string[];
    timestamp: Date;
    videos?: BackendVideoResult[];
}

// --- Профиль пользователя (Настройки) ---
export interface UserPreferences {
    allergies: string[];
    dietaryRestrictions: string[];
    favoriteCuisines: string[];
    dislikedCuisines: string[];
    favoriteIngredients: string[];
    dislikedIngredients: string[];
    preferredDifficulty: 'легко' | 'средне' | 'сложно' | null;
    availableTime: '15 мин' | '30 мин' | '1 час' | '>1 часа' | null;
    
    // Новое: Физические параметры и цели
    targetCalories: number; // ВОТ ЭТО ПОЛЕ МЫ ДОБАВИЛИ
    weight?: number;
    height?: number;
    age?: number;
    gender?: 'male' | 'female';
    activityLevel?: 'low' | 'medium' | 'high';
    goal?: 'lose' | 'maintain' | 'gain';
}

// --- Данные дневника калорий ---
export interface DiaryEntry {
    id: string;
    name: string;
    calories: number;
    protein?: number;
    fat?: number;
    carbs?: number;
    mealType: 'breakfast' | 'lunch' | 'dinner' | 'snack';
    timestamp: Date;
}

// Для отправки на бэкенд (без id и timestamp)
export interface DiaryEntryInput {
    name: string;
    calories: number;
    protein: number;
    fat: number;
    carbs: number;
    mealType: 'breakfast' | 'lunch' | 'dinner' | 'snack';
}

// --- Статистика дня (Прогресс в сайдбаре) ---
export interface DailyProgress {
    totalCalories: number;
    targetCalories: number;
    protein: number;
    fat: number;
    carbs: number;
}

// --- Сессии (Диалоги в сайдбаре) ---
export interface SessionDisplayInfo {
    id: string;
    title: string;
    updated_at: Date;
}

// --- Ответы от API Бэкенда ---
export interface BackendChatResponse { 
    reply: string;
    session_id: string;
    videos?: BackendVideoResult[]; 
    // AI может вернуть данные для авто-записи в дневник
    extracted_food?: {
        name: string;
        calories: number;
        protein: number;
        fat: number;
        carbs: number;
    };
    // Обновлённые данные дневника после записи
    diary_updated?: {
        summary: {
            totalCalories: number;
            protein: number;
            fat: number;
            carbs: number;
        };
    };
}

export interface BackendPersonalizedSuggestions {
    suggestions: string[];
}

// --- Типы для работы с рецептами ---
export interface Recipe {
    id: string;
    name: string;
    cuisine: string;
    taste: string[] | string;
    type: string;
    description: string;
    tags: string[];
    difficulty?: string;
    time?: string;
}

// --- Состояние диалога ---
export type ConversationStage = 
    | 'initial' 
    | 'asking_taste' 
    | 'asking_cuisine' 
    | 'asking_type' 
    | 'showing_suggestions' 
    | 'recipe_details';

export interface ConversationState {
    stage: ConversationStage;
    preferences: {
        taste: string | null;
        cuisine: string | null;
        type: string | null;
    };
    suggestedRecipeIds: string[];
    currentRecipeId: string | null;
}

export interface BotServiceResponse {
    text: string;
    suggestions: string[];
    newState: ConversationState;
}

export interface RecipeDetailsResponse {
    text: string;
    suggestions: string[];
}