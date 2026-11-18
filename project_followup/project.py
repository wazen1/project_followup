import frappe


class FollowupProjectMixin:
    def update_percent_complete(self):
        if self.get('custom_pf_mode') != 'متابعة غير مالية':
            return super().update_percent_complete()
        tasks = frappe.get_all('Task', filters={'project': self.name},
                               fields=['status', 'custom_pf_approved_by']) if self.name else []
        # Cancelled work remains visible and never counts as completed work.
        approved = sum(t.status == 'Completed' and bool(t.custom_pf_approved_by) for t in tasks)
        self.percent_complete = round(100 * approved / len(tasks), 2) if tasks else 0
        # ERPNext also calls this from Task.update_project and writes directly to DB.
        # Do not automatically close the project when progress reaches 100%.
