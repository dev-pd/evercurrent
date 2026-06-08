# Testing strategy

Companion to `AGENTS.md §11`. This doc lives at the "how" level —
where tests live, what tooling, what patterns, what to skip.

## TL;DR

| Layer | Tooling | Where | When run |
|---|---|---|---|
| Python unit (TDD) | pytest + pytest-asyncio | `apps/api/tests/unit/` | pre-commit, CI |
| Python integration | pytest + testcontainers | `apps/api/tests/integration/` | CI, `make test` |
| Eval (LLM behaviour) | custom runner | `apps/api/tests/evals/` | `make eval` only |
| TS unit + component | vitest + RTL + msw | `apps/web/__tests__/` | pre-commit, CI |
| E2E (one happy path) | Playwright | `apps/web/e2e/` | CI, `make e2e` |

Coverage gate: **80% line coverage** on
`auth/`, `tenancy/`, `scoring/`, `cards/`, `ingestion/`,
`db/repositories/`, `connectors/*/events`. Agents + prompts
excluded.

---

## TDD discipline

Red → green → refactor.

1. Write the failing test first. Run it. Watch it fail.
2. Write the minimum code to make it pass.
3. Refactor for clarity. Re-run tests.
4. Commit.

Apply only to deterministic modules. The list is in the gate above.

### Test naming

Full-sentence test names. They double as the spec.

```python
def test_score_includes_role_match_when_user_owns_subsystem():
    ...

def test_quiet_hours_defers_delivery_to_next_open_window():
    ...

def test_chunking_respects_overlap_across_paragraph_boundaries():
    ...
```

Read the test list aloud — it should describe what the module does.

### One assert per test

When possible. Multiple asserts in a single test hide which one
fails. Split into separate cases.

### Test public behaviour, not implementation

If you rename a private helper, the test should not break. Tests
that import `_compute_role_weight` are an anti-pattern — test
`score()` instead.

### Arrange-Act-Assert

```python
def test_x():
    # arrange
    member = make_member(role="mech", owned_subsystems=["chassis"])
    message = make_message(affected_roles=["mech"], entities=["chassis"])

    # act
    score = score_message_for_member(message, member)

    # assert
    assert score.total > 0.5
```

Blank line between phases. The reader sees the shape at a glance.

---

## Backend test setup

### conftest.py (root)

Lives at `apps/api/tests/conftest.py`. Provides:

```python
@pytest.fixture(scope="session")
def postgres_container():
    """One postgres container per session."""
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        ...
        yield pg

@pytest.fixture
async def db_session(postgres_container):
    """Per-test transaction, rolled back at teardown."""
    engine = create_async_engine(postgres_container.get_url())
    async with engine.begin() as conn:
        await conn.execute(text("BEGIN"))
        yield AsyncSession(conn)
        await conn.execute(text("ROLLBACK"))

@pytest.fixture
async def client(db_session):
    """FastAPI client with overridden DB dep."""
    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
```

Pattern: session-scoped expensive resources (Postgres container),
function-scoped cheap things (transactions, clients).

### Factories with polyfactory

```python
from polyfactory.factories.pydantic_factory import ModelFactory

class MessageFactory(ModelFactory[Message]):
    __model__ = Message

# in a test
msg = MessageFactory.build(text="hello", urgency="critical")
```

Typed fake data, no hand-written `MagicMock(text="hello")` noise.

### Async testing

`pytest-asyncio` with `asyncio_mode = "auto"` in `pyproject.toml`.
Every `async def test_x()` runs in an event loop without
boilerplate.

### Mocking LLM calls

Only for unit tests. Replace `llm.client.AnthropicProvider` with
a fake that returns a canned response. Use `dependency_overrides`
in FastAPI tests.

```python
class FakeLLM:
    def __init__(self, response: str):
        self.response = response
    async def generate(self, **kw):
        return LLMResponse(content=self.response, ...)

app.dependency_overrides[get_llm] = lambda: FakeLLM('{"topic": "test"}')
```

For integration tests, hit the real Anthropic API only behind a
`@pytest.mark.expensive` marker, skipped by default.

---

## Frontend test setup

### vitest.config.ts

```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: "./__tests__/setup.ts",
    globals: true,
  },
});
```

### setup.ts

```ts
import "@testing-library/jest-dom";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(cleanup);
```

### Mocking the API with MSW

```ts
import { setupServer } from "msw/node";
import { http, HttpResponse } from "msw";

export const server = setupServer(
  http.get("/api/v1/digests/today", () =>
    HttpResponse.json({ id: "abc", items: [], generated_at: "..." }),
  ),
);

// in setup.ts
beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

Tests render components that make real fetch calls; MSW intercepts
at the network layer. Components don't know they're in a test.

### Component test pattern

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

test("clicking thumbs up fires feedback", async () => {
  const onFeedback = vi.fn();
  render(<DigestItemCard item={fakeItem} onFeedback={onFeedback} />);

  await userEvent.click(screen.getByRole("button", { name: /helpful/i }));

  expect(onFeedback).toHaveBeenCalledWith({ useful: true });
});
```

Query by role + accessible name. Not by class, not by test-id.
If you reach for test-id, your component's accessibility is broken.

---

## E2E — Playwright

One happy path. Not a regression suite.

```ts
test("user signs in and sees morning digest", async ({ page }) => {
  await page.goto("/");
  await page.click("text=Sign in");
  // Auth0 dev tenant; pre-seeded user
  await page.fill('input[name="email"]', "test@example.com");
  await page.fill('input[name="password"]', process.env.E2E_PASSWORD!);
  await page.click("text=Continue");

  await expect(page.getByRole("heading", { name: /good morning/i })).toBeVisible();
  await expect(page.getByText("Top priority")).toBeVisible();
  await expect(page.locator('[data-card-kind="decision"]').first()).toBeVisible();
});
```

Use `await expect()` for everything. Playwright auto-retries until
the assertion passes or the timeout fires.

Run via `make e2e`. Backend must be seeded; fixture script lives at
`apps/web/e2e/seed.ts`.

---

## Eval harness

Lives at `apps/api/tests/evals/`. Different runner from pytest
because the failure mode is "score below baseline" not "exception."

```
tests/evals/
├── runner.py              custom orchestrator
├── data/
│   ├── router_labels.json    50 hand-labelled messages
│   ├── rag_questions.json    30 question/expected-source pairs
│   ├── digest_scenarios.json 5 scenarios
│   └── scoring_cases.json    20 scenarios
├── eval_router.py
├── eval_rag.py
├── eval_digest.py
└── eval_scoring.py
```

Each eval writes a JSON report under `evals/reports/<date>.json`:

```json
{
  "router": {"accuracy": 0.94, "n": 50, "baseline": 0.90, "pass": true},
  "rag":    {"precision_at_5": 0.78, "mrr": 0.62, "n": 30, "pass": true},
  "digest": {"avg_relevance": 4.3, "avg_voice": 4.1, "pass": true}
}
```

Baselines tracked in `docs/EVAL_BASELINE.md`. Not a CI gate; run
via `make eval`. Cost: ~$3 per full run.

---

## CI gates

GitHub Actions runs:

| Job | Step | Fail = block merge |
|---|---|---|
| python-lint | `make lint` (ruff + ty) | yes |
| python-test | `make test` (unit + integration) | yes |
| python-coverage | check 80% gate | yes |
| web-lint | `eslint .` | yes |
| web-typecheck | `tsc --noEmit` | yes |
| web-test | `vitest run` | yes |
| web-build | `next build` | yes |
| e2e | playwright | yes (cached browser) |
| evals | informational only | no |

Evals run on-demand or via a separate Action with a label
(`/eval`) so they don't burn API budget on every PR.

---

## What NOT to test

- **Prompt strings.** They live in `<module>/prompts/*.txt`.
  Eval harness covers them.
- **LLM-returned content.** Schema validation (Pydantic strict)
  + evals cover this.
- **SQLAlchemy query strings.** Test against a real DB.
- **CSS classnames.** Test what the user sees, not how you styled
  it.
- **Implementation details of third-party SDKs.** Trust the
  vendor.
- **Trivial passthrough wrappers.** A function that just calls
  another function with the same args doesn't need a test.

---

## Pre-commit profile

`.pre-commit-config.yaml` runs on staged files only:

1. ruff format
2. ruff check
3. ty check
4. eslint --fix
5. prettier --write
6. pytest --co --quiet -q tests/unit (no execution, just collection
   sanity)
7. vitest --run --reporter=dot (only `__tests__/**` that match
   staged file globs)

Full test suite runs in CI, not pre-commit. Hooks stay under 10
seconds.

---

## How a new phase adds tests

Phase doc's "Test plan" lists the test files to write. Workflow:

1. Create the test files. Write failing tests for every public
   behaviour the phase will add.
2. Run the suite. All new tests fail. Confirm the failures are for
   the right reasons.
3. Implement code to make tests pass one at a time.
4. Refactor when green.
5. `make test` clean before commit.

Phase 7 (scoring) is the canonical TDD example. Read its phase
doc for the pattern.

---

## When the test harness gets in the way

If you find yourself fighting the harness:

- **Test takes >100ms locally:** it's probably an integration test
  in `unit/`. Move it.
- **Mock setup is longer than the test:** the dep is too tangled.
  Refactor the production code, not the test.
- **Same fixture in 10 tests:** extract a factory or conftest
  fixture.
- **Test breaks every refactor:** it tests implementation, not
  behaviour. Rewrite.
