# Feature Specification: Centralized LLM Instance Management

**Feature Branch**: `006-centralized-llm`
**Created**: 2025-11-13
**Status**: Draft
**Input**: User description: "Should we create an one and only llm using create_llm function somewhere (main.py or config.py)? Right now, we create multiple llm using create_llm in different files. A good thing about this is we can have customized llm instance but we probably don't really need this.

If we have only one instance (llm). Configuring it for testing environment (pytest) will be much easier. When running pytest, we can create a mockLLM with all the responses kinda decided. => The behavior is controllable.

If we do this, we will need at least two LLMs:
(1) normal LLM
(2) LLM with a internal-llm tags

Overall, the idea looks good.


Then we can re-organize the mock-LLM or fake-LLM responses scripts. Especially thoses used in the test scripts."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Centralized LLM Instance Access (Priority: P1)

Developers need a single, consistent way to access LLM instances throughout the codebase instead of creating multiple instances with `create_llm()` in different files.

**Why this priority**: This is the foundation that enables all other improvements. Without centralized instances, we cannot achieve consistent testing behavior or simplified configuration.

**Independent Test**: Can be fully tested by importing the centralized LLM instances in any module and verifying they return the same configured instance without requiring multiple `create_llm()` calls. Delivers immediate value by reducing code duplication and potential configuration drift.

**Acceptance Scenarios**:

1. **Given** a module needs an LLM instance, **When** it imports from the centralized location, **Then** it receives a pre-configured LLM instance without calling `create_llm()`
2. **Given** multiple modules import the centralized LLM, **When** they use the instances, **Then** all modules share the same LLM instance (singleton pattern)
3. **Given** the application requires different LLM configurations, **When** modules access specific LLM types (normal vs internal-tagged), **Then** each receives the appropriate pre-configured instance

---

### User Story 2 - Simplified Test Environment Configuration (Priority: P2)

Test engineers need to easily configure deterministic LLM behavior for all tests without modifying individual test files or agent implementations.

**Why this priority**: Depends on P1 (centralized instances) but delivers significant testing improvements. Makes test maintenance much easier and enables controlled testing scenarios.

**Independent Test**: Can be fully tested by running the test suite with TESTING=true and verifying all LLM calls return predictable FakeChatModel responses without requiring per-test LLM configuration. Delivers value by making tests faster, more reliable, and easier to maintain.

**Acceptance Scenarios**:

1. **Given** TESTING environment variable is set to true, **When** tests import the centralized LLM, **Then** they automatically receive FakeChatModel instances without additional configuration
2. **Given** a test needs deterministic LLM responses, **When** the test runs using centralized LLM instances, **Then** all LLM calls return predictable, pattern-matched responses
3. **Given** production code uses centralized LLM instances, **When** TESTING=false, **Then** the same code automatically uses real ChatOpenAI instances

---

### User Story 3 - Organized Mock Response Management (Priority: P3)

Test maintainers need a clear, centralized structure for managing fake LLM response patterns and behaviors used across all tests.

**Why this priority**: Depends on P1 and P2 being complete. Improves test maintainability and makes it easier to add new response patterns, but system functions without it.

**Independent Test**: Can be fully tested by organizing fake response logic into a structured format and verifying tests can reference response patterns by name rather than embedding logic. Delivers value by making test updates easier and reducing response duplication.

**Acceptance Scenarios**:

1. **Given** a new test scenario requires specific LLM responses, **When** the test maintainer defines the response pattern in the centralized fake response repository, **Then** all tests can reference that pattern without duplicating logic
2. **Given** fake response patterns are organized by context (supervisor, emotional_support, rag_agent, etc.), **When** developers need to update response behavior, **Then** they can locate and modify patterns in a single, well-organized location
3. **Given** multiple tests use similar response patterns, **When** the pattern is defined once centrally, **Then** all tests automatically benefit from pattern improvements and bug fixes

---

### Edge Cases

- What happens when a module needs a custom temperature setting different from the centralized instances?
- How does the system handle tests that need to mock specific LLM failures or timeouts?
- What happens if centralized instances are accessed before initialization (e.g., import order issues)?
- How are LLM instances managed in concurrent test execution (pytest-xdist)?
- What happens when a new agent requires a third LLM configuration type beyond "normal" and "internal-tagged"?
- What happens to existing tests that still call `create_llm()` directly after migration? (Answer: They fail immediately - fail fast philosophy)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a centralized module that initializes and exposes pre-configured LLM instances
- **FR-002**: System MUST provide at least two distinct LLM instance types: (1) normal LLM for user-facing responses, (2) LLM with "internal-llm" tags for internal operations like query expansion
- **FR-003**: Centralized LLM instances MUST automatically use FakeChatModel when TESTING environment variable is true
- **FR-004**: Centralized LLM instances MUST automatically use real ChatOpenAI when TESTING environment variable is false or unset
- **FR-005**: All existing modules that call `create_llm()` MUST be refactored to import from the centralized LLM module instead
- **FR-006**: FakeChatModel response logic MUST be organized into a structured format (e.g., response registry, pattern-based matching system) that eliminates embedded conditional logic
- **FR-007**: System MUST preserve existing LLM configuration parameters (temperature, streaming settings, tags) when migrating to centralized instances
- **FR-008**: Centralized LLM module MUST initialize instances at import time to support singleton pattern
- **FR-009**: System MUST immediately break any code using old `create_llm()` patterns - fail fast to force migration to centralized instances
- **FR-010**: System MUST document the centralized LLM instance access pattern for future developers

### Key Entities *(include if feature involves data)*

- **Centralized LLM Module**: A Python module (e.g., `app/llm_instances.py` or `app/config/llm.py`) that initializes and exposes shared LLM instances
  - Attributes: response_llm (BaseChatModel), internal_llm (BaseChatModel with "internal-llm" tags)
  - Responsibilities: Initialize instances based on TESTING environment variable, apply appropriate configurations

- **Normal LLM Instance**: The primary LLM instance used for user-facing responses
  - Attributes: temperature (configurable, default varies by usage), streaming enabled/disabled, no special tags
  - Relationships: Used by supervisor, emotional_support, rag_agent modules

- **Internal LLM Instance**: LLM instance specifically for internal operations (e.g., query expansion)
  - Attributes: temperature=1.0, streaming disabled, tags=["internal-llm"]
  - Relationships: Used by advanced retriever for query expansion

- **Fake Response Registry**: Structured organization of FakeChatModel response patterns
  - Attributes: response patterns indexed by context type (supervisor, emotional_support, rag_agent), pattern matching rules
  - Relationships: Used by FakeChatModel when TESTING=true

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All LLM instance creation reduced to a single centralized location - zero `create_llm()` calls outside the centralized module
- **SC-002**: Test suite runs with 100% consistent FakeChatModel behavior without per-test LLM configuration
- **SC-003**: New tests can be written without needing to understand LLM initialization - developers simply import from centralized module
- **SC-004**: Fake response patterns are organized such that adding a new response scenario requires changes in only one location (the response registry)
- **SC-005**: Production code is unaffected by testing configuration - same import statements work in both test and production environments
- **SC-006**: Code duplication related to LLM initialization reduced by at least 80% (measured by lines of code)

## Assumptions

- Current LLM configurations are sufficient for most use cases - we do not need more than 2-3 centralized instances
- The two-instance approach (normal + internal-tagged) covers all current system requirements
- Tests do not require per-test LLM instance customization beyond response pattern matching
- The singleton pattern (shared instances) is acceptable - no requirements for instance isolation between operations
- FakeChatModel's pattern-based response matching is sufficient for test determinism
- Temperature settings can be standardized per instance type (current variations reflect lack of consistency rather than requirements)
- Import-time initialization is safe and does not create circular dependency issues
- **Development mode**: Breaking changes are acceptable - fail fast and fix forward rather than maintaining backward compatibility
- Legacy code will be eliminated, not supported - if tests break, they will be fixed to use the new pattern

## Open Questions

None at this time - all requirements are well-defined based on the user's description and codebase analysis.
