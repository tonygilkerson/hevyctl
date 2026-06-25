# Heavy CLI

My Heavy CLI

Of interest

* [hevycli](https://github.com/obay/hevycli)

## Setup

```sh
# Install UV
brew install uv

# tell it not to recreate git or overwrite your existing README:
uv init --app --no-readme --vcs none .

# Create .envrc.private for direnv to work
# Get API KEY from https://hevy.com 
printf 'export API_KEY="REDACTED"\n' > .envrc.private

# this will create your .venv
uv sync

# Verify
uv run hevyctl --version
```

## Dist

Python wheel

```sh
source .venv/bin/activate # if not done already

# build for dist
uv build
```

## As a User

To use `hevyctl`, as opposed to develop `hevyctl` then do the following:

```sh
# In a new terminal window not in this venv
python3 -m pip install ~/github/tonygilkerson/hevyctl/dist/hevyctl-0.1.0-py3-none-any.whl --user --break-system-packages

# Verify
hevyctl --version
```

## Usage Examples

```sh
# Fetch workouts
uv run hevyctl workout ls --pageSize 5

# Fetch routines
uv run hevyctl routine ls --pageSize 5
```
