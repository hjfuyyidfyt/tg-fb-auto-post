# Execution Roadmap

## Phase 0: Scope Lock

- Finalize MVP features
- Finalize menu map
- Finalize DB workload choice
- Finalize isolation rules for shared Oracle usage

## Phase 1: Server Foundation

- Verify SSH access
- Create project directories on the Ubuntu server
- Install Docker and Docker Compose if missing
- Prepare environment file strategy
- Prepare Redis and app runtime plan

## Phase 2: Repository Scaffold

- Create Python app structure
- Add configuration loading
- Add keyboard modules
- Add handler stubs
- Add service and repository boundaries

## Phase 3: Data Layer

- Add Oracle connection layer
- Define table naming convention with `EM_` prefix
- Add migration structure
- Add Redis integration for state and queue support

## Phase 4: Navigation Shell

- `/start` flow
- Owner gate
- Reply keyboard home menu
- Inline submenu rendering
- Shared back/home behavior

## Phase 5: Security And Roles

- Role checks
- Permission matrix
- Audit logging
- Sensitive action confirmation

## Phase 6: Channel And Group Management

- Add managed channel flow
- Add managed group flow
- Permission verification
- List and inspect registered entities

## Phase 7: Broadcast And Scheduling

- Create jobs
- Persist jobs
- Queue jobs
- Track execution results

## Phase 8: Deployment And Validation

- Compose stack
- Container startup
- Server-only smoke testing
- Test chats and test bot validation

## Phase 9: Expansion

- Analytics
- Bot health management
- Rule automation
- Advanced admin tooling
