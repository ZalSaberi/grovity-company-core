# Phase 3C — Personal Calendar & Meeting Requests

## Canonical calendar engine

Phase 3C reuses Frappe `Event`. It does not build a second calendar engine.

The operational calendar route is:

`/app/event/view/calendar/default`

Grovity synchronizes these records into private Event rows:

- Project Meeting
- Task deadline
- Milestone
- Meeting Action
- accepted Meeting Request

Personal planning uses ordinary private Event rows with `Grovity Entry Type = Personal Plan`.

## Privacy

Meeting-request availability is **Free/Busy only**. The availability API returns available time slots and does not return Event subject, description, project name, or private meeting details.

Grovity-managed project Events are private and are read-shared only with users who can already read the authoritative source document. A Project Membership change triggers a project calendar access re-sync.

## Meeting Request workflow

- `Requested -> Scheduled`
- `Requested -> Alternative Proposed -> Scheduled`
- `Requested -> Rejected`
- `Requested/Alternative Proposed/Scheduled -> Cancelled`

Accepting a request creates either:

- a normal private Event, or
- a Project Meeting, when Meeting Mode is `Project Meeting`.

## Retention

Company Owner preferences are permanent.

Project Manager personal-plan retention defaults to 30 days. Monthly lifecycle processing may email the previous month's calendar summary and archives old **Personal Plan** rows only.

Official Project Meetings, Task/Milestone history, Meeting Actions, and project audit records are never deleted by the Phase 3C retention job.

## Google Calendar

Frappe Event already contains Google Calendar synchronization fields. Phase 3C deliberately keeps `sync_with_google_calendar = 0` for Grovity-managed Events. Phase 11 will configure credentials/calendar mapping and turn on external sync without replacing this data model.
