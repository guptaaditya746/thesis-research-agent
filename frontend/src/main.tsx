/**
 * Entry point. With VITE_MOCK=1 (`npm run dev:mock`) the MSW service worker answers /api from
 * src/mocks before the app renders; otherwise requests go to the backend (Vite proxies /api in
 * dev; in production the backend serves this build at /).
 */
import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { createBrowserRouter, RouterProvider } from "react-router"

import { createQueryClient } from "@/api/client"
import { AppProviders } from "@/app/providers"
import { routes } from "@/app/routes"

import "./index.css"

async function start() {
  if (import.meta.env.VITE_MOCK === "1") {
    const { worker } = await import("./mocks/browser")
    await worker.start({ onUnhandledRequest: "bypass", quiet: true })
  }
  const router = createBrowserRouter(routes)
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <AppProviders client={createQueryClient()}>
        <RouterProvider router={router} />
      </AppProviders>
    </StrictMode>,
  )
}

void start()
