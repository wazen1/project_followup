frappe.pages['project-followup'].on_page_load=function(wrapper) {
 const page=frappe.ui.make_app_page({parent:wrapper,title:'متابعة المشاريع واللجان',single_column:true});
 const body=$('<div dir="rtl" style="padding:24px"></div>').appendTo(page.body);
 async function load() {
  body.empty().text('جارٍ تحميل المشاريع…');
  try {
   const {message:projects}=await frappe.call('project_followup.api.overview');
   body.empty();
   if (!projects.length) body.text('لا توجد مشاريع متابعة غير مالية متاحة. اختر «متابعة غير مالية» في نمط المشروع لبدء المتابعة.');
   for (const p of projects) {
    const card=$('<section style="border:1px solid var(--border-color);border-radius:8px;padding:16px;margin-bottom:16px"></section>').appendTo(body);
    $('<button class="btn btn-link"></button>').text(p.title).on('click',()=>frappe.set_route('Form','Project',p.name)).appendTo(card);
    $('<p></p>').text('نسبة المهام المعتمدة: '+p.progress+'% — '+(p.outcome||p.status)).appendTo(card);
    const table=$('<table class="table"><thead><tr><th>المهمة</th><th>المسؤول</th><th>الموعد</th><th>الحالة</th></tr></thead><tbody></tbody></table>').appendTo(card).find('tbody');
    for (const t of p.tasks) {
     const row=$('<tr></tr>').appendTo(table);
     const cell=$('<td></td>').appendTo(row);
     $('<button class="btn btn-link"></button>').text(t.subject).on('click',()=>frappe.set_route('Form','Task',t.name)).appendTo(cell);
     $('<td></td>').text(t.custom_pf_assignee||'غير مسندة').appendTo(row);
     $('<td></td>').text(t.exp_end_date||'غير محدد').appendTo(row);
     $('<td></td>').text(t.overdue?'متأخرة — '+t.status:t.status).css('color',t.overdue?'var(--red-600)':'inherit').appendTo(row);
    }
   }
  } catch(e) {body.empty().text('تعذّر تحميل المتابعة. حاول التحديث.');}
 }
 page.set_primary_action('تحديث',load);
 load();
};
