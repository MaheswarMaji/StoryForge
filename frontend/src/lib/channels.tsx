import { createContext, useContext, useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiGet } from './api';
interface Channel { id: string; name: string; [key: string]: unknown }
interface Channels { channels: Channel[]; selected: string; setSelected: (value: string) => void }
export const ChannelContext = createContext<Channels>({ channels: [], selected: 'all', setSelected: () => {} });
export const useChannels = () => useContext(ChannelContext);
export function ChannelProvider({ children }: { children: ReactNode }) {
  const [selected, setSelected] = useState(localStorage.getItem('sf_channel') || 'all');
  const { data: channels = [] } = useQuery({ queryKey: ['channels'], queryFn: () => apiGet<Channel[]>('/api/channels') });
  return <ChannelContext.Provider value={{ channels, selected, setSelected: value => { setSelected(value); localStorage.setItem('sf_channel', value); } }}>{children}</ChannelContext.Provider>;
}