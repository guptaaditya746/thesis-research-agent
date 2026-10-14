/** MSW in Node (Vitest): the same handlers as the browser worker. */
import { setupServer } from "msw/node"

import { handlers } from "./handlers"

export const server = setupServer(...handlers)
