"""Store-specific copy must never invent a product or carry another product's traits."""
import copy,unittest
from unittest.mock import patch
from planner import caption_for,clean_project,validate_plan,PlanError
from copy_rules import recover_details
from session_store import restore_session
from test_invariants import sample,make_plan

class StoreCopy(unittest.TestCase):
    def test_category_only_is_not_guessed_into_a_coffee_name(self):
        p=self.project(product='咖啡',detail=None);plan=make_plan(p)
        self.assertTrue(plan['copy_notes']);text=caption_for('product',p['facts'],'visit')[0]
        self.assertIn('咖啡',text);self.assertNotIn('拿铁',text)

    def project(self,shop='梧桐咖啡',product='生椰拿铁',detail='使用椰乳'):
        p=sample();p['facts'][0]['value']=shop;p['facts'][1]['value']=product
        from evidence_store import identity
        for shot in p['shots']:
            shot['product_binding'].update(value=product,evidence_id=identity(shot))
        if detail:p['facts'].append({'id':'details','kind':'product_detail','value':detail,'confirmed':True,
                                    'source':'程序构造的模拟事实','product_ref':{'id':'f2','value':product}})
        return p

    def test_two_coffees_and_bakery_have_distinct_specific_copy(self):
        choices=[('梧桐咖啡','生椰拿铁','使用椰乳'),('巷口咖啡','燕麦拿铁','使用燕麦奶'),('小麦面包房','原味可颂','当日烘焙')]
        texts=[]
        for shop,product,detail in choices:
            p=self.project(shop,product,detail);clean_project(p);text,refs=caption_for('product',p['facts'],'visit')
            self.assertIn(shop,text);self.assertIn(product,text);self.assertIn(detail,text)
            self.assertEqual(refs,['f1','f2','details']);texts.append(text)
        self.assertEqual(len(set(texts)),3)

    def test_no_details_does_not_invent_marketing_claims(self):
        p=self.project(detail=None);text,refs=caption_for('product',p['facts'],'visit')
        for claim in ('招牌','低糖','低卡','现磨','手作','椰乳','最受欢迎'):self.assertNotIn(claim,text)
        self.assertNotIn('details',refs);self.assertTrue(validate_plan(p,make_plan(p)))

    def test_unconfirmed_details_ignored(self):
        p=self.project();p['facts'][-1]['confirmed']=False
        for goal in ('visit','attract','promo'):
            text,refs=caption_for('product',p['facts'],goal)
            self.assertNotIn('使用椰乳',text);self.assertNotIn('details',refs)

    def test_wrong_product_traits_cannot_be_confirmed(self):
        p=self.project();p['facts'][-1]['product_ref']['value']='燕麦拿铁'
        with self.assertRaisesRegex(PlanError,'商品特点'):clean_project(p)
        text,refs=caption_for('product',p['facts'],'visit')
        self.assertNotIn('使用椰乳',text);self.assertNotIn('details',refs)

    def test_unconfirmed_product_cannot_support_confirmed_traits(self):
        p=self.project();p['facts'][1]['confirmed']=False
        with self.assertRaisesRegex(PlanError,'商品特点'):clean_project(p)

    def test_no_product_reference_rejected(self):
        p=self.project();p['facts'][-1].pop('product_ref')
        with self.assertRaisesRegex(PlanError,'商品特点'):clean_project(p)

    def test_renaming_product_recovers_details_as_unconfirmed_draft(self):
        p=self.project();p['facts'][1]['value']='燕麦拿铁'
        recovered=recover_details(p)
        self.assertEqual(recovered['facts'][-1]['value'],'使用椰乳');self.assertFalse(recovered['facts'][-1]['confirmed'])
        self.assertTrue(p['facts'][-1]['confirmed']);self.assertTrue(recovered['warnings'])
        with patch('session_store.reconcile',side_effect=lambda x:{**x,'warnings':[]}):restored=restore_session(p)
        self.assertFalse(restored['facts'][-1]['confirmed']);self.assertIn('商品特点',' '.join(restored['warnings']))

    def test_changed_details_invalidates_previous_copy(self):
        p=self.project();plan=make_plan(p);p['facts'][-1]['value']='使用燕麦奶'
        with self.assertRaisesRegex(PlanError,'文案'):validate_plan(p,plan)

    def test_promotional_conditions_and_validity_remain_complete(self):
        p=self.project();text,refs=caption_for('product',p['facts'],'promo')
        for i in (0,1,3,4,5):self.assertIn(p['facts'][i]['value'],text)
        self.assertEqual(refs,['f1','f2','details','f4','f5'])

    def test_other_roles_use_shop_without_claiming_product_process(self):
        p=self.project()
        for role in ('storefront','process','interior'):
            text,refs=caption_for(role,p['facts'],'visit')
            self.assertIn('梧桐咖啡',text);self.assertIn('f1',refs)
            self.assertNotIn('生椰拿铁',text);self.assertNotIn('使用椰乳',text)

    def test_unconfirmed_shop_not_named_in_other_roles(self):
        p=self.project();p['facts'][0]['confirmed']=False
        for role in ('storefront','process','interior'):
            text,refs=caption_for(role,p['facts'],'visit')
            self.assertNotIn('梧桐咖啡',text);self.assertNotIn('f1',refs)

    def test_environment_copy_does_not_invent_indoor_seating(self):
        p=self.project(shop='街角小吃档',product='炸豆腐',detail=None)
        text,refs=caption_for('interior',p['facts'],'visit')
        self.assertIn('街角小吃档',text);self.assertIn('门店环境',text)
        self.assertNotIn('店内',text);self.assertNotIn('堂食',text);self.assertNotIn('包间',text)
        self.assertEqual(refs,['f1'])

    def test_old_indoor_environment_text_requires_replanning(self):
        p=self.project();plan=make_plan(p)
        self.assertTrue(validate_plan(p,plan))
        segment=next(segment for segment in plan['segments'] if segment['role']=='interior')
        segment['text']=segment['text'].replace('门店环境','店内环境')
        with self.assertRaisesRegex(PlanError,'文案'):validate_plan(p,plan)

    def test_malformed_import_still_reaches_project_validation(self):
        p=self.project();p['facts'].insert(0,None)
        recovered=recover_details(p)
        with self.assertRaises(PlanError):clean_project(recovered)

if __name__=='__main__':unittest.main()
