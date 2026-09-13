import "@/App.css";
import { Toaster } from "@/components/ui/sonner";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { ChannelProvider } from "@/lib/api";
import Layout from "@/components/Layout";
import AuthCallback from "@/components/AuthCallback";
import LoginPage from "@/pages/LoginPage";
import DashboardPage from "@/pages/DashboardPage";
import UploadPage from "@/pages/UploadPage";
import LibraryPage from "@/pages/LibraryPage";
import StoryDetailPage from "@/pages/StoryDetailPage";
import ChannelsPage from "@/pages/ChannelsPage";
import SettingsPage from "@/pages/SettingsPage";
import SocialPage from "@/pages/SocialPage";
import NewsDeskPage from "@/pages/NewsDeskPage";
import CreatePage from "@/pages/CreatePage";
import AdminPage from "@/pages/AdminPage";

function AppRouter() {
  const location = useLocation();
  // Process the OAuth session_id BEFORE anything else (avoids the provider race condition)
  if (location.hash?.includes("session_id=")) return <AuthCallback />;
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<Layout />}>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/create" element={<CreatePage />} />
        <Route path="/stories" element={<LibraryPage />} />
        <Route path="/stories/:id" element={<StoryDetailPage />} />
        <Route path="/news" element={<NewsDeskPage />} />
        <Route path="/social" element={<SocialPage />} />
        <Route path="/channels" element={<ChannelsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/admin" element={<AdminPage />} />
      </Route>
    </Routes>
  );
}

function App() {
  return (
    <ChannelProvider>
      <BrowserRouter>
        <AppRouter />
      </BrowserRouter>
      <Toaster position="bottom-right" richColors closeButton theme="dark" />
    </ChannelProvider>
  );
}

export default App;
