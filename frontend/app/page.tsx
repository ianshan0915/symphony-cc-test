"use client";

import { ChatInterface } from "@/components/chat/ChatInterface";
import { ProtectedRoute } from "@/components/ProtectedRoute";

export default function Home() {
  return (
    <ProtectedRoute>
      <main className="h-screen w-screen overflow-hidden">
        <ChatInterface />
      </main>
    </ProtectedRoute>
  );
}
