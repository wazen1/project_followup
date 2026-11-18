frappe.ui.form.on('Task', {
 async refresh(frm) {
  const status_field = frm.get_docfield('status');
  if (frm.__pf_status_read_only === undefined) frm.__pf_status_read_only = status_field.read_only || 0;
  frm.set_df_property('status', 'read_only', frm.__pf_status_read_only);
  if (!frm.doc.project) return;
  const {message:project}=await frappe.db.get_value('Project',frm.doc.project,['custom_pf_mode','custom_pf_manager']);
  const active=project.custom_pf_mode==='متابعة غير مالية';
  for (const name of Object.keys(frm.fields_dict).filter(n=>n.startsWith('custom_pf_'))) frm.toggle_display(name,active);
  if (!active) return;
  frm.set_df_property('status', 'read_only', 1);
  frm.set_df_property('custom_pf_assignee','reqd',1);
  frm.set_df_property('custom_pf_specialization','reqd',1);
  frm.set_df_property('exp_end_date','reqd',1);
  if (frm.is_new()) {
   const parent=await frappe.db.get_doc('Project',frm.doc.project);
   frm.set_query('custom_pf_assignee',()=>({filters:{name:['in',[parent.custom_pf_manager,...(parent.custom_pf_team||[]).map(m=>m.user)].filter(Boolean)]}}));
   return;
  }
  const {message:ctx}=await frappe.call({method:'project_followup.api.task_context',args:{name:frm.doc.name}});
  if (!ctx.managed || ctx.closed) return;
  frm.set_query('custom_pf_assignee',()=>({filters:{name:['in',ctx.members]}}));
  const done=['Completed','Cancelled'].includes(frm.doc.status)&&frm.doc.custom_pf_approved_by;
  if (done) return;
  function action(label,code,fields=[]) {
   frm.add_custom_button(label,()=>{
    const run=async values=>{
     if (frm.is_dirty()) {
      await frm.save();
      if (frm.is_dirty()) return;
     }
     await frappe.call({method:'project_followup.api.task_action',args:{name:frm.doc.name,action:code,...values},freeze:true});
     await frm.reload_doc();
    };
    if (fields.length) frappe.prompt(fields,run,label,'تأكيد');
    else frappe.confirm('تأكيد: '+label+'؟',()=>run({}));
   });
  }
  const reason={fieldname:'reason',label:'السبب / ملاحظات المراجعة',fieldtype:'Small Text',reqd:1};
  if (ctx.assignee||ctx.manager) {
   if (['Open','Overdue'].includes(frm.doc.status)) action('بدء التنفيذ','start');
   if (['Open','Working','Overdue','Completed'].includes(frm.doc.status)) action('تقديم للمراجعة','submit',[{fieldname:'result',label:'نتيجة العمل',fieldtype:'Small Text',reqd:1,default:frm.doc.custom_pf_result}]);
   if (frm.doc.custom_pf_extension_state!=='بانتظار الموافقة') action('طلب تمديد','request_extension',[reason,{fieldname:'proposed_due',label:'الموعد الجديد المطلوب',fieldtype:'Datetime',reqd:1}]);
  }
  if (ctx.manager) {
   if (frm.doc.status==='Pending Review') {action('اعتماد الإنجاز وإقفال المهمة','approve');action('إعادة للتنفيذ','return',[reason]);}
   action('إلغاء المهمة بقرار','cancel',[reason]);
   if (frm.doc.custom_pf_extension_state==='بانتظار الموافقة') {action('اعتماد التمديد','approve_extension');action('رفض التمديد','reject_extension',[reason]);}
  }
 },
 project(frm) {frm.trigger('refresh');}
});
