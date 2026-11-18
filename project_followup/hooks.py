app_name = 'project_followup'
app_title = 'Project Followup'
app_publisher = 'Internal Systems'
app_description = 'Administrative projects, committees and reviewed task completion'
app_email = ''
app_license = 'MIT'
required_apps = ['erpnext']
after_install = 'project_followup.setup.install'
after_migrate = 'project_followup.setup.install'
extend_doctype_class = {'Project': ['project_followup.project.FollowupProjectMixin']}
doctype_js = {'Project': 'public/js/project.js', 'Task': 'public/js/task.js'}
doctype_list_js = {'Task': 'public/js/task_list.js'}
app_include_css = ['/assets/project_followup/css/gantt.css?v=20260928-1']
doc_events = {
 'Project': {'validate': 'project_followup.api.validate_project', 'on_update': 'project_followup.api.share_project', 'on_trash': 'project_followup.api.prevent_project_delete'},
 'Task': {'validate': 'project_followup.api.validate_task', 'on_update': 'project_followup.api.share_task', 'on_trash': 'project_followup.api.prevent_task_delete'},
 '*': {'validate': 'project_followup.finance.validate_financial_document'},
}
has_permission = {'Project': 'project_followup.api.project_permission', 'Task': 'project_followup.api.task_permission'}
permission_query_conditions = {'Project': 'project_followup.api.project_query', 'Task': 'project_followup.api.task_query'}
scheduler_events = {'daily': ['project_followup.notifications.deadline_notifications']}
