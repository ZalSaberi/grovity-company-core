
import frappe


KANBAN_BOARD_NAME = "Grovity Task Board"


def ensure_task_kanban_board():
    existing = frappe.db.exists(
        "Kanban Board",
        KANBAN_BOARD_NAME,
    )

    if existing:
        board = frappe.get_doc(
            "Kanban Board",
            existing,
        )

        changed = False

        if board.reference_doctype != "Task":
            board.reference_doctype = "Task"
            changed = True

        if board.field_name != "status":
            board.field_name = "status"
            changed = True

        if board.private:
            board.private = 0
            changed = True

        if changed:
            board.save(ignore_permissions=True)

        return board.name

    status_field = frappe.get_meta(
        "Task"
    ).get_field("status")

    if not status_field:
        frappe.throw(
            "Task status field is required "
            "for the Grovity Kanban board."
        )

    board = frappe.get_doc(
        {
            "doctype": "Kanban Board",
            "kanban_board_name": KANBAN_BOARD_NAME,
            "reference_doctype": "Task",
            "field_name": "status",
            "private": 0,
            "show_labels": 0,
        }
    )

    for option in (
        status_field.options or ""
    ).splitlines():
        option = option.strip()

        if not option:
            continue

        board.append(
            "columns",
            {
                "column_name": option,
            },
        )

    board.insert(ignore_permissions=True)

    return board.name


def ensure_project_views():
    ensure_task_kanban_board()
    frappe.clear_cache(doctype="Task")
    frappe.clear_cache(doctype="Project")
    frappe.clear_cache()
