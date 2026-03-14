"use client";

import {
  createContext,
  useContext,
  useMemo,
  type ReactNode,
} from "react";
import { Client } from "@langchain/langgraph-sdk";
import { config } from "@/lib/config";

/**
 * Context that holds the configured LangGraph SDK {@link Client}.
 *
 * The client is created once and shared across the component tree so every
 * hook / component that needs to talk to the backend uses the same instance
 * (and therefore the same base URL, headers, etc.).
 */
const ClientContext = createContext<Client | null>(null);

/** Props for {@link ClientProvider}. */
export interface ClientProviderProps {
  children: ReactNode;
  /** Override the API URL (useful for tests / Storybook). */
  apiUrl?: string;
}

/**
 * Provides a LangGraph SDK `Client` instance to the React tree.
 *
 * Wrap your application (or a subtree) with this provider so that
 * downstream consumers can call `useLangGraphClient()` to access
 * the pre-configured client.
 *
 * @example
 * ```tsx
 * // app/layout.tsx
 * <ClientProvider>
 *   {children}
 * </ClientProvider>
 * ```
 */
export function ClientProvider({ children, apiUrl }: ClientProviderProps) {
  const client = useMemo(
    () =>
      new Client({
        apiUrl: apiUrl ?? config.apiUrl,
      }),
    [apiUrl],
  );

  return (
    <ClientContext.Provider value={client}>{children}</ClientContext.Provider>
  );
}

/**
 * Return the LangGraph SDK client from the nearest {@link ClientProvider}.
 *
 * @throws If called outside a `<ClientProvider>`.
 */
export function useLangGraphClient(): Client {
  const client = useContext(ClientContext);
  if (!client) {
    throw new Error(
      "useLangGraphClient must be used within a <ClientProvider>. " +
        "Wrap your component tree with <ClientProvider> in your root layout.",
    );
  }
  return client;
}
