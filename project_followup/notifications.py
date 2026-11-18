"""In-app deadline reminders; never send email or external messages."""
import hashlib
import frappe
from frappe.utils import now_datetime, get_datetime, add_days


def deadline_notifications():
    from project_followup.api import MODE, TERMINAL
    now=now_datetime()
    for project in frappe.get_all('Project',filters={'custom_pf_mode':MODE,'custom_pf_closed_at':['is','not set']},fields=['name','custom_pf_manager']):
        for task in frappe.get_all('Task',filters={'project':project.name,'status':['not in',TERMINAL],'exp_end_date':['<=',add_days(now,1)]},fields=['name','exp_end_date','custom_pf_assignee']):
            if not task.exp_end_date:
                continue
            late=get_datetime(task.exp_end_date)<now
            recipients={task.custom_pf_assignee}
            if late:
                recipients.add(project.custom_pf_manager)
            for user in recipients-{None,''}:
                if not frappe.db.get_value('User',user,'enabled') or not frappe.has_permission('Task','read',doc=task.name,user=user):
                    continue
                key=hashlib.sha256(f'{task.name}|{user}|{task.exp_end_date}|{late}'.encode()).hexdigest()[:32]
                if frappe.db.exists('Notification Log',key):
                    continue
                title=('تأخرت مهمة: ' if late else 'اقترب موعد مهمة: ')+task.name
                # Notification Log.after_insert can send email based on user preferences.
                # Insert only this in-app notification, then update the bell explicitly.
                frappe.get_doc({'doctype':'Notification Log','name':key,'subject':title,'title':title,
                    'type':'Alert','for_user':user,'from_user':'Administrator','document_type':'Task','document_name':task.name,
                    'read':0,'owner':'Administrator','modified_by':'Administrator','creation':now,'modified':now}).db_insert()
                from frappe.desk.doctype.notification_log.notification_log import set_notifications_as_unseen
                set_notifications_as_unseen(user)
                frappe.publish_realtime('notification',user=user,after_commit=True)
