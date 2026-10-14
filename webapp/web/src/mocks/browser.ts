/** MSW in the browser (`npm run dev:mock`): the service worker answers /api from the fixtures. */
import { setupWorker } from "msw/browser"

import { handlers } from "./handlers"

export const worker = setupWorker(...handlers)
