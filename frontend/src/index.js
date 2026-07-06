import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { FingerprintProvider } from "@fingerprint/react";
import "@/index.css";
import App from "@/App";
import { registerServiceWorker } from "@/registerServiceWorker";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      refetchOnWindowFocus: false,
    },
  },
});

const root = ReactDOM.createRoot(document.getElementById("root"));
const fingerprintApiKey = process.env.REACT_APP_FINGERPRINT_API_KEY;
const app = (
  <QueryClientProvider client={queryClient}>
    <App />
  </QueryClientProvider>
);

root.render(
  <React.StrictMode>
    {fingerprintApiKey ? (
      <FingerprintProvider apiKey={fingerprintApiKey}>
        {app}
      </FingerprintProvider>
    ) : app}
  </React.StrictMode>,
);

registerServiceWorker();
