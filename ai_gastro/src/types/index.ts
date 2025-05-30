export interface Recipe {
    id: string;
    name: string;
    cuisine: string;
    taste: string[] | string; // Может быть массивом или строкой
    type: string;
    description: string;
    tags: string[];
    difficulty?: string; // Необязательное поле
    time?: string;       // Необязательное поле
}

export interface Message {
    id: number | string; // id может быть числом или строкой (для UUID в будущем)
    text: string;
    sender: 'user' | 'bot';
    suggestions?: string[];
    timestamp: Date;
}

export interface UserPreferences {
    taste: string | null;
    cuisine: string | null;
    type: string | null;
}

// Определяем возможные этапы диалога
export type ConversationStage = 
    | 'initial' 
    | 'asking_taste' 
    | 'asking_cuisine' 
    | 'asking_type' 
    | 'showing_suggestions' 
    | 'recipe_details';

export interface ConversationState {
    stage: ConversationStage;
    preferences: UserPreferences;
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

export interface FrontendMessage { // Уже должен быть
    id: string; 
    text: string;
    sender: 'user' | 'bot';
    suggestions?: string[];
    timestamp: Date; 
}

// Новый тип для отображения сессии в списке
export interface SessionDisplayInfo {
    id: string;
    title: string;
    updated_at: string; // Получаем как строку ISO, можем форматировать на фронте
}

// Тип ответа от бэкенда для списка сессий
// (соответствует SessionMetadataListResponse на бэке)
export interface BackendSessionMetadata {
    id: string;
    title: string;
    updated_at: string; // Бэкенд вернет строку ISO
}