# deploy/reproducible-setup

- `deploy/setup.sh`: repeatable setup on a fresh Ubuntu 24.04 (g++-14, node 20, git-lfs, uv; clone / pull, LFS,
  router + frontend builds, every data file incl. street matrices and the RAPTOR timetable).
- `deploy/run.sh`: backend (+ router) on 127.0.0.1:8000 and the production frontend via `vite preview` on
  0.0.0.0:8080 proxying `/api`; `stop`; logs in `logs/`.
- Frontend: the API base defaults to the page origin in production builds too (was `http://localhost:8000`);
  `vite preview` gets the `/api` proxy and allows any host (RunPod proxy).
