# Continuous integration

`.github/workflows/ci.yml` runs on pull requests targeting `main` and pushes to
`main`. Its independent jobs run backend Ruff checks, backend pytest tests with
MongoDB 8 managed by Testcontainers, and Angular ESLint checks for TypeScript and
external/inline templates. A separate frontend test job runs Jasmine/Karma tests
once in headless Chrome using `npm run test:ci`.
Python is selected from `backend/.python-version`; frontend CI uses Node.js 22.
Dependencies are installed from `uv.lock` and `package-lock.json`.

Run the same checks locally:

```bash
cd backend
uv sync --locked
uv run ruff check .
# Requires a running Docker daemon; Testcontainers starts MongoDB automatically.
uv run pytest tests
cd ../frontend
npm ci
npm run lint -- --max-warnings=0
npm run test:ci
```

Frontend tests require Chrome (preinstalled on GitHub-hosted Ubuntu runners).
For local Chromium installations, set `CHROME_BIN` to the Chromium executable.
The initial tests cover the welcome route's user details and role filtering,
logout redirect, and unknown-route fallback using a mocked Keycloak client.

The session-scoped `mongo_container` fixture starts MongoDB on a dynamically
assigned port only when database tests need it and removes it after the session.
Each database test initializes and drops `crossfit_test` and closes its async
client. Tests use the container's connection URL rather than `MONGO_URL`, so no
external MongoDB deployment is needed. GitHub-hosted Ubuntu runners provide
Docker; the CI job does not declare a separate MongoDB service.

The backend test job temporarily uses `ubuntu-22.04`, whose current hosted image
uses kernel 6.8. MongoDB 8 has a documented incompatibility with newer kernels
that can prevent startup. Docker containers use the host kernel, so changing the
container's Linux distribution does not resolve this error.
See the [MongoDB compatibility notice](https://www.mongodb.com/community/forums/t/mongodb-8-x-and-linux-kernel-6-19/337547)
and [GitHub runner details](https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2204-Readme.md).
Revisit this workaround when MongoDB supports the runner kernel and before
GitHub retires the Ubuntu 22.04 runner.

## Generated API documentation

`.github/workflows/swagger-generation.yml` runs after a push to `main` changes
`backend/src/crosfit_training_backend/api/**`, including merged pull requests.
It checks out current `main` with full tag history, invokes the existing
`backend/src/crosfit_training_backend/common/swagger_generator.py` script, and
commits only `docs/backend-swagger.json` if its contents change. It does not need
MongoDB or Keycloak because generation does not enter the application lifespan.

The commit message is:

```text
chore(swagger): regenerate backend schema for <tag>
```

`<tag>` is the nearest reachable Git tag (`git describe --tags --abbrev=0`),
including lightweight tags. When none exists it is `0.0.0`.
Generation is serialized, and pushes use the repository's `GITHUB_TOKEN`.
GitHub does not start another push workflow from this token's commits:
[GitHub workflow trigger documentation](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow).

The generation job requests `contents: write`. Repository or organization
policies must allow that permission, and `main` branch protection/rulesets must
permit the bot's direct push for automatic commits to work. No personal token is
needed. If `main` advances during generation, the normal Git push safely fails;
rerun the workflow to generate against the latest `main`.

When adding git-cliff, place this parser before broader commit parsers in its
`[git]` configuration to exclude generated schema commits:

```toml
commit_parsers = [
    { message = '^chore\(swagger\):', skip = true },
    # Other parsers follow.
]
```

See [git-cliff commit parser documentation](https://git-cliff.org/docs/configuration/git/#commit_parsers).
Changelog generation itself is not enabled yet.
