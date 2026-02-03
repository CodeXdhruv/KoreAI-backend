# HabitCity Backend

AI-driven motivation adaptation backend using PPO reinforcement learning.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn app.main:app --reload --port 8000
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/decide-action` | Get AI recommendation |
| POST | `/update-state` | Track habit completion |
| GET | `/health` | Health check / warm-up |

## Model Files

Place in `models/` directory:
- `habit_city_ppo_v5.zip` - PPO model
- `habit_city_vecnorm_v5.pkl` - VecNormalize stats

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `false` | Enable debug logging |
| `DETERMINISTIC_INFERENCE` | `true` | Use deterministic policy |
