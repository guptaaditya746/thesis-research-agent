import { createContext, useContext } from "react"

export interface ChatState {
  open: boolean
  setOpen: (open: boolean) => void
  /** the run the chat is scoped to (the run page in view), or null */
  runId: string | null
}

export const ChatContext = createContext<ChatState>({ open: false, setOpen: () => {}, runId: null })

export const useChat = () => useContext(ChatContext)
