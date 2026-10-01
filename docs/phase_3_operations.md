# Phase 3 — Meetings, Progress & Notifications

Implemented as a clean, project-scoped backend layer on top of Phase 2.

## Project Meeting
- Project
- Date & time
- Participants
- Agenda
- Summary
- Decisions
- Prepared by
- PM confirmation
- CEO confirmation
- Final lock after CEO confirmation

## Meeting Action
- Project / Meeting
- Description
- Assigned To
- Deadline
- Priority
- Status
- Optional generated Task link

`assigned_to` is intentionally used instead of `owner`; `owner` is a Frappe
system field and must not be repurposed for business assignment.

## Progress Report
- Period
- Progress percent
- Completed
- In progress
- Issues
- Risks
- Next actions
- Draft -> Submitted -> Approved / Revision Requested

## Notifications
Daily in-app reminders for Tasks, Milestones, Deliverables, Meetings and
Meeting Actions at T-7, T-3, T-1, Due Date and Overdue. Duplicate notifications
for the same document/user/stage are suppressed.
