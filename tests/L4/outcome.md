# L4 outcome

A 5,000-token streamed request was routed to SUB replica 2 on port 8004. The process group was verified to be owned by this session and received SIGTERM while one request was active. The client received a successful response (922 completion tokens, 4,140 content characters, 7.55 s total); no retry line was found in the LiteLLM log. The vLLM process exited cleanly after the request, the supervisor waited 30 s before restarting it, and the watchdog recorded the backend healthy again 2:30 after restart. The external health monitor observed HTTP 200 at 2:46.
