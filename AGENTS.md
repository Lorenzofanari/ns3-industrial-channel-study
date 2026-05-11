# AGENTS.md

Guidance for agents working in this standalone project.

- Keep this project independent from the parent repository's scheduler code.
- Use ns-3 for simulation.  Python scripts may orchestrate runs, parse CSV/JSON,
  validate trends and generate plots.
- Do not smooth, delete or hide anomalous results.
- If PLR/PER trends are not physically meaningful, flag the configuration and
  inspect the channel, PHY, MAC, traffic and metric extraction path.
- Keep all experimental parameters in `configs/`; C++ may contain only safe
  defaults and command-line plumbing.
- Treat `quadriga_raytraced` as external trace replay.  Synthetic traces are
  allowed only as documented placeholders and must not be used for final
  scientific claims.
- Preserve reproducibility metadata in every row: seed, ns-3 version, git hash
  when available, scenario, channel, PHY/MAC, payload, distance, jammer and
  simulation time.

