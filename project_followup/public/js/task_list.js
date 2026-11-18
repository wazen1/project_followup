/* Task-only presentation layer for the installed Frappe Gantt 0.6 API. */
(() => {
 const styleHref = '/assets/project_followup/css/gantt.css?v=20260928-1';
 if (!document.querySelector('link[data-pf-gantt-style]')) {
  $('<link rel="stylesheet" data-pf-gantt-style>').attr('href',styleHref).appendTo(document.head);
 }
 const settings = frappe.listview_settings.Task = frappe.listview_settings.Task || {};
 settings.add_fields = [...new Set([...(settings.add_fields || []), 'status'])];
 const proto = frappe.views.GanttView && frappe.views.GanttView.prototype;
 if (!proto || proto.pf_readable_gantt) return;
 const original = proto.render_gantt;
 proto.pf_readable_gantt = true;
 proto.render_gantt = function () {
  if (this.doctype === 'Task' && (!this.tasks || !this.tasks.length)) {
   this.$result.empty();
   return;
  }
  original.call(this);
  if (this.doctype !== 'Task' || !this.gantt) return;
  const view = this;
  const root = this.$result;
  const gantt = this.gantt;
  const escape = frappe.utils.escape_html;
  const records = new Map(this.tasks.map((task, i) => [task.id, {
   task, number: i + 1, item: view.get_item(task.id) || {}
  }]));
  const statuses = {
   Open: ['مفتوحة', 'open'], Working: ['قيد التنفيذ', 'working'],
   'Pending Review': ['بانتظار المراجعة', 'review'], Completed: ['مكتملة', 'completed'],
   Cancelled: ['ملغاة', 'cancelled'], Overdue: ['متأخرة', 'overdue']
  };
  const statusFor = item => statuses[item.status] || [item.status || 'مفتوحة', 'open'];
  const date = value => value ? moment(value).format('DD/MM/YYYY') : 'غير محدد';
  const subject = record => record.item.subject || record.task.name;
  let selected = records.has(view.pf_selected_task) ? view.pf_selected_task : null;
  let allArrows = view.pf_all_arrows === undefined ? true : Boolean(view.pf_all_arrows);
  root.addClass('pf-readable-gantt');
  // Frappe's original constructor owns callbacks and persistence; only adjust its presentation.
  Object.assign(gantt.options, {bar_height: 28, padding: 44, header_height: 50, bar_corner_radius: 8, arrow_curve: 8});
  const scale = gantt.update_view_scale.bind(gantt);
  gantt.update_view_scale = function (mode) {
   scale(mode);
   if (mode === 'Day') this.options.column_width = 52;
  };
  gantt.options.custom_popup_html = task => {
   const record = records.get(task.id);
   const state = statusFor(record.item);
   return `<div class="pf-gantt-popup" dir="rtl"><strong>${escape(subject(record))}</strong><p>${escape(task.id)}</p><p>${escape(date(task.start))} — ${escape(date(task.end))}</p><span>${escape(state[0])}</span></div>`;
  };
  const showPopup = gantt.show_popup.bind(gantt);
  gantt.show_popup = function (options) {
   showPopup(options);
   const card = gantt.popup_wrapper;
   const container = gantt.$container;
   // The Gantt library supplies its own dark popup skin. Apply an explicit
   // accessible palette on each show, including when a cached CSS file is used.
   const styles = {
    background: '#ffffff', color: '#1e293b', width: '260px',
    'max-width': 'calc(100% - 24px)', border: '1px solid #cbd5e1',
    'border-radius': '10px', 'box-shadow': '0 8px 24px #0f172a26',
    'z-index': '10', 'pointer-events': 'none'
   };
   for (const [property, value] of Object.entries(styles)) card.style.setProperty(property,value,'important');
   card.querySelectorAll('.pf-gantt-popup, .pf-gantt-popup *').forEach(element => {
    element.style.setProperty('color','#1e293b','important');
   });
   const content = card.querySelector('.pf-gantt-popup');
   if (content) {
    content.style.setProperty('background','#ffffff','important');
    content.style.setProperty('padding','12px 16px');
    content.style.setProperty('line-height','1.7');
   }
   const pointer = card.querySelector('.pointer');
   if (pointer) pointer.style.setProperty('display','none','important');
   const left = parseFloat(card.style.left) || 0;
   const top = parseFloat(card.style.top) || 0;
   card.style.left = Math.max(container.scrollLeft + 8, Math.min(left, container.scrollLeft + container.clientWidth - card.offsetWidth - 12)) + 'px';
   card.style.top = Math.max(container.scrollTop + 8, Math.min(top, container.scrollTop + container.clientHeight - card.offsetHeight - 12)) + 'px';
  };
  const onViewChange = gantt.options.on_view_change;
  gantt.options.on_view_change = mode => {
   if (onViewChange) onViewChange(mode);
   requestAnimationFrame(decorate);
  };
  gantt.refresh(this.tasks.map(task => ({...task,
   name: String(records.get(task.id).number),
   custom_class: 'pf-state-' + statusFor(records.get(task.id).item)[1]
  })));
  const supportedModes = new Set(['Day','Week','Month','Year']);
  view.$paging_area.find('.btn-view-mode').each(function () {
   if (!supportedModes.has(String($(this).data('value')))) $(this).remove();
  });
  const pager = view.$paging_area.find('.btn-paging').first().parent();
  if (pager.length && !pager.children('.pf-paging-label').length) {
   $('<span class="pf-paging-label"></span>').text('عدد المهام').prependTo(pager);
  }
  const timeline = root.children('.gantt-container').detach().addClass('pf-timeline');
  const toolbar = $('<div class="pf-gantt-toolbar" dir="rtl"></div>');
  const toolbarCopy = $('<div class="pf-gantt-toolbar-copy"></div>').appendTo(toolbar);
  $('<strong class="pf-gantt-title"></strong>').text('مخطط التنفيذ').appendTo(toolbarCopy);
  const hint = $('<span class="pf-gantt-hint" role="status"></span>').text('اختر رقم المهمة لعرض روابطها، أو اضغط اسمها لفتح التفاصيل.').appendTo(toolbarCopy);
  const tools = $('<div class="pf-gantt-tools"></div>').appendTo(toolbar);
  const completedCount = [...records.values()].filter(record => statusFor(record.item)[1] === 'completed').length;
  const overdueCount = [...records.values()].filter(record => statusFor(record.item)[1] === 'overdue').length;
  $('<span class="pf-summary-chip pf-summary-total"></span>').text(records.size+' مهام').appendTo(tools);
  if (completedCount) $('<span class="pf-summary-chip pf-summary-completed"></span>').text(completedCount+' مكتملة').appendTo(tools);
  if (overdueCount) $('<span class="pf-summary-chip pf-summary-overdue"></span>').text(overdueCount+' متأخرة').appendTo(tools);
  const toggleLabel = $('<label class="pf-gantt-toggle"></label>').appendTo(tools);
  const toggle = $('<input type="checkbox">').prop('checked',allArrows).appendTo(toggleLabel);
  $('<span></span>').text('إظهار كل الأسهم').appendTo(toggleLabel);
  $('<button type="button" class="btn btn-xs btn-default pf-clear-selection"></button>').text('إلغاء التحديد').on('click',()=>select(null)).appendTo(tools);
  root.prepend(toolbar);
  const layout = $('<div class="pf-gantt-layout"></div>').appendTo(root);
  timeline.appendTo(layout);
  gantt.set_scroll_position();
  const labels = $('<div class="pf-gantt-labels" dir="rtl"></div>').appendTo(layout);
  const labelHeader = $('<div class="pf-gantt-label-header"></div>').appendTo(labels);
  $('<span></span>').text('المهام والمواعيد').appendTo(labelHeader);
  $('<small></small>').text(records.size).appendTo(labelHeader);
  for (const [id, record] of records) {
   const row = $('<div class="pf-task-row"></div>').attr('data-id',id).appendTo(labels);
   $('<button type="button" class="pf-task-number"></button>').text(record.number)
    .attr({'aria-label':'عرض تبعيات '+subject(record),'aria-pressed':'false'})
    .on('click',()=>select(selected===id?null:id)).appendTo(row);
   const content = $('<div class="pf-task-content"></div>').appendTo(row);
   $('<button type="button" class="pf-task-title"></button>').text(subject(record)).attr('title',subject(record))
    .on('click',()=>frappe.set_route('Form','Task',id)).appendTo(content);
   const meta = $('<div class="pf-task-meta"></div>').appendTo(content);
   $('<span></span>').text(date(record.task.start)+' — '+date(record.task.end)).appendTo(meta);
   $('<span class="pf-task-status"></span>').addClass('pf-status-'+statusFor(record.item)[1]).text(statusFor(record.item)[0]).appendTo(meta);
  }
  toggle.on('change',()=>{allArrows=toggle.prop('checked');view.pf_all_arrows=allArrows;decorate();});
  function select(id) {
   selected=id;view.pf_selected_task=id;
   hint.text(id ? 'المهمة '+records.get(id).number+': '+subject(records.get(id)) : 'اختر رقم المهمة لعرض روابطها، أو اضغط اسمها لفتح التفاصيل.');
   decorate();
  }
  function decorate() {
   const svg = gantt.$svg;
   // Hide unused whitespace, retain enough bottom room for dependency curves.
   const chartHeight = gantt.options.header_height+gantt.options.padding+records.size*(gantt.options.bar_height+gantt.options.padding);
   svg.setAttribute('height',chartHeight);
   timeline.css('height',(chartHeight+10)+'px');
   svg.querySelectorAll('.arrow path').forEach(path=>{
    const connected=selected && (path.dataset.from===selected || path.dataset.to===selected);
    path.style.display=(allArrows||connected)?'':'none';
    path.classList.toggle('pf-active-arrow',Boolean(connected));
   });
   root.find('.pf-task-row').each(function(){
    const active=this.dataset.id===selected;
    this.classList.toggle('pf-selected',active);
    $(this).find('.pf-task-number').attr('aria-pressed',String(active));
   });
   svg.querySelectorAll('.bar-wrapper').forEach(bar=>bar.classList.toggle('pf-selected',bar.dataset.id===selected));
  }
  decorate();
 };
})();
