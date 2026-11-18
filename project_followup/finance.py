import frappe

FINANCIAL = ('Budget','Sales Order','Purchase Order','Sales Invoice','Purchase Invoice',
             'Journal Entry','Payment Entry','Expense Claim','Stock Entry','Timesheet')


def project_links(doc):
    for f in doc.meta.fields:
        if f.fieldtype == 'Link' and f.options == 'Project' and doc.get(f.fieldname):
            yield doc.get(f.fieldname)
        elif f.fieldtype == 'Table':
            for child in doc.get(f.fieldname) or []:
                yield from project_links(child)


def validate_financial_document(doc, method=None):
    if doc.doctype not in FINANCIAL:
        return
    if not frappe.get_meta('Project').has_field('custom_pf_mode'):
        return
    for name in set(project_links(doc)):
        frappe.db.sql('select name from `tabProject` where name=%s for update',(name,))
        mode = frappe.db.get_value('Project', name, 'custom_pf_mode')
        if mode == 'متابعة غير مالية':
            frappe.throw('لا يمكن ربط مستند مالي بمشروع متابعة غير مالية: '+name)


def ensure_no_finance(project):
    if project.get('sales_order'):
        frappe.throw('أزل الارتباط بأمر البيع بعد مراجعته قبل تصنيف المشروع كمتابعة غير مالية.')
    for dt in FINANCIAL:
        if not frappe.db.exists('DocType', dt):
            continue
        meta = frappe.get_meta(dt)
        sources = [meta] + [frappe.get_meta(f.options) for f in meta.fields if f.fieldtype == 'Table']
        for source in sources:
            for f in source.fields:
                if f.fieldtype == 'Link' and f.options == 'Project':
                    filters = {f.fieldname: project.name}
                    if source.istable:
                        filters['parenttype'] = dt
                    if frappe.db.exists(source.name, filters):
                        frappe.throw('المشروع مرتبط بسجل مالي من نوع '+dt+'؛ راجع الارتباط قبل تغيير تصنيفه.')
    for f in ('estimated_costing','total_costing_amount','total_billing_amount','total_expense_claim',
              'total_purchase_cost','total_sales_amount','total_billed_amount'):
        if float(project.get(f) or 0):
            frappe.throw('توجد مبالغ مالية في المشروع؛ لا يمكن تحويله إلى متابعة غير مالية قبل مراجعتها.')
