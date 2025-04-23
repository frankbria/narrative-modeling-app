# Shared Package

This package contains shared models and utilities used across the Narrative Modeling Application.

## Structure

- `models/` - Contains shared data models
- `database.py` - Database utilities and configurations

## Installation

This package is installed as a local dependency in development mode using Poetry:

```bash
poetry install
```

## Usage

Import shared models and utilities as needed:

```python
from shared.models import YourModel
from shared.database import YourDatabaseUtil
``` 