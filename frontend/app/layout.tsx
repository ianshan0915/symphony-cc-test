import type { Metadata } from "next";
import { ClientProvider } from "@/providers/ClientProvider";
import "./globals.css";

export const metadata: Metadata = {
  title: "Symphony Chat",
  description: "Agentic chat platform powered by LangGraph",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">
        <ClientProvider>{children}</ClientProvider>
      </body>
    </html>
  );
}
