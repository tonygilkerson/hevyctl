# Heavy CLI

My Heavy CLI

## Setup

```sh
# Install UV
brew install uv

# tell it not to recreate git or overwrite your existing README:
uv init --app --no-package --no-readme --vcs none .

# this will create your .venv
uv sync

# Create .envrc.private for direnv to work
# Get API KEY from https://hevy.com 
printf 'export API_KEY="REDACTED"\n' > .envrc.private

# Activate the environment
source .venv/bin/activate

# Verify
uv run python main.py
```