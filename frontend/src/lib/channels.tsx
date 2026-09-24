import { createContext, useContext, useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiGet } from './api';
// Mirrors backend.models.Channel; omitted voice values default server-side to local:auto.
interface Channel {
  id: string; key: string; name: string; description: string; language: string; tone: string;
  voice: string; voice_speed: number; music_mood: string; music_volume: number;
  safety_level: string; style_prefix: string; cta_text: string; is_kids: boolean;
  expressive_voice: boolean; mode: string; video_type: string; created_at: string;
}
interface Channels { channels: Channel[]; selected: string; setSelected: (value: string) => void }
export const ChannelContext = createContext<Channels>({ channels: [], selected: 'all', setSelected: () => {} });
export const useChannels = () => useContext(ChannelContext);
export function ChannelProvider({ children }: { children: ReactNode }) {
  const [selected, setSelected] = useState(localStorage.getItem('sf_channel') || 'all');
  const { data: channels = [] } = useQuery({ queryKey: ['channels'], queryFn: () => apiGet<Channel[]>('/api/channels') });
  return <ChannelContext.Provider value={{ channels, selected, setSelected: value => { setSelected(value); localStorage.setItem('sf_channel', value); } }}>{children}</ChannelContext.Provider>;
}