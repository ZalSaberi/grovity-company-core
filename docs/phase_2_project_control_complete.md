
# Grovity Phase 2 — Project Control Core

Status: acceptance suite implemented.

Phase 2 scope covered by the custom `company_core` app:

- Project membership and project-level isolation
- Project Manager / Contributor / Intern / Observer / Internal Specialist roles
- Project master extensions
- Lifecycle status and immutable status history
- Required status-change reason
- Suspension Event
- Task and Milestone extensions
- Task contributors
- Planned / actual progress
- Deliverable and delay reason
- Task dependencies and deadlines through ERPNext Task
- Task List
- Kanban
- Gantt
- Milestone view
- Project Passport
- Contract / collected / cost snapshot
- Finance and Legal status placeholders for later dedicated phases
- Project-level permission enforcement for UI/API/list/search paths
- Runtime performance baselines

Final Phase 2 acceptance is represented by:

`company_core.tests.test_phase2_acceptance`

Scale acceptance is represented by:

`company_core.phase2_scale_benchmark`

The scale benchmark uses 10 projects and 120 tasks to represent the
initial operational target for the Project Control Core.
