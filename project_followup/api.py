from contextlib import contextmanager
import frappe
from frappe.utils import get_datetime, now_datetime, getdate, today

MODE = 'متابعة غير مالية'
TERMINAL = ('Completed', 'Cancelled')


def managed(project):
    return project.get('custom_pf_mode') == MODE


def manager(project):
    return frappe.session.user in ('Administrator', project.get('custom_pf_manager'))


def members(project):
    return {m.user for m in project.get('custom_pf_team') or [] if m.user} | {project.get('custom_pf_manager')}


def authenticated():
    if frappe.session.user == 'Guest':
        frappe.throw('سجّل الدخول أولًا', frappe.PermissionError)


@contextmanager
def action_context(doctype, name):
    previous = getattr(frappe.flags,'followup_action',None)
    frappe.flags.followup_action = (doctype,name)
    try:
        yield
    finally:
        frappe.flags.followup_action = previous


def service(doc):
    return getattr(frappe.flags,'followup_action',None) == (doc.doctype,doc.name)


def lock_project(name):
    frappe.db.sql('select name from `tabProject` where name=%s for update',(name,))
    return frappe.get_doc('Project',name)


def protect_fields(doc, old, names):
    if not service(doc) and any(changed(doc,old,f) for f in names):
        frappe.throw('استخدم أزرار المراجعة والاعتماد لتغيير هذه البيانات.')


def changed(doc, old, field):
    a,b=doc.get(field),old.get(field)
    meta=doc.meta.get_field(field)
    if a and b and meta and meta.fieldtype in ('Date','Datetime'):
        return get_datetime(a)!=get_datetime(b)
    return a!=b


def validate_project(doc, method=None):
    if not doc.is_new():
        frappe.db.sql('select name from `tabProject` where name=%s for update',(doc.name,))
    old = doc.get_doc_before_save()
    if old and managed(old) and not managed(doc):
        frappe.throw('لا يمكن تعطيل ضوابط المتابعة بتغيير نمط المشروع. أنشئ مشروعًا ماليًا مستقلًا عند الحاجة.')
    if not managed(doc):
        return
    if not manager(doc):
        # Project creators with existing create permissions may choose a chair once.
        if not doc.is_new():
            frappe.throw('تعديل المشروع من اختصاص رئيس اللجنة أو مسؤول النظام.',frappe.PermissionError)
    if old and not manager(old):
        frappe.throw('لا يمكنك تغيير رئيس اللجنة لمنح نفسك صلاحية الإدارة.',frappe.PermissionError)
    if not doc.custom_pf_manager or not frappe.db.get_value('User',doc.custom_pf_manager,'enabled'):
        frappe.throw('حدد رئيسًا للجنة بحساب مستخدم فعّال.')
    seen=set()
    for row in doc.get('custom_pf_team') or []:
        employee=frappe.db.get_value('Employee',row.employee,['user_id','status'],as_dict=True)
        if not employee or employee.status!='Active' or not employee.user_id or not frappe.db.get_value('User',employee.user_id,'enabled'):
            frappe.throw('كل عضو يجب أن يكون موظفًا نشطًا مرتبطًا بحساب فعّال.')
        row.user=employee.user_id
        if row.user in seen or not row.specialization:
            frappe.throw('حدد اختصاص كل عضو ولا تكرر حساب العضو.')
        seen.add(row.user)
    from project_followup.finance import ensure_no_finance
    ensure_no_finance(doc)
    if not doc.expected_end_date:
        frappe.throw('حدد الموعد النهائي للمشروع أو اللجنة.')
    protected=['custom_pf_outcome','custom_pf_closure_report','custom_pf_actual_finish','custom_pf_closed_by','custom_pf_closed_at']
    if old:
        protect_fields(doc,old,protected)
        if old.get('custom_pf_closed_at'):
            frappe.throw('المشروع مقفل؛ لا يمكن تعديل قرار الإقفال.')
        if doc.status != old.status and doc.status in ('Completed','Cancelled','On hold') and not service(doc):
            frappe.throw('استخدم زر مراجعة وإقفال المشروع لتوثيق القرار.')
        for t in frappe.get_all('Task',filters={'project':doc.name,'status':['not in',TERMINAL]},fields=['custom_pf_assignee']):
            if t.custom_pf_assignee and t.custom_pf_assignee not in seen | {doc.custom_pf_manager}:
                frappe.throw('أعد إسناد المهام المفتوحة قبل إزالة عضوها من اللجنة.')
    elif doc.status != 'Open' or any(doc.get(f) for f in protected):
        frappe.throw('المشروع الجديد يبدأ مفتوحًا دون اعتماد سابق.')


def validate_task(doc, method=None):
    old=doc.get_doc_before_save()
    if old and old.project and old.project != doc.project:
        old_project=frappe.get_doc('Project',old.project)
        if managed(old_project):
            frappe.throw('لا يمكن نقل مهمة متابعة إلى مشروع آخر لتجاوز المراجعة.')
    if not doc.project:
        return
    project=lock_project(doc.project)
    if not managed(project):
        return
    if project.get('custom_pf_closed_at'):
        frappe.throw('المشروع مقفل ولا يقبل إنشاء المهام أو تعديلها.')
    if doc.is_group or doc.is_template:
        frappe.throw('أنشئ مهام تنفيذية مستقلة للمشروع الإداري.')
    if not doc.custom_pf_assignee or doc.custom_pf_assignee not in members(project):
        frappe.throw('اختر مسؤول المهمة من أعضاء اللجنة أو رئيسها.')
    if not doc.custom_pf_specialization or not doc.exp_end_date:
        frappe.throw('حدد اختصاص المهمة وموعدها النهائي.')
    protected=['custom_pf_original_due','custom_pf_approved_by','custom_pf_approved_at','custom_pf_review_note',
               'custom_pf_proposed_due','custom_pf_extension_reason','custom_pf_extension_state','custom_pf_extension_by','custom_pf_extension_at']
    if old:
        protect_fields(doc,old,protected)
        if old.get('custom_pf_approved_by') and old.status in TERMINAL:
            frappe.throw('المهمة مقفلة بقرار معتمد؛ لا يمكن تعديلها.')
        if changed(doc,old,'exp_end_date') and not service(doc):
            frappe.throw('استخدم طلب تمديد ثم اعتماد التمديد لحفظ الموعد الأصلي.')
        if doc.status != old.status and not service(doc):
            frappe.throw('استخدم أزرار بدء التنفيذ والتقديم للمراجعة والاعتماد.')
        if not manager(project):
            if old.custom_pf_assignee != frappe.session.user:
                frappe.throw('يمكن للمسؤول المباشر فقط تحديث نتيجة المهمة.',frappe.PermissionError)
            # The assignee cannot rewrite their assignment, scope, or schedule through REST.
            allowed={'modified','modified_by','custom_pf_result','custom_pf_evidence','custom_pf_blocker','progress'}
            if service(doc):
                allowed |= {'status','review_date','completed_on','completed_by',*protected}
            for f in doc.meta.fields:
                if f.fieldtype not in ('Section Break','Column Break','Tab Break','HTML','Button') and f.fieldname not in allowed:
                    if changed(doc,old,f.fieldname):
                        frappe.throw('هذا الحقل من اختصاص رئيس اللجنة: '+f.label,frappe.PermissionError)
    else:
        if not manager(project):
            frappe.throw('إنشاء مهام اللجنة من اختصاص رئيسها.',frappe.PermissionError)
        if doc.status not in ('Open','Working') or any(doc.get(f) for f in protected):
            frappe.throw('المهمة الجديدة لا تحمل قرار مراجعة سابقًا.')
        doc.custom_pf_original_due=doc.exp_end_date
    if not doc.custom_pf_original_due:
        doc.custom_pf_original_due=old.exp_end_date if old else doc.exp_end_date


@frappe.whitelist(methods=['POST'])
def task_action(name, action, result=None, reason=None, proposed_due=None):
    authenticated()
    reference=frappe.db.get_value('Task',name,'project')
    if not reference:
        frappe.throw('المهمة غير مرتبطة بمشروع متابعة.')
    project=lock_project(reference)
    frappe.db.sql('select name from `tabTask` where name=%s for update',(name,))
    task=frappe.get_doc('Task',name)
    if task.project!=reference:
        frappe.throw('تغير المشروع المرتبط بالمهمة؛ أعد المحاولة.')
    task.check_permission('read')
    if not managed(project) or project.get('custom_pf_closed_at'):
        frappe.throw('المشروع ليس مشروع متابعة مفتوحًا.')
    is_manager=manager(project)
    assignee=task.custom_pf_assignee == frappe.session.user
    if action in ('approve','return','cancel','approve_extension','reject_extension'):
        if not is_manager:
            frappe.throw('هذا الإجراء من اختصاص رئيس اللجنة.',frappe.PermissionError)
    elif action not in ('start','submit','request_extension') or not (assignee or is_manager):
        frappe.throw('ليست لديك صلاحية هذا الإجراء.',frappe.PermissionError)
    if task.status in TERMINAL and (task.custom_pf_approved_by or action!='submit'):
        frappe.throw('المهمة منتهية ولا تقبل هذا الإجراء.')
    if action=='start':
        if task.status not in ('Open','Overdue'):
            frappe.throw('المهمة ليست جديدة أو متأخرة.')
        task.status='Working'
    elif action=='submit':
        if task.status not in ('Open','Working','Overdue','Completed'):
            frappe.throw('المهمة ليست جاهزة للتقديم للمراجعة.')
        if not (result or task.custom_pf_result or '').strip():
            frappe.throw('أدخل نتيجة العمل قبل التقديم للمراجعة.')
        task.custom_pf_result=result or task.custom_pf_result
        task.status='Pending Review'
    elif action in ('approve','return'):
        if task.status!='Pending Review':
            frappe.throw('المهمة ليست بانتظار المراجعة.')
        if action=='return':
            if not (reason or '').strip():
                frappe.throw('حدد سبب الإعادة.')
            task.status='Working';task.custom_pf_review_note=reason
        else:
            if not task.custom_pf_result:
                frappe.throw('نتيجة العمل مطلوبة للاعتماد.')
            task.status='Completed';task.custom_pf_approved_by=frappe.session.user;task.custom_pf_approved_at=now_datetime()
    elif action=='cancel':
        if not (reason or '').strip():
            frappe.throw('حدد سبب إلغاء المهمة.')
        task.status='Cancelled';task.custom_pf_review_note=reason
        task.custom_pf_approved_by=frappe.session.user;task.custom_pf_approved_at=now_datetime()
    elif action=='request_extension':
        if task.custom_pf_extension_state=='بانتظار الموافقة':
            frappe.throw('يوجد طلب تمديد بانتظار الموافقة.')
        if not reason or not proposed_due or get_datetime(proposed_due)<=get_datetime(task.exp_end_date):
            frappe.throw('حدد سبب التمديد وموعدًا لاحقًا للموعد الحالي.')
        task.custom_pf_proposed_due=proposed_due;task.custom_pf_extension_reason=reason
        task.custom_pf_extension_state='بانتظار الموافقة';task.custom_pf_extension_by=None;task.custom_pf_extension_at=None
    elif action in ('approve_extension','reject_extension'):
        if task.custom_pf_extension_state!='بانتظار الموافقة':
            frappe.throw('لا يوجد طلب تمديد بانتظار الموافقة.')
        if action=='approve_extension':
            task.exp_end_date=task.custom_pf_proposed_due
            task.custom_pf_extension_state='مقبول'
        else:
            if not reason:
                frappe.throw('حدد سبب رفض التمديد.')
            task.custom_pf_extension_state='مرفوض';task.custom_pf_review_note=reason
        task.custom_pf_extension_by=frappe.session.user;task.custom_pf_extension_at=now_datetime()
    with action_context('Task',name):
        task.save(ignore_permissions=True)
    return {'status':task.status}


@frappe.whitelist(methods=['POST'])
def create_task(project, subject, assignee, specialization, due):
    authenticated()
    parent=lock_project(project)
    parent.check_permission('read')
    if not managed(parent) or not manager(parent):
        frappe.throw('إنشاء المهام من اختصاص رئيس اللجنة.',frappe.PermissionError)
    task=frappe.get_doc({'doctype':'Task','subject':subject,'project':project,'status':'Open',
        'custom_pf_assignee':assignee,'custom_pf_specialization':specialization,'exp_end_date':due})
    task.insert(ignore_permissions=True)
    return task.name


@frappe.whitelist(methods=['POST'])
def close_project(name, outcome, report, actual_finish=None):
    authenticated()
    project=lock_project(name)
    project.check_permission('read')
    if not managed(project) or not manager(project):
        frappe.throw('إقفال المشروع من اختصاص رئيس اللجنة.',frappe.PermissionError)
    if project.custom_pf_closed_at or outcome not in ('مكتمل','متوقف','ملغى') or not (report or '').strip():
        frappe.throw('حدد نتيجة صحيحة وتقريرًا ختاميًا لمشروع مفتوح.')
    tasks=frappe.get_all('Task',filters={'project':name},fields=['name','status','custom_pf_approved_by'])
    if any(t.status not in TERMINAL or not t.custom_pf_approved_by for t in tasks):
        frappe.throw('اعتمد إنجاز جميع المهام أو وثّق إلغاء المتبقي منها أولًا.')
    if outcome=='مكتمل' and any(t.status!='Completed' for t in tasks):
        frappe.throw('لا يمكن اعتبار المشروع مكتملًا مع مهام ملغاة؛ اختر متوقفًا أو ملغى أو راجع نطاق العمل.')
    if actual_finish and getdate(actual_finish)>getdate(today()):
        frappe.throw('تاريخ الانتهاء الفعلي لا يكون في المستقبل.')
    project.custom_pf_outcome=outcome;project.custom_pf_closure_report=report
    project.custom_pf_actual_finish=actual_finish;project.custom_pf_closed_by=frappe.session.user;project.custom_pf_closed_at=now_datetime()
    project.status={'مكتمل':'Completed','متوقف':'On hold','ملغى':'Cancelled'}[outcome]
    with action_context('Project',name):
        project.save(ignore_permissions=True)
    return {'status':project.status}


def share_project(doc, method=None):
    if not managed(doc):
        return
    from frappe.share import add, remove
    old=doc.get_doc_before_save()
    if old and managed(old):
        for user in members(old)-members(doc)-{None}:
            remove('Project',doc.name,user,flags={'ignore_share_permission':True})
    for user in members(doc)-{None}:
        add('Project',doc.name,user,read=1,write=int(user==doc.custom_pf_manager),notify=0,flags={'ignore_share_permission':True})


def share_task(doc, method=None):
    if not doc.project:
        return
    project=frappe.get_doc('Project',doc.project)
    if not managed(project):
        return
    from frappe.share import add, remove
    old=doc.get_doc_before_save()
    if old and old.custom_pf_assignee and old.custom_pf_assignee not in {doc.custom_pf_assignee,project.custom_pf_manager}:
        remove('Task',doc.name,old.custom_pf_assignee,flags={'ignore_share_permission':True})
    for user in {doc.custom_pf_assignee,project.custom_pf_manager}-{None}:
        add('Task',doc.name,user,read=1,write=1,notify=0,flags={'ignore_share_permission':True})
    frappe.clear_document_cache('Project',doc.project)


def project_permission(doc, user=None, permission_type=None):
    if managed(doc) and (user or frappe.session.user) not in members(doc)|{'Administrator'}:
        # Global project managers may inspect governance, but cannot approve as chair.
        if not set(frappe.get_roles(user)) & {'System Manager','Projects Manager'}:
            return False
    return None


def project_query(user=None):
    user=user or frappe.session.user
    if user=='Administrator' or set(frappe.get_roles(user)) & {'System Manager','Projects Manager'}:
        return ''
    quoted=frappe.db.escape(user)
    return f"(coalesce(`tabProject`.custom_pf_mode,'')!='{MODE}' or `tabProject`.custom_pf_manager={quoted} or exists (select 1 from `tabFollowup Team Member` m where m.parent=`tabProject`.name and m.parenttype='Project' and m.user={quoted}))"


def task_query(user=None):
    user=user or frappe.session.user
    if user=='Administrator' or set(frappe.get_roles(user)) & {'System Manager','Projects Manager'}:
        return ''
    quoted=frappe.db.escape(user)
    return f"(not exists (select 1 from `tabProject` p where p.name=`tabTask`.project and p.custom_pf_mode='{MODE}') or `tabTask`.custom_pf_assignee={quoted} or exists (select 1 from `tabProject` p where p.name=`tabTask`.project and p.custom_pf_manager={quoted}))"


def task_permission(doc, user=None, permission_type=None):
    if doc.project:
        project=frappe.get_doc('Project',doc.project)
        if managed(project) and (user or frappe.session.user) not in {doc.custom_pf_assignee,project.custom_pf_manager,'Administrator'}:
            if not set(frappe.get_roles(user)) & {'System Manager','Projects Manager'}:
                return False
    return None


def prevent_project_delete(doc, method=None):
    if managed(doc) and (doc.custom_pf_closed_at or frappe.db.exists('Task',{'project':doc.name})):
        frappe.throw('احفظ سجل المشروع ومهامه؛ استخدم قرار الإقفال بدل الحذف.')


def prevent_task_delete(doc, method=None):
    if doc.project and managed(frappe.get_doc('Project',doc.project)):
        frappe.throw('احفظ سجل المهمة؛ استخدم الإلغاء مع سبب بدل الحذف.')


@frappe.whitelist()
def task_context(name):
    authenticated()
    doc=frappe.get_doc('Task',name);doc.check_permission('read')
    if not doc.project:
        return {'managed':False}
    project=frappe.get_doc('Project',doc.project)
    return {'managed':managed(project),'manager':manager(project),'assignee':doc.custom_pf_assignee==frappe.session.user,
            'closed':bool(project.get('custom_pf_closed_at')),'members':list(members(project)-{None}) if managed(project) else []}


@frappe.whitelist()
def overview():
    authenticated()
    rows=[]
    for entry in frappe.get_list('Project',filters={'custom_pf_mode':MODE},fields=['name'],limit_page_length=200):
        project=frappe.get_doc('Project',entry.name)
        if not project.has_permission('read'):
            continue
        tasks=frappe.get_all('Task',filters={'project':entry.name},fields=['name','subject','status','exp_end_date','custom_pf_assignee'])
        visible=[]
        for task in tasks:
            if frappe.get_doc('Task',task.name).has_permission('read'):
                visible.append(dict(task,overdue=bool(task.exp_end_date and get_datetime(task.exp_end_date)<now_datetime() and task.status not in TERMINAL)))
        rows.append({'name':project.name,'title':project.project_name,'progress':project.percent_complete,'status':project.status,
                     'outcome':project.custom_pf_outcome,'tasks':visible})
    return rows
