---
description: Run automated strategy optimization loop
---

// turbo-all

## Automated Strategy Optimization

This workflow runs the intelligent optimizer continuously.

### Steps:

1. Ensure Docker is running:
```bash
docker compose up -d
```

2. Run the optimization loop:
```bash
docker exec backtest-app python -m backend.optimizer.optimization_loop
```

3. Check results:
```bash
docker cp backtest-app:/app/optimization_results.json ./optimization_results.json
```
