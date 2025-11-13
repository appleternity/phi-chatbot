export interface ChatMessage {
  id: string;
  sender: 'user' | 'bot';
  text: string;
  rating?: 'up' | 'down' | null;
  comment?: string | null;
}

export interface BotProfile {
  id: string;
  name: string;
  avatarColor: string;
  description: string;
  welcome_message: string;
}
