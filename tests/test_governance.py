import datetime
import importlib
import sys
import types
import unittest
from unittest.mock import Mock,patch


class Denied(Exception): pass


class Doc(dict):
    def __getattr__(self,key): return self.get(key)
    def __setattr__(self,key,value): self[key]=value
    def is_new(self): return self.get('_new',False)
    def get_doc_before_save(self): return self.get('_old')
    def check_permission(self,*args): pass
    def save(self,**kwargs): return self


class GovernanceTests(unittest.TestCase):
    def setUp(self):
        self.f=types.ModuleType('frappe')
        self.f.whitelist=lambda **kw:lambda fn:fn
        self.f.session=types.SimpleNamespace(user='member@test')
        self.f.flags=types.SimpleNamespace()
        self.f.PermissionError=Denied
        self.f.throw=Mock(side_effect=Denied)
        self.f.db=Mock()
        self.f.db.exists.return_value=False
        self.f.db.get_value.return_value='P1'
        self.f.get_all=Mock(return_value=[])
        self.f.get_roles=Mock(return_value=['Employee'])
        utils=types.ModuleType('frappe.utils')
        utils.get_datetime=lambda s: s if isinstance(s,datetime.datetime) else datetime.datetime.fromisoformat(str(s))
        utils.now_datetime=lambda:datetime.datetime(2026,9,15,12)
        utils.getdate=lambda s: datetime.date.fromisoformat(str(s)[:10])
        utils.today=lambda:'2026-09-15'
        utils.add_days=lambda d,n:d+datetime.timedelta(days=n)
        self.f.utils=utils
        self.p=Doc(doctype='Project',name='P1',custom_pf_mode='متابعة غير مالية',custom_pf_manager='chair@test',custom_pf_team=[Doc(user='member@test')],status='Open',custom_pf_closed_at=None)
        self.t=Doc(doctype='Task',name='T1',project='P1',status='Working',custom_pf_assignee='member@test',custom_pf_specialization='IT',exp_end_date=datetime.datetime(2026,9,20),custom_pf_original_due=datetime.datetime(2026,9,20))
        self.f.get_doc=lambda dt,name:self.p if dt=='Project' else self.t
        self.modules=patch.dict(sys.modules,{'frappe':self.f,'frappe.utils':utils})
        self.modules.start();self.addCleanup(self.modules.stop)
        for name in ['project_followup.api','project_followup.project','project_followup.finance']:
            sys.modules.pop(name,None)
        self.api=importlib.import_module('project_followup.api')
        self.api.lock_project=lambda name:self.p

    def test_employee_cannot_approve_or_cancel(self):
        for action in ['approve','return','cancel','approve_extension','reject_extension']:
            with self.subTest(action=action),self.assertRaises(Denied):
                self.api.task_action('T1',action,reason='reason')

    def test_other_member_cannot_submit_assigned_task(self):
        self.f.session.user='other@test'
        with self.assertRaises(Denied): self.api.task_action('T1','submit',result='done')

    def test_submission_requires_result(self):
        with self.assertRaises(Denied): self.api.task_action('T1','submit',result=' ')
        self.assertEqual(self.t.status,'Working')

    def test_submission_waits_for_review(self):
        self.api.task_action('T1','submit',result='Restored service')
        self.assertEqual(self.t.status,'Pending Review')
        self.assertFalse(self.t.custom_pf_approved_by)

    def test_chair_cannot_approve_unreviewed_task(self):
        self.f.session.user='chair@test'
        with self.assertRaises(Denied): self.api.task_action('T1','approve')

    def test_chair_records_approval(self):
        self.f.session.user='chair@test'
        self.t.status='Pending Review';self.t.custom_pf_result='Completed with evidence'
        self.api.task_action('T1','approve')
        self.assertEqual(self.t.status,'Completed')
        self.assertEqual(self.t.custom_pf_approved_by,'chair@test')
        self.assertIsNone(self.f.flags.followup_action)

    def test_extension_does_not_change_deadline_until_approval(self):
        original=self.t.exp_end_date
        self.api.task_action('T1','request_extension',reason='Supplier delay',proposed_due='2026-09-22 00:00:00')
        self.assertEqual(self.t.exp_end_date,original)
        self.f.session.user='chair@test'
        self.api.task_action('T1','approve_extension')
        self.assertEqual(self.t.custom_pf_original_due,original)
        self.assertEqual(self.t.exp_end_date,'2026-09-22 00:00:00')

    def test_shorter_extension_rejected(self):
        with self.assertRaises(Denied): self.api.task_action('T1','request_extension',reason='x',proposed_due='2026-09-19 00:00:00')

    def test_project_close_rejects_open_or_unapproved_tasks(self):
        self.f.session.user='chair@test'
        for state,approver in [('Working',None),('Completed',None),('Cancelled',None)]:
            self.f.get_all.return_value=[Doc(name='T1',status=state,custom_pf_approved_by=approver)]
            with self.subTest(state=state),self.assertRaises(Denied):
                self.api.close_project('P1','مكتمل','report')

    def test_cancelled_work_cannot_be_reported_as_complete(self):
        self.f.session.user='chair@test'
        self.f.get_all.return_value=[Doc(name='T1',status='Cancelled',custom_pf_approved_by='chair@test')]
        with self.assertRaises(Denied):self.api.close_project('P1','مكتمل','report')
        self.api.close_project('P1','متوقف','Committee stopped by decision')
        self.assertEqual(self.p.status,'On hold')
        self.assertTrue(self.p.custom_pf_closed_at)

    def test_financial_project_not_governed_by_new_task_actions(self):
        self.p.custom_pf_mode='مالي'
        with self.assertRaises(Denied):self.api.task_action('T1','submit',result='done')
        self.assertEqual(self.t.status,'Working')

    def test_completed_tasks_do_not_auto_close_project(self):
        mixin=importlib.import_module('project_followup.project').FollowupProjectMixin
        class Parent(Doc):
            def update_percent_complete(self):self.native_called=True
        class Project(mixin,Parent):pass
        p=Project(self.p)
        self.f.get_all.return_value=[Doc(status='Completed',custom_pf_approved_by='chair@test')]
        p.update_percent_complete()
        self.assertEqual(p.percent_complete,100)
        self.assertEqual(p.status,'Open')
        self.f.get_all.return_value.append(Doc(status='Cancelled',custom_pf_approved_by='chair@test'))
        p.update_percent_complete()
        self.assertEqual(p.percent_complete,50)
        p.custom_pf_mode='مالي';p.update_percent_complete()
        self.assertTrue(p.native_called)

    def test_financial_links_rejected_for_nonfinancial_project(self):
        finance=importlib.import_module('project_followup.finance')
        self.f.get_meta=lambda name:types.SimpleNamespace(has_field=lambda field:True)
        self.f.db.get_value.return_value='متابعة غير مالية'
        item=Doc(doctype='Purchase Order',project='P1')
        item.meta=types.SimpleNamespace(fields=[types.SimpleNamespace(fieldtype='Link',options='Project',fieldname='project')])
        with self.assertRaises(Denied):finance.validate_financial_document(item)
        self.f.db.get_value.return_value='مالي'
        finance.validate_financial_document(item)

    def test_same_deadline_from_browser_is_not_change(self):
        old=Doc(exp_end_date=datetime.datetime(2026,9,20))
        new=Doc(exp_end_date='2026-09-20 00:00:00')
        new.meta=types.SimpleNamespace(get_field=lambda name:types.SimpleNamespace(fieldtype='Datetime'))
        self.assertFalse(self.api.changed(new,old,'exp_end_date'))

    def test_action_context_cleared_after_save_failure(self):
        original=Doc.save
        with patch.object(Doc,'save',side_effect=RuntimeError('database failure')):
            with self.assertRaises(RuntimeError):self.api.task_action('T1','submit',result='done')
        self.assertIsNone(self.f.flags.followup_action)


if __name__=='__main__':unittest.main()
