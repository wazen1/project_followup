frappe.ui.form.on('Project', {
 refresh(frm) {
  const active=frm.doc.custom_pf_mode==='متابعة غير مالية';
  for (const f of ['estimated_costing','total_costing_amount','total_billing_amount','total_expense_claim','total_purchase_cost','total_sales_amount','total_billed_amount','gross_margin','per_gross_margin','customer','sales_order']) {
   if (frm.fields_dict[f]) frm.toggle_display(f,!active);
  }
  if (!active || frm.is_new()) return;
  frm.add_custom_button('مهام المشروع',()=>frappe.set_route('List','Task',{project:frm.doc.name}));
  frm.add_custom_button('لوحة المتابعة',()=>frappe.set_route('project-followup'));
  if (frm.doc.custom_pf_closed_at) {
   frm.dashboard.set_headline_alert('المشروع مقفل بقرار معتمد: '+frappe.utils.escape_html(frm.doc.custom_pf_outcome),'green');
   return;
  }
  if (frappe.session.user!=='Administrator' && frappe.session.user!==frm.doc.custom_pf_manager) return;
  frm.add_custom_button('إضافة مهمة',()=>{
   const users=[frm.doc.custom_pf_manager,...(frm.doc.custom_pf_team||[]).map(m=>m.user)].filter(Boolean);
   frappe.prompt([
    {fieldname:'subject',label:'المهمة',fieldtype:'Data',reqd:1},
    {fieldname:'assignee',label:'المسؤول المباشر',fieldtype:'Link',options:'User',reqd:1,get_query:()=>({filters:{name:['in',users]}})},
    {fieldname:'specialization',label:'الاختصاص المطلوب',fieldtype:'Data',reqd:1},
    {fieldname:'due',label:'الموعد النهائي',fieldtype:'Datetime',reqd:1}
   ],async values=>{
    const r=await frappe.call({method:'project_followup.api.create_task',args:{project:frm.doc.name,...values},freeze:true});
    frappe.set_route('Form','Task',r.message);
   },'إضافة مهمة للجنة','إنشاء');
  });
  frm.add_custom_button('مراجعة وإقفال المشروع',()=>{
   if (frm.is_dirty()) return frappe.msgprint('احفظ التعديلات قبل الإقفال.');
   frappe.prompt([
    {fieldname:'outcome',label:'نتيجة الإقفال',fieldtype:'Select',options:'مكتمل\nمتوقف\nملغى',reqd:1},
    {fieldname:'report',label:'التقرير الختامي وسبب الإقفال',fieldtype:'Small Text',reqd:1},
    {fieldname:'actual_finish',label:'تاريخ انتهاء العمل الفعلي إن كان معروفًا',fieldtype:'Date'}
   ],async values=>{
    await frappe.call({method:'project_followup.api.close_project',args:{name:frm.doc.name,...values},freeze:true});
    await frm.reload_doc();
   },'قرار إقفال المشروع','اعتماد الإقفال');
  });
 },
 custom_pf_mode(frm) {frm.trigger('refresh');}
});
