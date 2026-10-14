/**
 * The chat's transport to POST /api/chat (AI SDK v5), one per app. `body` is read when a
 * message is sent, so a message carries the run id of the page it was sent from (`run_id`;
 * pydantic-ai's VercelAIAdapter request model allows extra fields).
 */
import { DefaultChatTransport, type UIMessage } from "ai"

import { urls } from "@/api/client"

import { chatBody } from "./scope"

let transport: DefaultChatTransport<UIMessage> | null = null

export function chatTransport(): DefaultChatTransport<UIMessage> {
  transport ??= new DefaultChatTransport({ api: urls.chat(), body: chatBody })
  return transport
}
