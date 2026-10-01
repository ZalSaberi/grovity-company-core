# Phase 3B — Notification Template Layer

This layer extends the completed Phase 3 operations/notification engine without changing the Phase 3 checkpoint.

## Scope

- Editable `Grovity Notification Template` records in ERP UI.
- Persian In-App and Email templates.
- Short Persian SMS templates with a runtime hard cap of 134 Unicode characters.
- Deadline templates for T-7, T-3, T-1, Due Date and Overdue.
- Meeting summary publication to the exact `Meeting Participant` list.
- Dedicated Meeting Action assignment notifications after summary publication.
- Progress Report revision-request notifications.
- Channel-specific rendering while preserving the existing global notification settings.
- Notification delivery logging and deduplication remain in `Notification Delivery`.

## Meeting Summary workflow

1. PM records meeting summary, decisions and actions.
2. PM confirms the meeting.
3. PM selects **Publish Summary**.
4. The summary is sent to Meeting Participants through enabled channels.
5. Each Meeting Action assignee receives a dedicated Action notification.
6. Published summary/decisions/participant content is locked against silent edits.

## Template policy

Global channel switches in `Grovity Notification Settings` remain authoritative.
Each template can additionally enable/disable In-App, Email and SMS.

Deadline SMS behavior still respects the existing T-7/T-3/T-1/Due/Overdue SMS policy.
Custom event SMS is controlled by the template and the global SMS switch.

`MEETING_SUMMARY_PUBLISHED` and `PROGRESS_REPORT_REVISION_REQUESTED`
ship with SMS disabled by default.
`MEETING_ACTION_ASSIGNED` ships with SMS enabled, but no SMS is sent while
the global SMS channel is disabled.

## SMS length

Rendered SMS text is normalized and capped at 134 Unicode characters to keep
Persian notifications concise and generally within two concatenated UCS-2 SMS
segments.

## Navigation Cleanup Impact

No new general-user navigation item is required. The template DocType is an
administrative configuration surface intended for Company Owner/System Manager.
