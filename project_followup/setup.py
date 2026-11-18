import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def field(name, label, kind='Data', **kwargs):
    return dict(fieldname='custom_pf_'+name, label=label, fieldtype=kind, **kwargs)


def install():
    project = [
        field('section','المتابعة الإدارية واللجان','Section Break',insert_after='project_name'),
        field('mode','نمط المشروع','Select',options='مالي\nمتابعة غير مالية',default='مالي',in_list_view=1),
        field('kind','نوع العمل','Select',options='مشروع إداري\nلجنة\nلجنة أزمة\nمبادرة',depends_on="eval:doc.custom_pf_mode=='متابعة غير مالية'"),
        field('manager','رئيس اللجنة / مسؤول الاعتماد','Link',options='User',depends_on="eval:doc.custom_pf_mode=='متابعة غير مالية'"),
        field('team','الأعضاء واختصاصاتهم','Table',options='Followup Team Member',depends_on="eval:doc.custom_pf_mode=='متابعة غير مالية'"),
        field('review_section','قرار الإقفال','Section Break',depends_on="eval:doc.custom_pf_mode=='متابعة غير مالية'"),
        field('outcome','نتيجة الإقفال','Select',options='\nمكتمل\nمتوقف\nملغى',read_only=1),
        field('closure_report','التقرير الختامي / سبب الإقفال','Small Text',read_only=1),
        field('actual_finish','تاريخ انتهاء العمل الفعلي','Date',read_only=1),
        field('closed_by','اعتمد الإقفال','Link',options='User',read_only=1),
        field('closed_at','تاريخ تسجيل الإقفال','Datetime',read_only=1),
    ]
    task = [
        field('section','متابعة المسؤول والمراجعة','Section Break',insert_after='subject'),
        field('assignee','المسؤول المباشر','Link',options='User'),
        field('specialization','الاختصاص المطلوب'),
        field('original_due','الموعد الأصلي','Datetime',read_only=1),
        field('result','نتيجة العمل','Small Text'),
        field('evidence','مرفق الإنجاز','Attach'),
        field('blocker','سبب التعثر / الجهة المطلوبة','Small Text'),
        field('review_note','ملاحظة المراجعة / سبب الإلغاء','Small Text',read_only=1),
        field('approved_by','اعتمد إقفال المهمة','Link',options='User',read_only=1),
        field('approved_at','تاريخ اعتماد المهمة','Datetime',read_only=1),
        field('proposed_due','الموعد المطلوب بعد التمديد','Datetime',read_only=1),
        field('extension_reason','سبب طلب التمديد','Small Text',read_only=1),
        field('extension_state','حالة التمديد','Select',options='\nبانتظار الموافقة\nمقبول\nمرفوض',read_only=1),
        field('extension_by','اعتمد قرار التمديد','Link',options='User',read_only=1),
        field('extension_at','تاريخ قرار التمديد','Datetime',read_only=1),
    ]
    for fields in [project, task]:
        for previous, current in zip(fields, fields[1:]):
            current['insert_after'] = previous['fieldname']
    create_custom_fields({'Project': project, 'Task': task})
    for dt in ['Project','Task']:
        make_property_setter(dt,None,'track_changes','1','Check',for_doctype=True)
