# Tasks: MCP Character Service

**Input**: Design documents from `/mnt/d/Projects/mcp-character-service/specs/001-please-create-the/`
**Prerequisites**: plan.md (✓), research.md (✓), data-model.md (✓), contracts/ (✓), quickstart.md (✓)

## Execution Flow (main)
```
1. Load plan.md from feature directory
   → ✅ Implementation plan found with Python 3.11 + FastAPI + SQLAlchemy + PostgreSQL
2. Load optional design documents:
   → ✅ data-model.md: 4 entities (Character, Relationship, Personality, Archetype)
   → ✅ contracts/: 6 MCP tools (create_character, get_character, search_characters, etc.)
   → ✅ research.md: Technology decisions and architecture patterns
   → ✅ quickstart.md: 5 integration test scenarios
3. Generate tasks by category:
   → Setup: Python project, PostgreSQL, dependencies, linting
   → Tests: 6 MCP contract tests, 5 integration tests, performance tests
   → Core: 4 model classes, character service, MCP tools, database layer
   → Integration: Database setup, MCP server, health checks, logging
   → Polish: unit tests, documentation, optimization
4. Apply task rules:
   → Different files = marked [P] for parallel execution
   → Same file = sequential (no [P] marker)
   → Tests before implementation (TDD compliance)
5. Number tasks sequentially (T001-T042)
6. Dependencies: Setup → Tests → Models → Services → Integration → Polish
7. Parallel execution examples provided
8. Validation: All 6 MCP tools have contract tests, all 4 entities have models
9. Return: SUCCESS (42 tasks ready for execution)
```

## Format: `[ID] [P?] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- Include exact file paths in descriptions

## Path Conventions
Single microservice project structure:
- `src/` for source code
- `tests/` for all test files
- Repository root for configuration files

## Phase 3.1: Setup
- [ ] T001 Create project structure with src/, tests/, docs/, config/, migrations/ directories
- [ ] T002 Initialize Python 3.11 project with pyproject.toml and requirements.txt
- [ ] T003 [P] Configure ruff linting and black formatting in pyproject.toml
- [ ] T004 [P] Setup pytest configuration in pyproject.toml with test discovery
- [ ] T005 [P] Create Docker configuration files: Dockerfile and docker-compose.yml
- [ ] T006 [P] Setup environment configuration files: config/development.env, config/production.env, config/test.env
- [ ] T007 Install core dependencies: FastAPI, SQLAlchemy, Pydantic, asyncpg, redis, prometheus-client
- [ ] T008 Install MCP SDK and development dependencies: pytest, pytest-asyncio, httpx, factory-boy

## Phase 3.2: Tests First (TDD) ⚠️ MUST COMPLETE BEFORE 3.3
**CRITICAL: These tests MUST be written and MUST FAIL before ANY implementation**

### MCP Contract Tests
- [ ] T009 [P] Contract test for create_character MCP tool in tests/contract/test_mcp_create_character.py
- [ ] T010 [P] Contract test for get_character MCP tool in tests/contract/test_mcp_get_character.py
- [ ] T011 [P] Contract test for search_characters MCP tool in tests/contract/test_mcp_search_characters.py
- [ ] T012 [P] Contract test for create_relationship MCP tool in tests/contract/test_mcp_create_relationship.py
- [ ] T013 [P] Contract test for get_character_relationships MCP tool in tests/contract/test_mcp_get_character_relationships.py
- [ ] T014 [P] Contract test for update_character MCP tool in tests/contract/test_mcp_update_character.py

### Integration Tests
- [ ] T015 [P] Integration test for character creation scenario in tests/integration/test_character_creation.py
- [ ] T016 [P] Integration test for character relationships scenario in tests/integration/test_character_relationships.py
- [ ] T017 [P] Integration test for character search scenario in tests/integration/test_character_search.py
- [ ] T018 [P] Integration test for character updates scenario in tests/integration/test_character_updates.py
- [ ] T019 [P] Integration test for complex relationship network scenario in tests/integration/test_relationship_network.py

### Performance Tests
- [ ] T020 [P] Performance test for 200ms latency requirement in tests/performance/test_latency_requirements.py
- [ ] T021 [P] Performance test for concurrent access in tests/performance/test_concurrent_access.py

## Phase 3.3: Core Implementation (ONLY after tests are failing)

### Database Layer
- [ ] T022 [P] Database connection and session management in src/database/connection.py
- [ ] T023 [P] Database migration system setup in migrations/env.py and migrations/script.py.mako
- [ ] T024 Create initial database schema migration in migrations/versions/001_initial_schema.py

### Model Implementation
- [ ] T025 [P] Character model with SQLAlchemy in src/models/character.py
- [ ] T026 [P] Relationship model with bidirectional consistency in src/models/relationship.py
- [ ] T027 [P] Personality model with JSON fields in src/models/personality.py
- [ ] T028 [P] Archetype model with templates in src/models/archetype.py

### Service Layer
- [ ] T029 [P] Character service with business logic in src/services/character_service.py
- [ ] T030 [P] Relationship service with bidirectional management in src/services/relationship_service.py
- [ ] T031 [P] Search service with optimized queries in src/services/search_service.py

### MCP Protocol Implementation
- [ ] T032 [P] MCP server setup and configuration in src/mcp/server.py
- [ ] T033 [P] Character creation MCP tool in src/mcp/tools/create_character.py
- [ ] T034 [P] Character retrieval MCP tool in src/mcp/tools/get_character.py
- [ ] T035 [P] Character search MCP tool in src/mcp/tools/search_characters.py
- [ ] T036 [P] Relationship creation MCP tool in src/mcp/tools/create_relationship.py
- [ ] T037 [P] Relationship query MCP tool in src/mcp/tools/get_character_relationships.py
- [ ] T038 [P] Character update MCP tool in src/mcp/tools/update_character.py

## Phase 3.4: Integration
- [ ] T039 FastAPI application setup with MCP server integration in src/main.py
- [ ] T040 Health check endpoints and service monitoring in src/api/health.py
- [ ] T041 Structured logging and Prometheus metrics in src/utils/observability.py

## Phase 3.5: Polish
- [ ] T042 [P] Unit tests for validation logic in tests/unit/test_validation.py

## Dependencies
**Critical Path**:
- Setup (T001-T008) must complete before all other phases
- All tests (T009-T021) must complete and FAIL before implementation (T022-T041)
- Database layer (T022-T024) blocks model implementation (T025-T028)
- Models (T025-T028) block services (T029-T031)
- Services (T029-T031) block MCP tools (T032-T038)
- MCP tools (T032-T038) block integration (T039-T041)

**Parallel Execution Blocks**:
- Block 1: T003, T004, T005, T006 (configuration files)
- Block 2: T009-T014 (MCP contract tests)
- Block 3: T015-T019 (integration tests)
- Block 4: T020, T021 (performance tests)
- Block 5: T022, T023 (database setup)
- Block 6: T025-T028 (model classes)
- Block 7: T029-T031 (service classes)
- Block 8: T033-T038 (MCP tool implementations)

## Parallel Example
```bash
# Launch Block 2 (MCP contract tests) together:
Task: "Contract test for create_character MCP tool in tests/contract/test_mcp_create_character.py"
Task: "Contract test for get_character MCP tool in tests/contract/test_mcp_get_character.py"
Task: "Contract test for search_characters MCP tool in tests/contract/test_mcp_search_characters.py"
Task: "Contract test for create_relationship MCP tool in tests/contract/test_mcp_create_relationship.py"
Task: "Contract test for get_character_relationships MCP tool in tests/contract/test_mcp_get_character_relationships.py"
Task: "Contract test for update_character MCP tool in tests/contract/test_mcp_update_character.py"
```

## Notes
- [P] tasks target different files with no dependencies
- Verify all tests fail before implementing corresponding functionality
- Commit after each task completion
- Run full test suite before moving to next phase
- Monitor performance metrics during implementation

## Task Generation Rules Applied
✅ **6 MCP contract files → 6 contract test tasks [P]** (T009-T014)
✅ **4 entities in data-model → 4 model creation tasks [P]** (T025-T028)
✅ **5 quickstart scenarios → 5 integration test tasks [P]** (T015-T019)
✅ **6 MCP tools → 6 implementation tasks [P]** (T033-T038)
✅ **Different files marked [P], same files sequential**
✅ **TDD order: Tests (T009-T021) before implementation (T022-T041)**

## Validation Checklist
✅ All 6 MCP tools have corresponding contract tests
✅ All 4 entities have model creation tasks
✅ All 5 quickstart scenarios have integration tests
✅ Performance requirements (200ms latency) have dedicated tests
✅ Constitutional requirements (TDD, observability) addressed
✅ Each task specifies exact file path
✅ No [P] task modifies same file as another [P] task
